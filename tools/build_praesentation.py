"""Praesentation Studienprojekt 2 auf Basis der THM-Vorlage (FB M, Breitbild)."""
import copy, shutil, zipfile, re
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION

D = Path(__file__).parent
GRUEN, GRAU, ROT, BLAU = RGBColor(0x80, 0xBA, 0x24), RGBColor(0x4A, 0x5C, 0x66), RGBColor(0xB3, 0x26, 0x3E), RGBColor(0x2F, 0x6D, 0xB5)
HELL, DUNKEL, WEISS = RGBColor(0xE6, 0xEA, 0xEC), RGBColor(0x26, 0x32, 0x38), RGBColor(0xFF, 0xFF, 0xFF)
FUSS = "Aly Elbermawy"

# --- Vorlage vorbereiten: Fusszeile ersetzen --------------------------------
src = D / "vorlage.pptx"; tmp = D / "vorlage_fuss.pptx"
with zipfile.ZipFile(src) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
    for it in zi.infolist():
        data = zi.read(it.filename)
        if it.filename.endswith(".xml") and b"Referenten" in data:
            data = data.replace("Name des  Referenten".encode(), FUSS.encode())
        zo.writestr(it, data)

prs = Presentation(tmp)
# vorhandene Beispielfolien entfernen
sld = prs.slides._sldIdLst
for s in list(sld):
    prs.part.drop_rel(s.rId); sld.remove(s)

L = {l.name: l for l in prs.slide_layouts}


def ph(slide, idx):
    for p in slide.placeholders:
        if p.placeholder_format.idx == idx:
            return p
    return None


def drop_empty(slide, keep=(0, 10)):
    for p in list(slide.placeholders):
        if p.placeholder_format.idx not in keep and not p.has_text_frame or (
                p.placeholder_format.idx not in keep and p.has_text_frame and not p.text_frame.text.strip()):
            p._element.getparent().remove(p._element)


def folie(titel, layout="Textfolie"):
    s = prs.slides.add_slide(L[layout])
    ph(s, 0).text = titel
    return s


