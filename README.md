# Sensor-Based Fall Detection with Machine Learning

> **[📄 Read the Full Report (PDF)](report/main.pdf)**

**Studienprojekt 2**  TH Mittelhessen, Fachbereich 12 (Elektro- und Informationstechnik)

| | |
|---|---|
| **Author** | Aly Elbermawy
| **Semester** | SS 2026 |

---

## Project Goal

Develop a TinyML pipeline for **real-time fall detection** using a 6-axis IMU embedded in a **shoe insole**, targeting elderly and dementia patients. The system runs on an **ESP32-C6 microcontroller** with an external **MPU-6050** sensor.

---

## Current Results

All evaluations are **subject-independent** (tested on persons not seen during training).

| Model | Sensitivity | Specificity | Accuracy | FP | FN |
|---|---|---|---|---|---|
| Threshold (Bourke) | 96.7 % | 76.8 % | 77.5 % | 11,503 | 59 |
| Random Forest | 94.2 % | 99.6 % | 99.4 % | 215 | 105 |
| **1D-CNN** | **98.0 %** | **99.7 %** | **99.6 %** | **39** | **18** |

The int8-quantized TFLite model is **64 KB** — fits comfortably in the ESP32-C6's 4 MB flash.

---

## Project Structure

```
├── report/
│   ├── main.tex              <- Full LaTeX report (Aufgaben 1-4)
│   └── references.bib        <- BibTeX references
├── fall_pipeline.py           <- Threshold baseline + Random Forest
├── cnn_pipeline.py            <- 1D-CNN + int8 TFLite export
├── requirements.txt           <- Python dependencies
├── .github/
│   └── workflows/
│       └── build-pdf.yml      <- Auto-compiles LaTeX to PDF on push
└── README.md
```

---

## Progress & Methodology

### Aufgabe 1 — Sensor Axis Comparison ✅

Theoretical comparison of 3-, 6-, and 9-axis sensor configurations. Conclusion: **6-axis (accelerometer + gyroscope) is the optimal trade-off** — the gyroscope dramatically reduces false positives (specificity jumps from ~83% to ~96%), while the magnetometer adds marginal benefit for the short-duration fall event and introduces indoor magnetic interference.

### Aufgabe 2 — Sensor Properties ✅

Analysis of five sensor properties (measurement range, sampling rate, bit resolution, noise density, gyroscope drift) and their effect on detection quality. Recommended operating point: **±16 g, 20–50 Hz, ≥12 bit, low noise density, uncorrected drift** (negligible over a 1–2 s fall).

### Aufgabe 3 — Dataset Evaluation ✅

Evaluation of seven open-source fall datasets (SisFall, MobiFall/MobiAct, UMAFall, KFall, FallAllD, UniMiB SHAR, WEDA-FALL). **SisFall** selected as primary dataset (6-axis, ±16 g, 200 Hz, 38 subjects). **KFall** as secondary (pre-impact annotation).

### Aufgabe 4 — ML Model Development 🔄 In Progress

**Completed:**
- SisFall data loader with ADC-to-physical-unit conversion
- Downsampling (200 → 50 Hz) and impact-centered windowing (2 s, 50% overlap)
- Three progressively stronger models (see results table above)
- Feature importance analysis confirming gyroscope dominance (4 of top 5 features)
- Int8 TFLite quantization (64 KB model ready for ESP32-C6)

**Planned:**
- Sampling-rate ablation study (10 / 20 / 50 Hz)
- Cross-dataset validation (SisFall ↔ KFall)
- ESP32-C6 + MPU-6050 hardware integration
- Pilot foot dataset collection for domain adaptation
- Long-Lie post-fall monitoring layer

---

## Domain Gap: Waist → Foot

No public foot-mounted IMU fall-detection dataset exists. SisFall was recorded at the waist. The pipeline mitigates this gap through:

1. **Rotation-invariant magnitude features** (RF) — orientation-independent
2. **Per-window z-normalization** (CNN) — removes position-dependent offsets
3. **Subject-independent validation** — prevents overfitting to individual movement patterns
4. **Planned pilot foot data** — fine-tuning the CNN's last layers on self-collected insole data

---

## Quick Start

```bash
git clone https://github.com/Alyelb/ML-Modell-for-Fall-detection.git
cd ML-Modell-for-Fall-detection
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt

# Download SisFall and place in data/SisFall_dataset/

python fall_pipeline.py          # Threshold + RF baseline
python cnn_pipeline.py           # 1D-CNN + TFLite export
```

---

## Hardware Target

| Component | Specification |
|---|---|
| MCU | ESP32-C6 (RISC-V, WiFi 6 + BLE) |
| IMU | MPU-6050 (6-axis, ±16 g / ±2000 °/s) via I2C |
| Model size | 64 KB (int8 quantized TFLite) |
| Inference | < 50 ms per 2 s window |
| Form factor | Shoe insole integration |

---

## License

Academic use only (Studienprojekt, TH Mittelhessen).
