# Submission checklist

Submit through the judging form by the **code freeze: Saturday, November 14, 2:15 PM ET**.

## Everyone
- [ ] **Repository** is accessible to the judges, and the submitted commit is the one you'll demo.
- [ ] **README** names your product, track, **user** and the **one workflow** they finish, plus team members and exact setup and run steps.
- [ ] **Clean start works:** a teammate cloned the repo into a fresh folder, ran `fetch.py`, and ran your tool from the README alone.
- [ ] **Event data:** judged results use the frozen TCGA-BRCA release (checksums match `sources.csv`). Any extra data is public, permissively licensed and listed.
- [ ] **One result a judge can verify:** they can trace it to samples, files and a calculation, and reproduce it.
- [ ] **One limitation a judge can inspect:** visible in the product, not only in the README.
- [ ] **Human review:** the tool shows when a person must check a result before it's used.
- [ ] **Out of scope:** no diagnosis, treatment advice, risk score or clinical claim.
- [ ] **No secrets:** no keys, tokens or private links. Running Gitleaks is a quick way to check.
- [ ] **Short demo video** link in the README.
- [ ] **Third-party code** and its licenses listed.

## Cohort Control Tower and Repair Review Desk
- [ ] Your output (Control Tower) or decisions (Repair Review Desk) pass `python format/validate.py`.
- [ ] You tested against `format/examples/control-tower-practice-B.json` or a release you built with `make_release.py`.

## AI features
- [ ] The AI runs real queries or reads real files and shows its sources; it doesn't answer from memory.
- [ ] It says clearly when the data can't answer.
- [ ] It runs with a local model or a user-supplied key.

## Research models (if you trained one)
- [ ] Held-out evaluation split by patient, slide or cell line.
- [ ] A short model card: data, split, results, and where it fails.
