# 3-, 6- and 9-Axis Sensor Systems for Fall Detection — Comparative Study

LaTeX source and supporting materials for the Studienprojekt 2 thesis by Aly Elbermawy (TH Mittelhessen, 2026). This repository contains the thesis source (main.tex), the bibliography (references.bib) and supporting notes on dataset selection and sensor trade-offs for an insole-based fall-detection system.

## Project summary
Falls are a major health risk for older adults. This study analyzes whether adding gyroscopes (6-axis) or magnetometers (9-axis) improves automatic fall detection over accelerometer-only systems, with special attention to an insole-mounted sensor form factor. The conclusion recommends a 6-axis IMU as the practical sweet spot for insole-based fall detection.

## Contents
- `main.tex` — LaTeX source for the thesis (title page, chapters, tables, figures).
- `references.bib` — BibTeX bibliography used by the thesis.
- (future) `data/` — local dataset excerpts or metadata (not included here; see dataset links below).
- `README.md` — this file.

## Build (produce PDF)
Requirements: a LaTeX distribution (TeX Live / MiKTeX) with packages used in the source.

Typical build steps:
1. pdflatex main
2. bibtex main
3. pdflatex main
4. pdflatex main

This sequence produces `main.pdf`. If you use an IDE (TeXstudio, Overleaf) you can compile there as well.

## Dependencies / LaTeX packages (high level)
The document uses standard packages: `inputenc`, `fontenc`, `babel`, `geometry`, `setspace`, `amsmath`, `graphicx`, `booktabs`, `natbib`, `hyperref`, `acronym`, `fancyhdr`, `titlesec`. Ensure your TeX distribution provides these packages.

## Datasets and links referenced in the thesis
The thesis evaluates several public datasets; the primary recommendation for ML development is SisFall and a complementary use of KFall. Please retrieve datasets from the official project pages and heed their licensing and usage requirements:
- SisFall — SISTEMIC, Universidad de Antioquia (CC BY 4.0) — project page
- KFall — KAIST — project page
- MobiAct / MobiFall, UMAFall, FallAllD, UniMiB SHAR, WEDA-FALL — see references in `references.bib` for links and access notes

Note: raw datasets are not included in this repository. When using datasets, follow the dataset owners' license terms and citation requirements.

## Recommended metadata for the repository
- Short description: `Sensor-based fall detection — comparative study and dataset selection (LaTeX thesis + bibliography)`
- Topics: `fall-detection`, `inertial-sensors`, `imu`, `insole`, `thesis`, `latex`, `machine-learning`, `datasets`, `sisfall`, `kfall`

## License
Choose a license appropriate for your goals:
- If you want maximum reuse for code and scripts: MIT or BSD.
- If you want to allow academic reuse but limit commercial use of the thesis text: CC BY-NC (Creative Commons Attribution-NonCommercial).
- If you want full academic reuse with attribution: CC BY (Creative Commons Attribution).

I have not added a license file yet — please tell me which license you prefer and I will add it.

## Citation
If you use the thesis or the analysis in this repository, please cite:
Aly Elbermawy (2026). "3-, 6- and 9-Axis Sensor Systems for Fall Detection: A Comparative Study." Studienprojekt 2, Technische Hochschule Mittelhessen. (LaTeX source and bibliography included in this repository)

A BibTeX entry you can add to papers (example):
```bibtex
@misc{elbermawy2026fallstudy,
  author = {Aly Elbermawy},
  title  = {3-, 6- and 9-Axis Sensor Systems for Fall Detection: A Comparative Study},
  year   = {2026},
  note   = {Studienprojekt 2 — Technische Hochschule Mittelhessen. Repository: https://github.com/<your-account>/<repo-name>}
}
```

## Contributing
This repository currently holds the thesis source. If you'd like to continue development (ML experiments, data preprocessing, code), consider:
- Creating branches for code vs. thesis text (`thesis`, `ml`, `data`).
- Adding a `data/README.md` describing which datasets are used and how to obtain them.
- Adding notebooks or scripts under `notebooks/` or `src/` and a `requirements.txt` for Python dependencies.
- Adding CI to build the PDF automatically on push (I can prepare a GitHub Actions workflow for that).

## Contact
Author: Aly Elbermawy — (add your email or preferred contact)
Supervisor: Dr. Kovalev

---

If you want, I can:
- create the repository on GitHub and push these files (I will need the repository name and whether it should be public/private),
- add a LICENSE file you choose,
- add a GitHub Actions workflow that builds the LaTeX into a PDF on each push.
