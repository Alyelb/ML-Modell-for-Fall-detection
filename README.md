# Sensor-Based Fall Detection with Machine Learning

**Studienprojekt 2** — TH Mittelhessen (Fachbereich 12)  
Author: Aly Elbermawy · Supervisor: Prof. Dr. Kovalev · Industry Partner: TrackTech GmbH / Clever-Sole

## Overview

TinyML pipeline for fall detection using a 6-axis IMU (MPU-6050) embedded in a shoe insole, targeting the ESP32-C6 microcontroller.

## Pipeline

| Stage | Model | Sensitivity | Specificity | Accuracy |
|-------|-------|-------------|-------------|----------|
| 1 | Threshold (Bourke) | 0.967 | 0.768 | 0.775 |
| 2 | Random Forest | 0.942 | 0.996 | 0.994 |
| 3 | **1D-CNN** | **0.980** | **0.997** | **0.996** |

All results are **subject-independent** (tested on subjects not seen during training).

## Files

- `fall_pipeline.py` — Threshold baseline + Random Forest (scikit-learn, no TensorFlow needed)
- `cnn_pipeline.py` — 1D-CNN training + int8 TFLite export (TensorFlow/Keras)
- `requirements.txt` — Python dependencies

## Quick Start

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python fall_pipeline.py        # Threshold + RF baseline
python cnn_pipeline.py         # 1D-CNN + TFLite export
```

## Dataset

Trained on [SisFall](https://doi.org/10.3390/s17010198) (4505 recordings, 38 subjects, 200 Hz, ±16g).  
Data not included — download from SISTEMIC Lab and place in `data/SisFall_dataset/`.

## Hardware Target

- ESP32-C6 + MPU-6050 (external, I2C)
- int8 quantized model: **64 KB** (fits easily in 4 MB flash)
- Inference: < 50 ms per 2-second window on ESP32

## License

Academic use only (Studienprojekt).
