# Trial records pack: ClinicalTrials.gov (planned)

**One record = one dated version of a cancer trial's eligibility criteria**, plus organizer-written **fictional** cases to test them against.

**Status: planned, not yet available.** The organizers couldn't reach ClinicalTrials.gov from the environment used to build this pack, and the fictional cases need clinician review before release.

## What it will contain
- Two dated versions of each of 3 to 5 selected cancer trial records, linked to the source record and its version history.
- 30 to 50 **fictional** cases, each a short profile with dated facts. Some are deliberately incomplete (for example, a month and year but no day).
- An answer key, kept private, saying which cases move in, move out, or need more evidence between versions.

## The exercise
Build an assistant that compares eligibility language between versions and shows which fictional cases move in, move out, or need more evidence, with the exact clause behind each change.

A change in the registry record shows that the public record changed. Call it a formal protocol amendment only when supporting documentation confirms it.

## What it can't do
The cases are fictional: **never use or add real patient records.** Trial eligibility here is a research exercise, not screening real people for trials.

## To make it ready (organizers)
1. Pull version histories for about 10 recruiting breast cancer trials (the `cthist` R package works) and keep 3 to 5 with meaningful eligibility changes.
2. Write the fictional cases and the key; have a clinician review both.
3. Pin checksums of the saved record versions in `sources.csv`.
