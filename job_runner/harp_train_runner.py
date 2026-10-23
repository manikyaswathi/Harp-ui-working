#!/usr/bin/env python3
"""
HARP phase 2: train runtime estimators from the accumulated phase-1 results.

Runs inside the HARP train container (DockerFiles/Dockerfile_HARP_Phase2_Train) as a
TAPIS job or with docker/apptainer, or directly with Python. Steps:

  ingest    every sweep under the results folder (folders, zips, or plain CSVs): each job's
            harp_profile.csv and the merged CSVs, tagged with the system, queue, cores and
            memory its job was given (re-derived from campaign_spec.json)
  clean     keep SD / FS / test_data runs with a walltime, drop duplicates (the same run is in
            its job's CSV, the merged CSV and any copy of the folder), turn true/false into 1/0,
            drop columns that are mostly empty or never vary, impute the rest, and drop
            outlier walltimes among repeats of the same configuration
  train     the models picked in the UI (LR, NN, DTR) on the training sets picked in the UI
            (SD, SD+25FS, SD+50FS, SD+75FS), each with scaling / one-hot encoding built in
  score     on the test_data runs when there are any, otherwise by cross-validation; each model
            is scored as-is and padded by its adjustment factor (as the HARP pipeline does)
  select    the best model by the chosen policy

Usage:
  harp_train_runner.py [<spec>] [--runs PATH ...] [--output DIR]

<spec> is URL-safe base64 JSON, a JSON file, or raw JSON (all keys optional):
  {"name": "ultralytics_yolo", "application": "ultralytics-yolo", "campaigns": ["15e48705"],
   "models": ["LR", "NN", "DTR"], "training_sets": ["SD", "SD+25FS", "SD+50FS", "SD+75FS"],
   "policy": "mape" | "underpredict", "cv_folds": 5, "max_missing": 0.3, "outliers": true,
   "runs": ["harp_runs"], "dataset_file": "<standardized CSV staged by the HARP server>"}

--runs (or spec "runs", or spec "dataset_file", or the TAPIS input folder /TapisInput) is
where phase 1's results are. Results go to --output or the TAPIS output folder:
  consolidated_runs.csv  every run read, with where it came from
  training_data.csv      the cleaned table the models learned from
  data_report.json       what was read, dropped, imputed and why
  model_commons.csv      every model's scores (same columns as the HARP pipeline)
  models/<model>_<training set>_<time>.joblib
  harp_model_bundle.json what phase 3 needs: features, hardware catalog, models, best model
  harp_build_summary.json, and harp_progress.json while it runs
"""

import argparse
import base64
import json
import os
import sys
import time
import warnings
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeRegressor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harp_modeling as hm  # noqa: E402

MODELS = {"LR": "Linear regression", "NN": "Neural network", "DTR": "Decision tree"}
TRAINING_SETS = {"SD": 0.0, "SD+25FS": 0.25, "SD+50FS": 0.50, "SD+75FS": 0.75}
SUMMARY_FILE_NAME = "harp_build_summary.json"
PROGRESS_FILE_NAME = "harp_progress.json"
BUNDLE_FILE_NAME = "harp_model_bundle.json"
STEPS = ["preprocess", "train"]     # the HARP server's build page follows these two
SEED = 2048


def decode_spec(arg):
    if not arg:
        return {}
    if os.path.isfile(arg):
        with open(arg) as f:
            return json.load(f)
    if arg.lstrip().startswith("{"):
        return json.loads(arg)
    padded = arg.strip() + "=" * (-len(arg.strip()) % 4)
    return json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))


def input_paths(spec, given):
    tapis_in = [d for d in ("/TapisInput", os.environ.get("_tapisExecSystemInputDir")) if d and os.path.isdir(d)]
    if given:
        return given
    if spec.get("runs"):
        return [p if os.path.isabs(p) or os.path.exists(p) else next(
            (os.path.join(d, p) for d in tapis_in if os.path.exists(os.path.join(d, p))), p) for p in spec["runs"]]
    if spec.get("dataset_file"):
        for d in tapis_in + [os.getcwd()]:
            if os.path.isfile(os.path.join(d, spec["dataset_file"])):
                return [os.path.join(d, spec["dataset_file"])]
    if tapis_in:
        return tapis_in[:1]
    raise SystemExit("[HARP] no results to train on: give --runs (a results folder, zip or CSV)")


def output_dir(given=None):
    for candidate in ([given] if given else []) + ["/TapisOutput", os.environ.get("_tapisExecSystemOutputDir")]:
        if candidate:
            try:
                os.makedirs(candidate, exist_ok=True)
            except OSError:
                continue
            if os.access(candidate, os.W_OK):
                return candidate
    fallback = os.path.join(os.getcwd(), "harp_output")
    os.makedirs(fallback, exist_ok=True)
    return fallback


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1, default=str)
    os.replace(tmp, path)


