import React from 'react';
import { Icon } from './Icon';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'success';
  size?: 'sm' | 'md' | 'lg';
  icon?: string;
  iconPosition?: 'left' | 'right';
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  iconPosition = 'left',
  isLoading = false,
  className = '',
  disabled,
  ...props
}) => {
  const sizeClasses = {
    sm: 'px-3.5 py-1.5 text-xs gap-1.5 font-medium',
    md: 'px-5 py-2 text-sm gap-2 font-medium',
    lg: 'px-7 py-3 text-base gap-2.5 font-semibold',
  };

  const variantClasses = {
    primary:
      'bg-primary text-on-primary hover:bg-[#18181b] active:scale-[0.98] border border-zinc-900/10 shadow-sm shadow-zinc-950/10 ring-1 ring-white/10 ring-inset',
    secondary:
      'bg-transparent border border-zinc-300/80 text-zinc-900 hover:bg-zinc-100/70 hover:border-zinc-400 active:scale-[0.98] shadow-xs',
    outline:
      'bg-transparent border border-outline text-on-surface hover:bg-surface-container active:scale-[0.98]',
    ghost:
      'bg-transparent text-on-surface hover:bg-surface-container active:scale-[0.98] border border-transparent',
    destructive:
      'bg-error text-on-error hover:opacity-90 active:scale-[0.98] border border-transparent',
    success:
      'bg-success text-on-success hover:opacity-90 active:scale-[0.98] border border-transparent',
  };

  const iconSizes = {
    sm: 16,
    md: 18,
    lg: 20,
  };

  return (
    <button
      className={`inline-flex items-center justify-center rounded-full transition-all duration-150 disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="inline-block animate-spin mr-1">
          <Icon name="progress_activity" size={iconSizes[size]} />
        </span>
      ) : (
        icon && iconPosition === 'left' && <Icon name={icon} size={iconSizes[size]} />
      )}
      {children}
      {!isLoading && icon && iconPosition === 'right' && <Icon name={icon} size={iconSizes[size]} />}
    </button>
  );
};
