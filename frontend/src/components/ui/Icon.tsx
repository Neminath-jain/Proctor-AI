import React from 'react';

export interface IconProps {
  name: string;
  className?: string;
  size?: number | string;
}

export const Icon: React.FC<IconProps> = ({ name, className = '', size }) => {
  return (
    <span
      className={`material-symbols-outlined select-none ${className}`}
      style={size ? { fontSize: typeof size === 'number' ? `${size}px` : size } : undefined}
      aria-hidden="true"
    >
      {name}
    </span>
  );
};
