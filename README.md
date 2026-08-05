# Studienprojekt 2 – Sensorgestützte Sturzerkennung mittels ML-Modellen

👉 **[PDF direkt öffnen](./LateX_Code/main.pdf)**

## Projektüberblick
Dieses Repository enthält mein Studienprojekt an der TH Mittelhessen zur sensorgestützten Sturzerkennung mit Machine-Learning-Methoden.  
Die Arbeit untersucht, wie gut unterschiedliche Inertialsensor-Konfigurationen (3-, 6- und 9-Achsen) für die Sturzerkennung geeignet sind und welche Kombination aus Genauigkeit, Robustheit und Energi[...] 

Die inhaltliche Grundlage dieser Beschreibung orientiert sich an `LateX_Code/main.tex`.

## Ziel des Projekts
Das übergeordnete Ziel ist die Entwicklung eines alltagstauglichen, zuverlässigen und ressourcenschonenden Systems zur automatischen Erkennung von Stürzen.  
Dafür wird das Projekt in vier aufeinander aufbauende Aufgaben gegliedert.

## Projektaufgaben und Schritte
1. **Aufgabe 1 – Vergleich der Sensorachsen (3/6/9 Achsen)**  
   Theoretischer und literaturgestützter Vergleich der Sensorkonfigurationen hinsichtlich Eignung für Sturzerkennung.

2. **Aufgabe 2 – Bewertung relevanter Sensoreigenschaften**  
   Analyse wichtiger Hardware-Eigenschaften (z. B. Abtastrate, Messbereich, Rauschverhalten, Energiebedarf) und deren Einfluss auf die Erkennungsqualität.

3. **Aufgabe 3 – Auswahl geeigneter Open-Source-Datensätze**  
   Systematische Bewertung verfügbarer Fall-Datensätze (u. a. nach Sensorposition, Achsen, Klassenabdeckung und Datenqualität) als Grundlage für das spätere Modelltraining.

4. **Aufgabe 4 – Entwicklung und Training des ML-Modells**  
   Aufbau, Training und prototypische Integration eines geeigneten Modells für die praktische Sturzerkennung.

## Aktueller Stand
Ich befinde mich aktuell **am Anfang von Aufgabe 4**.  
Die Aufgaben 1 bis 3 wurden inhaltlich vorbereitet und dokumentiert; als nächster Schritt startet die eigentliche Modellentwicklung mit den ausgewählten Datensätzen.

## Repository-Inhalt
- `LateX_Code/main.tex` – Hauptdokument der wissenschaftlichen Ausarbeitung
- `LateX_Code/references.bib` – Literaturverzeichnis
- `README.md` – Projektübersicht

## PDF (lokal erstellen & live aktualisieren)
Die README verlinkt jetzt auf `LateX_Code/main.pdf`. Damit der Link funktioniert, muss `LateX_Code/main.pdf` im Repository vorhanden sein.

Wenn du die PDF lokal erstellen und bei Änderungen automatisch neu bauen möchtest ("live"), empfehle ich `latexmk` mit der `-pvc` Option. Schritte:

1. Installiere eine TeX-Distribution (falls noch nicht vorhanden):
   - Ubuntu/Debian: `sudo apt install texlive-full latexmk`
   - macOS: installiere MacTeX oder `brew install basictex` + `tlmgr`/`tinytex`

2. Wechsle ins Repo-Verzeichnis und starte den Live-Builder:

   ```bash
   cd path/to/repo
   latexmk -pdf -pvc LateX_Code/main.tex
   ```

   `latexmk -pdf -pvc` beobachtet `main.tex` (und inkludierte Dateien) und baut automatisch `LateX_Code/main.pdf` bei Änderungen.

Alternativ kannst du lokal einmalig mit `pdflatex` oder `xelatex` bauen, z. B. `latexmk -pdf LateX_Code/main.tex`.

Wenn du möchtest, kann ich zusätzlich eine GitHub Actions-Workflow-Datei erstellen, die bei jedem Push die PDF automatisch baut und committet. Sag mir kurz, ob du das willst.
