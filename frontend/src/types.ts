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
  claude_model: string;
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

// ---------------------------------------------------------------------------
// 解析画面（app/views/analyze.py 相当）
// ---------------------------------------------------------------------------

/** POST /api/analyze/upload */
export interface UploadInfo {
  upload_id: string;
  filename: string;
  size: number;
}

/** ゾーン定義（正規化座標 0〜1） */
export interface ZoneInput {
  name: string;
  polygon: [number, number][];
}

/** POST /api/analyze/run */
export interface AnalyzeRequest {
  upload_id: string;
  enable_seg: boolean;
  enable_track: boolean;
  enable_zone: boolean;
  model_name: string;
  conf: number;
  /** null は「全クラス（COCO 80）」 */
  classes: number[] | null;
  frame_stride: number;
  trace_length: number;
  zones: ZoneInput[];
}

/** クラス別集計（`pipeline.detections.summarize`） */
export interface ClassStat {
  total: number;
  max_in_frame: number;
}

/** ゾーン別集計（`pipeline.zones.ZoneAnalyzer.summary`） */
export interface ZoneStat {
  unique_tracks: number;
  intrusions: number;
  max_occupancy: number;
  total_dwell_sec: number;
  max_dwell_sec: number;
}

/** ID 別滞留時間 */
export interface TrackDwell {
  zone: string;
  tracker_id: number;
  dwell_sec: number;
}

/** GET /api/analyze/result/{job_id} の result（検出レコードは含まない） */
export interface AnalyzeResultSummary {
  run_id: string;
  stem: string;
  video_url: string | null;
  frames_processed: number;
  frames_total: number;
  fps: number;
  width: number;
  height: number;
  duration_sec: number;
  total_detections: number;
  unique_track_ids: number;
  stats: Record<string, ClassStat>;
  zone_summary: Record<string, ZoneStat>;
  per_track_dwell: TrackDwell[];
  total_records: number;
}

/** 検出結果 1 行（`pipeline.detections.DetectionRecord`） */
export interface DetectionRecord {
  frame: number;
  time_sec: number;
  class_id: number;
  class_name: string;
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  tracker_id: number | null;
}

/** GET /api/analyze/detections/{job_id} */
export interface DetectionPage {
  total: number;
  offset: number;
  limit: number;
  records: DetectionRecord[];
}

// ---------------------------------------------------------------------------
// アノテーション QA（app/views/annotation_qa.py 相当）
// ---------------------------------------------------------------------------

/** POST /api/annotation/review */
export interface AnnotationReview {
  /** Claude Vision のレビュー結果（Markdown） */
  review: string;
  model: string;
  /** サーバ側で正規化された提案ラベル */
  labels: string[];
}
