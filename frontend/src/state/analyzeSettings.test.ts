import { describe, expect, it } from 'vitest';

import type { Options } from '../types';
import {
  availableModels,
  correspondingModel,
  DEFAULT_ZONES_TEXT,
  defaultSettings,
  isClassSelectEnabled,
  isTraceLengthEnabled,
  isZoneEnabled,
  normalizeSettings,
  parseZones,
  toAnalyzeRequest,
  validateForRun,
} from './analyzeSettings';

const OPTIONS: Options = {
  models: ['yolo11n.pt', 'yolo11s.pt', 'yolo11m.pt'],
  seg_models: ['yolo11n-seg.pt', 'yolo11s-seg.pt', 'yolo11m-seg.pt'],
  lightweight_models: ['yolo11n.pt', 'yolo11s.pt'],
  coco_common: { person: 0, bicycle: 1, car: 2, motorcycle: 3, bus: 5, truck: 7 },
  resolution_presets: { '640x360': [640, 360] },
  export_formats: ['onnx'],
  registry_stages: ['None', 'Staging'],
  default_experiment: 'ml_motion_detection',
  detection_fields: ['frame', 'time_sec'],
};

describe('既定値', () => {
  it('Streamlit 版の既定（yolo11s / conf 0.25 / 追跡 ON / セグ・ゾーン OFF / 代表クラス全選択）', () => {
    const s = defaultSettings(OPTIONS);
    expect(s.modelName).toBe('yolo11s.pt');
    expect(s.conf).toBe(0.25);
    expect(s.enableTrack).toBe(true);
    expect(s.enableSeg).toBe(false);
    expect(s.enableZone).toBe(false);
    expect(s.allClasses).toBe(false);
    expect(s.selectedClasses).toEqual(['person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck']);
    expect(s.frameStride).toBe(1);
    expect(s.traceLength).toBe(30);
    expect(s.zoneText).toBe(DEFAULT_ZONES_TEXT);
  });
});

describe('設定の連動', () => {
  it('セグ ON でモデル一覧が -seg 系に切り替わる', () => {
    const s = { ...defaultSettings(OPTIONS), enableSeg: true };
    expect(availableModels(s, OPTIONS)).toEqual(OPTIONS.seg_models);
  });

  it('セグ ON で同グレードの -seg モデルへ寄せる（yolo11s → yolo11s-seg）', () => {
    const s = normalizeSettings({ ...defaultSettings(OPTIONS), enableSeg: true }, OPTIONS);
    expect(s.modelName).toBe('yolo11s-seg.pt');
  });

  it('セグ OFF に戻すと通常モデルへ戻る', () => {
    const seg = normalizeSettings({ ...defaultSettings(OPTIONS), enableSeg: true }, OPTIONS);
    const back = normalizeSettings({ ...seg, enableSeg: false }, OPTIONS);
    expect(back.modelName).toBe('yolo11s.pt');
  });

  it('追跡 OFF でゾーン解析は選べない（ゾーンは ID 前提）', () => {
    const s = { ...defaultSettings(OPTIONS), enableTrack: false };
    expect(isZoneEnabled(s)).toBe(false);
  });

  it('追跡を OFF にするとゾーン解析も強制的に OFF になる', () => {
    const s = normalizeSettings({ ...defaultSettings(OPTIONS), enableZone: true, enableTrack: false }, OPTIONS);
    expect(s.enableZone).toBe(false);
  });

  it('追跡 OFF で軌跡の長さも無効', () => {
    expect(isTraceLengthEnabled({ ...defaultSettings(OPTIONS), enableTrack: false })).toBe(false);
  });

  it('全クラス ON でクラス選択は無効', () => {
    expect(isClassSelectEnabled({ ...defaultSettings(OPTIONS), allClasses: true })).toBe(false);
  });

  it('correspondingModel は同グレードが無ければ先頭に落ちる', () => {
    expect(correspondingModel('yolo11x.pt', OPTIONS.seg_models)).toBe('yolo11n-seg.pt');
  });
});

