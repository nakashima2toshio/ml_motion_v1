/**
 * アプリのシェル — Streamlit 版 `app/Home.py` に対応する。
 *
 * Home.py がやっていたこと:
 *   - st.set_page_config(page_title, page_icon, layout="wide")  → index.html / styles.css
 *   - st.Page(...) × 5 / st.navigation([...]).run()             → nav.ts + ここのルーティング
 *
 * 各画面の中身は R1 以降で実装する（現状はプレースホルダ）。
 */
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';

import { DeviceBar } from './components/DeviceBar';
import { DEFAULT_PAGE, PAGES } from './nav';
import { AnalyzePage } from './pages/AnalyzePage';
import { AnnotationQaPage } from './pages/AnnotationQaPage';
import { ExperimentsPage } from './pages/ExperimentsPage';
import { ProductionPage } from './pages/ProductionPage';
import { RealtimePage } from './pages/RealtimePage';

const PAGE_COMPONENTS: Record<string, () => JSX.Element> = {
  '/analyze': AnalyzePage,
  '/realtime': RealtimePage,
  '/experiments': ExperimentsPage,
  '/production': ProductionPage,
  '/annotation-qa': AnnotationQaPage,
};

export function App(): JSX.Element {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">🎥</span>
          <span className="brand-name">Video ML Analytics Studio</span>
        </div>
        <nav className="nav">
          {PAGES.map((page) => (
            <NavLink
              key={page.path}
              to={page.path}
              className={({ isActive }) => (isActive ? 'nav-item nav-item-active' : 'nav-item')}
            >
              <span className="nav-icon">{page.icon}</span>
              <span>{page.title}</span>
            </NavLink>
          ))}
        </nav>
        <DeviceBar />
      </aside>

      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to={DEFAULT_PAGE.path} replace />} />
          {PAGES.map((page) => {
            const Component = PAGE_COMPONENTS[page.path];
            return <Route key={page.path} path={page.path} element={<Component />} />;
          })}
          <Route path="*" element={<Navigate to={DEFAULT_PAGE.path} replace />} />
        </Routes>
      </main>
    </div>
  );
}