def make_model(kind, features, n_rows):
    numeric = [c for c, k in features.items() if k == "numeric"]
    categorical = [c for c, k in features.items() if k == "categorical"]
    prep = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", hm.StableScaler())]), numeric),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                          ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical)])
    if kind == "LR":
        # linear regression; the penalty is picked by leave-one-out and is ~0 when there are plenty of runs,
        # but keeps the fit sane when a sweep has fewer runs than features
        est = RidgeCV(alphas=np.logspace(-6, 3, 19))
    elif kind == "DTR":
        est = DecisionTreeRegressor(random_state=SEED, min_samples_leaf=max(1, n_rows // 50))
    else:
        # lbfgs converges on the small tables profiling produces; the target is scaled too
        est = TransformedTargetRegressor(MLPRegressor(hidden_layer_sizes=(32, 16), solver="lbfgs", alpha=1e-3,
                                                      max_iter=5000, random_state=SEED), transformer=StandardScaler())
    return Pipeline([("prep", prep), ("model", est)])


def predict(model, X):
    return np.clip(model.predict(X), 1e-6, None)    # a runtime is never negative


def training_frames(table, ds, rng_seed=SEED):
    """(train, validation or None, test or None, note) for one training set, following the HARP pipeline:
    validation = 25% of FS (for the adjustment factor), test = test_data, FS share sampled to SD's size."""
    sd, fs, td = (table[table["run_type"] == t] for t in hm.RUN_TYPES)
    share = TRAINING_SETS[ds]
    val, pool = None, fs
    if len(fs) >= 4:
        pool, val = train_test_split(fs, test_size=0.25, random_state=rng_seed)
    if share and len(pool) == 0:
        return None, None, None, "no FS runs"
    frames = [sd]
    if share:
        # share of all FS runs (never the validation ones), resampled to as many runs as SD like the pipeline does
        take = pool.sample(n=min(len(pool), max(1, round(len(fs) * share))), random_state=rng_seed)
        if len(sd) > len(take):
            take = take.sample(n=len(sd), replace=True, random_state=rng_seed)
        frames.append(take)
    train = pd.concat(frames)
    if len(train) < 2:
        return None, None, None, f"only {len(train)} training run(s)"
    return train, val, (td if len(td) else None), None


def oof_predictions(kind, features, train, folds):
    """Out-of-fold predictions: every run is predicted by a model that never saw it."""
    X, y = train[list(features)], train[hm.TARGET].to_numpy(float)
    k = min(folds, len(train))
    pred = np.empty(len(train))
    for tr, te in KFold(n_splits=k, shuffle=True, random_state=SEED).split(X):
        m = make_model(kind, features, len(tr)).fit(X.iloc[tr], y[tr])
        pred[te] = predict(m, X.iloc[te])
    return y, pred


def train_all(table, features, spec, out, stamp, report_progress):
    models = [m for m in (spec.get("models") or MODELS) if m in MODELS] or list(MODELS)
    sets = [t for t in (spec.get("training_sets") or TRAINING_SETS) if t in TRAINING_SETS] or list(TRAINING_SETS)
    folds = int(spec.get("cv_folds") or 5)
    rows, skipped, saved = [], {}, []
    os.makedirs(os.path.join(out, "models"), exist_ok=True)
    for ds in sets:
        train, val, test, why = training_frames(table, ds)
        if train is None:
            skipped[ds] = why
            print(f"[HARP] skip {ds}: {why}", flush=True)
            continue
        for kind in models:
            report_progress(f"{kind} on {ds}")
            X, y = train[list(features)], train[hm.TARGET].to_numpy(float)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = make_model(kind, features, len(train)).fit(X, y)
                # adjustment factor from runs the model did not train on
                if val is not None and len(val):
                    vg, vp = val[hm.TARGET].to_numpy(float), predict(model, val[list(features)])
                elif len(train) >= 3:
                    vg, vp = oof_predictions(kind, features, train, folds)
                else:
                    vg, vp = y, predict(model, X)
                adj = hm.adjust_factor(vg, vp)
                if test is not None:
                    gold, pred, evaluated = test[hm.TARGET].to_numpy(float), predict(model, test[list(features)]), "test_data"
                elif len(train) >= 3:
                    gold, pred = oof_predictions(kind, features, train, folds)
                    evaluated = f"cross-validation ({min(folds, len(train))} folds)"
                else:
                    gold, pred, evaluated = y, predict(model, X), "training runs (too few to hold any out)"
            fname = f"{kind}_{ds}_{stamp}.joblib"
            joblib.dump(model, os.path.join(out, "models", fname))
            saved.append(f"models/{fname}")
            for padded, factor in (("no", 1.0), ("yes", adj)):
                s = hm.scores(gold, pred * factor)
                rows.append({"DataSet": ds, "RegModel": kind, "ADJ_FACTOR": factor, **s,
                             "MODEL_NAME": f"{kind}_{ds}_{padded}_{stamp}", "MODEL_FILE": f"models/{fname}",
                             "PADDED": padded, "N_TRAIN": len(train), "N_EVAL": len(gold), "EVALUATED_ON": evaluated})
            print(f"[HARP] {kind} on {ds}: MAPE {rows[-2]['MAPE']}% (padded x{adj}: {rows[-1]['MAPE']}%), {evaluated}",
                  flush=True)
    return rows, skipped, saved


def select_best(rows, policy):
    ok = [r for r in rows if isinstance(r.get("MAPE"), (int, float))]
    if not ok:
        return None
    if policy == "underpredict":     # the HARP pipeline's Predictor policy: fewest under-predictions, then smallest overshoot
        return min(ok, key=lambda r: (r["UPP"], r["OV_MAPE"], r["MAPE"]))
    return min(ok, key=lambda r: (r["MAPE"], r["UPP"]))


def run(spec, paths, out):
    name = spec.get("name") or "app"
    os.makedirs(out, exist_ok=True)
    stamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    progress = {"step": None, "steps": {s: "waiting" for s in STEPS}, "detail": None, "updated_at": None}

    def report(step=None, state=None, detail=None):
        if step:
            progress["step"], progress["steps"][step] = step, state
        progress["detail"] = detail
        progress["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        write_json(os.path.join(out, PROGRESS_FILE_NAME), progress)

    summary = {"name": name, "ok": False, "error": None, "files": []}
    report()
    try:
        report("preprocess", "running", "reading phase-1 results")
        raw, ingest_report = hm.ingest(paths)
        print(f"[HARP] read {len(raw)} rows from {len(ingest_report['campaigns'])} sweep(s) in {paths}", flush=True)
        raw.to_csv(os.path.join(out, "consolidated_runs.csv"), index=False)
        table, features, clean_report = hm.clean(raw, app=spec.get("application"), campaigns=spec.get("campaigns"),
                                                 max_missing=float(spec.get("max_missing", 0.3)),
                                                 outliers=bool(spec.get("outliers", True)))
        table.to_csv(os.path.join(out, "training_data.csv"), index=False)
        data_report = {"inputs": [str(p) for p in paths], "ingest": ingest_report, "clean": clean_report}
        write_json(os.path.join(out, "data_report.json"), data_report)
        print(f"[HARP] {clean_report['rows_out']} usable runs, by run type {clean_report.get('by_run_type')}, "
              f"features {list(features)}", flush=True)
        if clean_report.get("problems"):
            report("preprocess", "failed")
            raise RuntimeError("; ".join(clean_report["problems"]))
        report("preprocess", "done")

        report("train", "running")
        app = spec.get("application") or (clean_report.get("apps_found") or [name])[0]
        rows, skipped, saved = train_all(table, features, spec, out, stamp,
                                         lambda d: report("train", "running", d))
        if not rows:
            report("train", "failed")
            raise RuntimeError("no model could be trained: " + "; ".join(f"{k}: {v}" for k, v in skipped.items()))
        commons = pd.DataFrame(rows)
        commons.to_csv(os.path.join(out, "model_commons.csv"), index=False)
        policy = spec.get("policy") or "mape"
        best = select_best(rows, policy)
        bundle = {"application": app, "name": name, "created": stamp, "target": hm.TARGET, "unit": "seconds",
                  "features": features, "hardware_catalog": hm.hardware_catalog(table, features),
                  "feature_values": {c: (sorted(map(str, table[c].dropna().unique()))[:50] if k == "categorical"
                                         else [float(table[c].min()), float(table[c].max())])
                                     for c, k in features.items()},
                  "constants": clean_report.get("constants", {}), "rows": int(len(table)), "by_run_type": clean_report["by_run_type"],
                  "policy": policy, "best": best, "models": rows, "skipped_training_sets": skipped,
                  "sklearn_version": sklearn.__version__}
        write_json(os.path.join(out, BUNDLE_FILE_NAME), bundle)
        report("train", "done")
        print(f"[HARP] best ({policy}): {best['MODEL_NAME']}  MAPE {best['MAPE']}%  under-predicts {best['UPP']}%",
              flush=True)
        summary.update(ok=True, files=["consolidated_runs.csv", "training_data.csv", "data_report.json",
                                       "model_commons.csv", BUNDLE_FILE_NAME] + saved, best=best, skipped=skipped)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        summary["error"] = str(e)
    finally:
        write_json(os.path.join(out, SUMMARY_FILE_NAME), summary)
    print(f"[HARP] train {'done' if summary['ok'] else 'failed'}: {summary['error'] or len(summary['files'])} files",
          flush=True)
    return summary


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec", nargs="?", default="")
    ap.add_argument("--runs", action="append", help="phase-1 results: a folder, a zip, or a CSV (repeatable)")
    ap.add_argument("--input", help="a standardized training CSV (same as --runs CSV; kept for the HARP server)")
    ap.add_argument("--output")
    args = ap.parse_args(argv)
    spec = decode_spec(args.spec)
    out = output_dir(args.output)
    print(f"[HARP] writing results to {out}", flush=True)
    paths = input_paths(spec, (args.runs or []) + ([args.input] if args.input else []))
    return 0 if run(spec, paths, out)["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
