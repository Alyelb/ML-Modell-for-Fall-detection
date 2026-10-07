# Sensor-Based Fall Detection with Machine Learning

TinyML fall detection for a shoe-insole IMU, targeting the ESP32-C6.
Master's project (Studienprojekt 2), TH Mittelhessen.

The project trains on public fall datasets, quantifies how well such
models transfer to a foot-mounted sensor, and deploys the result to real
hardware.

---

## Repository structure

```
.
├── fall_lib.py              Shared library — all dataset loaders,
│                            windowing, models, evaluation, voting,
│                            cross-validation. Single source of truth;
│                            every notebook imports it.
├── fall_pipeline.py         Standalone threshold + Random Forest
├── cnn_pipeline.py          Standalone 1D-CNN training
├── requirements.txt
│
├── notebook/                One notebook per report section
│   ├── 01_basismodelle      Threshold, RF, CNN on SisFall + TFLite export
│   ├── 02_transfer          KFall, UMAFall, FallAllD + clipping control
│   ├── 03_fehlalarme        False-positive test, N-of-M voting
│   ├── 04_achsen            3-axis vs 6-axis ablation + UniMiB-SHAR
│   ├── 05_zielgruppe        WEDA-FALL, elderly vs younger subjects
│   ├── 06_progressiv        Progressive fine-tuning (single split)
│   ├── 07_progressiv_cv     Same, 5-fold cross-validated
│   ├── 08_hardneg_cv        Hard-negative weighting, cross-validated
│   ├── 09_pilotdaten        Recordings from the target hardware,
│   │                        base vs. lower-limb model
│   ├── 10_fussdomaene       Placement curve (9 body positions + foot),
│   │                        training with leg/foot data
│   └── 11_orientierung_matrix  Sensor orientation (mirror/rotation) and
│                            training-chain matrix incl. augmentation
│
├── firmware/                Arduino sketches for ESP32-C6 + MPU-6050/6500
│   ├── CleverSole/          Full detector: steps, inference, voting,
│   │                        deep sleep, BLE
│   ├── SensorLive/          Live sensor readout (serial + BLE UART)
│   ├── DatenLogger/         100 Hz recorder to internal flash
│   └── sketch_aug21a/       First I2C test sketch
│
├── report/                  LaTeX report, auto-compiled on every push
│   ├── main.tex
│   ├── main.pdf             ← viewable inline on GitHub
│   └── references.bib
│
└── .github/workflows/       CI: LaTeX → PDF
```

Datasets and trained models are not tracked. Download the datasets from
their sources and place them under `data/`.

---

## Signal processing

Identical in training and on the device:

```
Raw ADC → physical units (g, °/s) → downsample to 50 Hz
→ 2 s windows (100 × 6), impact-centred for falls
→ per-window, per-channel z-normalisation → model
```

The downsampling filter matters: a signal decimated from 200 Hz to
20 Hz keeps 96.8 % sensitivity, while one natively recorded at 20 Hz
drops to 34.0 %. Anti-aliasing preserves the impact envelope; without
it the peak is lost. This is why the firmware runs the sensor at
≥ 100 Hz with its internal low-pass filter enabled and decimates in
software.

---

## Baseline models (SisFall, subject-independent)

| Model | Sensitivity | Specificity | Accuracy |
|---|---|---|---|
| Threshold (Bourke, 2.8 g) | 96.7 % | 82.9 % | 83.2 % |
| Random Forest (18 features) | 92.7 % | 99.6 % | 99.4 % |
| **1D-CNN** | **98.7 %** | **99.8 %** | **99.8 %** |

The CNN has 61,601 parameters and exports to a 77.6 KB int8 TFLite
model.

The Random Forest uses 18 rotation-invariant features derived from the
acceleration and angular-rate magnitudes — the sensor's orientation
inside the shoe does not affect them, which matters when the insole
can be inserted either way. Verified numerically: after a random 3-D
rotation, 100 % of predictions are unchanged.

Gyroscope features carry **62.3 %** of total feature importance, with
`gyr_std` ranking first at 23.6 %. Since features are split evenly
between the two sensors, 50 % would mean no preference — the observed
value supports the six-axis recommendation.

---

## Cross-dataset transfer

| Dataset | Position | Native Hz | Range | Zero-Shot Se | Fine-Tuned Se |
|---|---|---|---|---|---|
| KFall | Lower back | 100 | ±16 g | **100.0 %** | 100.0 % |
| UMAFall | Waist | 20 | ±16 g | 43.8 % | 91.7 % |
| UMAFall | Ankle | 20 | ±16 g | 19.4 % | 27.8 % |
| FallAllD | Waist | 238 | ±8 g | 12.7 % | 69.8 % |

