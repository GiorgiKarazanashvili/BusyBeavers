import re, sys, time, importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # must come before cfw imports
from cfw.load import load_release
from cfw.diff import diff_releases
from cfw.impact import impact
from cfw.compare import compare


BC = re.compile(r"TCGA-\w\w-\w{4}-\d\d")
ROOT = Path("data/tcga-brca"); RAW = ROOT / "raw"
spec = importlib.util.spec_from_file_location("ref", ROOT / "reference_analyses.py")
ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)

def ref_results(d):
    c, p = ref.load(d)
    out = {"A1": ref.a1(c, p), "A2": ref.a2(c)}
    for o in out.values(): o.pop("sample_ids", None)
    return out

refA = ref_results(RAW)
print(f"{'test':28}{'found':>8}{'false':>7}{'A1':>5}{'A2':>5}{'safe':>7}{'secs':>6}")

def test_num(p):
    m = re.match(r"t(\d+)", p.name)
    return int(m.group(1)) if m else 10**9      # anything that isn't tN goes last

for d in sorted(ROOT.joinpath("releases").glob("t*"), key=test_num):
    t0 = time.time()
    _, _, findings, imp = compare(RAW, d)
    mine = {i for f in findings for i in f["sample_ids"]}
    truth = set(BC.findall((d / "CHANGES.json").read_text()))
    refB = ref_results(d)
    unsafe = [k for k, v in imp.items() if not v["affected"] and refA[k] != refB[k]]
    flag = lambda k: "Y" if imp[k]["affected"] else "-"
    print(f"{d.name:28}{len(truth & mine)}/{len(truth):<6}{len(mine - truth):>7}{flag('A1'):>5}{flag('A2'):>5}"
          f"{('ok' if not unsafe else 'BAD:' + ','.join(unsafe)):>7}{time.time() - t0:>6.1f}")
    if truth - mine: print("   MISSED:", sorted(truth - mine)[:6])
    if mine - truth: print("   EXTRA: ", sorted(mine - truth)[:6])