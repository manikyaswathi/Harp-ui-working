#!/usr/bin/env python3
"""
HARP phase 3: estimate how long a run will take, with the models phase 2 trained.

Runs inside the HARP estimate container (DockerFiles/Dockerfile_HARP_Phase3_Estimate) as a
TAPIS job or with docker/apptainer, or directly with Python. For every requested run (the
application's parameter values plus the system, queue and cores it would get) it builds the
same features phase 2 trained on, filling the node's hardware in from the hardware catalog
of the runs profiled on that system and queue, and asks the chosen model(s).

Usage:
  harp_estimate_runner.py <spec> [--models PATH] [--requests FILE] [--output DIR]

<spec> is URL-safe base64 JSON, a JSON file, or raw JSON:
  {"models_dir": "builds/ultralytics_yolo_2026_10_23",     phase 2's output folder (or a zip of it)
   "model": "best" | "all" | "<MODEL_NAME from model_commons.csv>",
   "margin": 0.10,                                          extra time on top of the padded estimate
   "requests": [{"name": "4 epochs on 8 cores", "params": {"epochs": 4, "model": "yolo11n"},
                 "system_id": "ascend-tapis", "queue": "debug", "cores": 8, "memory_mb": 32768}]}

--requests is a JSON list like "requests", or a CSV with one row per request (columns:
name, system_id, queue, cores, memory_mb, nodes, and one column per parameter).
--models (or spec "models_dir", or the TAPIS input folder) is phase 2's output.
Results go to --output or the TAPIS output folder: estimates.json, estimates.csv and
harp_estimate_summary.json.
"""

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import zipfile

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harp_modeling as hm  # noqa: E402,F401  (also needed to load the models: they contain hm.StableScaler)
from harp_train_runner import BUNDLE_FILE_NAME, decode_spec, output_dir, write_json  # noqa: E402

SUMMARY_FILE_NAME = "harp_estimate_summary.json"
REQUEST_KEYS = {"name", "system_id", "queue", "cores", "memory_mb", "nodes"}


def find_bundle(spec, given, scratch):
    candidates = [given] if given else []
    if spec.get("models_dir"):
        candidates.append(spec["models_dir"])
    for d in ("/TapisInput", os.environ.get("_tapisExecSystemInputDir")):
        if d and os.path.isdir(d):
            candidates += [os.path.join(d, spec["models_dir"])] if spec.get("models_dir") else []
            candidates.append(d)
    for c in candidates:
        if c and os.path.isfile(c) and zipfile.is_zipfile(c):
            dest = tempfile.mkdtemp(prefix="models_", dir=scratch)
            with zipfile.ZipFile(c) as z:
                z.extractall(dest)
            c = dest
        if c and os.path.isdir(c):
            for root, _, files in os.walk(c):
                if BUNDLE_FILE_NAME in files:
                    return root
    raise SystemExit(f"[HARP] no {BUNDLE_FILE_NAME} found in {candidates}: give --models (phase 2's output folder)")


def read_requests(spec, path):
    if not path:
        return spec.get("requests") or []
    if path.lower().endswith(".csv"):
        out = []
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                out.append({**{k: r[k] for k in REQUEST_KEYS if r.get(k) not in (None, "")},
                            "params": {k: v for k, v in r.items() if k not in REQUEST_KEYS and v not in (None, "")}})
        return out
    with open(path) as f:
        data = json.load(f)
    return data.get("requests", []) if isinstance(data, dict) else data


def pick_models(bundle, choice):
    rows = bundle["models"]
    if choice in (None, "", "best"):
        return [bundle["best"]]
    if choice == "all":
        return rows
    hit = [r for r in rows if r["MODEL_NAME"] == choice]
    if not hit:
        raise SystemExit(f"[HARP] model {choice} is not in this build; it has {[r['MODEL_NAME'] for r in rows]}")
    return hit


