"""検出結果のデータ構造とエクスポート（Phase 1）。

重い依存（cv2 / ultralytics / supervision）を持たない純粋なレイヤー。
CSV/JSON エクスポートと集計は標準ライブラリのみで完結し、単体テスト可能にする。
表示用 DataFrame だけ pandas を遅延 import する。
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass

# COCO の代表クラス（仕様書 §6 の初期クラス例）。サイドバーの既定選択に使う。
COCO_COMMON: dict[str, int] = {
    "person": 0,
    "bicycle": 1,
    "car": 2,
    "motorcycle": 3,
    "bus": 5,
    "truck": 7,
}

# エクスポートの列順（CSV ヘッダ／DataFrame 列）。
FIELDS: tuple[str, ...] = (
    "frame",
    "time_sec",
    "class_id",
    "class_name",
    "confidence",
    "x1",
    "y1",
    "x2",
    "y2",
)


@dataclass
class DetectionRecord:
    """1 フレーム中の 1 検出ボックス。"""

    frame: int
    time_sec: float
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def to_csv_bytes(records: list[DetectionRecord]) -> bytes:
    """検出レコードを CSV（UTF-8 BOM 付き / Excel 互換）バイト列に変換する。"""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(FIELDS))
    writer.writeheader()
    for r in records:
        writer.writerow(r.to_dict())
    # Excel で文字化けしないよう BOM を付与する。
    return buf.getvalue().encode("utf-8-sig")


def to_json_bytes(records: list[DetectionRecord]) -> bytes:
    """検出レコードを JSON 配列のバイト列に変換する。"""
    payload = [r.to_dict() for r in records]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def summarize(records: list[DetectionRecord]) -> dict[str, dict[str, int]]:
    """クラス別に「総検出数」と「単一フレーム内の最大同時数」を集計する。

    戻り値: {class_name: {"total": 総検出数, "max_in_frame": 最大同時数}}
    トラッキング（ID）は Phase 2 で導入するため、ここでは延べ検出数ベース。
    """
    total: dict[str, int] = {}
    per_frame: dict[tuple[int, str], int] = {}
    for r in records:
        total[r.class_name] = total.get(r.class_name, 0) + 1
        key = (r.frame, r.class_name)
        per_frame[key] = per_frame.get(key, 0) + 1

    max_in_frame: dict[str, int] = {}
    for (_frame, name), count in per_frame.items():
        if count > max_in_frame.get(name, 0):
            max_in_frame[name] = count

    return {
        name: {"total": total[name], "max_in_frame": max_in_frame.get(name, 0)}
        for name in sorted(total)
    }
