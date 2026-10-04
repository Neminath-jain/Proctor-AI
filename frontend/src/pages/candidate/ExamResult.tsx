import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { ExamSubmissionResult } from '../../types';
import { Button, Badge, Icon } from '../../components/ui';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

export const ExamResult: React.FC = () => {
  useDocumentTitle('Assessment Performance Report', 'Review verified candidate score and questions breakdown.');
  const { examId } = useParams<{ examId: string }>();
  const navigate = useNavigate();

  const [result, setResult] = useState<ExamSubmissionResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSessionResult = async () => {
      try {
        const { data: exams } = await apiClient.get<any[]>('/candidate/exams');
        const currentExam = exams.find((e) => e.id === examId);

        if (!currentExam || !currentExam.session_id) {
          setError('No completed examination session found.');
          return;
        }

        const { data: res } = await apiClient.post<ExamSubmissionResult>(
          `/candidate/sessions/${currentExam.session_id}/submit`
        );
        setResult(res);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load score report.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchSessionResult();
  }, [examId]);

  if (isLoading) {
    return (
      <div className="text-center py-24 text-on-surface-variant flex flex-col items-center gap-3">
        <span className="animate-spin">
          <Icon name="progress_activity" size={32} />
        </span>
        <p className="text-xs text-secondary">Loading examination results...</p>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl text-center max-w-md mx-auto my-16 p-8 shadow-subtle">
        <div className="w-10 h-10 rounded-xl bg-surface-container text-secondary border border-outline-variant flex items-center justify-center mx-auto mb-4">
          <Icon name="error_outline" size={20} />
        </div>
        <div className="text-xs text-secondary mb-1">
          Record unavailable
        </div>
        <h2 className="text-lg font-semibold text-primary mb-2">Scorecard Verification Failed</h2>
        <p className="text-xs text-secondary mb-6">{error}</p>
        <Button variant="secondary" size="sm" onClick={() => navigate('/exams')}>
          Return to assessments
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Assessment Performance Transcript Header */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 md:p-8 shadow-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-outline-variant/60">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="telemetry-beacon shrink-0" />
              <span className="text-xs font-medium text-secondary">
                Verified assessment record
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-semibold tracking-tight text-primary">
              Assessment Results
            </h1>
            <p className="text-xs text-secondary mt-1">
              Assessment ID: <span className="text-primary font-mono">{examId?.slice(0, 8) || 'N/A'}</span>
            </p>
          </div>
          <div className="flex sm:flex-col items-start sm:items-end gap-1">
            <span className="inline-flex items-center gap-1.5 text-xs text-primary font-medium bg-surface-container px-2.5 py-1 rounded-lg border border-outline-variant/60">
              <Icon name="verified_user" size={14} className="text-primary" />
              Completed
            </span>
          </div>
        </div>

        {/* Tabular Numerals Metrics Ledger */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-6">
          <div className="border-r border-outline-variant/40 pr-4">
            <div className="text-xs text-secondary font-medium">
              Score awarded
            </div>
            <div className="tabular-nums text-2xl font-bold text-primary mt-1 font-mono">
              {Number(result.score).toFixed(1)}
              <span className="text-xs font-normal text-secondary ml-1 font-sans">/ {Number(result.max_score).toFixed(1)}</span>
            </div>
          </div>

          <div className="border-r border-outline-variant/40 pr-4">
            <div className="text-xs text-secondary font-medium">
              Percentage
            </div>
            <div className="tabular-nums text-2xl font-bold text-primary mt-1 font-mono">
              {Number(result.percentage).toFixed(1)}%
            </div>
          </div>

          <div className="border-r border-outline-variant/40 pr-4">
            <div className="text-xs text-secondary font-medium">
              Questions
            </div>
            <div className="tabular-nums text-2xl font-bold text-primary mt-1 font-mono">
              {result.breakdown.length}
            </div>
          </div>

          <div>
            <div className="text-xs text-secondary font-medium">
              Outcome
            </div>
            <div className="text-base font-semibold text-primary mt-1.5 flex items-center gap-1.5">
              <Icon
                name={result.percentage >= 60 ? 'check_circle' : 'info'}
                size={16}
                className={result.percentage >= 60 ? 'text-success' : 'text-secondary'}
              />
              <span>{result.percentage >= 60 ? 'Passed' : 'Did not pass'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Itemized Question Performance Breakdown */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl overflow-hidden shadow-subtle">
        <div className="px-6 py-4 border-b border-outline-variant/60 flex items-center justify-between bg-surface-container-low/40">
          <div>
            <h3 className="text-xs font-semibold text-primary">
              Question Breakdown
            </h3>
            <span className="text-xs text-secondary">
              Review scored questions and responses
            </span>
          </div>
          <span className="text-xs text-secondary">
            {result.breakdown.length} questions
          </span>
        </div>

        <div className="divide-y divide-outline-variant/40">
          {result.breakdown.map((item, idx) => (
            <div
              key={item.question_id}
              className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-surface-container-low/30 transition-colors"
            >
              <div className="space-y-1.5">
                <div className="flex items-center gap-2.5">
                  <span className="font-mono text-xs font-medium text-primary bg-surface-container px-2 py-0.5 rounded border border-outline-variant/60">
                    Q{String(idx + 1).padStart(2, '0')}
                  </span>
                  <span className="text-xs text-secondary capitalize">
                    {item.type}
                  </span>
                  <Badge
                    variant={
                      item.is_correct
                        ? 'neutral'
                        : item.score_awarded > 0
                        ? 'warning'
                        : 'error'
                    }
                    size="xs"
                    className="capitalize"
                  >
                    {item.is_correct
                      ? 'Full credit'
                      : item.score_awarded > 0
                      ? 'Partial credit'
                      : 'No credit'}
                  </Badge>
                </div>
                <div className="text-xs text-secondary pl-1">
                  {item.feedback || 'Response evaluated.'}
                </div>
              </div>

              <div className="flex sm:flex-col items-baseline sm:items-end justify-between sm:justify-center shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-outline-variant/30">
                <span className="font-mono tabular-nums text-sm font-semibold text-primary">
                  {Number(item.score_awarded).toFixed(1)} / {Number(item.points_possible).toFixed(1)} pts
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Navigation Return Button */}
      <div className="flex justify-between items-center pt-2 pb-8">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate('/exams')}
          icon="arrow_back"
          className="text-xs font-medium"
        >
          Return to assessments
        </Button>
      </div>
    </div>
  );
};
