"""
cross_dataset_fallalld.py  —  Transfer SisFall → FallAllD (Waist)
=================================================================
Laedt ein auf SisFall trainiertes 1D-CNN (fall_model.keras) und
bewertet es auf den Taillendaten (Device 3) des FallAllD-Datensatzes.

Zwei Bedingungen:
  1. Zero-Shot  — Modell unveraendert auf FallAllD angewendet
  2. Fine-Tuning — letzte Schichten auf FallAllD-Daten nachtrainiert

Usage:
  python cross_dataset_fallalld.py              # Transfer
  python cross_dataset_fallalld.py --verify     # Label-Pruefung
"""

import argparse, sys, json, warnings
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly
from math import gcd

# =====================================================================
#   KONFIGURATION  —  HIER ANPASSEN
# =====================================================================
FALLALLD_DIR = Path("data/FallAllD")       # <-- ANPASSEN
MODEL_PATH   = Path("fall_model.keras")    # SisFall-Modell
FS_NATIVE    = 238                         # FallAllD native Hz
FS_TARGET    = 50                          # Ziel-Abtastrate
WINDOW_SEC   = 2                           # Fensterlaenge in Sekunden
OVERLAP      = 0.5                         # Ueberlappung
DEVICE       = 3                           # 1=Neck, 2=Wrist, 3=Waist
FT_EPOCHS    = 60                          # Fine-Tuning-Epochen
FT_LR        = 1e-4                        # Fine-Tuning-Lernrate
FREEZE_UPTO  = 3                           # Schichten einfrieren (0..N)
TEST_FRAC    = 0.25                        # Anteil Testprobanden

# LSM9DS1 Conversion (aus offiziellem MATLAB-Skript)
ACC_SEN      = 0.000244                    # g/LSB  (±8g, 16-bit)
GYR_SEN      = 0.07                        # °/s/LSB (±2000 dps)

# Label-Grenzen (aus ActivityID2Str.m)
ADL_IDS      = list(range(1, 45))          # A001..A044
FALL_IDS     = list(range(101, 136))       # A101..A135

# =====================================================================
#   DATEN LADEN
# =====================================================================
def find_trials(root: Path, device: int) -> list:
    """Findet alle Trials fuer ein bestimmtes Device."""
    pattern = f"*_D{device}_*_A.dat"
    acc_files = sorted(root.glob(pattern))
    if not acc_files:
        # Versuche rekursive Suche
        acc_files = sorted(root.rglob(pattern))
    return acc_files


def parse_filename(acc_path: Path) -> dict:
    """Extrahiert Metadaten aus dem Dateinamen.
    Format: S01_D1_A013_T01_A.dat
    """
    name = acc_path.stem                    # S01_D1_A013_T01_A
    parts = name.split("_")
    return {
        "subject":  int(parts[0][1:]),      # S01 → 1
        "device":   int(parts[1][1:]),       # D1  → 1
        "activity": int(parts[2][1:]),       # A013 → 13
        "trial":    int(parts[3][1:]),       # T01 → 1
    }


def load_trial(acc_path: Path) -> np.ndarray:
    """Laedt einen einzelnen Trial (Acc + Gyr) und gibt 6-Kanal-Array zurueck.
    Rueckgabe: (N, 6) in physikalischen Einheiten [g, °/s].
    """
    gyr_path = acc_path.parent / acc_path.name.replace("_A.dat", "_G.dat")
    if not gyr_path.exists():
        return None

    try:
        acc_raw = np.loadtxt(acc_path, delimiter=",", dtype=np.int16)
        gyr_raw = np.loadtxt(gyr_path, delimiter=",", dtype=np.int16)
    except Exception:
        return None

    # Laenge angleichen (sollte identisch sein, Sicherheitshalber)
    n = min(len(acc_raw), len(gyr_raw))
    acc_raw = acc_raw[:n]
    gyr_raw = gyr_raw[:n]

    # In physikalische Einheiten umrechnen
    acc = acc_raw.astype(np.float32) * ACC_SEN    # → g
    gyr = gyr_raw.astype(np.float32) * GYR_SEN    # → °/s

    return np.hstack([acc, gyr])                   # (N, 6)


