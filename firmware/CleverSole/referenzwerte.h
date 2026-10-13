/*
 * referenzwerte.h  --  Wertebereiche je Aktivitaet zur Anzeige
 *
 * Quelle: eigene Pilotaufnahmen am Knoechel (rechts + links, eine
 * Person), erzeugt mit tools/kennwerte_pilot.py. Je Ereignis:
 *   AMAX  Spitze |a| um das Ereignis            [g]
 *   WMAX  Spitze |w| um das Ereignis            [deg/s]
 *   LAGE  Lageaenderung vorher -> 1-3 s danach  [Grad]
 *   RUHE  Std. von |a| 1-3 s danach             [g]
 *
 * Das CNN entscheidet NICHT anhand dieser Grenzen -- es bewertet das
 * gesamte Signal (100 x 6 Werte). Die Bereiche dienen nur dazu, den
 * aktuellen Wert einzuordnen, und als zweite Stufe (STUFE2_*), die einen
 * Alarm bestaetigt. Fuer die Sohle mit Sohlenaufnahmen neu bestimmen.
 */
#ifndef REFERENZWERTE_H
#define REFERENZWERTE_H

// Stuerze (45 Ereignisse)
#define REF_STURZ_AMAX_MIN   1.83f
#define REF_STURZ_AMAX_MAX   9.64f
#define REF_STURZ_WMAX_MIN   52.0f
#define REF_STURZ_WMAX_MAX   628.0f
#define REF_STURZ_LAGE_MIN   11.0f
#define REF_STURZ_LAGE_MAX   108.0f
#define REF_STURZ_RUHE_MIN   0.00f
#define REF_STURZ_RUHE_MAX   0.17f

// Gehen (176 Ereignisse)
#define REF_GEHEN_AMAX_MIN   1.38f
#define REF_GEHEN_AMAX_MAX   3.07f
#define REF_GEHEN_LAGE_MAX   11.6f
#define REF_GEHEN_RUHE_MIN   0.15f

// Joggen (64), Springen (21), kraeftig Hinsetzen (14) -- nur zur Info
#define REF_JOGGEN_AMAX_MAX  6.53f
#define REF_SPRINGEN_AMAX_MAX 10.74f
#define REF_SITZEN_LAGE_MAX  35.8f

// Zweite Stufe: bestaetigt einen CNN-Alarm (Knoechel: 34/45 Stuerze,
// 0 Fehlalarme -- an denselben Daten bestimmt, also optimistisch)
#define STUFE2_AMAX_MIN      1.5f
#define STUFE2_LAGE_MIN      40.0f
#define STUFE2_RUHE_MAX      0.2f

#endif
