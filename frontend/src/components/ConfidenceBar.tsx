interface ConfidenceBarProps {
  value: number;
}

export function ConfidenceBar({ value }: ConfidenceBarProps) {
  const pct = Math.round(value * 100);
  return (
    <div className="confidence-bar" title={`${pct}% confidence`}>
      <div className="confidence-bar__track">
        <div className="confidence-bar__fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="confidence-bar__label mono">{pct}%</span>
    </div>
  );
}
