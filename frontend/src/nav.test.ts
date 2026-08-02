import { describe, expect, it } from 'vitest';

import { DEFAULT_PAGE, findPage, PAGES } from './nav';

/**
 * ナビは `app/Home.py` の `st.navigation([...])` と等価でなければならない。
 * Streamlit 版と React 版を併存させる間、ここがズレると「画面が消えた」ように見える。
 */
const HOME_PY_NAVIGATION = [
  { title: '解析', icon: '🎥', view: 'app/views/analyze.py' },
  { title: 'リアルタイム', icon: '📡', view: 'app/views/realtime.py' },
  { title: '実験管理', icon: '📊', view: 'app/views/experiments.py' },
  { title: '本番/最適化', icon: '⚙️', view: 'app/views/production.py' },
  { title: 'アノテーションQA', icon: '🏷', view: 'app/views/annotation_qa.py' },
];

describe('nav', () => {
  it('Home.py と同じ順序・タイトル・アイコンでページを並べる', () => {
    expect(PAGES.map((p) => ({ title: p.title, icon: p.icon, view: p.streamlitView }))).toEqual(HOME_PY_NAVIGATION);
  });

  it('既定ページは解析（Home.py の default=True）', () => {
    expect(DEFAULT_PAGE.title).toBe('解析');
    expect(DEFAULT_PAGE.path).toBe('/analyze');
  });

  it('パスは一意で、先頭スラッシュ始まり', () => {
    const paths = PAGES.map((p) => p.path);
    expect(new Set(paths).size).toBe(paths.length);
    paths.forEach((path) => expect(path.startsWith('/')).toBe(true));
  });

  it('findPage は既知のパスを引ける', () => {
    expect(findPage('/annotation-qa')?.title).toBe('アノテーションQA');
  });

  it('findPage は未知のパスで undefined を返す', () => {
    expect(findPage('/nope')).toBeUndefined();
  });

  it('全ページが移行フェーズを持つ', () => {
    PAGES.forEach((page) => expect(page.phase).toMatch(/^R[1-5]$/));
  });
});
