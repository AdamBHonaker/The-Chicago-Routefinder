export default function SignalLamp({ label, ariaLabel, className = "" }) {
  const cls = `signal-lamp-row${className ? ` ${className}` : ""}`;
  return (
    <span className={cls}>
      <span
        className="signal-lamp"
        aria-label={ariaLabel}
        role={ariaLabel ? "img" : undefined}
      />
      {label && <span className="signal-lamp__label">{label}</span>}
    </span>
  );
}
