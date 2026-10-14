"""netz_export.py -- int8-TFLite -> modell_netz.h fuer die eigenen Kerne (netz_int8.h)

Liest Gewichte und Quantisierungsparameter aus dem int8-Modell und
schreibt sie als C-Arrays. Die Multiplikatoren werden genau wie in
TensorFlow Lite berechnet (QuantizeMultiplier), damit die Firmware
dieselben Zahlen erhaelt wie der Referenzinterpreter.

    from netz_export import netz_header, netz_pruefen
"""
import math
from pathlib import Path

import numpy as np


def _quant_mult(m):
    """TFLite QuantizeMultiplier: m = q * 2^shift, q in [2^30, 2^31)."""
    if m == 0:
        return 0, 0
    q, shift = math.frexp(m)
    qf = int(round(q * (1 << 31)))
    if qf == (1 << 31):
        qf //= 2
        shift += 1
    if shift < -31:
        return 0, 0
    return qf, shift


def _interp(blob):
    import tensorflow as tf
    it = tf.lite.Interpreter(
        model_content=blob,
        experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF,
        experimental_preserve_all_tensors=True)
    it.allocate_tensors()
    return it


def _schichten(it):
    T = {t["index"]: t for t in it.get_tensor_details()}
    ops = it._get_ops_details()
    qp = lambda i: T[i]["quantization_parameters"]
    conv = [o for o in ops if o["op_name"] == "CONV_2D"]
    fc = [o for o in ops if o["op_name"] == "FULLY_CONNECTED"]
    mean = [o for o in ops if o["op_name"] == "MEAN"]
    if len(conv) != 3 or len(fc) != 2 or len(mean) != 1:
        raise ValueError("Unerwarteter Modellaufbau -- netz_int8.h erwartet 3 Conv, Mean, 2 Dense")
    return T, ops, qp, conv, fc, mean[0]


def _gewichtet(it, o, qp, T):
    ein, w_i, b_i = o["inputs"][:3]
    aus = o["outputs"][0]
    s_ein = float(np.float32(qp(ein)["scales"][0]))
    zp_ein = int(qp(ein)["zero_points"][0])
    s_aus = float(np.float32(qp(aus)["scales"][0]))
    zp_aus = int(qp(aus)["zero_points"][0])
    sw = qp(w_i)["scales"].astype(np.float32)
    W = it.get_tensor(w_i).astype(np.int8)
    B = it.get_tensor(b_i).astype(np.int32)
    n = W.shape[0]
    if len(sw) == 1:
        sw = np.repeat(sw, n)
    mult, shift = zip(*[_quant_mult(s_ein * float(s) / s_aus) for s in sw])
    return dict(W=W, B=B, mult=np.array(mult, np.int64), shift=np.array(shift, np.int64),
                zp_ein=zp_ein, zp_aus=zp_aus, s_aus=s_aus, n=n)


def _arr(name, typ, werte, je_zeile=16):
    werte = [int(v) for v in np.asarray(werte).ravel()]
    zeilen = [", ".join(str(v) for v in werte[i:i + je_zeile]) for i in range(0, len(werte), je_zeile)]
    return f"static const {typ} {name}[{len(werte)}] = {{\n  " + ",\n  ".join(zeilen) + "\n};\n"


def netz_header(blob, ziel):
    """Schreibt modell_netz.h und gibt die Kenngroessen zurueck."""
    it = _interp(blob)
    T, ops, qp, conv, fc, mean = _schichten(it)
    ein = it.get_input_details()[0]
    s_e, zp_e = ein["quantization"]
    L = [_gewichtet(it, o, qp, T) for o in conv]
    D = [_gewichtet(it, o, qp, T) for o in fc]
    m_ein, m_aus = mean["inputs"][0], mean["outputs"][0]
    s_mi = float(np.float32(qp(m_ein)["scales"][0])); zp_mi = int(qp(m_ein)["zero_points"][0])
    s_mo = float(np.float32(qp(m_aus)["scales"][0])); zp_mo = int(qp(m_aus)["zero_points"][0])
    lin = int(ein["shape"][1]); k = int(T[conv[0]["inputs"][1]]["shape"][2])
    l1 = lin - k + 1; l2 = l1 // 2 - k + 1; l3 = l2 // 2 - k + 1

    teile = ["/*\n * modell_netz.h  --  automatisch erzeugt von tools/export_firmware_model.py\n"
             " * Gewichte fuer netz_int8.h (eigene Kerne ohne TFLite Micro).\n"
             " * Nicht von Hand bearbeiten -- neu erzeugen.\n */\n"
             "#ifndef MODELL_NETZ_H\n#define MODELL_NETZ_H\n#include <stdint.h>\n\n",
             f"#define NETZ_LEN {lin}\n#define NETZ_KANAELE {int(ein['shape'][2])}\n#define NETZ_K {k}\n",
             f"#define NETZ_L1 {l1}\n#define NETZ_L2 {l2}\n#define NETZ_L3 {l3}\n",
             f"#define NETZ_C1 {L[0]['n']}\n#define NETZ_C2 {L[1]['n']}\n#define NETZ_C3 {L[2]['n']}\n"
             f"#define NETZ_D1 {D[0]['n']}\n",
             f"#define NETZ_EIN_SKALA {s_e:.9g}f\n#define NETZ_EIN_NULL {int(zp_e)}\n#define NETZ_ZP_EIN {int(zp_e)}\n"]
    for i, l in enumerate(L, 1):
        teile.append(f"#define NETZ_ZP{i} {l['zp_aus']}\n#define NETZ_AKT{i} {max(-128, l['zp_aus'])}\n")
    if zp_mi != L[2]["zp_aus"]:
        raise ValueError("Mean-Eingang hat anderen Nullpunkt als die letzte Faltung")
    teile.append(f"#define NETZ_ZP_MEAN {zp_mo}\n"
                 f"#define NETZ_MEAN_FAKTOR {s_mi / (s_mo * l3):.9g}f\n")
    teile.append(f"#define NETZ_ZPD1 {D[0]['zp_aus']}\n#define NETZ_AKTD1 {max(-128, D[0]['zp_aus'])}\n"
                 f"#define NETZ_ZPD2 {D[1]['zp_aus']}\n#define NETZ_SKALA_D2 {D[1]['s_aus']:.9g}f\n\n")
    for i, l in enumerate(L, 1):
        W = l["W"][:, 0, :, :]                     # [cout][k][cin]
        teile += [_arr(f"netz_w{i}", "int8_t", W), _arr(f"netz_b{i}", "int32_t", l["B"]),
                  _arr(f"netz_m{i}", "int32_t", l["mult"]), _arr(f"netz_s{i}", "int8_t", l["shift"])]
    for i, l in enumerate(D, 1):
        teile += [_arr(f"netz_wd{i}", "int8_t", l["W"]), _arr(f"netz_bd{i}", "int32_t", l["B"]),
                  _arr(f"netz_md{i}", "int32_t", l["mult"]), _arr(f"netz_sd{i}", "int8_t", l["shift"])]
    teile.append("\n#endif\n")
    Path(ziel).write_text("".join(teile))
    return dict(skala=s_e, null=zp_e)


