/**
 * ページ定義 — Streamlit 版 `app/Home.py` の `st.Page` / `st.navigation` 相当。
 *
 * タイトル・アイコン・並び順・既定ページを Home.py と一致させる。
 * ここが唯一のナビ定義で、`App.tsx` はこの配列からルートとリンクを生成する。
 */
export interface PageDef {
  /** ルーティングのパス（`/` は既定ページ） */
  path: string;
  /** ナビに出す日本語名（Home.py の title） */
  title: string;
  /** ナビのアイコン（Home.py の icon） */
  icon: string;
  /** 移行元の Streamlit ビュー。移行状況の追跡用 */
  streamlitView: string;
  /** 移行計画（docs/react_migration_todo.md）のフェーズ */
  phase: 'R1' | 'R2' | 'R3' | 'R4' | 'R5';
  /** 実装済みか。false の間はプレースホルダを出す */
  implemented: boolean;
}

export const PAGES: PageDef[] = [
  {
    path: '/analyze',
    title: '解析',
    icon: '🎥',
    streamlitView: 'app/views/analyze.py',
    phase: 'R1',
    implemented: true,
  },
  {
    path: '/realtime',
    title: 'リアルタイム',
    icon: '📡',
    streamlitView: 'app/views/realtime.py',
    phase: 'R5',
    implemented: false,
  },
  {
    path: '/experiments',
    title: '実験管理',
    icon: '📊',
    streamlitView: 'app/views/experiments.py',
    phase: 'R3',
    implemented: true,
  },
  {
    path: '/production',
    title: '本番/最適化',
    icon: '⚙️',
    streamlitView: 'app/views/production.py',
    phase: 'R4',
    implemented: false,
  },
  {
    path: '/annotation-qa',
    title: 'アノテーションQA',
    icon: '🏷',
    streamlitView: 'app/views/annotation_qa.py',
    phase: 'R2',
    implemented: true,
  },
];

/** 既定ページ（Home.py の `default=True` に対応）。 */
export const DEFAULT_PAGE: PageDef = PAGES[0];

/** パスからページ定義を引く。 */
export function findPage(path: string): PageDef | undefined {
  return PAGES.find((page) => page.path === path);
}
