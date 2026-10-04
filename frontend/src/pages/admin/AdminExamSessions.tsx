import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import {
  CandidateSessionRow,
  TimelineItem,
  LiveViolationEvent,
  BulkApproveResponse,
} from '../../types';
import { Button, Badge, Card, Icon, PillTab, StatusDot, Alert } from '../../components/ui';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { useExamLiveMonitoring } from '../../hooks/useExamLiveMonitoring';

export const AdminExamSessions: React.FC = () => {
  const { examId } = useParams<{ examId: string }>();
  const navigate = useNavigate();
  useDocumentTitle(
    'Candidate Monitoring & Integrity Command Center — Admin',
    'Real-time live proctoring grid, chronological violation review timeline, and deterministic trust scoring.'
  );

  // Authentication token for WebSocket
  const token = localStorage.getItem('access_token');

  // View state: 'grid' vs 'table'
  const [viewMode, setViewMode] = useState<string>('grid');

  // Filter & Search states
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [reviewFilter, setReviewFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'trust_asc' | 'trust_desc' | 'viols_desc' | 'started_desc' | 'name_asc'>('trust_asc');

  // Pagination State
  const [page, setPage] = useState(1);
  const [pageSize] = useState(30);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Live WebSocket Monitoring
  const [latestLiveAlert, setLatestLiveAlert] = useState<LiveViolationEvent | null>(null);

  const handleLiveViolation = useCallback((event: LiveViolationEvent) => {
    setLatestLiveAlert(event);
  }, []);

  const {
    isConnected,
    connectionStatus,
    liveSessions,
    setInitialSessions,
    updateSessionLocally,
    reconnect,
  } = useExamLiveMonitoring({
    examId,
    token,
    enabled: true,
    onViolationReceived: handleLiveViolation,
  });

  // Per-Candidate Review Workspace Modal State
  const [reviewSession, setReviewSession] = useState<CandidateSessionRow | null>(null);
  const [timelineItems, setTimelineItems] = useState<TimelineItem[]>([]);
  const [isLoadingTimeline, setIsLoadingTimeline] = useState(false);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [sessionReviewNotes, setSessionReviewNotes] = useState('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);
  const [reviewSuccessMsg, setReviewSuccessMsg] = useState<string | null>(null);

  // Evidence Inspection Modal State
  const [selectedEvidence, setSelectedEvidence] = useState<{
    url: string;
    blobUrl: string;
    type: 'image' | 'audio';
    title: string;
    timestamp?: string;
  } | null>(null);
  const [loadingEvidenceId, setLoadingEvidenceId] = useState<string | null>(null);

  // Bulk Approval Modal State
  const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);
  const [bulkMinTrust, setBulkMinTrust] = useState<number>(85.0);
  const [isSubmittingBulk, setIsSubmittingBulk] = useState(false);
  const [bulkResult, setBulkResult] = useState<BulkApproveResponse | null>(null);

  // Phase 6 Anti-Cheat Scan State
  const [isScanningAntiCheat, setIsScanningAntiCheat] = useState(false);
  const [antiCheatScanResult, setAntiCheatScanResult] = useState<string | null>(null);

  // Initial Fetch of Candidate Sessions from REST API
  const fetchSessions = useCallback(async () => {
    if (!examId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.get<CandidateSessionRow[]>(`/admin/exams/${examId}/sessions`, {
        params: { page, page_size: pageSize },
      });
      setInitialSessions(res.data);

      const countHeader = res.headers['x-total-count'];
      const pagesHeader = res.headers['x-total-pages'];
      if (countHeader) setTotalCount(Number(countHeader));
      if (pagesHeader) setTotalPages(Number(pagesHeader));
      else setTotalPages(Math.max(1, Math.ceil((Number(countHeader) || res.data.length) / pageSize)));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load candidate submissions.');
    } finally {
      setIsLoading(false);
    }
  }, [examId, page, pageSize, setInitialSessions]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Combine liveSessions map into a list
  const sessionList = useMemo(() => {
    return Object.values(liveSessions);
  }, [liveSessions]);

  // Filter and sort sessions
  const filteredSessions = useMemo(() => {
    return sessionList
      .filter((sess) => {
        // Search query
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchName = sess.candidate_name?.toLowerCase().includes(q);
          const matchEmail = sess.candidate_email?.toLowerCase().includes(q);
          const matchId = sess.session_id.toLowerCase().includes(q);
          if (!matchName && !matchEmail && !matchId) return false;
        }

        // Status filter
        if (statusFilter !== 'all' && sess.status !== statusFilter) return false;

        // Review status filter
        const reviewStatus = sess.review_status || 'pending';
        if (reviewFilter !== 'all' && reviewStatus !== reviewFilter) return false;

        // Risk tier filter
        const score = sess.trust_score !== undefined ? sess.trust_score : 100.0;
        if (riskFilter === 'safe' && score < 80.0) return false;
        if (riskFilter === 'moderate' && (score < 50.0 || score >= 80.0)) return false;
        if (riskFilter === 'critical' && score >= 50.0) return false;

        return true;
      })
      .sort((a, b) => {
        const scoreA = a.trust_score !== undefined ? a.trust_score : 100.0;
        const scoreB = b.trust_score !== undefined ? b.trust_score : 100.0;
        const violsA = a.violation_count || 0;
        const violsB = b.violation_count || 0;

        switch (sortBy) {
          case 'trust_asc':
            return scoreA - scoreB;
          case 'trust_desc':
            return scoreB - scoreA;
          case 'viols_desc':
            return violsB - violsA;
          case 'started_desc':
            return new Date(b.started_at).getTime() - new Date(a.started_at).getTime();
          case 'name_asc':
            return (a.candidate_name || '').localeCompare(b.candidate_name || '');
          default:
            return 0;
        }
      });
  }, [sessionList, searchQuery, statusFilter, reviewFilter, riskFilter, sortBy]);

  // Aggregate Metrics
  const totalSessionsCount = totalCount || sessionList.length;
  const activeSessionsCount = sessionList.filter((s) => s.status === 'in_progress').length;
  const criticalRiskCount = sessionList.filter((s) => (s.trust_score !== undefined ? s.trust_score < 50.0 : false)).length;
  const pendingReviewCount = sessionList.filter((s) => !s.review_status || s.review_status === 'pending').length;

  const avgTrustScore = useMemo(() => {
    if (sessionList.length === 0) return '100.0';
    const sum = sessionList.reduce((acc, s) => acc + (s.trust_score !== undefined ? s.trust_score : 100.0), 0);
    return (sum / sessionList.length).toFixed(1);
  }, [sessionList]);

  // Qualifying candidates for bulk approval (trust_score >= 85, no critical violations)
  const bulkQualifyingCount = useMemo(() => {
    return sessionList.filter((s) => {
      const score = s.trust_score !== undefined ? s.trust_score : 100.0;
      const reviewStatus = s.review_status || 'pending';
      return score >= bulkMinTrust && reviewStatus === 'pending';
    }).length;
  }, [sessionList, bulkMinTrust]);

  // Open Review Timeline Workspace
  const handleOpenReview = async (sess: CandidateSessionRow) => {
    setReviewSession(sess);
    setSessionReviewNotes(sess.review_notes || '');
    setIsLoadingTimeline(true);
    setTimelineError(null);
    setTimelineItems([]);
    setReviewSuccessMsg(null);

    try {
      const { data } = await apiClient.get<TimelineItem[]>(
        `/admin/exams/${examId}/sessions/${sess.session_id}/review-timeline`
      );
      setTimelineItems(data);
    } catch (err: any) {
      setTimelineError(err.response?.data?.detail || 'Failed to load chronological review timeline.');
    } finally {
      setIsLoadingTimeline(false);
    }
  };

  // Submit Session-level Verdict
  const handleSubmitSessionReview = async (verdict: 'reviewed_benign' | 'confirmed_cheating' | 'pending') => {
    if (!reviewSession || !examId) return;
    setIsSubmittingReview(true);
    setReviewSuccessMsg(null);

    try {
      await apiClient.post(`/admin/exams/${examId}/sessions/${reviewSession.session_id}/review`, {
        review_status: verdict,
        notes: sessionReviewNotes || undefined,
      });

      const updated = {
        ...reviewSession,
        review_status: verdict,
        review_notes: sessionReviewNotes,
        reviewed_at: new Date().toISOString(),
      };
      setReviewSession(updated);
      updateSessionLocally(reviewSession.session_id, updated);
      setReviewSuccessMsg(`Session marked as ${verdict.replace('_', ' ').toUpperCase()} successfully.`);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update session review status.');
    } finally {
      setIsSubmittingReview(false);
    }
  };

  // Submit Individual Violation Verdict (Recalculates Trust Score!)
  const handleReviewIndividualViolation = async (
    violationId: string,
    verdict: 'reviewed_benign' | 'confirmed_cheating' | 'unreviewed'
  ) => {
    if (!reviewSession || !examId) return;

    // Clean UUID if prefixed
    const cleanId = violationId.replace(/^viol_/, '');

    try {
      const { data } = await apiClient.post(
        `/admin/exams/${examId}/sessions/${reviewSession.session_id}/violations/${cleanId}/review`,
        { review_status: verdict }
      );

      // Update timeline item status locally
      setTimelineItems((prev) =>
        prev.map((item) =>
          item.id === violationId || item.id === `viol_${cleanId}`
            ? { ...item, review_status: verdict }
            : item
        )
      );

      // Update session trust score locally
      if (data.updated_trust_score !== undefined) {
        const updated = {
          ...reviewSession,
          trust_score: data.updated_trust_score,
        };
        setReviewSession(updated);
        updateSessionLocally(reviewSession.session_id, { trust_score: data.updated_trust_score });
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update violation review.');
    }
  };

  // Phase 6: Trigger On-Demand Anti-Cheat Forensic Scan
  const handleRunAntiCheatScan = async () => {
    if (!examId) return;
    setIsScanningAntiCheat(true);
    setAntiCheatScanResult(null);
    try {
      const { data } = await apiClient.post(`/admin/exams/${examId}/anti-cheat-scan`);
      setAntiCheatScanResult(
        `Anti-cheat scan completed: ${data.code_similarity_flags} code similarity flags, ${data.mcq_collusion_flags} MCQ collusion flags detected across ${data.sessions_scanned} sessions.`
      );
      await fetchSessions();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to execute anti-cheat scan.');
    } finally {
      setIsScanningAntiCheat(false);
    }
  };

  // Inspect Forensic Evidence
  const handleViewEvidence = async (url: string, violationType: string, timestamp?: string) => {
    if (!url) return;
    setLoadingEvidenceId(url);
    try {
      const endpoint = url.replace(/^\/api\/v1/, '');
      const res = await apiClient.get(endpoint, { responseType: 'blob' });
      const blobUrl = URL.createObjectURL(res.data);
      const isAudio = violationType.includes('audio');
      setSelectedEvidence({
        url,
        blobUrl,
        type: isAudio ? 'audio' : 'image',
        title: `${formatViolationName(violationType)} Evidence`,
        timestamp,
      });
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to retrieve evidence recording.');
    } finally {
      setLoadingEvidenceId(null);
    }
  };

  const handleCloseEvidence = () => {
    if (selectedEvidence?.blobUrl) {
      URL.revokeObjectURL(selectedEvidence.blobUrl);
    }
    setSelectedEvidence(null);
  };

  // Execute Bulk Approval
  const handleExecuteBulkApprove = async () => {
    if (!examId) return;
    setIsSubmittingBulk(true);
    setBulkResult(null);

    try {
      const { data } = await apiClient.post<BulkApproveResponse>(
        `/admin/exams/${examId}/sessions/bulk-approve`,
        { min_trust_score: bulkMinTrust }
      );
      setBulkResult(data);

      // Mark approved sessions locally
      for (const id of data.approved_session_ids) {
        updateSessionLocally(id, {
          review_status: 'reviewed_benign',
          reviewed_at: new Date().toISOString(),
        });
      }
      setTimeout(() => {
        setIsBulkModalOpen(false);
        setBulkResult(null);
        fetchSessions();
      }, 2000);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Bulk approval execution failed.');
    } finally {
      setIsSubmittingBulk(false);
    }
  };

  // Helpers
  const formatEventTitle = (title: string) => {
    if (title.toUpperCase().includes('ANSWER SUBMISSION')) {
      return title
        .replace(/ANSWER SUBMISSION\s*\/\/\s*/i, 'Answer submission — ')
        .replace(/\/\//g, '—');
    }
    return title
      .toLowerCase()
      .replace(/_/g, ' ')
      .replace(/(^|\s)\S/g, (c) => c.toUpperCase());
  };

  const formatViolationName = formatEventTitle;

  const getTrustBadge = (score?: number) => {
    const val = score !== undefined ? score : 100.0;
    if (val >= 80.0) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-950 border border-emerald-300">
          <StatusDot variant="emerald" pulse />
          <span className="font-mono tabular-nums">{val.toFixed(1)} / 100</span>
          <span>Safe</span>
        </span>
      );
    } else if (val >= 50.0) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-950 border border-amber-300">
          <StatusDot variant="amber" />
          <span className="font-mono tabular-nums">{val.toFixed(1)} / 100</span>
          <span>Moderate</span>
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-950 border border-rose-300">
          <StatusDot variant="rose" pulse />
          <span className="font-mono tabular-nums">{val.toFixed(1)} / 100</span>
          <span>Critical</span>
        </span>
      );
    }
  };

  const getSessionStatusBadge = (status: string) => {
    switch (status) {
      case 'submitted':
        return (
          <Badge variant="neutral" size="xs">
            Submitted
          </Badge>
        );
      case 'in_progress':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-950 border border-amber-300">
            <StatusDot variant="amber" ping />
            Live
          </span>
        );
      case 'timed_out':
        return (
          <Badge variant="neutral" size="xs">
            Timed out
          </Badge>
        );
      case 'terminated':
        return (
          <Badge variant="critical" size="xs">
            Terminated
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" size="xs" className="capitalize">
            {status.replace(/_/g, ' ')}
          </Badge>
        );
    }
  };

  const getReviewStatusBadge = (status?: string) => {
    switch (status) {
      case 'reviewed_benign':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-950 border border-emerald-300">
            <Icon name="check_circle" size={13} className="text-emerald-700" />
            Verified (Benign)
          </span>
        );
      case 'confirmed_cheating':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-950 border border-rose-300">
            <Icon name="gpp_bad" size={13} className="text-rose-700" />
            Cheating confirmed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-100 text-zinc-900 border border-zinc-300">
            <Icon name="hourglass_empty" size={13} className="text-zinc-600" />
            Pending review
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Navigation */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-xl p-6 shadow-terminal">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-6 border-b border-outline-variant/60">
          <div>
            <div className="flex items-center gap-3 mb-1.5 flex-wrap">
              <span className="telemetry-beacon shrink-0" />
              <span className="text-xs font-medium text-secondary">
                Live proctoring room
              </span>
              {/* WebSocket Status Indicator */}
              {isConnected ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-950 border border-emerald-300">
                  <StatusDot variant="emerald" pulse />
                  Live feed active
                </span>
              ) : connectionStatus === 'connecting' ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-950 border border-amber-300">
                  <StatusDot variant="amber" ping />
                  Connecting feed...
                </span>
              ) : (
                <button
                  onClick={reconnect}
                  className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-950 border border-amber-300 hover:bg-amber-200 transition-all"
                  title="Click to reconnect WebSocket stream"
                >
                  <Icon name="refresh" size={12} className="text-amber-800" />
                  Feed offline (reconnect)
                </button>
              )}
            </div>
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-primary">
              Live Proctoring & Integrity Command Center
            </h1>
            <p className="text-xs text-secondary mt-1">
              Real-time candidate monitoring, live alerts, and integrity review.
            </p>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap shrink-0">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRunAntiCheatScan}
              isLoading={isScanningAntiCheat}
              icon="policy"
              className="text-xs font-medium"
            >
              Run Anti-Cheat Scan
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsBulkModalOpen(true)}
              icon="rule"
              className="text-xs font-medium"
            >
              Approve Safe Sessions ({bulkQualifyingCount})
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={fetchSessions}
              isLoading={isLoading}
              icon="refresh"
              className="text-xs font-medium"
            >
              Refresh
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate('/admin/exams')}
              icon="arrow_back"
              className="text-xs font-medium"
            >
              Back to Exams
            </Button>
          </div>
        </div>

        {/* Anti-Cheat Scan Notification Banner */}
        {antiCheatScanResult && (
          <div className="mt-4">
            <Alert
              variant="warning"
              icon="policy"
              onClose={() => setAntiCheatScanResult(null)}
            >
              {antiCheatScanResult}
            </Alert>
          </div>
        )}

        {/* High-density Live Metrics Ledger */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 pt-6">
          <div className="border-r border-outline-variant/40 pr-3">
            <div className="text-xs text-secondary font-medium">
              Total candidates
            </div>
            <div className="font-mono tabular-nums text-2xl font-bold text-primary mt-1">
              {totalSessionsCount}
            </div>
          </div>

          <div className="border-r border-outline-variant/40 pr-3">
            <div className="text-xs text-secondary font-medium">
              Active sessions
            </div>
            <div className="font-mono tabular-nums text-2xl font-bold text-primary mt-1 flex items-center gap-1.5">
              {activeSessionsCount > 0 && <span className="telemetry-beacon shrink-0" />}
              {activeSessionsCount}
            </div>
          </div>

          <div className="border-r border-outline-variant/40 pr-3">
            <div className="text-xs text-secondary font-medium">
              Average trust score
            </div>
            <div className="font-mono tabular-nums text-2xl font-bold text-primary mt-1">
              {avgTrustScore} / 100
            </div>
          </div>

          <div className="border-r border-outline-variant/40 pr-3">
            <div className="text-xs text-secondary font-medium">
              Flagged sessions
            </div>
            <div
              className={`font-mono tabular-nums text-2xl font-bold mt-1 ${
                criticalRiskCount > 0 ? 'text-rose-700' : 'text-primary'
              }`}
            >
              {criticalRiskCount}
            </div>
          </div>

          <div>
            <div className="text-xs text-secondary font-medium">
              Pending reviews
            </div>
            <div className="font-mono tabular-nums text-2xl font-bold text-amber-800 mt-1">
              {pendingReviewCount}
            </div>
          </div>
        </div>
      </div>

      {/* Live Incident Broadcast Ticker Banner */}
      {latestLiveAlert && (
        <div className="p-3.5 rounded-xl border border-rose-300 bg-rose-50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2.5 flex-wrap">
            <StatusDot variant="rose" ping />
            <span className="font-bold text-rose-900">Live incident alert:</span>
            <span className="text-zinc-900 font-semibold">
              Candidate &quot;{latestLiveAlert.candidate_name || latestLiveAlert.candidate_id?.slice(0, 8)}&quot;
            </span>
            <span className="text-zinc-700">
              triggered{' '}
              <span className="text-rose-800 font-semibold">
                {formatViolationName(latestLiveAlert.violation.violation_type)}
              </span>
            </span>
            <span className="text-zinc-600">
              • Recalculated trust score:{' '}
              <span className="text-zinc-900 font-mono font-bold">{latestLiveAlert.trust_score.toFixed(1)}</span>
            </span>
          </div>

          <button
            onClick={() => {
              const matched = liveSessions[latestLiveAlert.session_id];
              if (matched) handleOpenReview(matched);
            }}
            className="text-xs text-rose-800 hover:text-rose-950 underline font-semibold cursor-pointer self-start sm:self-auto"
          >
            Review incident →
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-300 text-rose-950 flex items-center gap-3 text-xs font-medium">
          <Icon name="error" className="text-rose-700" size={18} />
          <span>Error loading sessions: {error}</span>
        </div>
      )}

      {/* View Switcher, Filter & Search Toolbar */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-xl p-4 shadow-terminal space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          {/* PillTab View Mode Selector */}
          <PillTab
            items={[
              { id: 'grid', label: 'Live Grid', icon: 'grid_view' },
              { id: 'table', label: 'Audit Table', icon: 'table_rows' },
            ]}
            activeId={viewMode}
            onChange={(id) => setViewMode(id)}
            size="sm"
          />

          {/* Search Box */}
          <div className="relative flex-1 max-w-md">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-secondary">
              <Icon name="search" size={16} />
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by candidate name, email, or session ID..."
              className="w-full pl-9 pr-4 py-2 text-xs bg-surface-container-low border border-outline-variant/60 rounded-lg text-primary placeholder-secondary focus:outline-none focus:border-primary"
            />
          </div>
        </div>

        {/* Multi-Factor Filter & Sort Bar */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-outline-variant/40 text-xs">
          {/* Status Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-secondary font-medium">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-surface-container-low border border-outline-variant/60 rounded-lg px-2.5 py-1 text-primary focus:outline-none"
            >
              <option value="all">All statuses</option>
              <option value="in_progress">In progress</option>
              <option value="submitted">Submitted</option>
              <option value="terminated">Terminated</option>
            </select>
          </div>

          {/* Review Status Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-secondary font-medium">Review:</span>
            <select
              value={reviewFilter}
              onChange={(e) => setReviewFilter(e.target.value)}
              className="bg-surface-container-low border border-outline-variant/60 rounded-lg px-2.5 py-1 text-primary focus:outline-none"
            >
              <option value="all">All reviews</option>
              <option value="pending">Pending review</option>
              <option value="reviewed_benign">Verified (Benign)</option>
              <option value="confirmed_cheating">Cheating confirmed</option>
            </select>
          </div>

          {/* Risk Tier Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-secondary font-medium">Risk tier:</span>
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="bg-surface-container-low border border-outline-variant/60 rounded-lg px-2.5 py-1 text-primary focus:outline-none"
            >
              <option value="all">All tiers</option>
              <option value="safe">Safe (≥ 80)</option>
              <option value="moderate">Moderate (50–79)</option>
              <option value="critical">Critical (&lt; 50)</option>
            </select>
          </div>

          {/* Sort By */}
          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-secondary font-medium">Sort by:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-surface-container-low border border-outline-variant/60 rounded-lg px-2.5 py-1 text-primary focus:outline-none"
            >
              <option value="trust_asc">Lowest trust first</option>
              <option value="trust_desc">Highest trust first</option>
              <option value="viols_desc">Most violations</option>
              <option value="started_desc">Recently started</option>
              <option value="name_asc">Candidate name</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content Area: Grid View vs Table View */}
      {isLoading && sessionList.length === 0 ? (
        <div className="text-center py-24 text-on-surface-variant flex flex-col items-center gap-3">
          <span className="animate-spin">
            <Icon name="progress_activity" size={28} />
          </span>
          <p className="text-xs text-secondary">Loading candidate sessions...</p>
        </div>
      ) : filteredSessions.length === 0 ? (
        <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-xl text-center py-16 px-6 shadow-terminal flex flex-col items-center">
          <div className="w-12 h-12 rounded-lg bg-surface-container flex items-center justify-center text-secondary mb-3 border border-outline-variant">
            <Icon name="group" size={24} />
          </div>
          <div className="text-xs text-secondary mb-1">
            No matching sessions found
          </div>
          <h3 className="text-base font-bold text-primary mb-1">No Matching Candidate Sessions</h3>
          <p className="text-xs text-secondary max-w-md mx-auto">
            Try adjusting your search query, status filters, or risk tier options.
          </p>
        </div>
      ) : viewMode === 'grid' ? (
        /* LIVE MONITORING GRID VIEW */
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filteredSessions.map((sess) => {
            const trustScore = sess.trust_score !== undefined ? sess.trust_score : 100.0;
            const isLive = sess.status === 'in_progress';
            return (
              <Card
                key={sess.session_id}
                variant="terminal"
                rounded="xl"
                hoverable
                className="p-5 flex flex-col justify-between space-y-4 border border-outline-variant/70 bg-surface-container-lowest transition-all hover:border-outline"
              >
                {/* Card Header */}
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        {isLive && <span className="telemetry-beacon shrink-0" />}
                        <h3 className="text-sm font-bold text-primary truncate">
                          {sess.candidate_name}
                        </h3>
                      </div>
                      <p className="text-xs text-secondary truncate">
                        {sess.candidate_email}
                      </p>
                    </div>
                    {getSessionStatusBadge(sess.status)}
                  </div>

                  {/* Thumbnail / Webcam Evidence Snapshot */}
                  <div className="relative rounded-lg overflow-hidden border border-outline-variant/50 bg-black aspect-video flex items-center justify-center group">
                    {sess.latest_snapshot_url ? (
                      <>
                        <img
                          src={
                            sess.latest_snapshot_url.startsWith('http') || sess.latest_snapshot_url.startsWith('blob:')
                              ? sess.latest_snapshot_url
                              : `${window.location.origin}${sess.latest_snapshot_url}`
                          }
                          alt="Live Candidate Snapshot"
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            // Fallback if image fails to render
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                        <button
                          onClick={() => handleViewEvidence(sess.latest_snapshot_url!, 'snapshot', sess.started_at)}
                          className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-1.5 text-white text-xs font-medium transition-opacity"
                        >
                          <Icon name="zoom_in" size={16} />
                          View Evidence
                        </button>
                      </>
                    ) : (
                      <div className="flex flex-col items-center gap-1.5 text-secondary text-xs">
                        <Icon name="videocam_off" size={20} />
                        <span>No snapshot available</span>
                      </div>
                    )}

                    {/* Live overlay tag */}
                    {isLive && (
                      <span className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/80 text-xs font-medium text-amber-400 border border-amber-500/40">
                        Live feed
                      </span>
                    )}
                  </div>
                </div>

                {/* Trust Score & Integrity Gauge */}
                <div className="p-3 rounded-lg bg-surface-container-low/50 border border-outline-variant/50 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-secondary font-medium">Trust score</span>
                    {getTrustBadge(trustScore)}
                  </div>

                  {/* Progress Bar Meter */}
                  <div className="w-full h-1.5 rounded-full bg-surface-container overflow-hidden border border-outline-variant/40">
                    <div
                      className={`h-full transition-all duration-300 ${
                        trustScore >= 80.0
                          ? 'bg-emerald-400'
                          : trustScore >= 50.0
                          ? 'bg-amber-400'
                          : 'bg-rose-500'
                      }`}
                      style={{ width: `${Math.min(100, Math.max(0, trustScore))}%` }}
                    />
                  </div>

                  {/* Telemetry Counter Chips */}
                  <div className="grid grid-cols-3 gap-2 pt-1 text-xs text-secondary">
                    <div className="flex flex-col">
                      <span className="text-[11px] font-medium text-secondary">Violations</span>
                      <span
                        className={`tabular-nums font-mono font-bold text-xs ${
                          (sess.violation_count || 0) > 0 ? 'text-rose-700' : 'text-primary'
                        }`}
                      >
                        {sess.violation_count || 0} logged
                      </span>
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[11px] font-medium text-secondary">Fullscreen</span>
                      <span
                        className={`tabular-nums font-mono font-bold text-xs ${
                          (sess.fullscreen_exit_count || 0) > 0 ? 'text-amber-800' : 'text-primary'
                        }`}
                      >
                        {sess.fullscreen_exit_count || 0} exits
                      </span>
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[11px] font-medium text-secondary">Tab away</span>
                      <span
                        className={`tabular-nums font-mono font-bold text-xs ${
                          (sess.total_tab_away_seconds || 0) > 0 ? 'text-amber-800' : 'text-primary'
                        }`}
                      >
                        {sess.total_tab_away_seconds || 0}s
                      </span>
                    </div>
                  </div>
                </div>

                {/* Card Footer: Review status and Action */}
                <div className="pt-2 border-t border-outline-variant/40 flex items-center justify-between gap-3">
                  <div className="flex flex-col">
                    <span className="text-xs text-secondary font-medium mb-1">Review status</span>
                    {getReviewStatusBadge(sess.review_status)}
                  </div>

                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleOpenReview(sess)}
                    icon="timeline"
                    className="text-xs font-medium"
                  >
                    Review Timeline
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        /* AUDIT LEDGER TABLE VIEW */
        <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-xl overflow-hidden shadow-terminal">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/70 text-xs font-medium text-secondary">
                  <th className="py-3 px-5">Candidate</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Trust Score</th>
                  <th className="py-3 px-4">Proctoring Log</th>
                  <th className="py-3 px-4">Review Status</th>
                  <th className="py-3 px-4 text-right">Score</th>
                  <th className="py-3 px-5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/40">
                {filteredSessions.map((sess) => (
                  <tr key={sess.session_id} className="hover:bg-surface-container-low/40 transition-colors">
                    <td className="py-3.5 px-5">
                      <div className="font-semibold text-primary">{sess.candidate_name}</div>
                      <div className="text-xs text-secondary">{sess.candidate_email}</div>
                    </td>
                    <td className="py-3.5 px-4">{getSessionStatusBadge(sess.status)}</td>
                    <td className="py-3.5 px-4">{getTrustBadge(sess.trust_score)}</td>
                    <td className="py-3.5 px-4 text-xs">
                      <div className="flex items-center gap-3">
                        <span
                          className={`tabular-nums font-mono ${
                            (sess.violation_count || 0) > 0 ? 'text-rose-700 font-bold' : 'text-secondary'
                          }`}
                        >
                          {sess.violation_count || 0} viols
                        </span>
                        <span
                          className={`tabular-nums font-mono ${
                            (sess.fullscreen_exit_count || 0) > 0 ? 'text-amber-800 font-bold' : 'text-secondary'
                          }`}
                        >
                          {sess.fullscreen_exit_count || 0} exits
                        </span>
                        <span
                          className={`tabular-nums font-mono ${
                            (sess.total_tab_away_seconds || 0) > 0 ? 'text-amber-800 font-bold' : 'text-secondary'
                          }`}
                        >
                          {sess.total_tab_away_seconds || 0}s away
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">{getReviewStatusBadge(sess.review_status)}</td>
                    <td className="py-3.5 px-4 text-right font-mono tabular-nums text-xs font-bold text-primary">
                      {sess.score !== null && sess.score !== undefined ? (
                        <span>{Number(sess.score).toFixed(1)} pts</span>
                      ) : (
                        <span className="text-secondary font-normal">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-5 text-right">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleOpenReview(sess)}
                        icon="timeline"
                        className="text-xs font-medium"
                      >
                        Review
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div className="p-3.5 bg-surface-container-low border-t border-outline-variant/70 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs text-secondary">
            <span>
              Showing <span className="text-primary font-bold">{filteredSessions.length}</span> of{' '}
              <span className="text-primary font-bold">{totalSessionsCount}</span> candidate sessions
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || isLoading}
                icon="chevron_left"
                className="text-xs font-medium"
              >
                Previous
              </Button>
              <span className="px-2 py-0.5 text-secondary">
                Page <span className="text-primary font-bold">{page}</span> of {Math.max(1, totalPages)}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || isLoading}
                icon="chevron_right"
                iconPosition="right"
                className="text-xs font-medium"
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================================== */}
      {/* PER-CANDIDATE TIMELINE & FORENSIC REVIEW WORKSPACE MODAL                        */}
      {/* ============================================================================== */}
      {reviewSession && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="max-w-4xl w-full max-h-[90vh] flex flex-col border border-outline-variant/70 bg-surface-container-lowest rounded-xl shadow-terminal overflow-hidden">
            {/* Modal Header */}
            <div className="p-5 border-b border-outline-variant/60 flex items-start justify-between bg-surface-container-low/40">
              <div className="space-y-1">
                <div className="flex items-center gap-2.5">
                  <span className="telemetry-beacon shrink-0" />
                  <span className="text-xs font-semibold text-secondary">
                    Candidate session & incident review
                  </span>
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h2 className="text-lg font-bold text-primary">
                    {reviewSession.candidate_name}
                  </h2>
                  <span className="text-xs text-secondary">
                    {reviewSession.candidate_email}
                  </span>
                  {getSessionStatusBadge(reviewSession.status)}
                </div>
                <div className="flex items-center gap-3 pt-1 text-xs text-secondary">
                  <span>
                    Session ID: <span className="text-primary font-semibold font-mono">{reviewSession.session_id.slice(0, 8)}</span>
                  </span>
                  <span>•</span>
                  <span>
                    Trust score:{' '}
                    <span className="text-primary font-bold font-mono tabular-nums">
                      {(reviewSession.trust_score !== undefined ? reviewSession.trust_score : 100.0).toFixed(1)} / 100
                    </span>
                  </span>
                  <span>•</span>
                  <span>
                    Review decision: {getReviewStatusBadge(reviewSession.review_status)}
                  </span>
                </div>
              </div>

              <button
                onClick={() => setReviewSession(null)}
                className="w-8 h-8 rounded-lg border border-outline-variant/60 flex items-center justify-center text-secondary hover:text-primary hover:bg-surface-container transition-all"
              >
                <Icon name="close" size={16} />
              </button>
            </div>

            {/* Modal Body: Integrated Vertical Chronological Timeline */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {reviewSuccessMsg && (
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-300 text-emerald-950 text-xs font-medium flex items-center gap-2">
                  <Icon name="check_circle" size={16} className="text-emerald-700" />
                  <span>{reviewSuccessMsg}</span>
                </div>
              )}

              {timelineError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-300 text-rose-950 text-xs font-medium flex items-center gap-2">
                  <Icon name="error" size={16} className="text-rose-700" />
                  <span>Error loading timeline: {timelineError}</span>
                </div>
              )}

              <div className="flex items-center justify-between pb-2 border-b border-outline-variant/40 text-xs">
                <span className="text-secondary text-xs font-medium">
                  Activity stream ({timelineItems.length} events)
                </span>
                <span className="text-secondary text-xs">
                  Correlated proctoring anomalies and submissions
                </span>
              </div>

              {isLoadingTimeline ? (
                <div className="text-center py-16 text-on-surface-variant flex flex-col items-center gap-2">
                  <span className="animate-spin">
                    <Icon name="progress_activity" size={24} />
                  </span>
                  <span className="text-xs text-secondary">Loading incident timeline...</span>
                </div>
              ) : timelineItems.length === 0 ? (
                <div className="text-center py-16 flex flex-col items-center text-on-surface-variant">
                  <div className="w-12 h-12 rounded-lg bg-surface-container text-primary border border-outline-variant flex items-center justify-center mb-3">
                    <Icon name="verified_user" size={24} />
                  </div>
                  <h4 className="text-sm font-bold text-primary">No violations recorded</h4>
                  <p className="text-xs text-secondary max-w-sm mt-1">
                    No violations or answer submissions recorded during this session window.
                  </p>
                </div>
              ) : (
                /* Vertical Timeline Items with Dot Markers */
                <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-outline-variant/60">
                  {timelineItems.map((item) => {
                    const isViolation = item.event_type === 'violation';
                    const isBenign = item.review_status === 'reviewed_benign';
                    const isCheating = item.review_status === 'confirmed_cheating';

                    return (
                      <div key={item.id} className="relative group">
                        {/* Dot marker */}
                        <div
                          className={`absolute -left-6 top-1 w-3 h-3 rounded-full border-2 bg-surface-container-lowest transition-all ${
                            isViolation
                              ? item.severity === 'critical'
                                ? 'border-rose-600 bg-rose-600 ring-4 ring-rose-100'
                                : item.severity === 'high'
                                ? 'border-amber-600 bg-amber-600'
                                : 'border-zinc-400 bg-zinc-300'
                              : 'border-primary bg-primary'
                          }`}
                        />

                        {/* Event Card */}
                        <div
                          className={`p-4 rounded-xl border transition-all ${
                            isViolation
                              ? isBenign
                                ? 'border-emerald-300 bg-emerald-50/70 shadow-xs'
                                : isCheating
                                ? 'border-rose-300 bg-rose-50/70 shadow-xs'
                                : 'border-outline-variant/60 bg-surface-container-low/40'
                              : 'border-outline-variant/40 bg-surface-container-lowest'
                          }`}
                        >
                          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2 pb-2">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span
                                className={`text-xs font-bold ${
                                  isViolation
                                    ? isCheating
                                      ? 'text-rose-950'
                                      : isBenign
                                      ? 'text-emerald-950'
                                      : item.severity === 'critical'
                                      ? 'text-rose-900'
                                      : 'text-zinc-900'
                                    : 'text-zinc-900'
                                }`}
                              >
                                {formatEventTitle(item.title)}
                              </span>

                              {isViolation && (
                                <Badge
                                  variant={
                                    item.severity === 'critical'
                                      ? 'critical'
                                      : item.severity === 'high'
                                      ? 'warning'
                                      : 'outline'
                                  }
                                  size="xs"
                                  className="text-[11px] capitalize font-medium"
                                >
                                  {item.severity}
                                </Badge>
                              )}

                              {isViolation && isBenign && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-700 text-white shadow-xs">
                                  <Icon name="check_circle" size={12} />
                                  Dismissed as false positive (0 penalty)
                                </span>
                              )}

                              {isViolation && isCheating && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-700 text-white shadow-xs">
                                  <Icon name="gpp_bad" size={12} />
                                  Confirmed violation
                                </span>
                              )}
                            </div>

                            <span className="font-mono text-xs text-secondary tabular-nums">
                              {new Date(item.timestamp).toLocaleTimeString([], {
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                                hour12: false,
                              })}
                            </span>
                          </div>

                          {/* Event Details Content */}
                          {isViolation ? (
                            <div className="space-y-3 pt-1">
                              {/* Metadata chips */}
                              {item.details && Object.keys(item.details).length > 0 && (
                                <div className="p-2.5 rounded-lg bg-zinc-100/90 text-xs border border-zinc-200/80 flex flex-wrap gap-x-4 gap-y-1">
                                  {Object.entries(item.details).map(([k, val]) => (
                                    <span key={k}>
                                      <span className="text-zinc-900 font-semibold">{k}:</span>{' '}
                                      <span className="font-mono tabular-nums text-zinc-800">{typeof val === 'object' ? JSON.stringify(val) : String(val)}</span>
                                    </span>
                                  ))}
                                </div>
                              )}

                              {/* Forensic Evidence & Human Actions */}
                              <div className="flex items-center justify-between gap-3 pt-1 flex-wrap">
                                {item.evidence_url ? (
                                  <Button
                                    variant="secondary"
                                    size="sm"
                                    onClick={() =>
                                      handleViewEvidence(item.evidence_url!, item.title, item.timestamp)
                                    }
                                    isLoading={loadingEvidenceId === item.evidence_url}
                                    icon={item.title.toLowerCase().includes('audio') ? 'audiotrack' : 'photo'}
                                    className="text-xs font-medium"
                                  >
                                    {item.title.toLowerCase().includes('audio')
                                      ? 'Play audio clip'
                                      : 'View snapshot'}
                                  </Button>
                                ) : (
                                  <span className="text-xs text-secondary">
                                    No media evidence attached
                                  </span>
                                )}

                                {/* Individual Verdict Buttons */}
                                <div className="flex items-center gap-2 ml-auto">
                                  <button
                                    onClick={() =>
                                      handleReviewIndividualViolation(
                                        item.id,
                                        isBenign ? 'unreviewed' : 'reviewed_benign'
                                      )
                                    }
                                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all border ${
                                      isBenign
                                        ? 'bg-emerald-700 text-white border-emerald-800 shadow-xs'
                                        : 'bg-white text-emerald-900 border-emerald-300 hover:bg-emerald-50'
                                    }`}
                                    title="Marking benign removes trust score penalty immediately"
                                  >
                                    {isBenign ? '✓ Benign' : 'Mark as benign'}
                                  </button>

                                  <button
                                    onClick={() =>
                                      handleReviewIndividualViolation(
                                        item.id,
                                        isCheating ? 'unreviewed' : 'confirmed_cheating'
                                      )
                                    }
                                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all border ${
                                      isCheating
                                        ? 'bg-rose-700 text-white border-rose-800 shadow-xs'
                                        : 'bg-white text-rose-900 border-rose-300 hover:bg-rose-50'
                                    }`}
                                  >
                                    {isCheating ? '✖ Cheating' : 'Confirm cheating'}
                                  </button>
                                </div>
                              </div>
                            </div>
                          ) : (
                            /* Candidate Submission Item */
                            <div className="space-y-2 pt-1">
                              <p className="text-xs text-primary font-medium">
                                {item.details?.question_text || 'Assessment Question'}
                              </p>
                              <div className="p-2.5 rounded bg-surface-container text-xs text-secondary border border-outline-variant/40 space-y-1">
                                <div>
                                  <span className="text-primary font-medium">Candidate response:</span>{' '}
                                  <span className="text-primary font-mono">
                                    {typeof item.details?.answer === 'object'
                                      ? JSON.stringify(item.details.answer)
                                      : String(item.details?.answer ?? '—')}
                                  </span>
                                </div>
                                <div className="flex items-center gap-3 text-xs">
                                  <span>
                                    Score awarded:{' '}
                                    <span className="text-primary font-bold font-mono tabular-nums">
                                      {item.details?.points_awarded ?? 0} / {item.details?.points_possible ?? 0} pts
                                    </span>
                                  </span>
                                  {item.details?.is_correct !== undefined && (
                                    <span
                                      className={`font-semibold ${
                                        item.details.is_correct ? 'text-emerald-800' : 'text-rose-800'
                                      }`}
                                    >
                                      {item.details.is_correct ? '● Correct' : '○ Incorrect'}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Modal Footer: Session-level Verdict & Review Notes Action Bar */}
            <div className="p-5 border-t border-outline-variant/60 bg-surface-container-low/40 space-y-3">
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                <input
                  type="text"
                  value={sessionReviewNotes}
                  onChange={(e) => setSessionReviewNotes(e.target.value)}
                  placeholder="Official proctor audit notes (e.g. 'False alarm due to external lighting flicker')..."
                  className="flex-1 px-3 py-2 text-xs bg-surface-container-lowest border border-outline-variant/60 rounded-lg text-primary placeholder-secondary focus:outline-none focus:border-primary"
                />

                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleSubmitSessionReview('reviewed_benign')}
                    isLoading={isSubmittingReview}
                    icon="check_circle"
                    className="text-xs font-semibold bg-emerald-50 text-emerald-900 border border-emerald-300 hover:bg-emerald-100"
                  >
                    Verify as benign
                  </Button>

                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleSubmitSessionReview('confirmed_cheating')}
                    isLoading={isSubmittingReview}
                    icon="gpp_bad"
                    className="text-xs font-semibold bg-rose-50 text-rose-900 border border-rose-300 hover:bg-rose-100"
                  >
                    Confirm cheating
                  </Button>

                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setReviewSession(null)}
                    className="text-xs font-medium"
                  >
                    Close
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================================== */}
      {/* BULK APPROVAL SAFETY MODAL                                                     */}
      {/* ============================================================================== */}
      {isBulkModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="max-w-lg w-full border border-outline-variant/70 bg-surface-container-lowest rounded-xl shadow-terminal p-6 space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
              <div className="flex items-center gap-2">
                <Icon name="rule" size={20} className="text-emerald-700" />
                <h3 className="text-base font-bold text-primary">Bulk approval guardrail</h3>
              </div>
              <button
                onClick={() => setIsBulkModalOpen(false)}
                className="w-7 h-7 rounded-lg border border-outline-variant/60 flex items-center justify-center text-secondary hover:text-primary hover:bg-surface-container transition-all"
              >
                <Icon name="close" size={16} />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <p className="text-secondary leading-relaxed">
                Automatically verify and approve candidate sessions whose aggregate integrity trust score meets or exceeds the strict safety threshold.
              </p>

              {/* Threshold Slider / Input */}
              <div className="p-3.5 rounded-lg bg-surface-container-low border border-outline-variant/50 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-secondary text-xs">Minimum trust score threshold:</span>
                  <span className="text-primary font-bold text-sm font-mono tabular-nums">
                    {bulkMinTrust.toFixed(1)} / 100
                  </span>
                </div>
                <input
                  type="range"
                  min="80"
                  max="95"
                  step="1"
                  value={bulkMinTrust}
                  onChange={(e) => setBulkMinTrust(Number(e.target.value))}
                  className="w-full accent-primary cursor-pointer"
                />
                <div className="flex justify-between text-[11px] text-secondary">
                  <span>80.0 (Standard safe)</span>
                  <span>85.0 (Recommended guardrail)</span>
                  <span>95.0 (High strictness)</span>
                </div>
              </div>

              {/* Summary Stats */}
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-300 flex items-center justify-between">
                <span className="text-emerald-950 font-semibold">Qualifying sessions:</span>
                <span className="font-bold text-base text-emerald-900 font-mono tabular-nums">
                  {bulkQualifyingCount} of {sessionList.length}
                </span>
              </div>

              {/* Guardrail Policy Disclaimer */}
              <div className="p-2.5 rounded bg-surface-container border border-outline-variant/40 text-xs text-secondary flex items-start gap-2">
                <Icon name="security" size={14} className="text-secondary shrink-0 mt-0.5" />
                <span>
                  Safety policy: Any session with critical severity infractions (e.g. face mismatch) is strictly blocked by the backend safety engine and requires manual review.
                </span>
              </div>

              {bulkResult && (
                <div className="p-3 rounded bg-emerald-50 border border-emerald-300 space-y-1">
                  <div className="text-emerald-950 font-bold">
                    ✓ Bulk approval complete: {bulkResult.approved_count} sessions verified.
                  </div>
                  {bulkResult.rejected_count > 0 && (
                    <div className="text-zinc-700 text-xs">
                      {bulkResult.rejected_count} sessions withheld due to safety threshold or critical alerts.
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-outline-variant/60">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsBulkModalOpen(false)}
                className="text-xs font-medium"
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleExecuteBulkApprove}
                disabled={bulkQualifyingCount === 0 || isSubmittingBulk}
                isLoading={isSubmittingBulk}
                className="text-xs font-medium"
              >
                Approve {bulkQualifyingCount} sessions
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================================== */}
      {/* EVIDENCE VIEWER MODAL: SECURE DARKROOM CONTAINER                               */}
      {/* ============================================================================== */}
      {selectedEvidence && (
        <div className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-[60] p-4">
          <div className="max-w-xl w-full border border-outline-variant/70 bg-surface-container-lowest rounded-xl shadow-terminal p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
              <div className="flex items-center gap-2">
                <Icon
                  name={selectedEvidence.type === 'audio' ? 'audiotrack' : 'photo'}
                  size={18}
                  className="text-primary"
                />
                <div>
                  <h4 className="text-sm font-bold text-primary">{selectedEvidence.title}</h4>
                  <span className="text-xs text-secondary">
                    Capture ID: <span className="font-mono">{selectedEvidence.url.slice(-12)}</span>
                  </span>
                </div>
              </div>
              <button
                onClick={handleCloseEvidence}
                className="w-7 h-7 rounded-lg border border-outline-variant/60 flex items-center justify-center text-secondary hover:text-primary hover:bg-surface-container transition-all"
              >
                <Icon name="close" size={16} />
              </button>
            </div>

            {selectedEvidence.timestamp && (
              <p className="text-xs text-secondary">
                Recorded at: <span className="font-mono tabular-nums">{new Date(selectedEvidence.timestamp).toLocaleString([], { hour12: false })}</span>
              </p>
            )}

            {/* Media Content */}
            {selectedEvidence.type === 'image' ? (
              <div className="rounded-lg overflow-hidden border border-outline-variant/60 bg-black aspect-video flex items-center justify-center">
                <img
                  src={selectedEvidence.blobUrl}
                  alt="Proctoring Evidence"
                  className="w-full h-full object-contain"
                />
              </div>
            ) : (
              <div className="p-4 rounded-lg bg-surface-container border border-outline-variant/60 space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-primary">
                  <Icon name="volume_up" size={15} />
                  <span>3-second voice recording (audio clip)</span>
                </div>
                <audio controls autoPlay src={selectedEvidence.blobUrl} className="w-full" />
              </div>
            )}

            <div className="p-2.5 rounded-lg bg-surface-container text-xs text-secondary flex items-center gap-2 border border-outline-variant/50">
              <Icon name="lock" size={13} className="text-secondary shrink-0" />
              <span>Restricted forensic evidence — subject to academic compliance retention policy.</span>
            </div>

            <div className="flex justify-end pt-2">
              <Button variant="primary" size="sm" onClick={handleCloseEvidence} className="text-xs font-medium">
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
