#!/usr/bin/env python3
"""
Regenerate employee master JSON from data/emp_master_data.csv.

Primary output (for deploy): <repo>/emp_master_data.json (cwd / app root).
Also writes data/emp_master_data.json for backward compatibility.

Run from repo root: python scripts/build_emp_master_json.py
"""
import json
import os
import sys

import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import hr_attendance as hr  # noqa: E402

CSV_PATH = os.path.join(_ROOT, "data", "emp_master_data.csv")
JSON_PRIMARY = os.path.join(_ROOT, "emp_master_data.json")
JSON_LEGACY = os.path.join(_ROOT, "data", "emp_master_data.json")


def main():
    if not os.path.isfile(CSV_PATH):
        print(f"Missing {CSV_PATH}", file=sys.stderr)
        sys.exit(1)
    raw = pd.read_csv(CSV_PATH, dtype=str, encoding="utf-8-sig")
    raw.columns = [str(c).strip() for c in raw.columns]
    emp = hr._standardize_master_df(raw)
    if emp.empty:
        print("Standardized master is empty — check CSV columns.", file=sys.stderr)
        sys.exit(1)
    records = emp.to_dict(orient="records")
    with open(JSON_PRIMARY, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(records)} rows -> {JSON_PRIMARY}")
    os.makedirs(os.path.dirname(JSON_LEGACY), exist_ok=True)
    with open(JSON_LEGACY, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Mirror       {len(records)} rows -> {JSON_LEGACY}")


if __name__ == "__main__":
    main()