def run(spec, bundle_dir, requests, out):
    with open(os.path.join(bundle_dir, BUNDLE_FILE_NAME)) as f:
        bundle = json.load(f)
    features, catalog, ranges = bundle["features"], bundle.get("hardware_catalog") or {}, bundle.get("feature_values") or {}
    margin = float(spec.get("margin", 0.10))
    chosen = pick_models(bundle, spec.get("model"))
    loaded = {}
    results = []
    for i, req in enumerate(requests):
        row, warnings = hm.request_row(req, features, catalog, bundle.get("constants"))
        for c, kind in features.items():      # outside what was profiled: the estimate is an extrapolation
            v = row.get(c)
            if kind == "numeric" and isinstance(v, float) and not np.isnan(v) and c in ranges:
                lo, hi = ranges[c]
                if v < lo or v > hi:
                    warnings.append(f"{c}={v:g} is outside the profiled range [{lo:g}, {hi:g}]")
            elif kind == "categorical" and isinstance(v, str) and v not in ranges.get(c, [v]):
                warnings.append(f"{c}={v} was never profiled")
        X = pd.DataFrame([row], columns=list(features))
        for m in chosen:
            if m["MODEL_FILE"] not in loaded:
                loaded[m["MODEL_FILE"]] = joblib.load(os.path.join(bundle_dir, m["MODEL_FILE"]))
            raw = float(max(loaded[m["MODEL_FILE"]].predict(X)[0], 0.0))
            padded = raw * float(m["ADJ_FACTOR"])
            results.append({"request": req.get("name") or f"request-{i + 1}", "model": m["MODEL_NAME"],
                            "model_kind": m["RegModel"], "training_set": m["DataSet"],
                            "system_id": req.get("system_id"), "queue": req.get("queue"), "cores": req.get("cores"),
                            "memory_mb": req.get("memory_mb"), "params": req.get("params") or {},
                            "estimate_seconds": round(raw, 3), "adj_factor": m["ADJ_FACTOR"],
                            "padded_seconds": round(padded, 3), "suggested_max_minutes": hm.ceil_minutes(padded, margin),
                            "model_mape": m.get("MAPE"), "model_underpredicts_pct": m.get("UPP"),
                            "warnings": warnings})
            print(f"[HARP] {results[-1]['request']}: {raw:.1f} s (padded {padded:.1f} s, ask for "
                  f"{results[-1]['suggested_max_minutes']} min) with {m['MODEL_NAME']}"
                  + (f"  [{'; '.join(warnings)}]" if warnings else ""), flush=True)
    write_json(os.path.join(out, "estimates.json"), {"application": bundle.get("application"), "build": bundle.get("created"),
                                                     "margin": margin, "estimates": results})
    flat = [{**{k: v for k, v in r.items() if k not in ("params", "warnings")},
             **{f"param_{k}": v for k, v in r["params"].items()}, "warnings": " | ".join(r["warnings"])} for r in results]
    pd.DataFrame(flat).to_csv(os.path.join(out, "estimates.csv"), index=False)
    return {"ok": True, "error": None, "estimates": len(results), "files": ["estimates.json", "estimates.csv"]}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec", nargs="?", default="")
    ap.add_argument("--models", help="phase 2's output folder or a zip of it")
    ap.add_argument("--requests", help="JSON list or CSV of runs to estimate")
    ap.add_argument("--output")
    args = ap.parse_args(argv)
    spec = decode_spec(args.spec)
    out = output_dir(args.output)
    scratch = tempfile.mkdtemp(prefix="harp_estimate_")
    summary = {"ok": False, "error": None}
    try:
        requests = read_requests(spec, args.requests)
        if not requests:
            raise ValueError("nothing to estimate: give \"requests\" in the spec or --requests")
        summary = run(spec, find_bundle(spec, args.models, scratch), requests, out)
    except (ValueError, KeyError, OSError) as e:
        summary["error"] = str(e)
        print(f"[HARP] estimate failed: {e}", flush=True)
    finally:
        write_json(os.path.join(out, SUMMARY_FILE_NAME), summary)
        shutil.rmtree(scratch, ignore_errors=True)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
