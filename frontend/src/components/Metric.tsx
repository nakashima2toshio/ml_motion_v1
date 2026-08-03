/** メトリクス表示（`st.metric` の置き換え）。 */
import type { ReactElement } from 'react';

interface Props {
  label: string;
  value: string | number;
}

export function Metric({ label, value }: Props): ReactElement {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}
