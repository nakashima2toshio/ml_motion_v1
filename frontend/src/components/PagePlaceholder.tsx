/**
 * 未移行ページのプレースホルダ。
 *
 * R0 の時点では 5 画面すべてが未実装。移行元の Streamlit ビューと、
 * それまでの使い方（Streamlit 版を起動する）を明示して、迷わないようにする。
 */
import type { PageDef } from '../nav';

interface Props {
  page: PageDef;
  /** この画面で移植する主な機能（移行チェックリストとして表示する） */
  features: string[];
  /** 操作マニュアル（docs/manual/*.md）のファイル名 */
  manual: string;
}

export function PagePlaceholder({ page, features, manual }: Props): JSX.Element {
  return (
    <div className="page">
      <h1 className="page-title">
        {page.icon} {page.title}
      </h1>
      <p className="page-caption">
        移行元: <code>{page.streamlitView}</code> ／ フェーズ: <strong>{page.phase}</strong>
      </p>

      <div className="notice">
        <strong>この画面はまだ React 版が未実装です（{page.phase} で実装）。</strong>
        <div>
          現時点では Streamlit 版をご利用ください: <code>streamlit run app/Home.py</code>
        </div>
      </div>

      <h2 className="section-title">移植する機能</h2>
      <ul className="feature-list">
        {features.map((feature) => (
          <li key={feature}>{feature}</li>
        ))}
      </ul>

      <p className="page-footnote">
        受け入れ基準: <code>docs/manual/{manual}</code> ／ 計画: <code>docs/react_migration_todo.md</code>
      </p>
    </div>
  );
}
