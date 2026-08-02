/** アノテーション QA 画面（R2 で実装）。移行元: app/views/annotation_qa.py */
import { PagePlaceholder } from '../components/PagePlaceholder';
import { findPage } from '../nav';

export function AnnotationQaPage(): JSX.Element {
  return (
    <PagePlaceholder
      page={findPage('/annotation-qa')!}
      manual="05_annotation_qa.md"
      features={[
        'フレーム画像のアップロードとプレビュー',
        '提案ラベル（カンマ区切り）の入力',
        'Claude Vision によるアノテーション妥当性レビュー',
        'レビュー結果（Markdown）の表示',
      ]}
    />
  );
}
