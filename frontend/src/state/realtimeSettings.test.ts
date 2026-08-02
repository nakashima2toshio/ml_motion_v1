import { describe, expect, it } from 'vitest';

import type { Options } from '../types';
import {
  defaultRealtimeSettings,
  normalizeRealtimeSettings,
  realtimeModels,
  toRealtimeQuery,
} from './realtimeSettings';

const OPTIONS: Options = {
  models: ['yolo11n.pt', 'yolo11s.pt', 'yolo11m.pt'],
  seg_models: ['yolo11n-seg.pt', 'yolo11s-seg.pt', 'yolo11m-seg.pt'],
  lightweight_models: ['yolo11n.pt', 'yolo11s.pt'],
  coco_common: { person: 0 },
  resolution_presets: { '640x360': [640, 360], '960x540': [960, 540], '1280x720': [1280, 720] },
  export_formats: ['onnx'],
  registry_stages: ['None', 'Staging'],
  default_experiment: 'ml_motion_detection',
  detection_fields: ['frame'],
  claude_model: 'claude-opus-4-8',
};

describe('defaultRealtimeSettings', () => {
  it('Streamlit 版の既定（Continuity 経路 / yolo11n / 自動切替 ON / 追跡 ON）', () => {
    const s = defaultRealtimeSettings(OPTIONS);
    expect(s.route).toBe('camera');
    expect(s.modelName).toBe('yolo11n.pt');
    expect(s.autoLight).toBe(true);
    expect(s.enableTrack).toBe(true);
    expect(s.enableSeg).toBe(false);
    expect(s.conf).toBe(0.25);
    expect(s.resolution).toBe('640x360');
    expect(s.frameSkip).toBe(1);
    expect(s.cameraIndex).toBe(0);
  });
});

describe('モデル一覧の切り替え', () => {
  it('セグ ON で -seg 系になる', () => {
    const s = { ...defaultRealtimeSettings(OPTIONS), enableSeg: true };
    expect(realtimeModels(s, OPTIONS)).toEqual(OPTIONS.seg_models);
  });

  it('セグ ON で同グレードの -seg モデルへ寄せる', () => {
    const s = normalizeRealtimeSettings(
      { ...defaultRealtimeSettings(OPTIONS), modelName: 'yolo11s.pt', enableSeg: true },
      OPTIONS,
    );
    expect(s.modelName).toBe('yolo11s-seg.pt');
  });

  it('セグ OFF に戻すと通常モデルへ戻る', () => {
    const seg = normalizeRealtimeSettings(
      { ...defaultRealtimeSettings(OPTIONS), enableSeg: true },
      OPTIONS,
    );
    const back = normalizeRealtimeSettings({ ...seg, enableSeg: false }, OPTIONS);
    expect(back.modelName).toBe('yolo11n.pt');
  });

  it('一覧に含まれていれば変更しない', () => {
    const s = { ...defaultRealtimeSettings(OPTIONS), modelName: 'yolo11m.pt' };
    expect(normalizeRealtimeSettings(s, OPTIONS).modelName).toBe('yolo11m.pt');
  });

  it('options 未取得なら何もしない', () => {
    const s = defaultRealtimeSettings(null);
    expect(normalizeRealtimeSettings(s, null)).toBe(s);
  });
});

describe('toRealtimeQuery', () => {
  it('サーバが読むパラメータを全て含む', () => {
    const query = new URLSearchParams(toRealtimeQuery(defaultRealtimeSettings(OPTIONS)));
    expect(query.get('camera_index')).toBe('0');
    expect(query.get('model_name')).toBe('yolo11n.pt');
    expect(query.get('enable_seg')).toBe('false');
    expect(query.get('enable_track')).toBe('true');
    expect(query.get('auto_light')).toBe('true');
    expect(query.get('conf')).toBe('0.25');
    expect(query.get('resolution')).toBe('640x360');
    expect(query.get('frame_skip')).toBe('1');
  });

  it('真偽値は小文字（サーバ側が "true"/"false" で判定するため）', () => {
    const s = { ...defaultRealtimeSettings(OPTIONS), enableSeg: true, autoLight: false };
    const query = new URLSearchParams(toRealtimeQuery(s));
    expect(query.get('enable_seg')).toBe('true');
    expect(query.get('auto_light')).toBe('false');
  });

  it('解像度のキーはそのまま渡す（サーバのプリセット名と一致させる）', () => {
    const s = { ...defaultRealtimeSettings(OPTIONS), resolution: '1280x720' };
    expect(new URLSearchParams(toRealtimeQuery(s)).get('resolution')).toBe('1280x720');
  });
});
