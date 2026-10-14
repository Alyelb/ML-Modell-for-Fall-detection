"""Praesentation 3: Anleitung -- vom trainierten Modell bis zur Meldung in der App."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from thm_deck import (DUNKEL, GRAU, GRUEN, HELL, QUELLEN, REPO, WEISS, Deck)  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402

d = Deck()
T, N = d.text, d.notiz
CODE_BG = RGBColor(0x26, 0x32, 0x38)


def code(slide, x, y, w, zeilen, size=14, h=None):
    """Dunkler Kasten mit Konsolen-/Codezeilen in Courier New."""
    h = h or 0.25 + 0.3 * len(zeilen)
    d.flaeche(slide, x, y, w, h, fill=CODE_BG)
    tb = T(slide, x + 0.2, y + 0.13, w - 0.4, h - 0.2, zeilen, size=size, color=WEISS, abstand=2)
    for p in tb.text_frame.paragraphs:
        for r in p.runs:
            r.font.name = "Courier New"
    return tb


def schritt(slide, nr, titel_text):
    """Kleine Schrittmarke oben rechts, damit man im Ablauf weiss, wo man ist."""
    T(slide, 10.75, 1.25, 2.0, 0.4, f"Schritt {nr} von 7", size=13, color=GRAU, align=PP_ALIGN.RIGHT)


# 1 ------------------------------------------------------------------ Titel
s = d.titelfolie([
    ("Vom trainierten Modell bis zur Meldung in der App", 18, True, DUNKEL),
    ("Anleitung: Export, Hochladen, Einbau, Test", 12, False, GRAU),
    ("Aly Elbermawy", 12, True, DUNKEL),
    ("Studienprojekt 2 · THM Campus Friedberg", 11, False, GRAU)])
N(s, "Dieser Teil ist zum Nachmachen gedacht. Alle Dateien liegen im GitHub-Repository.")

# 2 ------------------------------------------------------------ Ueberblick
s = d.folie("Der Weg in sieben Schritten")
d.ablauf(s, 0.47, 2.0, 12.3, [("1 Training", "Colab,\nNotebook 04"), ("2 Export", "Python-\nSkript"),
                              ("3 Arduino", "IDE ein-\nrichten"), ("4 Hochladen", "Selbsttest\nprüfen"),
                              ("5 Einbau", "Modul unter\ndie Ferse"), ("6 Kalibrieren", "stehen,\ngehen"),
                              ("7 App", "nRF Connect")], h=1.45, size=16)
T(s, 0.47, 3.85, 6.0, 2.9, [
    [("Wer nur das fertige Modell nutzen will, ", {"bold": True}),
     ("beginnt bei Schritt 3. Die Datei firmware/CleverSole/modell_sohle.h enthält das aktuelle Modell bereits.", {})],
], size=17)
T(s, 6.8, 3.85, 5.95, 2.9, [
    [("Repository: ", {"bold": True}), ("github.com/Alyelb/ML-Modell-for-Fall-detection", {})],
    [("Firmware: ", {"bold": True}), ("firmware/CleverSole/", {})],
    [("Ausführliche Anleitung: ", {"bold": True}), ("firmware/CleverSole/ANLEITUNG.md", {})],
], size=16, abstand=10)
N(s, "Überblick. Die Schritte 1 und 2 braucht man nur, wenn ein neues Modell trainiert werden soll.")

# 3 ------------------------------------------------------------ Material
s = d.folie("Was man braucht")
T(s, 0.47, 1.95, 6.0, 4.8, [
    [("Hardware", {"bold": True, "color": GRUEN})],
    [("Seeed XIAO ESP32-C6", {"bold": True})],
    [("IMU-Modul ", {"bold": True}), ("MPU-6050 oder MPU-6500 (I²C)", {})],
    [("LiPo-Akku ", {"bold": True}), ("mit Spannungsteiler 2 × 100 kΩ", {})],
    [("USB-C-Kabel ", {"bold": True}), ("mit Datenleitungen", {})],
], size=17, abstand=10)
T(s, 6.8, 1.95, 5.95, 4.8, [
    [("Software", {"bold": True, "color": GRUEN})],
    [("Arduino IDE 2 ", {"bold": True}), ("mit ESP32-Core 3.x", {})],
    [("Python 3.12 ", {"bold": True}), ("mit TensorFlow (nur für Schritt 2)", {})],
    [("Google Colab ", {"bold": True}), ("mit Drive (nur für Schritt 1)", {})],
    [("nRF Connect ", {"bold": True}), ("auf dem Smartphone (Android oder iOS)", {})],
], size=17, abstand=10)
N(s, "Python 3.14 hat noch kein TensorFlow, deshalb 3.12.")

# 4 ------------------------------------------------------------ Verdrahtung
s = d.folie("Verdrahtung: fünf Leitungen")
d.tabelle(s, 0.47, 1.95, 6.6, [
    ["XIAO ESP32-C6", "IMU-Modul", "Hinweis"],
    ["3V3", "VCC", ""],
    ["GND", "GND", "AD0 ebenfalls an GND"],
    ["D4 (GPIO22)", "SDA", ""],
    ["D5 (GPIO23)", "SCL", ""],
    ["D1 (GPIO1)", "INT", "weckt aus dem Tiefschlaf"],
], [2.0, 1.6, 3.0], size=16, h_zeile=0.55, zentriert_ab=3)
d.bild(s, QUELLEN / "foto_platine.jpg", 7.5, 1.95, w=5.25)
T(s, 0.47, 5.45, 6.6, 1.4, [
    [("INT muss auf GPIO0–7 liegen, ", {"bold": True}), ("sonst wacht das Gerät nie wieder auf.", {})],
    [("Akku-Messung: ", {"bold": True}), ("GPIO3 ist am XIAO C6 für die Antenne belegt – Teiler an D0 oder D2 und PIN_BATT_ADC anpassen.", {})],
], size=15, punkte=True, abstand=6)
N(s, "Die Pins stehen oben in CleverSole.ino. Nur GPIO0 bis GPIO7 sind beim C6 LP-GPIOs und können wecken.")

# 5 ------------------------------------------------------------ Schritt 1 Training
s = d.folie("Schritt 1: Modell trainieren (nur bei Bedarf)")
schritt(s, 1, "")
T(s, 0.47, 1.95, 6.3, 4.8, [
    "Notebook notebook/04_fuss_orientierung.ipynb in Colab öffnen, Drive verbinden, alle Zellen ausführen.",
    "Teil D trainiert die Kette SisFall → KFall → Schienbein-Stürze + Sohlen-Alltag mit Drehungen und Spiegelungen.",
    "Ergebnis im Drive-Ordner ML_Fall_Detection/ergebnisse/:",
], size=17, punkte=True, abstand=12)
code(s, 0.85, 4.35, 5.9, ["fall_model_lowerlimb_aug.keras"], size=15)
T(s, 7.2, 1.95, 5.55, 4.8, [
    [("Gut zu wissen", {"bold": True, "color": GRUEN})],
    "Eine GPU-Laufzeit in Colab spart viel Zeit.",
    "Die Daten erst lokal in Colab kopieren – direkt aus Drive zu lesen ist sehr langsam.",
    "Das Notebook schreibt neben dem Modell eine results.json mit allen Kennzahlen.",
], size=16, abstand=10)
N(s, "Wer das vorhandene Modell nutzt, überspringt diesen Schritt.")

# 6 ------------------------------------------------------------ Schritt 2 Export
s = d.folie("Schritt 2: Modell für den Chip exportieren")
schritt(s, 2, "")
code(s, 0.47, 1.95, 12.3, ["pip install tensorflow",
                           "python tools/export_firmware_model.py fall_model_lowerlimb_aug.keras Pilotdaten/"], size=15)
T(s, 0.47, 3.0, 6.2, 0.4, [[("Das Skript erledigt alles:", {"bold": True, "color": GRUEN})]], size=16)
T(s, 0.47, 3.5, 6.2, 3.3, [
    "rechnet die Normierungsschichten in die Faltungen ein",
    "wandelt in int8 um (Kalibrierung mit den Pilotdaten)",
    "prüft int8 gegen das Originalmodell",
    "berechnet die Sollwerte für den Selbsttest",
    "schreibt firmware/CleverSole/modell_sohle.h",
], size=16, punkte=True, abstand=6)
code(s, 6.95, 3.0, 5.8, [
    "BatchNorm  : 3 Schichten eingerechnet",
    "int8-TFLite: 74.9 KB",
    "int8/float : 99.50% gleiche Entsch.",
    "Operatoren : CONV_2D, EXPAND_DIMS,",
    "             FULLY_CONNECTED, LOGISTIC,",
    "             MAX_POOL_2D, MEAN, RESHAPE",
    "Selbsttest : {0: -128, -5: -127, ...}",
], size=13)
T(s, 6.95, 5.6, 5.8, 1.1, [[("Steht MUL oder ADD in der Liste, ", {"bold": True}),
                             ("nicht hochladen – dann rechnet der Chip falsch.", {})]], size=15)
N(s, "Beispielausgabe gekürzt. Der Ordner Pilotdaten enthält die eigenen Logger-Aufnahmen, sie dienen nur der "
     "int8-Kalibrierung und der Kontrolle. Die Größe hängt leicht vom Modell ab, etwa 75 bis 80 KB.")

# 7 ------------------------------------------------------------ Schritt 3 Arduino
s = d.folie("Schritt 3: Arduino IDE einrichten")
schritt(s, 3, "")
T(s, 0.47, 1.95, 12.3, 0.4, "Datei → Einstellungen → Zusätzliche Boardverwalter-URLs:", size=16)
code(s, 0.47, 2.4, 12.3, ["https://espressif.github.io/arduino-esp32/package_esp32_index.json"], size=15)
d.tabelle(s, 0.47, 3.35, 7.4, [
    ["Werkzeuge →", "Einstellung"],
    ["Board", "ESP32C6 Dev Module"],
    ["Partition Scheme", "Huge APP (3MB No OTA)"],
    ["Flash Size", "4 MB"],
    ["USB CDC On Boot", "Enabled"],
], [3.0, 4.4], size=16, h_zeile=0.52, zentriert_ab=2)
T(s, 8.3, 3.35, 4.45, 3.3, [
    [("Nur eine TFLite-Bibliothek!", {"bold": True, "color": GRUEN})],
    "Der ESP32-Core 3.x bringt TFLite Micro schon mit. Eine zweite Bibliothek zusätzlich zu installieren führt dazu, "
    "dass der Chip scheinbar fehlerfrei rechnet, aber nichts ausgibt.",
], size=15, abstand=8)
N(s, "Ohne USB CDC On Boot bleibt der serielle Monitor leer. Die alte Bibliothek TensorFlowLite_ESP32 nicht verwenden.")

# 8 ------------------------------------------------------------ Schritt 4 Hochladen
s = d.folie("Schritt 4: Hochladen und Selbsttest prüfen")
schritt(s, 4, "")
T(s, 0.47, 1.95, 5.6, 4.8, [
    "Für den ersten Start in CleverSole.ino TESTMODUS auf 1 setzen.",
    "CleverSole.ino öffnen, Port wählen, Hochladen.",
    "Seriellen Monitor mit 115200 Baud öffnen.",
    [("Alle fünf Zeilen müssen OK zeigen. ", {"bold": True}),
     ("Erst dann sind die Sturz-Werte des Chips gültig.", {})],
], size=17, punkte=True, abstand=12)
code(s, 6.4, 1.95, 6.35, [
    "Sensor: MPU-6500 (WHO_AM_I = 0x70)",
    "Selbsttest 0: alle=   0  roh= -128  soll= -128  OK",
    "Selbsttest 1: alle=  -5  roh= -127  soll= -127  OK",
    "Selbsttest 2: alle=  10  roh= -113  soll= -113  OK",
    "Selbsttest 3: alle=  13  roh=   94  soll=   94  OK",
    "Selbsttest 4: alle= -13  roh=   56  soll=   56  OK",
    "Modell geladen. Arena benutzt: ... Byte",
    "BLE aktiv als \"CleverSole-01\"",
], size=12)
T(s, 6.4, 5.0, 6.35, 1.7, [[("Steht dort FALSCH: ", {"bold": True}),
                            ("Modell neu exportieren und prüfen, ob nur eine TFLite-Bibliothek eingebunden ist.", {})]],
  size=15)
N(s, "Die Sollwerte stehen in modell_sohle.h und werden bei jedem Export neu berechnet. Im Einsatz TESTMODUS wieder auf 0, "
     "sonst schläft das Gerät nie.")

# 9 ------------------------------------------------------------ Schritt 5 Einbau
s = d.folie("Schritt 5: Einbau in die Sohle")
schritt(s, 5, "")
d.bild(s, QUELLEN / "einbaulage.png", 0.47, 1.95, h=3.9)
T(s, 7.0, 1.95, 5.75, 4.8, [
    [("IMU-Modul flach unter die Ferse, ", {"bold": True}), ("Bauteilseite nach oben.", {})],
    [("Der aufgedruckte X-Pfeil zeigt zu den Zehen.", {"bold": True})],
    "XIAO und Akku liegen daneben – ihre Lage ist egal.",
    "Modul nicht auf ein Kabel legen; es darf nicht kippeln.",
    "Dieselbe Sohle passt links und rechts, die Firmware kalibriert sich selbst.",
], size=17, punkte=True, abstand=12)
N(s, "Wichtig ist nur das blaue IMU-Modul, nicht die USB-Buchse. Kleine Schieflagen gleicht die Kalibrierung aus.")

# 10 ------------------------------------------------------------ Schritt 6 Kalibrieren
s = d.folie("Schritt 6: Kalibrieren – einmal stehen, einmal gehen")
schritt(s, 6, "")
d.ablauf(s, 0.47, 2.0, 12.3, [("Aufwecken", "Sohle bewegen"), ("Stehen", "mindestens 1 s\nruhig"),
                              ("Gehen", "10–15 Schritte"), ("Fertig", "Erkennung läuft")], h=1.3, hervor=(3,), size=17)
code(s, 0.47, 3.75, 12.3, [
    "Kalibrierung ok: oben=(...) vorn=(...) Querachse 92 %, Abweichung zur Vorgabe 12 Grad",
    "12 Schritte, Einbaulage kalibriert -> Inferenz aktiv"], size=14)
T(s, 0.47, 4.85, 12.3, 1.9, [
    [("Stehen: ", {"bold": True}), ("die Schwerkraft zeigt, wo oben ist.", {})],
    [("Gehen: ", {"bold": True}), ("der Fuß dreht um die Querachse, die Schwungphase zeigt nach vorn.", {})],
    [("Klappt es nicht ", {"bold": True}), ("(zu wenig gegangen), gilt die Einbauvorgabe: Chip oben, X-Pfeil zu den Zehen.", {})],
], size=16, punkte=True, abstand=6)
N(s, "Die Kalibrierung läuft nach jedem Aufwachen neu, man muss nichts drücken.")

# 11 ------------------------------------------------------------ Schritt 7 App
s = d.folie("Schritt 7: Die Meldung in der App ansehen")
schritt(s, 7, "")
T(s, 0.47, 1.95, 5.6, 4.8, [
    "nRF Connect öffnen, scannen, CleverSole-01 verbinden.",
    "Dienst FFF0 öffnen.",
    "Bei FFF1 und FFF2 die Benachrichtigung einschalten (Pfeil-Symbol).",
    "Batterie steht im Dienst 180F.",
], size=17, punkte=True, abstand=12)
code(s, 6.4, 1.95, 6.35, [
    "FFF1  STURZ 93% n=3 batt=87",
    "      ... Person liegt still ...",
    "FFF2  LAGE vorwaerts 92%",
    "FFF2  STUFE2 bestaetigt",
], size=14)
d.tabelle(s, 6.4, 3.6, 6.35, [
    ["Meldung", "Bedeutung"],
    ["STURZ 93%", "Ausgabe des Netzes, keine Wahrscheinlichkeit"],
    ["LAGE", "Richtung aus der Liegelage"],
    ["STUFE2", "Aufprall, Lageänderung und Ruhe passen"],
], [1.7, 4.65], size=14, h_zeile=0.5, zentriert_ab=2)
N(s, "n=3 heißt: drei von fünf Fenstern haben für Sturz gestimmt. Die Richtung ist eine Schätzung; links und rechts "
     "werden als seitlich zusammengefasst.")

# 12 ------------------------------------------------------------ Testmodus
s = d.folie("Für Versuche: der Testmodus")
code(s, 0.47, 1.95, 5.6, ["#define TESTMODUS 1", "", "T,812345,4,0", "T,812545,71,1", "T,812745,96,2", "T,812945,94,3"],
     size=15)
T(s, 6.4, 1.95, 6.35, 4.8, [
    "Jede Entscheidung wird alle 0,2 s gesendet: Zeit in ms, Sturz-Wert in %, Stimmen von 5.",
    "Das Gerät schläft nicht ein.",
    "Mitschnitt im seriellen Monitor oder in nRF Connect (FFF2), Uhrzeit jeder Aktivität notieren.",
    [("Auswerten: ", {"bold": True}), ("erkannte ÷ ausgeführte Stürze = Sensitivität; Alarme im Alltag ÷ Stunden = Fehlalarme je Stunde.", {})],
], size=16, punkte=True, abstand=10)
N(s, "Die Beispielzeilen sind ausgedacht und zeigen nur das Format.")

# 13 ------------------------------------------------------------ Fehlersuche
s = d.folie("Wenn etwas nicht funktioniert")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Symptom", "Ursache", "Abhilfe"],
    ["Serieller Monitor bleibt leer", "USB CDC On Boot aus", "Werkzeuge → USB CDC On Boot: Enabled"],
    ["IMU nicht gefunden", "Verdrahtung, Adresse", "SDA/SCL prüfen, AD0 an GND"],
    ["Selbsttest FALSCH, immer gleicher Wert", "zwei TFLite-Bibliotheken oder MUL/ADD im Modell", "eine Bibliothek, Modell neu exportieren"],
    ["AllocateTensors fehlgeschlagen", "Arena zu klein", "ARENA_GROESSE in 16-KB-Schritten erhöhen"],
    ["Wacht nicht mehr auf", "INT nicht auf GPIO0–7", "INT an D1 (GPIO1) legen"],
    ["Keine Meldungen in der App", "Benachrichtigung aus", "bei FFF1/FFF2 Benachrichtigung einschalten"],
    ["Viele Fehlalarme", "Kalibrierung fehlgeschlagen", "Meldung „Kalibrierung ok“ prüfen, mehr gehen"],
], [3.8, 4.0, 4.5], size=14, h_zeile=0.56, zentriert_ab=3)
N(s, "Die häufigsten Probleme aus dem Projekt.")

# 14 ------------------------------------------------------------ Fragen
s = d.folie("Fragen?")
T(s, 0.47, 2.3, 12.3, 2.0, [
    "Alle Dateien und die ausführliche Anleitung:",
    [("github.com/Alyelb/ML-Modell-for-Fall-detection", {"bold": True})],
], size=20, color=GRAU, abstand=10)
N(s, "Danke.")

d.speichern(REPO / "praesentation" / "3_Anleitung_Modell_auf_den_Chip.pptx")
