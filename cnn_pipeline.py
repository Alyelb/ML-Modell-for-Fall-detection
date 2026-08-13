"""
cnn_pipeline.py  —  Sturzerkennung: 1D-CNN-Pipeline (SisFall)
=============================================================
Baut auf demselben Daten-Loader wie fall_pipeline.py auf.

  1. Laedt SisFall-Rohdaten, rechnet in g / dps um.
  2. Downsampling 200 -> FS_TARGET Hz.
  3. Fensterung mit Impact-Zentrierung fuer Stuerze.
  4. Trainiert ein 1D-CNN (6 Kanaele: ax,ay,az,gx,gy,gz)
     mit SUBJEKT-UNABHAENGIGEM Split (Leave-Groups-Out).
  5. Exportiert das Modell als int8-quantisiertes TFLite
     (bereit fuer ESP32 / nRF52840 Deployment).

Aufruf:
    python cnn_pipeline.py

Voraussetzungen (zusaetzlich zu fall_pipeline.py):
    pip install tensorflow
"""

from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import confusion_matrix, classification_report
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"          # weniger TF-Logspam
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# ============================ CONFIG ============================
DATA_DIR     = Path("data/SisFall_dataset")   # <-- ANPASSEN falls noetig
FS_SOURCE    = 200       # SisFall Abtastrate [Hz]
FS_TARGET    = 50        # Zielrate [Hz]
WIN_SEC      = 2.0       # Fensterlaenge [s]
WIN_OVERLAP  = 0.5       # Ueberlappung
LABEL_MODE   = "impact"  # "impact" oder "whole"
N_FALL_WIN   = 3         # Fenster pro Sturz (impact-Modus, 3 fuer mehr Daten)

# CNN-Hyperparameter
EPOCHS       = 30
BATCH_SIZE   = 64
LEARNING_RATE = 0.001
DROPOUT      = 0.3
TEST_SIZE    = 0.25      # Anteil Subjekte fuer Test
RANDOM_STATE = 42
# ================================================================

# SisFall-Umrechnungskonstanten
ADXL_TO_G  = (2 * 16)   / (2 ** 13)
ITG_TO_DPS = (2 * 2000) / (2 ** 16)


def load_trial(path):
    """SisFall .txt -> (N,6) Array [ax,ay,az (g), gx,gy,gz (dps)]."""
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
    acc = arr[:, 0:3] * ADXL_TO_G
    gyr = arr[:, 3:6] * ITG_TO_DPS
    return np.hstack([acc, gyr])


def parse_name(path):
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


def load_dataset():
    """Laedt alle Trials und gibt (X_windows, y_labels, groups) zurueck."""
    files = [p for p in sorted(Path(DATA_DIR).rglob("*.txt"))
             if p.stem[:1].upper() in ("D", "F")]
    if not files:
        raise SystemExit(f"Keine .txt unter {DATA_DIR} gefunden.")

    X, y, groups = [], [], []
    w = int(WIN_SEC * FS_TARGET)
    min_len = WIN_SEC * FS_SOURCE

    for path in files:
        sig = load_trial(path)
        if sig is None or len(sig) < min_len:
            continue
        label, subject = parse_name(path)
        sig = downsample(sig)

        if label == 1 and LABEL_MODE == "impact":
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
            X.append(win)            # raw 6-channel window fuer CNN
            y.append(label)
            groups.append(subject)

    return np.asarray(X), np.asarray(y), np.asarray(groups)


def normalize_per_window(X):
    """Per-Window Z-Normalisierung (positionsrobust)."""
    mu = X.mean(axis=1, keepdims=True)
    sd = X.std(axis=1, keepdims=True) + 1e-8
    return (X - mu) / sd


