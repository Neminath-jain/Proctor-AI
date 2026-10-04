import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { UserRole } from '../types';

interface ProtectedRouteProps {
  children: React.ReactElement;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <div style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
          Loading session...
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <div className="glass-card" style={{ padding: '2.5rem', textAlign: 'center', maxWidth: '500px', margin: '3rem auto' }}>
        <h2 style={{ color: 'var(--accent-rose)', marginBottom: '1rem' }}>Access Denied</h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
          Your current account role (<strong>{user.role}</strong>) does not have permission to view this section.
        </p>
        <Navigate to="/" replace />
      </div>
    );
  }

  return children;
};
