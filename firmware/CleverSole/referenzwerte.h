/*
 * referenzwerte.h  --  Schwellen der zweiten Stufe (Bestaetigung)
 *
 * Quelle: eigene Pilotaufnahmen am Knoechel (rechts + links, eine
 * Person), erzeugt mit tools/kennwerte_pilot.py. Je Ereignis:
 *   AMAX  Spitze |a| um das Ereignis            [g]
 *   WMAX  Spitze |w| um das Ereignis            [deg/s]
 *   LAGE  Lageaenderung vorher -> 1-3 s danach  [Grad]
 *   RUHE  Std. von |a| 1-3 s danach             [g]
 *
 * Das CNN entscheidet NICHT anhand dieser Grenzen -- es bewertet das
 * gesamte Signal (100 x 6 Werte). Die Schwellen bestaetigen nur einen
 * Alarm (STUFE2). Fuer die Sohle mit Sohlenaufnahmen neu bestimmen.
 */
#ifndef REFERENZWERTE_H
#define REFERENZWERTE_H

// Zweite Stufe: bestaetigt einen CNN-Alarm (Knoechel: 34/45 Stuerze,
// 0 Fehlalarme -- an denselben Daten bestimmt, also optimistisch)
#define STUFE2_AMAX_MIN      1.5f
#define STUFE2_LAGE_MIN      40.0f
#define STUFE2_RUHE_MAX      0.2f

#endif
