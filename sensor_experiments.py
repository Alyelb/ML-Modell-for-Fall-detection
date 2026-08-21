"""
sensor_experiments.py  --  Achsen-Ablation und Zielgruppenvalidierung
=====================================================================
Enthaelt die Lade- und Auswertefunktionen fuer zwei Experimente:

  1. Achsen-Ablation (3 vs. 6 Achsen)
     Prueft die zentrale Empfehlung aus Kapitel 2 empirisch: Wie viel
     Sensitivitaet kostet der Verzicht auf das Gyroskop?
     Datensaetze: SisFall (intern), UniMiB-SHAR (extern, nur 3 Achsen)

  2. WEDA-FALL Zielgruppentest
     Falsch-Positiv-Test auf Daten von Personen ueber 80 Jahren.
     Achtung: Die aelteren Probanden haben KEINE Stuerze ausgefuehrt,
     der Datensatz erlaubt fuer diese Gruppe daher nur eine
     Bewertung der Fehlalarmrate.

Verwendung: siehe das zugehoerige Colab-Notebook.
"""

from pathlib import Path
from math import gcd
import re

import numpy as np
from scipy.signal import resample_poly


# =====================================================================
#   GEMEINSAME PARAMETER
# =====================================================================
FS_TARGET = 50
WIN_SEC   = 2.0
OVERLAP   = 0.5
WIN_LEN   = int(FS_TARGET * WIN_SEC)
STEP      = int(WIN_LEN * (1 - OVERLAP))

# SisFall ADC -> physikalische Einheiten
ADXL_TO_G  = (2 * 16)   / (2 ** 13)
ITG_TO_DPS = (2 * 2000) / (2 ** 16)

G_MS2       = 9.80665      # m/s^2 -> g
RAD_TO_DEG  = 57.29578     # rad/s -> deg/s


