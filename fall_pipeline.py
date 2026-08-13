"""
fall_pipeline.py  —  Sturzerkennung: Baseline-Pipeline (SisFall)
================================================================
End-to-End, ohne TensorFlow (nur numpy / scipy / scikit-learn):

  1. Liest die rohen SisFall-.txt-Dateien und rechnet die ADC-Rohwerte
     in physikalische Einheiten um (Beschleunigung in g, Drehrate in °/s).
  2. Downsampling 200 Hz -> Zielrate (Default 50 Hz).
  3. Zerlegt jede Aufzeichnung in ueberlappende Fenster.
  4. Extrahiert ROTATIONSINVARIANTE Magnitude-Features pro Fenster
     (positionsrobust -> hilft spaeter beim Wechsel Huefte -> Fuss).
  5. Trainiert & bewertet SUBJEKT-UNABHAENGIG:
        (a) Threshold-Baseline (Bourke-Stil)
        (b) Random Forest
     -> Sensitivitaet, Spezifitaet, Accuracy, Confusion-Matrix.

Aufruf:
    python fall_pipeline.py
Vorher unten im CONFIG-Block DATA_DIR auf deinen SisFall-Ordner setzen.
"""

from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
from scipy.stats import skew, kurtosis
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.metrics import confusion_matrix
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ============================ CONFIG ============================
DATA_DIR     = Path("data/SisFall_dataset")
FS_SOURCE    = 200      # SisFall-Abtastrate [Hz]
FS_TARGET    = 50       # Zielrate [Hz]  (20-50 empfohlen, vgl. Kapitel 2)
WIN_SEC      = 2.0      # Fensterlaenge [s]
WIN_OVERLAP  = 0.5      # 50 % Ueberlappung
THR_UPPER_G  = 2.0      # oberer Impact-Schwellwert [g]   (Baseline)
THR_LOWER_G  = 0.6      # unterer Freifall-Schwellwert [g] (Baseline)
LABEL_MODE   = "impact" # "impact" (empfohlen): Sturz-Fenster auf den Aufprall
                        #  zentriert;  "whole": jedes Fenster erbt das Trial-Label
N_FALL_WIN   = 1        # Anzahl Sturz-Fenster je Sturz-Aufzeichnung (impact-Modus)
RF_TREES     = 200
CV_FOLDS     = 5
RANDOM_STATE = 42
# ===============================================================

# SisFall-Umrechnungskonstanten (offizielles Readme):
#   ADXL345 (+/-16 g, 13 bit): g   = raw * (2*16) / 2**13
#   ITG3200 (+/-2000 dps,16b): dps = raw * (2*2000)/ 2**16
ADXL_TO_G  = (2 * 16)   / (2 ** 13)     # ~ 0.00390625
ITG_TO_DPS = (2 * 2000) / (2 ** 16)     # ~ 0.06103516

FEATURE_NAMES = [
    "acc_mean", "acc_std", "acc_max", "acc_min", "acc_range", "acc_rms",
    "acc_energy", "acc_mad", "acc_skew", "acc_kurt", "jerk_std", "jerk_max",
    "sma_acc", "gyr_mean", "gyr_std", "gyr_max", "gyr_rms", "gyr_energy",
]


def load_trial(path):
    """SisFall-.txt -> (N,6)-Array [ax,ay,az (g), gx,gy,gz (dps)] oder None."""
    rows = []
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip().strip(";").strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            rows.append([float(p) for p in parts[:9]])
        except ValueError:
            continue
    if not rows:
        return None
    arr = np.asarray(rows, dtype=float)
    acc = arr[:, 0:3] * ADXL_TO_G          # Spalten 0-2 = ADXL345
    gyr = arr[:, 3:6] * ITG_TO_DPS         # Spalten 3-5 = ITG3200
    return np.hstack([acc, gyr])           # (Spalten 6-8 = MMA8451Q, ungenutzt)


def parse_name(path):
    """z.B. F01_SA01_R01.txt -> (label, subject).  F=Sturz(1), D=ADL(0)."""
    parts = path.stem.split("_")
    activity = parts[0]
    subject = parts[1] if len(parts) > 1 else "UNK"
    label = 1 if activity.upper().startswith("F") else 0
    return label, subject


def downsample(sig):
    if FS_TARGET == FS_SOURCE:
        return sig
    return resample_poly(sig, FS_TARGET, FS_SOURCE, axis=0)


def iter_windows(sig):
    w = int(WIN_SEC * FS_TARGET)
    step = max(1, int(w * (1 - WIN_OVERLAP)))
    for s in range(0, len(sig) - w + 1, step):
        yield sig[s:s + w]


