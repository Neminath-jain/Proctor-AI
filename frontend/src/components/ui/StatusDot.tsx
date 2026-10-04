import React from 'react';

export interface StatusDotProps {
  variant?: 'emerald' | 'amber' | 'rose' | 'zinc';
  size?: 'sm' | 'md';
  ping?: boolean;
  pulse?: boolean;
  className?: string;
}

const colorMap = {
  emerald: {
    bg: 'bg-emerald-600',
    ping: 'bg-emerald-400',
  },
  amber: {
    bg: 'bg-amber-600',
    ping: 'bg-amber-400',
  },
  rose: {
    bg: 'bg-rose-600',
    ping: 'bg-rose-400',
  },
  zinc: {
    bg: 'bg-zinc-600',
    ping: 'bg-zinc-400',
  },
};

const sizeMap = {
  sm: {
    container: 'h-2 w-2 min-w-[8px] min-h-[8px] max-w-[8px] max-h-[8px]',
    dot: 'h-2 w-2 min-w-[8px] min-h-[8px]',
  },
  md: {
    container: 'h-2.5 w-2.5 min-w-[10px] min-h-[10px] max-w-[10px] max-h-[10px]',
    dot: 'h-2.5 w-2.5 min-w-[10px] min-h-[10px]',
  },
};

export const StatusDot: React.FC<StatusDotProps> = ({
  variant = 'emerald',
  size = 'sm',
  ping = false,
  pulse = false,
  className = '',
}) => {
  const colors = colorMap[variant] || colorMap.emerald;
  const sizes = sizeMap[size] || sizeMap.sm;

  if (ping) {
    return (
      <span className={`relative inline-flex items-center justify-center shrink-0 ${sizes.container} ${className}`}>
        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${colors.ping} opacity-75`} />
        <span className={`relative inline-flex rounded-full ${sizes.dot} ${colors.bg} shrink-0`} />
      </span>
    );
  }

  if (pulse) {
    return (
      <span className={`relative inline-flex items-center justify-center shrink-0 ${sizes.container} ${className}`}>
        <span className={`inline-flex rounded-full ${sizes.dot} ${colors.bg} animate-pulse shrink-0`} />
      </span>
    );
  }

  return (
    <span
      className={`inline-flex rounded-full shrink-0 ${sizes.dot} ${colors.bg} ${className}`}
    />
  );
};
