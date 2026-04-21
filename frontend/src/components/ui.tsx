import type { ReactNode } from 'react';

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ');
}

export function PageShell({ children }: { children: ReactNode }) {
  return <div className="page-shell">{children}</div>;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        {eyebrow ? <p className="page-eyebrow">{eyebrow}</p> : null}
        <h1 className="page-title">{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </div>
  );
}

export function SurfaceCard({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={cx('surface-card', className)}>{children}</section>;
}

export function SectionHeading({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        <h2 className="section-title">{title}</h2>
        {description ? <p className="section-description">{description}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function MetricTile({
  label,
  value,
  meta,
  accent = 'var(--accent)',
}: {
  label: string;
  value: ReactNode;
  meta?: ReactNode;
  accent?: string;
}) {
  return (
    <div className="metric-tile">
      <span className="metric-label">{label}</span>
      <strong className="metric-value" style={{ color: accent }}>
        {value}
      </strong>
      {meta ? <span className="metric-meta">{meta}</span> : null}
    </div>
  );
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'accent';
}) {
  return <span className={cx('ui-badge', `ui-badge--${tone}`)}>{children}</span>;
}

export function ActionButton({
  children,
  variant = 'primary',
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost';
}) {
  return (
    <button className={cx('ui-button', `ui-button--${variant}`, className)} {...props}>
      {children}
    </button>
  );
}
