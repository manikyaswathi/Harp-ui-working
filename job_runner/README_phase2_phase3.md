# HARP phase 2 (train) and phase 3 (estimate) containers

Phase 1 (the sweep jobs) leaves a results folder that grows with every sweep. Phase 2
reads all of it, cleans it and trains the runtime estimators picked in the UI. Phase 3
uses those models to estimate how long a new run will take, and how many minutes to ask for.

```
 phase 1 results folder ──► harp-train (phase 2) ──► models folder ──► harp-estimate (phase 3) ──► estimates
 harp_runs/<sweep>-<id>/     ingest, clean,          model_commons.csv    params + system/queue/cores   estimates.json
   campaign_spec.json        train, score,           models/*.joblib      -> features -> models          estimates.csv
   manifest.json             select                  harp_model_bundle.json
   jobs/<job>/harp_profile.csv
   <app>_<timestamp>.csv
```

| File | What it is |
|---|---|
| `harp_modeling.py` | Shared: reads phase-1 folders / zips / CSVs, cleans, hardware catalog, scores |
| `harp_train_runner.py` | Phase 2 entry point |
| `harp_estimate_runner.py` | Phase 3 entry point |
| `requirements-model.txt` | Pinned numpy, pandas, scikit-learn, joblib (shared by both images) |
| `../DockerFiles/Dockerfile_HARP_Phase2_Train` | `harp-train` image |
| `../DockerFiles/Dockerfile_HARP_Phase3_Estimate` | `harp-estimate` image |

## Build the images

From the repository root:

```bash
docker build -f DockerFiles/Dockerfile_HARP_Phase2_Train    -t <hub>/harp-train:1.0.0 .
docker build -f DockerFiles/Dockerfile_HARP_Phase3_Estimate -t <hub>/harp-estimate:1.0.0 .
docker push <hub>/harp-train:1.0.0 && docker push <hub>/harp-estimate:1.0.0
```

Both pin the same library versions on purpose: a scikit-learn model only loads in the version that saved it.

## Phase 2: train

```bash
docker run --rm -v $PWD/harp_runs:/TapisInput:ro -v $PWD/out:/TapisOutput <hub>/harp-train:1.0.0 \
  '{"name": "ultralytics_yolo", "models": ["LR", "NN", "DTR"], "training_sets": ["SD", "SD+25FS", "SD+50FS", "SD+75FS"]}'
```

`/TapisInput` can hold the results folder itself, zips of it (like `Del_example_runs/*.zip`), or plain CSVs.
Without Docker: `python3 job_runner/harp_train_runner.py '<spec>' --runs harp_runs --output out`.
The spec can be raw JSON, a JSON file, or URL-safe base64 JSON (how the HARP server passes it to TAPIS jobs).
Every key is optional:

| Key | Meaning | Default |
|---|---|---|
| `models` | `LR` (linear regression), `NN` (neural network), `DTR` (decision tree) | all three |
| `training_sets` | `SD`, `SD+25FS`, `SD+50FS`, `SD+75FS` | all four |
| `application` | Which app to train on, when the folder holds several | the only one there |
| `campaigns` | Sweep IDs to learn from (the 8-character suffix of the folder) | all |
| `policy` | How the best model is picked: `mape` (smallest error) or `underpredict` (fewest under-estimates, then smallest overshoot, as the original HARP Predictor did) | `mape` |
| `cv_folds` | Folds for cross-validation when there are no test_data runs | `5` |
| `max_missing` | Drop a column missing in more than this share of runs; impute the rest | `0.3` |
| `outliers` | Drop outlier walltimes among repeats of one configuration | `true` |

### What it does

1. **Ingest.** Every sweep folder (`campaign_spec.json`) is read: each job's `harp_profile.csv` *and* the merged CSV,
   so runs are kept even when a sweep never merged. Each row is tagged with its sweep, job, and the system, queue,
   cores, memory and nodes its job was given, by re-deriving the job plan from `campaign_spec.json`.
   Runs in `harp_failures.csv` are counted, never used.
2. **Clean.** Keep SD / FS / test_data runs with a positive walltime; drop duplicates (the same run is in its job's CSV,
   the merged CSV and any copied results folder); turn `true/false` into `1/0`; drop columns that are mostly empty or
   never vary (their values are remembered for phase 3); drop walltimes more than 3.5 robust z-scores from the median
   among four or more repeats of one configuration. Everything dropped, and why, is in `data_report.json`.
