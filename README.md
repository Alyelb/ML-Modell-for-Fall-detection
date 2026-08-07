# Studienprojekt 2 – Sensorgestützte Sturzerkennung mittels ML-Modellen

## PDF direkt öffnen
- Direkter Link im Repository: **[LateX_Code/main.pdf](https://github.com/Alyelb/Sensorgest-tzte-Sturzerkennung-mittels-ML-Modellen/blob/main/LateX_Code/main.pdf)**
- Falls die GitHub-Vorschau nicht lädt: Datei öffnen und **Download** nutzen oder direkt über den Raw-Link herunterladen:  
  **https://raw.githubusercontent.com/Alyelb/Sensorgest-tzte-Sturzerkennung-mittels-ML-Modellen/main/LateX_Code/main.pdf**

> Quelle der Inhalte: `LateX_Code/main.tex` (Kapitelstruktur und Begründungen).

## Projektüberblick und Zielsetzung
Dieses Repository dokumentiert ein Studienprojekt zur automatischen Sturzerkennung mit Inertialsensoren für ein späteres Insole-/Wearable-Szenario.  
Der Fokus liegt auf einer belastbaren, literatur- und datenblattgestützten Entscheidungsbasis für die Modellentwicklung.

Übergeordnetes Ziel:
- zuverlässige Sturzerkennung,
- möglichst geringe Fehlalarme,
- sinnvolle Balance aus Erkennungsqualität, Energiebedarf und Implementierungsaufwand.

## Aufgaben (1–4) mit Vorgehen und Ergebnis

### Aufgabe 1 – Vergleich von 3-, 6- und 9-Achsen-Systemen
**Problem/Ziel**  
Klären, ob mehr Achsen die Sturzerkennung tatsächlich verbessern und ob der Zusatzaufwand gerechtfertigt ist.

**Methode**  
Literaturvergleich + Datenblattabgleich (u. a. Sensitivität/Spezifität, Energie- und Integrationsaufwand).

**Konkrete Schritte**
1. Physikalische Bedeutung der Achsengruppen (Beschleunigung, Gyroskop, Magnetometer) strukturiert aufgestellt.
2. 3-Achsen-Ansatz (SVM/Schwellwerte) mit realen Schwächen bei ADL-Abgrenzung bewertet.
3. 6-Achsen-Nutzen über quantitative Studienergebnisse begründet (v. a. weniger False Positives).
4. 9-Achsen-Zusatznutzen gegen Driftkorrektur vs. Indoor-Magnetstörungen und Mehrkosten abgewogen.
5. Repräsentative Komponenten (MPU-6050, LSM6DSOX, BHI360) über Datenblätter verglichen.

**Ergebnis/Status**  
Abgeschlossen. Für den Use Case ist **6-Achsen** der beste Kompromiss; 9-Achsen bringt für kurze Sturzereignisse meist keinen proportionalen Mehrwert.

---

### Aufgabe 2 – Einfluss der Sensoreigenschaften auf Erkennungsqualität
**Problem/Ziel**  
Bestimmen, welche Sensorparameter die spätere ML-Leistung praktisch beeinflussen.

**Methode**  
Kompakte, literaturbasierte Bewertung von fünf Kernparametern:
- Messbereich,
- Abtastrate,
- Bit-Auflösung,
- Rauschdichte,
- Drift.

**Konkrete Schritte**
1. Messbereich gegen Clipping-Risiko analysiert (Impact-Peaks als kritisches Merkmal).
2. Abtastraten-Einfluss auf Genauigkeit vs. Daten-/Energiebedarf verglichen.
3. Quantisierung und effektive Auflösung (unter Rauscheinfluss) eingeordnet.
4. Rauschdichte über RMS-Rauschen auf Merkmalsextraktion bezogen.
5. Gyroskop-Drift auf die kurze Sturzdauer skaliert und Relevanz reduziert bewertet.
6. Empfohlenen Arbeitsbereich für das Zielsystem zusammengefasst.

**Ergebnis/Status**  
Abgeschlossen. Empfohlen ist eine 6-Achsen-IMU mit praxisnahen Parametern wie z. B. **±16 g**, **20–50 Hz**, mindestens **12 Bit** und niedriger Rauschdichte.

---

### Aufgabe 3 – Auswahl und Bewertung von Open-Source-Datensätzen
**Problem/Ziel**  
Geeignete Datensätze für Aufgabe 4 auswählen, passend zur geplanten Sensorik und zum Zielanwendungsfall.

**Methode**  
Systematische Bewertung von sieben Datensätzen nach:
- Sensorposition,
- Achsenkonfiguration/Abtastrate,
- Klassenabdeckung (Stürze/ADL),
- Probandendiversität,
- Verfügbarkeit/Zugänglichkeit.

**Konkrete Schritte**
1. Datensatz-Übersichtstabelle erstellt (SisFall, MobiFall/MobiAct, UMAFall, KFall, FallAllD, UniMiB SHAR, WEDA-FALL).
2. Einzelbewertung je Datensatz mit Stärken/Limitierungen durchgeführt.
3. Zugangswege/Lizenzen dokumentiert (Direktdownload vs. Anfrage/Vertrag).
4. Primär- und Sekundärdatensatz begründet ausgewählt.

**Ergebnis/Status**  
Abgeschlossen. **SisFall** als Primärdatensatz; **KFall** als ergänzender Datensatz (u. a. wegen Pre-Impact-Annotation).

---

### Aufgabe 4 – Entwicklung und Training des ML-Modells
**Problem/Ziel**  
Ein robustes ML-Modell für Sturzerkennung mit den ausgewählten Datensätzen entwickeln und prototypisch für das Zielsystem nutzbar machen.

**Methode**  
Datengestützte Pipeline auf Basis der Ergebnisse aus Aufgaben 1–3.

**Konkrete Schritte (abgeleiteter Umsetzungspfad)**
1. Datensätze beschaffen/vereinheitlichen und Zielkanäle (6-Achsen) konsistent aufbereiten.
2. Abtastrate und Sensorbereiche gemäß den begründeten Empfehlungen harmonisieren.
3. Trainings-/Validierungsstrategie mit klarer Probandentrennung definieren.
4. Merkmals- und/oder Sequenzmodell(e) trainieren und gegen ADL-Fehlalarme optimieren.
5. Ergebnisse mit Literatur-Benchmarks vergleichen und Robustheit dokumentieren.

**Ergebnis/Status**  
**In Arbeit (Startphase)**. Grundlagen und Datensatzentscheidung sind abgeschlossen; Modellpipeline ist der nächste aktive Arbeitsschritt.

## Work Tree (Arbeitsbaum)
```text
Studienprojekt Sturzerkennung
├── A1: Sensorachsen-Vergleich (3/6/9)
│   ├── Literaturauswertung
│   ├── Datenblattvergleich (MPU-6050, LSM6DSOX, BHI360)
│   └── Entscheidung: 6-Achsen bevorzugt
├── A2: Sensoreigenschaften
│   ├── Messbereich / Clipping
│   ├── Abtastrate
│   ├── Bit-Auflösung
│   ├── Rauschdichte
│   └── Drift-Bewertung + empfohlener Arbeitspunkt
├── A3: Datensatzanalyse
│   ├── 7 Open-Source-Datensätze bewertet
│   ├── Verfügbarkeit & Lizenz geprüft
│   └── Entscheidung: SisFall (primär) + KFall (sekundär)
└── A4: ML-Entwicklung (Fortsetzung)
    ├── Datenaufbereitung / Harmonisierung
    ├── Feature- & Modelltraining
    ├── Evaluation / Vergleich mit Benchmarks
    └── Prototypische Integration ins Zielsystem
```

## How to continue (Roadmap ab Aufgabe 4)
1. **Datengrundlage finalisieren**: SisFall und KFall reproduzierbar laden, Metadaten dokumentieren, Versionierung festhalten.
2. **Preprocessing standardisieren**: Kanalmapping, Resampling (20–50 Hz Zielbereich), Fensterung, Normalisierung.
3. **Baseline zuerst**: Einfache Baseline (z. B. klassisches Modell) als Referenz vor komplexeren Deep-Learning-Varianten.
4. **Robuste Evaluation**: Probandenübergreifende Splits, Sensitivität/Spezifität/F1 getrennt ausweisen, Fehlalarmanalyse je ADL.
5. **Ablationen durchführen**: Einfluss von Samplingrate, Sensor-Kombination und Featuregruppen isoliert testen.
6. **Deployment-Vorbereitung**: Rechenzeit, Speicherbedarf und Energieprofil für Insole-Hardware abschätzen.
7. **Dokumentation fortführen**: Ergebnisse direkt in `LateX_Code/main.tex` konsistent nachpflegen.

## Repository-Struktur
- `LateX_Code/main.tex` – Hauptdokument (Source of Truth)
- `LateX_Code/references.bib` – Literaturdatenbank
- `LateX_Code/main.pdf` – erzeugte PDF-Ausgabe
- `.github/workflows/build-latex-pdf.yml` – automatischer PDF-Build und Update

## Automatischer PDF-Build (GitHub Actions)
Bei Push auf `main` und manuellem Start (`workflow_dispatch`) wird `LateX_Code/main.tex` gebaut.  
Wenn sich `LateX_Code/main.pdf` ändert, wird die Datei automatisch mit Commit-Message
`chore: auto-build LaTeX PDF` zurück nach `main` geschrieben und zusätzlich als Workflow-Artefakt hochgeladen.
