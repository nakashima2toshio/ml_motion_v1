/** リアルタイム画面のエンドポイント。 */
import type { RealtimeSettingsResponse, RealtimeStats } from '../types';
import { API_BASE, getJson, postJson } from './client';

/** 設定（軽量モデル自動切替など）を解決する。 */
export const getRealtimeSettings = (query: string): Promise<RealtimeSettingsResponse> =>
  getJson<RealtimeSettingsResponse>(`/api/realtime/settings?${query}`);

/** 配信中の FPS / 検出数。 */
export const getRealtimeStats = (): Promise<RealtimeStats> =>
  getJson<RealtimeStats>('/api/realtime/stats');

/** 配信を停止してカメラを解放する。 */
export const stopRealtime = (): Promise<{ stopped: boolean }> =>
  postJson<{ stopped: boolean }>('/api/realtime/stop', {});

/** 経路1: MJPEG の URL（`<img src>` に渡す）。 */
export const mjpegUrl = (query: string): string => `${API_BASE}/api/realtime/mjpeg?${query}`;

/** 経路2: WebSocket の URL。 */
export function websocketUrl(query: string): string {
  if (API_BASE) {
    return `${API_BASE.replace(/^http/, 'ws')}/api/realtime/ws?${query}`;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/api/realtime/ws?${query}`;
}
