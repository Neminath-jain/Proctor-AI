import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'fog' | 'surface' | 'dark' | 'terminal';
  rounded?: 'lg' | 'xl' | '2xl' | '3xl';
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'default',
  rounded = '2xl',
  hoverable = false,
  className = '',
  ...props
}) => {
  const roundedClass = {
    lg: 'rounded-lg',
    xl: 'rounded-xl',
    '2xl': 'rounded-2xl',
    '3xl': 'rounded-3xl',
  }[rounded];

  const variantClass = {
    default: 'bg-surface-container-low border border-outline-variant/60 shadow-subtle',
    fog: 'fog-gradient-card border border-outline-variant shadow-subtle',
    surface: 'bg-surface-container-lowest border border-outline-variant/60 shadow-subtle',
    dark: 'bg-[#111111] text-white border border-[#262626] shadow-terminal',
    terminal: 'bg-surface-container-lowest border border-outline-variant/80 shadow-terminal',
  }[variant];

  const hoverClass = hoverable
    ? 'transition-all duration-150 hover:border-outline hover:shadow-elevation'
    : '';

  return (
    <div
      className={`${roundedClass} ${variantClass} ${hoverClass} p-6 text-on-surface ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className = '',
  ...props
}) => (
  <div className={`mb-4 flex flex-col space-y-1.5 ${className}`} {...props}>
    {children}
  </div>
);

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  children,
  className = '',
  ...props
}) => (
  <h3 className={`text-lg font-semibold tracking-tight text-on-surface ${className}`} {...props}>
    {children}
  </h3>
);

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  children,
  className = '',
  ...props
}) => (
  <p className={`text-sm text-on-surface-variant ${className}`} {...props}>
    {children}
  </p>
);

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className = '',
  ...props
}) => (
  <div className={`${className}`} {...props}>
    {children}
  </div>
);

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className = '',
  ...props
}) => (
  <div className={`mt-6 pt-4 border-t border-outline-variant/60 flex items-center justify-between ${className}`} {...props}>
    {children}
  </div>
);
