"""
cross_position.py  --  Cross-Position-Transfer: SisFall (Huefte) -> UMAFall (Knoechel)
=====================================================================================
Beantwortet die zentrale Frage des Projekts:
  "Wie gut uebertraegt sich ein an der Huefte trainiertes Modell auf eine
   fussnahe Sensorposition?"

Ablauf:
  1. Laedt UMAFall-CSV-Dateien und extrahiert NUR den ANKLE-Sensor.
     (Die Sensor-ID des Knoechels wird PRO DATEI aus dem Header gelesen,
      da die Zuordnung nicht in allen Aufnahmen identisch ist.)
  2. Synchronisiert Accelerometer- und Gyroskop-Stroeme auf ein Zeitraster.
  3. Resampling 20 Hz -> FS_TARGET (Modell-Eingangsrate).
  4. Fensterung analog zur SisFall-Pipeline.
  5. Evaluation A: Zero-Shot  - SisFall-Modell direkt auf Knoechel-Daten.
     Evaluation B: Fine-Tuning - letzte Schichten auf Knoechel-Daten angepasst,
                   subjekt-unabhaengig getestet.

Aufruf:
    python cross_position.py
"""

from pathlib import Path
import re
import numpy as np
from scipy.signal import resample_poly
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import confusion_matrix
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import tensorflow as tf
from tensorflow import keras

# ============================ CONFIG ============================
UMA_DIR      = Path("data/UMAFall_Dataset")     # <-- ANPASSEN
MODEL_PATH   = Path("fall_model.keras")         # SisFall-trainiertes Modell
POSITION     = "ANKLE"       # ANKLE | WAIST | CHEST | WRIST | RIGHTPOCKET
FS_UMA       = 20            # native SensorTag-Rate [Hz]
FS_TARGET    = 50            # Eingangsrate des Modells [Hz]
WIN_SEC      = 2.0
WIN_OVERLAP  = 0.5
LABEL_MODE   = "impact"
N_FALL_WIN   = 3

# Fine-Tuning
DO_FINETUNE  = True
FT_EPOCHS    = 60
FT_LR        = 1e-4          # kleine Lernrate: vortrainierte Merkmale erhalten
FT_TEST_SIZE = 0.3           # Anteil Subjekte im Test
FREEZE_UPTO  = 6             # erste N Schichten einfrieren (Conv-Bloecke 1-2)
RANDOM_STATE = 42
# ================================================================

SENSOR_ACC, SENSOR_GYR = 0, 1


def parse_header_positions(text):
    """Liest die Zuordnung Sensor_ID -> Position aus dem Dateikopf.
    Beispielzeile:  %B0:B4:48:B8:77:03; 4; ANKLE; SensorTag"""
    mapping = {}
    for line in text.splitlines():
        if not line.startswith("%"):
            continue
        parts = [p.strip() for p in line.lstrip("%").split(";")]
        if len(parts) >= 3 and parts[1].isdigit():
            mapping[int(parts[1])] = parts[2].upper()
    return mapping


def load_uma_trial(path, position=POSITION):
    """UMAFall-CSV -> (N,6) [ax,ay,az (g), gx,gy,gz] fuer die gewaehlte Position.
    Gibt None zurueck, wenn die Position in der Datei fehlt."""
    text = path.read_text(errors="ignore")
    id_to_pos = parse_header_positions(text)

    target_ids = [sid for sid, pos in id_to_pos.items() if pos == position]
    if not target_ids:
        return None
    target_id = target_ids[0]

    acc, gyr = {}, {}          # sample_no -> (x,y,z)
    for line in text.splitlines():
        if line.startswith("%") or not line.strip():
            continue
        parts = line.strip().rstrip(";").split(";")
        if len(parts) < 7:
            continue
        try:
            sample = int(parts[1])
            x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
            stype, sid = int(parts[5]), int(parts[6])
        except ValueError:
            continue
        if sid != target_id:
            continue
        if stype == SENSOR_ACC:
            acc[sample] = (x, y, z)
        elif stype == SENSOR_GYR:
            gyr[sample] = (x, y, z)

    common = sorted(set(acc) & set(gyr))
    if len(common) < WIN_SEC * FS_UMA:
        return None

    a = np.array([acc[s] for s in common], dtype=float)
    g = np.array([gyr[s] for s in common], dtype=float)
    return np.hstack([a, g])


