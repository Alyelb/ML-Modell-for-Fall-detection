"""Praesentation 3: Anleitung -- vom fertigen Keras-Modell bis zur Erkennung in der Sohle.

Ausgangspunkt: Es gibt bereits ein trainiertes Modell (.keras). Jede Folie
ist ein Schritt, den man am Rechner direkt nachmachen kann.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from thm_deck import DUNKEL, GRAU, GRUEN, HELL, REPO, WEISS, Deck  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402

d = Deck()
T, N = d.text, d.notiz
CODE_BG = RGBColor(0x26, 0x32, 0x38)
KOMMENTAR = RGBColor(0x9C, 0xCC, 0x65)
SCHRITTE = 6


def code(slide, x, y, w, zeilen, size=13, h=None):
    """Dunkler Kasten mit Code; Text ab '  #' wird gruen gesetzt."""
    h = h or 0.22 + 0.27 * len(zeilen) * size / 13
    d.flaeche(slide, x, y, w, h, fill=CODE_BG)
    absaetze = []
    for z in zeilen:
        if "  # " in z:
            i = z.index("  # ")
            absaetze.append([(z[:i], {}), (z[i:], {"color": KOMMENTAR})])
        elif z.lstrip().startswith("# "):
            absaetze.append([(z, {"color": KOMMENTAR})])
        else:
            absaetze.append([(z, {})])
    tb = T(slide, x + 0.2, y + 0.11, w - 0.4, h - 0.15, absaetze, size=size, color=WEISS, abstand=1)
    for p in tb.text_frame.paragraphs:
        for r in p.runs:
            r.font.name = "Courier New"
    return tb


def schritt(slide, nr):
    T(slide, 10.75, 1.25, 2.0, 0.4, f"Schritt {nr} von {SCHRITTE}", size=13, color=GRAU, align=PP_ALIGN.RIGHT)


def kasten(slide, x, y, w, h, kopf, zeilen, size=15):
    d.flaeche(slide, x, y, w, h, fill=HELL)
    T(slide, x + 0.25, y + 0.18, w - 0.5, 0.4, [[(kopf, {"bold": True, "color": GRAU})]], size=size)
    T(slide, x + 0.25, y + 0.65, w - 0.5, h - 0.8, zeilen, size=size, punkte=True, abstand=6)


# 1 ------------------------------------------------------------------ Titel
s = d.titelfolie([
    ("Vom Keras-Modell zur Sturzerkennung in der Sohle", 18, True, DUNKEL),
    ("Anleitung in sechs Schritten", 12, False, GRAU),
    ("Aly Elbermawy", 12, True, DUNKEL),
    ("Studienprojekt 2 · THM Campus Friedberg", 11, False, GRAU)])
N(s, "Ausgangspunkt: Ein Modell ist schon trainiert und liegt als .keras-Datei vor. "
     "Ich zeige, wie es von dieser Datei bis auf den Chip in der Sohle kommt.")

# 2 ------------------------------------------------------------------ Ueberblick
s = d.folie("Der Weg in sechs Schritten")
d.ablauf(s, 0.47, 2.0, 12.3, [("1 Ordner", "Projekt öffnen,\nDateien ablegen"),
                              ("2 Python", "einmalig\neinrichten"),
                              ("3 Export", "ein Befehl"),
                              ("4 Arduino", "einmalig\neinrichten"),
                              ("5 Hochladen", "auf den Chip"),
                              ("6 Testen", "live mitlesen")], h=1.45, hervor=(2,), size=16)
T(s, 0.47, 3.9, 12.3, 2.8, [
    [("Ausgangspunkt: ", {"bold": True}), ("ein trainiertes Modell, z. B. ", {}),
     ("mein_modell.keras", {"bold": True}), (".", {})],
    [("Ergebnis: ", {"bold": True}), ("Die Sohle zeigt alle 0,2 s an, ob gerade ein Sturz passiert.", {})],
    [("Schritt 2 und 4 ", {"bold": True}), ("macht man nur beim ersten Mal. Für jedes neue Modell genügen danach "
                                           "Schritt 1, 3 und 5.", {})],
], size=17, punkte=True, abstand=12)
N(s, "Der wichtigste Schritt ist der Export (grün): Er macht aus der Keras-Datei die Dateien, die der Chip versteht.")

# 3 ------------------------------------------------------------------ Was man braucht
s = d.folie("Was man braucht")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Was", "Wofür"],
    ["Das Modell: mein_modell.keras", "das trainierte Netz – das soll auf den Chip"],
    ["Ordner mit Logger-Aufnahmen (CSV)", "echte Messdaten zum Umrechnen und Prüfen"],
    ["Projektordner von GitHub", "Exportskript und Firmware"],
    ["Python 3 (python.org)", "führt das Exportskript aus"],
    ["Arduino IDE 2 (arduino.cc)", "lädt die Firmware auf den Chip"],
    ["Sohle mit XIAO ESP32-C6 + USB-C-Kabel", "der Chip selbst"],
], [5.3, 7.0], size=16, h_zeile=0.6, zentriert_ab=2)
N(s, "Die Logger-Aufnahmen sind die CSV-Dateien aus dem DatenLogger, z. B. der Ordner Pilotdaten. "
     "Es reichen einige Minuten Gehen und ein paar Stürze.")

# 4 ------------------------------------------------------------------ Schritt 1
s = d.folie("Schritt 1: Projektordner öffnen und Dateien hineinlegen")
schritt(s, 1)
T(s, 0.47, 1.95, 5.9, 4.8, [
    [("Projekt holen: ", {"bold": True}), ("github.com/Alyelb/ML-Modell-for-Fall-detection → Code → Download ZIP, entpacken.", {})],
    [("Modell hineinlegen: ", {"bold": True}), ("mein_modell.keras direkt in den Projektordner kopieren.", {})],
    [("Aufnahmen hineinlegen: ", {"bold": True}), ("den Ordner mit den CSV-Dateien daneben legen, z. B. Pilotdaten.", {})],
    [("Konsole öffnen: ", {"bold": True}), ("im Projektordner in die Adresszeile des Explorers cmd tippen und Enter drücken.", {})],
], size=16, punkte=True, abstand=12)
code(s, 6.75, 1.95, 6.0, [
    "ML-Modell-for-Fall-detection/",
    "  mein_modell.keras   # hierher kopieren",
    "  Pilotdaten/         # Logger-CSV-Dateien",
    "    01_ANKLE_R_walking.csv",
    "    02_ANKLE_R_fall_forward.csv",
    "    ...",
    "  firmware/CleverSole/",
    "  tools/",
    "  requirements.txt",
], size=13)
N(s, "Wichtig ist nur, dass Modell und Aufnahmen-Ordner im Projektordner liegen und die Konsole dort geöffnet ist.")

# 5 ------------------------------------------------------------------ Schritt 2
s = d.folie("Schritt 2: Python einrichten (nur beim ersten Mal)")
schritt(s, 2)
code(s, 0.47, 1.95, 12.3, [
    "python --version                    # zeigt z. B. Python 3.11 – sonst Python installieren",
    "pip install -r requirements.txt     # installiert TensorFlow und Co.",
], size=14)
T(s, 0.47, 3.05, 12.3, 3.6, [
    "Beide Befehle in der Konsole aus Schritt 1 eingeben.",
    "Der zweite Befehl lädt TensorFlow herunter und dauert einige Minuten.",
    [("Danach nie wieder nötig ", {"bold": True}), ("– auch nicht für ein neues Modell.", {})],
], size=17, punkte=True, abstand=12)
N(s, "requirements.txt ist eine Liste der Python-Bibliotheken, die das Projekt braucht.")

# 6 ------------------------------------------------------------------ Schritt 3
s = d.folie("Schritt 3: Das Modell für den Chip umwandeln – ein Befehl")
schritt(s, 3)
code(s, 0.47, 1.95, 12.3, ["python tools/export_firmware_model.py mein_modell.keras Pilotdaten/"], size=16)
T(s, 0.47, 2.85, 5.6, 3.9, [
    [("Das Skript ", {"bold": True}), ("rechnet das Modell in ganze Zahlen um (int8), damit es auf den Chip passt.", {})],
    [("Mit den Aufnahmen ", {"bold": True}), ("prüft es, dass das kleine Modell genauso entscheidet wie das Original.", {})],
    [("Die Ergebnisse ", {"bold": True}), ("schreibt es direkt in den Firmware-Ordner – nichts kopieren.", {})],
], size=16, punkte=True, abstand=12)
code(s, 6.4, 2.85, 6.35, [
    "Modell         : mein_modell.keras",
    "int8-TFLite    : 76.7 KB",
    "int8 vs. float : 99.5% gleiche",
    "                 Entscheidungen",
    "geschrieben    : .../modell_sohle.h",
    "eigene Kerne   : Entscheidung",
    "                 gleich 100.0%",
    "geschrieben    : .../modell_netz.h",
], size=12)
N(s, "Gut ist: über 95 % gleiche Entscheidungen. Steht dort ‚kein C++-Compiler gefunden‘, wird nur die zweite "
     "Prüfung übersprungen – die Dateien sind trotzdem fertig. Die Beispielausgabe ist gekürzt.")

# 7 ------------------------------------------------------------------ Was entsteht
s = d.folie("Was der Export erzeugt")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Datei", "Wo", "Was drin ist"],
    ["mein_modell_int8.tflite", "neben der .keras-Datei", "das umgewandelte Modell (int8) – zum Aufheben"],
    ["modell_netz.h", "firmware/CleverSole/", "die Gewichte als C-Code – damit rechnet der Chip"],
    ["modell_sohle.h", "firmware/CleverSole/", "Prüfwerte für den Selbsttest beim Start"],
], [3.6, 3.4, 5.3], size=16, h_zeile=0.62, hervor=(2,), zentriert_ab=3)
T(s, 0.47, 4.75, 12.3, 1.9, [
    [("Warum nicht direkt die .tflite-Datei? ", {"bold": True}),
     ("Die übliche Bibliothek (TFLite Micro) rechnet auf diesem Chip falsch. Deshalb rechnet die Firmware "
      "mit eigenen, einfachen Funktionen – mit denselben Gewichten und denselben Ergebnissen.", {})],
], size=16)
N(s, "Die drei Dateien nie von Hand ändern. Für ein neues Modell einfach Schritt 3 wiederholen.")

# 8 ------------------------------------------------------------------ Schritt 4
s = d.folie("Schritt 4: Arduino IDE einrichten (nur beim ersten Mal)")
schritt(s, 4)
T(s, 0.47, 1.95, 12.3, 0.4, "Datei → Einstellungen → „Zusätzliche Boardverwalter-URLs“ einfügen:", size=16)
code(s, 0.47, 2.45, 12.3, ["https://espressif.github.io/arduino-esp32/package_esp32_index.json"], size=14)
T(s, 0.47, 3.3, 5.6, 0.4, "Danach im Boardverwalter „esp32“ installieren.", size=16)
d.tabelle(s, 0.47, 3.85, 7.0, [
    ["Werkzeuge →", "Einstellung"],
    ["Board", "ESP32C6 Dev Module"],
    ["Partition Scheme", "Huge APP (3MB No OTA)"],
    ["USB CDC On Boot", "Enabled"],
], [2.9, 4.1], size=16, h_zeile=0.52, zentriert_ab=2)
kasten(s, 7.9, 3.85, 4.85, 2.1, "Gut zu wissen", [
    "Keine weitere Bibliothek nötig.",
    "Ohne „USB CDC On Boot“ bleibt der Monitor leer."], size=14)
N(s, "Diese Einstellungen bleiben gespeichert.")

# 9 ------------------------------------------------------------------ Schritt 5
s = d.folie("Schritt 5: Firmware auf den Chip laden")
schritt(s, 5)
T(s, 0.47, 1.95, 5.9, 4.8, [
    "Sohle per USB-C anschließen.",
    "In der Arduino IDE öffnen: firmware/CleverSole/CleverSole.ino – die anderen Dateien erscheinen als Reiter.",
    "Oben den Port wählen und auf den Pfeil (Hochladen) klicken.",
    "Serieller Monitor öffnen, 115200 Baud.",
    [("Alle fünf Selbsttests OK ", {"bold": True}), ("= der Chip rechnet richtig.", {})],
], size=16, punkte=True, abstand=10)
code(s, 6.75, 1.95, 6.0, [
    "Sensor: MPU-6500 (WHO_AM_I = 0x70)",
    "BLE aktiv als \"CleverSole-01\"",
    "Selbsttest 0: ... OK",
    "Selbsttest 1: ... OK",
    "Selbsttest 2: ... OK",
    "Selbsttest 3: ... OK",
    "Selbsttest 4: ... OK",
    "Modell (eigene Kerne) ok",
], size=13)
N(s, "Steht bei einem Selbsttest FALSCH, wurden modell_netz.h und modell_sohle.h nicht zusammen erzeugt – Schritt 3 wiederholen.")

# 10 ------------------------------------------------------------------ Schritt 6
s = d.folie("Schritt 6: Testen – stehen, gehen, live mitlesen")
schritt(s, 6)
d.ablauf(s, 0.47, 1.95, 7.6, [("Stehen", "1 s ruhig"), ("Gehen", "10–15 Schritte"), ("Läuft", "Inferenz aktiv")],
         h=1.15, hervor=(2,), size=15)
code(s, 0.47, 3.35, 7.6, [
    "LIVE  Sturz   2%  [..........]  Stimmen 0/5  kein Sturz",
    "LIVE  Sturz  91%  [#########.]  Stimmen 1/5  Verdacht",
    "LIVE  Sturz  97%  [##########]  Stimmen 3/5  STURZ!",
], size=12)
T(s, 0.47, 4.55, 7.6, 2.2, [
    [("Sturz %: ", {"bold": True}), ("Wert des Netzes für die letzten 2 s, alle 0,2 s neu.", {})],
    [("Stimmen: ", {"bold": True}), ("wie viele der letzten 5 Werte über 50 % lagen.", {})],
    [("STURZ! ", {"bold": True}), ("ab 3 von 5 – genau ein Alarm je Sturz.", {})],
], size=15, punkte=True, abstand=6)
kasten(s, 8.4, 1.95, 4.35, 2.9, "Am Handy mitlesen", [
    "App „Serial Bluetooth Terminal“",
    "Devices → Bluetooth LE → CleverSole-01",
    "Es erscheinen dieselben LIVE-Zeilen",
    "Optional: nach jedem Sturz anhalten, weiter mit R"], size=14)
N(s, "Stehen und Gehen kalibrieren die Einbaulage; erst danach rechnet das Modell. "
     "Das Anhalten nach einem Sturz schaltet man in CleverSole.ino mit NACH_STURZ_AUF_R_WARTEN ein.")

# 11 ------------------------------------------------------------------ Fehler
s = d.folie("Wenn etwas nicht klappt")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Was man sieht", "Was hilft"],
    ["„python“ wird nicht gefunden", "Python installieren, dabei „Add to PATH“ anhaken"],
    ["Export: „Unerwarteter Modellaufbau“", "Modell hat einen anderen Aufbau als das Projekt-CNN → Netz anpassen"],
    ["Serieller Monitor bleibt leer", "Werkzeuge → USB CDC On Boot: Enabled"],
    ["Selbsttest FALSCH", "Schritt 3 wiederholen, dann neu hochladen"],
    ["Keine LIVE-Zeilen", "erst 1 s stehen und 10–15 Schritte gehen"],
    ["App findet die Sohle nicht", "Bluetooth LE wählen, nicht Classic"],
], [5.0, 7.3], size=15, h_zeile=0.58, zentriert_ab=2)
N(s, "Die eigenen Rechenfunktionen passen zum Projekt-CNN (3 Faltungen, Mittelwert, 2 Dense-Schichten). "
     "Andere Filterzahlen gehen, ein ganz anderer Aufbau nicht.")

# 12 ------------------------------------------------------------------ Begriffe
s = d.folie("Kurz erklärt")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Begriff", "In einem Satz"],
    ["TensorFlow / Keras", "Werkzeug zum Trainieren; Keras baut das Netz aus Schichten"],
    [".keras", "das trainierte Modell mit Kommazahlen – zu groß für den Chip"],
    ["int8", "jedes Gewicht als ganze Zahl von −128 bis 127: viermal kleiner"],
    [".tflite", "Dateiformat für das umgewandelte Modell"],
    ["Kerne", "kleine C-Funktionen, die eine Schicht ausrechnen – hier selbst geschrieben"],
], [3.2, 9.1], size=16, h_zeile=0.6, zentriert_ab=2)
N(s, "Zum Nachschlagen.")

# 13 ------------------------------------------------------------------ Fragen
s = d.folie("Fragen?")
T(s, 0.47, 2.3, 12.3, 2.0, [
    "Alles Weitere steht in firmware/CleverSole/ANLEITUNG.md:",
    [("github.com/Alyelb/ML-Modell-for-Fall-detection", {"bold": True})],
], size=20, color=GRAU, abstand=10)
N(s, "Danke.")

d.speichern(REPO / "praesentation" / "3_Anleitung_Modell_auf_den_Chip.pptx")