**Zero-shot success is not explained by any single factor.** FallAllD
has the highest sampling rate of all yet the worst zero-shot result. A
control experiment ruled out the measurement range: clipping SisFall
synthetically to ±8 g, ±4 g and even ±2 g leaves the results
essentially unchanged, because only 0.5 % of windows ever exceed 8 g.
What remains is the sensor's own signal characteristics — internal
filtering, noise, response time. Fine-tuning recovers performance in
every case.

---

## False alarms

Tested on ankle-mounted ADL recordings only, so every positive is by
definition a false alarm:

| | Rate | Per hour |
|---|---|---|
| Overall | 2.61 % | ~94 |
| Jogging | 15.44 % | |
| Walking | 3.65 % | |
| Clapping | 0.55 % | |

The pattern follows ground contact: each heel strike produces a short,
steep acceleration pulse that resembles an impact. The model is not
uncertain about these — it assigns them probability 1.000 — so raising
the decision threshold alone does not solve it.

### Temporal voting

Requiring N of the last M windows to be positive (0.2 s step) cuts
false alarms by 84 % but costs 55 % of sensitivity on this data. A
coarser 1.0 s step fails outright: the impact then falls inside a
single window, so any rule with N ≥ 2 is mathematically unable to
fire.

Voting also **depends on domain adaptation**. Going from 1-of-1 to
5-of-7 costs the unadapted model 88 % of its sensitivity but the
fine-tuned model only 55 %. An unadapted model emits scattered,
isolated positives that the rule discards; an adapted one emits a
contiguous block around the impact. Order matters: fine-tune first,
then vote.

---

## Cross-validated findings

Two questions gave misleading answers on a single split and were
repeated with 5-fold subject-independent cross-validation and paired
comparison.

**Progressive fine-tuning — confirmed.** Adapting via an intermediate
dataset beats direct adaptation:

| Strategy | Sensitivity (95 % CI) |
|---|---|
| Zero-shot | 25.5 % [19.3; 32.8] |
| Direct: SisFall → target | 42.7 % [35.2; 50.5] |
| After KFall stage only | 17.2 % [12.1; 23.9] |
| **Progressive: SisFall → KFall → target** | **52.2 % [44.5; 59.9]** |

Paired difference +9.9 pp (95 % CI [+5.1; +14.7]), better in 5 of 5
folds, specificity unchanged. Note that the intermediate stage on its
own makes things *worse* — it generalises the representation rather
than improving it.

**Hard-negative weighting — rejected.** Up-weighting high-impact ADL
windows trades sensitivity for specificity: −8.2 pp Se and +2.0 pp Sp,
both significant, both consistent across all five folds. In absolute
terms, 166 fewer false alarms but 23 more missed falls. For fall
detection that is the wrong direction: voting can suppress false
alarms downstream, but nothing recovers a missed fall.

Plain fine-tuning raised sensitivity from 12.4 % to 75.2 % — domain
adaptation outperforms every add-on measure tested.

---

## Axis ablation

Three models, identical architecture, split and hyperparameters; only
the input channels differ.

| Variant | Sensitivity | Specificity | Parameters |
|---|---|---|---|
| 6 axes (acc + gyro) | 98.3 % | 99.9 % | 61,601 |
| 3 axes (acc only) | 98.0 % | 99.8 % | 61,121 |
| 3 axes (gyro only) | 93.3 % | 99.3 % | 61,121 |

On SisFall the gyroscope contributes only 0.3 pp — but both variants
sit near the ceiling, where small differences vanish, and the position
is the waist, where walking is smooth. At the foot, where acceleration
is saturated by heel strikes, the picture may differ.

External check on UniMiB-SHAR (accelerometer only, ±2 g smartphone):
zero-shot 21.3 %, fine-tuned 95.9 %.

---

## Target group

WEDA-FALL includes 11 subjects aged 77–95 alongside 14 younger ones —
every other dataset used here is predominantly young. The older group
performed no falls for safety reasons, so only the false-alarm rate is
assessable, and only on the six activities both groups performed.

Aggregated, the older group produces 3.8× more false alarms. Broken
down by movement, almost all of it comes from one activity:

| Movement | Older | Younger |
|---|---|---|
| Walking | 0.70 % | 0.41 % |
| Stairs | 0.81 % | 1.98 % |
| **Clapping** | **25.51 %** | **2.54 %** |

Walking and stair climbing — the movements that matter for an insole —
are comparable. There is no evidence that everyday movements of older
people are inherently harder to classify. The aggregate figure alone
would have hidden this.

---

## Foot domain (in progress)

