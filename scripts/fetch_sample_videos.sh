#!/usr/bin/env bash
# サンプル動画を data/ に取得する（Phase 1/2/5 の動作確認用）。
#
# 使い方:
#   bash scripts/fetch_sample_videos.sh
#
# 取得元: intel-iot-devkit/sample-videos（物体検出デモで広く使われる公開リポジトリ）。
# COCO 代表クラス（person / bicycle / car 等）が映るため、既定モデルでそのまま検出できる。
# data/*.mp4 は .gitignore 済みのためリポジトリには含まれない。
set -euo pipefail

# リポジトリルート直下の data/ を出力先にする（スクリプトの場所基準で解決）。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_DIR="${ROOT_DIR}/data"
mkdir -p "${OUT_DIR}"

BASE="https://github.com/intel-iot-devkit/sample-videos/raw/master"

# 取得対象: 出力ファイル名 元ファイル名
declare -a SAMPLES=(
  "sample_person_bicycle_car.mp4 person-bicycle-car-detection.mp4"
  "sample_people.mp4 people-detection.mp4"
  "sample_car.mp4 car-detection.mp4"
)

for entry in "${SAMPLES[@]}"; do
  out="${entry%% *}"
  src="${entry##* }"
  dest="${OUT_DIR}/${out}"
  if [[ -f "${dest}" ]]; then
    echo "skip (既に存在): ${dest}"
    continue
  fi
  echo "download: ${src} -> ${dest}"
  curl -fL --retry 3 -o "${dest}" "${BASE}/${src}"
done

echo ""
echo "完了。取得した動画:"
ls -lh "${OUT_DIR}"/*.mp4 2>/dev/null || echo "(mp4 なし)"
echo ""
echo "次: streamlit run app/Home.py →「解析」ページの Upload で data/ の mp4 を選択 → ▶ Run 解析"
