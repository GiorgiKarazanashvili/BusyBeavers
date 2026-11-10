# Evidence Navigator — five project ideas

**The track in one line:** help a person reach a decision they can trace back to the data, and see where the evidence stops.

These are starting points, not assignments. Combine them, change them, or build something else. Whatever you build, give judges **one result they can verify** and **one limitation they can inspect**.

You'll receive the findings records and decision scenario at kickoff. Until then, build against `examples/findings.example.json` and `data/wisconsin_readable.csv` (use `source_row` to link back to the official file).

---

## 1 · Evidence Passport
**Problem:** A number on a slide travels without its evidence. Reviewers can't tell how it was calculated or what it rests on.
**Build:** A view where every headline number opens a "passport": the calculation, the exact source rows, the data version and checksum, known limitations, and who must review it.
**Show judges:** A judge clicks the headline figure and reproduces it from the passport without your help.
**Tools:** Streamlit or Gradio; pandas.
**Effort:** Good first project. Strong on *Understanding the evidence* and *Working tool*.

## 2 · Decision Room
**Problem:** A data engineer, a researcher, a data-use reviewer and a program leader need different detail about the same decision, and they often end up with different versions of the facts.
**Build:** One tool with four role views built from the same findings. It ends in a recorded decision (proceed, fix a problem, narrow the question, or stop) with reasons, limitations and the reviewer named.
**Show judges:** Switch roles live and show the underlying numbers never change. Then export the decision summary.
**Tools:** Streamlit, Gradio or a small web app; a JSON file for the findings.
**Effort:** Medium. Strong on *Role fit* and *Decision usefulness*.

## 3 · Pooled-vs-Grouped Explainer
**Problem:** A single pooled figure can hide differences between groups, and non-specialists can't see that from a table.
**Build:** An interactive chart that lets a reviewer switch between the pooled figure and group-level results, always showing denominators, and explains in plain language when the pooled figure is misleading.
**Show judges:** A non-specialist judge uses it for 30 seconds and explains back what the pooled figure hides.
**Tools:** Altair, Plotly or Observable; check accessibility with axe-core or Lighthouse.
**Effort:** Medium. Strong on *Usability and accessibility* and *Communication*.

## 4 · Conflict Resolver
**Problem:** Analysts often disagree, for example one says a fix resolves the problem and another says it doesn't. Reviewers need to see what each claim rests on.
**Build:** A tool that takes two or more findings that point different ways, shows the evidence behind each side by side, and says what extra evidence would settle it.
**Show judges:** Add a new, conflicting finding live and show the tool place it next to the existing evidence without changing the facts.
**Tools:** Streamlit or Gradio; the shared findings format for input.
**Effort:** Medium to hard. Strong on *Safety and uncertainty* and *Understanding the evidence*.

## 5 · Grounded Reviewer Assistant
**Problem:** People want to ask questions in plain language, but AI assistants make things up.
**Build:** An assistant that answers only from the findings and the data, cites source rows for every answer, and says "the evidence doesn't support that" when it can't. It must work without secrets in the repo, so use a local model or let users bring their own API key.
**Show judges:** Ask one supported question (answer with citations) and one unsupported question (a clear refusal).
**Tools:** any LLM or local model; a retrieval step over `findings.json`; logging of what it cited.
**Effort:** Hard. Strong on *Safety and uncertainty* and *Role fit*. Make sure a judge can run it without your API key.

---

**Pairing with Cohort Firewall:** if your tool reads the shared findings format (`examples/findings.schema.json`), you can open a Cohort Firewall team's results directly. That's optional, but it makes a strong demo.

**Out of scope for every idea:** classifiers, diagnosis, risk scores or clinical claims.
