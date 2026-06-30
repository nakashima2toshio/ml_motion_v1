# data/ — サンプル動画・データセット置き場

解析（Phase 1/2/5）の入力に使う動画や、学習（Phase 4）用データセットを置くディレクトリ。

- **動画・データセットの実体は Git 管理外**（`.gitignore` で `data/*.mp4` / `*.mov` / `*.avi` / `data/datasets/` を除外）。この README と `.gitkeep` のみコミットされる。
- 解析ページの **Upload** はローカルのどこからでもファイルを選べるが、整理のためここに置くことを推奨。

## サンプル動画の取得

```bash
bash scripts/fetch_sample_videos.sh
```

`data/` に以下が保存される（取得元: [intel-iot-devkit/sample-videos](https://github.com/intel-iot-devkit/sample-videos)、物体検出デモで広く使われる公開リポジトリ）。

| ファイル | 内容 | 主な対象クラス |
|---|---|---|
| `sample_person_bicycle_car.mp4` | 人・自転車・車が混在 | person / bicycle / car |
| `sample_people.mp4` | 人物中心 | person |
| `sample_car.mp4` | 車両中心 | car |

> ライセンス・利用条件は取得元リポジトリに従うこと。商用利用や再配布の前に元リポジトリの規約を確認する。

## 自分で用意する場合

iPhone / QuickTime 等で撮影した mp4 を AirDrop 等で Mac に転送し、ここに置く。
解析ページの Upload で選択 → **▶ Run 解析**（初回は `yolo11s.pt` が自動ダウンロード）。

## 学習用データセット（Phase 4）

`data/datasets/<name>/` に YOLO 標準レイアウト（`images/train`・`images/val`・`labels/...`）で配置し、
`data.yaml` を「実験管理」ページの「data.yaml 生成」で作成する（`data/datasets/` も Git 管理外）。
