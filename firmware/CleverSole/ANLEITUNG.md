# CleverSole — Firmware für ESP32-C6 + MPU-6050

## 1. Verkabelung

```
ESP32-C6            MPU-6050
--------            --------
3.3V          →     VCC
GND           →     GND
GPIO6 (SDA)   →     SDA
GPIO7 (SCL)   →     SCL
GPIO4         ←     INT        ← wichtig für das Aufwachen
                    AD0  → GND (Adresse 0x68)

Batterie (LiPo)
---------------
BAT+ ─┬─ 100 kΩ ─┬─ 100 kΩ ─ GND
      │          │
      │        GPIO1 (ADC)
      └─ zum Regler
```

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

## 3. Modell einbinden

In `modell.h` wird mit `EINBAU_SOHLE` gewählt:

| `EINBAU_SOHLE` | Einbau | Modell |
|---|---|---|
| `1` (Standard) | flach in der Sohle, Bauteilseite oben, USB-C zur Außenseite/Ferse | B2r: Lower-Limb mit Orientierungs-Augmentierung, ohne Sohlendaten (`modell_sohle.h`) |
| `0` | seitlich am Knöchel, USB-C oben | Lower-Limb (`modell_knoechel.h`) |

Die passende Achsdrehung (`R_EINBAU`) wird mit ausgewählt. Wird das
Board anders eingebaut, stimmt sie nicht mehr -- dann sinkt die
Erkennung deutlich (Bericht, Abschnitt Sensororientierung).

Modelldateien neu erzeugen:

```bash
pip install tensorflow
python tools/export_firmware_model.py <modell>.keras Pilotdaten/ modell_sohle.h
```

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

**Stufe 5 — Modell** (`MODELL_VERFUEGBAR 1`)
Auf die Inferenzzeit achten. Bei über 150 ms wird das Intervall von
200 ms knapp; dann `INFERENZ_INTERVALL` erhöhen.

## 5. Bekannte Fallstricke

**TensorFlow Lite Micro auf dem ESP32-C6.** Der Arduino-ESP32-Core 3.x
bringt `esp-tflite-micro` bereits mit; eine zusätzliche Bibliothek ist
dann nicht nötig. Die alte Bibliothek `TensorFlowLite_ESP32` ist
veraltet und nicht zu verwenden. Findet der Compiler
`tensorflow/lite/micro/micro_interpreter.h` nicht, im
Bibliotheksverwalter `Chirale_TensorFlowLite` installieren (wird
automatisch eingebunden). Läuft beides nicht, ist der verlässliche Weg
ESP-IDF mit der Komponente `esp-tflite-micro`:

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
