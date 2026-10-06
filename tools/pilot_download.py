"""
pilot_download.py  --  Aufnahmen vom DatenLogger auf den PC holen
==================================================================
Sendet "d" an das Board, liest die Ausgabe und speichert jede
Aufnahme als eigene CSV-Datei. Ersetzt das Kopieren aus dem
Serial Monitor.

Voraussetzung:  pip install pyserial
                Arduino Serial Monitor muss GESCHLOSSEN sein.

Aufruf:
    python tools/pilot_download.py                 # Port automatisch
    python tools/pilot_download.py --port COM5     # Windows
    python tools/pilot_download.py --port COM5 --loeschen
        -> nach erfolgreichem Speichern Flash leeren ("x")

Ergebnis: Ordner Pilotdaten/<Datum_Uhrzeit>/ mit einer CSV je
Aufnahme. Diesen Ordner in Google Drive nach
ML_Fall_Detection/Pilotdaten/ hochladen.
"""
import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial fehlt:  pip install pyserial")


def finde_port():
    ports = list(list_ports.comports())
    for p in ports:
        text = f"{p.description} {p.hwid}".lower()
        if any(k in text for k in ("usb jtag", "esp32", "303a", "cp210", "ch340", "usb serial")):
            return p.device
    if len(ports) == 1:
        return ports[0].device
    print("Gefundene Ports:")
    for p in ports:
        print(f"  {p.device:10s} {p.description}")
    sys.exit("Port nicht eindeutig -- bitte mit --port angeben.")


def lies_bis(ser, ende, timeout_s):
    puffer, t0 = [], time.time()
    while time.time() - t0 < timeout_s:
        zeile = ser.readline().decode("utf-8", errors="ignore")
        if not zeile:
            continue
        puffer.append(zeile)
        t0 = time.time()                 # Timeout nur bei Stillstand
        if ende in zeile:
            break
    return "".join(puffer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--ziel", default="Pilotdaten")
    ap.add_argument("--loeschen", action="store_true",
                    help="Flash nach erfolgreichem Speichern leeren")
    args = ap.parse_args()

    port = args.port or finde_port()
    print(f"Verbinde mit {port} ...")
    ser = serial.Serial(port, 115200, timeout=2)
    time.sleep(2.0)                      # Board startet ggf. neu
    ser.reset_input_buffer()

    ser.write(b"d")
    text = lies_bis(ser, "Alles ausgegeben.", timeout_s=20)
    if "Keine Aufnahmen" in text:
        sys.exit("Keine Aufnahmen auf dem Board.")

    bloecke = re.findall(r"===== DATEI: (.+?) =====\r?\n(.*?)===== ENDE",
                         text, re.S)
    if not bloecke:
        print(text[-500:])
        sys.exit("Keine Dateien in der Ausgabe gefunden.")

    ordner = Path(args.ziel) / datetime.now().strftime("%Y-%m-%d_%H%M")
    ordner.mkdir(parents=True, exist_ok=True)
    print(f"\n{'Datei':<34} {'Zeilen':>7} {'Dauer':>7}")
    for name, inhalt in bloecke:
        name = name.strip().lstrip("/")
        zeilen = [z for z in inhalt.splitlines() if z.strip()]
        daten = [z for z in zeilen if z[0].isdigit()]
        (ordner / name).write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        dauer = int(daten[-1].split(",")[0]) / 1000 if daten else 0
        warn = "  <-- sehr kurz" if dauer < 5 else ""
        print(f"{name:<34} {len(daten):>7} {dauer:>6.1f}s{warn}")

    print(f"\n{len(bloecke)} Aufnahmen gespeichert in {ordner.resolve()}")

    if args.loeschen:
        ser.write(b"x")
        print(lies_bis(ser, "geloescht", timeout_s=10).strip().splitlines()[-1])
    else:
        print("Flash NICHT geloescht (mit --loeschen beim naechsten Mal).")
    ser.close()


if __name__ == "__main__":
    main()
