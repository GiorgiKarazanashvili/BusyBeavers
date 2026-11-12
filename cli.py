import sys, json, importlib.util
from cfw.load import load_release
from cfw.diff import diff_releases
from cfw.impact import impact

A, B = sys.argv[1], sys.argv[2]
ra, rb = load_release(A), load_release(B)
print("files A:", {k: v.shape for k, v in ra.items()})
print("files B:", {k: v.shape for k, v in rb.items()})

findings = diff_releases(ra, rb)
print(f"\n{len(findings)} finding(s)")
for f in findings:
    print(" ", f["type"], f["file"], f["sample_ids"][:6], f.get("columns_changed", ""))

imp = impact(ra, rb)
spec = importlib.util.spec_from_file_location("ref", "data/tcga-brca/reference_analyses.py")
ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)

print()
for k, v in imp.items():
    print(k, "AFFECTED" if v["affected"] else "unchanged", "-", v["reason"])
    if v["affected"]:                                    # rerun only what's affected
        before = getattr(ref, k.lower())(*[x for x in ref.load(A)][: 2 if k == "A1" else 1])
        after = getattr(ref, k.lower())(*[x for x in ref.load(B)][: 2 if k == "A1" else 1])
        for r in (before, after): r.pop("sample_ids", None)
        print("   before:", before); print("   after: ", after)