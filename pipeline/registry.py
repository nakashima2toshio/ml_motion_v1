"""MLflow Model Registry ヘルパー（Phase 4）。

ステージ管理（Staging/Production/Archived）とモデル登録を扱う。
mlflow は重い依存のため遅延 import。ステージ正規化は依存なしで単体テスト可能。
"""

from __future__ import annotations

# MLflow Model Registry の標準ステージ（mlflow<3 の stage API）。
STAGES: tuple[str, ...] = ("None", "Staging", "Production", "Archived")

_ALIASES = {
    "none": "None",
    "staging": "Staging",
    "stage": "Staging",
    "production": "Production",
    "prod": "Production",
    "archived": "Archived",
    "archive": "Archived",
}


def normalize_stage(stage: str) -> str:
    """ステージ名の表記ゆれを標準形へ正規化する（不正値は ValueError）。"""
    key = stage.strip().lower()
    if key not in _ALIASES:
        raise ValueError(f"未知のステージ: {stage!r}（許可: {', '.join(STAGES)}）")
    return _ALIASES[key]


def register_model(run_id: str, artifact_path: str, model_name: str) -> str:
    """Run の成果物を Model Registry に登録し、バージョン番号を返す（mlflow 遅延 import）。"""
    import mlflow

    mlflow.set_tracking_uri(_tracking_uri())
    result = mlflow.register_model(model_uri=f"runs:/{run_id}/{artifact_path}", name=model_name)
    return result.version


def transition_stage(model_name: str, version: str, stage: str, archive_existing: bool = True) -> None:
    """登録済みモデルバージョンのステージを遷移させる（mlflow 遅延 import）。"""
    from mlflow.tracking import MlflowClient

    target = normalize_stage(stage)
    client = MlflowClient(tracking_uri=_tracking_uri())
    client.transition_model_version_stage(
        name=model_name,
        version=version,
        stage=target,
        archive_existing_versions=archive_existing,
    )


def list_versions(model_name: str) -> list[dict]:
    """登録済みモデルのバージョン一覧（mlflow 遅延 import）。"""
    from mlflow.tracking import MlflowClient

    client = MlflowClient(tracking_uri=_tracking_uri())
    versions = client.search_model_versions(f"name='{model_name}'")
    return [{"version": v.version, "stage": v.current_stage, "run_id": v.run_id} for v in versions]


def _tracking_uri() -> str:
    from pipeline.experiments import tracking_uri

    return tracking_uri()