def features(win):
    """Rotationsinvariante Magnitude-Features (positionsrobust)."""
    acc, gyr = win[:, 0:3], win[:, 3:6]
    amag = np.linalg.norm(acc, axis=1)
    gmag = np.linalg.norm(gyr, axis=1)
    jerk = np.diff(amag)
    return np.array([
        amag.mean(), amag.std(), amag.max(), amag.min(), np.ptp(amag),
        np.sqrt(np.mean(amag ** 2)), np.mean(amag ** 2),
        np.mean(np.abs(amag - amag.mean())), skew(amag), kurtosis(amag),
        jerk.std(), np.max(np.abs(jerk)),
        np.mean(np.abs(acc).sum(axis=1)),
        gmag.mean(), gmag.std(), gmag.max(),
        np.sqrt(np.mean(gmag ** 2)), np.mean(gmag ** 2),
    ], dtype=float)


def threshold_predict(win):
    amag = np.linalg.norm(win[:, 0:3], axis=1)
    return int(amag.max() > THR_UPPER_G and amag.min() < THR_LOWER_G)


def se_sp(y_true, y_pred):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    se = tp / (tp + fn) if (tp + fn) else 0.0
    sp = tn / (tn + fp) if (tn + fp) else 0.0
    acc = (tp + tn) / max(1, tp + tn + fp + fn)
    return se, sp, acc, (tn, fp, fn, tp)


def main():
    files = [p for p in sorted(Path(DATA_DIR).rglob("*.txt"))
             if p.stem[:1].upper() in ("D", "F")]   # nur echte Trials (Readme.txt etc. ueberspringen)
    if not files:
        raise SystemExit(f"Keine .txt unter {DATA_DIR} gefunden. DATA_DIR pruefen.")

    X, y, groups, y_thr = [], [], [], []
    min_len = WIN_SEC * FS_SOURCE
    for path in files:
        sig = load_trial(path)
        if sig is None or len(sig) < min_len:
            continue
        label, subject = parse_name(path)
        sig = downsample(sig)
        w = int(WIN_SEC * FS_TARGET)

        if label == 1 and LABEL_MODE == "impact":
            # Fenster auf den Aufprall (max. Beschleunigungsbetrag) zentrieren
            amag = np.linalg.norm(sig[:, 0:3], axis=1)
            peak = int(np.argmax(amag))
            offsets = range(-(N_FALL_WIN // 2), N_FALL_WIN // 2 + 1)
            wins = []
            for k in offsets:
                start = peak - w // 2 + k * (w // 2)
                start = max(0, min(start, len(sig) - w))
                wins.append(sig[start:start + w])
        else:
            wins = list(iter_windows(sig))

        for win in wins:
            X.append(features(win))
            y.append(label)
            groups.append(subject)
            y_thr.append(threshold_predict(win))

    X, y = np.asarray(X), np.asarray(y)
    groups, y_thr = np.asarray(groups), np.asarray(y_thr)
    print(f"Fenster: {len(y)}  |  Stuerze: {int(y.sum())}  ADL: {int((y == 0).sum())}"
          f"  |  Subjekte: {len(set(groups))}")

    se, sp, acc, _ = se_sp(y, y_thr)
    print("\n[Threshold-Baseline]")
    print(f"  Sensitivitaet {se:.3f}   Spezifitaet {sp:.3f}   Accuracy {acc:.3f}")

    rf = RandomForestClassifier(n_estimators=RF_TREES, random_state=RANDOM_STATE,
                                n_jobs=-1, class_weight="balanced")
    cv = GroupKFold(n_splits=min(CV_FOLDS, len(set(groups))))
    y_pred = cross_val_predict(rf, X, y, groups=groups, cv=cv, n_jobs=-1)
    se, sp, acc, (tn, fp, fn, tp) = se_sp(y, y_pred)
    print("\n[Random Forest - subjekt-unabhaengige CV]")
    print(f"  Sensitivitaet {se:.3f}   Spezifitaet {sp:.3f}   Accuracy {acc:.3f}")
    print(f"  TN={tn}  FP={fp}  FN={fn}  TP={tp}")

    cm = confusion_matrix(y, y_pred, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.imshow(cm, cmap="Greens")
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["ADL", "Sturz"]); ax.set_yticklabels(["ADL", "Sturz"])
    ax.set_xlabel("Vorhergesagt"); ax.set_ylabel("Wahr")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, cm[i, j], ha="center", va="center")
    ax.set_title("Random Forest - Confusion Matrix")
    fig.tight_layout(); fig.savefig("confusion_matrix.png", dpi=150)
    print("\nConfusion-Matrix -> confusion_matrix.png")

    rf.fit(X, y)
    imp = sorted(zip(FEATURE_NAMES, rf.feature_importances_), key=lambda t: -t[1])
    print("\nTop-Features:")
    for name, val in imp[:8]:
        print(f"  {name:12s} {val:.3f}")


if __name__ == "__main__":
    main()
