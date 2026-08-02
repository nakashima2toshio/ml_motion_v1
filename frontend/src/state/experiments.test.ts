import { describe, expect, it } from 'vitest';

import { defaultTrainForm, parseClasses, toTrainRequest, validateTrainForm } from './experiments';

describe('defaultTrainForm', () => {
  it('Streamlit 版の既定（data.yaml パス / epochs 50 / Run 名は空）', () => {
    const form = defaultTrainForm('yolo11s.pt');
    expect(form.dataYaml).toBe('data/datasets/custom/data.yaml');
    expect(form.epochs).toBe(50);
    expect(form.runName).toBe('');
    expect(form.baseModel).toBe('yolo11s.pt');
  });
});

describe('validateTrainForm', () => {
  it('既定値は実行できる', () => {
    expect(validateTrainForm(defaultTrainForm('yolo11s.pt'))).toBeNull();
  });

  it('data.yaml が空なら実行できない', () => {
    expect(validateTrainForm({ ...defaultTrainForm('yolo11s.pt'), dataYaml: '   ' })).toContain('data.yaml');
  });

  it.each([0, -1, 1001, 1.5])('epochs=%s は弾く', (epochs) => {
    expect(validateTrainForm({ ...defaultTrainForm('yolo11s.pt'), epochs })).toContain('epochs');
  });

  it.each([1, 50, 1000])('epochs=%s は通す', (epochs) => {
    expect(validateTrainForm({ ...defaultTrainForm('yolo11s.pt'), epochs })).toBeNull();
  });
});

describe('toTrainRequest', () => {
  it('Run 名が空欄なら null で送る（自動命名に任せる）', () => {
    const body = toTrainRequest(defaultTrainForm('yolo11s.pt'), 'ml_motion_detection');
    expect(body.run_name).toBeNull();
    expect(body.experiment).toBe('ml_motion_detection');
  });

  it('前後の空白は落とす', () => {
    const form = { ...defaultTrainForm('yolo11s.pt'), dataYaml: '  a/data.yaml  ', runName: '  試行1  ' };
    const body = toTrainRequest(form, '  exp  ');
    expect(body.data_yaml).toBe('a/data.yaml');
    expect(body.run_name).toBe('試行1');
    expect(body.experiment).toBe('exp');
  });

  it('実験名が空欄なら null（サーバ側の既定を使う）', () => {
    expect(toTrainRequest(defaultTrainForm('yolo11s.pt'), '   ').experiment).toBeNull();
  });
});

describe('parseClasses', () => {
  it('カンマ区切りを配列にする', () => {
    expect(parseClasses('person,car,truck')).toEqual(['person', 'car', 'truck']);
  });

  it('空白と空要素を落とす', () => {
    expect(parseClasses(' person , , car ,')).toEqual(['person', 'car']);
  });

  it('重複は 1 つにする', () => {
    expect(parseClasses('person,car,person')).toEqual(['person', 'car']);
  });

  it('入力順を保つ（並び順がクラス ID になるため）', () => {
    expect(parseClasses('truck,person,car')).toEqual(['truck', 'person', 'car']);
  });

  it('空文字は空配列', () => {
    expect(parseClasses('  ')).toEqual([]);
  });
});
