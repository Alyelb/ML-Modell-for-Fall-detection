/*
 * netz_int8.h  --  eigene int8-Inferenz des 1D-CNN, ohne TensorFlow Lite Micro
 *
 * Warum: Auf dem ESP32-C6 lieferte TFLite Micro eine vom Eingang
 * unabhaengige, konstante Ausgabe (p = 0,47), waehrend dieselbe Datei am
 * PC korrekt rechnet. Diese Datei rechnet dieselben int8-Operationen wie
 * die Referenzkerne von TensorFlow Lite (Faltung und Dense mit
 * Kanal-Multiplikatoren, Max-Pooling, Mittelwert), nur in einfachem C.
 * tools/export_firmware_model.py erzeugt die Gewichte (modell_netz.h)
 * und prueft am PC, dass jede Schicht Bit fuer Bit mit TFLite
 * uebereinstimmt.
 *
 * Aufbau (fest): 3 x [Conv1D k=5 + ReLU] mit Max-Pooling 2 nach den
 * ersten beiden, Mittelwert ueber die Zeit, Dense 64 + ReLU, Dense 1,
 * Sigmoid (in float).
 */
#ifndef NETZ_INT8_H
#define NETZ_INT8_H

#include <stdint.h>
#include <string.h>
#include <math.h>
#include "modell_netz.h"

// ---- Festkomma-Arithmetik wie in TFLite (gemmlowp) ----------------------
static inline int32_t netz_srdhm(int32_t a, int32_t b) {
  if (a == b && a == INT32_MIN) return INT32_MAX;
  int64_t ab = (int64_t)a * (int64_t)b;
  int32_t nudge = ab >= 0 ? (1 << 30) : (1 - (1 << 30));
  return (int32_t)((ab + nudge) / (1ll << 31));
}
static inline int32_t netz_rdbpot(int32_t x, int e) {
  if (e <= 0) return x;
  const int32_t mask = (int32_t)((1ll << e) - 1);
  const int32_t rest = x & mask;
  const int32_t schwelle = (mask >> 1) + ((x < 0) ? 1 : 0);
  return (x >> e) + ((rest > schwelle) ? 1 : 0);
}
static inline int32_t netz_mbqm(int32_t x, int32_t m, int shift) {
  const int links = shift > 0 ? shift : 0;
  const int rechts = shift > 0 ? 0 : -shift;
  return netz_rdbpot(netz_srdhm(x * (1 << links), m), rechts);
}
static inline int8_t netz_s8(int32_t v) {
  return (int8_t)(v < -128 ? -128 : (v > 127 ? 127 : v));
}

// ---- Schichten ------------------------------------------------------------
// Conv1D, Eingang [lin][cin], Gewichte [cout][k][cin], Ausgang [lout][cout]
static void netz_conv(const int8_t *ein, int lin, int cin, int8_t *aus, int cout,
                      const int8_t *w, const int32_t *b, const int32_t *mult,
                      const int8_t *shift, int32_t zp_ein, int32_t zp_aus,
                      int32_t akt_min) {
  const int lout = lin - NETZ_K + 1;
  for (int t = 0; t < lout; t++) {
    for (int o = 0; o < cout; o++) {
      int32_t acc = b[o];
      const int8_t *wo = w + o * NETZ_K * cin;
      for (int k = 0; k < NETZ_K; k++) {
        const int8_t *x = ein + (t + k) * cin;
        const int8_t *wk = wo + k * cin;
        for (int i = 0; i < cin; i++) acc += (int32_t)wk[i] * ((int32_t)x[i] - zp_ein);
      }
      int32_t v = netz_mbqm(acc, mult[o], shift[o]) + zp_aus;
      if (v < akt_min) v = akt_min;
      aus[t * cout + o] = netz_s8(v);
    }
  }
}

static void netz_maxpool2(const int8_t *ein, int lin, int c, int8_t *aus) {
  for (int t = 0; t < lin / 2; t++)
    for (int i = 0; i < c; i++) {
      int8_t a = ein[(2 * t) * c + i], b = ein[(2 * t + 1) * c + i];
      aus[t * c + i] = a > b ? a : b;
    }
}