def text(slide, x, y, w, h, runs, size=16, color=DUNKEL, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, bullets=False, space=6):
    """runs: str oder Liste von Absaetzen; Absatz = str oder Liste (text, {opts})."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05); tf.margin_top = tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(space)
        teile = para if isinstance(para, list) else [(para, {})]
        if bullets:
            p.text = ""
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", "228600"); pPr.set("indent", "-228600")
            bu = pPr.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}buChar", {"char": "•"})
            pPr.append(bu)
        for t, o in teile:
            r = p.add_run(); r.text = t
            f = r.font; f.size = Pt(o.get("size", size)); f.bold = o.get("bold", bold)
            f.italic = o.get("italic", False)
            f.color.rgb = o.get("color", color)
    return tb


def kasten(slide, x, y, w, h, fill=HELL, line=None):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line; sh.line.width = Pt(1)
    sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def kennzahl(slide, x, y, w, zahl, label, farbe=GRUEN, h=1.55, zsize=40):
    kasten(slide, x, y, w, h)
    text(slide, x + 0.15, y + 0.1, w - 0.3, 0.8, [[(zahl, {"bold": True, "size": zsize, "color": farbe})]])
    text(slide, x + 0.15, y + h - 0.68, w - 0.3, 0.62, label, size=13, color=GRAU)


def bild(slide, datei, x, y, w=None, h=None):
    kw = {}
    if w: kw["width"] = Inches(w)
    if h: kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(datei), Inches(x), Inches(y), **kw)


def tabelle(slide, x, y, w, zeilen, breiten, size=13, h_zeile=0.36, hervor=()):
    rows, cols = len(zeilen), len(zeilen[0])
    t = slide.shapes.add_table(rows, cols, Inches(x), Inches(y), Inches(w), Inches(h_zeile * rows)).table
    for j, b in enumerate(breiten):
        t.columns[j].width = Inches(b)
    for i, z in enumerate(zeilen):
        t.rows[i].height = Inches(h_zeile)
        for j, v in enumerate(z):
            c = t.cell(i, j); c.text = ""
            c.margin_left = c.margin_right = Inches(0.08); c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = c.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            r = p.add_run(); r.text = str(v)
            r.font.size = Pt(size); r.font.bold = (i == 0) or (i in hervor)
            c.fill.solid()
            if i == 0:
                c.fill.fore_color.rgb = GRAU; r.font.color.rgb = WEISS
            else:
                c.fill.fore_color.rgb = RGBColor(0xEF, 0xF6, 0xE4) if i in hervor else (WEISS if i % 2 else RGBColor(0xF3, 0xF5, 0xF6))
                r.font.color.rgb = DUNKEL
    return t


def saeulen(slide, x, y, w, h, kategorien, reihen, farben, titel=None, max_=None, fmt='0"%"',
            legende=True, size=12):
    cd = CategoryChartData(); cd.categories = kategorien
    for name, werte in reihen:
        cd.add_series(name, werte)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.font.size = Pt(size); ch.font.color.rgb = GRAU
    ch.has_title = bool(titel)
    if titel:
        ch.chart_title.text_frame.text = titel
        tr = ch.chart_title.text_frame.paragraphs[0].runs[0]; tr.font.size = Pt(size + 2); tr.font.bold = True
        tr.font.color.rgb = DUNKEL
    ch.has_legend = legende and len(reihen) > 1
    if ch.has_legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(size)
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RGBColor(0xDD, 0xDD, 0xDD)
    va.format.line.fill.background(); va.tick_labels.font.size = Pt(size - 1)
    va.minimum_scale = 0
    if max_: va.maximum_scale = max_
    va.tick_labels.number_format = fmt; va.tick_labels.number_format_is_linked = False
    ca = ch.category_axis; ca.tick_labels.font.size = Pt(size); ca.format.line.color.rgb = RGBColor(0xBB, 0xBB, 0xBB)
    pl = ch.plots[0]; pl.gap_width = 60; pl.overlap = -10
    pl.has_data_labels = True
    dl = pl.data_labels; dl.font.size = Pt(size - 1); dl.font.color.rgb = DUNKEL
    dl.number_format = fmt; dl.number_format_is_linked = False; dl.position = XL_LABEL_POSITION.OUTSIDE_END
    for s, f in zip(pl.series, farben):
        s.format.fill.solid(); s.format.fill.fore_color.rgb = f
    return ch


def notiz(slide, t):
    slide.notes_slide.notes_text_frame.text = t


# =====================================================================
# 1 Titel
s = prs.slides.add_slide(L["1_THM-Titelfolie"])
p = ph(s, 10); tf = p.text_frame; tf.text = ""
for i, (t, sz, b, c) in enumerate([("Sturzerkennung mit TinyML in einer sensorischen Einlegesohle", 18, True, DUNKEL),
                                   ("Studienprojekt 2 · Mechatronik (M.Sc.)", 12, False, GRAU),
                                   ("Aly Elbermawy", 12, True, DUNKEL),
                                   ("Betreuer: Prof. Dr. Sergej Kovalev", 11, False, GRAU),
                                   ("Partner: TrackTech GmbH / Clever-Sole", 11, False, GRAU)]):
    pp = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    pp.space_after = Pt(6 if i == 0 else 2)
    r = pp.add_run(); r.text = t; r.font.size = Pt(sz); r.font.bold = b; r.font.color.rgb = c
notiz(s, "Begrüßung. Thema: Sturzerkennung, die vollständig in einer Schuhsohle auf einem Mikrocontroller läuft. "
         "Partner Clever-Sole entwickelt die Sohle, ich habe die Erkennung untersucht und prototypisch umgesetzt.")

# 2 Motivation
s = folie("Motivation und Ziel")
text(s, 0.47, 1.85, 12.3, 1.2, [
    [("Nach einem Sturz ist entscheidend, wie lange die Person unbemerkt liegen bleibt. ", {}),
     ("Ziel: ", {"bold": True}), ("eine Sturzerkennung, die direkt in der Einlegesohle läuft, ohne Smartphone oder Cloud.", {})]],
     size=18)
for i, (z, l) in enumerate([("6 Achsen", "IMU: Beschleunigung + Drehrate"),
                            ("≈ 80 KB", "int8-Modell auf dem ESP32-C6 (TinyML)"),
                            ("0", "öffentliche Datensätze mit Stürzen an der Sohle")]):
    kennzahl(s, 0.47 + i * 4.15, 3.35, 3.95, z, l, farbe=[GRUEN, GRAU, ROT][i], h=1.7, zsize=40)
text(s, 0.47, 5.35, 12.3, 1.3, [
    [("Leitfrage: ", {"bold": True}),
     ("Lässt sich ein am Rumpf trainiertes Modell auf den Fuß übertragen, und was braucht es dafür?", {})]], size=18)
notiz(s, "Die meisten Datensätze messen an Hüfte oder Handgelenk. Für die Sohle gibt es keinen Sturzdatensatz. "
         "Daraus ergibt sich die Leitfrage des Projekts.")

# 3 Sensorik
s = folie("Sensorik: Warum 6 Achsen?")
tabelle(s, 0.47, 1.95, 7.6, [
    ["Konfiguration", "misst", "Nutzen für Stürze"],
    ["3 Achsen (Acc)", "Aufprall, Freifall", "Basis, viele Fehlalarme"],
    ["6 Achsen (+ Gyro)", "+ Drehrate", "hoch: Sp 83 → 96 %"],
    ["9 Achsen (+ Mag)", "+ absolute Richtung", "gering, Störung innen"],
], [2.3, 2.3, 3.0], size=14, h_zeile=0.5, hervor=(2,))
text(s, 8.45, 1.95, 4.3, 3.0, [
    [("Arbeitspunkt", {"bold": True, "color": GRUEN, "size": 18})],
    "±16 g, ±2000 °/s",
    "Erfassung 100 Hz, Modell 50 Hz",
    "≥ 12 Bit, geringe Rauschdichte",
    "Drift über 1–2 s Sturz unkritisch"], size=16, space=8)
text(s, 0.47, 4.75, 12.3, 1.8, [
    [("Eigene Messung: ", {"bold": True}),
     ("Am Rumpf bringt das Gyroskop im CNN nur +0,7 pp (98,7 vs. 98,0 %, Deckeneffekt); "
      "im Random Forest stammen 62 % der Merkmalswichtigkeit vom Gyroskop.", {})]], size=16)
notiz(s, "Literatur: das Gyroskop senkt vor allem Fehlalarme. Magnetometer lohnt nicht, da Stürze kurz sind und "
         "Magnetfelder in Innenräumen gestört werden. Eigene Ablation: an der Hüfte kaum Unterschied, weil nahe 100 %.")

# 4 Datensaetze
s = folie("Datensätze: Messorte am Körper")
bild(s, D / "koerper.png", 0.47, 1.8, h=5.0)
text(s, 7.75, 1.9, 5.0, 4.8, [
    [("SisFall", {"bold": True}), (" – Hüfte, Basismodell", {})],
    [("KFall", {"bold": True}), (" – Rücken, Zwischenstufe", {})],
    [("UMAFall, FallAllD", {"bold": True}), (" – Transfer", {})],
    [("WEDA-FALL", {"bold": True}), (" – Ältere (77–95 J.)", {})],
    [("CAPPIMU", {"bold": True}), (" – 9 Positionen, Stürze am Schienbein", {})],
    [("ImbalanSense, Smart-Insole", {"bold": True}), (" – Sohle, nur Alltag", {})],
    [("Eigene Pilotdaten", {"bold": True}), (" – Hüfte, Knöchel", {})],
], size=15, bullets=True, space=7)
notiz(s, "Stürze gibt es an Rumpf, Arm, Schienbein und Knöchel. An der Sohle nur Alltagsdaten. "
         "Das Modell muss also Stürze vom Bein und Alltag vom Fuß kombinieren.")

# 5 Prototyp
s = folie("Prototyp und Datenaufnahme")
bild(s, Path("/home/claude/ml-modell-for-fall-detection/bericht/Bilder/foto_platine.jpg"), 0.47, 1.85, h=2.6)
bild(s, Path("/home/claude/ml-modell-for-fall-detection/bericht/Bilder/foto_platine_unten.jpg"), 3.25, 1.85, h=2.6)
bild(s, D / "einbaulage.png", 6.35, 1.85, h=2.6)
text(s, 0.47, 4.75, 12.3, 2.0, [
    [("Hardware: ", {"bold": True}), ("Seeed XIAO ESP32-C6 + IMU-Modul (I²C), Akku; 100 Hz, ±16 g, ±2000 °/s", {})],
    [("DatenLogger: ", {"bold": True}), ("Aufnahme in den Flash, Steuerung per Smartphone (BLE), Auto-Stopp nach 120 s", {})],
    [("Pilotdaten (1 Person): ", {"bold": True}), ("Hüfte, Knöchel l./r. · 67 Stürze auf Matte · Gehen, Joggen, Treppen, Sitzen, Springen, Aufheben", {})],
], size=15, bullets=True, space=6)
notiz(s, "Eigene Logger-Firmware, damit Daten der Zielhardware entstehen. Knöchel: USB-C oben. "
         "Sohle: flach, Bauteilseite oben, USB-C zur Außenseite. Sohlenaufnahmen waren unvollständig und werden nicht ausgewertet.")

# 6 Pipeline
s = folie("Verarbeitungskette auf dem Chip")
schritte = [("IMU", "100 Hz\n±16 g"), ("Filtern", "→ 50 Hz"), ("Fenster", "2 s\n100 × 6"), ("Einbaulage", "feste\nDrehung"),
            ("Z-Norm", "je Kanal"), ("1D-CNN", "61 601 Param.\nint8, 80 KB"), ("3 von 5", "alle 0,2 s"), ("Alarm", "BLE")]
bw, gap, y0 = 1.32, 0.235, 2.3
for i, (k, u) in enumerate(schritte):
    x = 0.47 + i * (bw + gap)
    hi = k in ("1D-CNN", "Einbaulage")
    sh = kasten(s, x, y0, bw, 1.55, fill=GRUEN if hi else HELL)
    text(s, x, y0 + 0.12, bw, 0.45, [[(k, {"bold": True, "size": 15, "color": WEISS if hi else DUNKEL})]], align=PP_ALIGN.CENTER)
    text(s, x, y0 + 0.62, bw, 0.85, u.split("\n"), size=12, color=WEISS if hi else GRAU, align=PP_ALIGN.CENTER, space=0)
    if i < len(schritte) - 1:
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + bw + 0.03), Inches(y0 + 0.65), Inches(gap - 0.06), Inches(0.25))
        a.fill.solid(); a.fill.fore_color.rgb = GRAU; a.line.fill.background()
text(s, 0.47, 4.3, 6.0, 2.4, [
    [("Training (Python, Colab)", {"bold": True, "color": GRUEN, "size": 17})],
    "SisFall → KFall → Schienbein-Stürze + Sohlen-Alltag",
    "Rotations-/Spiegelaugmentierung (B2r)",
    "Export: TFLite int8, 9 Operatoren"], size=15, space=6)
text(s, 6.8, 4.3, 5.95, 2.4, [
    [("Firmware (Arduino, TFLite Micro)", {"bold": True, "color": GRUEN, "size": 17})],
    "Inferenz alle 200 ms, Rechenlast ≈ 5 %",
    "int8 = float in 96 % der Pilotfenster",
    "Einbaulage Sohle: x' = x, y' = −z, z' = y"], size=15, space=6)
notiz(s, "Die gesamte Kette läuft auf dem ESP32-C6. Neu gegenüber dem Standard: die feste Drehung der Einbaulage "
         "vor der Inferenz, da das CNN die Achsen einzeln auswertet.")

# 7 Methodik
s = folie("Bewertung: fair und statistisch abgesichert")
for i, (k, t) in enumerate([("Subjektunabhängig", "Kein Proband zugleich in Training und Test."),
                            ("5-fach gepaart", "Verfahren auf denselben Falten vergleichen, 95-%-KI der Differenz."),
                            ("Fehlalarme je Stunde", "Auf reinen Alltagsdaten – für ein Notrufsystem entscheidend."),
                            ("Betrieb wie Firmware", "0,2 s Schritt, 3 von 5; Sturz erkannt, wenn ≤ 1 s nach Aufprall Alarm.")]):
    x = 0.47 + (i % 2) * 6.2; y = 1.95 + (i // 2) * 1.95
    kasten(s, x, y, 5.95, 1.7)
    text(s, x + 0.2, y + 0.15, 5.6, 0.5, [[(k, {"bold": True, "size": 18, "color": GRUEN})]])
    text(s, x + 0.2, y + 0.7, 5.6, 0.9, t, size=15)
text(s, 0.47, 5.95, 12.3, 0.8, [[("Warum? ", {"bold": True}),
     ("Zwei frühere Einzelaufteilungen lieferten gegensätzliche Ergebnisse (−8,5 vs. +43,5 pp) – erst die Kreuzvalidierung war belastbar.", {})]], size=15)
notiz(s, "Stürze sind selten. Mit einer einzigen Aufteilung kippen Ergebnisse. Deshalb fünffach und gepaart. "
         "Genauigkeit ist bei seltenen Stürzen wenig aussagekräftig, daher Sensitivität und Fehlalarme je Stunde.")

# 8 Basismodell
s = folie("Ergebnis 1: Basismodell am Rumpf (SisFall)")
saeulen(s, 0.47, 1.8, 7.4, 4.95, ["Schwellwert", "Random Forest", "1D-CNN"],
        [("Sensitivität", (96.7, 94.2, 98.0)), ("Spezifität", (76.8, 99.6, 99.7))], [GRAU, GRUEN], max_=110, fmt='0.0"%"')
kennzahl(s, 8.3, 1.95, 4.45, "11 503 → 39", "Fehlalarm-Fenster: Schwellwert → CNN", farbe=GRUEN, zsize=34)
kennzahl(s, 8.3, 3.75, 4.45, "105 → 18", "übersehene Stürze: Random Forest → CNN", farbe=GRAU, zsize=34)
text(s, 8.3, 5.5, 4.45, 1.2, "Jede Stufe behebt die Schwäche der vorigen. Das CNN wird Basismodell.", size=15)
notiz(s, "Subjektunabhängiger Test auf 10 Probanden. Das CNN ist am Rumpf praktisch an der Obergrenze.")

# 9 Transfer
s = folie("Ergebnis 2: Übertragbarkeit auf andere Datensätze")
saeulen(s, 0.47, 1.8, 7.6, 4.95, ["KFall\nRücken", "UMAFall\nTaille", "UMAFall\nKnöchel", "FallAllD\nTaille"],
        [("Zero-Shot", (100.0, 43.8, 19.4, 12.7)), ("nach Fine-Tuning", (100.0, 91.7, 27.8, 69.8))], [GRAU, GRUEN], max_=115, fmt='0"%"')
text(s, 8.4, 1.95, 4.35, 4.8, [
    [("Sensitivität", {"bold": True, "color": GRUEN, "size": 18})],
    "Fine-Tuning schließt die Lücke zuverlässig.",
    [("Messbereich? ", {"bold": True}), ("Nein: SisFall auf ±8 g begrenzt bleibt bei 98,7 %.", {})],
    [("Abtastrate? ", {"bold": True}), ("Nein: FallAllD hat 238 Hz und scheitert trotzdem.", {})],
    [("Wahrscheinlicher: ", {"bold": True}), ("die Achsenlage (→ Ergebnis 6).", {})]], size=15, space=9)
notiz(s, "KFall überträgt ohne Anpassung. FallAllD scheitert trotz hoher Abtastrate. Clipping-Kontrolle schließt den "
         "Messbereich aus. Die spätere Erkenntnis zur Orientierung bietet eine einfachere Erklärung.")

# 10 Fehlalarme / Voting / Progressiv
s = folie("Ergebnis 3: Fehlalarme, Voting, Trainingsstrategie")
kennzahl(s, 0.47, 1.9, 3.95, "94 / h", "Fehlalarme am Knöchel ohne Anpassung, v. a. Joggen und Gehen", farbe=ROT)
kennzahl(s, 4.62, 1.9, 3.95, "+9,9 pp", "progressiv (SisFall → KFall → Ziel) statt direkt, 5/5 Falten", farbe=GRUEN)
kennzahl(s, 8.77, 1.9, 3.98, "−7,4 pp", "Sensitivität durch Hard Negatives – falscher Tausch", farbe=GRAU)
text(s, 0.47, 3.8, 12.3, 2.9, [
    [("Voting (5 von 7): ", {"bold": True}), ("−84 % Fehlalarme, aber die Hälfte der Sensitivität. Ohne Anpassung bleiben 3 von 47 Stürzen, mit Anpassung 13.", {})],
    [("→ Voting ersetzt die Anpassung nicht, es setzt sie voraus.", {"bold": True, "color": GRUEN})],
    [("Hard Negatives: ", {"bold": True}), ("Sp +2,1 pp gegen Se −7,4 pp. Fehlalarme lassen sich nachgelagert filtern, verpasste Stürze nicht.", {})],
    [("Progressiv: ", {"bold": True}), ("hilft bei wenig Zieldaten (UMAFall, 157 Stürze); bei vielen (CAPPIMU) kein Unterschied.", {})]],
    size=15, bullets=True, space=8)
notiz(s, "Jeder Fersenaufsatz sieht für das Rumpfmodell wie ein Aufprall aus. Voting wirkt nur, wenn das Modell "
         "um den Aufprall einen zusammenhängenden Block positiver Fenster liefert.")

# 11 Positionskurve
s = folie("Ergebnis 4: Vom Rumpf zum Fuß")
bild(s, D / "positionskurve.png", 0.47, 1.8, w=12.3)
text(s, 0.47, 5.85, 12.3, 0.9, [
    [("Sohle: 161–290 Fehlalarme/h", {"bold": True, "color": ROT}), (" – mehr als an jeder anderen Position. ", {}),
     ("Links und rechts unterscheiden sich bei denselben Stürzen bis Faktor 9.", {"bold": True})]], size=16)
notiz(s, "CAPPIMU misst dieselben Stürze gleichzeitig an neun Positionen. Statt einer fallenden Kurve sieht man "
         "einen Seitenunterschied. Am Fuß sind Alltagsspitzen höher als Sturzspitzen.")

# 12 Vorher / Nachher Fussdaten
s = folie("Ergebnis 5: Vorher/Nachher – Daten vom Bein und vom Fuß")
kat = ["A Basis", "K +KFall", "B1 +Bein", "B2 +Fuß", "B2r +Augm."]
saeulen(s, 0.47, 1.8, 6.0, 4.4, kat, [("Se Schienbein", (28.0, 22.6, 83.9, 84.5, 85.0))], [GRUEN],
        titel="Sensitivität am Schienbein", max_=100, fmt='0"%"', legende=False)
saeulen(s, 6.75, 1.8, 6.0, 4.4, kat, [("FP/h Smart-Insole", (290, 65, 508, 53, 18))], [ROT],
        titel="Fehlalarme/h an der Sohle (Smart-Insole, extern)", max_=600, fmt='0', legende=False)
text(s, 0.47, 6.3, 12.3, 0.55, [
    [("Fußdaten ohne Stürze: −95 % Fehlalarme bei gleicher Sensitivität (+0,6 pp, n. s.). ", {"bold": True}),
     ("Smart-Insole im Training: Ergebnis folgt.", {"color": GRAU})]], size=15)
notiz(s, "Sturzdaten vom Bein heben die Sensitivität um 61 Prozentpunkte. Ohne Fußdaten explodieren die Fehlalarme, "
         "weil jeder Fersenaufsatz wie ein Beinimpuls aussieht. ImbalanSense behebt das ohne Sensitivitätsverlust.")

# 13 Orientierung
s = folie("Ergebnis 6: Die Achsenlage ist eine eigene Fehlerquelle")
saeulen(s, 0.47, 1.8, 6.6, 4.3, ["Oberarm", "Handgelenk", "Schienbein"],
        [("links original", (6.2, 9.9, 16.6)), ("links gespiegelt", (60.2, 60.3, 41.9)), ("rechts original", (54.6, 51.8, 39.5))],
        [GRAU, GRUEN, BLAU], titel="Basismodell, Sensitivität", max_=75, fmt='0"%"')
kennzahl(s, 7.4, 1.9, 5.35, "3 → 15 von 22", "Stürze an der eigenen Hüfte – nur durch Achsen wie SisFall (+z vorn, +y unten)", farbe=GRUEN, zsize=34)
kennzahl(s, 7.4, 3.65, 5.35, "+17,3 pp", "Rotationsaugmentierung (B2r): Se bei gedrehtem Sensor, 5/5 Falten", farbe=GRAU, zsize=34)
text(s, 0.47, 6.2, 12.3, 0.6, [[("Mein Befund: ", {"bold": True, "color": GRUEN}),
     ("Spiegelung erklärt den Seitenunterschied vollständig. Die Einbaulage gehört zur Modellspezifikation.", {"bold": True})]], size=16)
notiz(s, "Das CNN wertet die Achsen einzeln aus. Gespiegelt erreicht die linke Seite die Werte der rechten. "
         "An der eigenen Hüfte reicht eine feste Drehung in den SisFall-Rahmen, ermittelt aus Schwerkraft und Liegelage. "
         "Die Augmentierung kostet nichts und macht das Modell robuster.")

# 14 Pilot
s = folie("Ergebnis 7: Pilotversuch auf der eigenen Hardware")
tabelle(s, 0.47, 1.9, 6.4, [
    ["Modell (3 von 5)", "Hüfte", "Knöchel r.", "Knöchel l."],
    ["Basis, Rohdaten", "3 / 14", "17 / 51", "13 / 42"],
    ["Basis, SisFall-Achsen", "15 / 14", "–", "–"],
    ["B2 (Bein + Fuß)", "15 / 82", "22 / 27", "20 / 39"],
    ["B2r (augmentiert)", "16 / 63", "20 / 17", "11 / 18"],
    ["B2r, links 180° gedreht", "–", "–", "20 / 7"],
], [2.5, 1.3, 1.3, 1.3], size=13, h_zeile=0.45, hervor=(5,))
text(s, 0.47, 4.75, 6.4, 0.6, "erkannte Stürze / Fehlalarm-Ereignisse (22/23/22 Stürze, 6–10 min Alltag)", size=12, color=GRAU)
bild(s, D / "kennwerte_pilot.png", 7.1, 1.85, w=5.65)
text(s, 7.1, 4.3, 5.65, 2.4, [
    [("Spitzenwerte trennen nicht ", {"bold": True}), ("(Alltag bis 10,7 g).", {})],
    [("Lageänderung > 40° + Ruhe < 0,2 g: ", {"bold": True}), ("34 von 45 Knöchelstürzen, 0 Fehlalarme.", {})],
    "→ zweite Stufe hinter dem CNN"], size=14, bullets=True, space=6)
notiz(s, "Am Knöchel erkennen die Beinmodelle fast alle Stürze, obwohl sie weder Hardware noch Person kannten. "
         "Die Liegelage zeigte, dass der linke Sensor 180 Grad gedreht war. Einfache Kennwerte sind ein guter Bestätiger.")

# 15 Behauptungen
s = folie("Geprüfte Behauptungen")
tabelle(s, 0.47, 1.85, 12.3, [
    ["Behauptung", "Ergebnis", "Beleg"],
    ["Fine-Tuning schließt die Domänenlücke", "bestätigt", "UMAFall Taille 44 → 92 %"],
    ["Fußdaten ohne Stürze kosten Sensitivität", "widerlegt", "Se +0,6 pp, Fehlalarme −95 %"],
    ["Die Position bestimmt die Leistung", "widerlegt", "Achsenlage: Spiegeltest 6 → 60 %"],
    ["Höhere Abtastrate / ±16 g sichern den Transfer", "widerlegt", "FallAllD 238 Hz: 12,7 %; ±8 g: 98,7 %"],
    ["Hard Negatives senken Fehlalarme sinnvoll", "widerlegt", "Sp +2,1 pp gegen Se −7,4 pp"],
    ["Augmentierung kostet Sensitivität", "widerlegt", "Se +4,6 pp, gedreht +17,3 pp"],
    ["Voting / progressives Training helfen", "teilweise", "nur mit Anpassung / bei wenig Zieldaten"],
    ["Smart-Insole im Training, breiteres Vortraining", "offen", "Notebooks 04 / 05, Teil E"],
], [5.2, 1.6, 5.5], size=14, h_zeile=0.52)
notiz(s, "Zusammenfassung der Hypothesen. Wichtig: Mehrere naheliegende Annahmen haben sich als falsch erwiesen.")

# 16 Fazit
s = folie("Fazit und Ausblick")
text(s, 0.47, 1.9, 7.0, 4.9, [
    [("Fazit", {"bold": True, "color": GRUEN, "size": 20})],
    [("Am Fuß sind Fehlalarme das Kernproblem, ", {"bold": True}), ("nicht die Sensitivität.", {})],
    [("Die richtigen Daten wirken am stärksten: ", {"bold": True}), ("Bein-Stürze +61 pp, Sohlen-Alltag −95 % Fehlalarme.", {})],
    [("Achsenlage = übersehene Fehlerquelle; ", {"bold": True}), ("Einbaulage festlegen und ausgleichen, augmentieren.", {})],
    [("Auf eigener Hardware: ", {"bold": True}), ("am Knöchel nahezu alle Stürze erkannt.", {})]], size=16, space=10)
kasten(s, 7.75, 1.9, 5.0, 3.9)
text(s, 7.95, 2.05, 4.6, 0.5, [[("Ausblick", {"bold": True, "color": GRUEN, "size": 20})]])
text(s, 7.95, 2.65, 4.6, 4.0, [
    "Aufnahmen in beiden Sohlen, mehrere Personen",
    "Zweite Stufe: Lageänderung + Liegephase",
    "Alarmparameter auf Sohlendaten festlegen",
    "Energiebedarf im Dauerbetrieb messen",
    "Kommerzielles Modell (ohne Smart-Insole/MobiAct) nach Lizenzprüfung an Clever-Sole"], size=15, bullets=True, space=8)
notiz(s, "Kernaussagen und nächste Schritte. Das Modell an der Sohle selbst ist noch nicht validiert.")

# 17 Danke
s = folie("Vielen Dank – Fragen?")
text(s, 0.47, 2.6, 12.3, 1.2, [[("Sturzerkennung mit TinyML in einer sensorischen Einlegesohle", {"bold": True, "size": 24})]],
     align=PP_ALIGN.LEFT)
text(s, 0.47, 3.6, 12.3, 1.6, ["Aly Elbermawy · aly.elbermawy@m.thm.de",
                               "Code, Notebooks, Firmware und Bericht: github.com/Alyelb/ML-Modell-for-Fall-detection"], size=16, color=GRAU)
bild(s, Path("/home/claude/ml-modell-for-fall-detection/bericht/Bilder/foto_platine.jpg"), 9.3, 4.4, h=2.4)

# leere Platzhalter entfernen
for sl in prs.slides:
    for p in list(sl.placeholders):
        if p.has_text_frame and not p.text_frame.text.strip() and p.placeholder_format.idx not in (10,):
            p._element.getparent().remove(p._element)

# Foliennummer aus dem Layout uebernehmen (python-pptx kopiert sie nicht)
from pptx.enum.shapes import PP_PLACEHOLDER
for i, sl in enumerate(prs.slides):
    if i == 0:
        continue
    for lp in sl.slide_layout.placeholders:
        if lp.placeholder_format.type == PP_PLACEHOLDER.SLIDE_NUMBER:
            sl.shapes._spTree.append(copy.deepcopy(lp._element))
out = D / "Praesentation_Sturzerkennung.pptx"
prs.save(out)
print("gespeichert", out, len(prs.slides), "Folien")
