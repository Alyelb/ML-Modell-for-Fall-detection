# CleverSole — Firmware für XIAO ESP32-C6 + MPU-6050/6500 (Einlegesohle)

## 1. Verkabelung

```
XIAO ESP32-C6       IMU-Modul (MPU-6050/6500)
-------------       -------------------------
3V3           →     VCC
GND           →     GND
D4 (GPIO22)   →     SDA
D5 (GPIO23)   →     SCL
D1 (GPIO1)    ←     INT        ← wichtig für das Aufwachen
                    AD0  → GND (Adresse 0x68)

Batterie (LiPo): Spannungsteiler 2 × 100 kΩ an PIN_BATT_ADC
```

Die Pins stehen oben in `CleverSole.ino` (`PIN_SDA`, `PIN_SCL`,
`PIN_MPU_INT`, `PIN_BATT_ADC`) und müssen zur tatsächlichen Verdrahtung
passen. Hinweis: Auf dem XIAO ESP32-C6 ist GPIO3 intern für die
Antennenumschaltung belegt; liegt der Spannungsteiler an einem anderen
ADC-Pin (z. B. D0/GPIO0 oder D2/GPIO2), `PIN_BATT_ADC` anpassen.

**Der INT-Pin muss auf GPIO0–GPIO7 liegen.** Nur diese sind beim
ESP32-C6 LP-GPIOs und können aus dem Tiefschlaf wecken. Liegt der Pin
woanders, wacht das Gerät nie wieder auf.

Der Spannungsteiler ist nötig, weil ein voller LiPo 4,2 V liefert, der
ADC aber maximal 3,3 V verträgt. Zwei gleiche Widerstände halbieren die
Spannung; `BATT_TEILER 2.0` rechnet das zurück.

## 2. Arduino IDE einrichten

Boards-Manager-URL:
```
https://espressif.github.io/arduino-esp32/package_esp32_index.json
```

Dann: `Werkzeuge → Board → ESP32 Arduino → ESP32C6 Dev Module`

Einstellungen:
- **Partition Scheme:** `Huge APP (3MB No OTA)` — das Modell braucht Platz
- **Flash Size:** 4 MB

## 3. Einbau in die Sohle und Modell

Die Firmware ist **nur für die Einlegesohle** gedacht.

**Einbau:** Das blaue IMU-Modul liegt flach unter der Ferse, die
Bauteilseite (Chip) zeigt nach oben, der auf das Modul gedruckte
**X-Pfeil zeigt zu den Zehen**. XIAO und Akku können beliebig daneben
liegen – maßgeblich ist nur das IMU-Modul, nicht die USB-Buchse.

**Kalibrierung (automatisch):** Nach jedem Aufwachen bestimmt die
Firmware die tatsächliche Lage des Moduls selbst:

1. Kurz stillstehen (≥ 1 s) → Richtung der Schwerkraft = „oben“.
2. Losgehen (ca. 10–15 Schritte) → Hauptdrehachse des Fußes = Querachse,
   die Richtung der Schwungphase legt „vorwärts“ fest.
