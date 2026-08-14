"""
cross_dataset_kfall.py  --  Cross-Dataset-Transfer: SisFall -> KFall
====================================================================
Prueft, ob der in den UMAFall-Experimenten beobachtete Leistungsabfall
ein allgemeines Merkmal des Datensatzwechsels ist oder eine
Besonderheit von UMAFall.

KFall eignet sich als Gegenprobe besonders gut:
  - 15 Sturzarten (UMAFall: nur 3)
  - 100 Hz native Abtastrate (kein Hochtasten noetig)
  - 32 Probanden, anderes Kollektiv als SisFall
  - Position: unterer Ruecken (nahe der SisFall-Huefte)

Dateiformat (CSV mit Kopfzeile):
  TimeStamp(s),FrameCounter,AccX,AccY,AccZ,GyrX,GyrY,GyrZ,EulerX,EulerY,EulerZ
  Beschleunigung in g, Drehrate in Grad/s -> identisch zur SisFall-Pipeline.
  Die Euler-Kanaele werden verworfen (reine 6-Achsen-Auswertung).

Benennung:  SA06/S06T01R01.csv  ->  Subjekt 06, Task 01, Trial 01
Label:      T01-T21 = ADL (21 Typen), T22-T36 = Sturz (15 Typen)

Aufruf:
    python cross_dataset_kfall.py            # Zero-Shot + Fine-Tuning
    python cross_dataset_kfall.py --verify    # nur Label-Grenze pruefen
"""

from pathlib import Path
import argparse
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
KFALL_DIR    = Path("data/KFall")          # <-- ANPASSEN
MODEL_PATH   = Path("fall_model.keras")    # SisFall-trainiertes Modell
FS_KFALL     = 100          # native Abtastrate [Hz]
FS_TARGET    = 50           # Eingangsrate des Modells [Hz]
WIN_SEC      = 2.0
WIN_OVERLAP  = 0.5
LABEL_MODE   = "impact"
N_FALL_WIN   = 3

FALL_TASK_MIN = 22          # T22-T36 = Stuerze (T01-T21 = ADL)

DO_FINETUNE  = True
FT_EPOCHS    = 60
FT_LR        = 1e-4
FT_TEST_SIZE = 0.3
FREEZE_UPTO  = 3
MAX_FILES    = None         # z.B. 500 zum schnellen Testen, None = alle
RANDOM_STATE = 42
# ================================================================


def parse_kfall_name(path):
    """S06T01R01.csv -> (subject, task, trial). Gibt None bei Fehlformat."""
    m = re.match(r"S(\d+)T(\d+)R(\d+)", path.stem, re.IGNORECASE)
    if not m:
        return None
    return f"S{m.group(1)}", int(m.group(2)), int(m.group(3))


def load_kfall_trial(path):
    """KFall-CSV -> (N,6) [ax,ay,az (g), gx,gy,gz (Grad/s)]."""
    rows = []
    with path.open(errors="ignore") as fh:
        header = fh.readline()                       # Kopfzeile ueberspringen
        for line in fh:
            parts = line.strip().split(",")
            if len(parts) < 8:
                continue
            try:                                     # Spalten 2-7 = Acc + Gyr
                rows.append([float(p) for p in parts[2:8]])
            except ValueError:
                continue
    if not rows:
        return None
    return np.asarray(rows, dtype=float)


def downsample(sig):
    if FS_TARGET == FS_KFALL:
        return sig
    return resample_poly(sig, FS_TARGET, FS_KFALL, axis=0)


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


def list_files():
    files = sorted(KFALL_DIR.rglob("*.csv"))
    files = [f for f in files if parse_kfall_name(f)]
    if MAX_FILES:
        files = files[:MAX_FILES]
    return files


def verify_label_boundary():
    """Prueft empirisch, ob die Grenze T21/T22 korrekt ist.

    Stuerze muessen deutlich hoehere Spitzenbeschleunigungen aufweisen
    als ADL. Steigt der Median der Spitzenwerte genau ab T22 sprunghaft
    an, ist die angenommene Grenze bestaetigt.
    """
    files = list_files()
    print(f"Pruefe Label-Grenze anhand von {len(files)} Dateien ...\n")

    peaks = {}
    for path in files:
        meta = parse_kfall_name(path)
        if not meta:
            continue
        _, task, _ = meta
        sig = load_kfall_trial(path)
        if sig is None:
            continue
        pk = float(np.linalg.norm(sig[:, 0:3], axis=1).max())
        peaks.setdefault(task, []).append(pk)

    print(f"{'Task':>5} {'n':>4} {'Median Peak [g]':>16}   angenommen")
    print("-" * 48)
    for task in sorted(peaks):
        med = float(np.median(peaks[task]))
        lab = "Sturz" if task >= FALL_TASK_MIN else "ADL"
        bar = "#" * int(min(med, 12) * 2)
        print(f"T{task:02d} {len(peaks[task]):>5} {med:>15.2f}   {lab:<6} {bar}")

    adl = [np.median(v) for t, v in peaks.items() if t < FALL_TASK_MIN]
    fal = [np.median(v) for t, v in peaks.items() if t >= FALL_TASK_MIN]
    if adl and fal:
        print("-" * 48)
        print(f"Median ADL-Peak   (T01-T{FALL_TASK_MIN-1}): {np.median(adl):.2f} g")
        print(f"Median Sturz-Peak (T{FALL_TASK_MIN}-T36): {np.median(fal):.2f} g")
        if np.median(fal) > np.median(adl):
            print("\n=> Grenze plausibel: Stuerze zeigen hoehere Spitzenwerte.")
        else:
            print("\n=> WARNUNG: Grenze pruefen! FALL_TASK_MIN ggf. anpassen.")


