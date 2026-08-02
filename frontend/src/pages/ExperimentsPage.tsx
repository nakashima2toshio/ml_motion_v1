/** 実験管理画面（R3 で実装）。移行元: app/views/experiments.py */
import { PagePlaceholder } from '../components/PagePlaceholder';
import { findPage } from '../nav';

export function ExperimentsPage(): JSX.Element {
  return (
    <PagePlaceholder
      page={findPage('/experiments')!}
      manual="03_experiments.md"
      features={[
        'MLflow Tracking URI の表示と Run 一覧の取得',
        'Run 比較テーブルと最良 Run（mAP50-95）',
        '転移学習ジョブの起動（data.yaml / ベースモデル / epochs / Run 名）',
        'データセット data.yaml の生成',
        'Model Registry のステージ表示',
      ]}
    />
  );
}