def parse_uma_name(path):
    """UMAFall_Subject_01_ADL_Aplausing_1_...  -> (label, subject)"""
    stem = path.stem
    m = re.search(r"Subject_(\d+)", stem)
    subject = f"S{m.group(1)}" if m else "UNK"
    label = 1 if "_FALL_" in stem.upper() else 0
    return label, subject


def resample_to_target(sig):
    if FS_UMA == FS_TARGET:
        return sig
    return resample_poly(sig, FS_TARGET, FS_UMA, axis=0)


def iter_windows(sig, w):
    step = max(1, int(w * (1 - WIN_OVERLAP)))
    for s in range(0, len(sig) - w + 1, step):
        yield sig[s:s + w]


def normalize_per_window(X):
    mu = X.mean(axis=1, keepdims=True)
    sd = X.std(axis=1, keepdims=True) + 1e-8
    return (X - mu) / sd


def se_sp(y_true, y_pred):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    se = tp / (tp + fn) if (tp + fn) else 0.0
    sp = tn / (tn + fp) if (tn + fp) else 0.0
    acc = (tp + tn) / max(1, tp + tn + fp + fn)
    return se, sp, acc, (tn, fp, fn, tp)


def load_uma_dataset():
    files = sorted(list(UMA_DIR.rglob("*.csv")) + list(UMA_DIR.rglob("*.CSV")))
    if not files:
        raise SystemExit(f"Keine CSV unter {UMA_DIR} gefunden. UMA_DIR pruefen.")

    w = int(WIN_SEC * FS_TARGET)
    X, y, groups = [], [], []
    skipped = 0

    for path in files:
        sig = load_uma_trial(path)
        if sig is None:
            skipped += 1
            continue
        label, subject = parse_uma_name(path)
        sig = resample_to_target(sig)
        if len(sig) < w:
            skipped += 1
            continue

        if label == 1 and LABEL_MODE == "impact":
            amag = np.linalg.norm(sig[:, 0:3], axis=1)
            peak = int(np.argmax(amag))
            wins = []
            for k in range(-(N_FALL_WIN // 2), N_FALL_WIN // 2 + 1):
                start = peak - w // 2 + k * (w // 2)
                start = max(0, min(start, len(sig) - w))
                wins.append(sig[start:start + w])
        else:
            wins = list(iter_windows(sig, w))

        for win in wins:
            X.append(win)
            y.append(label)
            groups.append(subject)

    print(f"  ({skipped} Dateien uebersprungen: Position fehlt oder zu kurz)")
    return np.asarray(X), np.asarray(y), np.asarray(groups)


def main():
    print(f"=== Cross-Position-Transfer: SisFall (Huefte) -> UMAFall ({POSITION}) ===\n")

    if not MODEL_PATH.exists():
        raise SystemExit(f"{MODEL_PATH} nicht gefunden. Zuerst cnn_pipeline.py ausfuehren.")

    print(f"Lade UMAFall-Daten (Position: {POSITION}) ...")
    X, y, groups = load_uma_dataset()
    if len(y) == 0:
        raise SystemExit("Keine verwertbaren Fenster gefunden.")
    print(f"Fenster: {len(y)}  |  Stuerze: {int(y.sum())}  "
          f"ADL: {int((y==0).sum())}  |  Subjekte: {len(set(groups))}\n")

    X = normalize_per_window(X)

    # ---------- A) Zero-Shot ----------
    model = keras.models.load_model(MODEL_PATH)
    y_prob = model.predict(X, verbose=0).ravel()
    y_pred = (y_prob >= 0.5).astype(int)
    se0, sp0, acc0, (tn, fp, fn, tp) = se_sp(y, y_pred)

    print("=" * 62)
    print("[A] ZERO-SHOT  (SisFall-Modell, keinerlei Anpassung)")
    print(f"    Sensitivitaet {se0:.3f}   Spezifitaet {sp0:.3f}   Accuracy {acc0:.3f}")
    print(f"    TN={tn}  FP={fp}  FN={fn}  TP={tp}")
    print("=" * 62)

    results = {"zero_shot": (se0, sp0, acc0)}

    # ---------- B) Fine-Tuning ----------
    if DO_FINETUNE and len(set(groups)) >= 3:
        splitter = GroupShuffleSplit(n_splits=1, test_size=FT_TEST_SIZE,
                                     random_state=RANDOM_STATE)
        tr, te = next(splitter.split(X, y, groups))

        # Zero-Shot auf demselben Testsplit (fairer Vergleich)
        yp_te = (model.predict(X[te], verbose=0).ravel() >= 0.5).astype(int)
        se_z, sp_z, acc_z, _ = se_sp(y[te], yp_te)

        ft = keras.models.load_model(MODEL_PATH)
        for layer in ft.layers[:FREEZE_UPTO]:
            layer.trainable = False

        n_neg, n_pos = int((y[tr] == 0).sum()), int((y[tr] == 1).sum())
        cw = {0: 1.0, 1: n_neg / max(1, n_pos)}

        ft.compile(optimizer=keras.optimizers.Adam(learning_rate=FT_LR),
                   loss="binary_crossentropy",
                   metrics=[keras.metrics.Recall(name="recall")])
        print(f"\n[B] FINE-TUNING  (Train: {len(tr)} Fenster, "
              f"Test: {len(te)} Fenster / {len(set(groups[te]))} Subjekte)")
        ft.fit(X[tr], y[tr], validation_data=(X[te], y[te]),
               epochs=FT_EPOCHS, batch_size=32, class_weight=cw, verbose=2)

        yp = (ft.predict(X[te], verbose=0).ravel() >= 0.5).astype(int)
        se1, sp1, acc1, (tn, fp, fn, tp) = se_sp(y[te], yp)

        print("\n" + "=" * 62)
        print("[B] NACH FINE-TUNING  (subjekt-unabhaengiger Test)")
        print(f"    Sensitivitaet {se1:.3f}   Spezifitaet {sp1:.3f}   Accuracy {acc1:.3f}")
        print(f"    TN={tn}  FP={fp}  FN={fn}  TP={tp}")
        print("=" * 62)

        print("\n--- VERGLEICH auf identischem Testsplit ---")
        print(f"  Zero-Shot : Se {se_z:.3f}  Sp {sp_z:.3f}  Acc {acc_z:.3f}")
        print(f"  Fine-Tuned: Se {se1:.3f}  Sp {sp1:.3f}  Acc {acc1:.3f}")
        print(f"  Delta     : Se {se1-se_z:+.3f}  Sp {sp1-sp_z:+.3f}  Acc {acc1-acc_z:+.3f}")

        ft.save("fall_model_ankle_finetuned.keras")
        print("\nFeinabgestimmtes Modell -> fall_model_ankle_finetuned.keras")
        results["zero_shot_split"] = (se_z, sp_z, acc_z)
        results["finetuned"] = (se1, sp1, acc1)

        # Balkendiagramm
        labels = ["Zero-Shot", "Fine-Tuned"]
        se_v = [se_z, se1]; sp_v = [sp_z, sp1]
        xpos = np.arange(2); width = 0.35
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(xpos - width/2, se_v, width, label="Sensitivitaet")
        ax.bar(xpos + width/2, sp_v, width, label="Spezifitaet")
        ax.set_xticks(xpos); ax.set_xticklabels(labels)
        ax.set_ylim(0, 1.05); ax.legend()
        ax.set_title(f"Cross-Position-Transfer ({POSITION})")
        for i, (s, p) in enumerate(zip(se_v, sp_v)):
            ax.text(i - width/2, s + 0.02, f"{s:.2f}", ha="center", fontsize=9)
            ax.text(i + width/2, p + 0.02, f"{p:.2f}", ha="center", fontsize=9)
        fig.tight_layout(); fig.savefig("cross_position.png", dpi=150)
        print("Diagramm -> cross_position.png")

    return results


if __name__ == "__main__":
    main()
