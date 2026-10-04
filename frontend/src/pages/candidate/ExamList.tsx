import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { CandidateAvailableExam } from '../../types';
import { Button, Card, Badge, Icon, Alert } from '../../components/ui';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

export const ExamList: React.FC = () => {
  useDocumentTitle('Available Assessments', 'Browse and launch scheduled proctored assessments.');
  const navigate = useNavigate();
  const [exams, setExams] = useState<CandidateAvailableExam[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchExams = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<CandidateAvailableExam[]>('/candidate/exams');
      setExams(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load available examinations.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchExams();
  }, []);

  const handleStartExam = (exam: CandidateAvailableExam) => {
    if (exam.enable_browser_proctoring && !exam.session_id) {
      navigate(`/exams/${exam.id}/check`);
    } else {
      navigate(`/exams/${exam.id}/take`);
    }
  };

  const handleViewResult = (examId: string) => {
    navigate(`/exams/${examId}/result`);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 pb-2">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-primary">
            Available Examinations
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            Active and published assessments eligible for your candidate account.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={fetchExams}
          disabled={isLoading}
          icon="refresh"
        >
          Refresh List
        </Button>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {isLoading ? (
        <div className="text-center py-16 text-on-surface-variant flex flex-col items-center gap-3">
          <span className="animate-spin">
            <Icon name="progress_activity" size={32} />
          </span>
          <p className="text-sm">Loading examinations...</p>
        </div>
      ) : exams.length === 0 ? (
        <Card variant="default" className="text-center py-16 px-6 max-w-lg mx-auto">
          <div className="w-14 h-14 rounded-3xl bg-surface-container-high text-secondary flex items-center justify-center mx-auto mb-4">
            <Icon name="event_available" size={28} />
          </div>
          <h3 className="text-base font-semibold text-primary mb-1.5">No Active Assessments Available</h3>
          <p className="text-xs text-on-surface-variant max-w-sm mx-auto leading-relaxed mb-5">
            You do not currently have any scheduled or published examinations. New assessments will appear here automatically once made live by your proctor or instructor.
          </p>
          <Button variant="secondary" size="sm" onClick={fetchExams} icon="refresh">
            Check for Updates
          </Button>
        </Card>
      ) : (
        <div className="space-y-3">
          {exams.map((exam) => {
            const isCompleted =
              exam.session_status === 'submitted' ||
              exam.session_status === 'timed_out' ||
              exam.session_status === 'terminated';
            const inProgress = exam.session_status === 'in_progress';
            const hasSubmitted =
              isCompleted && exam.session_score !== undefined && exam.session_score !== null;

            return (
              <div
                key={exam.id}
                className="border border-outline-variant/70 hover:border-outline bg-surface-container-lowest rounded-xl p-5 transition-all shadow-subtle hover:shadow-terminal flex flex-col lg:flex-row lg:items-center justify-between gap-5"
              >
                {/* Left: Exam Details & Status Tags */}
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span className="text-xs font-mono text-secondary">
                      ID: {exam.id.substring(0, 8)}
                    </span>

                    {exam.enable_browser_proctoring ? (
                      <span className="inline-flex items-center gap-1.5 text-xs text-secondary font-medium">
                        <span className="telemetry-beacon shrink-0" />
                        Proctored
                      </span>
                    ) : (
                      <span className="text-xs text-secondary font-medium">
                        Standard
                      </span>
                    )}

                    {isCompleted ? (
                      <Badge
                        variant={exam.session_status === 'terminated' ? 'error' : 'neutral'}
                        size="xs"
                        rounded="md"
                        icon={exam.session_status === 'terminated' ? 'block' : 'check'}
                      >
                        {exam.session_status === 'terminated' ? 'Terminated' : 'Completed'}
                      </Badge>
                    ) : inProgress ? (
                      <Badge variant="success" size="xs" rounded="md" icon="pending">
                        In Progress
                      </Badge>
                    ) : (
                      <Badge variant="outline" size="xs" rounded="md" icon="schedule">
                        Available
                      </Badge>
                    )}
                  </div>

                  <h3 className="text-base md:text-lg font-semibold text-primary tracking-tight truncate">
                    {exam.title}
                  </h3>

                  <p className="text-xs text-secondary line-clamp-1 max-w-2xl">
                    {exam.description || 'Assessment session.'}
                  </p>
                </div>

                {/* Middle: Tabular Specifications */}
                <div className="flex items-center gap-6 text-xs text-on-surface-variant shrink-0 py-2 lg:py-0 border-y lg:border-y-0 lg:border-x border-outline-variant/40 lg:px-6">
                  <div>
                    <div className="text-xs text-secondary font-medium mb-0.5">
                      Duration
                    </div>
                    <div className="tabular-nums font-medium text-primary">
                      {exam.duration_minutes} mins
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-secondary font-medium mb-0.5">
                      Points
                    </div>
                    <div className="tabular-nums font-medium text-primary">
                      {exam.total_points || 100} pts
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-secondary font-medium mb-0.5">
                      Deadline
                    </div>
                    <div className="tabular-nums font-medium text-primary">
                      {new Date(exam.end_time).toLocaleDateString()}
                    </div>
                  </div>
                </div>

                {/* Right: Actions & Score */}
                <div className="shrink-0 flex items-center justify-between lg:justify-end gap-3 min-w-[170px]">
                  {hasSubmitted ? (
                    <div className="flex items-center gap-3 w-full lg:w-auto justify-between">
                      <div className="text-right">
                        <div className="text-xs text-secondary font-medium">
                          Score
                        </div>
                        <div className="tabular-nums text-sm font-semibold text-success font-mono">
                          {exam.session_score} / {exam.total_points}
                        </div>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleViewResult(exam.id)}
                        icon="bar_chart"
                      >
                        View results
                      </Button>
                    </div>
                  ) : inProgress ? (
                    <Button
                      variant="primary"
                      size="sm"
                      className="w-full lg:w-auto shadow-subtle text-xs font-medium"
                      onClick={() => handleStartExam(exam)}
                      icon="play_arrow"
                    >
                      Resume exam
                    </Button>
                  ) : (
                    <Button
                      variant="primary"
                      size="sm"
                      className="w-full lg:w-auto shadow-subtle text-xs font-medium"
                      onClick={() => handleStartExam(exam)}
                      disabled={!exam.is_window_open}
                      icon="play_arrow"
                    >
                      {exam.is_window_open
                        ? exam.enable_browser_proctoring
                          ? 'Start pre-check'
                          : 'Start exam'
                        : 'Window closed'}
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
