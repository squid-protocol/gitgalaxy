import json
import subprocess


def get_json(rev):
    out = subprocess.check_output(["git", "show", f"{rev}:tests/golden_master_zero_dep_audit.json"])
    return json.loads(out)


old_data = get_json("HEAD~1")
new_data = get_json("HEAD")

files = new_data["6. Parsed Files (Scanned Artifacts)"]["assembly/bootos"]["Files"]
for path, new_f in files.items():
    old_f = old_data["6. Parsed Files (Scanned Artifacts)"]["assembly/bootos"]["Files"][path]
    print(f"\n{path} changes:")
    old_sigs = old_f.get("7. Structural Signatures (Net Mitigated Signals)", {})
    new_sigs = new_f.get("7. Structural Signatures (Net Mitigated Signals)", {})
    for k, v in new_sigs.items():
        if old_sigs.get(k) != v:
            print(f"  {k}: {old_sigs.get(k)} -> {v}")
