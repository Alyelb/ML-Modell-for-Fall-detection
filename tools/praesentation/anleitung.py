"""Praesentation 3: Anleitung -- vom Einbau des Chips bis zur Meldung in der App,
danach: ein neues Modell trainieren und auf den Chip bringen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from thm_deck import (DUNKEL, GRAU, GRUEN, HELL, QUELLEN, REPO, WEISS, Deck)  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402

d = Deck()
T, N = d.text, d.notiz
CODE_BG = RGBColor(0x26, 0x32, 0x38)
KOMMENTAR = RGBColor(0x9C, 0xCC, 0x65)
SCHRITTE = 9


def code(slide, x, y, w, zeilen, size=13, h=None):
    """Dunkler Kasten mit Code; Text nach '#' oder '//' wird gruen gesetzt."""
    h = h or 0.22 + 0.27 * len(zeilen) * size / 13
    d.flaeche(slide, x, y, w, h, fill=CODE_BG)
    absaetze = []
    for z in zeilen:
        teil = None
        for marke in ("  # ", "  // "):
            if marke in z:
                i = z.index(marke)
                teil = [(z[:i], {}), (z[i:], {"color": KOMMENTAR})]
                break
        if teil is None and z.lstrip().startswith(("#", "//")) and not z.lstrip().startswith("#define"):
            teil = [(z, {"color": KOMMENTAR})]
        absaetze.append(teil or [(z, {})])
    tb = T(slide, x + 0.2, y + 0.11, w - 0.4, h - 0.15, absaetze, size=size, color=WEISS, abstand=1)
    for p in tb.text_frame.paragraphs:
        for r in p.runs:
            r.font.name = "Courier New"
    return tb


def schritt(slide, nr):
    T(slide, 10.75, 1.25, 2.0, 0.4, f"Schritt {nr} von {SCHRITTE}", size=13, color=GRAU, align=PP_ALIGN.RIGHT)


def hinweis(slide, x, y, w, h, kopf, zeilen, size=15):
    d.flaeche(slide, x, y, w, h, fill=HELL)
    T(slide, x + 0.25, y + 0.18, w - 0.5, 0.4, [[(kopf, {"bold": True, "color": GRAU})]], size=size)
    T(slide, x + 0.25, y + 0.65, w - 0.5, h - 0.8, zeilen, size=size, punkte=True, abstand=6)


# 1 ------------------------------------------------------------------ Titel
s = d.titelfolie([
    ("Vom Einbau des Chips bis zur Meldung in der App", 18, True, DUNKEL),
    ("Anleitung: Einbau, Hochladen, Kalibrieren, eigenes Modell", 12, False, GRAU),
    ("Aly Elbermawy", 12, True, DUNKEL),
    ("Studienprojekt 2 · THM Campus Friedberg", 11, False, GRAU)])
N(s, "Zum Nachmachen. Erst die fertige Sohle in Betrieb nehmen, danach zeige ich, wie man ein neues Modell trainiert "
     "und auf den Chip bringt. Alle Dateien liegen im GitHub-Repository.")

# 2 ------------------------------------------------------------ Ueberblick
s = d.folie("Der Weg in neun Schritten")
T(s, 0.47, 1.9, 6.0, 0.4, [[("Sohle in Betrieb nehmen", {"bold": True, "color": GRUEN})]], size=17)
d.ablauf(s, 0.47, 2.4, 12.3, [("1 Verdrahten", "fünf Leitungen"), ("2 Einbauen", "Modul unter\ndie Ferse"),
                              ("3 Prüfen", "vor dem\nFestkleben"), ("4 Arduino", "IDE ein-\nrichten"),
                              ("5 Hochladen", "Selbsttest"), ("6 Kalibrieren", "stehen,\ngehen"),
                              ("7 App", "live mitlesen,\nAlarm")], h=1.3, size=15)
T(s, 0.47, 4.15, 6.0, 0.4, [[("Neues Modell (nur bei Bedarf)", {"bold": True, "color": GRUEN})]], size=17)
d.ablauf(s, 0.47, 4.65, 4.0, [("8 Trainieren", "Colab"), ("9 Exportieren", "Python")], h=1.3, size=15)
T(s, 5.0, 4.7, 7.75, 2.0, [
    "Das aktuelle Modell steckt bereits in der Firmware. Schritt 8 und 9 braucht man nur für ein neu trainiertes Modell.",
    [("Repository: ", {"bold": True}), ("github.com/Alyelb/ML-Modell-for-Fall-detection", {})],
], size=15, abstand=8)
N(s, "Überblick.")

# 3 ------------------------------------------------------------ Verdrahtung
s = d.folie("Schritt 1: Verdrahtung – fünf Leitungen")
schritt(s, 1)
d.tabelle(s, 0.47, 1.95, 6.6, [
    ["XIAO ESP32-C6", "IMU-Modul", "Hinweis"],
    ["3V3", "VCC", ""],
    ["GND", "GND", "AD0 ebenfalls an GND"],
    ["D4 (GPIO22)", "SDA", "I²C-Daten"],
    ["D5 (GPIO23)", "SCL", "I²C-Takt"],
    ["D1 (GPIO1)", "INT", "weckt aus dem Tiefschlaf"],
], [2.0, 1.6, 3.0], size=16, h_zeile=0.55, zentriert_ab=3)
d.bild(s, QUELLEN / "foto_platine.jpg", 7.5, 1.95, w=5.25)
T(s, 0.47, 5.45, 6.6, 1.4, [
    [("INT muss auf GPIO0–7 liegen, ", {"bold": True}), ("sonst wacht das Gerät nie wieder auf.", {})],
    [("Akku-Messung: ", {"bold": True}), ("GPIO3 ist am XIAO C6 für die Antenne belegt – Teiler (2 × 100 kΩ) an D0 oder D2, PIN_BATT_ADC anpassen.", {})],
], size=15, punkte=True, abstand=6)
N(s, "Die Pins stehen oben in CleverSole.ino. Nur GPIO0 bis GPIO7 sind beim C6 LP-GPIOs und können wecken.")

# 4 ------------------------------------------------------------ Einbau
s = d.folie("Schritt 2: Das IMU-Modul richtig in die Sohle setzen")
schritt(s, 2)
d.bild(s, QUELLEN / "einbaulage.png", 0.47, 1.95, h=3.6)
T(s, 7.0, 1.95, 5.75, 4.8, [
    [("Unter die Ferse, ", {"bold": True}), ("dort ist die Sohle am flachsten und der Aufprall am deutlichsten.", {})],
    [("Flach, Bauteilseite nach oben. ", {"bold": True}), ("Nicht auf ein Kabel legen, nicht kippeln.", {})],
    [("Der aufgedruckte X-Pfeil zeigt zu den Zehen.", {"bold": True})],
    [("XIAO und Akku ", {"bold": True}), ("liegen daneben – ihre Lage ist egal. Es zählt nur das blaue IMU-Modul.", {})],
    [("Links und rechts gleich einbauen: ", {"bold": True}), ("Pfeil zu den Zehen, Chip oben. Nicht spiegeln.", {})],
], size=16, punkte=True, abstand=10)
T(s, 0.47, 5.75, 6.3, 1.0, [[("Warum so genau? ", {"bold": True}),
    ("Das Netz wertet jede Achse einzeln aus. Gespiegelt eingebaute Sensoren erkannten im Projekt bis zu neunmal weniger Stürze.", {})]],
  size=14, color=GRAU)
N(s, "Die Firmware gleicht kleine Schieflagen selbst aus. Die Richtung „vorn“ nimmt sie aber vom X-Pfeil – deshalb ist er wichtig.")

# 5 ------------------------------------------------------------ Pruefen
s = d.folie("Schritt 3: Vor dem Festkleben prüfen")
schritt(s, 3)
T(s, 0.47, 1.95, 6.0, 4.8, [
    "Modul mit Klebeband fixieren, Firmware hochladen (Schritt 4 und 5), Sohle in den Schuh.",
    "Kurz stillstehen, dann 15–20 Schritte gehen.",
    "Im seriellen Monitor die Kalibrierungszeile lesen:",
], size=16, punkte=True, abstand=10)
code(s, 0.47, 3.55, 12.3, ["Kalibrierung ok: oben=(-0.08 -0.08 0.99) vorn=(0.98 0.10 -0.05) Querachse 85 %,",
                           "                 Abweichung zur Vorgabe 6 Grad"], size=13)
d.tabelle(s, 0.47, 4.45, 12.3, [
    ["Wert", "gut", "dann prüfen"],
    ["oben", "nahe (0, 0, 1)", "anderes Vorzeichen oder Achse → Modul liegt falsch herum oder hochkant"],
    ["Abweichung zur Vorgabe", "unter 45 Grad", "darüber → X-Pfeil zeigt nicht zu den Zehen"],
    ["Querachse", "über 70 %", "darunter → mehr gehen; Modul sitzt locker"],
], [3.0, 2.6, 6.7], size=14, h_zeile=0.5, zentriert_ab=3)
N(s, "Erst festkleben, wenn diese Zeile passt. Die Beispielwerte sind ausgedacht und zeigen nur, wie es aussehen soll.")

# 6 ------------------------------------------------------------ Begriffe
s = d.folie("Kurz erklärt: was ist was?")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Begriff", "Was es ist", "Wo es im Projekt vorkommt"],
    ["TensorFlow", "Bibliothek von Google zum Trainieren neuronaler Netze", "Training in Colab (Notebooks)"],
    ["Keras", "einfache Oberfläche von TensorFlow: Netz aus Schichten zusammenstecken", "Modell bauen, trainieren, .keras speichern"],
    [".keras", "gespeichertes Modell mit Aufbau und Gewichten (Gleitkomma)", "fall_model_lowerlimb_aug.keras"],
    ["TensorFlow Lite", "kompaktes Format für kleine Geräte; Gewichte als ganze Zahlen (int8)", ".tflite, rund 77 KB"],
    ["TFLite Micro", "Bibliothek, die .tflite auf Mikrocontrollern ausführt", "auf dem C6 fehlerhaft → ersetzt"],
    ["eigene Kerne", "dieselben int8-Rechenschritte in einfachem C", "netz_int8.h + modell_netz.h"],
], [2.4, 5.6, 4.3], size=14, h_zeile=0.58, zentriert_ab=3)
N(s, "Der Weg: Keras-Modell trainieren → in int8 umrechnen (TensorFlow Lite) → als C-Datei in die Firmware. "
     "Auf dem Chip rechnen jetzt eigene Funktionen statt TFLite Micro.")

# 7 ------------------------------------------------------------ Arduino
s = d.folie("Schritt 4: Arduino IDE einrichten")
schritt(s, 4)
T(s, 0.47, 1.95, 12.3, 0.4, "Datei → Einstellungen → Zusätzliche Boardverwalter-URLs, danach im Boardverwalter „esp32“ (Espressif, 3.x) installieren:", size=15)
code(s, 0.47, 2.45, 12.3, ["https://espressif.github.io/arduino-esp32/package_esp32_index.json"], size=14)
d.tabelle(s, 0.47, 3.35, 7.4, [
    ["Werkzeuge →", "Einstellung"],
    ["Board", "ESP32C6 Dev Module"],
    ["Partition Scheme", "Huge APP (3MB No OTA)"],
    ["Flash Size", "4 MB"],
    ["USB CDC On Boot", "Enabled"],
], [3.0, 4.4], size=16, h_zeile=0.52, zentriert_ab=2)
hinweis(s, 8.3, 3.35, 4.45, 2.6, "Keine Zusatzbibliothek", [
    "Die Firmware braucht keine TFLite-Bibliothek mehr.",
    "Ohne „USB CDC On Boot“ bleibt der serielle Monitor leer."], size=14)
N(s, "Ordner firmware/CleverSole öffnen, CleverSole.ino laden. Alle .h-Dateien im selben Ordner werden automatisch mitkompiliert.")

# 8 ------------------------------------------------------------ Hochladen
s = d.folie("Schritt 5: Hochladen und Selbsttest lesen")
schritt(s, 5)
T(s, 0.47, 1.95, 5.6, 4.8, [
    "Port wählen, Hochladen, seriellen Monitor mit 115200 Baud öffnen.",
    "Beim Start rechnet der Chip fünf feste Eingaben und vergleicht sie mit den Werten vom PC.",
    [("Alle fünf Zeilen OK: ", {"bold": True}), ("Der Chip rechnet richtig.", {})],
    [("Danach im Betrieb: ", {"bold": True}), ("alle 0,2 s eine LIVE-Zeile: Sturz-Wert, Stimmen der letzten fünf Fenster, Urteil.", {})],
], size=16, punkte=True, abstand=10)
code(s, 6.4, 1.95, 6.35, [
    "Sensor: MPU-6500 (WHO_AM_I = 0x70)",
    "BLE aktiv als \"CleverSole-01\"",
    "Selbsttest 0: alle=   0  p=0.000  soll=0.000  OK",
    "Selbsttest 1: alle=  -5  p=0.003  soll=0.004  OK",
    "Selbsttest 2: alle=  10  p=0.057  soll=0.059  OK",
    "Selbsttest 3: alle=  13  p=0.866  soll=0.867  OK",
    "Selbsttest 4: alle= -13  p=0.718  soll=0.719  OK",
    "Modell (eigene Kerne) ok, 117000 us je Fenster",
    "LIVE  Sturz   2%  [..........]  Stimmen 0/5  kein Sturz",
    "LIVE  Sturz  91%  [#########.]  Stimmen 1/5  Verdacht",
    "LIVE  Sturz  97%  [##########]  Stimmen 3/5  STURZ!",
], size=10)
N(s, "Die Sollwerte schreibt das Exportskript in modell_sohle.h. Verdacht erscheint beim ersten Fenster über 50 %, STURZ! bei drei von fünf (nach 0,4–0,8 s). Ein Wert, der sich über Minuten nicht ändert, ist ein Fehler.")

# 9 ------------------------------------------------------------ Kalibrieren
s = d.folie("Schritt 6: Kalibrieren – einmal stehen, einmal gehen")
schritt(s, 6)
d.ablauf(s, 0.47, 2.0, 12.3, [("Aufwecken", "Sohle bewegen"), ("Stehen", "mindestens 1 s\nruhig"),
                              ("Gehen", "10–15 Schritte"), ("Fertig", "Erkennung läuft")], h=1.3, hervor=(3,), size=17)
code(s, 0.47, 3.7, 12.3, [
    "Kalibrierung ok: oben=(...) vorn=(...) Querachse 85 %, Abweichung zur Vorgabe 6 Grad",
    "12 Schritte, Einbaulage kalibriert -> Inferenz aktiv"], size=13)
T(s, 0.47, 4.75, 12.3, 2.0, [
    [("Stehen: ", {"bold": True}), ("Die Schwerkraft zeigt, wo oben ist – damit wird die Neigung ausgeglichen.", {})],
    [("Gehen: ", {"bold": True}), ("Der Fuß dreht um die Querachse. Passt sie nicht zum X-Pfeil, wird nur die Neigung korrigiert "
                                  "(„Gang unklar: nur Neigung korrigiert“) – z. B. wenn man das Modul in der Hand bewegt.", {})],
    [("Automatisch: ", {"bold": True}), ("nach jedem Aufwachen neu, man muss nichts drücken.", {})],
], size=15, punkte=True, abstand=6)
N(s, "Genau diese Ausrichtung über die Schwerkraft wurde auf den Pilotdaten geprüft: alle 67 Stürze erkannt.")

# 10 ------------------------------------------------------------ App
s = d.folie("Schritt 7: Live mitlesen und Alarme in der App")
schritt(s, 7)
T(s, 0.47, 1.95, 5.6, 4.8, [
    [("Live mitlesen: ", {"bold": True}), ("App „Serial Bluetooth Terminal“ → Devices → Bluetooth LE → CleverSole-01. "
                                          "Es erscheinen dieselben Zeilen wie am USB; R sendet „weiter“.", {})],
    [("Alarme: ", {"bold": True}), ("nRF Connect → CleverSole-01 → Dienst FFF0; bei FFF1 und FFF2 die drei Pfeile antippen.", {})],
    "Batterie: Dienst 180F, Wert in Prozent.",
], size=15, punkte=True, abstand=10)
code(s, 6.4, 1.95, 6.35, ["FFF1  STURZ 93% n=3 batt=87", "      ... Person liegt still ...",
                          "FFF2  LAGE vorwaerts 92%", "FFF2  STUFE2 bestaetigt"], size=14)
d.tabelle(s, 6.4, 3.45, 6.35, [
    ["Meldung", "Bedeutung"],
    ["STURZ 93%", "Ausgabe des Netzes (keine Wahrscheinlichkeit)"],
    ["n=3", "drei von fünf Fenstern haben „Sturz“ gesagt"],
    ["LAGE", "Richtung aus der Liegelage (Schätzung)"],
    ["STUFE2", "Aufprall, Lageänderung und Ruhe passen"],
], [1.7, 4.65], size=14, h_zeile=0.5, zentriert_ab=2)
N(s, "Links und rechts werden als seitlich zusammengefasst, weil das Vorzeichen zwischen den Füßen nicht verlässlich ist.")

# 11 ------------------------------------------------------------ Testmodus
s = d.folie("Für Versuche: Schalter in CleverSole.ino")
d.tabelle(s, 0.47, 1.95, 5.6, [
    ["Schalter", "Wirkung"],
    ["LIVE_AUSGABE 1", "jede Entscheidung als LIVE-Zeile (Standard)"],
    ["NACH_STURZ_AUF_\nR_WARTEN", "nach Alarm anhalten bis R; Zeile einkommentieren"],
    ["TESTMODUS 1", "Zeilen T,Zeit,Sturz %,Stimmen; kein Schlaf"],
], [2.4, 3.2], size=13, h_zeile=0.62, zentriert_ab=3)
T(s, 6.4, 1.95, 6.35, 4.8, [
    "Jede Entscheidung kommt alle 0,2 s, seriell und über Bluetooth.",
    "Mit R-Warten bleibt die Sohle nach einem Sturz stehen, bis man R sendet – praktisch, wenn man nach dem Sturz liegen bleibt.",
    "Mitschnitt im seriellen Monitor oder in Serial Bluetooth Terminal, Uhrzeit jeder Aktivität notieren.",
    [("Auswerten: ", {"bold": True}), ("erkannte ÷ ausgeführte Stürze = Sensitivität; Alarme im Alltag ÷ Stunden = Fehlalarme je Stunde.", {})],
], size=16, punkte=True, abstand=10)
N(s, "Im Einsatz TESTMODUS auf 0 und R-Warten auskommentiert lassen.")

# 12 ------------------------------------------------------------ Training
s = d.folie("Schritt 8: Ein neues Modell trainieren (Keras)")
schritt(s, 8)
code(s, 0.47, 1.95, 7.6, [
    "from tensorflow import keras",
    "from tensorflow.keras import layers",
    "",
    "m = keras.Sequential([",
    "  layers.Input(shape=(100, 6)),           # 2 s x 6 Kanaele",
    "  layers.Conv1D(32, 5, activation=\"relu\"),  # 32 Muster je 0,1 s",
    "  layers.BatchNormalization(),",
    "  layers.MaxPooling1D(2),                 # Zeit halbieren",
    "  layers.Conv1D(64, 5, activation=\"relu\"),",
    "  layers.BatchNormalization(),",
    "  layers.MaxPooling1D(2),",
    "  layers.Conv1D(128, 5, activation=\"relu\"),",
    "  layers.BatchNormalization(),",
    "  layers.GlobalAveragePooling1D(),        # Mittel ueber die Zeit",
    "  layers.Dense(64, activation=\"relu\"),",
    "  layers.Dropout(0.3),",
    "  layers.Dense(1, activation=\"sigmoid\"),  # Sturz-Wert 0..1",
    "])",
    "m.compile(optimizer=\"adam\", loss=\"binary_crossentropy\")",
    "m.fit(X, y, epochs=30)                     # X: Fenster, y: 0/1",
    "m.save(\"fall_model_lowerlimb_aug.keras\")",
], size=10)
T(s, 8.4, 1.95, 4.35, 4.8, [
    [("So steht es in fall_lib.py ", {"bold": True}), ("(build_cnn). Die Notebooks rufen es auf.", {})],
    [("In der Praxis: ", {"bold": True}), ("notebook/04_fuss_orientierung.ipynb in Colab öffnen, Drive verbinden, alle Zellen ausführen.", {})],
    [("Ergebnis ", {"bold": True}), ("im Drive-Ordner ML_Fall_Detection/ergebnisse/: fall_model_lowerlimb_aug.keras und results.json.", {})],
    "GPU-Laufzeit wählen; Daten erst lokal in Colab kopieren.",
], size=15, punkte=True, abstand=10)
N(s, "Keras baut das Netz Schicht für Schicht. fit() passt die Gewichte an die Beispiele an, save() speichert alles in einer Datei.")

# 13 ------------------------------------------------------------ Export
s = d.folie("Schritt 9: Das Modell für den Chip exportieren")
schritt(s, 9)
code(s, 0.47, 1.95, 12.3, ["pip install tensorflow",
                           "python tools/export_firmware_model.py fall_model_lowerlimb_aug.keras Pilotdaten/"], size=14)
code(s, 0.47, 2.95, 7.6, [
    "m = keras.models.load_model(\"...keras\")",
    "m, n = bn_falten(m)          # Normierung in Faltungen einrechnen",
    "conv = tf.lite.TFLiteConverter.from_keras_model(m)",
    "conv.optimizations = [tf.lite.Optimize.DEFAULT]",
    "conv.representative_dataset = beispiele  # echte Fenster",
    "conv.target_spec.supported_ops = [",
    "    tf.lite.OpsSet.TFLITE_BUILTINS_INT8]  # nur int8",
    "conv.inference_input_type = tf.int8",
    "conv.inference_output_type = tf.int8",
    "blob = conv.convert()        # .tflite, ca. 77 KB",
    "netz_header(blob, \"modell_netz.h\")  # Gewichte als C",
], size=11)
T(s, 8.4, 2.95, 4.35, 3.9, [
    [("Das Skript macht alles in einem Lauf ", {"bold": True}), ("und prüft dabei int8 gegen das Original.", {})],
    [("Ergebnis: ", {"bold": True}), ("modell_netz.h und modell_sohle.h in firmware/CleverSole/ – danach nur neu hochladen.", {})],
    [("Pilotdaten/: ", {"bold": True}), ("eigene Logger-Aufnahmen; daraus lernt der Konverter die Wertebereiche.", {})],
], size=15, punkte=True, abstand=10)
N(s, "representative_dataset: Der Konverter sieht echte Fenster und legt daraus fest, welcher Zahlenbereich auf -128 bis 127 abgebildet wird.")

# 14 ------------------------------------------------------------ Dateien
s = d.folie("Was im Firmware-Ordner liegt")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Datei", "Inhalt", "Von Hand ändern?"],
    ["CleverSole.ino", "Hauptprogramm: Sensor, Kalibrierung, Netz, Abstimmung, Bluetooth, Schlaf", "ja (Pins, TESTMODUS)"],
    ["modell.h", "bindet das Modell ein, Einbauvorgabe (Chip oben, X zu den Zehen)", "selten"],
    ["netz_int8.h", "eigene int8-Rechenfunktionen für das Netz", "nein"],
    ["modell_netz.h", "Gewichte für netz_int8.h", "nein – erzeugt"],
    ["modell_sohle.h", "Kopie der .tflite (nicht ausgeführt) und Selbsttest-Sollwerte", "nein – erzeugt"],
    ["referenzwerte.h", "Schwellen der zweiten Stufe (Aufprall, Lage, Ruhe)", "ja, nach Sohlen-Messungen"],
    ["ANLEITUNG.md", "diese Anleitung ausführlich", "–"],
], [2.6, 6.9, 2.8], size=14, h_zeile=0.56, zentriert_ab=3)
N(s, "Erzeugte Dateien nie von Hand ändern, sondern mit dem Exportskript neu erzeugen.")

# 15 ------------------------------------------------------------ Fehlersuche
s = d.folie("Wenn etwas nicht funktioniert")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Symptom", "Ursache", "Abhilfe"],
    ["Serieller Monitor bleibt leer", "USB CDC On Boot aus", "Werkzeuge → USB CDC On Boot: Enabled"],
    ["IMU nicht gefunden", "Verdrahtung, Adresse", "SDA/SCL prüfen, AD0 an GND"],
    ["Selbsttest FALSCH", "modell_netz.h passt nicht zu modell_sohle.h", "beide mit dem Exportskript neu erzeugen"],
    ["p bleibt minutenlang gleich", "alte Firmware mit TFLite Micro", "neueste Firmware, EIGENE_KERNE 1"],
    ["Wacht nicht mehr auf", "INT nicht auf GPIO0–7", "INT an D1 (GPIO1) legen"],
    ["Keine Meldungen in der App", "Benachrichtigung aus / Classic statt LE", "FFF1/FFF2 Pfeile antippen; Bluetooth LE wählen"],
    ["Viele Fehlalarme", "Modul verdreht oder locker", "Kalibrierungszeile prüfen (Schritt 3)"],
], [3.6, 4.2, 4.5], size=14, h_zeile=0.56, zentriert_ab=3)
N(s, "Die häufigsten Probleme aus dem Projekt.")

# 16 ------------------------------------------------------------ Fragen
s = d.folie("Fragen?")
T(s, 0.47, 2.3, 12.3, 2.0, [
    "Alle Dateien und die ausführliche Anleitung (firmware/CleverSole/ANLEITUNG.md):",
    [("github.com/Alyelb/ML-Modell-for-Fall-detection", {"bold": True})],
], size=20, color=GRAU, abstand=10)
N(s, "Danke.")

d.speichern(REPO / "praesentation" / "3_Anleitung_Modell_auf_den_Chip.pptx")
