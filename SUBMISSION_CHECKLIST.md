# Submission checklist

Submit through the judging form by the **code freeze: Saturday, November 14, 2:15 PM ET**.

## Required
- [ ] **Repository** is accessible to the judges, and the submitted commit is the one you'll demo.
- [ ] **README** has a short project summary, your track, team members, and the exact setup and run steps.
- [ ] **Clean start works:** a teammate cloned the repo into a fresh folder and ran it from the README alone.
- [ ] **Official data:** you use `data/breast-cancer-wisconsin.data` and verify it against `SHA256SUMS`. No other datasets in the judged result.
- [ ] **Short demo video** link is in the README.
- [ ] **Evidence:** each main conclusion links to the check, fields and rows behind it, or is clearly marked as an interpretation.
- [ ] **Assumptions stated:** collection groups are derived from UCI's documentation, not recorded in the data.
- [ ] **Human review:** the tool shows when a person must review a result before it's used.
- [ ] **Out of scope:** no classifier, diagnosis, risk score, or clinical claim.
- [ ] **No secrets:** no credentials, tokens, private links or personal information. Running Gitleaks is a quick way to check.
- [ ] **Third-party code:** components and their licenses are listed.

## Track 1 · Cohort Firewall
- [ ] Returns one verdict: Ready, Conditional, Blocked or Insufficient Evidence.
- [ ] Re-checks when the question or file changes. Test it on `practice/`.
- [ ] Gives specific next steps for a Conditional or Blocked result.

## Track 2 · Evidence Navigator
- [ ] A judge can finish the decision scenario without the presenter's help.
- [ ] Each of the four roles sees the same underlying numbers.
- [ ] Ends with a summary: chosen option, reasons, limitations, and who reviews it.
- [ ] Usable with a keyboard, and readable without relying on color.

## Optional
- [ ] Output in the shared findings format: `examples/findings.schema.json`.
