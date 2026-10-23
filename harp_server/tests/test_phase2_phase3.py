"""Phase 2 (train) and phase 3 (estimate) runners on phase-1 results folders."""
import csv
import json
import os
import random
import shutil

import pytest

pytest.importorskip("sklearn")
pytest.importorskip("joblib")

import harp_estimate_runner  # noqa: E402
import harp_modeling as hm  # noqa: E402
import harp_train_runner  # noqa: E402
from harp_server.build import parse_metrics  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXAMPLES = os.path.join(REPO, "Del_example_runs")
COLUMNS = ["run_config", "run_type", "sys_name", "sys_tot_cores_count", "sys_phy_mem_bytes", "sys_gpu_name",
           "run_n", "run_method", "walltime"]


def make_campaign(root, name, cid, run_sets, targets, seed=1):
    """A results folder like phase 1 leaves: spec, manifest, jobs/<job>/harp_profile.csv, merged CSV."""
    spec = {"name": name, "application": "euler", "repetitions": 2, "combos_per_job": 1, "distribution": "split",
            "run_sets": run_sets, "targets": [{**t, "key": f"t{i}", "weight": 1} for i, t in enumerate(targets)]}
    cdir = os.path.join(root, f"{name}-{cid}")
    os.makedirs(cdir)
    with open(os.path.join(cdir, "campaign_spec.json"), "w") as f:
        json.dump(spec, f)
    rng, merged, manifest = random.Random(seed), [], []
    job_targets = hm._plan_targets(spec)
    n = 0
    for rt in hm.RUN_TYPES:
        for rs in (r for r in run_sets if r["run_type"] == rt):
            for size in rs["parameters"]["n"]:
                for method in rs["parameters"]["method"]:
                    job = f"{name}-{rt}-{n:04d}"
                    t = job_targets[job]
                    rows = []
                    for rep in range(2):
                        wall = size / 1000 * (3 if method == "slow" else 1) * 16 / t["cores_per_node"] * rng.uniform(0.95, 1.05)
                        rows.append([f"{job}.run-0.iteration-{rep}", rt, "Linux", 96, 1081772077056 + rng.randint(0, 9999),
                                     "none", size, method, round(wall, 4)])
                    os.makedirs(os.path.join(cdir, "jobs", job))
                    with open(os.path.join(cdir, "jobs", job, "harp_profile.csv"), "w", newline="") as f:
                        csv.writer(f).writerows([COLUMNS] + rows)
                    merged += rows
                    manifest.append({"name": job, "status": "FINISHED", "rows": len(rows)})
                    n += 1
    with open(os.path.join(cdir, "manifest.json"), "w") as f:
        json.dump({"campaign": cid, "jobs": manifest}, f)
    with open(os.path.join(cdir, "euler_2026_10_21_00_00_00.csv"), "w", newline="") as f:
        csv.writer(f).writerows([COLUMNS] + merged)
    return cdir


@pytest.fixture
def runs(tmp_path):
    root = tmp_path / "harp_runs"
    targets = [{"system_id": "pitzer", "queue": "serial", "cores_per_node": 4, "memory_mb": 16000},
               {"system_id": "pitzer", "queue": "serial", "cores_per_node": 16, "memory_mb": 64000}]
    sd = {"run_type": "SD", "parameters": {"n": [100, 200, 400, 800], "method": ["fast", "slow"]}}
    fs = {"run_type": "FS", "parameters": {"n": [1600, 3200, 6400, 12800], "method": ["fast", "slow"]}}
    td = {"run_type": "test_data", "parameters": {"n": [2400, 9600], "method": ["fast", "slow"]}}
    make_campaign(str(root), "euler-sd", "aaaa1111", [sd], targets, seed=1)
    make_campaign(str(root), "euler-fs", "bbbb2222", [fs, td], targets, seed=2)
    return root


