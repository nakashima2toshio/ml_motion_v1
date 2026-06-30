"""データセット設計ヘルパー（Phase 4）。

YOLO 形式の data.yaml 生成・train/val 分割・クラス定義を扱う。
重い依存を持たず（PyYAML のみ）単体テスト可能にする。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DatasetSpec:
    """データセット定義（クラス・分割・パスの命名規約）。

    root 配下に images/{train,val} と labels/{train,val} を置く YOLO 標準レイアウトを想定。
    """

    name: str
    classes: list[str]
    root: str = "data/datasets"
    train_subdir: str = "images/train"
    val_subdir: str = "images/val"

    def class_map(self) -> dict[int, str]:
        """クラス ID → 名前。"""
        return {i: c for i, c in enumerate(self.classes)}


def build_dataset_yaml(spec: DatasetSpec) -> str:
    """ultralytics 学習用の data.yaml テキストを生成する。"""
    import yaml

    doc = {
        "path": f"{spec.root}/{spec.name}",
        "train": spec.train_subdir,
        "val": spec.val_subdir,
        "names": spec.class_map(),
    }
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


def train_val_split(items: list[str], val_ratio: float = 0.2) -> tuple[list[str], list[str]]:
    """ファイル一覧を決定的に train/val へ分割する（乱数非依存・再現性確保）。

    ソート後、step = round(1/val_ratio) ごとに val へ割り当てる。
    val_ratio<=0 なら全件 train、val_ratio>=1 なら全件 val。
    """
    ordered = sorted(items)
    if val_ratio <= 0:
        return ordered, []
    if val_ratio >= 1:
        return [], ordered
    step = max(2, round(1 / val_ratio))
    val = ordered[::step]
    val_set = set(val)
    train = [x for x in ordered if x not in val_set]
    return train, val
