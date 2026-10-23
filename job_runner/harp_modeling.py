"""
Shared code for the HARP phase 2 (train) and phase 3 (estimate) containers.

Phase 1 (the sweep jobs) leaves a results folder like

  <storage>/harp_runs/
    <sweep>-<campaign id>/
      campaign_spec.json            what was asked: parameters, targets (system, queue, cores, memory)
      manifest.json                 every TAPIS job with its status
      <app>_<timestamp>.csv         merged profiling rows (only when the sweep finished)
      jobs/<job name>/harp_profile.csv     each job's own rows (kept even if the merge never ran)
      jobs/<job name>/harp_failures.csv    runs that failed (never used for training)

Runs accumulate: every sweep adds a folder. This module reads all of them (folders,
zips of them, or plain CSVs), puts them in one table, cleans it, and turns it into
features. Phase 2 trains on that table; phase 3 builds the same features for a run
you have not done yet and asks the trained models how long it will take.

Only pandas, numpy and scikit-learn are needed.
"""

import csv
import itertools
import json
import math
import os
import shutil
import tempfile
import zipfile

import numpy as np
import pandas as pd

RUN_TYPES = ("SD", "FS", "test_data")
TARGET = "walltime"
PROFILE_FILE_NAME = "harp_profile.csv"
FAILURES_FILE_NAME = "harp_failures.csv"
# Where each row came from; never features.
PROVENANCE = ["app", "campaign", "job", "source"]
# Known when a job is submitted, so the estimate phase can always fill them in.
SUBMIT_FEATURES = ["system_id", "queue", "sys_alloc_nodes", "sys_alloc_cores", "sys_alloc_mem_mb"]
# Measured on the node; the estimate phase fills them from the hardware catalog (per system/queue).
MISSING = ["", "nan", "null"]      # "none" is a real value (e.g. sys_gpu_name when there is no GPU)
NOT_FEATURES = {"run_config", "run_type", TARGET, "sys_name"} | set(PROVENANCE)


# ------------------------------------------------------------------ ingest
def _plan_targets(spec):
    """job name -> target, re-deriving harp_server/harp_server/sweep.py:plan_jobs (same order, same names)."""
    targets = spec.get("targets") or []
    if not targets:
        return {}
    combos = []
    for rs in spec.get("run_sets") or []:
        names = list(rs.get("parameters") or {})
        for _ in itertools.product(*(rs["parameters"][n] for n in names)):
            combos.append(rs.get("run_type"))
    size = max(1, int(spec.get("combos_per_job") or 1))
    chunks = []
    for rt in RUN_TYPES:
        typed = [c for c in combos if c == rt]
        chunks += [rt for _ in range(0, len(typed), size)]
    if spec.get("distribution") == "replicate":
        assignments = [(rt, t) for rt in chunks for t in targets]
    else:
        cycle = itertools.cycle([t for t in targets for _ in range(int(t.get("weight") or 1))])
        assignments = [(rt, next(cycle)) for rt in chunks]
    return {f"{spec.get('name')}-{rt}-{n:04d}": t for n, (rt, t) in enumerate(assignments)}


def _read_csv(path):
    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def _job_of(run_config):
    return (run_config or "").split(".run-")[0]


def _campaign_rows(cdir):
    """Rows of one campaign folder, each tagged with its job's hardware, plus counts for the report."""
    with open(os.path.join(cdir, "campaign_spec.json")) as f:
        spec = json.load(f)
    folder = os.path.basename(os.path.normpath(cdir))
    cid = folder.rsplit("-", 1)[-1] if "-" in folder else folder
    jobs = _plan_targets(spec)
    manifest = {}
    if os.path.isfile(os.path.join(cdir, "manifest.json")):
        with open(os.path.join(cdir, "manifest.json")) as f:
            manifest = {j["name"]: j for j in json.load(f).get("jobs", [])}
    rows, failures = [], 0
    jobs_dir = os.path.join(cdir, "jobs")
    for job in sorted(os.listdir(jobs_dir)) if os.path.isdir(jobs_dir) else []:
        rows += [(r, f"jobs/{job}/{PROFILE_FILE_NAME}") for r in _read_csv(os.path.join(jobs_dir, job, PROFILE_FILE_NAME))]
        failures += len(_read_csv(os.path.join(jobs_dir, job, FAILURES_FILE_NAME)))
    for name in sorted(os.listdir(cdir)):        # the merged CSV(s); duplicates of the job rows are removed later
        if name.endswith(".csv") and name != FAILURES_FILE_NAME:
            rows += [(r, name) for r in _read_csv(os.path.join(cdir, name))]
    out = []
    for r, src in rows:
        job = _job_of(r.get("run_config"))
        t = jobs.get(job, {})
        out.append({"app": spec.get("application", ""), "campaign": f"{spec.get('name', folder)}#{cid}", "job": job,
                    "source": f"{folder}/{src}", "system_id": t.get("system_id", ""), "queue": t.get("queue", ""),
                    "sys_alloc_nodes": t.get("node_count", ""), "sys_alloc_cores": t.get("cores_per_node", ""),
                    "sys_alloc_mem_mb": t.get("memory_mb", ""), **r})
    statuses = [j.get("status") for j in manifest.values()]
    info = {"campaign": f"{spec.get('name', folder)}#{cid}", "app": spec.get("application", ""), "folder": folder,
            "jobs": len(manifest) or len(jobs), "jobs_finished": statuses.count("FINISHED"),
            "jobs_failed": statuses.count("FAILED"), "rows_read": len(out), "failed_runs": failures}
    return out, info


