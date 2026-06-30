# data/ — テスト動画の置き場所

開発・テストで使う動画ファイルを置くディレクトリ。
**動画本体は Git にコミットしない**（`.gitignore` で `*.mp4` 等を除外）。
取得スクリプトだけをリポジトリで共有し、各自が実行して取得する。

```
data/
├── README.md       # このファイル（コミット対象）
├── .gitkeep        # ディレクトリ保持用（コミット対象）
└── raw/            # 取得した動画（Git 管理外）
```

## 取得方法

依存ライブラリ `supervision`（`requirements.txt` に同梱）の公式アセットを使う。

```bash
# 推奨セット（車両 VEHICLES + 歩行者 PEOPLE_WALKING）を data/raw/ に取得
python scripts/download_test_videos.py

# 利用可能なアセット一覧
python scripts/download_test_videos.py --list

# 個別指定 / 全取得
python scripts/download_test_videos.py --assets VEHICLES SUBWAY MARKET_SQUARE
python scripts/download_test_videos.py --all
```

## 動画の用途（仕様書 `docs/ml_motion_detection_spec.md` 対応）

| アセット | 主な用途 | 対応フェーズ |
|---|---|---|
| `VEHICLES` | 道路・車。車両カウント / ゾーン侵入の定番 | P1 検出 / P2 ゾーン解析 |
| `PEOPLE_WALKING` | 歩行者。ByteTrack による ID 付与・滞留時間 | P2 追跡 |
| `SUBWAY` | 改札・通路。ゾーン通過カウント | P2 ゾーン解析 |
| `MARKET_SQUARE` | 広場・群衆。密集シーンでの ID 維持の堅牢性 | P2 追跡 |

いずれも COCO 事前学習（`person` / `car` / `bus` / `truck` / `bicycle` 等）で
そのまま検出でき、YOLO11 → ByteTrack → supervision ゾーン解析の検証に使える。
