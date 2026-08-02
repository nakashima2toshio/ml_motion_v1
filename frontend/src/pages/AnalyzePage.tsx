/** 解析画面（R1 で実装）。移行元: app/views/analyze.py */
import { PagePlaceholder } from '../components/PagePlaceholder';
import { findPage } from '../nav';

export function AnalyzePage(): JSX.Element {
  return (
    <PagePlaceholder
      page={findPage('/analyze')!}
      manual="01_analyze.md"
      features={[
        'mp4/mov/avi のアップロードと ▶ Run 解析',
        'セグメンテーション / トラッキング（ByteTrack）/ ゾーン解析の切り替え',
        'モデル・信頼度しきい値・対象クラス・フレーム間引き・軌跡の長さの設定',
        'ゾーン定義（正規化 0〜1 の JSON）',
        '進捗表示（SSE）と注釈付き動画のプレビュー',
        '総検出数 / ユニークID数 / 処理フレーム / クラス別（延べ・最大同時）',
        'ゾーン解析テーブル・ID別滞留時間・検出結果テーブル',
        'CSV / JSON / 注釈付き動画のダウンロード',
        'NL要約（Claude）',
      ]}
    />
  );
}
