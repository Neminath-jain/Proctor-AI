import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { Exam } from '../../types';
import { Button, Badge, Icon, Alert } from '../../components/ui';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

export const AdminExamList: React.FC = () => {
  useDocumentTitle('Manage Assessments — Admin', 'Create and oversee examination configurations.');
  const navigate = useNavigate();
  const [exams, setExams] = useState<Exam[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchExams = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<Exam[]>('/admin/exams');
      setExams(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load exams.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchExams();
  }, []);

  const handleDelete = async (id: string, title: string) => {
    if (!window.confirm(`Are you sure you want to delete exam "${title}"? This cannot be undone.`)) {
      return;
    }
    try {
      await apiClient.delete(`/admin/exams/${id}`);
      setExams((prev) => prev.filter((e) => e.id !== id));
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete exam.');
    }
  };

  const publishedCount = exams.filter((e) => e.status === 'published').length;
  const draftCount = exams.filter((e) => e.status === 'draft').length;
  const totalQuestions = exams.reduce((acc, e) => acc + (e.question_count || 0), 0);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'published':
        return (
          <Badge variant="success" size="xs">
            Published
          </Badge>
        );
      case 'draft':
        return (
          <Badge variant="warning" size="xs">
            Draft
          </Badge>
        );
      case 'archived':
        return (
          <Badge variant="neutral" size="xs">
            Archived
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" size="xs" className="font-medium capitalize">
            {status}
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Quick Action Bar */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 shadow-subtle">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-6 border-b border-outline-variant/60">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="telemetry-beacon shrink-0" />
              <span className="text-xs font-medium text-secondary">
                Exam management
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-semibold tracking-tight text-primary">
              Assessment Management
            </h1>
            <p className="text-xs text-secondary mt-1">
              Create, configure question banks, and manage active proctored examinations.
            </p>
          </div>

          <Link to="/admin/exams/create">
            <Button variant="primary" size="sm" icon="add" id="create-exam-btn" className="text-xs font-medium shadow-subtle">
              Create exam
            </Button>
          </Link>
        </div>

        {/* Summary Metric Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-6">
          <div className="border-r border-outline-variant/40 pr-4">
            <div className="text-xs text-secondary font-medium">
              Total exams
            </div>
            <div className="tabular-nums text-2xl font-bold text-primary mt-1 font-mono">
              {exams.length}
            </div>
          </div>

          <div className="border-r border-outline-variant/40 pr-4">
            <div className="text-xs text-secondary font-medium">
              Published
            </div>
            <div className="tabular-nums text-2xl font-bold text-primary mt-1 font-mono">
              {publishedCount}
            </div>
          </div>

          <div className="border-r border-outline-variant/40 pr-4">
            <div className="text-xs text-secondary font-medium">
              Drafts
            </div>
            <div className="tabular-nums text-2xl font-bold text-primary mt-1 font-mono">
              {draftCount}
            </div>
          </div>

          <div>
            <div className="text-xs text-secondary font-medium">
              Questions
            </div>
            <div className="tabular-nums text-2xl font-bold text-primary mt-1 font-mono">
              {totalQuestions}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          Error loading assessments: {error}
        </Alert>
      )}

      {isLoading ? (
        <div className="text-center py-20 text-on-surface-variant flex flex-col items-center gap-3">
          <span className="animate-spin">
            <Icon name="progress_activity" size={28} />
          </span>
          <p className="text-xs text-secondary">Loading examinations...</p>
        </div>
      ) : exams.length === 0 ? (
        <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl text-center py-16 px-6 shadow-subtle flex flex-col items-center">
          <div className="w-12 h-12 rounded-xl bg-surface-container flex items-center justify-center text-secondary mb-3 border border-outline-variant/60">
            <Icon name="post_add" size={24} />
          </div>
          <div className="text-xs text-secondary mb-1">
            No exams found
          </div>
          <h3 className="text-base font-semibold text-primary mb-1">No assessments in registry</h3>
          <p className="text-xs text-secondary max-w-md mx-auto mb-6">
            Create an assessment with multiple-choice and coding questions to begin.
          </p>
          <Link to="/admin/exams/create">
            <Button variant="primary" size="sm" icon="add" className="text-xs font-medium">
              Create your first exam
            </Button>
          </Link>
        </div>
      ) : (
        <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl overflow-hidden shadow-subtle">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/70 text-xs font-medium text-secondary">
                  <th className="py-3 px-5">Assessment</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Questions</th>
                  <th className="py-3 px-4 text-right">Points</th>
                  <th className="py-3 px-4 text-right">Duration</th>
                  <th className="py-3 px-5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/40">
                {exams.map((exam) => (
                  <tr
                    key={exam.id}
                    className="hover:bg-surface-container-low/40 transition-colors"
                  >
                    <td className="py-4 px-5">
                      <div className="flex items-center gap-2.5">
                        <span className="font-mono text-xs text-secondary bg-surface-container px-1.5 py-0.5 rounded border border-outline-variant/50">
                          {exam.id.slice(0, 6)}
                        </span>
                        <Link
                          to={`/admin/exams/${exam.id}/builder`}
                          className="font-medium text-primary hover:underline"
                        >
                          {exam.title}
                        </Link>
                      </div>
                    </td>
                    <td className="py-4 px-4">{getStatusBadge(exam.status)}</td>
                    <td className="py-4 px-4 text-right font-mono tabular-nums text-xs text-primary font-medium">
                      {exam.question_count || 0}
                    </td>
                    <td className="py-4 px-4 text-right font-mono tabular-nums text-xs text-primary font-medium">
                      {Number(exam.total_points || 0).toFixed(1)} pts
                    </td>
                    <td className="py-4 px-4 text-right font-mono tabular-nums text-xs text-secondary">
                      {exam.duration_minutes} mins
                    </td>
                    <td className="py-4 px-5 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => navigate(`/admin/exams/${exam.id}/builder`)}
                          title="Edit Questions & Settings"
                          icon="tune"
                          className="text-xs font-medium"
                        >
                          Edit
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => navigate(`/admin/exams/${exam.id}/sessions`)}
                          title="View Candidate Submissions & Monitoring"
                          icon="analytics"
                          className="text-xs font-medium"
                        >
                          Sessions
                        </Button>
                        <button
                          onClick={() => handleDelete(exam.id, exam.title)}
                          className="w-7 h-7 rounded border border-outline-variant/60 text-secondary hover:text-error hover:border-error/50 hover:bg-error-container/20 flex items-center justify-center transition-all ml-1"
                          title="Delete Assessment"
                        >
                          <Icon name="delete" size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