def netz_pruefen(blob, fenster_int8, cxx="g++"):
    """Kompiliert netz_int8.h am PC und vergleicht jede Schicht mit TFLite.

    fenster_int8: Array [n, 100, 6] int8. Gibt ein dict zurueck: Anteil
    gleicher roher Ausgaenge und Entscheidungen, max. Abweichung von p,
    Zahl der Fenster, in denen die Faltungen nicht bitgleich sind.
    """
    import subprocess, tempfile
    fw = Path(__file__).resolve().parents[1] / "firmware" / "CleverSole"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        netz_header(blob, tmp / "modell_netz.h")
        (tmp / "netz_int8.h").write_text((fw / "netz_int8.h").read_text())
        (tmp / "t.cpp").write_text(r'''
#include <cstdio>
#include "netz_int8.h"
int main(){ int n; if(scanf("%d",&n)!=1) return 1; static int8_t x[NETZ_LEN*NETZ_KANAELE];
 for(int j=0;j<n;j++){ for(int i=0;i<NETZ_LEN*NETZ_KANAELE;i++){int v; scanf("%d",&v); x[i]=(int8_t)v;}
  float p=netzRechnen(x); printf("%d %.6f", (int)netz_roh_aus, p);
  for(int i=0;i<NETZ_C3;i++) printf(" %d",(int)netz_mittel[i]);
  long s=0; for(int i=0;i<NETZ_L3*NETZ_C3;i++) s+=netz_p5[i]*(i%7+1); printf(" %ld\n",s);} }''')
        subprocess.run([cxx, "-O2", "-o", str(tmp / "t"), str(tmp / "t.cpp")], check=True)
        eingabe = f"{len(fenster_int8)}\n" + "\n".join(" ".join(map(str, f.ravel())) for f in fenster_int8)
        aus = subprocess.run([str(tmp / "t")], input=eingabe, capture_output=True, text=True, check=True).stdout.split("\n")
    it = _interp(blob)
    T, ops, qp, conv, fc, mean = _schichten(it)
    ei, ao = it.get_input_details()[0], it.get_output_details()[0]
    gleich, dp, schicht, entsch = 0, 0.0, 0, 0
    for f, zeile in zip(fenster_int8, aus):
        it.set_tensor(ei["index"], f[None].astype(np.int8)); it.invoke()
        werte = zeile.split()
        roh_c, p_c = int(werte[0]), float(werte[1])
        mittel_c = np.array(werte[2:2 + 128], int)
        s_c = int(werte[-1])
        roh_ref = int(it.get_tensor(fc[1]["outputs"][0]).ravel()[0])
        p_ref = (int(it.get_tensor(ao["index"]).ravel()[0]) - int(ao["quantization"][1])) * float(ao["quantization"][0])
        p5 = it.get_tensor(conv[2]["outputs"][0]).ravel().astype(np.int64)
        s_ref = int((p5 * (np.arange(p5.size) % 7 + 1)).sum())
        m_ref = it.get_tensor(mean["outputs"][0]).ravel()
        gleich += roh_c == roh_ref
        dp = max(dp, abs(p_c - p_ref))
        schicht += int(s_c != s_ref)              # Faltungen muessen bitgleich sein
        entsch += (p_c > 0.5) == (p_ref > 0.5)
    n = len(fenster_int8)
    return dict(roh_gleich=gleich / n, entscheidung_gleich=entsch / n,
                max_dp=dp, faltung_abweichend=schicht)
