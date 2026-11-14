# Cohort Firewall

**Product:** Cohort Firewall, for the Cohort Control Tower track
**Team:** Busy Beavers: [Giorgi Karazanashvili], [Daniel Matuzka], [Hoang Anh Khoi Le], [Viriyananda Susilo Tjiong]

## Who it's for and what they finish

**User:** a research engineer responsible for a dataset that gets new releases.

**Workflow:** connect two releases, see what changed (sample swaps, duplicate profiles under new
IDs, samples that appeared or disappeared, coverage lost by subgroup, missing measurements),
and rerun only the analyses those changes affect. The tool writes a validated `findings.json`
(format v0.2) with findings, before/after analysis results, and proposed repairs.

**Example:** on the practice release, the sample count is unchanged but membership changed.
The tool flags the swap and the replaced samples, marks A1 (ER-alpha protein by clinical ER
status) as affected and reruns it, and leaves A2 (RNA subtype mix) alone with the reason.

Research use only: no diagnosis, treatment advice, risk score or clinical claim.

**Demo video:** [link]

The organizers' original challenge text is in [CHALLENGE_README.md](CHALLENGE_README.md).
API and dashboard details are in [CONTROL_TOWER_README.md](CONTROL_TOWER_README.md).

## Run it

Python [3.12] recommended. Run everything from the repo root.

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python data/tcga-brca/fetch.py                  # release A (includes a 64 MB RNA file)
    python data/tcga-brca/make_release.py           # practice release B
    python data/tcga-brca/make_release.py --verify  # should print: practice-B matches the published release

Start the API and the dashboard in two terminals (venv active in both):

    uvicorn backend.main:app --port 8000
    streamlit run frontend/app.py                   # opens http://localhost:8501

In the dashboard pick `baseline` and `practice-B`, then press Compare.

Or from the command line, with the API running:

    curl -s -X POST localhost:8000/api/compare -H "content-type: application/json" \
         -d '{"release_a":"baseline","release_b":"practice-B","wait":true}'

`findings.json` is written to `outputs/runs/<run id>/` and checked by the organizers'
`format/validate.py`. If validation fails, the rejected file is kept as `findings.invalid.json`
in the same folder.

## What you should see on practice-B

- Two events in the protein file: a swap of two samples' profiles, and 5 samples replaced by
  copies of other samples under new IDs. The sample count is unchanged while membership changed.
- A1 (ER-alpha protein by clinical ER status): affected, rerun, before/after numbers shown.
- A2 (RNA subtype mix of primary tumors): left alone, with the reason.

## Try a sealed envelope

    python envelopes/unseal.py practice orange meadow pilot lantern

Then compare `baseline` with `envelope-practice` in the dashboard. Envelopes ship without an RNA
file; its absence is treated as normal.

## Check it yourself

    pytest -q                          # app tests
    python scripts/make_tests.py       # builds regression releases t0-t12 with known answers
    python scripts/make_hard_tests.py  # builds harder ones t13-t21 (clinical swap, ID drift, noise-only...)
    python scripts/scorecard.py        # per release: planted changes found, false findings, analyses affected, safety check

In the scorecard, `found` is planted sample IDs reported, `false` is reported IDs not planted,
`A1`/`A2` show whether we reran each analysis, and `safe` is `ok` when every analysis we left
alone gives identical numbers under the organizers' reference code.

## How it works

| Part | Role |
|---|---|
| `cfw/load.py` | Reads every release file and orients matrices so samples are rows |
| `cfw/compare.py` | Skips files whose bytes are identical, loads only what differs |
| `cfw/fingerprint.py`, `cfw/diff.py` | Per-sample hashes with a numeric tolerance re-check; finds swaps, duplicates, adds/removes, missingness |
| `cfw/impact.py` | The exact slice each analysis reads, compared between releases |
| `detection/engine.py` | Turns that into v0.2 findings, reruns affected analyses, proposes repairs and a verdict |
| `backend/`, `frontend/` | API, packaging and validation, dashboard (no detection logic) |

## Known limits

- Impact mapping is written for A1 and A2 on TCGA-BRCA. A new analysis needs a new slice in `cfw/impact.py`.
- One replace-with-duplicates event is reported as three findings (duplicate, added, removed).
- ID format changes (case, trailing whitespace) are reported as removed plus added samples.
- A verdict of `Conditional` means at least one finding touches an analysis; repairs are proposals only and no release file is modified.
- No AI summary yet.

## Human review and limitations

Every finding carries `needs_human_review` and a `limitation` field, and repairs are proposals
only: no release file is modified. [Check that the dashboard shows these, then say where.]

## Third-party code

pandas, numpy (BSD-3-Clause); FastAPI, uvicorn, httpx (BSD / MIT); Streamlit, requests (Apache-2.0);
pytest (MIT). Data: TCGA-BRCA from the UCSC Xena hub, frozen release (checksums in `data/tcga-brca/sources.csv`).