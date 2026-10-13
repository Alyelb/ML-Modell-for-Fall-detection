/*
 * modell.h  --  Modell und Montagevorgabe fuer die Einlegesohle
 *
 * Einbau: Das blaue IMU-Modul liegt flach unter der Ferse,
 *         Bauteilseite (Chip) nach oben, der aufgedruckte X-Pfeil
 *         zeigt zu den Zehen. Lage von XIAO und Akku ist egal.
 *
 * Modell: B2r -- SisFall -> KFall -> Unterschenkel-Stuerze (CAPPIMU)
 *         + Sohlen-Alltag (ImbalanSense), rotations-/spiegelaugmentiert.
 *         Erzeugt mit tools/export_firmware_model.py.
 *
 * Trainingsrahmen des Modells: x' = vorwaerts, y' = abwaerts (entlang
 * des Unterschenkels), z' = nach links. Die Firmware bestimmt die
 * Drehung Sensor -> Trainingsrahmen nach jedem Aufwachen selbst
 * (Kalibrierung in CleverSole.ino). R_MONTAGE gilt nur, solange diese
 * Kalibrierung noch nicht abgeschlossen ist oder fehlschlaegt.
 */
#ifndef MODELL_H
#define MODELL_H

#include "modell_sohle.h"

// Montagevorgabe (Chip oben, X zu den Zehen):
//   x' = x  (vorwaerts),  y' = -z  (abwaerts),  z' = y  (links)
#define R_MONTAGE_WERTE { {1.0f, 0.0f,  0.0f}, \
                          {0.0f, 0.0f, -1.0f}, \
                          {0.0f, 1.0f,  0.0f} }

#endif