The central open question: how well does a model trained on trunk data
transfer to a foot-mounted sensor? No public dataset contains falls
recorded at the foot, so the question is answered by combining
sources that each cover one aspect (notebook `10_fussdomaene`,
report chapter 6).

**What the foot signal looks like.** Two insole datasets recorded with
the same commercial insole IMU (Moticon OpenGo), no falls, no relevant
clipping:

| Dataset | Duration | median \|a\| | 99th pct. \|a\| |
|---|---|---|---|
| Smart-Insole v1.0 | 92 min | 1.04 g | 5.1 g |
| ImbalanSense | 4.7 h | 1.05 g | 4.4 g |

Ordinary gait at the sole exceeds 4 g in one sample out of a hundred,
and single axes reach ±13–16 g without any fall. A fixed impact
threshold is not viable at the foot, and ±16 g is required there even
though ±8 g suffices at the waist.

**Partner recordings.** The existing insole prototype records at 10 Hz
with ±2 g and no gyroscope: 16.7 % of all samples are clipped, and the
magnitude tops out at exactly √3 · 2 g = 3.46 g. Unsuitable for
training; the project's own logger (`firmware/DatenLogger`) records at
100 Hz, ±16 g, ±2000 °/s.

**Placement curve** (CAPPIMU, same 731 falls seen from nine positions,
base model zero-shot):

| Position | Left | Right |
|---|---|---|
| Upper arm | 6.2 % | 54.6 % |
| Wrist | 9.9 % | 51.8 % |
| Shin | 16.6 % | 39.5 % |

Chest 48.4 %, head 28.4 %, pocket 23.0 %. There is no monotonic decline
with distance from the trunk — **the side matters more than the
position.** Sensors on the left and right are worn mirror-imaged, so
what changes is the axis orientation, and the CNN processes axes
individually. Left and right insoles are mirror images too: a model
for the sole must be orientation-invariant (rotation/mirror
augmentation or magnitude features).

At every position except the head, the 99th percentile of everyday
peaks exceeds the median fall peak — at the shin ~10 g vs ~3 g.

**False alarms at the sole** (base model): 161/h (ImbalanSense),
290/h (Smart-Insole) — 373/h for elderly, 302/h for Parkinson's,
215/h for younger adults, all performing the same walking tests.

**Lower-limb training** (5-fold, subject-independent):

| Variant | Se shin (95 % CI) | FP/h ImbalanSense | FP/h Smart-Insole (external) |
|---|---|---|---|
| A base (SisFall) | 28.0 % [25.8; 30.4] | 161 | 290 |
| K + KFall | 22.6 % [20.5; 24.8] | 51 | 65 |
| B1 + shin falls | 83.9 % [81.9; 85.7] | 412 | 508 |
| **B2 + shin falls + sole ADL** | **84.5 % [82.5; 86.2]** | **18** | **53** |

Shin falls lift sensitivity by +61 pp (5/5 folds) but triple the
false alarms at the sole: the model learns "strong leg impulse = fall",
and every heel strike is one. Adding sole recordings without falls
cuts sole false alarms by >95 % (significant, 5/5 folds) **at no cost
in sensitivity** (+0.6 pp, n.s.) — unlike hard-negative weighting,
which cost 8 pp. Adding target-domain data works; re-weighting
existing data does not.

**Pilot recordings, own hardware** (ESP32-C6 + MPU-6500, one person,
lower-limb model, zero-shot): ankle right 83 % / left 77 % window
sensitivity, 100 % / 95 % of falls detected within ±1 s; walking and
jogging 0–4 false windows out of ~170. Remaining false alarms come from
sitting down, sitting hard and picking things up — movements where the
leg itself goes horizontal. At the ankle a fall peaks at only
2.6–2.9 g, below jogging and jumping (8–12 g); impacts are therefore
located via the subsequent lying phase, not the highest peak.

**Sensor orientation.** Rotating the pilot recordings in software:
mirroring and rotation about the leg axis barely matter (model was
trained on both shins), but arbitrary 3-D rotations drop sensitivity to
as low as 14 %. The mounting orientation in the insole is part of the
model specification. Notebook 11 tests rotation augmentation.

53 false alarms per hour on unseen people is still too many for an
alarm system; temporal voting and long-lie detection remain necessary.
No source contains falls *at the sole* — that gap is what the pilot
recordings address (pending).

---

## Datasets

