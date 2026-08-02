/**
 * 実験管理画面の入力ルール（UI から切り離した純粋関数）。
 *
 * Streamlit 版 `app/views/experiments.py` のフォームに相当する検証をここに集約する。
 */
import type { TrainRequest } from '../types';

export interface TrainForm {
  dataYaml: string;
  baseModel: string;
  epochs: number;
  runName: string;
}

/** 学習フォームの初期値（Streamlit 版のウィジェット既定値と一致させる）。 */
export function defaultTrainForm(baseModel: string): TrainForm {
  return {
    dataYaml: 'data/datasets/custom/data.yaml',
    // Streamlit 版は selectbox の index=1（yolo11s）が既定。
    baseModel,
    epochs: 50,
    runName: '',
  };
}

/** 学習フォームの検証。問題があれば文言を返す（null なら実行可）。 */
export function validateTrainForm(form: TrainForm): string | null {
  if (form.dataYaml.trim() === '') return 'data.yaml のパスを入力してください。';
  if (!Number.isInteger(form.epochs) || form.epochs < 1 || form.epochs > 1000) {
    return 'epochs は 1〜1000 の整数で指定してください。';
  }
  return null;
}

/** 学習フォームを API のリクエストボディへ変換する。 */
export function toTrainRequest(form: TrainForm, experiment: string): TrainRequest {
  return {
    data_yaml: form.dataYaml.trim(),
    base_model: form.baseModel,
    epochs: form.epochs,
    experiment: experiment.trim() || null,
    // 空欄は「自動命名」なので null で送る。
    run_name: form.runName.trim() || null,
  };
}

/**
 * カンマ区切りのクラス名を正規化する（空白除去・空要素除去・重複排除）。
 *
 * **クラス ID は並び順で決まる**ため、入力順を保持する（ソートしない）。
 * サーバ側 `parse_classes` と同じ規則。
 */
export function parseClasses(text: string): string[] {
  const classes: string[] = [];
  for (const chunk of text.split(',')) {
    const name = chunk.trim();
    if (name !== '' && !classes.includes(name)) classes.push(name);
  }
  return classes;
}