def load_dataset():
    files = list_files()
    if not files:
        raise SystemExit(f"Keine CSV unter {KFALL_DIR} gefunden. KFALL_DIR pruefen.")

    w = int(WIN_SEC * FS_TARGET)
    X, y, groups = [], [], []
    skipped = 0

    for path in files:
        meta = parse_kfall_name(path)
        if not meta:
            skipped += 1
            continue
        subject, task, _ = meta
        label = 1 if task >= FALL_TASK_MIN else 0

        sig = load_kfall_trial(path)
        if sig is None or len(sig) < WIN_SEC * FS_KFALL:
            skipped += 1
            continue
        sig = downsample(sig)
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

    if skipped:
        print(f"  ({skipped} Dateien uebersprungen)")
    return np.asarray(X), np.asarray(y), np.asarray(groups)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true",
                    help="Nur die Label-Grenze empirisch pruefen")
    args = ap.parse_args()

    if args.verify:
        verify_label_boundary()
        return

    print("=== Cross-Dataset-Transfer: SisFall -> KFall ===\n")
    if not MODEL_PATH.exists():
        raise SystemExit(f"{MODEL_PATH} fehlt. Zuerst cnn_pipeline.py ausfuehren.")

    print("Lade KFall-Daten ...")
    X, y, groups = load_dataset()
    print(f"Fenster: {len(y)}  |  Stuerze: {int(y.sum())}  "
          f"ADL: {int((y==0).sum())}  |  Subjekte: {len(set(groups))}\n")

    X = normalize_per_window(X)

    # ---------- A) Zero-Shot ----------
    model = keras.models.load_model(MODEL_PATH)
    y_pred = (model.predict(X, verbose=0).ravel() >= 0.5).astype(int)
    se0, sp0, acc0, (tn, fp, fn, tp) = se_sp(y, y_pred)

    print("=" * 62)
    print("[A] ZERO-SHOT  (SisFall-Modell, keine Anpassung)")
    print(f"    Sensitivitaet {se0:.3f}   Spezifitaet {sp0:.3f}   Accuracy {acc0:.3f}")
    print(f"    TN={tn}  FP={fp}  FN={fn}  TP={tp}")
    print("=" * 62)

    # ---------- B) Fine-Tuning ----------
    if DO_FINETUNE and len(set(groups)) >= 3:
        splitter = GroupShuffleSplit(n_splits=1, test_size=FT_TEST_SIZE,
                                     random_state=RANDOM_STATE)
        tr, te = next(splitter.split(X, y, groups))

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
        print(f"\n[B] FINE-TUNING (Train {len(tr)} / Test {len(te)} Fenster, "
              f"{len(set(groups[te]))} Testsubjekte)")
        ft.fit(X[tr], y[tr], validation_data=(X[te], y[te]),
               epochs=FT_EPOCHS, batch_size=64, class_weight=cw, verbose=2)

        yp = (ft.predict(X[te], verbose=0).ravel() >= 0.5).astype(int)
        se1, sp1, acc1, (tn, fp, fn, tp) = se_sp(y[te], yp)

        print("\n" + "=" * 62)
        print("[B] NACH FINE-TUNING (subjekt-unabhaengiger Test)")
        print(f"    Sensitivitaet {se1:.3f}   Spezifitaet {sp1:.3f}   Accuracy {acc1:.3f}")
        print(f"    TN={tn}  FP={fp}  FN={fn}  TP={tp}")
        print("=" * 62)

        print("\n--- VERGLEICH auf identischem Testsplit ---")
        print(f"  Zero-Shot : Se {se_z:.3f}  Sp {sp_z:.3f}  Acc {acc_z:.3f}")
        print(f"  Fine-Tuned: Se {se1:.3f}  Sp {sp1:.3f}  Acc {acc1:.3f}")
        print(f"  Delta     : Se {se1-se_z:+.3f}  Sp {sp1-sp_z:+.3f}  Acc {acc1-acc_z:+.3f}")

        ft.save("fall_model_kfall_finetuned.keras")

        xpos = np.arange(2); width = 0.35
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(xpos - width/2, [se_z, se1], width, label="Sensitivitaet")
        ax.bar(xpos + width/2, [sp_z, sp1], width, label="Spezifitaet")
        ax.set_xticks(xpos); ax.set_xticklabels(["Zero-Shot", "Fine-Tuned"])
        ax.set_ylim(0, 1.05); ax.legend()
        ax.set_title("Cross-Dataset-Transfer (SisFall -> KFall)")
        for i, (s, p) in enumerate(zip([se_z, se1], [sp_z, sp1])):
            ax.text(i - width/2, s + 0.02, f"{s:.2f}", ha="center", fontsize=9)
            ax.text(i + width/2, p + 0.02, f"{p:.2f}", ha="center", fontsize=9)
        fig.tight_layout(); fig.savefig("cross_dataset_kfall.png", dpi=150)
        print("\nDiagramm -> cross_dataset_kfall.png")


if __name__ == "__main__":
    main()
