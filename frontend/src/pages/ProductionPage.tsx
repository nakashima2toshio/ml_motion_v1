/** 本番化・最適化画面（R4 で実装）。移行元: app/views/production.py */
import { PagePlaceholder } from '../components/PagePlaceholder';
import { findPage } from '../nav';

export function ProductionPage(): JSX.Element {
  return (
    <PagePlaceholder
      page={findPage('/production')!}
      manual="04_production.md"
      features={[
        '入力ディレクトリの確認とバッチ推論（進捗は SSE）',
        'バッチ結果のマニフェスト表示',
        'モデル変換（ONNX / CoreML / TorchScript / TensorRT）と量子化（FP32 / FP16 / INT8）',
        'レイテンシ・スループット計測',
        'Model Registry からのモデル取得・差し替え',
      ]}
    />
  );
}
