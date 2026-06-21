"""Derive the COPD severity-mix anchors from the real Apollo dataset -> data/apollo_severity.json.

Reads datasets/apollo_hospitals/copd_generated_data_for_london_hackathon.csv (70,383 synthetic
COPD encounters) and computes two AGE-stratified clinical profiles:

  - "low"  = patients aged < 65   (lower-acuity catchment proxy)
  - "high" = patients aged 65+    (higher-acuity / more-vulnerable catchment proxy)

per profile: respiratory-ward share (WARD_TYPE==1), ICU/critical share (Cardiac_Arrest==1 as a
critical-care proxy), and mean Length of Stay. At runtime SeverityProvider interpolates between
these two REAL profiles by each catchment's vulnerabilityWeight (plan.md §0/§5: Apollo gives
clinical texture, never a climate predictor — the output stays tagged `simulated`).

Usage:
    python data/scripts/build_severity.py [path/to/copd_csv]
Default CSV path: ../.datasets-src/datasets/apollo_hospitals/...  (the cloned datasets repo).
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # .../ClimateHack
DEFAULT_CSV = ROOT / ".datasets-src/datasets/apollo_hospitals/copd_generated_data_for_london_hackathon.csv"
OUT = ROOT / "data" / "apollo_severity.json"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is1(v) -> bool:
    return (v or "").strip() in ("1", "1.0")


def build(csv_path: Path) -> dict:
    groups = {"low": {"n": 0, "ward1": 0, "icu": 0, "los": []},
              "high": {"n": 0, "ward1": 0, "icu": 0, "los": []}}
    with csv_path.open(newline="") as f:
        next(f)  # skip the "Table 1" title line; real header is line 2
        for r in csv.DictReader(f):
            age = _num(r.get("AGE"))
            if age is None:
                continue
            g = groups["high"] if age >= 65 else groups["low"]
            g["n"] += 1
            if _is1(r.get("WARD_TYPE")):
                g["ward1"] += 1
            if _is1(r.get("Cardiac_Arrest")):
                g["icu"] += 1
            los = _num(r.get("LOS"))
            if los is not None:
                g["los"].append(los)

    def profile(g: dict) -> dict:
        n = g["n"]
        return {
            "respWardPct": round(100 * g["ward1"] / n, 1),
            "icuPct": round(100 * g["icu"] / n, 1),
            "avgLOS": round(statistics.mean(g["los"]), 1),
        }

    return {
        "_meta": {
            "source": "Apollo Hospitals — synthetic COPD encounters (datasets/apollo_hospitals)",
            "derivation": "AGE-stratified over 70,383 rows: respWardPct=WARD_TYPE==1, icuPct=Cardiac_Arrest==1 (critical-care proxy), avgLOS=mean(LOS).",
            "honesty": "Apollo is a SYNTHETIC clinical cohort used for severity texture only, never as a climate/admissions predictor (plan.md §0). Runtime output stays tagged simulated.",
            "rowsLow": groups["low"]["n"], "rowsHigh": groups["high"]["n"],
        },
        "interpolateBy": "vulnerabilityWeight; t = clamp((vw - vwMin)/(vwMax - vwMin), 0, 1)",
        "vwMin": 0.85, "vwMax": 1.40,
        "anchors": {"low": profile(groups["low"]), "high": profile(groups["high"])},
    }


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    if not csv_path.exists():
        sys.exit(f"Apollo CSV not found: {csv_path}\nClone london2026-datasets and pass the path.")
    out = build(csv_path)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {OUT}")
    print(json.dumps(out["anchors"], indent=2))


if __name__ == "__main__":
    main()