def _unpack(path, scratch):
    if zipfile.is_zipfile(path):
        dest = tempfile.mkdtemp(prefix="zip_", dir=scratch)
        with zipfile.ZipFile(path) as z:
            for m in z.infolist():      # no absolute paths or '..' escaping the folder
                target = os.path.realpath(os.path.join(dest, m.filename))
                if not target.startswith(os.path.realpath(dest) + os.sep) and target != os.path.realpath(dest):
                    raise ValueError(f"{path}: unsafe path in zip: {m.filename}")
            z.extractall(dest)
        return dest
    return path


def ingest(paths):
    """Folders, zips or CSVs of phase-1 results -> (one DataFrame of every run, report)."""
    scratch = tempfile.mkdtemp(prefix="harp_ingest_")
    rows, campaigns, loose = [], [], []
    try:
        queue = list(paths)
        while queue:
            p = queue.pop(0)
            if not os.path.exists(p):
                raise FileNotFoundError(p)
            p = _unpack(p, scratch) if os.path.isfile(p) and p.lower().endswith(".zip") else p
            if os.path.isfile(p):
                if p.lower().endswith(".csv"):
                    rows += [{"source": os.path.basename(p), **r} for r in _read_csv(p)]
                    loose.append(os.path.basename(p))
                continue
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith(("__MACOSX", ".")))
                if "campaign_spec.json" in files:
                    r, info = _campaign_rows(root)
                    rows += r
                    campaigns.append(info)
                    dirs[:] = []                      # its jobs/ folder is read with it
                    continue
                for f in sorted(files):
                    if f.lower().endswith(".zip"):
                        queue.append(os.path.join(root, f))
                    elif f.lower().endswith(".csv") and f != FAILURES_FILE_NAME:
                        rows += [{"source": f, **r} for r in _read_csv(os.path.join(root, f))]
                        loose.append(os.path.relpath(os.path.join(root, f), p))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    df = pd.DataFrame(rows)
    seen = {}
    for c in campaigns:          # the same sweep folder can come in more than once (e.g. a copy of the results)
        seen.setdefault(c["campaign"], {**c, "copies": 0})["copies"] += 1
    report = {"rows_read": len(df), "campaigns": list(seen.values()), "loose_csvs": loose}
    if df.empty:
        return df, report
    for c in PROVENANCE + SUBMIT_FEATURES:
        if c not in df.columns:
            df[c] = ""
    first = PROVENANCE + ["run_config", "run_type"] + SUBMIT_FEATURES
    rest = [c for c in df.columns if c not in first and c != TARGET]
    df = df[[c for c in first if c in df.columns] + rest + ([TARGET] if TARGET in df.columns else [])]
    return df, report


# ------------------------------------------------------------------ clean
def _to_number(series):
    s = series.astype(str).str.strip()
    lower = s.str.lower()
    s = s.mask(lower.isin(["true", "false"]), (lower == "true").astype(int).astype(str))
    s = s.mask(lower.isin(MISSING))
    num = pd.to_numeric(s, errors="coerce")
    return num if num.notna().sum() == s.notna().sum() else None