# =====================================================================
#   HILFSFUNKTIONEN
# =====================================================================
def downsample(sig, fs_from, fs_to):
    if int(fs_from) == int(fs_to):
        return sig
    g = gcd(int(fs_from), int(fs_to))
    return resample_poly(sig, fs_to // g, fs_from // g, axis=0)


def znorm(X):
    mu = X.mean(axis=1, keepdims=True)
    sd = X.std(axis=1, keepdims=True) + 1e-8
    return (X - mu) / sd


def window_trial(signal, label, win_len=WIN_LEN, step=STEP):
    """Impact-zentriert bei Stuerzen, gleitend bei ADL."""
    out, n = [], len(signal)
    if label == 1:
        mag = np.sqrt(np.sum(signal[:, :3] ** 2, axis=1))
        peak = int(np.argmax(mag))
        start = max(0, peak - win_len // 2)
        end = start + win_len
        if end > n:
            end, start = n, max(0, n - win_len)
        if end - start == win_len:
            out.append(signal[start:end])
    else:
        for s in range(0, n - win_len + 1, step):
            out.append(signal[s:s + win_len])
    return out


def select_channels(X, mode):
    """mode: 'acc6' (alle), 'acc3' (nur Beschleunigung),
             'gyr3' (nur Drehrate)"""
    if mode == "acc6":
        return X
    if mode == "acc3":
        return X[:, :, 0:3]
    if mode == "gyr3":
        return X[:, :, 3:6]
    raise ValueError(f"Unbekannter Modus: {mode}")


# =====================================================================
#   SISFALL
# =====================================================================
def load_sisfall_trial(path):
    rows = []
    for line in Path(path).read_text(errors="ignore").splitlines():
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
    arr = np.asarray(rows, dtype=np.float32)
    acc = arr[:, 0:3] * ADXL_TO_G
    gyr = arr[:, 3:6] * ITG_TO_DPS
    return np.hstack([acc, gyr])


def load_sisfall(root, fs_source=200, verbose=True):
    """Rueckgabe: X (N, WIN_LEN, 6), y, groups"""
    files = sorted(Path(root).rglob("*.txt"))
    if verbose:
        print(f"[SisFall] {len(files)} Dateien")

    X, y, g = [], [], []
    for f in files:
        parts = f.stem.split("_")
        label = 1 if parts[0].upper().startswith("F") else 0
        subject = parts[1] if len(parts) > 1 else "UNK"

        data = load_sisfall_trial(f)
        if data is None or len(data) < fs_source:
            continue
        data = downsample(data, fs_source, FS_TARGET)
        for w in window_trial(data, label):
            X.append(w); y.append(label); g.append(subject)

    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=np.int32)
    g = np.asarray(g)
    if verbose:
        print(f"[SisFall] {len(y)} Fenster "
              f"({int(y.sum())} Sturz, {len(y)-int(y.sum())} ADL)")
    return X, y, g


# =====================================================================
#   UNIMIB-SHAR   (nur 3 Achsen, .mat-Format)
# =====================================================================
# Aktivitaeten 1-9  = ADL, 10-17 = Sturz  (aus acc_names.mat abgeleitet)
UNIMIB_FALL_START = 10
UNIMIB_WIN        = 151     # Fensterlaenge im Datensatz
UNIMIB_FS         = 50


def load_unimib(mat_dir, verbose=True):
    """Laedt acc_data.mat / acc_labels.mat.

    Struktur: jede Zeile in acc_data ist ein Fenster mit 453 Werten,
    das als (3, 151) zu interpretieren ist -- also drei Achsen
    hintereinander, je 151 Abtastwerte. Einheit ist m/s^2.

    Rueckgabe: X (N, WIN_LEN, 3) in g, y, groups (Probanden-ID)
    """
    import scipy.io as sio

    mat_dir = Path(mat_dir)
    data = sio.loadmat(mat_dir / "acc_data.mat")["acc_data"]
    lab  = sio.loadmat(mat_dir / "acc_labels.mat")["acc_labels"]

    if verbose:
        print(f"[UniMiB] {data.shape[0]} Fenster, "
              f"{len(np.unique(lab[:, 1]))} Probanden")

    # Mittigen Ausschnitt der Laenge WIN_LEN entnehmen
    lo = (UNIMIB_WIN - WIN_LEN) // 2
    hi = lo + WIN_LEN

    X = data.reshape(-1, 3, UNIMIB_WIN)        # (N, 3, 151)
    X = np.transpose(X, (0, 2, 1))             # (N, 151, 3)
    X = X[:, lo:hi, :]                         # (N, WIN_LEN, 3)
    X = (X / G_MS2).astype(np.float32)         # m/s^2 -> g

    y = (lab[:, 0] >= UNIMIB_FALL_START).astype(np.int32)
    groups = lab[:, 1].astype(np.int32)

    if verbose:
        print(f"[UniMiB] {len(y)} Fenster "
              f"({int(y.sum())} Sturz, {len(y)-int(y.sum())} ADL), "
              f"Shape {X.shape}")
    return X, y, groups


# =====================================================================
#   WEDA-FALL   (Handgelenk, Fitbit Sense)
# =====================================================================
# Verzeichnisstruktur:  dataset/50Hz/<Bewegungscode>/U<id>_R<trial>_<typ>.csv
#   Bewegungscodes:  D01..D11 = ADL,  F01..F08 = Sturz
#   Sensortypen:     accel, gyro, orientation, vertical_accel
#   Einheiten:       m/s^2 bzw. rad/s, Kopfzeile vorhanden
#
# ZWEI BESONDERHEITEN DIESES DATENSATZES:
#
# 1) Die Zeitstempel sind stark ungleichmaessig. Die Fitbit-Erfassung
#    liefert Buendel von Abtastwerten im Abstand von 1-2 ms, gefolgt
#    von Luecken bis zu 93 ms. Die effektive Rate schwankt je nach
#    Datei zwischen etwa 40 und 50 Hz. Die Zeilen duerfen daher NICHT
#    als gleichmaessig abgetastet behandelt werden; es wird auf ein
#    regelmaessiges Raster interpoliert.
#
# 2) Die aelteren Probanden (U21-U31, 77-95 Jahre) haben aus
#    Sicherheitsgruenden KEINE Stuerze ausgefuehrt. Fuer diese Gruppe
#    ist ausschliesslich die Fehlalarmrate bewertbar.
# =====================================================================
WEDA_FS = 50

WEDA_YOUNG   = {f"U{i:02d}" for i in range(1, 15)}    # U01-U14
WEDA_ELDERLY = {f"U{i:02d}" for i in range(21, 32)}   # U21-U31

WEDA_MOVEMENTS = {
    "D01": "Gehen",                 "D02": "Joggen",
    "D03": "Treppe auf/ab",         "D04": "Hinsetzen/Aufstehen",
    "D05": "In Stuhl fallen",       "D06": "Hocken/Schuhe binden",
    "D07": "Stolpern",              "D08": "Springen",
    "D09": "Auf Tisch schlagen",    "D10": "Klatschen",
    "D11": "Tuer oeffnen",
    "F01": "Sturz vorwaerts (Ausrutschen)",
    "F02": "Sturz seitlich (Ausrutschen)",
    "F03": "Sturz rueckwaerts (Ausrutschen)",
    "F04": "Sturz vorwaerts (Stolpern)",
    "F05": "Sturz rueckwaerts beim Hinsetzen",
    "F06": "Sturz vorwaerts im Sitzen",
    "F07": "Sturz rueckwaerts im Sitzen",
    "F08": "Sturz seitlich im Sitzen",
}


def _read_weda_csv(path):
    """Liest eine WEDA-CSV anhand der Kopfzeile.

    Rueckgabe: (t, xyz) mit t (N,) in Sekunden und xyz (N, 3),
    oder None.
    """
    try:
        lines = Path(path).read_text(errors="ignore").splitlines()
    except Exception:
        return None
    if len(lines) < 2:
        return None

    header = [h.strip().lstrip("\ufeff").lower()
              for h in lines[0].split(",")]

    def col(suffix):
        for i, h in enumerate(header):
            if h.endswith(suffix):
                return i
        return None

    it, ix = col("time_list"), col("x_list")
    iy, iz = col("y_list"), col("z_list")
    if None in (it, ix, iy, iz):
        return None

    rows = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        p = line.split(",")
        if len(p) <= max(it, ix, iy, iz):
            continue
        try:
            rows.append((float(p[it]), float(p[ix]),
                         float(p[iy]), float(p[iz])))
        except ValueError:
            continue

    if len(rows) < 10:
        return None
    arr = np.asarray(rows, dtype=np.float64)
    return arr[:, 0], arr[:, 1:4]


def _resample_to_grid(t, xyz, fs=WEDA_FS):
    """Interpoliert ungleichmaessig abgetastete Daten auf ein
    regelmaessiges Raster mit fs Hz."""
    # Zeitstempel muessen streng monoton sein
    keep = np.concatenate([[True], np.diff(t) > 0])
    t, xyz = t[keep], xyz[keep]
    if len(t) < 10:
        return None

    duration = t[-1] - t[0]
    if duration <= 0:
        return None

    n = int(np.floor(duration * fs)) + 1
    grid = t[0] + np.arange(n) / fs
    out = np.empty((n, xyz.shape[1]), dtype=np.float32)
    for c in range(xyz.shape[1]):
        out[:, c] = np.interp(grid, t, xyz[:, c])
    return out


def find_weda_trials(root, fs_dir="50Hz"):
    """Sucht alle Trials. Rueckgabe: Liste von Metadaten-Dicts."""
    root = Path(root)

    # Datensatzwurzel finden (dataset/<fs>/<code>/)
    cand = list(root.rglob(fs_dir))
    base = cand[0] if cand else root

    out = []
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        code = d.name.upper()
        seen = {}
        for f in sorted(d.glob("*.csv")):
            m = re.match(r"(U\d+)_R(\d+)_(.+)", f.stem)
            if not m:
                continue
            user, trial, stype = m.group(1), int(m.group(2)), m.group(3).lower()
            seen.setdefault((user, trial), {})[stype] = f

        for (user, trial), files in sorted(seen.items()):
            if "accel" not in files:
                continue
            out.append({
                "movement": code,
                "label":    1 if code.startswith("F") else 0,
                "user":     user,
                "trial":    trial,
                "accel":    files["accel"],
                "gyro":     files.get("gyro"),
                "group":    ("elderly" if user in WEDA_ELDERLY
                             else "young" if user in WEDA_YOUNG else "other"),
            })
    return out


def load_weda(root, group=None, fs_dir="50Hz", verbose=True):
    """Laedt WEDA-FALL.

    group: None (alle), 'young' oder 'elderly'.

    Rueckgabe: X (N, WIN_LEN, 6) in [g, rad/s], y, groups (User-ID),
               meta (Bewegungscode je Fenster)
    """
    entries = find_weda_trials(root, fs_dir)
    if not entries:
        print(f"[WEDA] Keine Trials gefunden unter {root}")
        return (np.empty((0, WIN_LEN, 6), np.float32),
                np.empty(0, np.int32), np.empty(0), np.empty(0))

    if group is not None:
        entries = [e for e in entries if e["group"] == group]

    if verbose:
        users = sorted({e["user"] for e in entries})
        n_f = sum(e["label"] for e in entries)
        print(f"[WEDA] {len(entries)} Trials "
              f"({n_f} Sturz, {len(entries)-n_f} ADL)")
        print(f"[WEDA] Gruppe: {group or 'alle'} | "
              f"{len(users)} Probanden: {', '.join(users)}")

    X, y, g, meta = [], [], [], []
    skipped = 0

    for e in entries:
        a = _read_weda_csv(e["accel"])
        if a is None:
            skipped += 1
            continue
        t_a, acc = a
        acc_r = _resample_to_grid(t_a, acc, WEDA_FS)
        if acc_r is None or len(acc_r) < WEDA_FS:
            skipped += 1
            continue

        if e["gyro"] is not None:
            gy = _read_weda_csv(e["gyro"])
            if gy is None:
                skipped += 1
                continue
            t_g, gyr = gy
            gyr_r = _resample_to_grid(t_g, gyr, WEDA_FS)
            if gyr_r is None:
                skipped += 1
                continue
            n = min(len(acc_r), len(gyr_r))
            data = np.hstack([acc_r[:n], gyr_r[:n]])
        else:
            skipped += 1
            continue

        # Einheiten an SisFall angleichen:
        #   Beschleunigung  m/s^2 -> g
        #   Drehrate        rad/s -> deg/s
        # (Der Fitbit liefert rad/s; Spitzenwerte um 32 rad/s
        #  entsprechen rund 1820 deg/s und liegen damit im selben
        #  Bereich wie die ITG3200-Daten von SisFall.)
        data[:, :3] /= G_MS2
        data[:, 3:] *= RAD_TO_DEG

        if WEDA_FS != FS_TARGET:
            data = downsample(data, WEDA_FS, FS_TARGET)

        for w in window_trial(data, e["label"]):
            X.append(w); y.append(e["label"])
            g.append(e["user"]); meta.append(e["movement"])

    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=np.int32)
    g = np.asarray(g)
    meta = np.asarray(meta)

    if verbose:
        print(f"[WEDA] {len(y)} Fenster "
              f"({int(y.sum())} Sturz, {len(y)-int(y.sum())} ADL)")
        if skipped:
            print(f"[WEDA] uebersprungen: {skipped}")
    return X, y, g, meta


