"""Praesentation 1: Technik -- neuronale Netze kurz erklaert und was man erwarten kann."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from thm_deck import (DUNKEL, GRAU, GRUEN, HELL, HELLGRAU, LINIE, REPO, ROT, WEISS, Deck)  # noqa: E402
from pptx.chart.data import CategoryChartData  # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION  # noqa: E402
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

d = Deck()
T, N = d.text, d.notiz

# 1 ------------------------------------------------------------------ Titel
s = d.titelfolie([
    ("Wie ein neuronales Netz einen Sturz erkennt", 18, True, DUNKEL),
    ("Technischer Hintergrund zur Sturzerkennung in der Sohle", 12, False, GRAU),
    ("Aly Elbermawy", 12, True, DUNKEL),
    ("Studienprojekt 2 · THM Campus Friedberg", 11, False, GRAU)])
N(s, "Dieser Teil erklärt ohne Formeln, was im Modell passiert und welche Ergebnisse man realistisch erwarten kann.")

# 2 ------------------------------------------------------------ Was der Sensor sieht
s = d.folie("Das Modell sieht 600 Zahlen – zwei Sekunden Bewegung")
kanaele = ["Beschleunigung x", "Beschleunigung y", "Beschleunigung z", "Drehrate x", "Drehrate y", "Drehrate z"]
x0, y0, w, zh = 2.75, 2.05, 6.6, 0.48
for i, k in enumerate(kanaele):
    yi = y0 + i * (zh + 0.08)
    T(s, 0.47, yi + 0.1, 2.15, 0.3, k, size=14, color=GRAU, align=PP_ALIGN.RIGHT)
    d.flaeche(s, x0, yi, w, zh, fill=HELL)
    for j in range(1, 20):
        d.linie(s, x0 + j * w / 20, yi, x0 + j * w / 20, yi + zh, farbe=WEISS, breite=1)
d.flaeche(s, x0 + 9 * w / 20, y0, 2 * w / 20, 6 * (zh + 0.08) - 0.08, fill=None, line=GRUEN)
T(s, x0, y0 + 6 * (zh + 0.08) + 0.08, w, 0.35, "100 Zeitpunkte = 2 Sekunden (50 pro Sekunde)", size=14,
  color=GRAU, align=PP_ALIGN.CENTER)
T(s, 9.75, 2.05, 3.0, 4.6, [
    "Jede Spalte ist ein Moment, jede Zeile ein Messkanal.",
    "Alle 0,2 s rückt das Fenster weiter und das Modell entscheidet neu.",
    "Vorher wird jeder Kanal normiert – das Modell sieht die Form, nicht den absoluten Wert.",
], size=16, abstand=12)
N(s, "Der Sensor misst 100-mal pro Sekunde, das Modell bekommt 50 Werte pro Sekunde. Ein Fenster sind 100 × 6 = 600 "
     "Zahlen. Der grüne Rahmen zeigt ein Stück von 0,1 s, so groß ist ein Filter in der ersten Schicht.")

# 3 ------------------------------------------------------------ Drei Wege
s = d.folie("Drei Wege, aus Messwerten eine Entscheidung zu machen")
spalten = [
    ("Grenzwert", "Ist die Beschleunigung irgendwann größer als z. B. 2,8 g?",
     ["einfach, sofort verständlich", "kennt nur die Höhe der Spitze", "jeder harte Schritt löst aus"]),
    ("Random Forest", "Viele Entscheidungsbäume stimmen über 18 Kennwerte ab (Maximum, Streuung, …).",
     ["robust, gut erklärbar", "Kennwerte muss man vorgeben", "Reihenfolge der Ereignisse geht verloren"]),
    ("1D-CNN", "Ein neuronales Netz lernt selbst, welche Muster im Verlauf auf einen Sturz hinweisen.",
     ["bewertet den ganzen Verlauf", "braucht viele Beispieldaten", "Achsenlage muss stimmen"]),
]
for i, (k, satz, pkt) in enumerate(spalten):
    x = 0.47 + i * 4.2
    T(s, x, 2.1, 3.9, 0.5, [[(k, {"bold": True})]], size=20, color=GRUEN if i == 2 else DUNKEL)
    T(s, x, 2.7, 3.9, 1.3, satz, size=16)
    T(s, x, 3.85, 3.9, 2.4, pkt, size=15, punkte=True, color=GRAU, abstand=6)
N(s, "Alle drei habe ich auf denselben SisFall-Daten verglichen. Das CNN ist im Projekt das Modell auf dem Chip.")

# 4 ------------------------------------------------------------ Warum nicht Min/Max
s = d.folie("Warum nicht einfach Minimum und Maximum?")
schwellen = [1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8, 4.0]
se = [100.0, 99.9, 99.7, 99.2, 98.0, 96.9, 95.8, 94.1, 91.3, 88.7, 86.0, 81.8, 79.0, 74.7]
sp = [51.8, 62.9, 70.5, 75.3, 78.7, 81.1, 82.9, 85.0, 87.1, 89.3, 91.3, 93.1, 94.5, 95.9]
cd = CategoryChartData()
cd.categories = [f"{v:.1f}".replace(".", ",") for v in schwellen]
cd.add_series("Stürze erkannt (Sensitivität)", se)
cd.add_series("Alltag richtig erkannt (Spezifität)", sp)
ch = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(0.47), Inches(1.85), Inches(7.9), Inches(4.65), cd).chart
ch.font.size = Pt(13)
ch.font.color.rgb = GRAU
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.TOP
ch.legend.include_in_layout = False
va = ch.value_axis
va.minimum_scale, va.maximum_scale = 50, 100
va.major_gridlines.format.line.color.rgb = LINIE
va.format.line.fill.background()
va.tick_labels.number_format = '0"%"'
va.tick_labels.number_format_is_linked = False
for ser, farbe in zip(ch.plots[0].series, (GRUEN, GRAU)):
    ser.format.line.color.rgb = farbe
    ser.format.line.width = Pt(2.5)
    ser.marker.format.fill.solid()
    ser.marker.format.fill.fore_color.rgb = farbe
    ser.marker.format.line.color.rgb = farbe
    ser.smooth = False
T(s, 0.47, 6.5, 7.9, 0.35, "Grenzwert auf die Spitze von |a| in g (SisFall, Hüfte)", size=12, color=GRAU)
T(s, 8.75, 1.95, 4.0, 4.8, [
    "Jeder Grenzwert tauscht verpasste Stürze gegen Fehlalarme. Einen Punkt, an dem beides gut ist, gibt es nicht.",
    [("Das CNN liegt bei 99,0 % und 99,3 % ", {"bold": True}),
     ("– weit über dieser Kurve, weil es nicht nur die Spitze, sondern den Verlauf davor und danach bewertet.", {})],
    "An der Sohle sind Alltagsspitzen sogar höher als Sturzspitzen. Dort scheitert jeder Grenzwert.",
], size=16, abstand=12)
N(s, "Erinnerung aus dem Projekt: Die Daten werden nicht nach Minimum und Maximum bewertet. Die Kurve zeigt, warum. "
     "Bei 1,5 g findet der Grenzwert alle Stürze, hält aber fast jedes zweite Alltagsfenster für einen Sturz. "
     "Bei 4 g sind die Fehlalarme selten, dafür wird jeder vierte Sturz verpasst. Minimum und Maximum werden nur "
     "noch als zweite Stufe genutzt, um einen Alarm des CNN zu bestätigen (Aufprall, Lageänderung, Ruhe).")

# 5 ------------------------------------------------------------ Filter
s = d.folie("Ein Filter ist ein kleines Muster, das über das Signal gleitet")
n_box, bw = 20, 0.5
for i in range(n_box):
    d.flaeche(s, 0.8 + i * (bw + 0.08), 2.4, bw, 0.5, fill=HELL)
d.flaeche(s, 0.8 + 7 * (bw + 0.08) - 0.06, 2.3, 5 * (bw + 0.08) + 0.04, 0.7, fill=None, line=GRUEN)
d.linie(s, 0.8 + 9.5 * (bw + 0.08), 3.05, 0.8 + 9.5 * (bw + 0.08), 3.7, farbe=GRUEN, breite=1.75, pfeil=True)
T(s, 0.8 + 6 * (bw + 0.08), 3.75, 3.6, 0.6, "„passt hier gut“ → hoher Wert", size=15, color=GRUEN, align=PP_ALIGN.CENTER)
T(s, 0.8, 1.95, 11.5, 0.4, "Messwerte eines Kanals über die Zeit", size=13, color=GRAU)
T(s, 0.47, 4.6, 12.3, 2.2, [
    [("Erste Schicht: ", {"bold": True}), ("32 Filter über je 5 Zeitpunkte (0,1 s). Sie finden einfache Formen – einen steilen Anstieg, einen Stoß, eine Drehung.", {})],
    [("Weitere Schichten: ", {"bold": True}), ("setzen diese Formen zu größeren Mustern zusammen – zum Beispiel Drehung, dann Stoß, dann Ruhe.", {})],
    [("Gelernt, nicht programmiert: ", {"bold": True}), ("welche Muster wichtig sind, hat das Netz aus Tausenden Beispielen selbst bestimmt.", {})],
], size=16, punkte=True, abstand=10)
N(s, "1D-CNN heißt: Die Filter gleiten nur entlang der Zeit. Ein Filter vergleicht sich an jeder Stelle mit dem Signal "
     "und liefert dort einen hohen Wert, wo die Form passt.")

# 6 ------------------------------------------------------------ Aufbau
s = d.folie("Der Aufbau des Modells auf dem Chip")
d.ablauf(s, 0.47, 2.05, 12.3, [("Eingang", "100 × 6"), ("Faltung", "32 Filter"), ("Faltung", "64 Filter"),
                               ("Faltung", "128 Filter"), ("Mittelwert", "über die Zeit"), ("Entscheidung", "64 → 1"),
                               ("Sturz-Wert", "0 … 1")], h=1.25, hervor=(6,), size=16)
T(s, 0.47, 3.75, 6.0, 3.0, [
    [("Klein genug für die Sohle", {"bold": True, "color": GRUEN})],
    "61 601 Gewichte, nach dem Export 77 KB. Eine Entscheidung dauert auf dem ESP32-C6 nur einen Bruchteil der 0,2 s "
    "zwischen zwei Fenstern.",
], size=16, abstand=8)
T(s, 6.8, 3.75, 5.95, 3.0, [
    [("Zwischen den Faltungen", {"bold": True, "color": GRUEN})],
    "wird die Zeitachse jeweils halbiert. So sieht jede Schicht einen längeren Ausschnitt, die letzte fast das ganze Fenster.",
], size=16, abstand=8)
N(s, "Faltung, Pooling, Faltung, Pooling, Faltung, Mittelwert über die Zeit, zwei Dense-Schichten. Die Normierungsschichten "
     "aus dem Training sind für den Chip in die Faltungen eingerechnet.")

# 7 ------------------------------------------------------------ Lernen
s = d.folie("Lernen heißt: Gewichte so lange anpassen, bis die Beispiele stimmen")
kreis = [("Beispiel", "Fenster mit bekannter Antwort\n(Sturz oder Alltag)", 1.2, 2.0),
         ("Vorhersage", "das Netz rechnet einen\nSturz-Wert aus", 7.4, 2.0),
         ("Fehler", "wie weit lag es daneben?", 7.4, 4.55),
         ("Korrektur", "alle Gewichte ein kleines Stück\nin die richtige Richtung", 1.2, 4.55)]
for k, u, x, y in kreis:
    d.flaeche(s, x, y, 4.7, 1.45, fill=HELL)
    T(s, x + 0.25, y + 0.15, 4.2, 0.4, [[(k, {"bold": True})]], size=18)
    T(s, x + 0.25, y + 0.6, 4.2, 0.8, u.split("\n"), size=14, color=GRAU, abstand=0)
d.linie(s, 5.95, 2.72, 7.35, 2.72, farbe=GRAU, breite=2, pfeil=True)
d.linie(s, 9.75, 3.5, 9.75, 4.5, farbe=GRAU, breite=2, pfeil=True)
d.linie(s, 7.35, 5.27, 5.95, 5.27, farbe=GRAU, breite=2, pfeil=True)
d.linie(s, 3.55, 4.5, 3.55, 3.5, farbe=GRAU, breite=2, pfeil=True)
T(s, 0.47, 6.3, 12.3, 0.5, "Diese Runde läuft viele Tausend Mal. Getestet wird immer mit Personen, die im Training nicht vorkamen.",
  size=15, color=DUNKEL)
N(s, "Wichtig für die Erwartung: Das Netz lernt nur, was in den Beispielen steckt. Fehlen Stürze an der Sohle, "
     "kann es Sohlenstürze nur so gut erkennen, wie sie Stürzen am Bein ähneln.")

# 8 ------------------------------------------------------------ Ausgabe und Alarm
s = d.folie("Vom Sturz-Wert zum Alarm: drei von fünf müssen zustimmen")
werte = [0.04, 0.09, 0.31, 0.72, 0.93, 0.88, 0.47, 0.81, 0.12, 0.05]
for i, v in enumerate(werte):
    x = 0.8 + i * 1.18
    hoch = v >= 0.5
    d.flaeche(s, x, 2.3, 1.0, 1.0, fill=GRUEN if hoch else HELL)
    T(s, x, 2.55, 1.0, 0.5, f"{v:.2f}".replace(".", ","), size=18, bold=True, color=WEISS if hoch else GRAU,
      align=PP_ALIGN.CENTER)
    T(s, x, 3.4, 1.0, 0.3, f"{i * 0.2:.1f} s".replace(".", ","), size=12, color=GRAU, align=PP_ALIGN.CENTER)
d.flaeche(s, 0.8 + 3 * 1.18 - 0.08, 2.2, 5 * 1.18 - 0.02, 1.2, fill=None, line=ROT)
T(s, 0.8 + 3 * 1.18, 1.8, 5.8, 0.35, "4 von 5 über 0,5 → Alarm", size=15, bold=True, color=ROT)
T(s, 0.47, 4.15, 12.3, 2.6, [
    [("Beispielhafte Folge, ", {"bold": True}), ("alle 0,2 s ein Wert. Einzelne Ausreißer lösen nichts aus; erst wenn der Wert "
                                               "mehrfach hintereinander hoch ist, meldet die Sohle einen Sturz.", {})],
    [("Der Sturz-Wert ist keine echte Wahrscheinlichkeit. ", {"bold": True}),
     ("„93 %“ heißt: das Netz ist sich sicher – nicht, dass es in 93 von 100 Fällen stimmt.", {})],
    [("Danach prüft eine zweite Stufe ", {"bold": True}), ("Aufprall, Lageänderung und Ruhe und meldet die Sturzrichtung.", {})],
], size=16, punkte=True, abstand=10)
N(s, "Die Zahlen in den Kästchen sind ein ausgedachtes Beispiel zur Erklärung, keine Messung. Schwelle 0,5, Alarm bei 3 von 5. "
     "Die Prozentzahl in der App ist die Ausgabe des Netzes, nicht kalibriert.")

# 9 ------------------------------------------------------------ Export
s = d.folie("Vom Trainingsrechner auf den Mikrocontroller")
d.ablauf(s, 0.47, 2.05, 12.3, [("Keras-Modell", "Gleitkomma\n≈ 240 KB"), ("Normierung", "in Faltungen\neingerechnet"),
                               ("int8", "ganze Zahlen\n−128 … 127"), ("TFLite", "77 KB"), ("C-Datei", "modell_sohle.h"),
                               ("ESP32-C6", "TFLite Micro")], h=1.35, hervor=(2,), size=16)
T(s, 0.47, 3.85, 12.3, 2.9, [
    [("int8 statt Gleitkomma: ", {"bold": True}), ("viermal kleiner und schneller. Auf den eigenen Pilotdaten trifft das int8-Modell in 99,5 % der Fenster dieselbe Entscheidung.", {})],
    [("Normierung einrechnen: ", {"bold": True}), ("ohne diesen Schritt rechnete der Chip immer 0,47 – unabhängig vom Sensor. Das Exportskript erledigt das jetzt automatisch.", {})],
    [("Selbsttest beim Start: ", {"bold": True}), ("fünf feste Eingaben, deren Ergebnis beim Export berechnet wurde. Weicht der Chip ab, stimmt keine spätere Zahl.", {})],
], size=16, punkte=True, abstand=10)
N(s, "Die Schritte macht ein einziges Skript: tools/export_firmware_model.py. Die Details stehen in der Anleitung.")

# 10 ------------------------------------------------------------ Erwartung
s = d.folie("Was man realistisch erwarten kann")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Situation", "Ergebnis", "Wie belastbar?"],
    ["Hüfte, Laborstürze (SisFall)", "99,0 % erkannt, 99,3 % Alltag richtig", "hoch – 10 fremde Personen"],
    ["Schienbein, fremde Personen (CAPPIMU)", "84 % erkannt", "hoch – fünffach kreuzvalidiert"],
    ["Alltag an der Sohle (zwei fremde Datensätze)", "13 bzw. 28 Fehlalarm-Fenster je Stunde", "mittel – vor der 3-von-5-Regel"],
    ["Eigene Hardware, Lage ausgerichtet", "67 von 67 Stürzen", "gering – eine Person, Matte"],
    ["Echte Stürze in der Sohle", "noch nicht gemessen", "offen"],
], [4.6, 4.2, 3.5], size=15, h_zeile=0.56, zentriert_ab=3)
T(s, 0.47, 5.6, 12.3, 1.1, [
    [("Kurz: ", {"bold": True}), ("Das Modell erkennt Stürze am Bein zuverlässig. Wie viele Fehlalarme im echten Alltag an der Sohle "
                               "übrig bleiben, zeigt erst ein längerer Test mit mehreren Personen.", {})]], size=16)
N(s, "Die Fehlalarm-Fenster je Stunde sind vor der Abstimmungsregel gezählt; mit 3 von 5 werden es weniger. "
     "Alle Stürze in den Datensätzen sind simuliert, meist von jungen Menschen.")

# 11 ------------------------------------------------------------ Fehlerquellen
s = d.folie("Typische Fehlerquellen – und wie das Projekt sie abfängt")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Fehlerquelle", "Was passiert", "Gegenmaßnahme"],
    ["Sensor anders eingebaut", "Erkennung fällt um ein Drittel und mehr", "Selbstkalibrierung, gedrehte Trainingsdaten"],
    ["Keine Daten der Zielposition", "Fersenaufsatz wirkt wie ein Sturz", "Alltagsdaten von der Sohle ins Training"],
    ["Messbereich oder Abtastrate zu klein", "Aufprall wird abgeschnitten oder verschluckt", "±16 g, 100 Hz"],
    ["Rechenfehler auf dem Chip", "immer derselbe Wert", "Selbsttest beim Start"],
    ["Nur ein Grenzwert", "Joggen und Springen lösen aus", "CNN + Abstimmung + zweite Stufe"],
], [3.8, 4.1, 4.4], size=15, h_zeile=0.62, zentriert_ab=3)
N(s, "Jede Zeile ist im Projekt tatsächlich aufgetreten.")

# 12 ------------------------------------------------------------ Begriffe
s = d.folie("Begriffe auf einen Blick")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Begriff", "Bedeutung"],
    ["Sensitivität", "Anteil der Stürze, die erkannt werden"],
    ["Spezifität", "Anteil der Alltagsfenster, die richtig als „kein Sturz“ gelten"],
    ["Fehlalarme je Stunde", "wie oft das System im Alltag fälschlich auslöst – für Nutzer die wichtigste Zahl"],
    ["Fenster", "2 s Messdaten, die das Modell auf einmal bewertet"],
    ["Augmentierung", "Trainingsdaten zusätzlich gedreht oder gespiegelt, damit die Einbaulage weniger zählt"],
    ["Kreuzvalidierung", "fünfmal mit anderen Testpersonen prüfen – ein Ergebnis zählt nur, wenn es stabil ist"],
    ["Quantisierung (int8)", "Gewichte als ganze Zahlen speichern, damit das Modell auf den Chip passt"],
], [3.2, 9.1], size=15, h_zeile=0.56, zentriert_ab=9)
N(s, "Zum Nachschlagen.")

# 13 ------------------------------------------------------------ Fragen
s = d.folie("Fragen?")
T(s, 0.47, 2.3, 12.3, 2.0, [
    "Im zweiten Teil zeige ich das Projekt mit allen Ergebnissen,",
    "im dritten Teil, wie man ein Modell auf den Chip bringt und die Meldung in der App sieht.",
], size=20, color=GRAU, abstand=10)
N(s, "Überleitung.")

d.speichern(REPO / "praesentation" / "1_Technik_Neuronale_Netze.pptx")
