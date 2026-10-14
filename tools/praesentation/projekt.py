"""Praesentation 2: das Projekt (ca. 20 min).

Erzaehlt den Weg: was ich gemacht habe, warum, was herauskam und welche
Entscheidung daraus folgte. Diagramme stehen gesammelt auf zwei Folien.
Zahlen aus den Laeufen vom 13./14.10.2026.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from thm_deck import (DUNKEL, GRAU, GRUEN, HELL, HELLGRAU, QUELLEN, REPO, ROT, WEISS, Deck)  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402

d = Deck()
T, N = d.text, d.notiz
ETAPPEN = 8


def etappe(nr, titel, gemacht, ergebnis, folgerung, rechts=None, notiz=""):
    """Eine Station des Weges: links drei Abschnitte, rechts ein Bild oder eine Notiz."""
    s = d.folie(titel)
    T(s, 10.75, 1.25, 2.0, 0.4, f"Etappe {nr} von {ETAPPEN}", size=13, color=GRAU, align=PP_ALIGN.RIGHT)
    breite = 7.4 if rechts else 12.3
    y = 1.95
    for kopf, inhalt in (("Was ich gemacht habe", gemacht), ("Was herauskam", ergebnis),
                         ("Was ich daraus entschieden habe", folgerung)):
        T(s, 0.47, y, breite, 0.35, [[(kopf, {"bold": True, "color": GRUEN})]], size=15)
        tb = T(s, 0.47, y + 0.38, breite, 1.15, inhalt, size=16, abstand=4)
        y += 1.62
    if rechts:
        rechts(s)
    N(s, notiz)
    return s


def kasten_rechts(zeilen, titel="Kurz"):
    def f(s):
        d.flaeche(s, 8.3, 1.95, 4.45, 3.1, fill=HELL)
        T(s, 8.55, 2.15, 4.0, 0.4, [[(titel, {"bold": True, "color": GRAU})]], size=15)
        T(s, 8.55, 2.65, 4.0, 2.4, zeilen, size=15, punkte=True, abstand=8)
    return f


# 1 ------------------------------------------------------------------ Titel
s = d.titelfolie([
    ("Sturzerkennung mit TinyML in einer sensorischen Einlegesohle", 18, True, DUNKEL),
    ("Studienprojekt 2 · Mechatronik (M.Sc.)", 12, False, GRAU),
    ("Aly Elbermawy", 12, True, DUNKEL),
    ("Betreuer: Prof. Dr. Sergej Kovalev", 11, False, GRAU),
    ("Partner: NEARBY (vormals Clever-Sole / TrackTech GmbH)", 11, False, GRAU)])
N(s, "Begrüßung. Ich erzähle den Weg des Projekts: was ich jeweils angenommen habe, was die Versuche gezeigt haben "
     "und warum ich am Ende bei diesem Modell und dieser Firmware gelandet bin.")

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
N(s, "Zielgruppe sind ältere Menschen und Menschen mit Demenz. Die Rechnung läuft komplett auf dem Chip.")

# 3 ------------------------------------------------------------------ Weg
s = d.folie("Der Weg in acht Etappen")
stationen = ["Hüfte", "andere\nDatensätze", "Fehlalarme", "Bein + Fuß", "links ≠ rechts",
             "eigene\nHardware", "die Sohle\nselbst", "auf den Chip"]
x0, x1, y = 1.1, 12.2, 3.0
d.linie(s, x0, y, x1, y, farbe=HELLGRAU, breite=2.5)
for i, k in enumerate(stationen):
    xi = x0 + i * (x1 - x0) / (len(stationen) - 1)
    d.flaeche(s, xi - 0.16, y - 0.16, 0.32, 0.32, fill=GRUEN if i == 7 else WEISS, line=GRUEN, form=9)
    T(s, xi - 0.3, y - 0.75, 0.6, 0.4, str(i + 1), size=16, bold=True, color=GRUEN, align=PP_ALIGN.CENTER)
    T(s, xi - 0.85, y + 0.35, 1.7, 0.8, k.split("\n"), size=14, color=DUNKEL, align=PP_ALIGN.CENTER, abstand=0)
T(s, 0.47, 4.75, 12.3, 1.9, [
    "Fast jede Etappe begann mit einer naheliegenden Annahme – und mehrere davon waren falsch.",
    "Ich zeige jeweils, was ich gemacht habe, was herauskam und welche Entscheidung daraus folgte. "
    "Die wichtigsten Zahlen stehen danach gesammelt auf zwei Folien.",
], size=17, abstand=10)
N(s, "Überblick über den Weg.")

# 4 ------------------------------------------------------------------ Prototyp
s = d.folie("Der Prototyp: ein Mikrocontroller und ein Bewegungssensor")
d.bild(s, QUELLEN / "foto_platine.jpg", 0.47, 1.95, h=2.7)
d.bild(s, QUELLEN / "foto_platine_unten.jpg", 3.95, 1.95, h=2.7)
d.bild(s, QUELLEN / "einbaulage.png", 7.55, 1.95, h=2.7)
T(s, 0.47, 5.0, 12.3, 1.8, [
    [("Seeed XIAO ESP32-C6 ", {"bold": True}), ("mit Bluetooth, dazu ein IMU-Modul (Beschleunigung + Drehrate) und ein Akku.", {})],
    [("Messung: ", {"bold": True}), ("100 Hz, ±16 g, ±2000 °/s. Das Modell sieht 2-Sekunden-Fenster mit 50 Hz.", {})],
    [("Eigene Logger-Firmware: ", {"bold": True}), ("Aufnahmen per Smartphone starten und stoppen, damit Daten genau dieser Hardware entstehen.", {})],
], size=16, punkte=True, abstand=6)
N(s, "Die Hardware hat der Partner vorgegeben. Den Logger habe ich geschrieben, um eigene Daten aufzunehmen.")

# 5 ------------------------------------------------------------------ Etappe 1
etappe(1, "Etappe 1: Zuerst ein Modell, das an der Hüfte funktioniert",
       "Auf SisFall (Hüfte, 38 Personen) drei Verfahren verglichen: Grenzwert auf die Beschleunigung, "
       "Random Forest mit 18 Kennwerten, 1D-CNN auf dem ganzen Signal.",
       "Der Grenzwert findet fast alle Stürze, meldet aber auch jeden harten Schritt. Das CNN erkennt "
       "99 % der Stürze bei 99 % richtig erkanntem Alltag – an fremden Testpersonen.",
       "Das CNN wird das Basismodell. Es bewertet den Verlauf (Bewegung, Aufprall, Ruhe), "
       "nicht nur die Spitze. Klein genug für den Chip: 61 601 Gewichte.",
       kasten_rechts(["Grenzwert: einfach, aber viele Fehlalarme",
                      "Random Forest: gut, aber Reihenfolge geht verloren",
                      "CNN: lernt das Muster selbst"], "Drei Ansätze"),
       "Ab hier werden Minimum und Maximum nur noch als zweite Stufe benutzt, nicht zur Entscheidung.")

# 6 ------------------------------------------------------------------ Etappe 2
etappe(2, "Etappe 2: Funktioniert das Modell auch auf anderen Daten?",
       "Das Hüftmodell ohne Anpassung auf KFall, UMAFall und FallAllD angewendet, danach kurz nachtrainiert. "
       "Zwei Kontrollversuche: Messbereich künstlich begrenzt, Abtastraten verglichen.",
       "KFall funktioniert sofort, die anderen kaum. Meine Vermutungen – zu kleiner Messbereich, zu niedrige "
       "Abtastrate – waren beide falsch: begrenzt auf ±2 g bleibt die Hüfte bei 98 %, FallAllD scheitert trotz 238 Hz.",
       "Ein kurzes Nachtraining auf Daten der neuen Quelle reicht meist. Am Knöchel reicht es nicht – dort fehlen "
       "passende Sturzdaten. Die echte Ursache fand ich erst in Etappe 5.",
       kasten_rechts(["KFall: ohne Anpassung 99,5 %", "UMAFall Taille: 46 → 94 % nach Nachtraining",
                      "FallAllD: 11 → 76 %", "UMAFall Knöchel: bleibt bei 25 %"], "Erkannte Stürze"),
       "Die Kontrollversuche sind wichtig: Ohne sie hätte ich die falsche Ursache in den Bericht geschrieben.")

# 7 ------------------------------------------------------------------ Etappe 3
etappe(3, "Etappe 3: Am Knöchel sind die Fehlalarme das Problem",
       "Das Modell auf reinen Alltagsdaten am Knöchel laufen lassen und drei Gegenmittel getestet: "
       "höhere Schwelle, Abstimmung über mehrere Fenster (3 von 5), schwierige Alltagsbeispiele stärker gewichten.",
       "Jeder Fersenaufsatz sieht für das Modell wie ein Aufprall aus – mit voller Sicherheit, eine höhere "
       "Schwelle hilft kaum. Die Abstimmung senkt Fehlalarme um 70 %, kostet aber 40 % der Stürze. "
       "Das Umgewichten kostet ebenfalls Stürze.",
       "Kein Trick ersetzt passende Daten. Ich brauche Stürze vom Bein und Alltag vom Fuß. "
       "Die 3-von-5-Regel bleibt trotzdem in der Firmware, als Glättung.",
       kasten_rechts(["Fehlalarme ohne Anpassung: 137 je Stunde", "Joggen: jedes fünfte Fenster",
                      "Umgewichten: −6 Punkte Sensitivität"], "Am Knöchel"),
       "Alle Vergleiche fünffach kreuzvalidiert. Zwei frühere Einzelauswertungen hatten gegensätzliche Ergebnisse geliefert.")

# 8 ------------------------------------------------------------------ Etappe 4
etappe(4, "Etappe 4: Stürze vom Bein und Alltag vom Fuß kombinieren",
       "Neue Quellen gesucht: CAPPIMU misst dieselben Stürze an neun Körperstellen, auch am Schienbein. "
       "ImbalanSense und Smart-Insole messen in der Sohle, aber nur Alltag. Daraus eine Trainingskette gebaut.",
       "Beinstürze heben die Erkennung am Schienbein von 21 auf 83 %. Ohne Fußdaten steigen dafür die "
       "Fehlalarme an der Sohle auf mehrere hundert je Stunde. Mit Sohlen-Alltag sinken sie um über 90 % – "
       "ohne Stürze zu kosten.",
       "Training: Hüfte → Rücken → Schienbein-Stürze + Sohlen-Alltag. Smart-Insole bleibt draußen: "
       "kostet Sensitivität und ist nur akademisch nutzbar.",
       kasten_rechts(["SisFall → KFall", "→ CAPPIMU Schienbein (Stürze)", "→ ImbalanSense Sohle (Alltag)",
                      "→ Firmware-Modell B2r"], "Trainingskette"),
       "Die Zahlen dazu stehen auf der Ergebnisfolie.")

# 9 ------------------------------------------------------------------ Etappe 5
etappe(5, "Etappe 5: Die Überraschung – links und rechts sind verschieden",
       "Auf CAPPIMU verglichen, wie gut das Modell an jeder Körperstelle erkennt. Erwartet hatte ich: "
       "je weiter vom Rumpf, desto schlechter.",
       "Stattdessen unterscheiden sich linke und rechte Körperseite bei denselben Stürzen bis Faktor neun. "
       "Spiegelt man die linke Seite rechnerisch, erreicht sie die Werte der rechten. Ursache ist die Lage der "
       "Sensorachsen, nicht die Position.",
       "Zwei Gegenmittel: Im Training jedes Fenster zusätzlich zufällig drehen und spiegeln, und in der Firmware "
       "die Einbaulage selbst bestimmen. Das erklärt rückblickend auch Etappe 2.",
       kasten_rechts(["Oberarm links 5 %, rechts 47 %", "links gespiegelt: 54 %",
                      "gedreht ohne Augmentierung: 58 %", "gedreht mit Augmentierung: 76 %"], "Erkannte Stürze"),
       "Das war der wichtigste Befund des Projekts. Das CNN wertet jede Achse einzeln aus und ist deshalb nicht drehunempfindlich.")

# 10 ------------------------------------------------------------------ Etappe 6
etappe(6, "Etappe 6: Test auf der eigenen Hardware",
       "Mit dem Logger an Hüfte und beiden Knöcheln aufgenommen: vier Sturzarten auf einer Matte, dazu Gehen, Joggen, "
       "Treppen, kräftiges Hinsetzen, Springen, Aufheben. Ausgewertet wie auf dem Chip (alle 0,2 s, 3 von 5).",
       "Roh erkennt das Hüftmodell an der eigenen Hüfte nur 2 von 22 Stürzen. Allein die Achsen wie in SisFall "
       "auszurichten bringt 15 von 22. Das fertige Modell findet nach Ausrichtung über die Schwerkraft "
       "alle 67 Stürze.",
       "Die Firmware bestimmt die Lage nach jedem Aufwachen selbst: Schwerkraft im Stand gibt „oben“, "
       "der X-Pfeil gibt „vorn“.",
       kasten_rechts(["eine Person, Stürze auf Matte", "6–9 Minuten schwieriger Alltag je Stelle",
                      "Fehlalarme v. a. beim Hinsetzen", "keine Rate je Stunde ableitbar"], "Einschränkungen"),
       "Ehrlich: An der Hüfte gab es viele Fehlalarme. Die Hüfte ist aber nicht die Zielposition.")

# 11 ------------------------------------------------------------------ Etappe 7
etappe(7, "Etappe 7: Die Sohle selbst",
       "Die Partnerdaten der bisherigen Sohle analysiert und zum Schluss eigene Aufnahmen in beiden Sohlen gemacht: "
       "vier Sturzarten, Gehen, Joggen, Springen.",
       "Die Partnerdaten (10 Hz, ±2 g, ohne Gyroskop) schneiden schon beim Gehen ab. In den eigenen Aufnahmen "
       "liegt kein Sturz über der stärksten Alltagsbewegung: Joggen und Springen erreichen 6,5–7,7 g, "
       "die Stürze 2,3–5,7 g.",
       "An der Sohle kann ein Grenzwert grundsätzlich nicht funktionieren – der Verlauf entscheidet. "
       "Für den Sensor heißt das: ±16 g, 100 Hz, mit Gyroskop.",
       kasten_rechts(["Stürze auf die Knie: harter Boden", "übrige Stürze: weiche Unterlage",
                      "mit dem Modell noch nicht ausgewertet"], "Zu beachten"),
       "Normales Gehen erreicht an der Sohle über 4 g, die bisherige Sohle misst höchstens 3,5 g.")

# 12 ------------------------------------------------------------------ Etappe 8
etappe(8, "Etappe 8: Das Modell auf den Chip bringen",
       "Modell in ganze Zahlen umgerechnet (int8, 77 KB), Firmware mit Schlafmodus, Schrittzähler, "
       "Selbstkalibrierung, 3-von-5-Regel, Lageprüfung nach dem Alarm und Bluetooth geschrieben.",
       "Auf dem Chip kam zuerst immer derselbe Wert heraus (0,47) – egal, was der Sensor maß. Am PC rechnete "
       "dieselbe Datei richtig. Die Bibliothek TFLite Micro rechnete auf dem ESP32-C6 falsch.",
       "Ich rechne das Netz jetzt mit eigenen int8-Funktionen, Schicht für Schicht am PC gegen TFLite geprüft. "
       "Ein Selbsttest beim Start zeigt sofort, ob der Chip richtig rechnet.",
       kasten_rechts(["Sensor → 2-s-Fenster", "Lage ausgleichen", "CNN (int8)", "3 von 5 → Lage + Ruhe prüfen",
                      "Bluetooth an die App"], "Kette auf dem Chip"),
       "Lehre: Ein Modell, das am PC stimmt, ist auf dem Chip noch nicht bewiesen. Deshalb der Selbsttest.")

# 13 ------------------------------------------------------------------ Ergebnisse 1
s = d.folie("Ergebnisse I: was die Daten von Bein und Fuß bewirken")
d.diagramm(s, 0.47, 1.85, 6.1, 4.25, ["nur Hüfte", "+ Rücken", "+ Beinstürze", "+ Sohlen-Alltag\n(B2r)"],
           [("Sensitivität am Schienbein", (30.2, 21.5, 84.3, 84.0))], [GRUEN],
           titel="Erkannte Stürze am Schienbein", max_=100, fmt='0"%"', legende=False)
d.diagramm(s, 6.75, 1.85, 6.0, 4.25, ["nur Hüfte", "+ Beinstürze", "+ Sohlen-Alltag\n(B2r)"],
           [("Fehlalarme je Stunde (Smart-Insole)", (101, 310, 28))], [ROT],
           titel="Fehlalarme je Stunde an der Sohle", max_=360, fmt='0', legende=False)
T(s, 0.47, 6.25, 12.3, 0.6, "Fünffach kreuzvalidiert, fremde Testpersonen; Smart-Insole war nie im Training.",
  size=14, color=GRAU)
N(s, "Links: Ohne Beinstürze erkennt das Modell am Schienbein nur 21–30 %, mit Beinstürzen 84 %. "
     "Rechts: Die Beinstürze treiben die Fehlalarme an der Sohle hoch, der Sohlen-Alltag holt sie wieder herunter. "
     "Werte der beiden letzten Säulen aus dem augmentierten Lauf.")

# 14 ------------------------------------------------------------------ Ergebnisse 2
s = d.folie("Ergebnisse II: Achsenlage und die Sohle selbst")
d.diagramm(s, 0.47, 1.85, 6.1, 4.25, ["Oberarm", "Handgelenk", "Schienbein"],
           [("links", (5.1, 13.5, 12.2)), ("links gespiegelt", (53.8, 57.5, 48.3)), ("rechts", (47.3, 50.9, 48.3))],
           [HELLGRAU, GRUEN, GRAU], titel="Erkannte Stürze je Körperseite", max_=70, fmt='0"%"')
d.diagramm(s, 6.75, 1.85, 6.0, 4.25, ["stärkste\nAlltagsbew.", "seitlich", "rückwärts", "Knie", "vorwärts"],
           [("rechte Sohle", (6.51, 5.35, 3.98, 3.47, 2.30)), ("linke Sohle", (7.68, 4.11, 4.65, 5.69, 3.53))],
           [GRAU, GRUEN], titel="Höchste Beschleunigung an der Sohle", max_=9, fmt='0.0" g"')
T(s, 0.47, 6.25, 12.3, 0.6, "Links: CAPPIMU, dieselben Stürze an beiden Körperseiten. Rechts: eigene Aufnahmen in beiden Sohlen.",
  size=14, color=GRAU)
N(s, "Links der Spiegeltest aus Etappe 5, rechts die eigenen Sohlenaufnahmen aus Etappe 7.")

# 15 ------------------------------------------------------------------ Gelernt
s = d.folie("Was ich aus dem Projekt mitnehme")
T(s, 0.47, 1.95, 12.3, 4.8, [
    [("Annahmen prüfen, bevor man sie aufschreibt. ", {"bold": True}),
     ("Messbereich, Abtastrate, Position – alles naheliegend, alles durch einen Kontrollversuch widerlegt.", {})],
    [("Einzelne Auswertungen täuschen. ", {"bold": True}),
     ("Bei seltenen Stürzen hat erst die fünffache Kreuzvalidierung belastbare Antworten geliefert.", {})],
    [("Passende Daten schlagen jeden Trick. ", {"bold": True}),
     ("Schwelle, Abstimmung, Umgewichten halfen wenig; Daten von Bein und Fuß halfen viel.", {})],
    [("Die Einbaulage gehört zum Modell. ", {"bold": True}),
     ("Ohne sie scheitert selbst ein gutes Modell an der eigenen Hüfte.", {})],
    [("Früh auf der echten Hardware testen. ", {"bold": True}),
     ("Der Fehler auf dem Chip war nur dort sichtbar.", {})],
], size=18, punkte=True, abstand=14)
N(s, "Die fünf Punkte, die ich beim nächsten Projekt von Anfang an so machen würde.")

# 16 ------------------------------------------------------------------ Empfehlungen
s = d.folie("Was ich für die Sohle empfehle")
T(s, 0.47, 1.95, 7.6, 4.9, [
    [("Sensor: ", {"bold": True}), ("6 Achsen, mindestens ±16 g, 100 Hz. Mit ±2 g und 10 Hz ist an der Sohle kein Sturz messbar.", {})],
    [("Einbaulage festlegen ", {"bold": True}), ("und in der Firmware ausgleichen – das kostet nichts und macht den größten Unterschied.", {})],
    [("Stürze an der Sohle aufnehmen: ", {"bold": True}), ("mehrere Personen, harter Boden, beide Füße. Erst dann ist das Modell an der Sohle validiert.", {})],
    [("Lizenzen prüfen: ", {"bold": True}), ("Smart-Insole und MobiAct sind nur akademisch nutzbar. Das kommerzielle Modell verzichtet darauf.", {})],
], size=17, punkte=True, abstand=14)
d.flaeche(s, 8.5, 1.95, 4.25, 3.3, fill=HELL)
T(s, 8.75, 2.15, 3.8, 0.4, [[("Noch offen", {"bold": True, "color": GRAU})]], size=16)
T(s, 8.75, 2.65, 3.8, 2.5, ["Fehlalarme im Dauerbetrieb über Stunden", "Energiebedarf mit Schlafmodus",
                            "Zwei Sohlen gemeinsam auswerten", "Ältere Menschen als Testpersonen"],
  size=15, punkte=True, abstand=8)
N(s, "Das kommerzielle Modell wird mit allen Datensätzen außer Smart-Insole und MobiAct trainiert; der Lauf ist angestoßen.")

# 17 ------------------------------------------------------------------ Fazit
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

# 18 ------------------------------------------------------------------ Danke
s = d.folie("Vielen Dank – Fragen?")
d.bild(s, QUELLEN / "foto_platine.jpg", 0.47, 1.95, h=3.6)
T(s, 6.0, 2.4, 6.75, 2.5, [[("Aly Elbermawy", {"bold": True})], "aly.elbermawy@m.thm.de",
                           "Studienprojekt 2 · THM Campus Friedberg"], size=18, abstand=8)
N(s, "Danke.")

d.speichern(REPO / "praesentation" / "2_Projekt_Sturzerkennung.pptx")
