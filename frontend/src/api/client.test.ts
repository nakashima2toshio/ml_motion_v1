import { describe, expect, it } from 'vitest';

import { extractErrorMessage } from './client';

describe('extractErrorMessage', () => {
  it('FastAPI の {"detail": "..."} を取り出す', () => {
    expect(extractErrorMessage({ detail: 'モデルの読み込みに失敗しました' }, 'fallback')).toBe(
      'モデルの読み込みに失敗しました',
    );
  });

  it('422 の detail 配列は msg を連結する', () => {
    const body = { detail: [{ msg: 'field required' }, { msg: 'value is not a valid float' }] };
    expect(extractErrorMessage(body, 'fallback')).toBe('field required / value is not a valid float');
  });

  it('detail が無ければ fallback を返す', () => {
    expect(extractErrorMessage({ foo: 'bar' }, '500 Internal Server Error')).toBe('500 Internal Server Error');
  });

  it('本文が null（JSON でない）でも fallback を返す', () => {
    expect(extractErrorMessage(null, '502 Bad Gateway')).toBe('502 Bad Gateway');
  });

  it('空文字の detail は fallback に落とす', () => {
    expect(extractErrorMessage({ detail: '   ' }, 'fallback')).toBe('fallback');
  });

  it('msg を持たない detail 配列は fallback に落とす', () => {
    expect(extractErrorMessage({ detail: [{ loc: ['body'] }] }, 'fallback')).toBe('fallback');
  });
});
