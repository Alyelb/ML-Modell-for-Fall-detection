"""
export_firmware_model.py  --  Keras-Modell -> int8-TFLite -> modell.h
======================================================================
Erzeugt aus einem trainierten Modell die Datei
firmware/CleverSole/modell.h, die die Firmware direkt einbindet.

Aufruf (im Repo-Ordner):
    python tools/export_firmware_model.py fall_model_lowerlimb.keras Pilotdaten/

    Argument 1: Keras-Modell (.keras)
    Argument 2: Ordner mit Pilotaufnahmen (DatenLogger-CSV). Dient als
                repraesentativer Datensatz fuer die int8-Kalibrierung
                und zur Kontrolle, dass int8 und float uebereinstimmen.

Ausgabe:
    firmware/CleverSole/modell.h     C-Array, 16-Byte-ausgerichtet
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


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    modell_pfad, pilot = Path(sys.argv[1]), Path(sys.argv[2])
    import tensorflow as tf
    from tensorflow import keras

    m = keras.models.load_model(modell_pfad, compile=False)

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

    # --- modell.h schreiben ---------------------------------------------
    hexz = [", ".join(f"0x{b:02x}" for b in blob[i:i + 12])
            for i in range(0, len(blob), 12)]
    ziel = Path(__file__).resolve().parents[1] / "firmware" / "CleverSole" / "modell.h"
    ziel.write_text(
        "/*\n"
        " * modell.h  --  automatisch erzeugt von tools/export_firmware_model.py\n"
        f" * Quelle      : {modell_pfad.name}\n"
        f" * Groesse     : {len(blob)} Byte (int8)\n"
        f" * Operatoren  : {', '.join(ops)}\n"
        f" * int8/float  : {gleich:.2%} gleiche Entscheidungen (Pilotdaten)\n"
        " * Nicht von Hand bearbeiten -- neu erzeugen.\n"
        " */\n"
        "#ifndef MODELL_H\n#define MODELL_H\n\n"
        "#define MODELL_VERFUEGBAR 1\n\n"
        f"alignas(16) const unsigned char modell_tflite[] = {{\n  "
        + ",\n  ".join(hexz) + "\n};\n"
        f"const unsigned int modell_tflite_len = {len(blob)};\n\n"
        "#endif\n")
    print(f"geschrieben     : {ziel}")


if __name__ == "__main__":
    main()
