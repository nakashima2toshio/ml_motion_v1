/**
 * 解析画面のサイドバー設定と、その連動ルール。
 *
 * Streamlit 版 `app/views/analyze.py` の暗黙の連動をここに集約する:
 *   - セグ ON  → モデル一覧が SEG_MODELS に切り替わる
 *   - 追跡 OFF → ゾーン解析は disabled（ゾーンは ID 前提）
 *   - 追跡 OFF → 軌跡の長さは disabled
 *   - 全クラス ON → クラス選択は disabled（＝全 COCO 80 クラス）
 *
 * UI から切り離した純粋関数にして、vitest で固定する。
 */
import type { AnalyzeRequest, Options, ZoneInput } from '../types';

export interface AnalyzeSettings {
  enableSeg: boolean;
  enableTrack: boolean;
  enableZone: boolean;
  modelName: string;
  conf: number;
  allClasses: boolean;
  selectedClasses: string[];
  frameStride: number;
  traceLength: number;
  zoneText: string;
}

/** ゾーン定義の既定値（Streamlit 版 DEFAULT_ZONES と同じ）。 */
export const DEFAULT_ZONES_TEXT = JSON.stringify(
  [{ name: 'ゾーンA', polygon: [[0.3, 0.3], [0.7, 0.3], [0.7, 0.9], [0.3, 0.9]] }],
  null,
  2,
);

/** サイドバーの初期値（Streamlit 版のウィジェット既定値と一致させる）。 */
export function defaultSettings(options: Options | null): AnalyzeSettings {
  return {
    enableSeg: false,
    enableTrack: true,
    enableZone: false,
    // Streamlit 版は selectbox の index=1（yolo11s）が既定。
    modelName: options?.models[1] ?? 'yolo11s.pt',
    conf: 0.25,
    allClasses: false,
    selectedClasses: options ? Object.keys(options.coco_common) : [],
    frameStride: 1,
    traceLength: 30,
    zoneText: DEFAULT_ZONES_TEXT,
  };
}

/** 現在のタスクで選べるモデル一覧（セグ ON なら -seg 系）。 */
export function availableModels(settings: AnalyzeSettings, options: Options | null): string[] {
  if (!options) return [];
  return settings.enableSeg ? options.seg_models : options.models;
}

/** ゾーン解析のチェックを押せるか（トラッキング ON が前提）。 */
export function isZoneEnabled(settings: AnalyzeSettings): boolean {
  return settings.enableTrack;
}

/** 軌跡の長さスライダを押せるか。 */
export function isTraceLengthEnabled(settings: AnalyzeSettings): boolean {
  return settings.enableTrack;
}

/** クラス選択を押せるか（「全クラス」ON なら不可）。 */
export function isClassSelectEnabled(settings: AnalyzeSettings): boolean {
  return !settings.allClasses;
}

/**
 * 連動ルールを適用して設定を正規化する。
 *
 * タスク切り替えで不整合（seg なのに通常モデル、追跡 OFF なのにゾーン ON）が
 * 残らないよう、変更のたびにこれを通す。
 */
export function normalizeSettings(settings: AnalyzeSettings, options: Options | null): AnalyzeSettings {
  const models = availableModels(settings, options);
  const next: AnalyzeSettings = { ...settings };

  // セグの ON/OFF でモデル一覧が入れ替わる。対応する同グレードのモデルへ寄せる。
  if (models.length > 0 && !models.includes(next.modelName)) {
    next.modelName = correspondingModel(next.modelName, models);
  }
  // ゾーン解析はトラッキング前提。
  if (!next.enableTrack) next.enableZone = false;
  return next;
}

/**
 * モデル一覧が切り替わったとき、同じグレード（n/s/m）のモデルへ対応付ける。
 * 例: yolo11s.pt → yolo11s-seg.pt
 */
export function correspondingModel(current: string, candidates: string[]): string {
  const grade = /yolo11([nsmlx])/.exec(current)?.[1];
  const matched = grade ? candidates.find((name) => name.startsWith(`yolo11${grade}`)) : undefined;
  return matched ?? candidates[0];
}

/** ゾーン定義 JSON のパース結果。 */
export type ZoneParseResult = { ok: true; zones: ZoneInput[] } | { ok: false; error: string };

/**
 * ゾーン定義（正規化座標 0〜1 の JSON）をパースする。
 *
 * 失敗時のメッセージは Streamlit 版
 * 「ゾーン定義(JSON)の解析に失敗しました: ...」を踏襲する。
 */
export function parseZones(text: string): ZoneParseResult {
  const fail = (reason: string): ZoneParseResult => ({
    ok: false,
    error: `ゾーン定義(JSON)の解析に失敗しました: ${reason}`,
  });

  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (e) {
    return fail(e instanceof Error ? e.message : String(e));
  }
  if (!Array.isArray(data)) return fail('トップレベルは配列である必要があります');

  const zones: ZoneInput[] = [];
  for (const item of data) {
    if (typeof item !== 'object' || item === null) return fail('各要素はオブジェクトである必要があります');
    const { name, polygon } = item as { name?: unknown; polygon?: unknown };
    if (typeof name !== 'string' || name === '') return fail('name（文字列）が必要です');
    if (!Array.isArray(polygon) || polygon.length < 3) return fail(`${name}: polygon には 3 点以上必要です`);

    const points: [number, number][] = [];
    for (const point of polygon) {
      if (!Array.isArray(point) || point.length !== 2) return fail(`${name}: polygon の要素は [x, y] です`);
      const [x, y] = point as [unknown, unknown];
      if (typeof x !== 'number' || typeof y !== 'number' || Number.isNaN(x) || Number.isNaN(y)) {
        return fail(`${name}: polygon の座標は数値です`);
      }
      if (x < 0 || x > 1 || y < 0 || y > 1) {
        return fail(`${name}: polygon の座標は 0〜1 の正規化座標です（${x}, ${y}）`);
      }
      points.push([x, y]);
    }
    zones.push({ name, polygon: points });
  }
  if (zones.length === 0) return fail('ゾーンが 1 つも定義されていません');
  return { ok: true, zones };
}

/** 実行前チェック。押せない理由があれば文言を返す（null なら実行可）。 */
export function validateForRun(settings: AnalyzeSettings, uploadId: string | null): string | null {
  if (!uploadId) return '先に動画をアップロードしてください。';
  if (!settings.allClasses && settings.selectedClasses.length === 0) {
    return '対象クラスを1つ以上選ぶか「全クラス」を有効にしてください。';
  }
  if (settings.enableZone) {
    const parsed = parseZones(settings.zoneText);
    if (!parsed.ok) return parsed.error;
  }
  return null;
}

/** 設定を API のリクエストボディへ変換する。 */
export function toAnalyzeRequest(
  settings: AnalyzeSettings,
  uploadId: string,
  options: Options,
): AnalyzeRequest {
  const parsed = settings.enableZone ? parseZones(settings.zoneText) : null;
  return {
    upload_id: uploadId,
    enable_seg: settings.enableSeg,
    enable_track: settings.enableTrack,
    enable_zone: settings.enableZone,
    model_name: settings.modelName,
    conf: settings.conf,
    // null は「全クラス（COCO 80）」。
    classes: settings.allClasses
      ? null
      : settings.selectedClasses.map((name) => options.coco_common[name]).filter((id) => id !== undefined),
    frame_stride: settings.frameStride,
    trace_length: settings.traceLength,
    zones: parsed && parsed.ok ? parsed.zones : [],
  };
}
