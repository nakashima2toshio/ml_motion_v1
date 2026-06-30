"""Phase 4 の依存なしロジック（dataset / experiments 整形 / registry ステージ）の単体テスト。"""

from __future__ import annotations

import pytest
import yaml

from pipeline.dataset import DatasetSpec, build_dataset_yaml, train_val_split
from pipeline.experiments import best_run, format_runs_table
from pipeline.registry import STAGES, normalize_stage


# ---- dataset ----
def test_dataset_class_map():
    spec = DatasetSpec(name="custom", classes=["person", "car"])
    assert spec.class_map() == {0: "person", 1: "car"}


def test_build_dataset_yaml_parses():
    spec = DatasetSpec(name="custom", classes=["person", "car"], root="data/datasets")
    text = build_dataset_yaml(spec)
    doc = yaml.safe_load(text)
    assert doc["path"] == "data/datasets/custom"
    assert doc["train"] == "images/train"
    assert doc["names"] == {0: "person", 1: "car"}


def test_train_val_split_deterministic():
    items = [f"img{i}.jpg" for i in range(10)]
    train1, val1 = train_val_split(items, val_ratio=0.2)
    train2, val2 = train_val_split(items, val_ratio=0.2)
    assert (train1, val1) == (train2, val2)  # 決定的
    assert set(train1) | set(val1) == set(items)  # 全件カバー
    assert set(train1) & set(val1) == set()       # 重複なし
    assert len(val1) > 0


def test_train_val_split_edge_ratios():
    items = ["a", "b", "c"]
    assert train_val_split(items, 0.0) == (["a", "b", "c"], [])
    assert train_val_split(items, 1.0) == ([], ["a", "b", "c"])


# ---- experiments 整形 ----
def _runs():
    return [
        {"run_name": "baseline", "status": "FINISHED",
         "metrics": {"metrics/mAP50(B)": 0.74, "metrics/mAP50-95(B)": 0.49}},
        {"run_name": "ft_v2", "status": "FINISHED",
         "metrics": {"metrics/mAP50(B)": 0.81, "metrics/mAP50-95(B)": 0.55}},
    ]


def test_format_runs_table():
    rows = format_runs_table(_runs())
    assert rows[0] == {"run": "baseline", "status": "FINISHED", "mAP50": 0.74, "mAP50-95": 0.49}


def test_format_runs_table_missing_metrics():
    rows = format_runs_table([{"run_name": "x", "status": "RUNNING", "metrics": {}}])
    assert rows[0]["mAP50"] == 0.0


def test_best_run_picks_max():
    assert best_run(_runs())["run_name"] == "ft_v2"


def test_best_run_empty():
    assert best_run([]) is None


# ---- registry ステージ ----
def test_normalize_stage_aliases():
    assert normalize_stage("prod") == "Production"
    assert normalize_stage("STAGING") == "Staging"
    assert normalize_stage(" archive ") == "Archived"


def test_normalize_stage_invalid():
    with pytest.raises(ValueError):
        normalize_stage("bogus")


def test_stages_constant():
    assert STAGES == ("None", "Staging", "Production", "Archived")
