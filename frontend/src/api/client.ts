/**
 * バックエンド（FastAPI）呼び出しの薄いラッパ。
 *
 * dev は Vite のプロキシで同一オリジンに見えるため、既定のベース URL は空文字。
 * 別ポート/別ホストの API を叩くときだけ `VITE_API_BASE` を設定する。
 */
import type { AnnotationReview, DeviceInfo, Health, JobEvent, JobStatus, Options, UploadInfo } from '../types';

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '';

/** API 呼び出しの失敗。UI はこの message をそのまま出してよい。 */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * FastAPI のエラーレスポンスから表示用メッセージを取り出す。
 * `{"detail": "..."}` と `{"detail": [{"msg": ...}]}`（422）の両方に対応する。
 */
export function extractErrorMessage(body: unknown, fallback: string): string {
  if (typeof body === 'string' && body.trim() !== '') return body;
  if (typeof body !== 'object' || body === null) return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim() !== '') return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === 'object' && item !== null ? (item as { msg?: unknown }).msg : undefined))
      .filter((msg): msg is string => typeof msg === 'string');
    if (messages.length > 0) return messages.join(' / ');
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    // バックエンド未起動が最も多い。原因が分かる文言にする。
    throw new ApiError('バックエンドに接続できません（uvicorn backend.app.main:app --port 8000 を確認）', 0);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(extractErrorMessage(body, `${response.status} ${response.statusText}`), response.status);
  }
  return body as T;
}

/** JSON ボディで POST する。 */
export function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/** 動画をアップロードする（multipart/form-data）。 */
export function uploadVideo(file: File): Promise<UploadInfo> {
  const form = new FormData();
  form.append('file', file);
  // Content-Type は boundary 付きでブラウザに決めさせる（自分で指定しない）。
  return request<UploadInfo>('/api/analyze/upload', { method: 'POST', body: form });
}

/** アノテーション QA: 画像＋提案ラベルを Claude Vision でレビューする。 */
export function reviewAnnotation(file: File, labels: string): Promise<AnnotationReview> {
  const form = new FormData();
  form.append('file', file);
  form.append('labels', labels);
  return request<AnnotationReview>('/api/annotation/review', { method: 'POST', body: form });
}

export const getHealth = (): Promise<Health> => request<Health>('/api/health');
export const getDeviceInfo = (): Promise<DeviceInfo> => request<DeviceInfo>('/api/meta/device');
export const getOptions = (): Promise<Options> => request<Options>('/api/meta/options');
export const getJobStatus = <T>(kind: string, jobId: string): Promise<JobStatus<T>> =>
  request<JobStatus<T>>(`/api/${kind}/result/${jobId}`);

/** GET で任意のパスを叩く（画面固有のエンドポイント用）。 */
export const getJson = <T>(path: string): Promise<T> => request<T>(path);

/** SSE 購読の解除関数。 */
export type Unsubscribe = () => void;

/**
 * ジョブの進捗（SSE）を購読する。
 *
 * サーバは `event:` に種別を入れて配信するため、既定の `message` ハンドラでは
 * 受け取れない。種別ごとに addEventListener する。
 */
export function subscribeJob(
  kind: string,
  jobId: string,
  onEvent: (event: JobEvent) => void,
  onError?: (message: string) => void,
): Unsubscribe {
  const source = new EventSource(`${API_BASE}/api/${kind}/stream/${jobId}`);
  const types: JobEvent['type'][] = ['started', 'progress', 'done', 'error'];

  const handle = (raw: MessageEvent<string>) => {
    try {
      onEvent(JSON.parse(raw.data) as JobEvent);
    } catch {
      onError?.('進捗イベントの解析に失敗しました');
    }
  };

  types.forEach((type) => source.addEventListener(type, handle as EventListener));
  source.onerror = () => {
    // done/error 配信後はサーバが接続を閉じる。完了後の再接続は抑止する。
    if (source.readyState === EventSource.CLOSED) return;
    onError?.('進捗の受信が切断されました');
  };

  return () => {
    types.forEach((type) => source.removeEventListener(type, handle as EventListener));
    source.close();
  };
}
