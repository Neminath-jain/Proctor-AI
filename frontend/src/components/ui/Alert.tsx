import React from 'react';
import { Icon } from './Icon';

export interface AlertProps {
  variant?: 'warning' | 'error' | 'success' | 'info';
  title?: string;
  icon?: string;
  onClose?: () => void;
  className?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}

const variantStyles = {
  warning: {
    container: 'bg-amber-50 border-amber-300 text-amber-950',
    iconColor: 'text-amber-800',
    defaultIcon: 'warning',
    closeButton: 'text-amber-900 hover:text-amber-950 hover:bg-amber-100/60',
  },
  error: {
    container: 'bg-rose-50 border-rose-300 text-rose-950',
    iconColor: 'text-rose-800',
    defaultIcon: 'error',
    closeButton: 'text-rose-900 hover:text-rose-950 hover:bg-rose-100/60',
  },
  success: {
    container: 'bg-emerald-50 border-emerald-300 text-emerald-950',
    iconColor: 'text-emerald-800',
    defaultIcon: 'check_circle',
    closeButton: 'text-emerald-900 hover:text-emerald-950 hover:bg-emerald-100/60',
  },
  info: {
    container: 'bg-zinc-100 border-zinc-300 text-zinc-900',
    iconColor: 'text-zinc-700',
    defaultIcon: 'info',
    closeButton: 'text-zinc-700 hover:text-zinc-900 hover:bg-zinc-200/60',
  },
};

export const Alert: React.FC<AlertProps> = ({
  variant = 'info',
  title,
  icon,
  onClose,
  className = '',
  action,
  children,
}) => {
  const styles = variantStyles[variant] || variantStyles.info;
  const iconName = icon || styles.defaultIcon;

  return (
    <div
      role="alert"
      className={`p-3.5 rounded-xl border flex items-start justify-between gap-3 text-xs leading-relaxed shadow-xs transition-all ${styles.container} ${className}`}
    >
      <div className="flex items-start gap-2.5 flex-1 min-w-0">
        <Icon name={iconName} size={18} className={`${styles.iconColor} shrink-0 mt-0.5`} />
        <div className="space-y-0.5 flex-1 min-w-0">
          {title && <div className="font-semibold">{title}</div>}
          <div className="font-normal">{children}</div>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0 self-center">
        {action}
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Dismiss notification"
            className={`p-1 rounded transition-colors ${styles.closeButton}`}
          >
            <Icon name="close" size={15} />
          </button>
        )}
      </div>
    </div>
  );
};
