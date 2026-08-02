/** メトリクス表示（`st.metric` の置き換え）。 */
interface Props {
  label: string;
  value: string | number;
}

export function Metric({ label, value }: Props): JSX.Element {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}
