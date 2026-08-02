import { describe, expect, it } from 'vitest';

import type { JobEvent } from '../types';
import { initialJobState, jobReducer, progressLabel } from './jobReducer';

const event = (type: JobEvent['type'], data: Record<string, unknown> = {}, message = ''): JobEvent => ({
  seq: 0,
  ts: 0,
  type,
  message,
  data,
});

describe('jobReducer', () => {
  it('start で running になり job_id を持つ', () => {
    const state = jobReducer(initialJobState, { type: 'start', jobId: 'abc' });
    expect(state.status).toBe('running');
    expect(state.jobId).toBe('abc');
    expect(state.error).toBeNull();
  });

  it('progress で 0〜1 の進捗を持つ', () => {
    let state = jobReducer(initialJobState, { type: 'start', jobId: 'abc' });
    state = jobReducer(state, { type: 'event', event: event('progress', { current: 30, total: 120 }) });
    expect(state.progress).toBeCloseTo(0.25);
    expect(state.frames).toEqual({ current: 30, total: 120 });
  });

  it('進捗が総数を超えても 1 を上回らない', () => {
    let state = jobReducer(initialJobState, { type: 'start', jobId: 'abc' });
    state = jobReducer(state, { type: 'event', event: event('progress', { current: 130, total: 120 }) });
    expect(state.progress).toBe(1);
  });

  it('total=0（フレーム数不明）では前の進捗を保つ', () => {
    let state = jobReducer(initialJobState, { type: 'start', jobId: 'abc' });
    state = jobReducer(state, { type: 'event', event: event('progress', { current: 1, total: 0 }) });
    expect(state.progress).toBeNull();
  });

  it('フレーム数を伴わない progress はメッセージだけを更新する（モデル読み込み中）', () => {
    let state = jobReducer(initialJobState, { type: 'start', jobId: 'abc' });
    state = jobReducer(state, { type: 'event', event: event('progress', {}, 'モデルを読み込み中…') });
    expect(state.frames).toBeNull();
    expect(state.progress).toBeNull();
    expect(progressLabel(state)).toBe('モデルを読み込み中…');
  });

  it('done で completed かつ 100%', () => {
    let state = jobReducer(initialJobState, { type: 'start', jobId: 'abc' });
    state = jobReducer(state, { type: 'event', event: event('progress', { current: 118, total: 120 }) });
    state = jobReducer(state, { type: 'event', event: event('done') });
    expect(state.status).toBe('completed');
    expect(state.progress).toBe(1);
  });

  it('error で failed になりメッセージを保持する', () => {
    let state = jobReducer(initialJobState, { type: 'start', jobId: 'abc' });
    state = jobReducer(state, {
      type: 'event',
      event: event('error', {}, 'RuntimeError: 動画処理に失敗しました'),
    });
    expect(state.status).toBe('failed');
    expect(state.error).toContain('動画処理に失敗しました');
  });

  it('メッセージ無しの error でも既定文言を出す', () => {
    const state = jobReducer(initialJobState, { type: 'event', event: event('error') });
    expect(state.error).toBe('解析に失敗しました');
  });

  it('fail アクション（接続断など）で failed になる', () => {
    let state = jobReducer(initialJobState, { type: 'start', jobId: 'abc' });
    state = jobReducer(state, { type: 'fail', message: '進捗の受信が切断されました' });
    expect(state.status).toBe('failed');
    expect(state.error).toBe('進捗の受信が切断されました');
  });

  it('reset で初期状態に戻る', () => {
    let state = jobReducer(initialJobState, { type: 'start', jobId: 'abc' });
    state = jobReducer(state, { type: 'reset' });
    expect(state).toEqual(initialJobState);
  });

  it('再実行（start）で前回のエラーが残らない', () => {
    let state = jobReducer(initialJobState, { type: 'event', event: event('error', {}, '失敗') });
    state = jobReducer(state, { type: 'start', jobId: 'def' });
    expect(state.error).toBeNull();
    expect(state.status).toBe('running');
  });
});

describe('progressLabel', () => {
  it('Streamlit と同じ「解析中… n/total フレーム」', () => {
    const state = { ...initialJobState, frames: { current: 30, total: 120 } };
    expect(progressLabel(state)).toBe('解析中… 30/120 フレーム');
  });

  it('バッチ画面は単位を「ファイル」に差し替えられる', () => {
    const state = { ...initialJobState, frames: { current: 1, total: 2 } };
    expect(progressLabel(state, '処理中…', 'ファイル')).toBe('処理中… 1/2 ファイル');
  });

  it('フレーム数が無ければメッセージを出す', () => {
    const state = { ...initialJobState, message: 'モデルを読み込み中…' };
    expect(progressLabel(state)).toBe('モデルを読み込み中…');
  });
});

describe('start の初期メッセージ', () => {
  it('画面ごとの文言を渡せる（バッチ画面に解析用の文言が漏れない）', () => {
    const state = jobReducer(initialJobState, { type: 'start', jobId: 'x', message: '処理中…' });
    expect(state.message).toBe('処理中…');
    expect(progressLabel(state, '処理中…', 'ファイル')).toBe('処理中…');
  });

  it('省略時は中立な既定文言', () => {
    expect(jobReducer(initialJobState, { type: 'start', jobId: 'x' }).message).toBe('実行中…');
  });

  it('started イベントにメッセージが無ければ開始時の文言を保つ', () => {
    let state = jobReducer(initialJobState, { type: 'start', jobId: 'x', message: '処理中…' });
    state = jobReducer(state, {
      type: 'event',
      event: { seq: 0, ts: 0, type: 'started', message: '', data: {} },
    });
    expect(state.message).toBe('処理中…');
  });
});
