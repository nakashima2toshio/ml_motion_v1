/**
 * 表コンポーネント（`st.dataframe` の置き換え）。
 *
 * 検出結果テーブルは数万行になりうるため、大きいデータは呼び出し側でページング
 * して渡す（全件は CSV/JSON ダウンロードへ誘導する方針）。
 */
import type { ReactElement, ReactNode } from 'react';

export interface Column<T> {
  key: string;
  label: string;
  /** 省略時は `row[key]` をそのまま表示 */
  render?: (row: T) => ReactNode;
  align?: 'left' | 'right';
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  /** 行が 0 件のときの文言 */
  empty?: string;
}

export function DataTable<T extends object>({
  columns,
  rows,
  empty = 'データがありません',
}: Props<T>): ReactElement {
  if (rows.length === 0) {
    return <p className="table-empty">{empty}</p>;
  }
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={column.align === 'right' ? 'align-right' : undefined}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column.key} className={column.align === 'right' ? 'align-right' : undefined}>
                  {column.render ? column.render(row) : formatCell((row as Record<string, unknown>)[column.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3);
  return String(value);
}
