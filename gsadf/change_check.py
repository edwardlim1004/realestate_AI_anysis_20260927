"""Skip expensive simulations if the verified official quarterly records did not change."""
import argparse
import hashlib
import json
import os
from pathlib import Path
SERIES=("real_hpi","pir","ptr")
def fingerprint(root):
    root=Path(root);h=hashlib.sha256()
    for key in SERIES:
        path=root/f"korea_{key}_quarterly.csv"
        if not path.is_file(): raise ValueError("Missing official observations: "+key)
        data=path.read_bytes()
        if not data: raise ValueError("Empty official data: "+key)
        h.update(key.encode()+b"\0"+hashlib.sha256(data).digest())
    return h.hexdigest()
def decide(root):
    root=Path(root)
    old=(root/".previous_series_sha256").read_text(encoding="ascii").strip() if (root/".previous_series_sha256").exists() else None
    now=fingerprint(root)
    changed=old!=now
    print("GSADF_SOURCE_"+("CHANGED" if changed else "UNCHANGED"),now[:16])
    return changed
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--data-dir",default="gsadf/data");a.add_argument("--status-path",default="gsadf/audit/status.json");args=a.parse_args()
    changed=decide(args.data_dir)
    outfile=os.environ.get("GITHUB_OUTPUT")
    if outfile:
        with open(outfile,"a",encoding="utf-8") as f:f.write("changed="+str(changed).lower()+"\n")
    if not changed:
        status=Path(args.status_path);status.parent.mkdir(parents=True,exist_ok=True)
        status.write_text(json.dumps({"status":"NO_OFFICIAL_DATA_CHANGE","compositePromoted":False},indent=2),encoding="utf-8")