# =====================================================================
#   MODELL UND AUSWERTUNG
# =====================================================================
def build_cnn(win_len, n_channels, dropout=0.3, lr=1e-3):
    """Identische Architektur wie in cnn_pipeline.py, lediglich die
    Zahl der Eingangskanaele ist parametrierbar."""
    from tensorflow import keras
    from tensorflow.keras import layers

    m = keras.Sequential([
        layers.Input(shape=(win_len, n_channels)),
        layers.Conv1D(32, 5, activation="relu"),
        layers.BatchNormalization(),
        layers.MaxPooling1D(2),
        layers.Conv1D(64, 5, activation="relu"),
        layers.BatchNormalization(),
        layers.MaxPooling1D(2),
        layers.Conv1D(128, 5, activation="relu"),
        layers.BatchNormalization(),
        layers.GlobalAveragePooling1D(),
        layers.Dense(64, activation="relu"),
        layers.Dropout(dropout),
        layers.Dense(1, activation="sigmoid"),
    ])
    m.compile(optimizer=keras.optimizers.Adam(learning_rate=lr),
              loss="binary_crossentropy", metrics=["accuracy"])
    return m


def evaluate(model, X, y, label=""):
    from sklearn.metrics import confusion_matrix
    p = (model.predict(X, verbose=0).flatten() > 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[0, 1]).ravel()
    se = tp / (tp + fn) if (tp + fn) else 0.0
    sp = tn / (tn + fp) if (tn + fp) else 0.0
    ac = (tp + tn) / len(y)
    if label:
        print(f"  {label:22s}  Se={se:.3f}  Sp={sp:.3f}  Acc={ac:.3f}  "
              f"FP={fp:>4d}  FN={fn:>3d}")
    return {"Se": round(se, 4), "Sp": round(sp, 4), "Acc": round(ac, 4),
            "FP": int(fp), "FN": int(fn)}
