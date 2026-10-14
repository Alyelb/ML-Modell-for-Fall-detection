"""
export_firmware_model.py  --  Keras-Modell -> int8-TFLite -> modell.h
======================================================================
Erzeugt aus einem trainierten Modell die Datei
firmware/CleverSole/modell.h, die die Firmware direkt einbindet.

Aufruf (im Repo-Ordner):
    python tools/export_firmware_model.py fall_model_lowerlimb_aug.keras Pilotdaten/

    Argument 1: Keras-Modell (.keras)
    Argument 2: Ordner mit Pilotaufnahmen (DatenLogger-CSV). Dient als
                repraesentativer Datensatz fuer die int8-Kalibrierung
                und zur Kontrolle, dass int8 und float uebereinstimmen.
    Argument 3: (optional) Name der Zieldatei in firmware/CleverSole/,
                Standard: modell_sohle.h

BatchNorm-Schichten werden vorher automatisch in die folgende Faltung
bzw. Dense-Schicht eingerechnet (siehe bn_falten).

Ausgabe:
    firmware/CleverSole/modell_netz.h  Gewichte fuer die eigenen Kerne
                                       (netz_int8.h, Standard der Firmware)
    firmware/CleverSole/<Argument 3>   C-Array, 16-Byte-ausgerichtet
    <modell>_int8.tflite             zum Archivieren
    Liste der verwendeten Operatoren (muss zum Resolver in
    CleverSole.ino passen).
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fall_lib as fl  # noqa: E402


def bn_falten(m):
    """Rechnet jede BatchNormalization in die folgende Conv1D/Dense ein.

    TFLM wertet die aus BatchNorm entstehenden MUL/ADD-Operationen mit
    Broadcast auf dem ESP32-C6 falsch aus (konstante Ausgabe). Nach der
    Faltung bleiben nur CONV_2D, FULLY_CONNECTED, Pooling und Aktivierung.
    BN(x) = s*x + t je Kanal. MaxPooling darf dazwischen liegen, wenn alle
    s > 0 (dann vertauschbar); GlobalAveragePooling und Dropout sind linear.
    Gibt (neues Modell, Anzahl gefalteter Schichten) zurueck.
    """
    from tensorflow import keras
    from tensorflow.keras import layers

    neu, offen, n = [], None, 0
    for lay in m.layers:
        if isinstance(lay, layers.BatchNormalization):
            g, b, mu, var = [w.astype(np.float64) for w in lay.get_weights()]
            s = g / np.sqrt(var + lay.epsilon)
            offen = (s, b - mu * s)
            n += 1
            continue
        if offen is not None and isinstance(lay, layers.MaxPooling1D) and not np.all(offen[0] > 0):
            raise ValueError("BatchNorm mit negativem Faktor vor MaxPooling -- nicht faltbar")
        if offen is not None and isinstance(lay, (layers.Conv1D, layers.Dense)):
            s, t = offen
            W, bias = [w.astype(np.float64) for w in lay.get_weights()]
            if isinstance(lay, layers.Conv1D):
                W2 = W * s[None, :, None]
                b2 = bias + np.einsum("kio,i->o", W, t)
            else:
                W2 = W * s[:, None]
                b2 = bias + t @ W
            kopie = lay.__class__.from_config(lay.get_config())
            neu.append((kopie, [W2.astype(np.float32), b2.astype(np.float32)]))
            offen = None
            continue
        kopie = lay.__class__.from_config(lay.get_config())
        neu.append((kopie, lay.get_weights()))
    if offen is not None:
        raise ValueError("BatchNorm am Modellende -- keine Folgeschicht zum Einrechnen")
    if n == 0:
        return m, 0
    f = keras.Sequential([layers.Input(shape=m.input_shape[1:])] + [k for k, _ in neu])
    for k, w in neu:
        if w:
            k.set_weights(w)
    return f, n


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    modell_pfad, pilot = Path(sys.argv[1]), Path(sys.argv[2])
    import tensorflow as tf
    from tensorflow import keras

    m_orig = keras.models.load_model(modell_pfad, compile=False)
    m, n_bn = bn_falten(m_orig)

    trials = fl.load_pilot(pilot, verbose=False)
    X, y, _, _ = fl.build_windows(trials, mode="sliding")
    X = fl.znorm(X).astype(np.float32)
    rng = np.random.default_rng(0)
    # Kalibrierung: alle Sturzfenster plus zufaellige ADL-Fenster, damit
    # auch die grossen Amplituden der Stuerze den Wertebereich bestimmen
    idx = np.r_[np.where(y == 1)[0],
                rng.choice(np.where(y == 0)[0], min(400, int((y == 0).sum())),
                           replace=False)]
    rng.shuffle(idx)
    X_cal = X[idx]
    if n_bn:
        d = np.abs(m.predict(X, batch_size=512, verbose=0)
                   - m_orig.predict(X, batch_size=512, verbose=0)).max()
        print(f"BatchNorm       : {n_bn} Schichten eingerechnet, max. Abweichung {d:.1e}")
        if d > 1e-3:
            sys.exit("Faltung weicht ab -- Export abgebrochen")

    def gen():
        for i in range(len(X_cal)):
            yield [X_cal[i:i + 1]]

    conv = tf.lite.TFLiteConverter.from_keras_model(m)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = gen
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    blob = conv.convert()
    tfl_pfad = modell_pfad.with_name(modell_pfad.stem + "_int8.tflite")
    tfl_pfad.write_bytes(blob)

    # --- Kontrolle: int8 gegen float auf allen Pilotfenstern ---------
    it = tf.lite.Interpreter(
        model_content=blob,
        experimental_op_resolver_type=tf.lite.experimental.OpResolverType
        .BUILTIN_WITHOUT_DEFAULT_DELEGATES)   # echte Operatoren, ohne XNNPACK
    it.allocate_tensors()
    ein, aus = it.get_input_details()[0], it.get_output_details()[0]
    s_in, z_in = ein["quantization"]
    s_out, z_out = aus["quantization"]
    p_int8 = np.empty(len(X))
    for i in range(len(X)):
        q = np.clip(np.round(X[i:i + 1] / s_in) + z_in, -128, 127).astype(np.int8)
        it.set_tensor(ein["index"], q)
        it.invoke()
        p_int8[i] = (it.get_tensor(aus["index"]).astype(np.float32).ravel()[0] - z_out) * s_out
    p_float = m.predict(X, batch_size=512, verbose=0).ravel()
    gleich = np.mean((p_int8 > 0.5) == (p_float > 0.5))
    ops = sorted({o["op_name"] for o in it._get_ops_details()})

    print(f"Modell          : {modell_pfad.name}  ({m.count_params():,} Parameter)")
    print(f"int8-TFLite     : {len(blob)/1024:.1f} KB -> {tfl_pfad.name}")
    print(f"Eingang         : scale={s_in:.6f} zero_point={z_in}")
    print(f"Ausgang         : scale={s_out:.6f} zero_point={z_out}")
    print(f"int8 vs. float  : {gleich:.2%} gleiche Entscheidungen auf {len(X)} Pilotfenstern, "
          f"max. |dp| = {np.abs(p_int8 - p_float).max():.3f}")
    print(f"Operatoren      : {', '.join(ops)}")
    if {"MUL", "ADD"} & set(ops):
        print("WARNUNG         : MUL/ADD mit Broadcast im Graphen. TFLM wertet"
              " diese auf dem ESP32-C6 falsch aus (konstante Ausgabe)."
              " BatchNorm vor dem Export in die Folgeschichten einrechnen.")

    # --- Selbsttest: konstante Eingaben, Sollwerte fuer die Firmware ----
    # Die Firmware rechnet dieselben Muster und vergleicht. Schlaegt der
    # Test fehl, rechnet TFLM anders als der Konverter -- dann stimmt
    # keine der spaeteren Zahlen.
    muster = [0, -5, 10, 13, -13]
    soll = []
    for v in muster:
        it.set_tensor(ein["index"], np.full(ein["shape"], v, np.int8))
        it.invoke()
        soll.append(int(it.get_tensor(aus["index"]).ravel()[0]))
    print(f"Selbsttest      : {dict(zip(muster, soll))}")

    # --- modell.h schreiben ---------------------------------------------
    hexz = [", ".join(f"0x{b:02x}" for b in blob[i:i + 12])
            for i in range(0, len(blob), 12)]
    name = sys.argv[3] if len(sys.argv) > 3 else "modell_sohle.h"
    ziel = Path(__file__).resolve().parents[1] / "firmware" / "CleverSole" / name
    waechter = name.upper().replace(".", "_")
    ziel.write_text(
        "/*\n"
        " * modell.h  --  automatisch erzeugt von tools/export_firmware_model.py\n"
        f" * Quelle      : {modell_pfad.name}\n"
        f" * Groesse     : {len(blob)} Byte (int8)\n"
        f" * Operatoren  : {', '.join(ops)}\n"
        f" * int8/float  : {gleich:.2%} gleiche Entscheidungen (Pilotdaten)\n"
        " * Nicht von Hand bearbeiten -- neu erzeugen.\n"
        " */\n"
        f"#ifndef {waechter}\n#define {waechter}\n\n"
        "#define MODELL_VERFUEGBAR 1\n\n"
        "// Selbsttest: konstanter Eingang -> erwarteter roher int8-Ausgang.\n"
        "// Von tools/export_firmware_model.py aus genau diesem Modell\n"
        "// berechnet; die Firmware prueft damit beim Start, ob TFLM\n"
        "// dasselbe rechnet wie der Konverter.\n"
        f"#define MODELL_TEST_N      {len(muster)}\n"
        f"#define MODELL_TEST_MUSTER {{ {', '.join(str(v) for v in muster)} }}\n"
        f"#define MODELL_TEST_SOLL   {{ {', '.join(str(v) for v in soll)} }}\n\n"
        f"alignas(16) const unsigned char modell_tflite[] = {{\n  "
        + ",\n  ".join(hexz) + "\n};\n"
        f"const unsigned int modell_tflite_len = {len(blob)};\n\n"
        "#endif\n")
    print(f"geschrieben     : {ziel}")

    # --- eigene Kerne (netz_int8.h): Gewichte schreiben und pruefen -----
    from netz_export import netz_header, netz_pruefen
    netz_ziel = ziel.with_name("modell_netz.h")
    netz_header(blob, netz_ziel)
    q_all = np.clip(np.round(X / s_in) + z_in, -128, 127).astype(np.int8)
    auswahl = np.r_[np.where(y == 1)[0], np.where(y == 0)[0][:300]]
    try:
        erg = netz_pruefen(blob, q_all[auswahl])
        print(f"eigene Kerne    : Faltungen bitgleich in "
              f"{1 - erg['faltung_abweichend'] / len(auswahl):.1%} der Fenster, "
              f"Entscheidung gleich {erg['entscheidung_gleich']:.1%}, max. |dp| {erg['max_dp']:.3f}")
    except FileNotFoundError:
        print("eigene Kerne    : kein C++-Compiler (g++) gefunden -- Pruefung uebersprungen")
    print(f"geschrieben     : {netz_ziel}")


if __name__ == "__main__":
    main()
