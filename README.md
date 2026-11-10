# OncoSys AI Healthcare Hackathon — event data

**Dataset:** Breast Cancer Wisconsin (Original), UCI Machine Learning Repository. Frozen for this event as `v1.0.0`.

**This is a data-readiness exercise. Classifiers, diagnosis and clinical claims are out of scope.**

## The shared question
A reviewer wants to report one malignant share across all eight collection groups. Should they report the pooled figure, show group results alongside it, or pause? Show the evidence behind your decision and explain what the data can support.

| Track | Brief | What you build |
|---|---|---|
| **Cohort Firewall** | `track1-cohort-firewall/` | A tool that audits the data for the question and returns Ready, Conditional, Blocked or Insufficient Evidence, with the evidence behind it |
| **Evidence Navigator** | `track2-evidence-navigator/` | An interactive tool that helps four kinds of users understand the findings and make the publishing decision |

The full rules and the scoring rubric for each track are in the challenge package.

## Files
| Path | What it is |
|---|---|
| `data/breast-cancer-wisconsin.data` | 699 rows, no header row; `?` means missing |
| `data/breast-cancer-wisconsin.names` | UCI's documentation. Read sections 4, 7 and 8. |
| `SHA256SUMS` | Checksums. Verify before you start. |
| `starter/starter.ipynb` | Loads the data, verifies checksums and derives collection groups |

## Quick start
```bash
sha256sum -c SHA256SUMS
```
```bash
pip install pandas jupyter
```
```bash
jupyter notebook starter/starter.ipynb
```

## Source and citation
Collected by Dr. William H. Wolberg, University of Wisconsin Hospitals, Madison, 1989–1991; donated to UCI on 15 July 1992.
Cite: Wolberg, W. (1990). *Breast Cancer Wisconsin (Original)* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5HP4Z
Dataset license: [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/), as listed on the [UCI dataset page](https://archive.ics.uci.edu/dataset/15). This license statement applies to the UCI dataset. The starter notebook derives collection groups from UCI’s documented row boundaries; those labels are not fields in the source data.

The data is de-identified but patient-derived. Don't attempt to re-identify anyone or link it to other sources.