def clean(df, app=None, campaigns=None, max_missing=0.3, outliers=True):
    """Every run -> the training table. Returns (table, features {name: numeric|categorical}, report)."""
    rep = {"rows_in": int(len(df)), "dropped_rows": {}, "dropped_columns": {}, "outliers": [], "imputed_columns": {}}

    def drop(mask, reason):
        n = int(mask.sum())
        if n:
            rep["dropped_rows"][reason] = rep["dropped_rows"].get(reason, 0) + n
        return df[~mask]

    if df.empty:
        rep.update(rows_out=0, problems=["no profiling rows found"])
        return df, {}, rep
    apps = sorted(a for a in df["app"].dropna().unique() if a)
    rep["apps_found"] = apps
    if app:
        df = drop(~df["app"].isin([app, ""]), f"other application (kept {app})")
    elif len(apps) > 1:
        raise ValueError(f"these runs are from several applications {apps}; pick one with \"application\"")
    if campaigns:
        keep = df["campaign"].str.split("#").str[-1].isin(campaigns) | df["campaign"].isin(campaigns)
        df = drop(~keep, "sweep not selected")
    df = drop(~df.get("run_type", pd.Series("", index=df.index)).isin(RUN_TYPES), "run type is not SD, FS or test_data")
    df = df.copy()
    df[TARGET] = pd.to_numeric(df.get(TARGET), errors="coerce")
    df = drop(df[TARGET].isna() | (df[TARGET] <= 0), "no walltime")
    # the same run is in its job's CSV, the merged CSV and any copy of the results folder
    key = df["run_config"].fillna("").astype(str) if "run_config" in df.columns else pd.Series("", index=df.index)
    named = key.ne("")
    dup = (named & key.duplicated()) | (~named & df.drop(columns=["source"]).astype(str).duplicated())
    df = drop(dup, "duplicate (same run in several files)")

    candidates = [c for c in df.columns if c not in NOT_FEATURES and (c.startswith(("run_", "sys_")) or c in SUBMIT_FEATURES)]
    features = {}
    for c in candidates:
        blank = df[c].isna() | df[c].astype(str).str.strip().str.lower().isin(MISSING)
        if blank.all():
            rep["dropped_columns"][c] = "not recorded"
            continue
        if blank.mean() > max_missing:
            rep["dropped_columns"][c] = f"missing in {int(blank.sum())} of {len(df)} rows"
            continue
        num = _to_number(df[c])
        df[c] = num if num is not None else df[c].astype(str).str.strip().mask(blank)
        if df[c].nunique(dropna=True) <= 1:
            rep["dropped_columns"][c] = "same value in every run"
            v = df[c].dropna().iloc[0]
            rep.setdefault("constants", {})[c] = v.item() if hasattr(v, "item") else v
            continue
        if blank.any():
            rep["imputed_columns"][c] = int(blank.sum())
        features[c] = "numeric" if num is not None else "categorical"

    if outliers and features:
        # same configuration repeated: drop walltimes far from the group's median (robust z > 3.5)
        keep = pd.Series(True, index=df.index)
        for _, g in df.groupby([df[c].astype(str) for c in features], sort=False):
            if len(g) < 4:
                continue
            med = g[TARGET].median()
            mad = (g[TARGET] - med).abs().median()
            if mad <= 0:
                continue
            z = 0.6745 * (g[TARGET] - med).abs() / mad
            bad = z > 3.5
            keep[g.index[bad]] = False
            rep["outliers"] += [{"run_config": r.get("run_config"), "walltime": float(r[TARGET]), "group_median": float(med)}
                                for _, r in g[bad].iterrows()]
        df = drop(~keep, "outlier walltime for its configuration")

    rep["rows_out"] = int(len(df))
    rep["by_run_type"] = {t: int((df["run_type"] == t).sum()) for t in RUN_TYPES}
    rep["by_campaign"] = {k: int(v) for k, v in df["campaign"].value_counts().items()}
    rep["by_system_queue"] = {f"{s}/{q}": int(v) for (s, q), v in df.groupby(["system_id", "queue"]).size().items()}
    rep["features"] = features
    rep["walltime"] = {k: round(float(v), 4) for k, v in df[TARGET].describe().items()} if len(df) else {}
    problems = []
    if len(df) < 3:
        problems.append(f"needs at least 3 usable runs to train and score a model; has {len(df)}")
    if not features:
        problems.append("nothing varies between runs, so there is nothing to learn from")
    rep["problems"] = problems
    context = [c for c in ("system_id", "queue") if c not in features]     # kept for the hardware catalog
    cols = PROVENANCE + ["run_config", "run_type"] + context + list(features) + [TARGET]
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True), features, rep


def hardware_catalog(df, features):
    """Median measured hardware per system/queue, so an estimate only needs the system, queue and cores."""
    measured = [c for c, kind in features.items() if c.startswith("sys_") and c not in SUBMIT_FEATURES and kind == "numeric"]
    cat = {}
    if not measured or "system_id" not in df.columns:
        return cat
    for (s, q), g in df.groupby([df["system_id"].fillna(""), df["queue"].fillna("")]):
        cat[f"{s}/{q}"] = {c: float(g[c].median()) for c in measured if g[c].notna().any()}
    for s, g in df.groupby(df["system_id"].fillna("")):
        cat.setdefault(f"{s}/*", {c: float(g[c].median()) for c in measured if g[c].notna().any()})
    return cat


