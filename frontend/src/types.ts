/**
 * バックエンド `backend/app/schemas.py` と 1:1 対応する型。
 * 片方だけ変えないこと（API スキーマを変えたらここも必ず追随させる）。
 */

/** GET /api/health */
export interface Health {
  status: string;
  version: string;
}

/** GET /api/meta/device — Streamlit 版の上部デバイス表示に相当 */
export interface DeviceInfo {
  device: string;
  torch: string | null;
  mps_available: boolean;
  cuda_available: boolean;
}

/** GET /api/meta/options — 各画面の選択肢（pipeline の定数の写し） */
export interface Options {
  models: string[];
  seg_models: string[];
  lightweight_models: string[];
  coco_common: Record<string, number>;
  resolution_presets: Record<string, [number, number]>;
  export_formats: string[];
  registry_stages: string[];
  default_experiment: string;
  detection_fields: string[];
}

/** ジョブ起動（202） */
export interface JobAccepted {
  job_id: string;
}

/** SSE で流れる 1 イベント */
export interface JobEvent {
  seq: number;
  ts: number;
  type: 'started' | 'progress' | 'done' | 'error';
  message: string;
  data: Record<string, unknown>;
}

/** progress イベントの data */
export interface JobProgress {
  current: number;
  total: number;
}

/** GET /api/xxx/result/{job_id} */
export interface JobStatus<T = Record<string, unknown>> {
  job_id: string;
  kind: string;
  status: 'running' | 'completed' | 'failed';
  result: T | null;
  error: string | null;
}
