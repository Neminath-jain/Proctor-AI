import React, { useState } from 'react';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { Button, Card, Badge, Icon } from './ui';

export const RBACTester: React.FC = () => {
  const { user } = useAuth();
  const [loadingRoute, setLoadingRoute] = useState<string | null>(null);
  const [result, setResult] = useState<{
    endpoint: string;
    status: number;
    data: any;
    allowed: boolean;
  } | null>(null);

  const testEndpoint = async (path: string) => {
    setLoadingRoute(path);
    try {
      const res = await apiClient.get(path);
      setResult({
        endpoint: path,
        status: res.status,
        data: res.data,
        allowed: true,
      });
    } catch (err: any) {
      setResult({
        endpoint: path,
        status: err.response?.status || 500,
        data: err.response?.data || { error: err.message },
        allowed: false,
      });
    } finally {
      setLoadingRoute(null);
    }
  };

  return (
    <Card rounded="2xl" className="p-6 md:p-8">
      <div className="flex items-center gap-2.5 mb-2">
        <div className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center text-primary">
          <Icon name="shield" size={18} />
        </div>
        <h3 className="text-base font-semibold text-primary">Role-Based Access Control (RBAC) Simulator</h3>
      </div>
      <p className="text-xs text-on-surface-variant mb-5">
        Current session role: <strong className="text-primary font-semibold capitalize">{user?.role}</strong>.
        Click below to simulate requests to protected routes with role verification.
      </p>

      <div className="flex flex-wrap gap-2.5 mb-5">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => testEndpoint('/auth/me')}
          id="test-me-route-btn"
          disabled={loadingRoute !== null}
          isLoading={loadingRoute === '/auth/me'}
          icon="play_arrow"
        >
          /auth/me (All Roles)
        </Button>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => testEndpoint('/auth/grader-only')}
          id="test-grader-route-btn"
          disabled={loadingRoute !== null}
          isLoading={loadingRoute === '/auth/grader-only'}
          icon="play_arrow"
        >
          /auth/grader-only (Grader & Admin)
        </Button>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => testEndpoint('/auth/admin-only')}
          id="test-admin-route-btn"
          disabled={loadingRoute !== null}
          isLoading={loadingRoute === '/auth/admin-only'}
          icon="play_arrow"
        >
          /auth/admin-only (Admin Only)
        </Button>
      </div>

      {result && (
        <div
          className={`p-4 rounded-xl border ${
            result.allowed
              ? 'bg-success-container/30 border-success/30'
              : 'bg-error-container/30 border-error/30'
          }`}
        >
          <div className="flex justify-between items-center mb-3">
            <div className="flex items-center gap-2">
              <Icon
                name={result.allowed ? 'check_circle' : 'cancel'}
                size={18}
                className={result.allowed ? 'text-success' : 'text-error'}
              />
              <span className="text-xs font-semibold text-primary">
                {result.endpoint} → HTTP {result.status} {result.allowed ? 'OK (Authorized)' : 'Forbidden'}
              </span>
            </div>
            <Badge variant={result.allowed ? 'success' : 'error'} size="sm">
              {result.allowed ? 'Access Granted' : 'Access Denied (403)'}
            </Badge>
          </div>

          <pre className="p-3 rounded-lg bg-[#111111] text-gray-200 font-mono text-xs overflow-x-auto">
            {JSON.stringify(result.data, null, 2)}
          </pre>
        </div>
      )}
    </Card>
  );
};