# ------------------------------------------------------------------ scores (same definitions as pipeline/modules/ModelTrainer/RegressionMetrics.py)
def scores(gold, pred):
    gold, pred = np.asarray(gold, float), np.asarray(pred, float)
    if not len(gold):
        return {k: None for k in ("MSE", "MAE", "MAPE", "UPP", "UP_MAPE", "OV_MAPE")}
    ape = np.abs(gold - pred) / gold * 100
    under, over = pred < gold, pred > gold
    r = lambda v: round(float(v), 4)
    return {"MSE": r(np.mean((gold - pred) ** 2)), "MAE": r(np.mean(np.abs(gold - pred))), "MAPE": r(ape.mean()),
            "UPP": r(under.mean() * 100), "UP_MAPE": r(ape[under].mean() if under.any() else 0.0),
            "OV_MAPE": r(ape[over].mean() if over.any() else 0.0)}


def adjust_factor(gold, pred):
    """Pad predictions by the average relative miss of the runs they under-predicted (the pipeline's ADJ_FACTOR)."""
    gold, pred = np.asarray(gold, float), np.asarray(pred, float)
    under = pred < gold
    if not under.any():
        return 1.0
    return round(1.0 + float(np.mean(np.abs(gold[under] - pred[under]) / gold[under])), 2)


# ------------------------------------------------------------------ estimate-time features
def request_row(req, features, catalog, constants=None):
    """One estimate request -> one feature row (dict) and the warnings about it.

    req: {"params": {"epochs": 4, ...}, "system_id": "...", "queue": "...", "cores": 8, "memory_mb": 32768,
          "nodes": 1, "hardware": {"sys_tot_cores_count": 96, ...}}
    """
    params = {k if k.startswith("run_") else f"run_{k}": v for k, v in (req.get("params") or {}).items()}
    given = {"system_id": req.get("system_id"), "queue": req.get("queue"), "sys_alloc_cores": req.get("cores"),
             "sys_alloc_mem_mb": req.get("memory_mb"), "sys_alloc_nodes": req.get("nodes"),
             **params, **(req.get("hardware") or {})}
    where = f"{req.get('system_id', '')}/{req.get('queue', '')}"
    hw = catalog.get(where) or catalog.get(f"{req.get('system_id', '')}/*") or {}
    row, warnings = {}, []
    if catalog and where not in catalog:
        warnings.append(f"no profiled runs on {where}; node hardware is "
                        + ("taken from the system's other queues" if hw else "guessed"))
    for c, kind in features.items():
        v = given.get(c)
        if v in (None, "") and c in hw:
            v = hw[c]
        if v in (None, ""):
            row[c] = np.nan
            warnings.append(f"{c} not given; using the training data's typical value")
            continue
        if kind == "numeric":
            try:
                v = float(1 if str(v).lower() == "true" else 0 if str(v).lower() == "false" else v)
            except ValueError:
                warnings.append(f"{c}={v!r} is not a number; using the training data's typical value")
                v = np.nan
        else:
            v = str(v)
        row[c] = v
    constants = constants or {}
    for c in sorted(set(given) - set(features)):
        v = given[c]
        if v in (None, "") or c not in constants and not c.startswith("run_"):
            continue
        if c not in constants:
            warnings.append(f"{c} was never profiled, so it does not change the estimate")
        elif str(v) != str(constants[c]) and _num_or_str(v) != _num_or_str(constants[c]):
            warnings.append(f"every profiled run used {c}={constants[c]}; the estimate cannot tell what {v} changes")
    return row, warnings


def _num_or_str(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


def ceil_minutes(seconds, margin):
    return max(1, int(math.ceil(seconds * (1 + margin) / 60.0)))


# ------------------------------------------------------------------ model building block
from sklearn.base import BaseEstimator, TransformerMixin  # noqa: E402


class StableScaler(BaseEstimator, TransformerMixin):
    """StandardScaler that never divides by a near-zero spread.

    Measured hardware columns barely vary between nodes of one queue (memory differs by a few
    kilobytes), and with few runs a plain z-score turns that noise into huge values for any
    other node. The spread used is at least `rel` x |mean|, so a column has to really vary to
    matter. Saved inside every model, so phase 3 needs this module to load them.
    """

    def __init__(self, rel=0.01):
        self.rel = rel

    def fit(self, X, y=None):
        X = np.asarray(X, float)
        self.mean_ = np.nanmean(X, axis=0)
        floor = np.maximum(self.rel * np.abs(self.mean_), 1e-12)
        self.scale_ = np.maximum(np.nanstd(X, axis=0), floor)
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X):
        return (np.asarray(X, float) - self.mean_) / self.scale_

    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features if input_features is not None else [f"x{i}" for i in range(self.n_features_in_)],
                          dtype=object)
