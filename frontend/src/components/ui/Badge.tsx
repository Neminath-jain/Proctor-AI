import React from 'react';
import { Icon } from './Icon';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'success' | 'warning' | 'error' | 'critical' | 'neutral' | 'outline' | 'dark' | 'telemetry';
  size?: 'xs' | 'sm' | 'md';
  icon?: string;
  iconPosition?: 'left' | 'right';
  rounded?: 'full' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'sm',
  icon,
  iconPosition = 'left',
  rounded = 'full',
  className = '',
  ...props
}) => {
  const sizeClasses = {
    xs: 'px-2 py-0.5 text-[11px] gap-1 font-medium',
    sm: 'px-2.5 py-0.5 text-xs gap-1 font-medium',
    md: 'px-3.5 py-1 text-sm gap-1.5 font-medium',
  };

  const iconSizes = {
    xs: 12,
    sm: 14,
    md: 16,
  };

  const variantClasses = {
    success:
      'bg-emerald-100 text-emerald-950 border border-emerald-300 font-medium',
    warning:
      'bg-amber-100 text-amber-950 border border-amber-300 font-medium',
    error:
      'bg-rose-100 text-rose-950 border border-rose-300 font-medium',
    critical:
      'bg-rose-700 text-white border border-rose-800 font-semibold shadow-xs',
    neutral:
      'bg-zinc-100 text-zinc-900 border border-zinc-200 font-medium',
    outline:
      'bg-transparent text-zinc-900 border border-zinc-300 font-medium',
    dark:
      'bg-zinc-900 text-white border border-zinc-900 font-medium',
    telemetry:
      'bg-surface-container-lowest text-primary border border-outline-variant/80 shadow-subtle',
  };

  // Default icons for semantic statuses to enforce rule: "never rely on color alone"
  let effectiveIcon = icon;
  if (!effectiveIcon) {
    if (variant === 'success') effectiveIcon = 'check_circle';
    else if (variant === 'warning') effectiveIcon = 'warning';
    else if (variant === 'error') effectiveIcon = 'error';
    else if (variant === 'critical') effectiveIcon = 'gpp_bad';
  }

  const radiusClass = rounded === 'md' ? 'rounded-md' : 'rounded-full';

  return (
    <span
      className={`inline-flex items-center ${radiusClass} select-none ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {effectiveIcon && iconPosition === 'left' && (
        <Icon name={effectiveIcon} size={iconSizes[size]} className="opacity-90 shrink-0" />
      )}
      <span>{children}</span>
      {effectiveIcon && iconPosition === 'right' && (
        <Icon name={effectiveIcon} size={iconSizes[size]} className="opacity-90 shrink-0" />
      )}
    </span>
  );
};
