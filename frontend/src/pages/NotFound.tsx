import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Icon } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export const NotFound: React.FC = () => {
  const navigate = useNavigate();
  useDocumentTitle('404 — Page Not Found', 'The requested page or examination could not be found.');

  return (
    <div className="min-h-[65vh] flex items-center justify-center p-4">
      <Card variant="default" className="max-w-md w-full text-center p-8 md:p-10 border border-outline-variant/60 shadow-xl">
        <div className="w-16 h-16 rounded-3xl bg-surface-container-high text-primary flex items-center justify-center mx-auto mb-6 shadow-inner">
          <Icon name="explore_off" size={32} className="text-secondary" />
        </div>

        <div className="text-xs font-semibold text-secondary mb-1.5">
          Error 404
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-primary mb-2">
          Page Not Found
        </h1>
        <p className="text-xs text-secondary leading-relaxed mb-8">
          The requested page or assessment could not be found or may have been moved.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Button
            variant="primary"
            onClick={() => navigate('/')}
            icon="dashboard"
            className="w-full sm:w-auto"
          >
            Go to Dashboard
          </Button>
          <Button
            variant="secondary"
            onClick={() => navigate('/exams')}
            icon="assignment"
            className="w-full sm:w-auto"
          >
            Available Exams
          </Button>
        </div>
      </Card>
    </div>
  );
};
