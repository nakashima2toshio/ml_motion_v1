/**
 * リアルタイム画面の設定とクエリ組み立て（純粋関数）。
 *
 * Streamlit 版 `app/views/realtime.py` のサイドバーに対応する。
 * サーバ側 `core/realtime_session.py` の `resolve_settings` と規則を揃える。
 */
import type { Options } from '../types';

/** 取り込み経路。 */
export type RealtimeRoute = 'camera' | 'browser';

export interface RealtimeSettings {
  route: RealtimeRoute;
  cameraIndex: number;
  enableSeg: boolean;
  enableTrack: boolean;
  /** ユーザーが選んだモデル（自動切替前） */
  modelName: string;
  autoLight: boolean;
  conf: number;
  resolution: string;
  frameSkip: number;
}

/** 初期値（Streamlit 版のウィジェット既定値と一致させる）。 */
export function defaultRealtimeSettings(options: Options | null): RealtimeSettings {
  return {
    route: 'camera',
    cameraIndex: 0,
    enableSeg: false,
    enableTrack: true,
    // Streamlit 版のリアルタイム画面は selectbox の index=0（yolo11n）が既定。
    modelName: options?.models[0] ?? 'yolo11n.pt',
    autoLight: true,
    conf: 0.25,
    resolution: options ? Object.keys(options.resolution_presets)[0] : '640x360',
    frameSkip: 1,
  };
}

/** 現在のタスクで選べるモデル一覧（セグ ON なら -seg 系）。 */
export function realtimeModels(settings: RealtimeSettings, options: Options | null): string[] {
  if (!options) return [];
  return settings.enableSeg ? options.seg_models : options.models;
}

/**
 * セグの ON/OFF でモデル一覧が入れ替わるので、同グレードのモデルへ寄せる。
 * （`analyzeSettings.correspondingModel` と同じ規則）
 */
export function normalizeRealtimeSettings(
  settings: RealtimeSettings,
  options: Options | null,
): RealtimeSettings {
  const models = realtimeModels(settings, options);
  if (models.length === 0 || models.includes(settings.modelName)) return settings;

  const grade = /yolo11([nsmlx])/.exec(settings.modelName)?.[1];
  const matched = grade ? models.find((name) => name.startsWith(`yolo11${grade}`)) : undefined;
  return { ...settings, modelName: matched ?? models[0] };
}

/**
 * API へ渡すクエリ文字列を組み立てる。
 *
 * MJPEG / WebSocket / settings で同じパラメータを使うため 1 箇所にまとめる。
 * `camera_index` は経路1でしか使わないが、送っても無害なので常に含める。
 */
export function toRealtimeQuery(settings: RealtimeSettings): string {
  return new URLSearchParams({
    camera_index: String(settings.cameraIndex),
    model_name: settings.modelName,
    enable_seg: String(settings.enableSeg),
    enable_track: String(settings.enableTrack),
    auto_light: String(settings.autoLight),
    conf: String(settings.conf),
    resolution: settings.resolution,
    frame_skip: String(settings.frameSkip),
  }).toString();
}