// Dense, Gewichte [nout][nin]
static void netz_dense(const int8_t *ein, int nin, int8_t *aus, int nout,
                       const int8_t *w, const int32_t *b, const int32_t *mult,
                       const int8_t *shift, int32_t zp_ein, int32_t zp_aus,
                       int32_t akt_min) {
  for (int o = 0; o < nout; o++) {
    int32_t acc = b[o];
    const int8_t *wo = w + o * nin;
    for (int i = 0; i < nin; i++) acc += (int32_t)wo[i] * ((int32_t)ein[i] - zp_ein);
    int32_t v = netz_mbqm(acc, mult[o], shift[o]) + zp_aus;
    if (v < akt_min) v = akt_min;
    aus[o] = netz_s8(v);
  }
}

// Puffer (statisch, rund 4 KB)
static int8_t netz_p1[NETZ_L1 * NETZ_C1];
static int8_t netz_p2[NETZ_L1 / 2 * NETZ_C1];
static int8_t netz_p3[NETZ_L2 * NETZ_C2];
static int8_t netz_p4[NETZ_L2 / 2 * NETZ_C2];
static int8_t netz_p5[NETZ_L3 * NETZ_C3];
static int8_t netz_mittel[NETZ_C3];
static int8_t netz_d1[NETZ_D1];
static int8_t netz_roh_aus;      // roher int8-Ausgang der letzten Dense-Schicht

// Eingang: int8, [100][6] mit Skala/Nullpunkt NETZ_EIN_SKALA / NETZ_EIN_NULL.
// Rueckgabe: Sturz-Wert p in [0, 1].
static float netzRechnen(const int8_t *ein) {
  netz_conv(ein, NETZ_LEN, NETZ_KANAELE, netz_p1, NETZ_C1, netz_w1, netz_b1,
            netz_m1, netz_s1, NETZ_ZP_EIN, NETZ_ZP1, NETZ_AKT1);
  netz_maxpool2(netz_p1, NETZ_L1, NETZ_C1, netz_p2);
  netz_conv(netz_p2, NETZ_L1 / 2, NETZ_C1, netz_p3, NETZ_C2, netz_w2, netz_b2,
            netz_m2, netz_s2, NETZ_ZP1, NETZ_ZP2, NETZ_AKT2);
  netz_maxpool2(netz_p3, NETZ_L2, NETZ_C2, netz_p4);
  netz_conv(netz_p4, NETZ_L2 / 2, NETZ_C2, netz_p5, NETZ_C3, netz_w3, netz_b3,
            netz_m3, netz_s3, NETZ_ZP2, NETZ_ZP3, NETZ_AKT3);
  // Mittelwert ueber die Zeit, auf den naechsten int8-Wert gerundet.
  // (TFLite rundet hier je nach Version um +-1 anders; Faltungen und
  // Dense-Schichten sind dagegen bitgleich.)
  for (int i = 0; i < NETZ_C3; i++) {
    int32_t summe = 0;
    for (int t = 0; t < NETZ_L3; t++) summe += (int32_t)netz_p5[t * NETZ_C3 + i] - NETZ_ZP3;
    float r = roundf((float)summe * NETZ_MEAN_FAKTOR) + (float)NETZ_ZP_MEAN;
    netz_mittel[i] = netz_s8((int32_t)r);
  }
  netz_dense(netz_mittel, NETZ_C3, netz_d1, NETZ_D1, netz_wd1, netz_bd1,
             netz_md1, netz_sd1, NETZ_ZP_MEAN, NETZ_ZPD1, NETZ_AKTD1);
  int8_t roh;
  netz_dense(netz_d1, NETZ_D1, &roh, 1, netz_wd2, netz_bd2, netz_md2, netz_sd2,
             NETZ_ZPD1, NETZ_ZPD2, -128);
  netz_roh_aus = roh;
  const float logit = ((int32_t)roh - NETZ_ZPD2) * NETZ_SKALA_D2;
  return 1.0f / (1.0f + expf(-logit));
}

#endif
