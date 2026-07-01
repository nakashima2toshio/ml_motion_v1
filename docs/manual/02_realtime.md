# 📡 リアルタイム画面 操作マニュアル

**画面**: 左ナビ「リアルタイム」（`app/views/realtime.py`）。

## 目的
iPhone / Web カメラの映像を**準リアルタイム**に検出（＋追跡）する。2 経路を選べる。

- **Continuity Camera (OpenCV)**（既定・最推奨）：iPhone を Mac のカメラとして取り込む。**ローカル実行（Mac 上の `streamlit run`）専用**。
- **ブラウザ (streamlit-webrtc)**（代替）：ブラウザのカメラを使う。追加依存が必要。

## 事前準備
- Continuity Camera：macOS Ventura+ / iPhone XR+。iPhone を Mac の近くに置き Continuity Camera を有効化。
- ブラウザ経路：`uv pip install -e '.[realtime]'`（streamlit-webrtc / av）。

## 画面の構成（サイドバー）
| セクション | 項目 | 種類 | 既定 | 説明 |
|---|---|---|---|---|
| 取り込み経路 | 経路 | ラジオ | Continuity Camera (OpenCV) | もう一方は「ブラウザ (streamlit-webrtc)」 |
| タスク | セグメンテーション | チェック | OFF | マスク描画 |
| タスク | トラッキング（ByteTrack） | チェック | ON | ID・軌跡 |
| モデル | YOLO11 モデル | 選択 | 先頭(n) | seg 時は `-seg` |
| モデル | リアルタイム用に軽量モデルへ自動切替 | チェック | ON | 重いモデル選択時に自動で `yolo11s` へ（`⚡ 自動切替` 表示） |
| モデル | 信頼度しきい値 | スライダ | 0.25 | |
| スループット最適化 | 解像度 | 選択 | 640x360 | 960x540 / 1280x720 も可（大きいほど重い） |
| スループット最適化 | フレームスキップ（N フレームに1回推論） | スライダ | 1 | 上げると fps 向上・検出は間引き |

## 操作手順

### 経路1: Continuity Camera（OpenCV）
1. iPhone を Mac の近くに置き Continuity Camera を有効化。
2. 経路＝「Continuity Camera (OpenCV)」を選択。
3. **カメラ index** を指定（`0`=内蔵、`1`〜=外部/iPhone）。
4. **▶ 開始 / ⏹ 停止** トグルを ON にすると取り込み開始。中央に注釈付き映像、下に `FPS / 検出数 / frame` が更新。
5. 停止はトグルを OFF。

### 経路2: ブラウザ（streamlit-webrtc）
1. `uv pip install -e '.[realtime]'` を実行済みにする。
2. 経路＝「ブラウザ (streamlit-webrtc)」を選択。
3. ブラウザのカメラ許可ダイアログで iPhone/Web カメラを選択 → 映像に注釈が重なる。

## 出力・結果の見方
- 中央：検出（＋追跡なら ID・軌跡）を重ねたライブ映像。
- 直下キャプション：`FPS: xx.x / 検出数: n / frame i`。目標は **≥10fps**。

## つまずきやすい点（トラブルシュート）
| 症状 | 対処 |
|---|---|
| 「フレームを取得できませんでした」 | カメラ index を変える（0/1/2…）、iPhone の Continuity 有効化を確認 |
| Continuity 経路が動かない | この経路は**ローカルの `streamlit run` 専用**。リモート/クラウドでは不可 |
| ブラウザ経路が「追加依存が必要」 | `uv pip install -e '.[realtime]'` を実行 |
| fps が出ない | 解像度を 640x360 に、フレームスキップを上げる、軽量モデル自動切替を ON、モデルを n/s へ |
| 重いモデル警告（⚠️） | 自動切替 ON か、手動で yolo11n/s を選ぶ |