| Dataset | Subjects | Hz | Position | Role |
|---|---|---|---|---|
| [SisFall](https://doi.org/10.3390/s17010198) | 38 | 200 | Hip | Primary training |
| [KFall](https://doi.org/10.3390/s21093199) | 32 | 100 | Lower back | Transfer, intermediate stage |
| [UMAFall](https://doi.org/10.3390/s17010120) | 19 | 20 | 5 positions | Position transfer, FP test |
| [FallAllD](https://doi.org/10.1109/JSEN.2019.2966342) | 15 | 238 | 3 positions | Sensor transfer |
| [UniMiB-SHAR](https://doi.org/10.3390/app7101101) | 30 | 50 | Pocket | 3-axis check |
| WEDA-FALL | 25 | 50 | Wrist | Target group |
| [CAPPIMU](https://github.com/quiqi/CAPPIMU) | 30 | 50 | 9 positions incl. shin | Placement curve, leg training |
| [ImbalanSense](https://doi.org/10.5281/zenodo.20924766) | 40 | 100 | Insole | Foot ADL, training + FP test (CC BY 4.0) |
| [Smart-Insole v1.0](https://doi.org/10.3390/s21082821) | 29 | 100 | Insole | External FP test only (non-commercial licence) |

Checked and not used: AnkFall (ankle, requested, pending),
HuGaDB (foot, but ±2 g), UP-Fall (ankle, ≈18 Hz),
MobiAct (pocket, adds nothing over the above).

Two documentation discrepancies worth noting for anyone reusing these
datasets:

- **KFall fall tasks are T20–T34, not T22–T36.** The bundled label
  files list F01 as task 20; the annotated `Fall_impact_frame` matches
  the measured acceleration peak at T20 to within one sample, and not
  at T22. The earlier assumption mislabelled 606 of 5075 recordings.
- **The Smart Insole Database (GitHub) contains no IMU channels**
  despite its documentation. Not to be confused with the
  *Smart-Insole Dataset v1.0* (HMU BMI Lab), which does. All 30 published files hold only 38 CapSense pressure
  electrodes and force-plate readings.

No public dataset contains falls recorded from a foot-mounted IMU.
That gap is what this project addresses.

---

## Hardware

- **MCU:** ESP32-C6 (RISC-V, WiFi 6, BLE 5)
- **IMU:** MPU-6050 or MPU-6500 via I2C, ±16 g, ±2000 °/s, 100 Hz,
  internal DLPF enabled
- **Model:** int8 TFLite, 77.6 KB on 4 MB flash

The firmware auto-detects the sensor: `WHO_AM_I` 0x68 is an MPU-6050,
0x70 an MPU-6500, 0x71 an MPU-9250. This matters because the MPU-6500
has a separate accelerometer filter register (0x1D) that the 6050 does
not — left unset, its filter stays at 460 Hz and the anti-aliasing
before decimation is missing.

### Firmware parameters

| Parameter | Value | Status |
|---|---|---|
| Sensor ODR | ≥ 100 Hz, DLPF on | established |
| Measurement range | ±16 g | established |
| Model input | 100 × 6 (2 s @ 50 Hz) | established |
| Inference interval | 200 ms | established |
| Voting window M | 3–7 | provisional |
| Voting threshold N | 2–5 | provisional |
| Decision threshold | 0.5–0.9 | provisional |

The upper four follow from physics and the control experiments and
hold regardless of domain. The lower three describe a
sensitivity/false-alarm trade-off that depends on the adapted model;
no satisfactory operating point was found on public ankle data, so
they must be set on pilot recordings from the target hardware.

---

## Quick start

```bash
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

Notebooks run in Colab and fetch `fall_lib.py` from this repository.
Run `01_basismodelle` first — it produces the model the others load.

For the firmware: Arduino IDE, board *ESP32C6 Dev Module*, partition
scheme *Huge APP*, and `USB CDC On Boot: Enabled` (without it the
serial output goes to the UART pins instead of USB).

---

## Status

- [x] Sensor comparison (3/6/9 axes)
- [x] Sensor property analysis
- [x] Dataset evaluation
- [x] Threshold, Random Forest, 1D-CNN
- [x] Cross-dataset transfer with control experiments
- [x] False-alarm analysis and temporal voting
- [x] Cross-validated method comparison
- [x] Firmware: sensor, step detection, deep sleep, BLE
- [ ] TFLite deployment on device
- [x] Foot-domain datasets: loaders and evaluation notebook
- [x] Placement curve and lower-limb training (notebook 10)
- [x] Pilot recordings at waist and both ankles (target hardware)
- [ ] Pilot recordings in the insole / on top of the foot
- [ ] Orientation test and training matrix (notebook 11)
- [ ] Voting parameters from pilot data
- [ ] Long-lie detection

## Report

The full report (German) compiles automatically on every push:
[`report/main.pdf`](report/main.pdf).

## License

Academic use only.
