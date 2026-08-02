/** リアルタイム画面（R5 で実装）。移行元: app/views/realtime.py */
import { PagePlaceholder } from '../components/PagePlaceholder';
import { findPage } from '../nav';

export function RealtimePage(): JSX.Element {
  return (
    <PagePlaceholder
      page={findPage('/realtime')!}
      manual="02_realtime.md"
      features={[
        'Continuity Camera 経路（サーバ側 OpenCV → MJPEG 配信）',
        'ブラウザカメラ経路（getUserMedia → WebSocket 推論。streamlit-webrtc の置き換え）',
        'カメラ index / 開始・停止',
        '解像度プリセット・フレームスキップ・軽量モデルへの自動切替',
        'FPS・検出数の表示',
      ]}
    />
  );
}