3. Daraus folgt die Drehung in den Trainingsrahmen des Modells
   (x' vorwärts, y' abwärts, z' links). Ausgabe z. B.:
   `Kalibrierung ok: ... Querachse 92 %, Abweichung zur Vorgabe 12 Grad`
4. Erst danach startet die Erkennung (`Inferenz aktiv`).

Liegt das Modul schief oder verdreht, gleicht die Kalibrierung das aus.
Schlägt sie fehl (zu wenig Gehen), gilt die Montagevorgabe aus
`modell.h`. Mit `KALIB_RICHTUNG_AUTO 0` wird „vorwärts“ nicht aus dem
Gang, sondern aus dem X-Pfeil übernommen.

**Modell:** `modell_sohle.h` (B2r, int8, ca. 77 KB). Neu erzeugen:

```bash
pip install tensorflow
python tools/export_firmware_model.py <modell>.keras Pilotdaten/
```

Das Skript rechnet die BatchNorm-Schichten automatisch in die folgenden
Faltungen ein (sonst entstehen MUL/ADD-Operationen mit Broadcast, die
TFLM auf dem ESP32-C6 falsch auswertet: konstante Ausgabe ≈ 0,47),
prüft int8 gegen float und schreibt die Sollwerte des Selbsttests
(`MODELL_TEST_MUSTER` / `MODELL_TEST_SOLL`) in `modell_sohle.h`.
Steht in der Ausgabe `MUL` oder `ADD` bei den Operatoren, das Modell
nicht hochladen.

## 3a. Rechenkern: eigene int8-Kerne (Standard)

Auf dem ESP32-C6 lieferte TensorFlow Lite Micro eine vom Eingang
unabhängige, konstante Ausgabe (`p=0.469`), mit gefalteter wie mit
ungefalteter BatchNorm. Die Firmware rechnet das Netz deshalb
standardmäßig mit eigenen Kernen (`netz_int8.h`, `#define EIGENE_KERNE 1`):
dieselben int8-Rechenschritte wie TFLite, ohne Bibliothek. Die Gewichte
stehen in `modell_netz.h`, das `export_firmware_model.py` zusammen mit
`modell_sohle.h` erzeugt und am PC gegen TFLite prüft (Faltungen
bitgleich, Entscheidungen gleich).

Beim Start erscheint immer:

```
Selbsttest 0: alle=   0  p=0.000  soll=0.000  OK
...
Selbsttest 4: alle= -13  p=0.718  soll=0.719  OK
Modell (eigene Kerne) ok, ... us je Fenster
```

Im Betrieb erscheint mit `LIVE_AUSGABE 1` (Standard) alle 0,2 s eine Zeile:

```
LIVE  Sturz   2%  [..........]  Stimmen 0/5  kein Sturz
LIVE  Sturz  91%  [#########.]  Stimmen 1/5  Verdacht
LIVE  Sturz  97%  [##########]  Stimmen 3/5  STURZ!
LIVE  Sturz  12%  [#.........]  Stimmen 0/5  nach Alarm: Lage wird geprueft
```

`Sturz %` ist die Ausgabe des Netzes für die letzten 2 s (keine echte
Wahrscheinlichkeit), `Stimmen` die Fenster über 50 % unter den letzten
fünf. *Verdacht* erscheint sofort beim ersten Fenster über 50 %, der
Alarm bei 3 von 5 (nach 0,4–0,8 s). Pro Sturz gibt es genau einen Alarm;
während der Lageprüfung (bis 15 s) wird kein neuer ausgelöst. Mit
`LIVE_AUSGABE 0` erscheint stattdessen alle 10 s eine Zusammenfassung
(`p` = letzter Wert, `max der letzten 10 s` = höchster Wert seitdem).

**Kalibrierung:** Standard ist jetzt `KALIB_RICHTUNG_AUTO 0`: Hochachse
und Neigung aus der Schwerkraft, „vorn“ aus dem X-Pfeil. Weicht die aus
dem Gang bestimmte Querachse mehr als 45° davon ab (z. B. Modul in der
Hand bewegt), wird nur die Neigung korrigiert
(`... (Gang unklar: nur Neigung korrigiert)`).

## 3b. Meldungen über Bluetooth

Beispiel eines Alarms (Reihenfolge wie gesendet):

```
FFF1  STURZ 93% n=3 batt=87
      ... Person liegt still ...
FFF2  LAGE vorwaerts 92% (vor 92 rueck 0 seit 20)
FFF2  STUFE2 bestaetigt (Aufprall+Lage+Ruhe)
```

| Zeile | Bedeutung |
|---|---|
| `STURZ 93%` | Ausgabe des CNN (0–100 %). **Kein** kalibrierter Wahrscheinlichkeitswert, sondern ein Wert, ab 50 % stimmt das Fenster für „Sturz“; Alarm bei 3 von 5 Fenstern. |
| `LAGE` | Richtung aus der Liegelage; die Prozentzahl ist der Anteil der Schwerkraft auf der jeweiligen Achse (Übereinstimmung, keine Wahrscheinlichkeit). |
| `STUFE2` | Bestätigung durch einfache Kennwerte: \|a\|max > 1,5 g, Lageänderung > 40°, Ruhe in der Liegephase < 0,2 g. |

Die Schwellen der zweiten Stufe stehen in `referenzwerte.h`
(Knöchel-Pilotdaten, eine Person) und sind mit Sohlenaufnahmen neu zu
bestimmen (`tools/kennwerte_pilot.py`). Das CNN selbst arbeitet ohne
feste Grenzen; es bewertet das gesamte 2-s-Signal.

Weitere Zeilen: `LAGE keine Liegephase gefunden` (15 s ohne Ruhe),
Batteriestand über `180F`.

## 3c. Testmodus

`#define TESTMODUS 1` in `CleverSole.ino`: jede Modellausgabe wird
alle 0,2 s als `T,<ms>,<Sturz %>,<Stimmen von 5>` über Serial und BLE (`FFF2`) gesendet, der Tiefschlaf ist
abgeschaltet. Für Versuche: Serial Monitor oder nRF Connect mitloggen,
Uhrzeit jeder Aktivität notieren, danach Alarme zählen
(Sensitivität = erkannte / ausgeführte Stürze; Fehlalarme je Stunde =
Alarme im Alltag / Stunden). Im Einsatz `TESTMODUS 0`.

## 4. In Stufen testen

Alles auf einmal in Betrieb zu nehmen macht die Fehlersuche schwer.
Besser nacheinander:

**Stufe 1 — Sensor** (`MODELL_VERFUEGBAR 0`)
Erwartete Ausgabe: `WHO_AM_I = 0x68`. Bei Ruhe muss der Betrag der
Beschleunigung bei etwa 1,000 g liegen. Weicht er ab, stimmt die
Umrechnung oder der Messbereich nicht.

**Stufe 2 — Schrittzähler**
Zehn Schritte gehen. Es muss erscheinen: `10 Schritte erkannt →
Inferenz aktiv`. Zählt es zu viel oder zu wenig, `SCHRITT_SCHWELLE_G`
anpassen (mehr Schritte gezählt als gegangen → Wert erhöhen).

**Stufe 3 — Schlaf**
Gerät zwei Minuten ruhig liegen lassen. Es muss in den Tiefschlaf
gehen und beim Anstoßen wieder aufwachen (`Aufwachgrund`-Ausgabe).
Wacht es nicht auf, liegt der INT-Pin falsch.

**Stufe 4 — BLE**
Mit nRF Connect oder LightBlue scannen. Es muss `CleverSole-01`
erscheinen, mit Batteriedienst.

**Stufe 5 — Modell** (`MODELL_VERFUEGBAR 1`, `TESTMODUS 1`)
Beim Start erscheinen fünf Zeilen `Selbsttest i: ... OK`. Steht dort
`FALSCH`, rechnet TFLM anders als der Konverter (zwei TFLM-Bibliotheken
oder MUL/ADD im Modell) – dann ist jede spätere Zahl wertlos.
Auf die Inferenzzeit achten. Bei über 150 ms wird das Intervall von
200 ms knapp; dann `INFERENZ_INTERVALL` erhöhen.

## 5. Bekannte Fallstricke

**TensorFlow Lite Micro auf dem ESP32-C6.** Der Arduino-ESP32-Core 3.x
bringt `esp-tflite-micro` bereits mit; eine zusätzliche Bibliothek ist
nicht nötig und schadet: Sind Header und kompilierte Bibliothek aus
verschiedenen TFLM-Versionen, läuft `Invoke()` scheinbar fehlerfrei,
schreibt den Ausgabetensor aber nicht. Also **nur eine** TFLM-Quelle
(`TensorFlowLite_ESP32` und `Chirale_TensorFlowLite` deinstallieren).
Läuft es so nicht, ist der verlässliche Weg ESP-IDF mit der Komponente
`esp-tflite-micro`:

```bash
idf.py add-dependency "espressif/esp-tflite-micro"
```

Die Signalkette in dieser Datei lässt sich unverändert übernehmen; nur
das Gerüst um `setup()`/`loop()` ändert sich.

**Arena zu klein.** Meldet `AllocateTensors fehlgeschlagen`, in
Schritten von 16 KB erhöhen. Der tatsächliche Bedarf wird nach
erfolgreichem Start ausgegeben.

**Operatoren fehlen.** Fehlt einer, nennt TFLM ihn beim Start. Dann in
`modellInit()` ein `resolver.AddXxx()` ergänzen und den Zähler
`MicroMutableOpResolver<10>` erhöhen. Die benötigten Operatoren
stehen im Kopfkommentar von `modell.h`.

## 6. Was noch offen ist

Die Voting-Parameter (`VOTE_N`, `VOTE_M`, `VOTE_SCHWELLE`) sind
vorläufig. Sie wurden an UMAFall-Knöcheldaten bestimmt, wo sich kein
befriedigender Betriebspunkt fand. Nach der Pilotdatenerhebung sind
sie neu festzulegen.

Ebenso ist die Dezimation von 100 auf 50 Hz hier eine Mittelung über
zwei Werte, während im Training ein Polyphasenfilter verwendet wurde.
Die Näherung ist auf den Pilotdaten zu prüfen: Beide Wege auf
denselben Rohdaten rechnen und die Ausgaben vergleichen.

## 7. Energiebedarf (überschlägig)

| Zustand | Strom | Bemerkung |
|---|---|---|
| Tiefschlaf | ~15 µA | MPU im Motion-Modus, C6 schläft |
| Aktiv ohne BLE | ~30 mA | Messen und Rechnen |
| Aktiv mit BLE | ~45 mA | während der Übertragung |

Mit 250 mAh: rund 6–8 Stunden Dauerbetrieb, bei realistischem
Wechsel zwischen Gehen und Ruhen deutlich mehr. Der tatsächliche
Verbrauch ist zu messen — die Werte oben sind Datenblattschätzungen.
