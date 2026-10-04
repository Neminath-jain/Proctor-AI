import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { ExamDetailResponse, Question, QuestionOption, TestCase } from '../../types';
import { Button, Card, Badge, PillTab, Icon, Alert } from '../../components/ui';

export const AdminExamBuilder: React.FC = () => {
  const { examId } = useParams<{ examId: string }>();
  const navigate = useNavigate();
  const isCreating = !examId;

  // Exam Details State
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [startTime, setStartTime] = useState(new Date().toISOString().slice(0, 16));
  const [endTime, setEndTime] = useState(
    new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 16)
  );
  const [status, setStatus] = useState<'draft' | 'published' | 'archived'>('draft');

  // Proctoring Settings State
  const [enableBrowserProctoring, setEnableBrowserProctoring] = useState(true);
  const [maxFullscreenExits, setMaxFullscreenExits] = useState(2);
  const [fullscreenWarningTimeoutSeconds, setFullscreenWarningTimeoutSeconds] = useState(10);
  const [maxTabAwaySeconds, setMaxTabAwaySeconds] = useState(60);
  const [pasteCharThreshold, setPasteCharThreshold] = useState(50);

  // Phase 4 Video & Audio AI Proctoring Settings
  const [proctorFrameIntervalSeconds, setProctorFrameIntervalSeconds] = useState(10);
  const [faceSimilarityThreshold, setFaceSimilarityThreshold] = useState(0.60);
  const [consecutiveNoFaceLimit, setConsecutiveNoFaceLimit] = useState(3);
  const [sustainedAudioThresholdSeconds, setSustainedAudioThresholdSeconds] = useState(5.0);
  const [audioWindowSeconds, setAudioWindowSeconds] = useState(30);

  // Questions State
  const [questions, setQuestions] = useState<Question[]>([]);
  const [isLoading, setIsLoading] = useState(!isCreating);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New Question Form Modal State
  const [showQuestionModal, setShowQuestionModal] = useState(false);
  const [qType, setQType] = useState<'mcq' | 'coding'>('mcq');
  const [qText, setQText] = useState('');
  const [qPoints, setQPoints] = useState(5.0);
  // MCQ state
  const [mcqOptions, setMcqOptions] = useState<QuestionOption[]>([
    { id: 'opt_1', text: 'Option 1' },
    { id: 'opt_2', text: 'Option 2' },
  ]);
  const [mcqCorrect, setMcqCorrect] = useState<string[]>(['opt_1']);
  const [mcqMulti, setMcqMulti] = useState(false);
  const [mcqPartial, setMcqPartial] = useState(false);
  // Coding state
  const [codeStarter, setCodeStarter] = useState('def solution():\n    pass\n');
  const [codeTestCases, setCodeTestCases] = useState<TestCase[]>([
    { input: '2 3', expected_output: '5', is_hidden: false },
    { input: '10 20', expected_output: '30', is_hidden: true },
  ]);

  useEffect(() => {
    if (!isCreating && examId) {
      const loadExam = async () => {
        setIsLoading(true);
        try {
          const { data } = await apiClient.get<ExamDetailResponse>(`/admin/exams/${examId}`);
          setTitle(data.title);
          setDescription(data.description || '');
          setDurationMinutes(data.duration_minutes);
          setStartTime(new Date(data.start_time).toISOString().slice(0, 16));
          setEndTime(new Date(data.end_time).toISOString().slice(0, 16));
          setStatus(data.status as any);
          setQuestions(data.questions || []);
          setEnableBrowserProctoring(data.enable_browser_proctoring ?? true);
          setMaxFullscreenExits(data.max_fullscreen_exits ?? 2);
          setFullscreenWarningTimeoutSeconds(data.fullscreen_warning_timeout_seconds ?? 10);
          setMaxTabAwaySeconds(data.max_tab_away_seconds ?? 60);
          setPasteCharThreshold(data.paste_char_threshold ?? 50);
          setProctorFrameIntervalSeconds((data as any).proctor_frame_interval_seconds ?? 10);
          setFaceSimilarityThreshold((data as any).face_similarity_threshold ?? 0.60);
          setConsecutiveNoFaceLimit((data as any).consecutive_no_face_limit ?? 3);
          setSustainedAudioThresholdSeconds((data as any).sustained_audio_threshold_seconds ?? 5.0);
          setAudioWindowSeconds((data as any).audio_window_seconds ?? 30);
        } catch (err: any) {
          setError(err.response?.data?.detail || 'Failed to load exam details.');
        } finally {
          setIsLoading(false);
        }
      };
      loadExam();
    }
  }, [examId, isCreating]);

  // Save Exam Metadata
  const handleSaveExam = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);

    // Ensure newly created exams start as draft until questions are added
    const effectiveStatus = isCreating ? 'draft' : status;

    // Validation: prevent publishing if there are no questions
    if (!isCreating && effectiveStatus === 'published' && questions.length === 0) {
      setError('Cannot publish an exam with 0 questions. Add at least one question before publishing.');
      setIsSaving(false);
      return;
    }

    try {
      const payload = {
        title,
        description,
        duration_minutes: Number(durationMinutes),
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        status: effectiveStatus,
        enable_browser_proctoring: enableBrowserProctoring,
        max_fullscreen_exits: Number(maxFullscreenExits),
        fullscreen_warning_timeout_seconds: Number(fullscreenWarningTimeoutSeconds),
        max_tab_away_seconds: Number(maxTabAwaySeconds),
        paste_char_threshold: Number(pasteCharThreshold),
        proctor_frame_interval_seconds: Number(proctorFrameIntervalSeconds),
        face_similarity_threshold: Number(faceSimilarityThreshold),
        consecutive_no_face_limit: Number(consecutiveNoFaceLimit),
        sustained_audio_threshold_seconds: Number(sustainedAudioThresholdSeconds),
        audio_window_seconds: Number(audioWindowSeconds),
      };

      if (isCreating) {
        const { data } = await apiClient.post('/admin/exams', payload);
        navigate(`/admin/exams/${data.id}/builder`, { replace: true });
      } else {
        await apiClient.put(`/admin/exams/${examId}`, payload);
        alert('Exam saved successfully!');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save examination.');
    } finally {
      setIsSaving(false);
    }
  };

  // Add Question Handler
  const handleAddQuestion = async () => {
    if (!examId) {
      alert('Please save the exam first before adding questions.');
      return;
    }
    if (!qText.trim()) {
      alert('Question prompt text cannot be blank.');
      return;
    }

    try {
      let payload: any;
      if (qType === 'mcq') {
        payload = {
          type: 'mcq',
          question_text: qText,
          points: Number(qPoints),
          options: mcqOptions,
          is_multiselect: mcqMulti,
          partial_credit: mcqPartial,
          correct_answer: mcqMulti ? mcqCorrect : mcqCorrect[0] || 'opt_1',
        };
      } else {
        payload = {
          type: 'coding',
          question_text: qText,
          points: Number(qPoints),
          starter_code: { python: codeStarter },
          allowed_languages: ['python', 'javascript'],
          test_cases: codeTestCases,
          time_limit: 3,
          memory_limit: 128000,
        };
      }

      const { data } = await apiClient.post<Question>(`/admin/exams/${examId}/questions`, payload);
      setQuestions((prev) => [...prev, data]);
      setShowQuestionModal(false);

      // Reset question modal fields
      setQText('');
      setQPoints(5.0);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to add question.');
    }
  };

  // Delete Question Handler
  const handleDeleteQuestion = async (questionId: string) => {
    if (!window.confirm('Delete this question from the exam?')) return;
    try {
      await apiClient.delete(`/admin/exams/${examId}/questions/${questionId}`);
      setQuestions((prev) => prev.filter((q) => q.id !== questionId));
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete question.');
    }
  };

  if (isLoading) {
    return (
      <div className="text-center py-24 text-on-surface-variant flex flex-col items-center gap-3">
        <span className="animate-spin">
          <Icon name="progress_activity" size={32} />
        </span>
        <p className="text-sm">Loading assessment settings...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-4 pb-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate('/admin/exams')}
          icon="arrow_back"
        >
          Back to Exams
        </Button>
        <h2 className="text-xl md:text-2xl font-bold tracking-tight text-primary">
          {isCreating ? 'Create Assessment' : 'Edit Assessment & Question Bank'}
        </h2>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Exam Metadata Form */}
      <Card rounded="2xl" className="p-6 md:p-8">
        <div className="flex items-center gap-2 mb-6 pb-3 border-b border-outline-variant/60">
          <Icon name="tune" className="text-primary" size={20} />
          <h3 className="text-base font-semibold text-primary">Assessment Configuration</h3>
        </div>

        <form onSubmit={handleSaveExam} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1.5">
              Exam Title
            </label>
            <input
              type="text"
              className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-4 py-2.5 text-sm text-on-surface focus:outline-none focus:border-primary transition-colors"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              placeholder="e.g. Data Structures & Algorithms Assessment"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1.5">
              Description & Instructions
            </label>
            <textarea
              className="w-full rounded-2xl bg-surface-container-lowest border border-outline-variant px-4 py-2.5 text-sm text-on-surface focus:outline-none focus:border-primary transition-colors resize-y"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Guidelines, allowed resources, and instructions for test takers"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-2">
            <div>
              <label className="block text-xs font-medium text-on-surface-variant mb-1.5">
                Duration (Minutes)
              </label>
              <input
                type="number"
                className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-4 py-2 text-sm text-on-surface focus:outline-none focus:border-primary"
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                min={1}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-on-surface-variant mb-1.5">
                Start Time
              </label>
              <input
                type="datetime-local"
                className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-2 text-xs text-on-surface focus:outline-none focus:border-primary"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-on-surface-variant mb-1.5">
                End Time
              </label>
              <input
                type="datetime-local"
                className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-2 text-xs text-on-surface focus:outline-none focus:border-primary"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-on-surface-variant mb-1.5">
                Status
              </label>
              <select
                className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-2 text-xs text-on-surface font-medium focus:outline-none focus:border-primary"
                value={status}
                onChange={(e) => setStatus(e.target.value as any)}
              >
                <option value="draft">Draft (Unpublished)</option>
                <option value="published" disabled={isCreating || questions.length === 0}>
                  Published (Live) {isCreating || questions.length === 0 ? '— Requires at least 1 question' : ''}
                </option>
                <option value="archived">Archived</option>
              </select>
              {(isCreating || questions.length === 0) && (
                <p className="text-[10px] text-secondary mt-1">
                  Assessments are created as Drafts. Add questions first, then switch to Published.
                </p>
              )}
            </div>
          </div>

          {/* Browser Proctoring Controls */}
          <div className="pt-4 border-t border-outline-variant/60 space-y-4">
            <div className="flex items-center justify-between p-3.5 rounded-2xl bg-surface-container border border-outline-variant/60">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-surface-container-high flex items-center justify-center text-primary">
                  <Icon name="videocam" size={20} />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-primary">Browser-Level Proctoring</h4>
                  <p className="text-[11px] text-on-surface-variant">
                    Enforces camera/mic verification, fullscreen retention, tab away duration limits, and paste anomaly flagging.
                  </p>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableBrowserProctoring}
                  onChange={(e) => setEnableBrowserProctoring(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
              </label>
            </div>

            {enableBrowserProctoring && (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 p-4 rounded-2xl bg-surface-container-low border border-outline-variant/40 animate-in fade-in">
                  <div>
                    <label className="block text-[11px] font-medium text-on-surface-variant mb-1">
                      Max Fullscreen Exits
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="10"
                      className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary font-mono"
                      value={maxFullscreenExits}
                      onChange={(e) => setMaxFullscreenExits(Number(e.target.value))}
                    />
                    <span className="text-[10px] text-secondary">Auto-submits after threshold</span>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-on-surface-variant mb-1">
                      Return Countdown (Sec)
                    </label>
                    <input
                      type="number"
                      min="3"
                      max="60"
                      className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary font-mono"
                      value={fullscreenWarningTimeoutSeconds}
                      onChange={(e) => setFullscreenWarningTimeoutSeconds(Number(e.target.value))}
                    />
                    <span className="text-[10px] text-secondary">Warning modal timeout</span>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-on-surface-variant mb-1">
                      Max Cumulative Away (Sec)
                    </label>
                    <input
                      type="number"
                      min="10"
                      max="600"
                      className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary font-mono"
                      value={maxTabAwaySeconds}
                      onChange={(e) => setMaxTabAwaySeconds(Number(e.target.value))}
                    />
                    <span className="text-[10px] text-secondary">Total tab switch tolerance</span>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-on-surface-variant mb-1">
                      Paste Flag Threshold (Chars)
                    </label>
                    <input
                      type="number"
                      min="10"
                      max="500"
                      className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary font-mono"
                      value={pasteCharThreshold}
                      onChange={(e) => setPasteCharThreshold(Number(e.target.value))}
                    />
                    <span className="text-[10px] text-secondary">Flagged for instructor review</span>
                  </div>
                </div>

                {/* Video & Audio AI Proctoring Parameters (Phase 4) */}
                <div className="p-4 rounded-2xl bg-surface-container-low border border-outline-variant/40 space-y-3 animate-in fade-in">
                  <div className="flex items-center gap-2 text-xs font-semibold text-primary pb-1 border-b border-outline-variant/40">
                    <Icon name="psychology" size={16} />
                    <span>AI Video & Audio Proctoring Parameters (Phase 4)</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    <div>
                      <label className="block text-[11px] font-medium text-on-surface-variant mb-1">
                        Webcam Sampling (Sec)
                      </label>
                      <input
                        type="number"
                        min="3"
                        max="60"
                        className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary font-mono"
                        value={proctorFrameIntervalSeconds}
                        onChange={(e) => setProctorFrameIntervalSeconds(Number(e.target.value))}
                      />
                      <span className="text-[10px] text-secondary">Snapshot frequency (5-10s)</span>
                    </div>

                    <div>
                      <label className="block text-[11px] font-medium text-on-surface-variant mb-1">
                        Face Match Threshold
                      </label>
                      <input
                        type="number"
                        min="0.1"
                        max="1.0"
                        step="0.05"
                        className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary font-mono"
                        value={faceSimilarityThreshold}
                        onChange={(e) => setFaceSimilarityThreshold(Number(e.target.value))}
                      />
                      <span className="text-[10px] text-secondary">Cosine match tolerance (0.60)</span>
                    </div>

                    <div>
                      <label className="block text-[11px] font-medium text-on-surface-variant mb-1">
                        Max Consecutive Absence
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="10"
                        className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary font-mono"
                        value={consecutiveNoFaceLimit}
                        onChange={(e) => setConsecutiveNoFaceLimit(Number(e.target.value))}
                      />
                      <span className="text-[10px] text-secondary">Auto-submits after 0 faces</span>
                    </div>

                    <div>
                      <label className="block text-[11px] font-medium text-on-surface-variant mb-1">
                        Speech Threshold (Sec)
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="30"
                        className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-1.5 text-xs text-on-surface focus:outline-none focus:border-primary font-mono"
                        value={sustainedAudioThresholdSeconds}
                        onChange={(e) => setSustainedAudioThresholdSeconds(Number(e.target.value))}
                      />
                      <span className="text-[10px] text-secondary">Cumulative speech flag limit</span>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="flex justify-end pt-4">
            <Button
              type="submit"
              variant="primary"
              disabled={isSaving}
              isLoading={isSaving}
              icon="save"
            >
              {isCreating ? 'Save & Continue' : 'Save Changes'}
            </Button>
          </div>
        </form>
      </Card>

      {/* Question Bank Section */}
      {!isCreating && (
        <Card rounded="2xl" className="p-6 md:p-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 mb-6 border-b border-outline-variant/60">
            <div>
              <h3 className="text-base font-semibold text-primary">
                Question Bank ({questions.length})
              </h3>
              <p className="text-xs text-on-surface-variant mt-0.5">
                Total Assessment Points: {questions.reduce((acc, q) => acc + q.points, 0)} pts
              </p>
            </div>

            <Button
              variant="primary"
              size="sm"
              onClick={() => setShowQuestionModal(true)}
              icon="add"
            >
              Add Question
            </Button>
          </div>

          {questions.length === 0 ? (
            <div className="text-center py-12 text-on-surface-variant border border-dashed border-outline-variant rounded-2xl p-6">
              <Icon name="help_outline" size={32} className="text-secondary mb-2 mx-auto" />
              <p className="text-sm font-medium text-on-surface mb-1">No questions added yet</p>
              <p className="text-xs text-on-surface-variant">
                You must add at least 1 question before this exam can be published.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {questions.map((q, idx) => (
                <div
                  key={q.id}
                  className="p-4 rounded-xl border border-outline-variant/70 bg-surface-container-lowest flex items-center justify-between gap-4 transition-colors hover:bg-surface-container"
                >
                  <div className="space-y-1 overflow-hidden">
                    <div className="flex items-center gap-2">
                      <Badge variant="neutral" size="sm">
                        Q{idx + 1}
                      </Badge>
                      <Badge variant="outline" size="sm">
                        {q.type.toUpperCase()}
                      </Badge>
                      <span className="text-xs font-semibold text-primary">
                        {q.points} Pts
                      </span>
                    </div>
                    <div className="text-sm font-medium text-primary line-clamp-1">
                      {q.question_text}
                    </div>
                  </div>

                  <button
                    onClick={() => handleDeleteQuestion(q.id)}
                    className="w-8 h-8 rounded-full border border-outline-variant text-on-surface-variant hover:text-error hover:border-error/40 hover:bg-error-container/30 flex items-center justify-center transition-all shrink-0"
                    title="Delete Question"
                  >
                    <Icon name="delete" size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Add Question Modal */}
      {showQuestionModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <Card rounded="3xl" className="max-w-xl w-full max-h-[90vh] overflow-y-auto p-6 md:p-8 border border-outline-variant">
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-outline-variant/60">
              <h3 className="text-lg font-bold text-primary">Add Question</h3>
              <button
                onClick={() => setShowQuestionModal(false)}
                className="w-8 h-8 rounded-full hover:bg-surface-container flex items-center justify-center text-on-surface-variant"
              >
                <Icon name="close" size={18} />
              </button>
            </div>

            {/* Question Type Switcher using PillTab */}
            <div className="mb-6 flex justify-center">
              <PillTab
                items={[
                  { id: 'mcq', label: 'Multiple Choice (MCQ)', icon: 'checklist' },
                  { id: 'coding', label: 'Coding Assessment', icon: 'code' },
                ]}
                activeId={qType}
                onChange={(id) => setQType(id as 'mcq' | 'coding')}
              />
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-on-surface-variant mb-1.5">
                  Question Prompt / Problem Text
                </label>
                <textarea
                  className="w-full rounded-2xl bg-surface-container-lowest border border-outline-variant px-4 py-2.5 text-sm text-on-surface focus:outline-none focus:border-primary"
                  rows={3}
                  value={qText}
                  onChange={(e) => setQText(e.target.value)}
                  placeholder="Enter problem prompt..."
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-on-surface-variant mb-1.5">
                  Points
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0.5"
                  className="w-full rounded-full bg-surface-container-lowest border border-outline-variant px-4 py-2 text-sm text-on-surface focus:outline-none focus:border-primary"
                  value={qPoints}
                  onChange={(e) => setQPoints(Number(e.target.value))}
                  required
                />
              </div>

              {/* MCQ Options Config */}
              {qType === 'mcq' && (
                <div className="space-y-4 pt-2">
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 text-xs font-medium text-on-surface cursor-pointer">
                      <input
                        type="checkbox"
                        checked={mcqMulti}
                        onChange={(e) => setMcqMulti(e.target.checked)}
                        className="accent-primary w-4 h-4 rounded"
                      />
                      Multi-Select Question
                    </label>
                    {mcqMulti && (
                      <label className="flex items-center gap-2 text-xs font-medium text-on-surface cursor-pointer">
                        <input
                          type="checkbox"
                          checked={mcqPartial}
                          onChange={(e) => setMcqPartial(e.target.checked)}
                          className="accent-primary w-4 h-4 rounded"
                        />
                        Award Partial Credit
                      </label>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-on-surface-variant mb-2">
                      Options (Check the correct answers):
                    </label>
                    <div className="space-y-2">
                      {mcqOptions.map((opt, idx) => (
                        <div key={opt.id} className="flex items-center gap-2">
                          <input
                            type={mcqMulti ? 'checkbox' : 'radio'}
                            name="correct_choice"
                            checked={mcqCorrect.includes(opt.id)}
                            onChange={() => {
                              if (mcqMulti) {
                                setMcqCorrect((prev) =>
                                  prev.includes(opt.id)
                                    ? prev.filter((id) => id !== opt.id)
                                    : [...prev, opt.id]
                                );
                              } else {
                                setMcqCorrect([opt.id]);
                              }
                            }}
                            className="accent-primary w-4 h-4 cursor-pointer shrink-0"
                          />
                          <input
                            type="text"
                            className="flex-1 rounded-full bg-surface-container-lowest border border-outline-variant px-4 py-2 text-sm text-on-surface focus:outline-none focus:border-primary"
                            value={opt.text}
                            onChange={(e) => {
                              const newOpts = [...mcqOptions];
                              newOpts[idx].text = e.target.value;
                              setMcqOptions(newOpts);
                            }}
                            placeholder={`Option ${idx + 1}`}
                          />
                          {mcqOptions.length > 2 && (
                            <button
                              type="button"
                              onClick={() => {
                                setMcqOptions((prev) => prev.filter((o) => o.id !== opt.id));
                                setMcqCorrect((prev) => prev.filter((id) => id !== opt.id));
                              }}
                              className="w-8 h-8 rounded-full border border-outline-variant text-on-surface-variant hover:text-error flex items-center justify-center"
                            >
                              <Icon name="delete" size={16} />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        const newId = `opt_${Date.now()}`;
                        setMcqOptions((prev) => [...prev, { id: newId, text: '' }]);
                      }}
                      className="mt-3"
                      icon="add"
                    >
                      Add Option
                    </Button>
                  </div>
                </div>
              )}

              {/* Coding Problem Config */}
              {qType === 'coding' && (
                <div className="space-y-4 pt-2">
                  <div>
                    <label className="block text-xs font-medium text-on-surface-variant mb-1.5">
                      Starter Code Template (Python)
                    </label>
                    <textarea
                      className="w-full rounded-2xl bg-[#111111] text-gray-200 border border-[#262626] font-mono text-xs px-4 py-3 focus:outline-none"
                      rows={4}
                      value={codeStarter}
                      onChange={(e) => setCodeStarter(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-on-surface-variant mb-2">
                      Test Cases:
                    </label>
                    <div className="space-y-3">
                      {codeTestCases.map((tc, idx) => (
                        <div
                          key={idx}
                          className="p-3.5 rounded-2xl bg-surface-container border border-outline-variant/70 space-y-2"
                        >
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="block text-[11px] text-on-surface-variant mb-1">
                                Input (stdin)
                              </label>
                              <input
                                type="text"
                                className="w-full rounded-lg bg-surface-container-lowest border border-outline-variant px-3 py-1.5 text-xs text-on-surface font-mono"
                                value={tc.input}
                                onChange={(e) => {
                                  const newTests = [...codeTestCases];
                                  newTests[idx].input = e.target.value;
                                  setCodeTestCases(newTests);
                                }}
                                placeholder="e.g. 2 3"
                              />
                            </div>
                            <div>
                              <label className="block text-[11px] text-on-surface-variant mb-1">
                                Expected (stdout)
                              </label>
                              <input
                                type="text"
                                className="w-full rounded-lg bg-surface-container-lowest border border-outline-variant px-3 py-1.5 text-xs text-on-surface font-mono"
                                value={tc.expected_output}
                                onChange={(e) => {
                                  const newTests = [...codeTestCases];
                                  newTests[idx].expected_output = e.target.value;
                                  setCodeTestCases(newTests);
                                }}
                                placeholder="e.g. 5"
                              />
                            </div>
                          </div>
                          <div className="flex items-center justify-between pt-1">
                            <label className="flex items-center gap-2 text-xs text-on-surface cursor-pointer">
                              <input
                                type="checkbox"
                                checked={tc.is_hidden}
                                onChange={(e) => {
                                  const newTests = [...codeTestCases];
                                  newTests[idx].is_hidden = e.target.checked;
                                  setCodeTestCases(newTests);
                                }}
                                className="accent-primary w-3.5 h-3.5 rounded"
                              />
                              Hidden test case
                            </label>
                            {codeTestCases.length > 1 && (
                              <button
                                type="button"
                                onClick={() => setCodeTestCases((prev) => prev.filter((_, i) => i !== idx))}
                                className="text-xs text-error hover:underline flex items-center gap-1"
                              >
                                <Icon name="delete" size={14} /> Remove
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        setCodeTestCases((prev) => [
                          ...prev,
                          { input: '', expected_output: '', is_hidden: true },
                        ])
                      }
                      className="mt-3"
                      icon="add"
                    >
                      Add Test Case
                    </Button>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-6 mt-6 border-t border-outline-variant/60">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowQuestionModal(false)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleAddQuestion}
              >
                Add Question
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