def downsample(signal: np.ndarray, fs_from: int, fs_to: int) -> np.ndarray:
    """Polyphasen-Resampling (anti-aliased)."""
    if fs_from == fs_to:
        return signal
    g = gcd(fs_from, fs_to)
    return resample_poly(signal, fs_to // g, fs_from // g, axis=0)


def load_fallalld(root: Path, device: int = 3, verbose: bool = True):
    """Laedt alle Trials eines Devices, konvertiert und downsampled.
    Rueckgabe: list[(signal_2d, label_int, subject_int)]
    """
    acc_files = find_trials(root, device)
    if not acc_files:
        print(f"[FEHLER] Keine Dateien gefunden in {root} fuer D{device}")
        print(f"         Erwartet: *_D{device}_*_A.dat")
        sys.exit(1)

    device_name = {1: "Neck", 2: "Wrist", 3: "Waist"}.get(device, "?")
    if verbose:
        print(f"[FallAllD] {len(acc_files)} Trials gefunden (Device {device} = {device_name})")

    trials = []
    skipped = 0
    subjects_seen = set()
    fall_count = 0
    adl_count = 0

    for acc_path in acc_files:
        meta = parse_filename(acc_path)
        activity = meta["activity"]

        # Label bestimmen
        if activity in FALL_IDS:
            label = 1
            fall_count += 1
        elif activity in ADL_IDS:
            label = 0
            adl_count += 1
        else:
            skipped += 1
            continue

        # Daten laden
        data = load_trial(acc_path)
        if data is None or len(data) < FS_NATIVE:
            skipped += 1
            continue

        # Downsample
        data = downsample(data, FS_NATIVE, FS_TARGET)
        subjects_seen.add(meta["subject"])
        trials.append((data, label, meta["subject"]))

    if verbose:
        print(f"  Geladen: {len(trials)} Trials "
              f"({fall_count} Stuerze, {adl_count} ADL) "
              f"von {len(subjects_seen)} Probanden")
        if skipped:
            print(f"  Uebersprungen: {skipped}")

    return trials


# =====================================================================
#   WINDOWING (identisch mit SisFall-Pipeline)
# =====================================================================
def window_trial(signal: np.ndarray, label: int,
                 win_len: int, step: int) -> list:
    """Erzeugt Fenster aus einem Trial.
    Bei Stuerzen: Impact-zentriertes Fenster.
    Bei ADL: gleitende Fenster mit Ueberlappung.
    """
    windows = []
    n = len(signal)

    if label == 1:
        # Impact-zentriert: Fenster um den max. Beschleunigungsbetrag
        acc_mag = np.sqrt(np.sum(signal[:, :3] ** 2, axis=1))
        peak = np.argmax(acc_mag)
        start = max(0, peak - win_len // 2)
        end = start + win_len
        if end > n:
            end = n
            start = max(0, end - win_len)
        if end - start == win_len:
            windows.append(signal[start:end])
    else:
        # Gleitende Fenster
        for start in range(0, n - win_len + 1, step):
            windows.append(signal[start:start + win_len])

    return windows


def prepare_windows(trials: list, verbose: bool = True):
    """Erzeugt gefensterte Daten aus allen Trials."""
    win_len = int(FS_TARGET * WINDOW_SEC)
    step = int(win_len * (1 - OVERLAP))

    X_list, y_list, g_list = [], [], []

    for signal, label, subject in trials:
        wins = window_trial(signal, label, win_len, step)
        for w in wins:
            X_list.append(w)
            y_list.append(label)
            g_list.append(subject)

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    groups = np.array(g_list, dtype=np.int32)

    # Per-Window Z-Normalisierung
    mu = X.mean(axis=1, keepdims=True)
    sigma = X.std(axis=1, keepdims=True) + 1e-8
    X = (X - mu) / sigma

    if verbose:
        n_fall = int(y.sum())
        n_adl = len(y) - n_fall
        n_sub = len(np.unique(groups))
        print(f"[Fenster] {len(y)} gesamt ({n_fall} Sturz, {n_adl} ADL) "
              f"von {n_sub} Probanden, Shape {X.shape}")

    return X, y, groups


# =====================================================================
#   LABEL-PRUEFUNG (--verify)
# =====================================================================
def verify_labels(root: Path, device: int = 3):
    """Zeigt Spitzenbeschleunigung pro Activity-ID — zum Pruefen der
    ADL/Fall-Grenze."""
    from collections import defaultdict
    acc_files = find_trials(root, device)
    peaks = defaultdict(list)

    for acc_path in acc_files:
        meta = parse_filename(acc_path)
        data = load_trial(acc_path)
        if data is None or len(data) < 10:
            continue
        mag = np.sqrt(np.sum(data[:, :3] ** 2, axis=1))
        peaks[meta["activity"]].append(float(np.max(mag)))

    print(f"\n{'Activity':>10}  {'Typ':>5}  {'Median Peak':>12}  "
          f"{'Max Peak':>10}  {'N':>4}")
    print("-" * 55)
    for aid in sorted(peaks.keys()):
        p = peaks[aid]
        typ = "FALL" if aid >= 101 else "ADL"
        print(f"  A{aid:03d}       {typ:>5}  {np.median(p):10.2f} g  "
              f"{np.max(p):8.2f} g  {len(p):4d}")

    adl_peaks = [v for k, vals in peaks.items() if k < 100 for v in vals]
    fall_peaks = [v for k, vals in peaks.items() if k >= 101 for v in vals]
    if adl_peaks and fall_peaks:
        print(f"\nADL  Median: {np.median(adl_peaks):.2f} g, "
              f"Max: {np.max(adl_peaks):.2f} g")
        print(f"FALL Median: {np.median(fall_peaks):.2f} g, "
              f"Max: {np.max(fall_peaks):.2f} g")


# =====================================================================
#   TRANSFER-EXPERIMENT
# =====================================================================
def run_transfer(X, y, groups):
    """Zero-Shot + Fine-Tuning auf FallAllD."""
    import tensorflow as tf
    from tensorflow import keras
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.metrics import confusion_matrix

    warnings.filterwarnings("ignore")

    # --- Modell laden ---
    if not MODEL_PATH.exists():
        print(f"[FEHLER] Modell nicht gefunden: {MODEL_PATH}")
        print("         Zuerst cnn_pipeline.py ausfuehren!")
        sys.exit(1)

    model = keras.models.load_model(MODEL_PATH, compile=False)
    print(f"\n[Modell] {MODEL_PATH} geladen "
          f"({model.count_params():,} Parameter)")

    # --- Subjektunabhaengiger Split ---
    gss = GroupShuffleSplit(n_splits=1, test_size=TEST_FRAC, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups))
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    g_test = groups[test_idx]

    test_subs = np.unique(g_test)
    train_subs = np.unique(groups[train_idx])
    print(f"[Split]  Train: {len(X_train)} Fenster "
          f"({len(train_subs)} Probanden)  |  "
          f"Test: {len(X_test)} Fenster ({len(test_subs)} Probanden)")

    # --- Check: Eingabedimension ---
    expected_shape = model.input_shape[1:]      # (100, 6) erwartet
    actual_shape = X_test.shape[1:]
    if expected_shape != actual_shape:
        print(f"\n[WARNUNG] Shape-Mismatch: Modell erwartet {expected_shape}, "
              f"Daten haben {actual_shape}")
        print(f"          FS_TARGET={FS_TARGET}, WINDOW_SEC={WINDOW_SEC}")
        sys.exit(1)

    # --- Zero-Shot ---
    def evaluate(m, X_t, y_t, label=""):
        y_pred = (m.predict(X_t, verbose=0).flatten() > 0.5).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_t, y_pred, labels=[0, 1]).ravel()
        se = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        sp = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        acc = (tp + tn) / len(y_t)
        print(f"  {label:12s}  Se={se:.3f}  Sp={sp:.3f}  "
              f"Acc={acc:.3f}  FP={fp}  FN={fn}")
        return {"Se": round(se, 4), "Sp": round(sp, 4),
                "Acc": round(acc, 4), "FP": int(fp), "FN": int(fn)}

    model.compile(optimizer="adam",
                  loss="binary_crossentropy",
                  metrics=["accuracy"])

    print("\n--- Zero-Shot (SisFall-Modell unveraendert) ---")
    res_zs = evaluate(model, X_test, y_test, "Zero-Shot")

    # --- Fine-Tuning ---
    print(f"\n--- Fine-Tuning ({FT_EPOCHS} Epochen, "
          f"LR={FT_LR}, Freeze={FREEZE_UPTO}) ---")

    ft_model = keras.models.clone_model(model)
    ft_model.set_weights(model.get_weights())

    # Schichten einfrieren
    for i, layer in enumerate(ft_model.layers):
        layer.trainable = (i >= FREEZE_UPTO)

    trainable = sum(1 for l in ft_model.layers if l.trainable)
    frozen = sum(1 for l in ft_model.layers if not l.trainable)
    print(f"  Schichten: {frozen} eingefroren, {trainable} trainierbar")

    # Class weights
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    if n_pos > 0 and n_neg > 0:
        cw = {0: len(y_train) / (2 * n_neg),
              1: len(y_train) / (2 * n_pos)}
    else:
        cw = None

    ft_model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=FT_LR),
        loss="binary_crossentropy",
        metrics=["accuracy"]
    )

    ft_model.fit(
        X_train, y_train,
        epochs=FT_EPOCHS,
        batch_size=32,
        class_weight=cw,
        validation_split=0.15,
        verbose=0,
        callbacks=[
            keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=10,
                restore_best_weights=True),
            keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=5)
        ]
    )

    res_ft = evaluate(ft_model, X_test, y_test, "Fine-Tuned")

    return {"zero_shot": res_zs, "fine_tuned": res_ft}


# =====================================================================
#   MAIN
# =====================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Transfer SisFall → FallAllD (Waist)")
    parser.add_argument("--verify", action="store_true",
                        help="Label-Pruefung statt Transfer")
    args = parser.parse_args()

    print("=" * 60)
    print(" Cross-Dataset Transfer: SisFall → FallAllD")
    print(f" Device {DEVICE} ({'Neck' if DEVICE==1 else 'Wrist' if DEVICE==2 else 'Waist'})")
    print(f" {FS_NATIVE} Hz → {FS_TARGET} Hz")
    print("=" * 60)

    if args.verify:
        verify_labels(FALLALLD_DIR, DEVICE)
        return

    # Daten laden
    trials = load_fallalld(FALLALLD_DIR, DEVICE)
    X, y, groups = prepare_windows(trials)

    # Transfer
    results = run_transfer(X, y, groups)

    # Ergebnisse speichern
    out = {
        "dataset": "FallAllD",
        "device": DEVICE,
        "fs_native": FS_NATIVE,
        "fs_target": FS_TARGET,
        "results": results
    }
    out_path = Path("fallalld_transfer_results.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n[gesichert] {out_path}")


if __name__ == "__main__":
    main()
