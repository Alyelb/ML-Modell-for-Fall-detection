"""Praesentation 2: das Projekt (ca. 20 min). Zahlen aus den Laeufen vom 13./14.10.2026."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from thm_deck import (DUNKEL, GRAU, GRUEN, HELL, HELLGRAU, QUELLEN, REPO, ROT, WEISS, Deck)  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402

d = Deck()
T, N = d.text, d.notiz

# 1 ------------------------------------------------------------------ Titel
s = d.titelfolie([
    ("Sturzerkennung mit TinyML in einer sensorischen Einlegesohle", 18, True, DUNKEL),
    ("Studienprojekt 2 · Mechatronik (M.Sc.)", 12, False, GRAU),
    ("Aly Elbermawy", 12, True, DUNKEL),
    ("Betreuer: Prof. Dr. Sergej Kovalev", 11, False, GRAU),
    ("Partner: NEARBY (vormals Clever-Sole / TrackTech GmbH)", 11, False, GRAU)])
N(s, "Begrüßung. Ich zeige, wie weit man mit einer Sturzerkennung kommt, die vollständig in der Sohle läuft, "
     "was dabei funktioniert hat und was nicht.")

# 2 ------------------------------------------------------------ Worum es geht
s = d.folie("Ein Sturz soll direkt in der Sohle erkannt werden")
T(s, 0.47, 1.95, 7.2, 4.6, [
    "Nach einem Sturz zählt vor allem, wie lange jemand unbemerkt liegen bleibt. "
    "Gerade bei älteren oder dementen Menschen hilft kein Notrufknopf, den man selbst drücken muss.",
    "Die Idee: Die Sohle erkennt den Sturz selbst – mit einem Bewegungssensor und einem kleinen "
    "neuronalen Netz auf dem Mikrocontroller, ohne Smartphone und ohne Cloud.",
    [("Meine Leitfrage: ", {"bold": True}),
     ("Lässt sich ein Modell, das an der Hüfte gelernt hat, auf den Fuß übertragen – und was braucht es dafür?", {})],
], size=18, abstand=14)
d.bild(s, QUELLEN / "foto_platine.jpg", 8.2, 1.95, w=4.55)
d.bildunterschrift(s, 8.2, 5.5, 4.55, "Prototyp: XIAO ESP32-C6, IMU-Modul, Akku")
N(s, "Zielgruppe sind ältere Menschen und Menschen mit Demenz. Die Rechnung läuft komplett auf dem Chip "
     "in der Sohle. Die Leitfrage zieht sich durch den ganzen Vortrag.")

# 3 ------------------------------------------------------------------ Vorgehen
s = d.folie("So bin ich vorgegangen")
stationen = [("Rumpf", "Modell an der Hüfte\nlernen (SisFall)"),
             ("Transfer", "auf andere Datensätze\nübertragen"),
             ("Bein und Fuß", "Stürze vom Bein,\nAlltag von der Sohle"),
             ("Eigene Hardware", "Pilotaufnahmen\nHüfte, Knöchel, Sohle"),
             ("Firmware", "Modell auf dem\nESP32-C6 in der Sohle")]
x0, x1, y = 1.75, 11.55, 3.15
d.linie(s, x0, y, x1, y, farbe=HELLGRAU, breite=2.5)
for i, (k, u) in enumerate(stationen):
    xi = x0 + i * (x1 - x0) / (len(stationen) - 1)
    d.flaeche(s, xi - 0.17, y - 0.17, 0.34, 0.34, fill=GRUEN if i == 4 else WEISS,
              line=GRUEN, form=9)  # 9 = Ellipse
    T(s, xi - 1.2, y - 0.85, 2.4, 0.4, [[(k, {"bold": True})]], size=17, align=PP_ALIGN.CENTER)
    T(s, xi - 1.2, y + 0.35, 2.4, 0.9, u.split("\n"), size=14, color=GRAU, align=PP_ALIGN.CENTER, abstand=0)
T(s, 0.47, 5.0, 12.3, 1.4, [
    "Jeder Schritt hat eine Annahme geprüft. Mehrere naheliegende Annahmen haben sich dabei als falsch "
    "herausgestellt – davon handelt der größte Teil des Vortrags."], size=17, color=DUNKEL)
N(s, "Kurzer Überblick über den Weg. Ich gehe die Stationen der Reihe nach durch.")

# 4 ------------------------------------------------------------------ Prototyp
s = d.folie("Der Prototyp: ein Mikrocontroller und ein Bewegungssensor")
d.bild(s, QUELLEN / "foto_platine.jpg", 0.47, 1.95, h=2.7)
d.bild(s, QUELLEN / "foto_platine_unten.jpg", 3.95, 1.95, h=2.7)
d.bild(s, QUELLEN / "einbaulage.png", 7.55, 1.95, h=2.7)
T(s, 0.47, 5.0, 12.3, 1.8, [
    [("Seeed XIAO ESP32-C6 ", {"bold": True}), ("mit Bluetooth, dazu ein IMU-Modul (Beschleunigung + Drehrate) und ein Akku.", {})],
    [("Messung: ", {"bold": True}), ("100 Hz, ±16 g, ±2000 °/s. Das Modell sieht 2-Sekunden-Fenster mit 50 Hz.", {})],
    [("Einbau in der Sohle: ", {"bold": True}), ("IMU-Modul flach unter der Ferse, Chip oben, X-Pfeil zu den Zehen.", {})],
], size=16, punkte=True, abstand=6)
N(s, "Eigene Logger-Firmware, damit Daten von genau dieser Hardware entstehen. Lage von XIAO und Akku ist egal, "
     "entscheidend ist das IMU-Modul. Die Firmware kalibriert die genaue Lage selbst, dazu später mehr.")

# 5 ------------------------------------------------------------------ Daten
s = d.folie("Stürze gibt es in den Datensätzen überall – nur nicht an der Sohle")
d.bild(s, QUELLEN / "koerper.png", 0.47, 1.85, h=4.95)
T(s, 7.4, 1.95, 5.35, 4.8, [
    [("SisFall", {"bold": True}), (" – Hüfte, Grundlage des Modells", {})],
    [("KFall", {"bold": True}), (" – Rücken, Zwischenschritt", {})],
    [("UMAFall, FallAllD", {"bold": True}), (" – Prüfung der Übertragbarkeit", {})],
    [("CAPPIMU", {"bold": True}), (" – dieselben Stürze an neun Körperstellen, auch am Schienbein", {})],
    [("ImbalanSense, Smart-Insole", {"bold": True}), (" – Sohle, aber nur Alltag", {})],
    [("Eigene Aufnahmen", {"bold": True}), (" – Hüfte, Knöchel, beide Sohlen", {})],
], size=16, punkte=True, abstand=8)
N(s, "Kein öffentlicher Datensatz enthält Stürze an der Sohle. Das Modell muss also Stürze vom Bein mit "
     "Alltagsbewegungen vom Fuß kombinieren. Smart-Insole und MobiAct sind nur für nicht-kommerzielle Zwecke freigegeben.")

# 6 --------------------------------------------------- Drei Ansaetze
s = d.folie("Ein Grenzwert reicht nicht – das neuronale Netz bewertet den ganzen Verlauf")
d.tabelle(s, 0.47, 1.95, 7.3, [
    ["Ansatz (SisFall, Hüfte)", "Sensitivität", "Spezifität", "Fehlalarm-Fenster"],
    ["Grenzwert auf |a| (2,8 g)", "96,7 %", "82,9 %", "2074"],
    ["Random Forest (18 Merkmale)", "92,7 %", "99,6 %", "48"],
    ["1D-CNN (ganzes 2-s-Signal)", "99,0 %", "99,3 %", "82"],
], [3.1, 1.35, 1.35, 1.5], size=15, h_zeile=0.5, hervor=(3,))
T(s, 0.47, 4.25, 7.3, 2.5, [
    [("Grenzwert: ", {"bold": True}), ("schaut nur auf die Spitze – jeder harte Schritt löst aus.", {})],
    [("Random Forest: ", {"bold": True}), ("schaut auf Kennwerte wie Streuung oder Maximum, aber nicht auf die Reihenfolge.", {})],
    [("CNN: ", {"bold": True}), ("erkennt das Muster Bewegung → Aufprall → Ruhe im zeitlichen Ablauf.", {})],
], size=16, punkte=True, abstand=8)
T(s, 8.2, 1.95, 4.55, 4.8, [
    [("Warum nicht einfach Minimum und Maximum?", {"bold": True, "color": GRUEN})],
    "Weil sich Stürze und Alltag in den Grenzwerten überschneiden. Ein Grenzwert, der alle Stürze findet, "
    "meldet auch Treppen und Joggen.",
    "Am Fuß ist das noch deutlicher – siehe nächste Folie.",
], size=16, abstand=10)
N(s, "Hier die Erklärung, warum nicht nach Minimum und Maximum bewertet wird. Der Grenzwert findet fast alle Stürze, "
     "erzeugt aber 25-mal mehr Fehlalarm-Fenster als der Random Forest. Das CNN schaut auf alle 100 × 6 Werte "
     "des Fensters und damit auf die Form, nicht nur auf die Höhe. Gyroskop-Merkmale tragen im Random Forest 62 % "
     "der Wichtigkeit.")

# 7 --------------------------------------------------- Spitzen am Bein
s = d.folie("Am Bein ist der Alltag heftiger als der Sturz")
d.diagramm(s, 0.47, 1.85, 8.0, 4.9,
           ["Kopf", "Brust", "Hosentasche", "Schienbein\nrechts", "Schienbein\nlinks"],
           [("Sturz: typische Spitze (Median)", (2.85, 5.01, 4.32, 3.0, 2.9)),
            ("Alltag: seltene Spitze (99. Perzentil)", (2.22, 5.99, 10.41, 10.23, 9.89))],
           [GRUEN, GRAU], max_=12, fmt='0.0" g"', size=13)
T(s, 8.85, 1.95, 3.9, 4.8, [
    "Am Kopf liegt der Sturz noch über dem Alltag. Je weiter unten der Sensor sitzt, desto stärker kippt das Verhältnis.",
    "Am Schienbein erreicht der Alltag dreimal so hohe Spitzen wie ein typischer Sturz.",
    [("Folge: ", {"bold": True}), ("Am Fuß braucht es Daten vom Fuß und ein Modell, das den Verlauf bewertet.", {})],
], size=16, abstand=12)
N(s, "CAPPIMU, dieselben Stürze gleichzeitig an mehreren Positionen, rund 31 Stunden Alltag. An der Sohle "
     "(Smart-Insole, nur Alltag) liegt das 99. Perzentil bei 8 g.")

# 8 --------------------------------------------------- Transfer
s = d.folie("Ein Modell von der Hüfte überträgt sich nicht von selbst")
d.diagramm(s, 0.47, 1.85, 7.6, 4.9, ["KFall\nRücken", "UMAFall\nTaille", "FallAllD\nTaille", "UMAFall\nKnöchel"],
           [("ohne Anpassung", (99.5, 45.8, 11.3, 25.0)), ("nach Nachtraining", (100.0, 93.8, 75.8, 25.0))],
           [GRAU, GRUEN], max_=110, fmt='0"%"')
T(s, 8.45, 1.95, 4.3, 4.8, [
    [("Sensitivität", {"bold": True, "color": GRUEN})],
    "Ähnliche Hardware (KFall) funktioniert sofort. Andere Datensätze brauchen ein kurzes Nachtraining.",
    [("Am Knöchel hilft das nicht. ", {"bold": True}), ("Hier fehlen schlicht passende Sturzdaten.", {})],
    [("Messbereich? ", {"bold": True}), ("Kein Grund: auf ±2 g begrenzt bleibt die Hüfte bei 98 %.", {})],
], size=16, abstand=10)
N(s, "Jeweils subjektunabhängig getestet. Der Messbereich ist an der Hüfte kein Problem; an der Sohle sieht das "
     "anders aus, dazu später.")

# 9 --------------------------------------------------- Achsenlage
s = d.folie("Links und rechts: dieselben Stürze, völlig andere Ergebnisse")
d.diagramm(s, 0.47, 1.85, 7.6, 4.9, ["Oberarm", "Handgelenk", "Schienbein"],
           [("linke Seite", (5.1, 13.5, 12.2)), ("linke Seite, gespiegelt", (53.8, 57.5, 48.3)),
            ("rechte Seite", (47.3, 50.9, 48.3))],
           [HELLGRAU, GRUEN, GRAU], max_=70, fmt='0"%"')
T(s, 8.45, 1.95, 4.3, 4.8, [
    "Das Modell kennt nur die Lage des Sensors aus dem Training. Links sitzt der Sensor gespiegelt – "
    "und das Modell erkennt kaum etwas.",
    "Spiegelt man die Daten rechnerisch, erreicht links dieselben Werte wie rechts.",
    [("Die Einbaulage gehört zum Modell. ", {"bold": True}),
     ("Deshalb kalibriert die Firmware sie selbst und das Training dreht die Daten zufällig.", {})],
], size=16, abstand=10)
N(s, "Das war der überraschendste Befund. Zuerst sah es so aus, als sei die Position am Körper entscheidend. "
     "Tatsächlich war es die Achsenlage. Das CNN wertet jede Achse einzeln aus.")

# 10 --------------------------------------------------- Fussdaten
s = d.folie("Alltagsdaten von der Sohle senken die Fehlalarme drastisch")
kat = ["ohne Sohlendaten", "+ ImbalanSense", "+ ImbalanSense\n+ Smart-Insole"]
d.diagramm(s, 0.47, 1.85, 6.1, 4.25, kat, [("Fehlalarme je Stunde (Smart-Insole)", (310, 28, 11))], [ROT],
           titel="Fehlalarme je Stunde an der Sohle", max_=360, fmt='0', legende=False)
d.diagramm(s, 6.75, 1.85, 6.0, 4.25, kat, [("Sensitivität Schienbein", (84.3, 84.0, 82.1))], [GRUEN],
           titel="Sensitivität am Schienbein", max_=100, fmt='0.0"%"', legende=False)
T(s, 0.47, 6.25, 12.3, 0.6, [
    [("Sohlen-Alltag kostet keine Sensitivität. ", {"bold": True}),
     ("Smart-Insole senkt die Fehlalarme weiter, kostet aber 2 Punkte Sensitivität und ist nicht kommerziell nutzbar.", {})]],
    size=15)
N(s, "Fünffach kreuzvalidiert, alle drei Varianten augmentiert. Ohne Fußdaten lernt das Modell: kräftiger Impuls am Bein "
     "gleich Sturz, und jeder Fersenaufsatz ist so ein Impuls. Vorher, ohne Beinstürze, lag die Sensitivität am "
     "Schienbein bei 21 Prozent, mit Beinstürzen bei 83 Prozent. Smart-Insole war hier ein externer Test.")

# 11 --------------------------------------------------- Augmentierung
s = d.folie("Zufällige Drehungen im Training machen das Modell lagerobust")
d.diagramm(s, 0.47, 1.85, 8.1, 4.9, ["nur Hüfte", "+ Rücken", "Bein + Fuß\nohne Vortraining", "Bein + Fuß", "Bein + Fuß\naugmentiert"],
           [("Sensor wie im Test", (30.2, 21.1, 83.6, 84.1, 84.7)), ("Sensor zufällig gedreht", (27.1, 16.8, 51.6, 57.9, 75.8))],
           [GRAU, GRUEN], max_=100, fmt='0"%"')
T(s, 8.95, 1.95, 3.8, 4.8, [
    [("Sensitivität am Schienbein", {"bold": True, "color": GRUEN})],
    "Ohne Augmentierung fällt die Erkennung um ein Drittel, sobald der Sensor anders sitzt.",
    "Mit Augmentierung bleibt sie bei 76 % – ohne Verlust im Normalfall.",
    "Dieses Modell (B2r) läuft auf dem Chip.",
], size=16, abstand=10)
N(s, "Alle fünf Varianten aus demselben Lauf und denselben Falten. Augmentierung: jedes Trainingsfenster einmal "
     "zufällig gedreht, zur Hälfte gespiegelt. Gewinn gedreht +17,9 Prozentpunkte, in 5 von 5 Falten.")

# 12 --------------------------------------------------- Pilot
s = d.folie("Auf der eigenen Hardware: ohne Lagekorrektur geht wenig")
d.tabelle(s, 0.47, 1.95, 8.0, [
    ["Erkannte Stürze (Fehlalarme)", "Hüfte", "Knöchel rechts", "Knöchel links"],
    ["Hüftmodell, Rohdaten", "2/22 (12)", "16/23 (16)", "8/22 (39)"],
    ["B2r, Rohdaten", "18/22 (83)", "21/23 (21)", "17/22 (29)"],
    ["B2r, Lage aus der Schwerkraft ausgerichtet", "22/22 (65)", "23/23 (12)", "22/22 (17)"],
], [3.5, 1.5, 1.5, 1.5], size=15, h_zeile=0.55, hervor=(3,))
T(s, 0.47, 4.4, 8.0, 2.3, [
    "Eine Person, simulierte Stürze auf einer Matte, 6–9 Minuten gezielt schwieriger Alltag je Position.",
    "Die Fehlalarme stammen fast nur vom Hinsetzen und Aufheben. Eine Rate je Stunde lässt sich daraus nicht ableiten.",
], size=14, color=GRAU, abstand=8)
T(s, 8.85, 1.95, 3.9, 4.8, [
    "Das Modell hat weder diese Hardware noch diese Person gesehen.",
    "Richtet man die Daten nur über die Schwerkraft aus, findet es alle 67 Stürze.",
    [("Genau das macht jetzt die Firmware nach jedem Aufwachen.", {"bold": True})],
], size=16, abstand=12)
N(s, "Betrieb wie auf dem Chip: alle 0,2 Sekunden eine Entscheidung, Alarm bei 3 von 5. Ein Sturz gilt als erkannt, "
     "wenn spätestens eine Sekunde nach dem Aufprall ein Alarm kommt. Ehrlich gesagt: viele Fehlalarme an der Hüfte, "
     "die Hüfte ist aber nicht die Zielposition.")

# 13 --------------------------------------------------- Sohle selbst
s = d.folie("An der Sohle ist ein Sturz nicht lauter als Joggen")
d.diagramm(s, 0.47, 1.85, 7.9, 4.9, ["stärkste\nAlltagsbewegung", "Sturz\nseitlich", "Sturz\nrückwärts", "Sturz\nauf die Knie", "Sturz\nvorwärts"],
           [("rechte Sohle", (6.51, 5.35, 3.98, 3.47, 2.30)), ("linke Sohle", (7.68, 4.11, 4.65, 5.69, 3.53))],
           [GRAU, GRUEN], max_=9, fmt='0.0" g"', size=13)
T(s, 8.75, 1.95, 4.0, 4.8, [
    [("Höchste Beschleunigung je Aufnahme", {"bold": True, "color": GRUEN})],
    "Eigene Aufnahmen in beiden Sohlen. Jeder Sturz liegt unter der stärksten Alltagsbewegung (Joggen, Springen).",
    "Ein Grenzwert kann an der Sohle grundsätzlich nicht trennen.",
    [("Die Partnerdaten ", {"bold": True}), ("(10 Hz, ±2 g, ohne Gyroskop) schneiden schon beim Gehen ab.", {})],
], size=16, abstand=10)
N(s, "Einschränkung: Die meisten Stürze gingen auf ein Sofa oder eine Matte, nur die Stürze auf die Knie auf harten "
     "Boden. Auch die liegen unter Joggen und Springen. Normales Gehen erreicht an der Sohle über 4 g, der Sensor "
     "der bisherigen Sohle ist bei rund 3,5 g am Ende.")

# 14 --------------------------------------------------- Firmware
s = d.folie("Was auf dem Chip in der Sohle läuft")
d.ablauf(s, 0.47, 2.0, 12.3, [("IMU", "100 Hz\n±16 g"), ("Fenster", "2 s, 50 Hz\n100 × 6"),
                              ("Lage", "selbst\nkalibriert"), ("CNN", "int8, 77 KB"),
                              ("3 von 5", "alle 0,2 s"), ("Prüfung", "Lage + Ruhe"), ("Bluetooth", "an die App")],
         h=1.35, hervor=(2, 3), size=17)
T(s, 0.47, 3.9, 6.0, 2.9, [
    [("Selbstkalibrierung", {"bold": True, "color": GRUEN})],
    "Im Stand zeigt die Schwerkraft nach oben, beim Gehen dreht der Fuß um die Querachse, "
    "die Schwungphase zeigt nach vorn. Daraus folgt die Drehung in den Trainingsrahmen.",
], size=17, abstand=8)
T(s, 6.8, 3.9, 5.95, 2.9, [
    [("Was ich dabei gelernt habe", {"bold": True, "color": GRUEN})],
    "Auf dem Chip kam zunächst immer 0,47 heraus, egal was der Sensor maß. Ursache waren Rechenschritte, "
    "die TFLite Micro auf dem ESP32-C6 falsch auswertet. Sie sind jetzt ins Modell eingerechnet, "
    "und ein Selbsttest beim Start prüft das Ergebnis.",
], size=17, abstand=8)
N(s, "Die Kette läuft vollständig auf dem ESP32-C6. Rechenlast etwa 5 Prozent. Nach einem Alarm schätzt die Firmware "
     "aus der Liegelage die Richtung (vorwärts, rückwärts, seitlich) und prüft Aufprall, Lageänderung und Ruhe als zweite Stufe. "
     "Der Fehler mit 0,47: BatchNorm erzeugte MUL/ADD-Operationen mit Broadcast. Gefaltet ist die Abweichung 3e-6.")

# 15 --------------------------------------------------- Empfehlungen
s = d.folie("Was ich für die Sohle empfehle")
T(s, 0.47, 1.95, 7.6, 4.9, [
    [("Sensor: ", {"bold": True}), ("6 Achsen, mindestens ±16 g, 100 Hz. Mit ±2 g und 10 Hz ist an der Sohle kein Sturz messbar.", {})],
    [("Einbaulage festlegen ", {"bold": True}), ("und in der Firmware selbst kalibrieren – das kostet nichts und macht den größten Unterschied.", {})],
    [("Stürze an der Sohle aufnehmen: ", {"bold": True}), ("mehrere Personen, harter Boden, beide Füße. Erst dann ist das Modell an der Sohle validiert.", {})],
    [("Lizenzen prüfen: ", {"bold": True}), ("Smart-Insole und MobiAct sind nur akademisch nutzbar. Das kommerzielle Modell verzichtet darauf.", {})],
], size=17, punkte=True, abstand=14)
d.flaeche(s, 8.5, 1.95, 4.25, 3.3, fill=HELL)
T(s, 8.75, 2.15, 3.8, 0.4, [[("Noch offen", {"bold": True, "color": GRAU})]], size=16)
T(s, 8.75, 2.65, 3.8, 2.5, [
    "Fehlalarme im Dauerbetrieb über Stunden",
    "Energiebedarf mit Schlafmodus",
    "Zwei Sohlen gemeinsam auswerten",
    "Ältere Menschen als Testpersonen",
], size=15, punkte=True, abstand=8)
N(s, "Die Empfehlungen ergeben sich direkt aus den Ergebnissen. Das kommerzielle Modell wird mit allen Datensätzen "
     "außer Smart-Insole und MobiAct trainiert; der Lauf ist angestoßen, das Ergebnis reiche ich nach.")

# 16 --------------------------------------------------- Fazit
s = d.folie("Fazit")
T(s, 0.47, 1.95, 12.3, 3.6, [
    [("Am Fuß ist nicht die Erkennung das Problem, sondern die Fehlalarme. ", {"bold": True}),
     ("Alltagsdaten von der Sohle senken sie um über 90 %.", {})],
    [("Die Einbaulage war die übersehene Fehlerquelle. ", {"bold": True}),
     ("Selbstkalibrierung und gedrehte Trainingsdaten lösen sie.", {})],
    [("Ein Grenzwert kann an der Sohle nicht funktionieren. ", {"bold": True}),
     ("Ein Sturz ist dort nicht stärker als Joggen – das CNN bewertet den Verlauf.", {})],
], size=19, punkte=True, abstand=18)
T(s, 0.47, 5.6, 12.3, 1.0, "Code, Notebooks, Firmware und Bericht: github.com/Alyelb/ML-Modell-for-Fall-detection",
  size=14, color=GRAU)
N(s, "Drei Kernaussagen. Danach Fragen.")

# 17 --------------------------------------------------- Danke
s = d.folie("Vielen Dank – Fragen?")
d.bild(s, QUELLEN / "foto_platine.jpg", 0.47, 1.95, h=3.6)
T(s, 6.0, 2.4, 6.75, 2.5, [
    [("Aly Elbermawy", {"bold": True})],
    "aly.elbermawy@m.thm.de",
    "Studienprojekt 2 · THM Campus Friedberg",
], size=18, abstand=8)
N(s, "Danke.")

d.speichern(REPO / "praesentation" / "2_Projekt_Sturzerkennung.pptx")
