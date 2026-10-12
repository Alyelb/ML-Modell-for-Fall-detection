"""
fall_lib.py  --  Gemeinsame Bibliothek fuer alle Experimente
=============================================================
Eine einzige Quelle fuer Datensatz-Loader, Fensterung, Modell und
Auswertung. Alle Notebooks importieren dieses Modul, damit eine
Korrektur an einer Stelle in allen Experimenten wirksam wird.

Aufbau
------
  1. Konstanten und Hilfsfunktionen
  2. Fensterung
  3. Datensatz-Loader (SisFall, KFall, UMAFall, FallAllD,
     UniMiB-SHAR, WEDA-FALL, CAPPIMU, ImbalanSense,
     Smart-Insole)
  4. Modell und Auswertung
  5. Zeitliche Plausibilisierung (N-von-M-Voting)
  6. Ergebnisverwaltung

Verwendung
----------
    import fall_lib as fl
    X, y, g = fl.load_sisfall("/content/SisFall")
    run = fl.new_run("cross_dataset_kfall")
    fl.save_results(run, {"Se": 0.83})
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from math import gcd
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly


# =====================================================================
#  1. KONSTANTEN UND HILFSFUNKTIONEN
# =====================================================================
FS_TARGET = 50          # Ziel-Abtastrate aller Pipelines
WIN_SEC   = 2.0         # Fensterlaenge in Sekunden
OVERLAP   = 0.5         # Standardueberlappung
WIN_LEN   = int(FS_TARGET * WIN_SEC)
STEP      = int(WIN_LEN * (1 - OVERLAP))

# Einheiten
G_MS2      = 9.80665        # m/s^2 -> g
RAD_TO_DEG = 57.29578       # rad/s -> deg/s

# SisFall: ADC -> physikalische Einheiten
ADXL_TO_G  = (2 * 16)   / (2 ** 13)
ITG_TO_DPS = (2 * 2000) / (2 ** 16)

# FallAllD (LSM9DS1), aus dem offiziellen MATLAB-Skript
FALLALLD_ACC_SEN = 0.000244     # g/LSB
FALLALLD_GYR_SEN = 0.07         # deg/s/LSB


def downsample(sig: np.ndarray, fs_from, fs_to) -> np.ndarray:
    """Polyphasen-Resampling mit Anti-Aliasing."""
    fs_from, fs_to = int(fs_from), int(fs_to)
    if fs_from == fs_to:
        return sig
    d = gcd(fs_from, fs_to)
    return resample_poly(sig, fs_to // d, fs_from // d, axis=0)


def znorm(X: np.ndarray) -> np.ndarray:
    """Z-Normalisierung je Fenster und je Kanal.

    Wichtig: Die Normalisierung erfolgt entlang der Zeitachse (axis=1)
    getrennt fuer jeden Kanal. Absolute Skalenunterschiede zwischen
    Datensaetzen werden dadurch aufgehoben, die Signalform bleibt
    erhalten.
    """
    mu = X.mean(axis=1, keepdims=True)
    sd = X.std(axis=1, keepdims=True) + 1e-8
    return (X - mu) / sd


def acc_magnitude(sig: np.ndarray) -> np.ndarray:
    """Betrag der Beschleunigung (erste drei Kanaele)."""
    return np.sqrt(np.sum(sig[..., :3] ** 2, axis=-1))


# =====================================================================
#  2. FENSTERUNG
# =====================================================================
def window_impact_centered(signal, win_len=WIN_LEN, impact_idx=None):
    """Ein Fenster, zentriert auf den Aufprall.

    impact_idx: Ist der Aufprallzeitpunkt bekannt (z.B. aus den
    KFall-Labeldateien), wird er verwendet. Andernfalls dient das
    Maximum des Beschleunigungsbetrags als Naeherung.
    """
    n = len(signal)
    if n < win_len:
        return []
    if impact_idx is None:
        impact_idx = int(np.argmax(acc_magnitude(signal)))
    start = max(0, impact_idx - win_len // 2)
    end = start + win_len
    if end > n:
        end, start = n, n - win_len
    return [signal[start:end]]


def window_sliding(signal, win_len=WIN_LEN, step=STEP):
    """Gleitende Fenster in zeitlicher Reihenfolge."""
    return [signal[s:s + win_len]
            for s in range(0, len(signal) - win_len + 1, step)]


def window_trial(signal, label, win_len=WIN_LEN, step=STEP,
                 impact_idx=None):
    """Standardfensterung: impact-zentriert bei Stuerzen, gleitend
    bei ADL.

    Diese Variante wird fuer Training und Klassifikation einzelner
    Fenster verwendet. Fuer das Voting wird stattdessen
    `window_sliding_labeled` benoetigt, da dort die zeitliche Abfolge
    erhalten bleiben muss.
    """
    if label == 1:
        return window_impact_centered(signal, win_len, impact_idx)
    return window_sliding(signal, win_len, step)


def window_sliding_labeled(signal, label, win_len=WIN_LEN, step=STEP,
                           impact_idx=None):
    """Gleitende Fenster MIT korrekter Fensterbeschriftung.

    Hintergrund: Eine Sturzaufzeichnung von 15 Sekunden besteht
    ueberwiegend aus normalem Gehen oder Stehen; der eigentliche
    Aufprall dauert nur Bruchteile einer Sekunde. Werden alle Fenster
    einer Sturzaufzeichnung pauschal als "Sturz" beschriftet, entsteht
    erhebliches Label-Rauschen.

    Hier gilt ein Fenster nur dann als Sturz, wenn es den Aufprall
    tatsaechlich enthaelt. Alle uebrigen Fenster einer
    Sturzaufzeichnung werden als ADL beschriftet.

    Rueckgabe: (windows, labels)
    """
    wins = window_sliding(signal, win_len, step)
    if not wins:
        return [], []

    if label == 0:
        return wins, [0] * len(wins)

    if impact_idx is None:
        impact_idx = int(np.argmax(acc_magnitude(signal)))

    labels = []
    for i in range(len(wins)):
        start = i * step
        labels.append(1 if start <= impact_idx < start + win_len else 0)
    return wins, labels


def build_windows(trials, mode="standard", win_len=WIN_LEN, step=STEP):
    """Erzeugt aus einer Trial-Liste die Fenster-Arrays.

    trials: Liste von Dicts mit den Schluesseln
            'data' (N,6), 'label' (0/1), 'subject', optional
            'impact_idx' und 'activity'.
    mode:   'standard'  -> window_trial (Training/Einzelfenster)
            'sliding'   -> window_sliding_labeled (Voting/FP-Tests)

    Rueckgabe: X, y, groups, activities
    """
    X, y, g, a = [], [], [], []
    for t in trials:
        if mode == "sliding":
            wins, labs = window_sliding_labeled(
                t["data"], t["label"], win_len, step,
                t.get("impact_idx"))
        else:
            wins = window_trial(t["data"], t["label"], win_len, step,
                                t.get("impact_idx"))
            labs = [t["label"]] * len(wins)

        for w, l in zip(wins, labs):
            X.append(w); y.append(l)
            g.append(t["subject"]); a.append(t.get("activity", ""))

    if not X:
        return (np.empty((0, win_len, 6), np.float32),
                np.empty(0, np.int32), np.empty(0), np.empty(0))

    return (np.asarray(X, dtype=np.float32),
            np.asarray(y, dtype=np.int32),
            np.asarray(g), np.asarray(a))


# =====================================================================
#  3. DATENSATZ-LOADER
# =====================================================================
# Jeder Loader gibt eine Liste von Trial-Dicts zurueck:
#   {'data': (N,6) float32, 'label': 0|1, 'subject': str,
#    'activity': str, 'impact_idx': int|None}
# Die Kanalreihenfolge ist stets [AccX, AccY, AccZ, GyrX, GyrY, GyrZ]
# in den Einheiten [g, g, g, deg/s, deg/s, deg/s].
# =====================================================================

# ---------------------------------------------------------------------
#  SisFall  (Huefte, 200 Hz, +-16 g)
# ---------------------------------------------------------------------
SISFALL_FS = 200


def _read_sisfall_file(path):
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
    return np.hstack([arr[:, 0:3] * ADXL_TO_G,
                      arr[:, 3:6] * ITG_TO_DPS])


def load_sisfall(root, verbose=True):
    """SisFall. Dateiname: D01_SA01_R01.txt (D=ADL, F=Sturz)."""
    files = sorted(Path(root).rglob("*.txt"))
    trials = []
    for f in files:
        parts = f.stem.split("_")
        if not parts[0] or parts[0][0].upper() not in ("D", "F"):
            continue
        data = _read_sisfall_file(f)
        if data is None or len(data) < SISFALL_FS:
            continue
        trials.append({
            "data": downsample(data, SISFALL_FS, FS_TARGET),
            "label": 1 if parts[0][0].upper() == "F" else 0,
            "subject": parts[1] if len(parts) > 1 else "UNK",
            "activity": parts[0],
            "impact_idx": None,
        })
    if verbose:
        n_f = sum(t["label"] for t in trials)
        print(f"[SisFall] {len(trials)} Trials ({n_f} Sturz, "
              f"{len(trials)-n_f} ADL), "
              f"{len({t['subject'] for t in trials})} Probanden")
    return trials


# ---------------------------------------------------------------------
#  KFall  (unterer Ruecken, 100 Hz, Xsens MTw Awinda)
# ---------------------------------------------------------------------
KFALL_FS = 100

# KORREKTUR gegenueber frueheren Versionen dieses Projekts:
# Die Sturz-Tasks sind T20 bis T34, NICHT T22 bis T36.
# Nachgewiesen anhand der offiziellen Labeldateien (label_data_new.zip):
# dort ist F01 als Task 20 und F15 als Task 34 ausgewiesen, und der
# dokumentierte Fall_impact_frame stimmt bei T20 auf einen Abtastwert
# genau mit dem gemessenen Beschleunigungsmaximum ueberein, bei T22
# hingegen nicht. Die Spitzenwertanalyse bestaetigt dies:
#   T19: 1,56 g | T20: 4,52 g | T34: 4,75 g | T35: 2,13 g
# ADL sind damit T01-T19 sowie T35-T36 (21 Typen),
# Stuerze T20-T34 (15 Typen).
KFALL_FALL_TASKS = set(range(20, 35))       # T20..T34


def load_kfall_labels(label_dir):
    """Liest die offiziellen Labeldateien (*.xlsx) ein.

    Rueckgabe: {(subject_int, task_int, trial_int): impact_frame}
    Fehlt openpyxl oder das Verzeichnis, wird ein leeres Dict
    zurueckgegeben; die Loader nutzen dann das Beschleunigungsmaximum.
    """
    out = {}
    if label_dir is None or not Path(label_dir).exists():
        return out
    try:
        import openpyxl
    except ImportError:
        print("[KFall] openpyxl nicht verfuegbar -> Aufprallzeitpunkt "
              "wird geschaetzt")
        return out

    for f in sorted(Path(label_dir).rglob("*_label.xlsx")):
        m = re.search(r"SA(\d+)", f.stem)
        if not m:
            continue
        subject = int(m.group(1))
        try:
            ws = openpyxl.load_workbook(f, read_only=True).active
        except Exception:
            continue
        task = None
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0]:
                mt = re.search(r"\((\d+)\)", str(row[0]))
                task = int(mt.group(1)) if mt else None
            if task is None or row[2] is None or row[4] is None:
                continue
            try:
                out[(subject, task, int(row[2]))] = int(row[4])
            except (TypeError, ValueError):
                continue
    return out


def load_kfall(root, label_dir=None, verbose=True):
    """KFall. Dateiname: S06T01R01.csv
    Spalten: TimeStamp, FrameCounter, AccX..Z, GyrX..Z, EulerX..Z
    """
    labels = load_kfall_labels(label_dir)
    files = sorted(Path(root).rglob("*.csv"))
    trials = []
    n_lab = 0

    for f in files:
        m = re.search(r"S(\d+)T(\d+)R(\d+)", f.stem)
        if not m:
            continue
        subject, task, trial = (int(m.group(1)), int(m.group(2)),
                                int(m.group(3)))
        label = 1 if task in KFALL_FALL_TASKS else 0

        try:
            arr = np.genfromtxt(f, delimiter=",", skip_header=1)
        except Exception:
            continue
        if arr.ndim != 2 or arr.shape[1] < 8:
            continue
        data = arr[:, 2:8].astype(np.float32)
        data = data[~np.isnan(data).any(axis=1)]
        if len(data) < KFALL_FS:
            continue

        # Aufprallzeitpunkt aus der Labeldatei, auf die Zielrate skaliert
        impact = labels.get((subject, task, trial))
        if impact is not None:
            impact = int(impact * FS_TARGET / KFALL_FS)
            n_lab += 1

        trials.append({
            "data": downsample(data, KFALL_FS, FS_TARGET),
            "label": label,
            "subject": f"S{subject:02d}",
            "activity": f"T{task:02d}",
            "impact_idx": impact,
        })

    if verbose:
        n_f = sum(t["label"] for t in trials)
        print(f"[KFall] {len(trials)} Trials ({n_f} Sturz, "
              f"{len(trials)-n_f} ADL), "
              f"{len({t['subject'] for t in trials})} Probanden")
        print(f"[KFall] Sturz-Tasks T20-T34 | "
              f"{n_lab} Aufprallzeitpunkte aus Labeldateien")
    return trials


# ---------------------------------------------------------------------
#  UMAFall  (fuenf Positionen gleichzeitig, 20 Hz)
# ---------------------------------------------------------------------
UMAFALL_FS = 20
UMAFALL_POSITIONS = ("RIGHTPOCKET", "CHEST", "WAIST", "WRIST", "ANKLE")


def _umafall_sensor_map(path):
    """Sensor_ID -> Position aus dem Dateikopf.

    Die Zuordnung variiert zwischen Dateien und muss pro Datei
    gelesen werden. Der Kopf enthaelt Leerzeilen; er endet erst mit
    der ersten Datenzeile.
    """
    mapping = {}
    with open(path, "r", errors="ignore") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            if not s.startswith("%"):
                break
            parts = [p.strip() for p in s.lstrip("%").split(";")]
            if len(parts) >= 3 and parts[1].isdigit():
                mapping[int(parts[1])] = parts[2].upper()
    return mapping


def _read_umafall_file(path, position):
    sm = _umafall_sensor_map(path)
    sid = next((k for k, v in sm.items() if v == position), None)
    if sid is None:
        return None
    acc, gyr = {}, {}
    with open(path, "r", errors="ignore") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("%"):
                continue
            p = s.split(";")
            if len(p) < 7:
                continue
            try:
                smp = int(p[1])
                xyz = (float(p[2]), float(p[3]), float(p[4]))
                stype, sensor_id = int(p[5]), int(p[6])
            except ValueError:
                continue
            if sensor_id != sid:
                continue
            if stype == 0:
                acc[smp] = xyz
            elif stype == 1:
                gyr[smp] = xyz
    if not acc or not gyr:
        return None
    common = sorted(set(acc) & set(gyr))
    if len(common) < 10:
        return None
    return np.array([list(acc[s]) + list(gyr[s]) for s in common],
                    dtype=np.float32)


def load_umafall(root, position="ANKLE", verbose=True):
    """UMAFall fuer eine bestimmte Sensorposition."""
    position = position.upper()
    trials = []
    for f in sorted(Path(root).rglob("*.csv")):
        is_fall = "_FALL_" in f.stem.upper()
        ms = re.search(r"Subject_(\d+)", f.stem, re.IGNORECASE)
        # Die Schreibweise des Klassenmarkers schwankt zwischen den
        # Dateien: 208 der 746 Aufzeichnungen verwenden "_Fall_"
        # statt "_FALL_". Ohne IGNORECASE bleibt der Aktivitaetsname
        # dieser Dateien unerkannt. Die Klassenzuordnung oben ist
        # davon nicht betroffen, da sie ohnehin auf .upper() beruht.
        ma = re.search(r"_(?:ADL|FALL)_(.+?)_\d+_\d{4}-", f.stem,
                       re.IGNORECASE)
        data = _read_umafall_file(f, position)
        if data is None or len(data) < UMAFALL_FS:
            continue
        trials.append({
            "data": downsample(data, UMAFALL_FS, FS_TARGET),
            "label": 1 if is_fall else 0,
            "subject": f"S{int(ms.group(1)):02d}" if ms else "UNK",
            "activity": ma.group(1) if ma else "unknown",
            "impact_idx": None,
        })
    if verbose:
        n_f = sum(t["label"] for t in trials)
        print(f"[UMAFall {position}] {len(trials)} Trials "
              f"({n_f} Sturz, {len(trials)-n_f} ADL), "
              f"{len({t['subject'] for t in trials})} Probanden")
    return trials


# ---------------------------------------------------------------------
#  FallAllD  (drei Positionen, 238 Hz, LSM9DS1, +-8 g)
# ---------------------------------------------------------------------
FALLALLD_FS = 238
FALLALLD_DEVICES = {1: "NECK", 2: "WRIST", 3: "WAIST"}
FALLALLD_ADL  = set(range(1, 45))        # A001..A044
FALLALLD_FALL = set(range(101, 136))     # A101..A135


def load_fallalld(root, device=3, verbose=True):
    """FallAllD. Je Trial vier Dateien (_A, _G, _M, _B);
    verwendet werden Beschleunigung und Drehrate.
    Dateiname: S01_D3_A013_T01_A.dat
    """
    pattern = f"*_D{device}_*_A.dat"
    files = sorted(Path(root).glob(pattern)) or \
            sorted(Path(root).rglob(pattern))
    trials = []
    for acc_path in files:
        parts = acc_path.stem.split("_")
        if len(parts) < 4:
            continue
        try:
            subject = int(parts[0][1:])
            activity = int(parts[2][1:])
        except ValueError:
            continue
        if activity in FALLALLD_FALL:
            label = 1
        elif activity in FALLALLD_ADL:
            label = 0
        else:
            continue

        gyr_path = acc_path.parent / acc_path.name.replace("_A.dat",
                                                           "_G.dat")
        if not gyr_path.exists():
            continue
        try:
            a = np.loadtxt(acc_path, delimiter=",", dtype=np.int16)
            g = np.loadtxt(gyr_path, delimiter=",", dtype=np.int16)
        except Exception:
            continue
        n = min(len(a), len(g))
        if n < FALLALLD_FS:
            continue
        data = np.hstack([a[:n].astype(np.float32) * FALLALLD_ACC_SEN,
                          g[:n].astype(np.float32) * FALLALLD_GYR_SEN])
        trials.append({
            "data": downsample(data, FALLALLD_FS, FS_TARGET),
            "label": label,
            "subject": f"S{subject:02d}",
            "activity": f"A{activity:03d}",
            "impact_idx": None,
        })
    if verbose:
        n_f = sum(t["label"] for t in trials)
        print(f"[FallAllD {FALLALLD_DEVICES.get(device, device)}] "
              f"{len(trials)} Trials ({n_f} Sturz, "
              f"{len(trials)-n_f} ADL), "
              f"{len({t['subject'] for t in trials})} Probanden")
    return trials


# ---------------------------------------------------------------------
#  UniMiB-SHAR  (Hosentasche, 50 Hz, NUR Beschleunigung, +-2 g)
# ---------------------------------------------------------------------
UNIMIB_WIN        = 151
UNIMIB_FALL_START = 10      # Aktivitaeten 1-9 = ADL, 10-17 = Sturz


def load_unimib(mat_dir, verbose=True):
    """UniMiB-SHAR aus acc_data.mat / acc_labels.mat.

    Der Datensatz liegt bereits gefenstert vor (151 Abtastwerte je
    Fenster, als 3x151 gespeichert, Einheit m/s^2). Er enthaelt
    ausschliesslich Beschleunigungsdaten.

    Rueckgabe abweichend von den uebrigen Loadern:
    X (N, WIN_LEN, 3) in g, y, groups
    """
    import scipy.io as sio
    mat_dir = Path(mat_dir)
    data = sio.loadmat(mat_dir / "acc_data.mat")["acc_data"]
    lab = sio.loadmat(mat_dir / "acc_labels.mat")["acc_labels"]

    lo = (UNIMIB_WIN - WIN_LEN) // 2
    X = data.reshape(-1, 3, UNIMIB_WIN)
    X = np.transpose(X, (0, 2, 1))[:, lo:lo + WIN_LEN, :]
    X = (X / G_MS2).astype(np.float32)

    y = (lab[:, 0] >= UNIMIB_FALL_START).astype(np.int32)
    groups = np.array([f"S{s:02d}" for s in lab[:, 1]])

    if verbose:
        print(f"[UniMiB] {len(y)} Fenster ({int(y.sum())} Sturz, "
              f"{len(y)-int(y.sum())} ADL), "
              f"{len(np.unique(groups))} Probanden, nur 3 Achsen")
        print(f"[UniMiB] Messbereich des Smartphones: "
              f"max {np.abs(X).max():.2f} g")
    return X, y, groups


# ---------------------------------------------------------------------
#  WEDA-FALL  (Handgelenk, Fitbit Sense)
# ---------------------------------------------------------------------
WEDA_FS      = 50
WEDA_YOUNG   = {f"U{i:02d}" for i in range(1, 15)}     # 20-46 Jahre
WEDA_ELDERLY = {f"U{i:02d}" for i in range(21, 32)}    # 77-95 Jahre

WEDA_MOVEMENTS = {
    "D01": "Gehen",              "D02": "Joggen",
    "D03": "Treppe auf/ab",      "D04": "Hinsetzen/Aufstehen",
    "D05": "In Stuhl fallen",    "D06": "Hocken/Schuhe binden",
    "D07": "Stolpern",           "D08": "Springen",
    "D09": "Auf Tisch schlagen", "D10": "Klatschen",
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
    """Liest eine WEDA-CSV anhand ihrer Kopfzeile.
    Rueckgabe: (t, xyz) oder None."""
    try:
        lines = Path(path).read_text(errors="ignore").splitlines()
    except Exception:
        return None
    if len(lines) < 2:
        return None
    header = [h.strip().lstrip("\ufeff").lower()
              for h in lines[0].split(",")]

    def col(suffix):
        return next((i for i, h in enumerate(header)
                     if h.endswith(suffix)), None)

    it, ix, iy, iz = (col("time_list"), col("x_list"),
                      col("y_list"), col("z_list"))
    if None in (it, ix, iy, iz):
        return None

    rows = []
    for line in lines[1:]:
        p = line.strip().split(",")
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


def _weda_to_grid(t, xyz, fs=WEDA_FS):
    """Interpolation auf ein regelmaessiges Raster.

    Notwendig, weil die Fitbit-Erfassung Buendel von Abtastwerten im
    Abstand von 1-2 ms liefert, gefolgt von Luecken bis 93 ms. Die
    effektive Rate schwankt je nach Datei zwischen etwa 40 und 50 Hz.
    Eine Behandlung der Zeilen als gleichmaessig abgetastet wuerde die
    Zeitstruktur des Aufpralls verfaelschen.
    """
    keep = np.concatenate([[True], np.diff(t) > 0])
    t, xyz = t[keep], xyz[keep]
    if len(t) < 10 or t[-1] <= t[0]:
        return None
    n = int(np.floor((t[-1] - t[0]) * fs)) + 1
    grid = t[0] + np.arange(n) / fs
    out = np.empty((n, xyz.shape[1]), dtype=np.float32)
    for c in range(xyz.shape[1]):
        out[:, c] = np.interp(grid, t, xyz[:, c])
    return out


def find_weda_trials(root, fs_dir="50Hz"):
    """Sucht alle Trials. Verzeichnis = Bewegungscode,
    Dateiname = U<id>_R<trial>_<typ>.csv"""
    root = Path(root)
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
            seen.setdefault((m.group(1), int(m.group(2))),
                            {})[m.group(3).lower()] = f
        for (user, trial), files in sorted(seen.items()):
            if "accel" not in files or "gyro" not in files:
                continue
            out.append({
                "movement": code,
                "label": 1 if code.startswith("F") else 0,
                "user": user, "trial": trial,
                "accel": files["accel"], "gyro": files["gyro"],
                "group": ("elderly" if user in WEDA_ELDERLY
                          else "young" if user in WEDA_YOUNG else "other"),
            })
    return out


def load_weda(root, group=None, fs_dir="50Hz", verbose=True):
    """WEDA-FALL.

    group: None (alle), 'young' oder 'elderly'.

    Hinweis: Die aelteren Probanden (U21-U31) haben aus
    Sicherheitsgruenden KEINE Stuerze ausgefuehrt. Fuer diese Gruppe
    ist ausschliesslich die Fehlalarmrate bewertbar.
    """
    entries = find_weda_trials(root, fs_dir)
    if group is not None:
        entries = [e for e in entries if e["group"] == group]

    trials = []
    for e in entries:
        a = _read_weda_csv(e["accel"])
        g = _read_weda_csv(e["gyro"])
        if a is None or g is None:
            continue
        acc = _weda_to_grid(*a)
        gyr = _weda_to_grid(*g)
        if acc is None or gyr is None:
            continue
        n = min(len(acc), len(gyr))
        if n < WEDA_FS:
            continue
        data = np.hstack([acc[:n], gyr[:n]])
        # Einheiten an SisFall angleichen
        data[:, :3] /= G_MS2            # m/s^2 -> g
        data[:, 3:] *= RAD_TO_DEG       # rad/s -> deg/s
        trials.append({
            "data": downsample(data, WEDA_FS, FS_TARGET),
            "label": e["label"],
            "subject": e["user"],
            "activity": e["movement"],
            "impact_idx": None,
        })

    if verbose:
        n_f = sum(t["label"] for t in trials)
        subs = sorted({t["subject"] for t in trials})
        print(f"[WEDA {group or 'alle'}] {len(trials)} Trials "
              f"({n_f} Sturz, {len(trials)-n_f} ADL), "
              f"{len(subs)} Probanden")
    return trials



# ---------------------------------------------------------------------
#  CAPPIMU  (9 Positionen gleichzeitig, 50 Hz, BWT901CL, +-16 g)
# ---------------------------------------------------------------------
# Jede Position liegt als eigene CSV je Proband vor:
#   data/subject_<n>/<position>.csv
#   Spalten: time[ms], ax, ay, az [g], wx, wy, wz [deg/s], ex.., label
# Besonderheiten:
#   * Zeitstempel teils doppelt und mit Luecken zwischen den
#     Aktivitaetsbloecken -> Duplikate entfernen, je Block auf ein
#     gleichmaessiges 50-Hz-Raster interpolieren.
#   * Die Klasse 'fall' beschriftet die GESAMTE Sturzsitzung (~160 s,
#     mehrere Stuerze inkl. Aufstehen). Einzelne Aufpraelle werden
#     daher auf einer Referenzposition am Rumpf detektiert und ueber
#     die gemeinsamen Zeitstempel auf die Zielposition uebertragen.
#     Diese Beschriftung ist eine Naeherung und im Bericht so zu nennen.
CAPPIMU_FS = 50
CAPPIMU_POSITIONS = ("head", "chest", "arm_l", "arm_r", "wrist_l",
                     "wrist_r", "pocket", "knee_l", "knee_r")
CAPPIMU_FALL_LABEL = "fall"
_CAPPIMU_IMPACTS = {}      # Aufprallzeiten je Referenzdatei


def _read_cappimu_imu(path):
    import pandas as pd
    d = pd.read_csv(path, usecols=["time", "ax", "ay", "az",
                                   "wx", "wy", "wz", "label"])
    d = d.drop_duplicates("time").sort_values("time")
    d = d.dropna(subset=["ax", "ay", "az", "wx", "wy", "wz"])
    return (d["time"].to_numpy(np.float64),
            d[["ax", "ay", "az", "wx", "wy", "wz"]].to_numpy(np.float64),
            d["label"].astype(str).to_numpy())


def _cappimu_blocks(t, X, lab, fs=CAPPIMU_FS, max_gap_s=1.0):
    """Zerlegt in zusammenhaengende Bloecke gleicher Klasse und
    interpoliert jeden Block auf ein gleichmaessiges Raster.
    Liefert (zeitraster_ms, daten (N,6), label)."""
    if len(t) < 2:
        return []
    brk = np.where((np.diff(t) > max_gap_s * 1000) |
                   (lab[1:] != lab[:-1]))[0] + 1
    out = []
    for s, e in zip(np.r_[0, brk], np.r_[brk, len(t)]):
        if e - s < fs:                      # < 1 s -> verwerfen
            continue
        tt = t[s:e]
        grid = np.arange(tt[0], tt[-1], 1000.0 / fs)
        seg = np.column_stack([np.interp(grid, tt, X[s:e, k])
                               for k in range(6)])
        out.append((grid, seg.astype(np.float32), lab[s]))
    return out


def _cappimu_impact_times(blocks, min_g=2.5, min_dist_s=4.0,
                          fs=CAPPIMU_FS):
    """Aufprallzeitpunkte (ms) in den Sturzbloecken der Referenz."""
    from scipy.signal import find_peaks
    times = []
    for grid, seg, lab in blocks:
        if lab != CAPPIMU_FALL_LABEL:
            continue
        p, _ = find_peaks(acc_magnitude(seg), height=min_g,
                          distance=int(min_dist_s * fs))
        times.extend(grid[p].tolist())
    return times


def load_cappimu(root, position="knee_r", ref_position="chest",
                 context_s=5.0, min_g=2.5, min_dist_s=4.0,
                 subjects=None, verbose=True):
    """CAPPIMU fuer eine Sensorposition.

    root: Ordner, der subject_1 ... subject_30 enthaelt (".../data").
    position: Zielposition (siehe CAPPIMU_POSITIONS).
    ref_position: Rumpfposition zur Detektion der Aufpraelle.
    context_s: Laenge je Sturz-Trial vor und nach dem Aufprall.

    ADL: jeder Aktivitaetsblock ist ein Trial (Label 0).
    Stuerze: je erkanntem Aufprall ein Trial von 2*context_s Sekunden
    (Label 1, impact_idx gesetzt). Der Rest der Sturzsitzung
    (Aufstehen, Gehen zur Matte) wird verworfen, damit er weder als
    Sturz noch als ADL Label-Rauschen erzeugt.
    """
    position = position.lower()
    root = Path(root)
    subj_dirs = sorted((d for d in root.iterdir()
                        if d.is_dir() and d.name.startswith("subject_")),
                       key=lambda d: int(d.name.split("_")[1]))
    if subjects is not None:
        subj_dirs = [d for d in subj_dirs
                     if int(d.name.split("_")[1]) in set(subjects)]
    trials, n_imp = [], {}
    ctx = int(context_s * CAPPIMU_FS)
    half = int(0.5 * CAPPIMU_FS)

    for sd in subj_dirs:
        f = sd / f"{position}.csv"
        if not f.exists():
            continue
        sid = f"CAP{int(sd.name.split('_')[1]):02d}"
        blocks = _cappimu_blocks(*_read_cappimu_imu(f))

        rf = sd / f"{ref_position.lower()}.csv"
        key = (str(rf), min_g, min_dist_s)
        if key not in _CAPPIMU_IMPACTS:      # Referenz nur einmal lesen
            ref_blocks = (blocks if ref_position.lower() == position
                          else _cappimu_blocks(*_read_cappimu_imu(rf))
                          if rf.exists() else blocks)
            _CAPPIMU_IMPACTS[key] = _cappimu_impact_times(
                ref_blocks, min_g, min_dist_s)
        impacts = _CAPPIMU_IMPACTS[key]
        n_imp[sid] = len(impacts)

        for grid, seg, lab in blocks:
            if lab != CAPPIMU_FALL_LABEL:
                trials.append({"data": seg, "label": 0, "subject": sid,
                               "activity": lab, "impact_idx": None})
                continue
            mag = acc_magnitude(seg)
            for ti in impacts:
                if not (grid[0] <= ti <= grid[-1]):
                    continue
                c = int(np.argmin(np.abs(grid - ti)))
                lo, hi = max(0, c - half), min(len(seg), c + half + 1)
                c = lo + int(np.argmax(mag[lo:hi]))   # lokal verfeinern
                s, e = max(0, c - ctx), min(len(seg), c + ctx)
                if e - s < WIN_LEN:
                    continue
                trials.append({"data": seg[s:e], "label": 1,
                               "subject": sid, "activity": "fall",
                               "impact_idx": c - s})
    if verbose:
        n_f = sum(t["label"] for t in trials)
        cnt = list(n_imp.values())
        print(f"[CAPPIMU {position}] {len(trials)} Trials ({n_f} Sturz, "
              f"{len(trials)-n_f} ADL), {len(n_imp)} Probanden, "
              f"Aufpraelle je Proband: min {min(cnt) if cnt else 0}, "
              f"median {int(np.median(cnt)) if cnt else 0}, "
              f"max {max(cnt) if cnt else 0}")
    return trials


# ---------------------------------------------------------------------
#  Moticon OpenGo (Smart-Insole v1.0, ImbalanSense)
#  100 Hz, IMU in jeder Sohle: Acc [g], Gyro [deg/s]
# ---------------------------------------------------------------------
# Jede Sohle wird als eigener Trial behandelt (gleicher Proband).
# Beide Datensaetze enthalten KEINE Stuerze; sie dienen als
# fussnahe ADL- bzw. Negativdaten.
MOTICON_FS = 100
_MOTICON_COLS = {
    "left":  ["left acceleration X[g]", "left acceleration Y[g]",
              "left acceleration Z[g]", "left angular X[dps]",
              "left angular Y[dps]", "left angular Z[dps]"],
    "right": ["right acceleration X[g]", "right acceleration Y[g]",
              "right acceleration Z[g]", "right angular X[dps]",
              "right angular Y[dps]", "right angular Z[dps]"],
}


def _moticon_foot(df, foot):
    import pandas as pd
    """Extrahiert (N,6) einer Sohle; Luecken linear interpolieren."""
    cols = _MOTICON_COLS[foot]
    if not all(c in df.columns for c in cols):
        return None
    x = np.array(df[cols].apply(pd.to_numeric, errors="coerce"), dtype=np.float64)
    ok = ~np.isnan(x).any(axis=1)
    if ok.sum() < MOTICON_FS:
        return None
    i0, i1 = np.argmax(ok), len(ok) - np.argmax(ok[::-1])
    x = x[i0:i1]
    idx = np.arange(len(x))
    for k in range(6):
        m = np.isnan(x[:, k])
        if m.any():
            x[m, k] = np.interp(idx[m], idx[~m], x[~m, k])
    return downsample(x, MOTICON_FS, FS_TARGET).astype(np.float32)


def _read_moticon_txt(path):
    """Moticon-Export (.txt): Metadatenkopf mit '#', dann TSV."""
    import pandas as pd
    hdr, skip = None, 0
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            if line.startswith("# time"):
                hdr = line[2:].rstrip("\r\n").split("\t")
                skip = i + 1
                break
            if not line.startswith("#"):
                break
    if hdr is None:
        return None
    return pd.read_csv(path, sep="\t", skiprows=skip, header=None,
                       names=hdr, usecols=range(len(hdr)),
                       encoding="utf-8", encoding_errors="ignore",
                       on_bad_lines="skip", low_memory=False)


IMBALANSENSE_NOTED = {2, 3, 5, 23, 40}   # Hinweise im README


def load_imbalansense(root, feet=("left", "right"), exclude_noted=False,
                      verbose=True):
    """ImbalanSense (Zenodo 10.5281/zenodo.20924766, CC-BY 4.0).

    root: Ordner mit den .txt-Dateien von raw_recordings.zip
          (wird rekursiv durchsucht).
    Dateiname: user31-medium2-shaking.txt bzw. u16-heavy1-norm.txt
    activity: '<bedingung>_<intensitaet>', z.B. 'shaking_heavy'.
    """
    trials = []
    for f in sorted(Path(root).rglob("*.txt")):
        m = re.match(r"(?:u|user)(\d+)-([a-z]+)(\d)-([a-z]+)",
                     f.stem, re.IGNORECASE)
        if not m:
            continue
        uid = int(m.group(1))
        if exclude_noted and uid in IMBALANSENSE_NOTED:
            continue
        df = _read_moticon_txt(f)
        if df is None:
            continue
        for foot in feet:
            x = _moticon_foot(df, foot)
            if x is None or len(x) < WIN_LEN:
                continue
            trials.append({
                "data": x, "label": 0, "subject": f"IMB{uid:02d}",
                "activity": f"{m.group(4).lower()}_{m.group(2).lower()}",
                "impact_idx": None, "foot": foot,
            })
    if verbose:
        print(f"[ImbalanSense] {len(trials)} Trials (alle ADL), "
              f"{len({t['subject'] for t in trials})} Probanden, "
              f"{sum(len(t['data']) for t in trials)/FS_TARGET/3600:.2f} h")
    return trials


def load_smart_insole(root, feet=("left", "right"), verbose=True):
    """Smart-Insole Dataset v1.0 (HMU BMI Lab), Annotated_Data/*.xlsx.

    Nutzungsvereinbarung: nur nicht-kommerziell (Forschung/Lehre).
    root: Ordner 'Annotated_Data' (enthaelt EL/, PD/, S/).
    activity: Testcode, z.B. '1norm', '2tug'; zusaetzlich 'group'.
    """
    import pandas as pd
    trials = []
    for f in sorted(Path(root).rglob("*.xlsx")):
        m = re.match(r"([a-z]+)(\d+)[_-](\d[a-z]+)\d*$", f.stem,
                     re.IGNORECASE)
        if not m:
            continue
        try:
            df = pd.read_excel(f)
        except Exception:
            continue
        if len(df) < MOTICON_FS:
            continue
        grp = m.group(1).upper()
        for foot in feet:
            x = _moticon_foot(df, foot)
            if x is None or len(x) < WIN_LEN:
                continue
            trials.append({
                "data": x, "label": 0,
                "subject": f"SI_{grp}{int(m.group(2)):03d}",
                "activity": m.group(3).lower(), "impact_idx": None,
                "group": grp, "foot": foot,
            })
    if verbose:
        for g_ in ("S", "EL", "PD"):
            sub = [t for t in trials if t["group"] == g_]
            print(f"[Smart-Insole {g_:>2}] {len(sub)} Trials, "
                  f"{len({t['subject'] for t in sub})} Probanden, "
                  f"{sum(len(t['data']) for t in sub)/FS_TARGET/60:.1f} min")
    return trials


# ---------------------------------------------------------------------
#  Pilotdaten der Zielhardware (DatenLogger, ESP32-C6 + MPU-6500)
# ---------------------------------------------------------------------
# Ordnerstruktur: <root>/<Position>/<nr>_<POS>_<aktivitaet>.csv
#   Kopfzeile:  # position=... activity=... fs=100 ...
#   Daten:      t_ms,ax,ay,az,gx,gy,gz  (LSB, +-16 g, +-2000 deg/s)
# Der Unterordner bestimmt die Position (Right_Ankle und Left_Ankle
# tragen beide position=ANKLE in der Kopfzeile).
PILOT_FS = 100
PILOT_ACC_LSB = 1.0 / 2048.0
PILOT_GYR_LSB = 1.0 / 16.384


def _read_pilot_csv(path):
    rows = []
    for zeile in Path(path).read_text(errors="ignore").splitlines():
        teile = zeile.strip().split(",")
        if not zeile or not zeile[0].isdigit() or len(teile) != 7:
            continue                      # Kopf, abgeschnittene Zeilen
        try:
            rows.append([float(v) for v in teile])
        except ValueError:
            continue
    if len(rows) < PILOT_FS:
        return None
    a = np.asarray(rows)
    t, idx = np.unique(a[:, 0], return_index=True)
    a = a[idx]
    # Flash-Schreibzugriffe verzoegern einzelne Abtastungen: auf ein
    # exaktes 100-Hz-Raster interpolieren, dann wie im Training
    # heruntertasten.
    raster = np.arange(t[0], t[-1], 1000.0 / PILOT_FS)
    d = np.column_stack([np.interp(raster, t, a[:, k]) for k in range(1, 7)])
    d[:, :3] *= PILOT_ACC_LSB
    d[:, 3:] *= PILOT_GYR_LSB
    return downsample(d, PILOT_FS, FS_TARGET).astype(np.float32)


def pilot_impacts(data, min_rest_s=2.0, gyr_max=30.0, angle_min=40.0,
                  lead_s=2.0):
    """Aufprallindizes einer Sturzaufnahme ueber die Liegephase.

    Ruhephasen (|Gyro| < gyr_max, |a| ~ 1 g, >= min_rest_s), deren
    Schwerkraftrichtung um mehr als angle_min von der Stehhaltung zu
    Beginn abweicht, gelten als Liegen nach einem Sturz. Der Aufprall
    ist das Maximum von |a| in den lead_s Sekunden davor. Robuster als
    eine Spitzenschwelle, da am Knoechel Klopfmarken und Aufstehen
    oft staerker sind als der Sturz selbst.
    """
    fs = FS_TARGET
    a = data[:, :3]
    m = np.linalg.norm(a, axis=1)
    gy = np.linalg.norm(data[:, 3:6], axis=1)
    ker = np.ones(fs // 2) / (fs // 2)
    still = ((np.convolve(gy, ker, "same") < gyr_max) &
             (np.convolve(np.abs(m - 1), ker, "same") < 0.15))
    if not still.any():
        return []
    i0 = int(np.argmax(still))
    ref = a[i0:i0 + fs].mean(axis=0)
    ref /= np.linalg.norm(ref)
    out, start = [], None
    for i, v in enumerate(np.r_[still, False]):
        if v and start is None:
            start = i
        if not v and start is not None:
            if i - start >= min_rest_s * fs:
                g = a[start:i].mean(axis=0)
                g /= np.linalg.norm(g)
                if np.degrees(np.arccos(np.clip(g @ ref, -1, 1))) >= angle_min:
                    lo = max(0, start - int(lead_s * fs))
                    out.append(lo + int(np.argmax(m[lo:start + int(0.3 * fs)])))
            start = None
    return out


def load_pilot(root, context_s=5.0, verbose=True):
    """Pilotaufnahmen. ADL-Dateien sind je ein Trial; Sturzdateien
    liefern je Aufprall einen Trial von +-context_s (impact_idx
    gesetzt). 'subject' ist die Position, damit Gruppierungen je
    Position moeglich sind."""
    root = Path(root)
    trials = []
    for f in sorted(root.rglob("*.csv")):
        pos = (f.parent.name.upper() if f.parent != root
               else (re.match(r"\d+_([A-Z_]+?)_[a-z]", f.name) or [None, "UNK"])[1])
        act = re.sub(r"^\d+_[A-Z_]+?_(?=[a-z])", "", f.stem)
        x = _read_pilot_csv(f)
        if x is None or len(x) < WIN_LEN:
            continue
        base = {"subject": pos, "position": pos, "activity": act,
                "datei": f.name}
        if not act.startswith("fall"):
            trials.append({**base, "data": x, "label": 0, "impact_idx": None})
            continue
        ctx = int(context_s * FS_TARGET)
        for c in pilot_impacts(x):
            s, e = max(0, c - ctx), min(len(x), c + ctx)
            if e - s >= WIN_LEN:
                trials.append({**base, "data": x[s:e], "label": 1,
                               "impact_idx": c - s})
    if verbose:
        for p in sorted({t["position"] for t in trials}):
            sub = [t for t in trials if t["position"] == p]
            n_f = sum(t["label"] for t in sub)
            print(f"[Pilot {p}] {n_f} Stuerze, "
                  f"{sum(len(t['data']) for t in sub if not t['label'])/FS_TARGET/60:.1f} min ADL")
    return trials


# ---------------------------------------------------------------------
#  Orientierung: Rotation, Spiegelung, Augmentierung
# ---------------------------------------------------------------------
def rotate_windows(X, R, mirror_axis=None):
    """Dreht Fenster (N,T,6) mit der Matrix R (3x3), optional mit
    Spiegelung an der Ebene senkrecht zu mirror_axis. Die
    Winkelgeschwindigkeit ist ein Pseudovektor: bei einer Spiegelung
    wechseln die beiden anderen Gyro-Achsen das Vorzeichen."""
    A = X[..., :3] @ R.T
    G = X[..., 3:6] @ R.T
    if mirror_axis is not None:
        A = A.copy(); G = G.copy()
        A[..., mirror_axis] *= -1
        G[..., [k for k in range(3) if k != mirror_axis]] *= -1
    return np.concatenate([A, G], axis=-1).astype(np.float32)


def random_rotation_matrices(n, seed=0):
    from scipy.spatial.transform import Rotation
    return Rotation.random(n, random_state=seed).as_matrix()


def rotation_between(a, b):
    """Kleinste Drehung (3x3), die Richtung a auf Richtung b abbildet
    (Rodrigues). Die Drehung um b selbst bleibt unbestimmt -- sie ist
    aus der Schwerkraft allein nicht ableitbar."""
    a = np.asarray(a, float) / np.linalg.norm(a)
    b = np.asarray(b, float) / np.linalg.norm(b)
    v, c = np.cross(a, b), float(a @ b)
    if c < -0.9999:                         # entgegengesetzt: 180 Grad
        o = np.eye(3)[np.argmin(np.abs(a))]
        v = np.cross(a, o); v /= np.linalg.norm(v)
        return 2 * np.outer(v, v) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def mean_gravity(trials, gyr_max=20.0, max_trials=500):
    """Mittlere Schwerkraftrichtung in Ruhe (|Gyro| < gyr_max) ueber
    ADL-Trials. Dient zum Vergleich der Einbaulage zweier Datensaetze."""
    acc = []
    for t in [t for t in trials if not t["label"]][:max_trials]:
        d = t["data"]
        ruhe = np.linalg.norm(d[:, 3:6], axis=1) < gyr_max
        if ruhe.sum() > FS_TARGET:
            acc.append(d[ruhe, :3].mean(axis=0))
    g = np.mean(acc, axis=0)
    return g / np.linalg.norm(g)


def augment_orientation(X, y, copies=1, mirror_p=0.5, seed=0):
    """Haengt je Fenster `copies` zufaellig gedrehte (und mit
    Wahrscheinlichkeit mirror_p gespiegelte) Kopien an. X muss
    UNNORMIERT sein (g, deg/s); die Normalisierung folgt danach."""
    rng = np.random.default_rng(seed)
    Xs, ys = [X], [y]
    for c in range(copies):
        Rm = random_rotation_matrices(len(X), seed + 1000 * (c + 1))
        A = np.einsum("nij,ntj->nti", Rm, X[..., :3])
        G = np.einsum("nij,ntj->nti", Rm, X[..., 3:6])
        spiegel = rng.random(len(X)) < mirror_p
        ax = rng.integers(0, 3, len(X))
        for k in range(3):
            sel = spiegel & (ax == k)
            A[sel, :, k] *= -1
            for j in range(3):
                if j != k:
                    G[sel, :, j] *= -1
        Xs.append(np.concatenate([A, G], axis=-1).astype(np.float32))
        ys.append(y)
    return np.concatenate(Xs), np.concatenate(ys)


# =====================================================================
#  4. MODELL UND AUSWERTUNG
# =====================================================================
def build_cnn(win_len=WIN_LEN, n_channels=6, dropout=0.3, lr=1e-3):
    """1D-CNN. Die Kanalzahl ist parametrierbar, damit die
    Achsen-Ablation dieselbe Architektur verwenden kann."""
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


def class_weights(y):
    """Klassengewichte zum Ausgleich des Ungleichgewichts.

    Gibt stets ein verwendbares Dict zurueck. Enthaelt die Auswahl nur
    eine Klasse, werden neutrale Gewichte geliefert, damit nachgelagerte
    Zugriffe wie cw[1] nicht fehlschlagen.
    """
    y = np.asarray(y)
    n_pos, n_neg = int(y.sum()), int(len(y) - y.sum())
    if n_pos == 0 or n_neg == 0:
        return {0: 1.0, 1: 1.0}
    return {0: len(y) / (2 * n_neg), 1: len(y) / (2 * n_pos)}


def train(model, X, y, epochs=30, batch_size=64, patience=7,
          sample_weight=None, verbose=0):
    from tensorflow import keras
    model.fit(X, y, epochs=epochs, batch_size=batch_size,
              class_weight=None if sample_weight is not None
                           else class_weights(y),
              sample_weight=sample_weight,
              validation_split=0.15, verbose=verbose,
              callbacks=[
                  keras.callbacks.EarlyStopping(
                      monitor="val_loss", patience=patience,
                      restore_best_weights=True),
                  keras.callbacks.ReduceLROnPlateau(
                      monitor="val_loss", factor=0.5,
                      patience=max(2, patience // 2))])
    return model


def finetune(base, X, y, epochs=60, lr=1e-4, freeze=3,
             sample_weight=None, verbose=0):
    """Klont das Modell und trainiert die oberen Schichten nach."""
    from tensorflow import keras
    m = keras.models.clone_model(base)
    m.set_weights(base.get_weights())
    for i, layer in enumerate(m.layers):
        layer.trainable = (i >= freeze)
    m.compile(optimizer=keras.optimizers.Adam(learning_rate=lr),
              loss="binary_crossentropy", metrics=["accuracy"])
    return train(m, X, y, epochs=epochs, batch_size=32, patience=10,
                 sample_weight=sample_weight, verbose=verbose)


def evaluate(model, X, y, label="", threshold=0.5):
    from sklearn.metrics import confusion_matrix
    p = (model.predict(X, batch_size=256, verbose=0).flatten()
         > threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[0, 1]).ravel()
    se = tp / (tp + fn) if (tp + fn) else 0.0
    sp = tn / (tn + fp) if (tn + fp) else 0.0
    ac = (tp + tn) / len(y) if len(y) else 0.0
    if label:
        print(f"  {label:26s}  Se={se:.3f}  Sp={sp:.3f}  Acc={ac:.3f}  "
              f"FP={fp:>5d}  FN={fn:>4d}")
    return {"Se": round(se, 4), "Sp": round(sp, 4), "Acc": round(ac, 4),
            "FP": int(fp), "FN": int(fn), "TP": int(tp), "TN": int(tn)}


def subject_split(groups, y=None, test_size=0.25, seed=42):
    """Subjektunabhaengige Aufteilung. Rueckgabe: (train_idx, test_idx)"""
    from sklearn.model_selection import GroupShuffleSplit
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size,
                            random_state=seed)
    dummy = np.zeros(len(groups))
    return next(gss.split(dummy, y if y is not None else dummy, groups))


# =====================================================================
#  4c. KREUZVALIDIERUNG UND KONFIDENZINTERVALLE
# =====================================================================
# Eine einzelne Aufteilung liefert bei seltenen Stuerzen sehr wenige
# Testfaelle. Bei UMAFall am Knoechel etwa entfallen auf den Testsatz
# nur rund 36 Sturzfenster; ein Unterschied von zwei richtig erkannten
# Fenstern erscheint dann bereits als mehrere Prozentpunkte. Fuer
# belastbare Aussagen wird ueber alle Probanden kreuzvalidiert und das
# Ergebnis mit einem Konfidenzintervall versehen.
# =====================================================================

def group_kfold_splits(groups, y=None, n_splits=5, seed=42):
    """Subjektunabhaengige Kreuzvalidierung.

    Verwendet StratifiedGroupKFold, sofern verfuegbar: Damit bleibt
    zusaetzlich zur Probandentrennung das Klassenverhaeltnis in jeder
    Falte erhalten -- bei stark unausgewogenen Sturzdaten wesentlich,
    da einzelne Falten sonst gar keine Stuerze enthalten koennen.
    """
    try:
        from sklearn.model_selection import StratifiedGroupKFold
        if y is not None:
            cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True,
                                      random_state=seed)
            return list(cv.split(np.zeros(len(groups)), y, groups))
    except ImportError:
        pass
    from sklearn.model_selection import GroupKFold
    cv = GroupKFold(n_splits=n_splits)
    return list(cv.split(np.zeros(len(groups)),
                         y if y is not None else None, groups))


def wilson_ci(k, n, z=1.96):
    """Wilson-Konfidenzintervall fuer einen Anteil.

    Dem einfachen Normalapproximationsintervall vorzuziehen, da es
    auch bei kleinen Stichproben und Anteilen nahe 0 oder 1 gueltig
    bleibt.
    """
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    zentrum = (p + z * z / (2 * n)) / d
    breite = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(round(max(0.0, zentrum - breite), 4)),
            float(round(min(1.0, zentrum + breite), 4)))


def pool_folds(fold_results):
    """Fasst Faltenergebnisse zusammen.

    Aggregiert wird ueber die aufsummierten Konfusionsmatrizen, nicht
    ueber die Mittelwerte der Kennzahlen: Falten unterschiedlicher
    Groesse wuerden sonst gleich stark gewichtet. Zusaetzlich werden
    Mittelwert und Streuung ueber die Falten ausgewiesen.
    """
    tp = sum(r["TP"] for r in fold_results)
    tn = sum(r["TN"] for r in fold_results)
    fp = sum(r["FP"] for r in fold_results)
    fn = sum(r["FN"] for r in fold_results)

    se = tp / (tp + fn) if (tp + fn) else 0.0
    sp = tn / (tn + fp) if (tn + fp) else 0.0
    ac = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0

    se_folds = [r["Se"] for r in fold_results]
    sp_folds = [r["Sp"] for r in fold_results]

    return {
        "Se": round(se, 4), "Sp": round(sp, 4), "Acc": round(ac, 4),
        "Se_ci95": wilson_ci(tp, tp + fn),
        "Sp_ci95": wilson_ci(tn, tn + fp),
        "Se_mean_folds": round(float(np.mean(se_folds)), 4),
        "Se_std_folds": round(float(np.std(se_folds, ddof=1)), 4)
                        if len(se_folds) > 1 else 0.0,
        "Sp_mean_folds": round(float(np.mean(sp_folds)), 4),
        "TP": tp, "TN": tn, "FP": fp, "FN": fn,
        "n_folds": len(fold_results),
        "Se_per_fold": [round(v, 4) for v in se_folds],
    }


def paired_comparison(a_folds, b_folds, name_a="A", name_b="B",
                      metric="Se", verbose=True):
    """Gepaarter Vergleich zweier Verfahren ueber dieselben Falten.

    Da beide Verfahren auf identischen Falten bewertet werden, ist die
    gepaarte Betrachtung der Differenzen aussagekraeftiger als ein
    Vergleich der Mittelwerte: Schwankungen zwischen den Falten
    heben sich heraus.
    """
    a = np.array([r[metric] for r in a_folds], dtype=float)
    b = np.array([r[metric] for r in b_folds], dtype=float)
    d = b - a
    n = len(d)
    mittel = float(d.mean())
    streuung = float(d.std(ddof=1)) if n > 1 else 0.0
    se_mittel = streuung / np.sqrt(n) if n > 1 else 0.0
    ci = (round(mittel - 1.96 * se_mittel, 4),
          round(mittel + 1.96 * se_mittel, 4)) if n > 1 else (0.0, 0.0)
    gewinne = int((d > 0).sum())

    if verbose:
        print(f"  Gepaarter Vergleich ({metric}): "
              f"{name_b} minus {name_a}")
        print(f"    je Falte: {[float(round(v, 3)) for v in d]}")
        print(f"    Mittelwert: {mittel*100:+.1f} pp  "
              f"(95 %-KI [{ci[0]*100:+.1f}, {ci[1]*100:+.1f}] pp)")
        print(f"    {name_b} besser in {gewinne} von {n} Falten")
        if ci[0] > 0:
            print(f"    -> Vorteil fuer {name_b} statistisch gesichert.")
        elif ci[1] < 0:
            print(f"    -> Vorteil fuer {name_a} statistisch gesichert.")
        else:
            print(f"    -> Kein gesicherter Unterschied "
                  f"(Intervall schliesst null ein).")

    return {"metric": metric, "name_a": name_a, "name_b": name_b,
            "per_fold_delta": [round(float(v), 4) for v in d],
            "mean_delta": round(mittel, 4),
            "std_delta": round(streuung, 4),
            "ci95_delta": ci, "wins": gewinne, "n_folds": n,
            "significant": bool(ci[0] > 0 or ci[1] < 0)}


def print_pooled(name, p):
    """Einzeilige Ausgabe eines zusammengefassten Ergebnisses."""
    print(f"  {name:<22} Se={p['Se']:.3f} "
          f"[{p['Se_ci95'][0]:.3f}, {p['Se_ci95'][1]:.3f}]  "
          f"Sp={p['Sp']:.3f}  "
          f"(TP={p['TP']}, FN={p['FN']}, FP={p['FP']})")


def select_channels(X, mode):
    """'acc6' (alle), 'acc3' (Beschleunigung), 'gyr3' (Drehrate)"""
    return {"acc6": X, "acc3": X[:, :, 0:3],
            "gyr3": X[:, :, 3:6]}[mode]


# =====================================================================
#  4b. KLASSISCHE VERFAHREN (Schwellwert und Random Forest)
# =====================================================================
# Beide Verfahren arbeiten auf den ROHEN Fenstern in physikalischen
# Einheiten [g, deg/s], NICHT auf z-normalisierten Daten. Die
# Z-Normalisierung entfernt gerade jene absoluten Amplituden, auf
# denen ein Schwellwertverfahren beruht.
# =====================================================================

def threshold_predict(X_raw, acc_threshold=2.0, gyr_threshold=None):
    """Schwellwertverfahren nach Bourke.

    Ein Fenster gilt als Sturz, wenn der Betrag der Beschleunigung
    den Schwellwert ueberschreitet. Optional kann zusaetzlich eine
    Drehratenschwelle gefordert werden (UND-Verknuepfung).

    X_raw: (N, WIN_LEN, 6) in [g, deg/s] -- NICHT normalisiert.
    """
    acc_peak = acc_magnitude(X_raw).max(axis=1)
    pred = acc_peak > acc_threshold
    if gyr_threshold is not None:
        gyr_peak = np.sqrt(np.sum(X_raw[:, :, 3:6] ** 2,
                                  axis=2)).max(axis=1)
        pred = pred & (gyr_peak > gyr_threshold)
    return pred.astype(int)


def threshold_sweep(X_raw, y, thresholds=None, verbose=True):
    """Sucht den Schwellwert mit der besten Trennleistung.

    Rueckgabe: (bester_schwellwert, tabelle)
    """
    from sklearn.metrics import confusion_matrix
    if thresholds is None:
        thresholds = np.arange(1.4, 4.05, 0.1)

    tabelle, best, best_score = [], None, -1.0
    if verbose:
        print(f"  {'Schwelle':>9} {'Se':>7} {'Sp':>7} {'Acc':>7}")
        print("  " + "-"*34)
    for t in thresholds:
        p = threshold_predict(X_raw, acc_threshold=t)
        tn, fp, fn, tp = confusion_matrix(y, p, labels=[0, 1]).ravel()
        se = tp / (tp + fn) if (tp + fn) else 0.0
        sp = tn / (tn + fp) if (tn + fp) else 0.0
        ac = (tp + tn) / len(y)
        tabelle.append({"threshold": round(float(t), 2),
                        "Se": round(se, 4), "Sp": round(sp, 4),
                        "Acc": round(ac, 4),
                        "FP": int(fp), "FN": int(fn)})
        if verbose:
            print(f"  {t:>9.1f} {se:>7.3f} {sp:>7.3f} {ac:>7.3f}")
        # Youden-Index als Auswahlkriterium
        if se + sp - 1 > best_score:
            best_score, best = se + sp - 1, float(t)
    if verbose:
        print(f"\n  Bester Schwellwert (Youden-Index): {best:.1f} g")
    return best, tabelle


# --- Merkmale fuer den Random Forest --------------------------------
# 18 Merkmale, je neun aus Beschleunigung und Drehrate. Alle beruhen
# auf dem VEKTORBETRAG und sind damit rotationsinvariant: Die
# Ausrichtung des Sensors im Schuh beeinflusst sie nicht. Das ist fuer
# eine Einlegesohle wesentlich, da die Einbaulage nicht garantiert
# werden kann.
FEATURE_NAMES = [
    "acc_mean", "acc_std", "acc_max", "acc_min", "acc_range",
    "acc_rms", "acc_energy", "acc_skew", "acc_kurtosis",
    "gyr_mean", "gyr_std", "gyr_max", "gyr_min", "gyr_range",
    "gyr_rms", "gyr_energy", "gyr_skew", "gyr_kurtosis",
]


def extract_features(X_raw):
    """Berechnet die 18 rotationsinvarianten Merkmale.

    X_raw: (N, WIN_LEN, 6) in [g, deg/s] -- NICHT normalisiert.
    Rueckgabe: (N, 18)
    """
    from scipy.stats import skew, kurtosis

    # In doppelter Genauigkeit rechnen: Schiefe und Woelbung sind
    # dritte bzw. vierte Momente. Bei nahezu konstantem Signal -- etwa
    # ruhigem Stehen mit |a| ~ 1 g -- verstaerkt einfache Genauigkeit
    # den Rundungsfehler so stark, dass die Rotationsinvarianz
    # rechnerisch verloren geht.
    Xd = X_raw.astype(np.float64)
    acc = np.sqrt(np.sum(Xd[:, :, 0:3] ** 2, axis=2))   # (N, T)
    gyr = np.sqrt(np.sum(Xd[:, :, 3:6] ** 2, axis=2))

    def block(m):
        return np.column_stack([
            m.mean(axis=1),
            m.std(axis=1),
            m.max(axis=1),
            m.min(axis=1),
            m.max(axis=1) - m.min(axis=1),
            np.sqrt((m ** 2).mean(axis=1)),
            (m ** 2).sum(axis=1),
            skew(m, axis=1, bias=False),
            kurtosis(m, axis=1, bias=False),
        ])

    F = np.hstack([block(acc), block(gyr)]).astype(np.float32)
    return np.nan_to_num(F, nan=0.0, posinf=0.0, neginf=0.0)


def train_random_forest(F_train, y_train, n_estimators=200, seed=42):
    """Random Forest auf den extrahierten Merkmalen."""
    from sklearn.ensemble import RandomForestClassifier
    rf = RandomForestClassifier(
        n_estimators=n_estimators, class_weight="balanced",
        n_jobs=-1, random_state=seed)
    rf.fit(F_train, y_train)
    return rf


def evaluate_predictions(y_true, y_pred, label=""):
    """Wie evaluate(), jedoch fuer bereits vorliegende Vorhersagen
    (Schwellwertverfahren, Random Forest)."""
    from sklearn.metrics import confusion_matrix
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred,
                                      labels=[0, 1]).ravel()
    se = tp / (tp + fn) if (tp + fn) else 0.0
    sp = tn / (tn + fp) if (tn + fp) else 0.0
    ac = (tp + tn) / len(y_true) if len(y_true) else 0.0
    if label:
        print(f"  {label:26s}  Se={se:.3f}  Sp={sp:.3f}  Acc={ac:.3f}  "
              f"FP={fp:>5d}  FN={fn:>4d}")
    return {"Se": round(se, 4), "Sp": round(sp, 4), "Acc": round(ac, 4),
            "FP": int(fp), "FN": int(fn), "TP": int(tp), "TN": int(tn)}


def feature_importance(rf, names=None, top=None, verbose=True):
    """Merkmalswichtigkeit des Random Forest, absteigend sortiert."""
    names = names or FEATURE_NAMES
    imp = rf.feature_importances_
    order = np.argsort(imp)[::-1]
    rows = [{"rank": i + 1, "feature": names[j],
             "importance": round(float(imp[j]), 5),
             "sensor": "Gyroskop" if names[j].startswith("gyr")
                       else "Beschleunigung"}
            for i, j in enumerate(order)]
    if verbose:
        n = top or len(rows)
        print(f"  {'Rang':>4} {'Merkmal':<16} {'Wichtigkeit':>12} "
              f"{'Sensor':<16}")
        print("  " + "-"*52)
        for r in rows[:n]:
            print(f"  {r['rank']:>4} {r['feature']:<16} "
                  f"{r['importance']:>12.5f} {r['sensor']:<16}")
        n_gyr = sum(1 for r in rows[:5] if r["sensor"] == "Gyroskop")
        print(f"\n  Unter den fuenf wichtigsten Merkmalen sind "
              f"{n_gyr} gyroskopbasiert.")
    return rows


def export_tflite_int8(model, X_repr, path, n_samples=200):
    """Quantisierter int8-Export fuer die Portierung auf den ESP32.

    X_repr: repraesentative Eingabedaten (bereits normalisiert),
    aus denen der Konverter die Quantisierungsbereiche ableitet.
    """
    import tensorflow as tf

    def gen():
        for i in range(min(n_samples, len(X_repr))):
            yield [X_repr[i:i + 1].astype(np.float32)]

    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = gen
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    blob = conv.convert()
    Path(path).write_bytes(blob)
    kb = len(blob) / 1024
    print(f"  int8-TFLite: {kb:.1f} KB -> {path}")
    return kb


# =====================================================================
#  5. ZEITLICHE PLAUSIBILISIERUNG (N-VON-M-VOTING)
# =====================================================================
def n_of_m_hits(probs, threshold, n, m):
    """Indizes, an denen die N-von-M-Regel ausloest."""
    b = (np.asarray(probs) > threshold).astype(int)
    if len(b) < m:
        return []
    return [i for i in range(m - 1, len(b))
            if b[i - m + 1:i + 1].sum() >= n]


def count_alarm_events(probs, threshold, n, m):
    """Zaehlt Alarm-EREIGNISSE. Aufeinanderfolgende Ausloesungen
    gelten als ein Ereignis, wie es auch die Firmware handhaben
    wuerde."""
    hits = n_of_m_hits(probs, threshold, n, m)
    if not hits:
        return 0
    return 1 + sum(1 for a, b in zip(hits, hits[1:]) if b - a > 1)


def voting_eval(trial_probs, threshold, n, m, step_seconds):
    """Bewertet eine Voting-Regel auf Trial-Ebene.

    trial_probs: Liste von (probs, is_fall)-Tupeln.
    step_seconds: Realzeit je Fensterschritt (fuer FP/Stunde).
    """
    falls = [p for p, f in trial_probs if f]
    adls = [p for p, f in trial_probs if not f]
    detected = sum(1 for p in falls
                   if n_of_m_hits(p, threshold, n, m))
    fp = sum(count_alarm_events(p, threshold, n, m) for p in adls)
    steps = sum(len(p) for p in adls)
    hours = steps * step_seconds / 3600
    return {
        "rule": f"{n}-von-{m}", "threshold": threshold,
        "Se": round(detected / len(falls), 4) if falls else None,
        "detected": detected, "total_falls": len(falls),
        "fp_events": fp,
        "fp_per_hour": round(fp / hours, 2) if hours else None,
        "adl_hours": round(hours, 3),
    }


# =====================================================================
#  6. ERGEBNISVERWALTUNG
# =====================================================================
# Alle Experimente schreiben in denselben Ergebnisordner. Jeder Lauf
# erhaelt ein eigenes Unterverzeichnis aus Experimentname und
# Zeitstempel, sodass frueher Ergebnisse erhalten bleiben und
# Wiederholungen vergleichbar sind:
#
#   results/<experiment>_<JJJJ-MM-TT_HHMM>/
#       results.json      Kennzahlen und Konfiguration
#       notes.md          optionale Notizen
#       *.keras           gesicherte Modelle
# =====================================================================
RESULTS_ROOT = "/content/drive/MyDrive/ML_Fall_Detection/results"


def new_run(experiment, root=None):
    """Legt ein Verzeichnis fuer einen Experimentlauf an."""
    root = Path(root or RESULTS_ROOT)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    d = root / f"{experiment}_{stamp}"
    d.mkdir(parents=True, exist_ok=True)
    print(f"[Lauf] {d}")
    return d


def save_results(run_dir, results, config=None, notes=None):
    """Schreibt results.json und gibt den Pfad zurueck."""
    run_dir = Path(run_dir)
    payload = {
        "experiment": run_dir.name,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "config": config or {},
        "results": results,
    }
    p = run_dir / "results.json"
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    if notes:
        (run_dir / "notes.md").write_text(notes)
    print(f"[gesichert] {p}")
    return p


def load_run(run_dir):
    return json.loads((Path(run_dir) / "results.json").read_text())


def list_runs(experiment=None, root=None):
    """Listet vorhandene Laeufe, optional gefiltert."""
    root = Path(root or RESULTS_ROOT)
    if not root.exists():
        return []
    runs = sorted(p for p in root.iterdir()
                  if p.is_dir() and (experiment is None
                                     or p.name.startswith(experiment)))
    for r in runs:
        print(f"  {r.name}")
    return runs


def default_config():
    """Gibt die aktuelle Pipelinekonfiguration zur Dokumentation
    im Ergebnisdatensatz zurueck."""
    return {
        "fs_target": FS_TARGET, "window_sec": WIN_SEC,
        "overlap": OVERLAP, "window_len": WIN_LEN, "step": STEP,
        "kfall_fall_tasks": "T20-T34",
    }