def build_model(input_shape):
    """1D-CNN: 3 Conv-Bloecke -> GlobalAvgPool -> Dense -> Sigmoid."""
    model = keras.Sequential([
        # Block 1
        layers.Conv1D(32, kernel_size=7, activation="relu",
                      input_shape=input_shape, padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling1D(pool_size=2),

        # Block 2
        layers.Conv1D(64, kernel_size=5, activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling1D(pool_size=2),

        # Block 3
        layers.Conv1D(128, kernel_size=3, activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.GlobalAveragePooling1D(),

        # Classifier
        layers.Dropout(DROPOUT),
        layers.Dense(64, activation="relu"),
        layers.Dropout(DROPOUT),
        layers.Dense(1, activation="sigmoid"),
    ])
    return model


def plot_history(history):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    ax1.plot(history.history["loss"], label="Train")
    ax1.plot(history.history["val_loss"], label="Val")
    ax1.set_xlabel("Epoch"); ax1.set_ylabel("Loss"); ax1.legend()
    ax1.set_title("Loss")
    ax2.plot(history.history["recall"], label="Train Se")
    ax2.plot(history.history["val_recall"], label="Val Se")
    ax2.set_xlabel("Epoch"); ax2.set_ylabel("Sensitivity"); ax2.legend()
    ax2.set_title("Sensitivity")
    fig.tight_layout(); fig.savefig("cnn_training.png", dpi=150)
    print("Training-Kurven -> cnn_training.png")


def se_sp(y_true, y_pred):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    se = tp / (tp + fn) if (tp + fn) else 0.0
    sp = tn / (tn + fp) if (tn + fp) else 0.0
    acc = (tp + tn) / max(1, tp + tn + fp + fn)
    return se, sp, acc, (tn, fp, fn, tp)


def convert_tflite(model, X_cal):
    """Int8-Quantisierung -> .tflite (bereit fuer Mikrocontroller)."""
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    def representative_gen():
        idx = np.random.choice(len(X_cal), min(200, len(X_cal)), replace=False)
        for i in idx:
            yield [X_cal[i:i+1].astype(np.float32)]

    converter.representative_dataset = representative_gen
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type  = tf.int8
    converter.inference_output_type = tf.int8
    tflite_model = converter.convert()

    out = "fall_model_int8.tflite"
    Path(out).write_bytes(tflite_model)
    size_kb = len(tflite_model) / 1024
    print(f"\nTFLite-Modell -> {out}  ({size_kb:.1f} KB)")
    return out


def main():
    print("Lade Daten ...")
    X, y, groups = load_dataset()
    print(f"Fenster: {len(y)}  |  Stuerze: {int(y.sum())}  "
          f"ADL: {int((y==0).sum())}  |  Subjekte: {len(set(groups))}")

    # --- Per-Window-Normalisierung ---
    X = normalize_per_window(X)

    # --- Subjekt-unabhaengiger Split ---
    splitter = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE,
                                random_state=RANDOM_STATE)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    g_test = groups[test_idx]

    print(f"Train: {len(y_train)} ({int(y_train.sum())} Stuerze)  |  "
          f"Test:  {len(y_test)} ({int(y_test.sum())} Stuerze, "
          f"{len(set(g_test))} Subjekte)")

    # --- Class weights (Stuerze sind die Minderheit) ---
    n_neg = int((y_train == 0).sum())
    n_pos = int((y_train == 1).sum())
    class_weight = {0: 1.0, 1: n_neg / max(1, n_pos)}
    print(f"Class weight fuer Stuerze: {class_weight[1]:.1f}x")

    # --- Modell bauen & trainieren ---
    input_shape = (X_train.shape[1], X_train.shape[2])   # (100, 6) bei 50Hz/2s
    model = build_model(input_shape)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss="binary_crossentropy",
        metrics=[
            keras.metrics.BinaryAccuracy(name="accuracy"),
            keras.metrics.Recall(name="recall"),           # = Sensitivitaet
            keras.metrics.Precision(name="precision"),
        ],
    )
    model.summary()

    history = model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        class_weight=class_weight,
        verbose=1,
    )

    # --- Evaluation ---
    y_prob = model.predict(X_test, verbose=0).ravel()
    y_pred = (y_prob >= 0.5).astype(int)
    se, sp, acc, (tn, fp, fn, tp) = se_sp(y_test, y_pred)
    print(f"\n{'='*50}")
    print(f"[1D-CNN - subjekt-unabhaengiger Test]")
    print(f"  Sensitivitaet {se:.3f}   Spezifitaet {sp:.3f}   Accuracy {acc:.3f}")
    print(f"  TN={tn}  FP={fp}  FN={fn}  TP={tp}")
    print(f"{'='*50}")

    # --- Confusion-Matrix ---
    cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["ADL", "Sturz"]); ax.set_yticklabels(["ADL", "Sturz"])
    ax.set_xlabel("Vorhergesagt"); ax.set_ylabel("Wahr")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max()/2 else "black")
    ax.set_title("1D-CNN - Confusion Matrix")
    fig.tight_layout(); fig.savefig("cnn_confusion.png", dpi=150)
    print("Confusion-Matrix -> cnn_confusion.png")

    # --- Training-Kurven ---
    plot_history(history)

    # --- TFLite int8 Export ---
    convert_tflite(model, X_train)

    # --- Keras-Modell speichern ---
    model.save("fall_model.keras")
    print("Keras-Modell  -> fall_model.keras")


if __name__ == "__main__":
    main()