describe('parseZones', () => {
  it('既定のゾーン定義を読める', () => {
    const parsed = parseZones(DEFAULT_ZONES_TEXT);
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.zones).toHaveLength(1);
      expect(parsed.zones[0].name).toBe('ゾーンA');
      expect(parsed.zones[0].polygon).toHaveLength(4);
    }
  });

  it('JSON として壊れていれば Streamlit と同じ文言で失敗する', () => {
    const parsed = parseZones('{壊れた');
    expect(parsed.ok).toBe(false);
    if (!parsed.ok) expect(parsed.error).toContain('ゾーン定義(JSON)の解析に失敗しました');
  });

  it('配列でなければ失敗する', () => {
    expect(parseZones('{"name":"z"}').ok).toBe(false);
  });

  it('polygon が 3 点未満なら失敗する', () => {
    expect(parseZones('[{"name":"z","polygon":[[0,0],[1,1]]}]').ok).toBe(false);
  });

  it('0〜1 の範囲外の座標は失敗する（ピクセル座標の誤入力を弾く）', () => {
    const parsed = parseZones('[{"name":"z","polygon":[[0,0],[640,0],[640,480]]}]');
    expect(parsed.ok).toBe(false);
    if (!parsed.ok) expect(parsed.error).toContain('0〜1');
  });

  it('name が無ければ失敗する', () => {
    expect(parseZones('[{"polygon":[[0,0],[1,0],[1,1]]}]').ok).toBe(false);
  });

  it('空配列は失敗する', () => {
    expect(parseZones('[]').ok).toBe(false);
  });
});

describe('validateForRun', () => {
  it('未アップロードなら実行できない', () => {
    expect(validateForRun(defaultSettings(OPTIONS), null)).toBe('先に動画をアップロードしてください。');
  });

  it('クラス未選択かつ全クラス OFF なら Streamlit と同じ警告', () => {
    const s = { ...defaultSettings(OPTIONS), selectedClasses: [] };
    expect(validateForRun(s, 'u1')).toBe('対象クラスを1つ以上選ぶか「全クラス」を有効にしてください。');
  });

  it('全クラス ON ならクラス未選択でも実行できる', () => {
    const s = { ...defaultSettings(OPTIONS), selectedClasses: [], allClasses: true };
    expect(validateForRun(s, 'u1')).toBeNull();
  });

  it('ゾーン ON で JSON が壊れていれば実行できない', () => {
    const s = { ...defaultSettings(OPTIONS), enableZone: true, zoneText: '[[[' };
    expect(validateForRun(s, 'u1')).toContain('ゾーン定義(JSON)の解析に失敗しました');
  });

  it('ゾーン OFF なら JSON が壊れていても実行できる（使わないため）', () => {
    const s = { ...defaultSettings(OPTIONS), enableZone: false, zoneText: '[[[' };
    expect(validateForRun(s, 'u1')).toBeNull();
  });
});

describe('toAnalyzeRequest', () => {
  it('クラス名を COCO の ID に変換する', () => {
    const s = { ...defaultSettings(OPTIONS), selectedClasses: ['person', 'car'] };
    expect(toAnalyzeRequest(s, 'u1', OPTIONS).classes).toEqual([0, 2]);
  });

  it('全クラス ON では classes を null（＝COCO 80 全部）にする', () => {
    const s = { ...defaultSettings(OPTIONS), allClasses: true };
    expect(toAnalyzeRequest(s, 'u1', OPTIONS).classes).toBeNull();
  });

  it('ゾーン OFF では zones を空で送る（定義が残っていても使わない）', () => {
    const s = { ...defaultSettings(OPTIONS), enableZone: false };
    expect(toAnalyzeRequest(s, 'u1', OPTIONS).zones).toEqual([]);
  });

  it('ゾーン ON では解析済みのゾーンを送る', () => {
    const s = { ...defaultSettings(OPTIONS), enableZone: true };
    expect(toAnalyzeRequest(s, 'u1', OPTIONS).zones).toHaveLength(1);
  });
});
