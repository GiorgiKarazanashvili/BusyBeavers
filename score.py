import re, sys, json
from cfw.load import load_release
from cfw.diff import diff_releases

BC = re.compile(r"TCGA-\w\w-\w{4}-\d\d")

A, B, KEY = sys.argv[1:4]
findings = diff_releases(load_release(A), load_release(B))

mine = set()
for f in findings:
    mine |= set(f["sample_ids"])
truth = set(BC.findall(open(KEY).read()))

print("key IDs:", len(truth), "| my IDs:", len(mine))
print("found:   ", len(truth & mine), "/", len(truth))
print("MISSED (in key, not mine):", sorted(truth - mine))
print("EXTRA  (mine, not in key):", sorted(mine - truth))