# Aufnahmeprotokoll Pilotdaten

Eine Person, zwei Positionen: **WAIST** (Gürtel vorn, wie SisFall) und
**FOOT_INSOLE** (Schuhoberseite/Sohle, fest fixiert). Sensorausrichtung
markieren und in allen Aufnahmen gleich lassen.

## Ablauf je Aufnahme

1. USB am PC, Serial Monitor (115200): `p` bis Position stimmt, `a` bis
   Aktivität stimmt.
2. Monitor schließen, Board auf Powerbank/Akku umstecken.
3. **BOOT** drücken → 5 s Vorlauf → Aufnahme läuft.
4. 3 s ruhig stehen, dann 3× leicht auf den Sensor klopfen (Sync mit Video).
5. Aktivität ausführen (Video mitlaufen lassen).
6. **BOOT** drücken → Datei geschlossen. Erst danach umstecken.

Speicher reicht für einige Minuten. Nach jeder Position auslesen:
`python tools/pilot_download.py --loeschen`, dann den neuen Ordner in
Drive unter `ML_Fall_Detection/Pilotdaten/` ablegen.

## Aufnahmen je Position

| Aktivität | Dauer / Wiederholungen |
|---|---|
| walking | 2 min |
| jogging | 1 min |
| stairs_up, stairs_down | je 3 Durchgänge |
| sit_stand | 5× hinsetzen/aufstehen |
| sit_hard | 5× kräftig auf Sofa/Bett setzen |
| jumping | 10 Sprünge |
| pick_up | 5× Gegenstand vom Boden aufheben |
| fall_knees | 5 Stürze, je 5 s liegen bleiben |
| fall_lateral | 5 Stürze (links/rechts gemischt) |
| fall_forward | 5 Stürze, mit Händen abfangen |
| fall_slip | 3–5 Stürze |
| fall_backward | 3 Stürze, nur mit Helfer, auf Matte sitzend |

Stürze nur auf dicke Matte, langsam beginnen. Zwischen zwei Stürzen
mindestens 6 s Abstand (sonst trennt die Auswertung sie nicht).
Mehrere Stürze desselben Typs gehören in **eine** Datei.
