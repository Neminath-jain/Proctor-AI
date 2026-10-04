import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { AdminOverview } from '../components/AdminOverview';
import { Button, Badge, Icon } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export const Dashboard: React.FC = () => {
  useDocumentTitle('Dashboard — ProctorAI', 'Candidate and administrator examination control center.');
  const { user } = useAuth();

  const getRoleBadge = (role?: string) => {
    switch (role) {
      case 'admin':
        return (
          <Badge variant="dark" size="xs" icon="security" className="capitalize font-medium">
            Administrator
          </Badge>
        );
      case 'grader':
        return (
          <Badge variant="neutral" size="xs" icon="grade" className="capitalize font-medium">
            Grader
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" size="xs" icon="school" className="capitalize font-medium">
            Candidate
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Welcome Card & Navigation */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 md:p-8 shadow-subtle">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
          <div className="space-y-3 flex-1">
            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-primary">
              Welcome back, {user?.name}
            </h1>

            <p className="text-sm text-secondary max-w-2xl leading-relaxed">
              {user?.role === 'admin'
                ? 'Oversee assessment delivery, monitor real-time anti-cheat telemetry, and review flagged candidate sessions.'
                : 'View your assigned examinations, complete your system pre-checks, and access verified performance records.'}
            </p>

            <div className="flex flex-wrap gap-2.5 pt-2">
              {user?.role === 'admin' ? (
                <>
                  <Link to="/admin/exams">
                    <Button variant="primary" size="sm" icon="tune" className="shadow-subtle">
                      Manage Assessments
                    </Button>
                  </Link>
                  <Link to="/admin/exams/create">
                    <Button variant="secondary" size="sm" icon="add_circle">
                      Create New Exam
                    </Button>
                  </Link>
                  <Link to="/exams">
                    <Button variant="outline" size="sm" icon="assignment">
                      Available Assessments
                    </Button>
                  </Link>
                </>
              ) : (
                <Link to="/exams">
                  <Button variant="primary" size="sm" icon="assignment" className="shadow-subtle">
                    Available Assessments
                  </Button>
                </Link>
              )}
            </div>
          </div>

          {/* Account Profile Card */}
          <div className="border border-outline-variant/60 bg-surface-container-low/40 rounded-xl p-4 shrink-0 lg:w-72">
            <div className="text-xs font-medium text-secondary mb-1">
              Account
            </div>
            <div className="font-semibold text-sm text-primary truncate mb-1">
              {user?.name}
            </div>
            <div className="text-xs text-secondary truncate mb-3">
              {user?.email}
            </div>
            <div className="pt-2.5 border-t border-outline-variant/50 flex items-center justify-between">
              <span className="text-xs text-secondary">Role</span>
              {getRoleBadge(user?.role)}
            </div>
          </div>
        </div>
      </div>

      {/* Candidate Guidance & Information Panel (displayed for candidates) */}
      {user?.role !== 'admin' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 shadow-subtle flex flex-col justify-between">
            <div className="space-y-2">
              <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                <Icon name="check_circle" size={18} />
              </div>
              <h2 className="text-sm font-semibold text-primary">Before you begin an assessment</h2>
              <p className="text-xs text-secondary leading-relaxed">
                Please ensure you are in a well-lit, quiet room with a stable internet connection. Webcams and microphones are required for proctored sessions.
              </p>
            </div>
            <div className="pt-4">
              <Link to="/exams" className="text-xs font-medium text-primary hover:underline flex items-center gap-1">
                <span>View available assessments</span>
                <Icon name="arrow_forward" size={14} />
              </Link>
            </div>
          </div>

          <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 shadow-subtle flex flex-col justify-between">
            <div className="space-y-2">
              <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                <Icon name="verified_user" size={18} />
              </div>
              <h2 className="text-sm font-semibold text-primary">Assessment Integrity</h2>
              <p className="text-xs text-secondary leading-relaxed">
                Exams may enforce fullscreen mode and monitor tab focus. During an exam, remain centered in your camera frame and refrain from navigating away.
              </p>
            </div>
            <div className="pt-4">
              <span className="text-xs text-secondary flex items-center gap-1.5">
                <span className="telemetry-beacon shrink-0" />
                <span>Integrity services active during active sessions</span>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Administrator Control Center & Overview (Restricted strictly to Administrator role) */}
      {user?.role === 'admin' && <AdminOverview />}
    </div>
  );
};
