import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  compact?: boolean;
}

export function Button({
  variant = 'secondary',
  compact = false,
  className = '',
  ...props
}: ButtonProps) {
  const classes = ['nd-button', `nd-button--${variant}`, compact && 'nd-button--compact', className]
    .filter(Boolean)
    .join(' ');
  return <button className={classes} {...props} />;
}

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'flat' | 'bordered';
}

export function Card({ variant = 'bordered', className = '', ...props }: CardProps) {
  return <div className={`nd-card nd-card--${variant} ${className}`.trim()} {...props} />;
}

interface ModalProps {
  open: boolean;
  title: string;
  children?: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
}

export function Modal({ open, title, children, footer, onClose }: ModalProps) {
  if (!open) return null;
  return (
    <div className="nd-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="nd-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="nd-modal-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2 id="nd-modal-title">{title}</h2>
        <div className="nd-modal-body">{children}</div>
        <div className="nd-modal-footer">{footer}</div>
      </section>
    </div>
  );
}
