"""
experiments.py  --  Drei Experimente zur Quantifizierung der Domaenenluecke
==========================================================================
Beantwortet drei aufeinander aufbauende Fragen:

  EXP 1  Laengeres Fine-Tuning
         Reicht ein laengeres Training aus, um die Luecke zu schliessen?
         (FT_EPOCHS 20 -> 60, FREEZE_UPTO 6 -> 3)

  EXP 2  Kontrollexperiment WAIST vs. ANKLE
         Ist der Leistungsabfall wirklich auf die POSITION zurueckzufuehren
         oder nur auf den Datensatzwechsel? Der Taillensensor von UMAFall
         entspricht der SisFall-Position; faellt die Leistung dort NICHT ab,
         ist die Position die Ursache.

  EXP 3  Abtastraten-Kontrolle (20 Hz)
         UMAFall zeichnet mit 20 Hz auf, SisFall mit 200 Hz (auf 50 Hz
         heruntergetastet). Das Hochtasten 20 -> 50 Hz fuegt KEINE Information
         hinzu. Wird das SisFall-Modell direkt bei 20 Hz trainiert, entfaellt
         dieser Stoerfaktor und die verbleibende Differenz ist der reine
         Positionseffekt.

Aufruf:
    python experiments.py                  # alle drei
    python experiments.py --exp 1          # nur Experiment 1
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

CNN_SCRIPT   = Path("cnn_pipeline.py")
CROSS_SCRIPT = Path("cross_position.py")
RESULTS_MD   = Path("experiment_results.md")


def patch(path, pattern, replacement):
    """Ersetzt eine Konfigurationszeile in einer Skriptdatei."""
    src = path.read_text()
    new = re.sub(pattern, replacement, src, count=1)
    path.write_text(new)


def run(script):
    """Fuehrt ein Skript aus und gibt die Ausgabe zurueck (wird live gestreamt)."""
    print(f"\n>>> {script}")
    proc = subprocess.run([sys.executable, str(script)],
                          capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    print(out[-3000:])                       # letzte Zeilen anzeigen
    return out


def extract_metrics(output):
    """Liest Sensitivitaet / Spezifitaet / Accuracy aus der Skriptausgabe."""
    found = {}
    for tag, key in [("Zero-Shot", "zero"), ("Fine-Tuned", "fine")]:
        m = re.search(rf"{tag}\s*:\s*Se\s+([\d.]+)\s+Sp\s+([\d.]+)\s+Acc\s+([\d.]+)",
                      output)
        if m:
            found[key] = tuple(float(g) for g in m.groups())
    # Fallback: einzelner Testblock (z.B. reines cnn_pipeline)
    m = re.search(r"Sensitivitaet\s+([\d.]+)\s+Spezifitaet\s+([\d.]+)\s+Accuracy\s+([\d.]+)",
                  output)
    if m and "fine" not in found:
        found["single"] = tuple(float(g) for g in m.groups())
    return found


def exp1_longer_finetuning():
    print("\n" + "=" * 70)
    print("EXPERIMENT 1  --  Laengeres Fine-Tuning (60 Epochen, mehr trainierbare Schichten)")
    print("=" * 70)
    patch(CROSS_SCRIPT, r"FT_EPOCHS\s*=\s*\d+",    "FT_EPOCHS    = 60")
    patch(CROSS_SCRIPT, r"FREEZE_UPTO\s*=\s*\d+",  "FREEZE_UPTO  = 3")
    patch(CROSS_SCRIPT, r'POSITION\s*=\s*"[A-Z]+"', 'POSITION     = "ANKLE"')
    return extract_metrics(run(CROSS_SCRIPT))


def exp2_waist_control():
    print("\n" + "=" * 70)
    print("EXPERIMENT 2  --  Kontrolle: WAIST (gleiche Position wie SisFall)")
    print("=" * 70)
    patch(CROSS_SCRIPT, r'POSITION\s*=\s*"[A-Z]+"', 'POSITION     = "WAIST"')
    out = run(CROSS_SCRIPT)
    patch(CROSS_SCRIPT, r'POSITION\s*=\s*"[A-Z]+"', 'POSITION     = "ANKLE"')  # zuruecksetzen
    return extract_metrics(out)


def exp3_sampling_control():
    print("\n" + "=" * 70)
    print("EXPERIMENT 3  --  Abtastraten-Kontrolle: SisFall-Modell bei 20 Hz")
    print("=" * 70)
    print("Schritt 1: SisFall-Modell bei 20 Hz neu trainieren ...")
    patch(CNN_SCRIPT, r"FS_TARGET\s*=\s*\d+", "FS_TARGET    = 20")
    out_train = run(CNN_SCRIPT)

    print("Schritt 2: Cross-Position-Transfer bei 20 Hz (kein Hochtasten) ...")
    patch(CROSS_SCRIPT, r"FS_TARGET\s*=\s*\d+", "FS_TARGET    = 20")
    out_cross = run(CROSS_SCRIPT)

    # Ausgangszustand wiederherstellen
    patch(CNN_SCRIPT,   r"FS_TARGET\s*=\s*\d+", "FS_TARGET    = 50")
    patch(CROSS_SCRIPT, r"FS_TARGET\s*=\s*\d+", "FS_TARGET    = 50")

    res = extract_metrics(out_cross)
    res["sisfall_20hz"] = extract_metrics(out_train).get("single")
    return res


def fmt(t):
    return f"{t[0]:.3f} / {t[1]:.3f} / {t[2]:.3f}" if t else "--"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", type=int, choices=[1, 2, 3], default=None,
                    help="Nur ein einzelnes Experiment ausfuehren")
    args = ap.parse_args()

    for f in (CNN_SCRIPT, CROSS_SCRIPT):
        if not f.exists():
            raise SystemExit(f"{f} nicht gefunden.")

    results = {}
    if args.exp in (None, 1):
        results["EXP1 Ankle, 60 Epochen"] = exp1_longer_finetuning()
    if args.exp in (None, 2):
        results["EXP2 Waist (Kontrolle)"] = exp2_waist_control()
    if args.exp in (None, 3):
        results["EXP3 Ankle @ 20 Hz"]     = exp3_sampling_control()

    lines = ["# Ergebnisse der Transfer-Experimente", "",
             "Werte als Sensitivitaet / Spezifitaet / Accuracy.", "",
             "| Experiment | Zero-Shot | Fine-Tuned |",
             "|---|---|---|"]
    for name, r in results.items():
        lines.append(f"| {name} | {fmt(r.get('zero'))} | {fmt(r.get('fine'))} |")

    if "EXP3 Ankle @ 20 Hz" in results:
        s = results["EXP3 Ankle @ 20 Hz"].get("sisfall_20hz")
        if s:
            lines += ["", f"SisFall-Referenz bei 20 Hz (Huefte): {fmt(s)}"]

    text = "\n".join(lines)
    RESULTS_MD.write_text(text)
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)
    print(f"\nGespeichert unter {RESULTS_MD}")


if __name__ == "__main__":
    main()
