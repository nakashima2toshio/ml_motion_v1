/**
 * ジョブ（SSE）の状態遷移。
 *
 * Streamlit 版の `st.progress` + `st.error` に相当する部分を、
 * イベント列 → 表示状態の純粋な reducer として切り出す。
 */
import type { JobEvent, JobProgress } from '../types';

export interface JobState {
  status: 'idle' | 'running' | 'completed' | 'failed';
  jobId: string | null;
  /** 0〜1。総フレーム数が不明な間は null */
  progress: number | null;
  /** 進捗の内訳（"解析中… 120/300 フレーム" 用） */
  frames: JobProgress | null;
  message: string;
  error: string | null;
}

export const initialJobState: JobState = {
  status: 'idle',
  jobId: null,
  progress: null,
  frames: null,
  message: '',
  error: null,
};

export type JobAction =
  | { type: 'start'; jobId: string }
  | { type: 'event'; event: JobEvent }
  | { type: 'fail'; message: string }
  | { type: 'reset' };

export function jobReducer(state: JobState, action: JobAction): JobState {
  switch (action.type) {
    case 'start':
      return { ...initialJobState, status: 'running', jobId: action.jobId, message: '解析中…' };

    case 'fail':
      return { ...state, status: 'failed', error: action.message };

    case 'reset':
      return initialJobState;

    case 'event':
      return applyEvent(state, action.event);
  }
}

function applyEvent(state: JobState, event: JobEvent): JobState {
  switch (event.type) {
    case 'started':
      return { ...state, status: 'running', message: event.message || '解析中…' };

    case 'progress': {
      const frames = toProgress(event.data);
      return {
        ...state,
        status: 'running',
        frames,
        progress: frames && frames.total > 0 ? Math.min(1, frames.current / frames.total) : state.progress,
        message: event.message || state.message,
      };
    }

    case 'done':
      // 完了時は進捗を 100% に振り切る（最終フレームが端数で終わることがある）。
      return { ...state, status: 'completed', progress: 1, message: '完了' };

    case 'error':
      return { ...state, status: 'failed', error: event.message || '解析に失敗しました' };

    default:
      return state;
  }
}

function toProgress(data: Record<string, unknown>): JobProgress | null {
  const current = data.current;
  const total = data.total;
  if (typeof current !== 'number' || typeof total !== 'number') return null;
  return { current, total };
}

/** 進捗バーのラベル（Streamlit 版「解析中… n/total フレーム」と同じ）。 */
export function progressLabel(state: JobState): string {
  if (state.frames && state.frames.total > 0) {
    return `解析中… ${state.frames.current}/${state.frames.total} フレーム`;
  }
  return state.message || '解析中…';
}
