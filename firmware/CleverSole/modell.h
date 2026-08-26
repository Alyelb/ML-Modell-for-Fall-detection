/*
 * modell.h  --  Platzhalter fuer das quantisierte CNN
 *
 * Erzeugung aus fall_model_int8.tflite:
 *
 *   xxd -i fall_model_int8.tflite > modell_roh.h
 *
 * Danach in dieser Datei:
 *   - MODELL_VERFUEGBAR auf 1 setzen
 *   - den Array-Inhalt aus modell_roh.h hier einfuegen
 *   - Array in "modell_tflite" umbenennen
 *
 * Wichtig: Das Array muss 16-Byte-ausgerichtet sein, sonst schlaegt
 * TFLite Micro beim Laden fehl.
 */
#ifndef MODELL_H
#define MODELL_H

#define MODELL_VERFUEGBAR 0

#if MODELL_VERFUEGBAR
alignas(16) const unsigned char modell_tflite[] = {
  0x1c, 0x00, 0x00, 0x00, /* ... hier den Inhalt einfuegen ... */
};
const unsigned int modell_tflite_len = sizeof(modell_tflite);
#endif

#endif
