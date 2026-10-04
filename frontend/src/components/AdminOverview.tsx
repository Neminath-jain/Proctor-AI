import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import { DashboardOverviewData } from '../types';
import { Button, Badge, Icon, Alert } from './ui';

export const AdminOverview: React.FC = () => {
  const [data, setData] = useState<DashboardOverviewData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  const fetchOverview = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<DashboardOverviewData>('/admin/exams/overview/summary');
      setData(response.data);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch administrator dashboard overview.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
    const interval = setInterval(fetchOverview, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatRelativeTime = (timestamp?: string | null) => {
    if (!timestamp) return 'Recently';
    const date = new Date(timestamp);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffSec < 45) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  const getActivityBadgeVariant = (severity?: string, type?: string) => {
    if (severity === 'critical') return 'critical' as const;
    if (severity === 'high' || severity === 'warning') return 'warning' as const;
    if (type === 'violation') return 'warning' as const;
    if (type === 'submission') return 'success' as const;
    return 'outline' as const;
  };

  const getActivityIcon = (type?: string, severity?: string) => {
    if (severity === 'critical') return 'gpp_bad';
    if (type === 'violation') return 'warning';
    if (type === 'submission') return 'check_circle';
    if (type === 'exam') return 'assignment';
    return 'notifications';
  };

  return (
    <div id="admin-overview-section" className="space-y-6 pt-4 border-t border-outline-variant/40">
      {/* Header with Title and Refresh Control */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="telemetry-beacon shrink-0" />
            <span className="text-xs font-medium text-secondary uppercase tracking-wider">
              Live Operations & Invigilation
            </span>
          </div>
          <h2 className="text-lg md:text-xl font-semibold tracking-tight text-primary">
            Examination Overview & Action Center
          </h2>
          <p className="text-xs text-secondary">
            Real-time assessment summary, integrity monitoring, and rapid management shortcuts.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          <span className="text-[11px] text-secondary tabular-nums hidden md:inline">
            Updated {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchOverview}
            disabled={isLoading}
            isLoading={isLoading}
            icon="refresh"
            id="refresh-overview-btn"
            className="text-xs"
          >
            Refresh Data
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          Failed to synchronize overview data: {error}
        </Alert>
      )}

      {/* 1. EXAM OVERVIEW SUMMARY: Compact Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Exams */}
        <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 shadow-subtle flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Total Exams</span>
            <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
              <Icon name="quiz" size={18} />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl md:text-3xl font-bold tracking-tight text-primary tabular-nums font-mono">
              {data ? data.stats.total_exams : <span className="opacity-40 animate-pulse">--</span>}
            </div>
            <div className="text-xs text-secondary mt-1 flex items-center gap-1.5">
              <Badge variant="outline" size="xs">
                {data ? `${data.stats.active_exams} active` : '...'}
              </Badge>
              <span className="truncate">across question banks</span>
            </div>
          </div>
        </div>

        {/* Active In-Progress Sessions */}
        <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 shadow-subtle flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Active Sessions</span>
            <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
              <Icon name="cast_for_education" size={18} />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl md:text-3xl font-bold tracking-tight text-primary tabular-nums font-mono flex items-center gap-2">
              {data ? data.stats.active_sessions : <span className="opacity-40 animate-pulse">--</span>}
              {data && data.stats.active_sessions > 0 && (
                <span className="telemetry-beacon shrink-0" title="Active candidates streaming" />
              )}
            </div>
            <div className="text-xs text-secondary mt-1 truncate">
              {data && data.stats.active_sessions > 0 ? 'Live proctoring active' : 'No active sessions currently'}
            </div>
          </div>
        </div>

        {/* Total Candidates */}
        <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 shadow-subtle flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Total Candidates</span>
            <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
              <Icon name="groups" size={18} />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl md:text-3xl font-bold tracking-tight text-primary tabular-nums font-mono">
              {data ? data.stats.total_candidates : <span className="opacity-40 animate-pulse">--</span>}
            </div>
            <div className="text-xs text-secondary mt-1 truncate">
              Across {data ? data.stats.total_sessions : '...'} total examination sessions
            </div>
          </div>
        </div>

        {/* Flagged Sessions Awaiting Review */}
        <div className={`border rounded-2xl p-5 shadow-subtle flex flex-col justify-between transition-colors ${
          data && data.stats.flagged_sessions_count > 0
            ? 'border-amber-300 bg-amber-50/40'
            : 'border-outline-variant/60 bg-surface-container-lowest'
        }`}>
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Awaiting Review</span>
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
              data && data.stats.flagged_sessions_count > 0
                ? 'bg-amber-100 text-amber-950 border border-amber-300'
                : 'bg-surface-container text-primary'
            }`}>
              <Icon name="gavel" size={18} />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl md:text-3xl font-bold tracking-tight text-primary tabular-nums font-mono">
              {data ? data.stats.flagged_sessions_count : <span className="opacity-40 animate-pulse">--</span>}
            </div>
            <div className="text-xs mt-1 flex items-center gap-1.5">
              {data && data.stats.flagged_sessions_count > 0 ? (
                <Badge variant="warning" size="xs">
                  Action Required
                </Badge>
              ) : (
                <Badge variant="success" size="xs">
                  All Clear
                </Badge>
              )}
              <span className="text-secondary truncate">integrity anomalies</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. QUICK ACTIONS: Shortcuts formatted with the dashboard's visual card pattern */}
      <div>
        <div className="text-xs font-medium text-secondary mb-3 flex items-center gap-1.5">
          <Icon name="bolt" size={16} className="text-secondary" />
          <span>Quick Administrative Actions</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Action 1: Create New Exam */}
          <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 shadow-subtle flex flex-col justify-between hover:border-outline transition-colors">
            <div className="space-y-2">
              <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                <Icon name="add_circle" size={18} />
              </div>
              <h3 className="text-sm font-semibold text-primary">Create New Exam</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Configure question banks, MCQ options, coding test cases, time limits, and browser anti-cheat enforcement.
              </p>
            </div>
            <div className="pt-4">
              <Link
                to="/admin/exams/create"
                id="quick-action-create-exam"
                className="text-xs font-medium text-primary hover:underline flex items-center gap-1"
              >
                <span>Launch Exam Builder</span>
                <Icon name="arrow_forward" size={14} />
              </Link>
            </div>
          </div>

          {/* Action 2: Review Flagged Sessions */}
          <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 shadow-subtle flex flex-col justify-between hover:border-outline transition-colors">
            <div className="space-y-2">
              <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                <Icon name="policy" size={18} />
              </div>
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-primary">Review Flagged Sessions</h3>
                {data && data.stats.flagged_sessions_count > 0 && (
                  <Badge variant="warning" size="xs">
                    {data.stats.flagged_sessions_count} Pending
                  </Badge>
                )}
              </div>
              <p className="text-xs text-secondary leading-relaxed">
                Inspect candidate audit timelines, evaluate webcam snapshots, verify trust score breakdowns, and issue verdicts.
              </p>
            </div>
            <div className="pt-4">
              <Link
                to="/admin/exams"
                id="quick-action-review-flagged"
                className="text-xs font-medium text-primary hover:underline flex items-center gap-1"
              >
                <span>
                  {data && data.stats.flagged_sessions_count > 0
                    ? `Audit ${data.stats.flagged_sessions_count} flagged session${data.stats.flagged_sessions_count > 1 ? 's' : ''}`
                    : 'Browse candidate sessions'}
                </span>
                <Icon name="arrow_forward" size={14} />
              </Link>
            </div>
          </div>

          {/* Action 3: Live Monitoring & Roster */}
          <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 shadow-subtle flex flex-col justify-between hover:border-outline transition-colors">
            <div className="space-y-2">
              <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                <Icon name="monitoring" size={18} />
              </div>
              <h3 className="text-sm font-semibold text-primary">Live Invigilation & Roster</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Monitor active candidates in real time via live WebSockets, inspect tab away alerts, and broadcast announcements.
              </p>
            </div>
            <div className="pt-4">
              <Link
                to="/admin/exams"
                id="quick-action-manage-exams"
                className="text-xs font-medium text-primary hover:underline flex items-center gap-1"
              >
                <span>View all assessments</span>
                <Icon name="arrow_forward" size={14} />
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* 3. RECENT ACTIVITY FEED & FLAGGED QUEUE */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 pt-2">
        {/* Recent Activity Feed (7 Columns) */}
        <div className="lg:col-span-7 border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 md:p-6 shadow-subtle flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-outline-variant/60 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                  <Icon name="history" size={18} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-primary">Recent Activity Feed</h3>
                  <p className="text-xs text-secondary">Chronological event stream across candidates & assessments</p>
                </div>
              </div>
              <Badge variant="outline" size="xs">
                {data ? `${data.recent_activity.length} events` : 'Loading...'}
              </Badge>
            </div>

            {isLoading && !data ? (
              <div className="py-12 text-center text-xs text-secondary animate-pulse">
                Loading recent activity events...
              </div>
            ) : !data || data.recent_activity.length === 0 ? (
              <div className="py-10 text-center text-xs text-secondary">
                No recent activity recorded yet.
              </div>
            ) : (
              <div className="divide-y divide-outline-variant/40">
                {data.recent_activity.map((event) => (
                  <div
                    key={event.id}
                    className="py-3 first:pt-0 last:pb-0 flex items-start gap-3 hover:bg-surface-container-low/40 rounded-xl px-2 transition-colors"
                  >
                    <div className="mt-0.5 shrink-0 text-secondary">
                      <Icon name={getActivityIcon(event.type, event.severity)} size={18} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-xs font-semibold text-primary truncate">
                          {event.title}
                        </div>
                        <span className="text-[11px] text-secondary shrink-0 tabular-nums font-mono">
                          {formatRelativeTime(event.timestamp)}
                        </span>
                      </div>
                      {event.details && (
                        <p className="text-[11px] text-secondary mt-0.5 truncate">
                          {event.details}
                        </p>
                      )}
                      <div className="mt-1.5 flex items-center gap-2">
                        <Badge variant={getActivityBadgeVariant(event.severity, event.type)} size="xs">
                          {event.badge}
                        </Badge>
                        {event.exam_id && (
                          <Link
                            to={`/admin/exams/${event.exam_id}/sessions`}
                            className="text-[11px] font-medium text-primary hover:underline inline-flex items-center gap-0.5"
                          >
                            <span>Inspect sessions</span>
                            <Icon name="arrow_forward" size={12} />
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="pt-4 mt-4 border-t border-outline-variant/40 flex items-center justify-between">
            <span className="text-[11px] text-secondary">
              Proctoring telemetry updates in real-time
            </span>
            <Link
              to="/admin/exams"
              className="text-xs font-medium text-primary hover:underline flex items-center gap-1"
            >
              <span>Explore all exams</span>
              <Icon name="arrow_forward" size={14} />
            </Link>
          </div>
        </div>

        {/* Flagged Sessions Awaiting Review Queue (5 Columns) */}
        <div className="lg:col-span-5 border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 md:p-6 shadow-subtle flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-outline-variant/60 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                  <Icon name="verified_user" size={18} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-primary">Awaiting Review</h3>
                  <p className="text-xs text-secondary">Actionable candidate review queue</p>
                </div>
              </div>
              {data && data.flagged_sessions.length > 0 ? (
                <Badge variant="warning" size="xs">
                  {data.flagged_sessions.length} Pending
                </Badge>
              ) : (
                <Badge variant="success" size="xs">
                  Clean
                </Badge>
              )}
            </div>

            {isLoading && !data ? (
              <div className="py-12 text-center text-xs text-secondary animate-pulse">
                Checking integrity review queue...
              </div>
            ) : !data || data.flagged_sessions.length === 0 ? (
              <div className="py-12 px-4 text-center">
                <div className="w-10 h-10 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 mx-auto flex items-center justify-center mb-3">
                  <Icon name="task_alt" size={20} />
                </div>
                <div className="text-xs font-semibold text-primary">All Clear</div>
                <p className="text-[11px] text-secondary mt-1 leading-relaxed">
                  No candidate sessions currently require integrity review. All finished exams meet baseline trust thresholds.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {data.flagged_sessions.map((session) => (
                  <div
                    key={session.session_id}
                    className="border border-outline-variant/60 bg-surface-container-low/40 rounded-xl p-3.5 space-y-2 hover:border-outline transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold text-xs text-primary truncate">
                          {session.candidate_name}
                        </div>
                        <div className="text-[11px] text-secondary truncate">
                          {session.candidate_email}
                        </div>
                      </div>
                      <Badge
                        variant={session.trust_score < 80 ? 'critical' : 'warning'}
                        size="xs"
                      >
                        Trust: {Math.round(session.trust_score)}%
                      </Badge>
                    </div>

                    <div className="text-[11px] text-primary/90 font-medium truncate">
                      {session.exam_title}
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-outline-variant/40">
                      <span className="text-[11px] text-secondary flex items-center gap-1">
                        <Icon name="warning" size={13} className="text-amber-800" />
                        <span>{session.violation_count} flagged violation{session.violation_count === 1 ? '' : 's'}</span>
                      </span>
                      <Link
                        to={`/admin/exams/${session.exam_id}/sessions`}
                        className="text-xs font-semibold text-primary hover:underline flex items-center gap-0.5"
                      >
                        <span>Audit Session</span>
                        <Icon name="arrow_forward" size={14} />
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="pt-4 mt-4 border-t border-outline-variant/40">
            <Link
              to="/admin/exams"
              className="text-xs font-medium text-primary hover:underline flex items-center justify-between"
            >
              <span>Manage all exams and candidate sessions</span>
              <Icon name="arrow_forward" size={14} />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
