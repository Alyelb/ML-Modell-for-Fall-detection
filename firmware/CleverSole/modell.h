/*
 * modell.h  --  Auswahl von Modell und Einbaulage
 *
 * EINBAU_SOHLE 1 : Board flach in der Sohle, Bauteilseite oben,
 *                  USB-C zur Aussenseite (Ferse). Modell B2r:
 *                  Lower-Limb mit Orientierungs-Augmentierung, OHNE
 *                  Sohlendaten trainiert (robust gegen Einbaulage).
 * EINBAU_SOHLE 0 : Board seitlich am Knoechel, USB-C oben.
 *                  Lower-Limb-Modell (CAPPIMU + ImbalanSense).
 *
 * Die Modelldateien erzeugt tools/export_firmware_model.py.
 */
#ifndef MODELL_H
#define MODELL_H

#define EINBAU_SOHLE 1

#if EINBAU_SOHLE
  #include "modell_sohle.h"
  // Sohle -> Trainingsrahmen Knoechel: x' = x, y' = -z, z' = y
  // (aus der Einbaugeometrie: Sohlennormale -> Hochachse Knoechel)
  #define R_EINBAU_WERTE { {1.0f, 0.0f,  0.0f}, \
                           {0.0f, 0.0f, -1.0f}, \
                           {0.0f, 1.0f,  0.0f} }
#else
  #include "modell_knoechel.h"
  #define R_EINBAU_WERTE { {1.0f, 0.0f, 0.0f}, \
                           {0.0f, 1.0f, 0.0f}, \
                           {0.0f, 0.0f, 1.0f} }
#endif

#endif