def test_ingest_tags_hardware_and_cleaning_removes_copies(runs):
    copy = runs.parent / "harp_runs_copy"
    shutil.copytree(runs, copy)                      # the "copy results to another location" folder
    raw, rep = hm.ingest([str(runs), str(copy)])
    assert {c["campaign"]: c["copies"] for c in rep["campaigns"]} == {"euler-sd#aaaa1111": 2, "euler-fs#bbbb2222": 2}
    assert set(raw["sys_alloc_cores"]) == {4, 16}    # re-derived from the plan
    table, features, report = hm.clean(raw)
    assert report["rows_out"] == 16 + 16 + 8         # every run once (job CSV, merged CSV and copy are the same runs)
    assert report["dropped_rows"]["duplicate (same run in several files)"] == len(raw) - 40
    assert report["by_run_type"] == {"SD": 16, "FS": 16, "test_data": 8}
    assert {"run_n", "run_method", "sys_alloc_cores"} <= set(features) and features["run_method"] == "categorical"
    assert "sys_gpu_name" not in features and report["constants"]["sys_gpu_name"] == "none"


def test_train_then_estimate(runs, tmp_path):
    out, est = tmp_path / "out", tmp_path / "est"
    summary = harp_train_runner.run({"name": "euler", "models": ["LR", "DTR"], "training_sets": ["SD", "SD+50FS"]},
                                    [str(runs)], str(out))
    assert summary["ok"], summary["error"]
    with open(out / "model_commons.csv") as f:
        metrics = parse_metrics(f.read())            # what the HARP server reads back
    assert {(m["RegModel"], m["DataSet"]) for m in metrics} == {(m, d) for m in ("LR", "DTR") for d in ("SD", "SD+50FS")}
    bundle = json.loads((out / "harp_model_bundle.json").read_text())
    assert bundle["best"]["MODEL_NAME"] in {m["MODEL_NAME"] for m in metrics}
    assert all(r["EVALUATED_ON"] == "test_data" for r in bundle["models"])
    assert "pitzer/serial" in bundle["hardware_catalog"]

    request = {"params": {"n": 2400, "method": "slow"}, "system_id": "pitzer", "queue": "serial", "cores": 16,
               "memory_mb": 64000}
    assert harp_estimate_runner.main([json.dumps({"model": "all", "requests": [request]}), "--models", str(out),
                                      "--output", str(est)]) == 0
    result = json.loads((est / "estimates.json").read_text())["estimates"]
    assert len(result) == len(metrics)
    truth = 2400 / 1000 * 3 * 16 / 16
    best = next(r for r in result if r["model"].startswith("LR_SD+50FS_no"))
    assert best["estimate_seconds"] == pytest.approx(truth, rel=0.5)
    assert all(r["padded_seconds"] >= r["estimate_seconds"] and r["suggested_max_minutes"] >= 1 for r in result)


def test_sd_only_runs_fall_back_to_cross_validation(runs, tmp_path):
    summary = harp_train_runner.run({"campaigns": ["aaaa1111"]}, [str(runs)], str(tmp_path / "out"))
    assert summary["ok"], summary["error"]
    assert set(summary["skipped"]) == {"SD+25FS", "SD+50FS", "SD+75FS"}
    bundle = json.loads((tmp_path / "out" / "harp_model_bundle.json").read_text())
    assert bundle["by_run_type"] == {"SD": 16, "FS": 0, "test_data": 0}
    assert bundle["best"]["EVALUATED_ON"].startswith("cross-validation")


def test_too_little_data_is_reported(tmp_path):
    root = tmp_path / "runs"
    make_campaign(str(root), "tiny", "cccc3333", [{"run_type": "SD", "parameters": {"n": [100], "method": ["fast"]}}],
                  [{"system_id": "pitzer", "queue": "serial", "cores_per_node": 4, "memory_mb": 16000}])
    summary = harp_train_runner.run({}, [str(root)], str(tmp_path / "out"))
    assert not summary["ok"] and "at least 3 usable runs" in summary["error"]


@pytest.mark.skipif(not os.path.isdir(EXAMPLES), reason="no example phase-1 runs")
def test_example_yolo_runs(tmp_path):
    summary = harp_train_runner.run({"name": "ultralytics_yolo"}, [EXAMPLES], str(tmp_path / "out"))
    assert summary["ok"], summary["error"]
    report = json.loads((tmp_path / "out" / "data_report.json").read_text())["clean"]
    assert report["rows_out"] == 5 and report["by_run_type"]["SD"] == 5
