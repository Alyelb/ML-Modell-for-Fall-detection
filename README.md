# Sensor-Based Fall Detection with Machine Learning

<<<<<<< HEAD
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
=======
Master's project (Studienprojekt 2) at TH Mittelhessen — TinyML fall-detection pipeline for a shoe-insole IMU, targeting the ESP32-C6 microcontroller.
>>>>>>> 3da57f87 (Add ESP32 firmware + update README for public repo)

## Project Structure

```
.
├── fall_pipeline.py            # Threshold baseline + Random Forest
├── cnn_pipeline.py             # 1D-CNN training + int8 TFLite export
├── cross_position.py           # Transfer SisFall → UMAFall (WAIST / ANKLE)
├── cross_dataset_kfall.py      # Transfer SisFall → KFall
├── cross_dataset_fallalld.py   # Transfer SisFall → FallAllD
├── experiments.py              # Batch runner for multiple experiments
├── requirements.txt
│
├── report/                     # LaTeX report (auto-compiled via GitHub Actions)
│   ├── main.tex
│   ├── main.pdf                # ← viewable inline on GitHub
│   └── references.bib
│
├── ESP32_Code/                 # Firmware for ESP32-C6 + MPU-6050
│   └── sketch_aug21a/
│       └── sketch_aug21a.ino
│
└── .github/workflows/          # CI: LaTeX → PDF on every push
    └── build-pdf.yml
```

## ML Pipeline

Three models, each building on the previous:

| Model | Type | Sensitivity | Specificity | Accuracy |
|---|---|---|---|---|
| Threshold (Bourke) | Rule-based baseline | 96.7% | 76.8% | 77.5% |
| Random Forest | Classical ML (18 features) | 94.2% | 99.6% | 99.4% |
| **1D-CNN** | **Deep Learning (raw signal)** | **98.0%** | **99.7%** | **99.6%** |

All evaluations are **subject-independent** (GroupKFold / GroupShuffleSplit).

The 1D-CNN has 45,601 parameters and exports to a **64 KB** int8 TFLite model.

## Cross-Dataset Transfer Results

The trained SisFall model was evaluated on three external datasets to test generalization:

| Dataset | Position | Native Hz | Zero-Shot Se | Fine-Tuned Se |
|---|---|---|---|---|
| KFall | Lower back | 100 | **83.5%** | 96.4% |
| UMAFall | Waist | 20 | 42.2% | 92.2% |
| UMAFall | Ankle | 20 | 34.8% | 80.1% |
| FallAllD | Waist | 238 | 13.6% | 84.6% |

**Key finding:** Zero-shot transfer success depends on sensor-specific signal characteristics, not just sampling rate or measurement range. A clipping control experiment confirmed that FallAllD's ±8g range is not the cause of transfer failure. Fine-tuning consistently recovers performance across all configurations.

## Signal Processing Pipeline

```
Raw ADC → Physical units (g, °/s) → Downsample to 50 Hz
→ 2s sliding windows (50% overlap, impact-centered for falls)
→ Per-window z-normalization → Model
```

## Datasets Used

| Dataset | Subjects | Hz | Sensor Position | Role |
|---|---|---|---|---|
| [SisFall](https://doi.org/10.3390/s17010198) | 38 | 200 | Hip | Primary training |
| [KFall](https://doi.org/10.3390/s21093199) | 32 | 100 | Lower back | Transfer validation |
| [UMAFall](https://doi.org/10.3390/s17010120) | 19 | 20 | Multi-position | Position transfer |
| [FallAllD](https://doi.org/10.1109/JSEN.2019.2966342) | 15 | 238 | Multi-position | Sensor transfer |

Data not included — download from the respective sources and place in `data/`.

## Hardware Target

- **MCU:** ESP32-C6 (RISC-V, 160 MHz, WiFi 6, BLE 5)
- **IMU:** MPU-6050 via I2C (configured at ±16g, ±2000°/s, 100 Hz, DLPF enabled)
- **Deployment:** int8 TFLite model (64 KB) on 4 MB flash

## Quick Start

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

pip install -r requirements.txt

python fall_pipeline.py         # Threshold + Random Forest
python cnn_pipeline.py          # 1D-CNN + TFLite export
python cross_dataset_kfall.py   # Transfer to KFall
python cross_dataset_fallalld.py # Transfer to FallAllD
```

## Current Status

- [x] Theoretical sensor comparison (3/6/9-axis)
- [x] Sensor property analysis
- [x] Dataset evaluation (7 public datasets)
- [x] ML models: Threshold, Random Forest, 1D-CNN
- [x] Cross-dataset transfer: KFall, UMAFall, FallAllD
- [x] Clipping control experiment
- [ ] ESP32-C6 firmware + MPU-6050 integration
- [ ] Pilot foot dataset collection
- [ ] On-device TFLite deployment

## Report

The full report (German) is auto-compiled on every push and viewable at [`report/main.pdf`](report/main.pdf).

## License

Academic use only.