3. **Features.** `run_<param>` columns, what the job was given (`system_id`, `queue`, `sys_alloc_cores`,
   `sys_alloc_mem_mb`, `sys_alloc_nodes`) and the measured node hardware (`sys_*`), whichever vary. Numbers are
   imputed (median) and scaled; text is imputed (most frequent) and one-hot encoded. That preprocessing is saved
   inside each model, so phase 3 feeds raw values.
4. **Train and score.** Each picked model on each picked training set, the way the HARP pipeline splits data:
   validation = 25% of FS runs (sets the adjustment factor), test = test_data runs, and SD+xFS adds x% of the FS runs,
   resampled to as many runs as SD. With no test_data runs the scores come from cross-validation instead, and
   training sets that need FS runs are skipped when there are none. Each model is scored as-is and *padded*
   (multiplied by its adjustment factor, 1 + the average miss of the runs it under-estimated), with the pipeline's
   metrics: MSE, MAE, MAPE, UPP (% under-estimated), UP_MAPE, OV_MAPE.
5. **Select** the best model by `policy`.

### Output

| File | Contents |
|---|---|
| `consolidated_runs.csv` | Every run read, with where it came from |
| `training_data.csv` | The cleaned table the models learned from |
| `data_report.json` | Sweeps read, rows and columns dropped and why, counts per run type / sweep / queue |
| `model_commons.csv` | One row per model, as-is and padded (same columns the HARP server reads) |
| `models/<model>_<training set>_<time>.joblib` | The trained models |
| `harp_model_bundle.json` | What phase 3 needs: features, hardware catalog per system/queue, profiled ranges, models, best |
| `harp_build_summary.json`, `harp_progress.json` | Result and live progress, as the HARP server expects from a build job |

## Phase 3: estimate

```bash
docker run --rm -v $PWD/out:/TapisInput:ro -v $PWD/estimates:/TapisOutput <hub>/harp-estimate:1.0.0 \
  '{"model": "best", "margin": 0.1, "requests": [
     {"name": "4 epochs, 8 cores", "params": {"epochs": 4, "model": "yolo11n"},
      "system_id": "ascend-tapis", "queue": "debug", "cores": 8, "memory_mb": 32768}]}'
```

Without Docker: `python3 job_runner/harp_estimate_runner.py '<spec>' --models out --output estimates`.
`--requests file.json|file.csv` takes the requests from a file (CSV: `name, system_id, queue, cores, memory_mb, nodes`
and one column per parameter). `model` is `best`, `all`, or a `MODEL_NAME` from `model_commons.csv`.

For each request it builds the same features phase 2 used. Node hardware not given in `hardware` is taken from the
runs profiled on that system and queue (or the system's other queues). Each estimate has the model's raw estimate,
the padded estimate, and `suggested_max_minutes` (padded estimate + `margin`, rounded up). It also has warnings when
a value is outside what was profiled (an extrapolation), when a parameter was never varied, or when the queue was never
profiled. Results: `estimates.json`, `estimates.csv`, `harp_estimate_summary.json`.

## Try it on the example runs

```bash
python3 job_runner/harp_train_runner.py --runs Del_example_runs --output /tmp/harp_out
python3 job_runner/harp_estimate_runner.py \
  '{"requests": [{"params": {"epochs": 4}, "system_id": "ascend-tapis", "queue": "debug", "cores": 8, "memory_mb": 32768}]}' \
  --models /tmp/harp_out --output /tmp/harp_est
```

The two zips hold four YOLO sweeps (one is a copy of the other's folder). Of 20 rows read, 5 distinct successful
runs remain, all SD on `ascend-tapis/debug`, varying only epochs (1, 4) and cores (4, 8, 60). That is enough to exercise
the whole pipeline but not to trust the models: the SD+xFS sets are skipped (no FS runs), scores come from
cross-validation over 5 runs, and estimates outside 1 to 4 epochs are flagged as extrapolations. Add FS and
test_data sweeps to get real scores.

## Tests

```bash
cd harp_server && python3 -m pytest -q tests/test_phase2_phase3.py
```
