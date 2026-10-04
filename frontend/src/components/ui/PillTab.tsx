import React from 'react';
import { Icon } from './Icon';

export interface PillTabItem {
  id: string;
  label: string;
  icon?: string;
  badge?: string | number;
}

export interface PillTabProps {
  items: PillTabItem[];
  activeId: string;
  onChange: (id: string) => void;
  size?: 'sm' | 'md';
  className?: string;
}

export const PillTab: React.FC<PillTabProps> = ({
  items,
  activeId,
  onChange,
  size = 'md',
  className = '',
}) => {
  const sizeClasses = {
    sm: 'px-3 py-1 text-xs',
    md: 'px-4 py-1.5 text-sm',
  };

  return (
    <div
      className={`inline-flex items-center gap-1 p-1 bg-surface-container-high rounded-full border border-outline-variant select-none ${className}`}
      role="tablist"
    >
      {items.map((item) => {
        const isActive = item.id === activeId;
        return (
          <button
            key={item.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(item.id)}
            className={`inline-flex items-center gap-1.5 rounded-full font-medium transition-all duration-150 ${sizeClasses[size]} ${
              isActive
                ? 'bg-primary text-on-primary shadow-none'
                : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
            }`}
          >
            {item.icon && (
              <Icon
                name={item.icon}
                size={size === 'sm' ? 14 : 16}
                className={isActive ? 'text-on-primary' : 'text-on-surface-variant'}
              />
            )}
            <span>{item.label}</span>
            {item.badge !== undefined && (
              <span
                className={`ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-semibold ${
                  isActive
                    ? 'bg-surface-container-highest text-primary'
                    : 'bg-surface-container-highest text-on-surface-variant'
                }`}
              >
                {item.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
