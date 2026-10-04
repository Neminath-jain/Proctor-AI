import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import { apiClient } from '../../api/client';
import {
  CandidateQuestion,
  CodeRunResponse,
  SessionStartResponse,
  ViolationEvent,
  ViolationLogResult,
  ProctorFrameResponse,
  ProctorAudioResponse,
} from '../../types';
import { Button, Card, Badge, Icon } from '../../components/ui';

interface ToastNotification {
  id: string;
  message: string;
  variant: 'warning' | 'error' | 'info';
  icon?: string;
}

export const ExamRoom: React.FC = () => {
  const { examId } = useParams<{ examId: string }>();
  const navigate = useNavigate();

  const [session, setSession] = useState<SessionStartResponse | null>(null);
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [remainingSecs, setRemainingSecs] = useState<number>(0);
  const [isSaving, setIsSaving] = useState(false);
  const [isRunningCode, setIsRunningCode] = useState(false);
  const [runResult, setRunResult] = useState<CodeRunResponse | null>(null);
  const [activeCodeLang, setActiveCodeLang] = useState<string>('python');
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Proctoring States
  const [, setIsFullscreen] = useState(true);
  const [showFullscreenWarning, setShowFullscreenWarning] = useState(false);
  const [fullscreenCountdown, setFullscreenCountdown] = useState(10);
  const [fullscreenExits, setFullscreenExits] = useState(0);
  const [isTerminated, setIsTerminated] = useState(false);
  const [terminatedReason, setTerminatedReason] = useState<string | null>(null);
  const [showWithdrawModal, setShowWithdrawModal] = useState(false);
  const [isSubmittingWithdraw, setIsSubmittingWithdraw] = useState(false);
  const [toasts, setToasts] = useState<ToastNotification[]>([]);

  // Phase 4 Video & Audio Proctoring States
  const [isMediaActive, setIsMediaActive] = useState<boolean>(false);
  const [isMediaRevoked, setIsMediaRevoked] = useState<boolean>(false);
  const [isOnline, setIsOnline] = useState<boolean>(navigator.onLine);
  const [isPipMinimized, setIsPipMinimized] = useState<boolean>(false);
  const [lastFaceStatus, setLastFaceStatus] = useState<'verified' | 'warning'>('verified');
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [framesAnalyzedCount, setFramesAnalyzedCount] = useState<number>(0);
  const [lastVerifiedAt, setLastVerifiedAt] = useState<string>('');

  // Refs for tracking async state and event handlers
  const sessionRef = useRef<SessionStartResponse | null>(null);
  const awayStartRef = useRef<number | null>(null);
  const fsWarningTimerRef = useRef<number | null>(null);
  const isSubmittingRef = useRef<boolean>(false);
  const editorRef = useRef<any>(null);
  const isUploadingFrameRef = useRef<boolean>(false);
  const isUploadingAudioRef = useRef<boolean>(false);

  // Video & Audio Proctoring Refs
  const proctorVideoRef = useRef<HTMLVideoElement | null>(null);
  const proctorStreamRef = useRef<MediaStream | null>(null);

  sessionRef.current = session;

  const showToast = useCallback((message: string, variant: 'warning' | 'error' | 'info' = 'warning', icon?: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev.slice(-2), { id, message, variant, icon }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  // Post Violation to Backend with Server Revalidation
  const reportViolation = useCallback(
    async (event: ViolationEvent) => {
      const currentSession = sessionRef.current;
      if (!currentSession || !currentSession.enable_browser_proctoring || isSubmittingRef.current) {
        return;
      }

      try {
        const { data } = await apiClient.post<ViolationLogResult>(
          `/candidate/sessions/${currentSession.session_id}/violations`,
          event
        );

        setFullscreenExits(data.fullscreen_exit_count);

        if (data.should_auto_submit || data.session_status === 'terminated') {
          isSubmittingRef.current = true;
          setIsTerminated(true);
          setTerminatedReason(
            data.terminated_reason || 'Examination automatically terminated due to proctoring policy violations.'
          );
        }
        return data;
      } catch (err: any) {
        console.warn('Failed to report violation to proctoring server:', err);
      }
    },
    []
  );

  // Final Exam Submission Handler
  const handleFinalSubmit = useCallback(async () => {
    const currentSession = sessionRef.current;
    if (!currentSession || isSubmittingRef.current) return;
    isSubmittingRef.current = true;

    try {
      await apiClient.post(`/candidate/sessions/${currentSession.session_id}/submit`);
      navigate(`/exams/${examId}/result`);
    } catch (err: any) {
      // If already terminated or submitted, still redirect to results
      if (err.response?.status === 400) {
        navigate(`/exams/${examId}/result`);
      } else {
        alert(err.response?.data?.detail || 'Submission failed.');
        isSubmittingRef.current = false;
      }
    }
  }, [examId, navigate]);

  // 1. Initialize Exam Session
  useEffect(() => {
    const initSession = async () => {
      try {
        const { data } = await apiClient.post<SessionStartResponse>(`/candidate/exams/${examId}/start`);
        setSession(data);
        sessionRef.current = data;
        setRemainingSecs(data.remaining_seconds);
        setAnswers(data.saved_answers || {});
        setFullscreenExits(data.fullscreen_exit_count || 0);

        if (data.status === 'terminated' || data.status === 'submitted') {
          navigate(`/exams/${examId}/result`);
          return;
        }

        if (data.questions.length > 0) {
          const firstQ = data.questions[0];
          if (firstQ.type === 'coding' && firstQ.allowed_languages?.length) {
            setActiveCodeLang(firstQ.allowed_languages[0]);
          }
        }

        // Check if proctoring is enabled and request fullscreen if not already in fullscreen
        if (data.enable_browser_proctoring && !document.fullscreenElement) {
          setShowFullscreenWarning(true);
          setFullscreenCountdown(data.fullscreen_warning_timeout_seconds || 10);
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to start exam session.');
      }
    };
    initSession();
  }, [examId, navigate]);

  // 2. Countdown Timer
  useEffect(() => {
    if (remainingSecs <= 0 && session) {
      handleFinalSubmit();
      return;
    }

    const timer = setInterval(() => {
      setRemainingSecs((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleFinalSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [remainingSecs, session, handleFinalSubmit]);

  // 3. Fullscreen Enforcement
  useEffect(() => {
    const handleFullscreenChange = () => {
      const isNowFs = !!document.fullscreenElement;
      setIsFullscreen(isNowFs);

      const currentSession = sessionRef.current;
      if (!currentSession?.enable_browser_proctoring || isSubmittingRef.current) {
        return;
      }

      if (!isNowFs) {
        // Candidate exited fullscreen
        setShowFullscreenWarning(true);
        const timeoutLimit = currentSession.fullscreen_warning_timeout_seconds || 10;
        setFullscreenCountdown(timeoutLimit);

        reportViolation({
          violation_type: 'fullscreen_exit',
          metadata: { is_timeout: false },
        });

        showToast('Fullscreen exit detected! Return immediately to avoid disqualification.', 'error', 'fullscreen_exit');
      } else {
        // Returned to fullscreen
        setShowFullscreenWarning(false);
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [reportViolation, showToast]);

  // Fullscreen Countdown Warning Loop
  useEffect(() => {
    if (!showFullscreenWarning || !session?.enable_browser_proctoring) {
      if (fsWarningTimerRef.current) clearInterval(fsWarningTimerRef.current);
      return;
    }

    fsWarningTimerRef.current = window.setInterval(() => {
      setFullscreenCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(fsWarningTimerRef.current!);
          // Timeout reached while outside fullscreen -> Critical violation and terminate
          reportViolation({
            violation_type: 'fullscreen_exit',
            metadata: { is_timeout: true },
          });
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (fsWarningTimerRef.current) clearInterval(fsWarningTimerRef.current);
    };
  }, [showFullscreenWarning, session, reportViolation]);

  // 4. Tab-Switch & Visibility Tracking
  useEffect(() => {
    const handleVisibilityChange = () => {
      const currentSession = sessionRef.current;
      if (!currentSession?.enable_browser_proctoring || isSubmittingRef.current) return;

      if (document.hidden) {
        awayStartRef.current = Date.now();
      } else {
        if (awayStartRef.current) {
          const duration = Math.max(1, Math.round((Date.now() - awayStartRef.current) / 1000));
          awayStartRef.current = null;

          reportViolation({
            violation_type: 'tab_switch',
            metadata: { duration_seconds: duration },
          });

          showToast(
            `Tab switch detected (${duration}s away). Flagged on integrity record.`,
            duration >= 15 ? 'error' : 'warning',
            'tab'
          );
        }
      }
    };

    const handleWindowBlur = () => {
      const currentSession = sessionRef.current;
      if (!currentSession?.enable_browser_proctoring || isSubmittingRef.current) return;
      if (!awayStartRef.current) {
        awayStartRef.current = Date.now();
      }
    };

    const handleWindowFocus = () => {
      const currentSession = sessionRef.current;
      if (!currentSession?.enable_browser_proctoring || isSubmittingRef.current) return;
      if (awayStartRef.current) {
        const duration = Math.max(1, Math.round((Date.now() - awayStartRef.current) / 1000));
        awayStartRef.current = null;

        reportViolation({
          violation_type: 'tab_switch',
          metadata: { duration_seconds: duration },
        });

        showToast(
          `Focus change detected (${duration}s away). Flagged on integrity record.`,
          duration >= 15 ? 'error' : 'warning',
          'tab'
        );
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('blur', handleWindowBlur);
    window.addEventListener('focus', handleWindowFocus);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('blur', handleWindowBlur);
      window.removeEventListener('focus', handleWindowFocus);
    };
  }, [reportViolation, showToast]);

  // 5. Input Deterrents (DevTools Shortcuts, Prevention)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const currentSession = sessionRef.current;
      if (!currentSession?.enable_browser_proctoring) return;

      const isF12 = e.key === 'F12';
      const isCtrlShiftI = (e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'I' || e.key === 'i');
      const isCtrlShiftJ = (e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'J' || e.key === 'j');
      const isCtrlShiftC = (e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'C' || e.key === 'c');
      const isCtrlU = (e.ctrlKey || e.metaKey) && (e.key === 'u' || e.key === 'U');

      if (isF12 || isCtrlShiftI || isCtrlShiftJ || isCtrlShiftC || isCtrlU) {
        e.preventDefault();
        e.stopPropagation();

        reportViolation({
          violation_type: 'devtools_attempt',
          metadata: { key_combination: e.key },
        });

        showToast('Developer tools and inspection shortcuts are strictly prohibited.', 'error', 'terminal');
      }
    };

    window.addEventListener('keydown', handleKeyDown, true);
    return () => {
      window.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [reportViolation, showToast]);

  // Context Menu Deterrent
  const handleContextMenu = (e: React.MouseEvent) => {
    if (session?.enable_browser_proctoring) {
      e.preventDefault();
      reportViolation({
        violation_type: 'context_menu_attempt',
        metadata: {},
      });
      showToast('Right-click context menu is disabled during the assessment.', 'info', 'mouse');
    }
  };

  // Question Prompt Copy Deterrent
  const handleQuestionCopy = (e: React.ClipboardEvent) => {
    if (session?.enable_browser_proctoring) {
      e.preventDefault();
      reportViolation({
        violation_type: 'copy_attempt',
        metadata: { target: 'question_prompt' },
      });
      showToast('Copying assessment questions is prohibited and flagged.', 'warning', 'content_copy');
    }
  };

  // ==============================================================================
  // Phase 4: Video & Audio AI Proctoring Pipeline
  // ==============================================================================

  // 1. Initialize webcam & audio stream for active exam session
  // 1. Initialize webcam & audio stream for active exam session with disconnection detection
  const startMedia = useCallback(async () => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;

      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: 'user' },
          audio: true,
        });
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: true,
        });
      }

      // Attach lifecycle listeners to catch mid-exam revocation or hardware disconnection
      stream.getTracks().forEach((track) => {
        track.onended = () => {
          setIsMediaActive(false);
          setIsMediaRevoked(true);
          reportViolation({
            violation_type: 'media_permission_revoked',
            metadata: { media_type: track.kind, reason: 'hardware_ended_or_revoked' },
          });
          showToast(
            `Camera/Microphone stream disconnected. Please restore permissions immediately.`,
            'error',
            'videocam_off'
          );
        };
        track.onmute = () => {
          showToast(
            `Proctoring ${track.kind} muted or obscured.`,
            'warning',
            'mic_off'
          );
        };
      });

      proctorStreamRef.current = stream;
      setIsMediaActive(true);
      setIsMediaRevoked(false);

      if (proctorVideoRef.current) {
        proctorVideoRef.current.srcObject = stream;
        proctorVideoRef.current.play().catch(() => {});
      }
    } catch (err) {
      console.warn('Unable to access proctoring media stream in ExamRoom:', err);
      setIsMediaRevoked(true);
      reportViolation({
        violation_type: 'media_permission_revoked',
        metadata: { error: String(err) },
      });
      showToast('Media permissions unavailable. Please ensure camera and mic are allowed.', 'error', 'videocam_off');
    }
  }, [reportViolation, showToast]);

  useEffect(() => {
    startMedia();

    // Network connectivity listeners for graceful offline handling
    const handleOnline = () => {
      setIsOnline(true);
      showToast('Network connection restored. Syncing answers.', 'info', 'cloud_done');
    };
    const handleOffline = () => {
      setIsOnline(false);
      showToast('Network disconnected. Your answers are saved locally and will sync once reconnected.', 'warning', 'wifi_off');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      if (proctorStreamRef.current) {
        proctorStreamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, [startMedia, showToast]);

  // Synchronize stream with video element whenever media mounts or is activated
  useEffect(() => {
    if (isMediaActive && proctorVideoRef.current && proctorStreamRef.current) {
      if (proctorVideoRef.current.srcObject !== proctorStreamRef.current) {
        proctorVideoRef.current.srcObject = proctorStreamRef.current;
        proctorVideoRef.current.play().catch((err) => {
          console.warn('Proctor video playback error:', err);
        });
      }
    }
  }, [isMediaActive]);

  // Real-time audio input volume meter (Web Audio API)
  useEffect(() => {
    if (!isMediaActive || !proctorStreamRef.current) return;
    const stream = proctorStreamRef.current;
    const audioTracks = stream.getAudioTracks();
    if (audioTracks.length === 0) return;

    let audioCtx: AudioContext | null = null;
    let analyser: AnalyserNode | null = null;
    let source: MediaStreamAudioSourceNode | null = null;
    let animId: number;

    try {
      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtxClass) {
        audioCtx = new AudioCtxClass();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        source = audioCtx.createMediaStreamSource(new MediaStream([audioTracks[0]]));
        source.connect(analyser);

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        let lastSample = 0;

        const sample = (now: number) => {
          if (analyser) {
            analyser.getByteFrequencyData(dataArray);
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
              sum += dataArray[i];
            }
            const avg = sum / dataArray.length;
            if (now - lastSample > 120) {
              setAudioLevel(Math.min(100, Math.round((avg / 128) * 100)));
              lastSample = now;
            }
          }
          animId = requestAnimationFrame(sample);
        };

        animId = requestAnimationFrame(sample);
      }
    } catch (err) {
      console.warn('Audio meter initialization error:', err);
    }

    return () => {
      cancelAnimationFrame(animId);
      if (source) source.disconnect();
      if (audioCtx && audioCtx.state !== 'closed') {
        audioCtx.close().catch(() => {});
      }
    };
  }, [isMediaActive]);

  // 2. Periodic video frame capture & evaluation
  useEffect(() => {
    if (!session || !isMediaActive || isTerminated) return;

    const intervalSecs = session.proctor_frame_interval_seconds || 10;
    const intervalMs = Math.max(5000, intervalSecs * 1000);

    const captureAndEvaluateFrame = async () => {
      if (isSubmittingRef.current || !proctorVideoRef.current || isUploadingFrameRef.current) return;
      const video = proctorVideoRef.current;
      if (video.videoWidth === 0 || video.videoHeight === 0) return;

      isUploadingFrameRef.current = true;
      try {
        const canvas = document.createElement('canvas');
        canvas.width = 320;
        canvas.height = 240;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.drawImage(video, 0, 0, 320, 240);
        const frameB64 = canvas.toDataURL('image/jpeg', 0.7);

        const { data } = await apiClient.post<ProctorFrameResponse>(
          `/candidate/sessions/${session.session_id}/proctor/frame`,
          { frame_base64: frameB64 }
        );

        setFramesAnalyzedCount((c) => c + 1);
        setLastVerifiedAt(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));

        if (data.anomaly) {
          setLastFaceStatus('warning');
          if (data.warning) {
            showToast(data.warning, 'warning', 'videocam_off');
          }
        } else {
          setLastFaceStatus('verified');
        }

        if (data.should_auto_submit || data.session_status === 'terminated') {
          isSubmittingRef.current = true;
          setIsTerminated(true);
          setTerminatedReason(
            data.warning || 'Examination terminated due to persistent candidate absence or face mismatch.'
          );
        }
      } catch (err) {
        console.warn('Periodic proctor frame check error:', err);
      } finally {
        isUploadingFrameRef.current = false;
      }
    };

    const timer = setInterval(captureAndEvaluateFrame, intervalMs);
    const initialTimer = setTimeout(captureAndEvaluateFrame, 3000);

    return () => {
      clearInterval(timer);
      clearTimeout(initialTimer);
    };
  }, [session, isMediaActive, isTerminated, showToast]);

  // 3. Periodic audio slice capture & VAD evaluation
  useEffect(() => {
    if (!session || !isMediaActive || isTerminated || !proctorStreamRef.current) return;

    const audioTracks = proctorStreamRef.current.getAudioTracks();
    if (audioTracks.length === 0) return;

    let isDestroyed = false;

    const recordAudioSlice = () => {
      if (isDestroyed || isSubmittingRef.current || !proctorStreamRef.current) return;

      try {
        const audioStream = new MediaStream(proctorStreamRef.current.getAudioTracks());
        let mimeType = 'audio/webm';
        if (typeof MediaRecorder !== 'undefined' && !MediaRecorder.isTypeSupported('audio/webm')) {
          mimeType = '';
        }

        const recorder = new MediaRecorder(audioStream, mimeType ? { mimeType } : undefined);
        const chunks: Blob[] = [];

        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) chunks.push(e.data);
        };

        recorder.onstop = async () => {
          if (chunks.length === 0 || isDestroyed || isSubmittingRef.current) return;
          const blob = new Blob(chunks, { type: chunks[0].type || 'audio/webm' });
          const reader = new FileReader();
          reader.onloadend = async () => {
            const b64 = reader.result as string;
            if (!b64 || isDestroyed || isUploadingAudioRef.current) return;
            isUploadingAudioRef.current = true;
            try {
              const { data } = await apiClient.post<ProctorAudioResponse>(
                `/candidate/sessions/${session.session_id}/proctor/audio`,
                { audio_base64: b64, sample_rate: 16000 }
              );

              if (data.warning) {
                showToast(data.warning, 'warning', 'mic');
              }

              if (data.should_auto_submit || data.session_status === 'terminated') {
                isSubmittingRef.current = true;
                setIsTerminated(true);
                setTerminatedReason(data.warning || 'Examination terminated due to sustained speech detected.');
              }
            } catch (err) {
              console.warn('Periodic proctor audio check error:', err);
            } finally {
              isUploadingAudioRef.current = false;
            }
          };
          reader.readAsDataURL(blob);
        };

        recorder.start();
        setTimeout(() => {
          if (recorder.state === 'recording') {
            recorder.stop();
          }
        }, 3000);
      } catch (err) {
        console.warn('Audio recorder initialization failed:', err);
      }
    };

    const audioInterval = setInterval(recordAudioSlice, 12000);
    const initialAudioTimer = setTimeout(recordAudioSlice, 5000);

    return () => {
      isDestroyed = true;
      clearInterval(audioInterval);
      clearTimeout(initialAudioTimer);
    };
  }, [session, isMediaActive, isTerminated, showToast]);

  // Save single question answer to backend
  const saveAnswer = async (questionId: string, answerValue: any) => {
    if (!session) return;
    setIsSaving(true);
    try {
      await apiClient.post(
        `/candidate/sessions/${session.session_id}/questions/${questionId}/answer`,
        { answer: answerValue }
      );
      setAnswers((prev) => ({ ...prev, [questionId]: answerValue }));
    } catch (err: any) {
      console.error('Failed to autosave answer:', err);
    } finally {
      setIsSaving(false);
    }
  };

  // MCQ Selection Handler
  const handleMcqSelect = (optionId: string, isMultiselect: boolean) => {
    if (!session) return;
    const currentQ = session.questions[currentQIndex];
    const currentAnswer = answers[currentQ.id];

    let newAnswer: any;
    if (isMultiselect) {
      const selectedList: string[] = Array.isArray(currentAnswer) ? [...currentAnswer] : [];
      if (selectedList.includes(optionId)) {
        newAnswer = selectedList.filter((id) => id !== optionId);
      } else {
        newAnswer = [...selectedList, optionId];
      }
    } else {
      newAnswer = optionId;
    }

    saveAnswer(currentQ.id, newAnswer);
  };

  // Coding Code Change Handler
  const handleCodeChange = (newCode: string | undefined) => {
    if (!session || newCode === undefined) return;
    const currentQ = session.questions[currentQIndex];
    const codePayload = {
      source_code: newCode,
      language: activeCodeLang,
    };
    setAnswers((prev) => ({ ...prev, [currentQ.id]: codePayload }));
  };

  // Monaco Editor Mount & Paste-Burst Detection
  const handleEditorDidMount = (editor: any) => {
    editorRef.current = editor;

    editor.onDidPaste((e: any) => {
      if (!sessionRef.current?.enable_browser_proctoring) return;

      try {
        if (e && e.range && editor.getModel()) {
          const pastedText = editor.getModel().getValueInRange(e.range);
          const threshold = sessionRef.current.paste_char_threshold || 50;

          if (pastedText && pastedText.length >= threshold) {
            reportViolation({
              violation_type: 'paste_burst',
              metadata: {
                char_count: pastedText.length,
                field: 'monaco_editor',
                snippet_preview: pastedText.substring(0, 40) + '...',
              },
            });

            showToast(
              `Large paste detected (${pastedText.length} characters) — flagged for review.`,
              'warning',
              'content_paste'
            );
          }
        }
      } catch (pasteErr) {
        console.warn('Error reading paste content:', pasteErr);
      }
    });
  };

  // Run Code against visible test cases
  const handleRunCode = async () => {
    if (!session) return;
    const currentQ = session.questions[currentQIndex];
    const currentCode = answers[currentQ.id]?.source_code || currentQ.starter_code?.[activeCodeLang] || '';

    setIsRunningCode(true);
    setRunResult(null);
    try {
      const { data } = await apiClient.post<CodeRunResponse>(
        `/candidate/sessions/${session.session_id}/questions/${currentQ.id}/run-code`,
        {
          source_code: currentCode,
          language: activeCodeLang,
        }
      );
      setRunResult(data);
      await saveAnswer(currentQ.id, { source_code: currentCode, language: activeCodeLang });
      if (data.all_passed) {
        showToast('All visible test cases passed!', 'info', 'check_circle');
      } else {
        showToast(`${data.passed_count} of ${data.total_count} test cases passed.`, 'warning', 'info');
      }
    } catch (err: any) {
      if (err.response?.status === 429) {
        showToast('Test execution rate limit reached (5 second cooldown). Please wait before running again.', 'warning', 'hourglass_top');
      } else {
        const msg = err.response?.data?.detail || 'Code execution temporarily unavailable. Please retry.';
        showToast(msg, 'error', 'error_outline');
      }
    } finally {
      setIsRunningCode(false);
    }
  };

  // Re-enter fullscreen request
  const requestReenterFullscreen = async () => {
    try {
      if (document.documentElement.requestFullscreen) {
        await document.documentElement.requestFullscreen();
      } else if ((document.documentElement as any).webkitRequestFullscreen) {
        await (document.documentElement as any).webkitRequestFullscreen();
      }
      setShowFullscreenWarning(false);
    } catch (err) {
      console.error('Failed to enter fullscreen:', err);
    }
  };

  // DPDP Section 6: Candidate Consent Withdrawal
  const handleWithdrawConsent = async () => {
    setIsSubmittingWithdraw(true);
    try {
      if (examId) {
        await apiClient.post(`/privacy/exams/${examId}/withdraw-consent`);
      }

      // Immediately halt and release all camera and microphone tracks
      if (proctorStreamRef.current) {
        proctorStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      setIsMediaActive(false);

      isSubmittingRef.current = true;
      setIsTerminated(true);
      setTerminatedReason(
        'Proctoring consent was withdrawn by candidate under Section 6 of India\'s DPDP Act 2023. Video, audio, and browser monitoring stopped immediately. Your assessment has been submitted for administrative review.'
      );
      setShowWithdrawModal(false);
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to submit consent withdrawal.', 'error');
    } finally {
      setIsSubmittingWithdraw(false);
    }
  };


  if (error) {
    return (
      <Card variant="default" className="text-center max-w-md mx-auto my-16 p-8">
        <div className="w-12 h-12 rounded-full bg-error-container text-error flex items-center justify-center mx-auto mb-4">
          <Icon name="block" size={24} />
        </div>
        <h2 className="text-xl font-bold text-primary mb-2">Exam Inaccessible</h2>
        <p className="text-sm text-on-surface-variant mb-6">{error}</p>
        <Button variant="secondary" onClick={() => navigate('/exams')}>
          Return to Exam List
        </Button>
      </Card>
    );
  }

  if (!session) {
    return (
      <div className="text-center py-24 text-on-surface-variant flex flex-col items-center gap-3">
        <span className="animate-spin">
          <Icon name="progress_activity" size={32} />
        </span>
        <p className="text-sm">Establishing secure proctored session with assessment server...</p>
      </div>
    );
  }

  const currentQ: CandidateQuestion = session.questions[currentQIndex];
  const minutes = Math.floor(remainingSecs / 60);
  const seconds = remainingSecs % 60;
  const isTimeCritical = remainingSecs < 300;
  const isUrgentCritical = remainingSecs < 60;
  const maxExits = session.max_fullscreen_exits || 2;

  return (
    <div
      onContextMenu={handleContextMenu}
      className="flex flex-col h-[calc(100vh-130px)] space-y-4 select-text relative overflow-x-hidden"
    >
      {/* Toast Notification Stack */}
      <div className="fixed top-20 right-6 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto px-4 py-2.5 rounded-xl shadow-lg border text-xs font-medium flex items-center gap-2.5 transition-all animate-in fade-in slide-in-from-top-2 ${
              t.variant === 'error'
                ? 'bg-rose-50 text-rose-950 border-rose-300'
                : t.variant === 'warning'
                ? 'bg-amber-50 text-amber-950 border-amber-300'
                : 'bg-zinc-100 text-zinc-900 border-zinc-300'
            }`}
          >
            {t.icon && (
              <Icon
                name={t.icon}
                size={16}
                className={
                  t.variant === 'error'
                    ? 'text-rose-800'
                    : t.variant === 'warning'
                    ? 'text-amber-800'
                    : 'text-zinc-700'
                }
              />
            )}
            <span>{t.message}</span>
          </div>
        ))}
      </div>

      {/* Top Header Bar: Linear-style precision telemetry */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-xl px-5 py-3 flex justify-between items-center shrink-0 shadow-subtle">
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-sm md:text-base font-bold text-primary line-clamp-1">
                {session.exam_title}
              </h2>
              {session.enable_browser_proctoring && (
                <span className="inline-flex items-center gap-1.5 text-xs text-primary font-medium bg-surface-container px-2 py-0.5 rounded border border-outline-variant/60">
                  <span className="telemetry-beacon shrink-0" />
                  Live proctoring
                </span>
              )}
            </div>
            <div className="text-xs text-secondary mt-0.5">
              Question <span className="text-primary font-medium">{currentQIndex + 1}</span> of{' '}
              <span className="text-primary font-medium">{session.questions.length}</span> •{' '}
              <span className="text-primary font-medium">{currentQ.points}</span> pts
              {session.enable_browser_proctoring && (
                <span className="ml-2 text-secondary font-mono">
                  [Exits: {fullscreenExits}/{maxExits}]
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Server Countdown Timer: Calm Tabular Numerals (urgent red only in final 60s) */}
        <div className="flex items-center gap-3">
          <div
            className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg border text-xs font-semibold font-mono tabular-nums tracking-wider transition-colors ${
              isUrgentCritical
                ? 'bg-rose-100 text-rose-950 border-rose-300 font-bold animate-pulse'
                : isTimeCritical
                ? 'bg-amber-100 text-amber-950 border-amber-300'
                : 'bg-surface-container-low text-primary border-outline-variant/70 shadow-subtle'
            }`}
          >
            <Icon name="timer" size={15} className={isUrgentCritical ? 'text-rose-800' : 'text-secondary'} />
            <span className="tabular-nums">
              {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
            </span>
          </div>

          {/* Action Controls */}
          <div className="flex items-center gap-2">
            {isSaving && (
              <span className="text-xs text-secondary flex items-center gap-1">
                <Icon name="sync" size={13} className="animate-spin text-secondary" />
                <span className="hidden sm:inline">Saving...</span>
              </span>
            )}
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowWithdrawModal(true)}
              icon="shield"
              id="header-withdraw-consent-btn"
              className="text-xs text-secondary hover:text-rose-700"
              title="Withdraw Proctoring Consent under DPDP Act 2023"
            >
              <span className="hidden md:inline">Withdraw consent</span>
              <span className="md:hidden">Privacy</span>
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setShowSubmitModal(true)}
              icon="task_alt"
              className="text-xs font-medium shadow-subtle"
            >
              Finish exam
            </Button>
          </div>
        </div>
      </div>

      {/* Offline Alert Banner */}
      {!isOnline && (
        <div className="border border-amber-300 bg-amber-50 text-amber-950 rounded-xl px-4 py-2.5 flex items-center justify-between text-xs animate-in fade-in shrink-0">
          <div className="flex items-center gap-2">
            <Icon name="wifi_off" size={16} className="text-amber-800 shrink-0" />
            <span><strong>Offline mode:</strong> Network disconnected. Your answers are saved locally and will automatically synchronize when connection returns.</span>
          </div>
          <span className="text-[11px] text-amber-900 font-medium">Reconnecting...</span>
        </div>
      )}

      {/* Media Disconnected Warning Banner */}
      {isMediaRevoked && (
        <div className="border border-rose-300 bg-rose-50 text-rose-950 rounded-xl px-4 py-2.5 flex items-center justify-between text-xs animate-in fade-in shrink-0">
          <div className="flex items-center gap-2">
            <Icon name="videocam_off" size={16} className="text-rose-800 shrink-0" />
            <span><strong>Camera / Microphone disconnected:</strong> Continuous video and audio verification is required for this examination.</span>
          </div>
          <Button variant="secondary" size="sm" onClick={() => startMedia()} className="text-xs shrink-0">
            Restore Connection
          </Button>
        </div>
      )}

      {/* Question Palette Navigation Bar */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 shrink-0 scrollbar-thin">
        <span className="text-xs font-medium text-secondary mr-1 shrink-0 hidden sm:inline">
          Questions:
        </span>
        {session.questions.map((q, idx) => {
          const isAnswered = answers[q.id] !== undefined && answers[q.id] !== '';
          const isCurrent = idx === currentQIndex;

          return (
            <button
              key={q.id}
              onClick={() => setCurrentQIndex(idx)}
              className={`w-8 h-8 rounded-lg text-xs font-mono font-semibold shrink-0 transition-all flex items-center justify-center ${
                isCurrent
                  ? 'bg-primary text-on-primary ring-2 ring-primary ring-offset-2 ring-offset-background'
                  : isAnswered
                  ? 'bg-surface-container-highest text-primary border border-outline font-bold'
                  : 'bg-surface-container-lowest text-on-surface-variant border border-outline-variant/70 hover:bg-surface-container'
              }`}
            >
              {idx + 1}
            </button>
          );
        })}
      </div>

      {/* Main Examination Workspace: Calm Integrity Focus */}
      <div
        className={`flex-1 grid gap-4 overflow-hidden ${
          currentQ.type === 'coding' ? 'grid-cols-1 lg:grid-cols-12' : 'grid-cols-1'
        }`}
      >
        {/* Left Column: Problem Prompt & MCQ Options */}
        <div
          className={`border border-outline-variant/70 bg-surface-container-lowest rounded-xl p-6 md:p-8 flex flex-col justify-between overflow-y-auto shadow-terminal ${
            currentQ.type === 'coding' ? 'lg:col-span-5' : 'max-w-3xl mx-auto w-full'
          }`}
        >
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-xs text-secondary bg-surface-container px-2 py-0.5 rounded border border-outline-variant/50">
                {currentQ.type === 'mcq' ? 'Multiple choice' : 'Coding problem'} • {currentQ.points} pts
              </span>
              {currentQ.is_multiselect && (
                <span className="text-xs font-semibold text-amber-950 bg-amber-100 px-2 py-0.5 rounded border border-amber-300">
                  Multiple selection
                </span>
              )}
            </div>

            {/* Question Text with copy deterrent */}
            <h3
              onCopy={handleQuestionCopy}
              className="text-base md:text-lg font-medium text-primary whitespace-pre-wrap leading-relaxed select-none"
            >
              {currentQ.question_text}
            </h3>

            {/* MCQ Option Selection Cards */}
            {currentQ.type === 'mcq' && currentQ.options && (
              <div className="space-y-2.5 pt-2">
                {currentQ.options.map((opt, optIndex) => {
                  const currentAns = answers[currentQ.id];
                  const isSelected = currentQ.is_multiselect
                    ? Array.isArray(currentAns) && currentAns.includes(opt.id)
                    : currentAns === opt.id;
                  const keyLetter = String.fromCharCode(65 + optIndex);

                  return (
                    <div
                      key={opt.id}
                      onClick={() => handleMcqSelect(opt.id, currentQ.is_multiselect)}
                      className={`p-4 rounded-xl border transition-all cursor-pointer flex items-center gap-3.5 ${
                        isSelected
                          ? 'border-primary bg-surface-container-high text-primary font-medium shadow-subtle'
                          : 'border-outline-variant/60 bg-surface-container-lowest text-on-surface hover:bg-surface-container hover:border-outline-variant'
                      }`}
                    >
                      <span
                        className={`w-6 h-6 rounded flex items-center justify-center font-mono text-xs font-bold shrink-0 transition-colors ${
                          isSelected
                            ? 'bg-primary text-on-primary'
                            : 'bg-surface-container text-secondary border border-outline-variant/60'
                        }`}
                      >
                        {keyLetter}
                      </span>
                      <span className="text-sm leading-snug flex-1">{opt.text}</span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Coding Problem Visible Sample Cases */}
            {currentQ.type === 'coding' && currentQ.visible_test_cases && (
              <div className="mt-6">
                <h4 className="text-xs font-semibold text-on-surface-variant mb-2">
                  Sample test cases
                </h4>
                <div className="space-y-2">
                  {currentQ.visible_test_cases.map((tc, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-surface-container border border-outline-variant/60 font-mono text-xs text-on-surface space-y-1"
                    >
                      <div>
                        <span className="text-on-surface-variant font-medium">Input: </span>
                        <span>{tc.input || '(none)'}</span>
                      </div>
                      <div>
                        <span className="text-on-surface-variant font-medium">Expected: </span>
                        <span className="font-semibold">{tc.expected_output}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Navigation Pill Buttons */}
          <div className="flex justify-between items-center pt-6 mt-6 border-t border-outline-variant/60">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setCurrentQIndex((prev) => Math.max(0, prev - 1))}
              disabled={currentQIndex === 0}
              icon="arrow_back"
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setCurrentQIndex((prev) => Math.min(session.questions.length - 1, prev + 1))}
              disabled={currentQIndex === session.questions.length - 1}
              icon="arrow_forward"
              iconPosition="right"
            >
              Next
            </Button>
          </div>
        </div>

        {/* Right Column: Code Panel (Coding Assessment) */}
        {currentQ.type === 'coding' && (
          <div className="lg:col-span-7 flex flex-col gap-3 overflow-hidden">
            {/* Editor Toolbar */}
            <div className="border border-outline-variant bg-surface-container-low rounded-2xl px-4 py-2.5 flex justify-between items-center shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-xs text-on-surface-variant font-medium">Language:</span>
                <select
                  value={activeCodeLang}
                  onChange={(e) => setActiveCodeLang(e.target.value)}
                  className="rounded-full bg-surface-container-lowest border border-outline-variant px-3 py-1 text-xs text-on-surface font-medium focus:outline-none focus:border-primary"
                >
                  {(currentQ.allowed_languages || ['python']).map((lang) => (
                    <option key={lang} value={lang}>
                      {lang.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleRunCode}
                  disabled={isRunningCode}
                  isLoading={isRunningCode}
                  icon="play_arrow"
                >
                  {isRunningCode ? 'Running Sandbox Tests...' : 'Run Visible Tests'}
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    const currentCode =
                      answers[currentQ.id]?.source_code || currentQ.starter_code?.[activeCodeLang] || '';
                    saveAnswer(currentQ.id, { source_code: currentCode, language: activeCodeLang });
                  }}
                  icon="save"
                >
                  Save
                </Button>
              </div>
            </div>

            {/* Monaco Editor Frame */}
            <div className="flex-1 min-h-[260px] rounded-2xl overflow-hidden border border-[#262626] bg-[#111111]">
              <Editor
                height="100%"
                language={activeCodeLang === 'nodejs' ? 'javascript' : activeCodeLang}
                theme="vs-dark"
                value={
                  answers[currentQ.id]?.source_code !== undefined
                    ? answers[currentQ.id].source_code
                    : currentQ.starter_code?.[activeCodeLang] || '# Write your solution here\n'
                }
                onChange={handleCodeChange}
                onMount={handleEditorDidMount}
                options={{
                  minimap: { enabled: false },
                  fontSize: 13,
                  fontFamily: 'JetBrains Mono, monospace',
                  scrollBeyondLastLine: false,
                  automaticLayout: true,
                  wordWrap: 'on',
                }}
              />
            </div>

            {/* Terminal Test Results Console */}
            {runResult && (
              <div className="h-44 p-4 rounded-2xl bg-[#111111] text-white border border-[#262626] overflow-y-auto font-mono text-xs shrink-0">
                <div className="flex justify-between items-center mb-3 pb-2 border-b border-[#262626]">
                  <div className="flex items-center gap-2 text-gray-300">
                    <Icon name="terminal" size={16} />
                    <span className="font-semibold">Test Results</span>
                  </div>
                  <Badge
                    variant={runResult.all_passed ? 'success' : 'error'}
                    size="sm"
                    icon={runResult.all_passed ? 'check' : 'close'}
                  >
                    {runResult.passed_count} / {runResult.total_count} Passed
                  </Badge>
                </div>

                <div className="space-y-2">
                  {runResult.results.map((r) => (
                    <div
                      key={r.test_case_index}
                      className={`p-2.5 rounded-xl border ${
                        r.passed
                          ? 'bg-[#162319] border-[#25462c] text-gray-200'
                          : 'bg-[#291517] border-[#4d2126] text-gray-200'
                      }`}
                    >
                      <div className="flex justify-between font-semibold">
                        <span className="flex items-center gap-1.5">
                          <Icon
                            name={r.passed ? 'check_circle' : 'cancel'}
                            size={14}
                            className={r.passed ? 'text-[#488e53]' : 'text-[#c73e4a]'}
                          />
                          Test Case #{r.test_case_index + 1}: {r.status_description}
                        </span>
                        <span className="text-gray-400 font-normal">{r.runtime}s</span>
                      </div>
                      {r.actual_output && (
                        <div className="mt-1 text-gray-300">
                          <span className="text-gray-500">Output: </span>
                          {r.actual_output}
                        </div>
                      )}
                      {r.stderr && (
                        <div className="mt-1 text-[#f87171]">
                          <span className="text-gray-500">Stderr: </span>
                          {r.stderr}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Floating Picture-in-Picture Video/Audio Proctoring Widget */}
      {isMediaActive && (
        <div
          className={`fixed bottom-4 right-4 z-40 transition-all duration-300 shadow-2xl rounded-2xl overflow-hidden border border-outline-variant/70 bg-surface-container-lowest/95 backdrop-blur-md ${
            isPipMinimized ? 'w-56' : 'w-72'
          }`}
        >
          {/* Header Bar */}
          <div className="px-3 py-2 bg-surface-container-high/95 border-b border-outline-variant/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-600 shrink-0"></span>
              </span>
              <span className="text-[11px] font-bold text-primary tracking-wide">AI Proctor Active</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className={`text-xs font-medium px-2.5 py-0.5 rounded-full flex items-center gap-1 ${
                  lastFaceStatus === 'verified'
                    ? 'bg-success/15 text-success border border-success/30'
                    : 'bg-error/15 text-error border border-error/30'
                }`}
              >
                <Icon name={lastFaceStatus === 'verified' ? 'check_circle' : 'warning'} size={12} />
                {lastFaceStatus === 'verified' ? 'Face verified' : 'Check face'}
              </span>
              <button
                type="button"
                onClick={() => setIsPipMinimized(!isPipMinimized)}
                className="p-1 hover:bg-surface-container-highest rounded text-secondary hover:text-primary transition-colors"
                title={isPipMinimized ? 'Expand preview' : 'Minimize preview'}
              >
                <Icon name={isPipMinimized ? 'unfold_more' : 'unfold_less'} size={14} />
              </button>
            </div>
          </div>

          {/* Video Container - keep video mounted and playing */}
          <div className={`relative bg-black transition-all ${isPipMinimized ? 'h-0 opacity-0 overflow-hidden' : 'aspect-video'}`}>
            <video
              ref={(el) => {
                proctorVideoRef.current = el;
                if (el && proctorStreamRef.current && el.srcObject !== proctorStreamRef.current) {
                  el.srcObject = proctorStreamRef.current;
                  el.play().catch(() => {});
                }
              }}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover transform -scale-x-100"
            />

            {/* Live Recording Badge */}
            <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/75 backdrop-blur-sm px-2 py-0.5 rounded-full text-[10px] text-white font-bold tracking-wider">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shrink-0" />
              <span className="text-red-400">REC</span>
              {framesAnalyzedCount > 0 && (
                <span className="text-gray-300 font-mono text-[9px] border-l border-white/20 pl-1.5">
                  #{framesAnalyzedCount}
                </span>
              )}
            </div>

            {/* Live AI Status Badge */}
            <div className="absolute top-2 right-2 flex items-center gap-1 bg-black/75 backdrop-blur-sm px-2 py-0.5 rounded-full text-[10px] font-semibold text-emerald-400">
              <Icon name="verified_user" size={11} className="text-emerald-400" />
              <span>AI Monitored</span>
            </div>

            {/* Bottom Floating Status Bar */}
            <div className="absolute bottom-1.5 left-1.5 right-1.5 flex items-center justify-between pointer-events-none">
              {/* Mic & Live Audio Level Meter */}
              <div className="flex items-center gap-1.5 bg-black/70 backdrop-blur-sm px-2 py-0.5 rounded text-[10px] text-white">
                <Icon
                  name="mic"
                  size={12}
                  className={audioLevel > 15 ? 'text-success animate-pulse' : 'text-gray-300'}
                />
                <span>{audioLevel > 15 ? 'Audio Detected' : 'Audio Active'}</span>
                <div className="flex items-end gap-0.5 h-2.5 w-3 ml-0.5">
                  <span
                    className={`w-0.5 rounded-full transition-all duration-75 ${
                      audioLevel > 10 ? 'bg-success' : 'bg-gray-500'
                    }`}
                    style={{ height: `${Math.max(25, Math.min(100, audioLevel * 2))}%` }}
                  />
                  <span
                    className={`w-0.5 rounded-full transition-all duration-75 ${
                      audioLevel > 25 ? 'bg-success' : 'bg-gray-500'
                    }`}
                    style={{ height: `${Math.max(35, Math.min(100, audioLevel * 3))}%` }}
                  />
                  <span
                    className={`w-0.5 rounded-full transition-all duration-75 ${
                      audioLevel > 45 ? 'bg-success' : 'bg-gray-500'
                    }`}
                    style={{ height: `${Math.max(20, Math.min(100, audioLevel * 1.5))}%` }}
                  />
                </div>
              </div>

              {/* Timestamp of last analyzed frame */}
              {lastVerifiedAt && (
                <div className="bg-black/70 backdrop-blur-sm px-1.5 py-0.5 rounded text-[9px] text-gray-300 font-mono">
                  {lastVerifiedAt}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Fullscreen Warning Modal */}
      {showFullscreenWarning && !isTerminated && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <Card variant="surface" className="max-w-md w-full text-center border border-error/50 p-6 md:p-8">
            <div className="w-14 h-14 rounded-full bg-error-container text-error flex items-center justify-center mx-auto mb-4 animate-bounce">
              <Icon name="fullscreen_exit" size={28} />
            </div>
            <h3 className="text-xl font-bold text-primary mb-1">Fullscreen Mode Required</h3>
            <p className="text-sm text-on-surface-variant mb-4">
              You have exited fullscreen mode. Proctoring rules require full immersion throughout the examination.
            </p>

            <div className="p-3 mb-6 rounded-2xl bg-surface-container border border-outline-variant/60">
              <div className="text-xs text-secondary font-medium">Automatic Termination in</div>
              <div className="text-3xl font-mono font-extrabold text-error my-1">
                {fullscreenCountdown}s
              </div>
              <div className="text-xs text-on-surface-variant">
                Fullscreen Exits: <span className="font-bold text-primary">{fullscreenExits}</span> of{' '}
                <span className="font-bold text-primary">{maxExits}</span> allowed
              </div>
            </div>

            <Button variant="primary" className="w-full" onClick={requestReenterFullscreen} icon="fullscreen">
              Return to Fullscreen Now
            </Button>
          </Card>
        </div>
      )}

      {/* Examination Terminated Modal */}
      {isTerminated && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <Card variant="surface" className="max-w-md w-full text-center border border-error p-6 md:p-8">
            <div className="w-16 h-16 rounded-full bg-error text-white flex items-center justify-center mx-auto mb-4">
              <Icon name="gavel" size={32} />
            </div>
            <h3 className="text-xl font-bold text-primary mb-2">Examination Terminated</h3>
            <p className="text-sm text-on-surface-variant mb-6 leading-relaxed">
              {terminatedReason || 'Your exam has been automatically closed due to severe proctoring violations.'}
            </p>

            <Button
              variant="primary"
              className="w-full"
              onClick={() => navigate(`/exams/${examId}/result`)}
              icon="arrow_forward"
            >
              Proceed to Final Record
            </Button>
          </Card>
        </div>
      )}

      {/* Confirmation Modal */}
      {showSubmitModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <Card variant="surface" className="max-w-md w-full text-center border border-outline-variant p-6 md:p-8">
            <div className="w-14 h-14 rounded-full bg-surface-container-high text-primary flex items-center justify-center mx-auto mb-4">
              <Icon name="task_alt" size={28} />
            </div>
            <h3 className="text-xl font-bold text-primary mb-2">Submit Examination?</h3>
            <p className="text-sm text-on-surface-variant mb-6 leading-relaxed">
              Your code will be evaluated against all test cases (including hidden ones) and your score
              will be permanently recorded. You cannot re-enter this exam after submitting.
            </p>

            <div className="flex gap-3 justify-center">
              <Button variant="secondary" onClick={() => setShowSubmitModal(false)}>
                Continue Exam
              </Button>
              <Button variant="primary" onClick={handleFinalSubmit}>
                Confirm & Submit
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* DPDP Section 6 Withdraw Consent Modal */}
      {showWithdrawModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <Card variant="surface" className="max-w-md w-full text-center border border-outline-variant p-6 md:p-8 space-y-4">
            <div className="w-14 h-14 rounded-full bg-surface-container flex items-center justify-center text-rose-800 mx-auto">
              <Icon name="shield" size={28} />
            </div>
            <div className="space-y-1">
              <Badge variant="outline" size="xs">
                DPDP Section 6 Statutory Right
              </Badge>
              <h3 className="text-xl font-bold text-primary">Withdraw Proctoring Consent?</h3>
            </div>
            <p className="text-xs text-secondary leading-relaxed">
              Under Section 6 of India&apos;s Digital Personal Data Protection Act, 2023, you have the right to withdraw your proctoring consent at any time.
            </p>
            <div className="p-3.5 rounded-xl bg-surface-container-low border border-outline-variant/60 text-left text-xs space-y-1.5 text-secondary">
              <div className="font-semibold text-primary">Upon confirmation:</div>
              <ul className="list-disc list-inside space-y-1 text-[11px] leading-relaxed">
                <li>Webcam, microphone, and browser telemetry stop immediately.</li>
                <li>Your exam session is terminated and marked as <em>consent_withdrawn</em>.</li>
                <li>Answers saved so far will be submitted for institutional review.</li>
              </ul>
            </div>

            <div className="flex flex-col sm:flex-row gap-2.5 justify-center pt-2">
              <Button
                variant="secondary"
                onClick={() => setShowWithdrawModal(false)}
                disabled={isSubmittingWithdraw}
                className="text-xs"
              >
                Keep Consenting & Continue
              </Button>
              <Button
                variant="primary"
                id="confirm-withdraw-consent-btn"
                onClick={handleWithdrawConsent}
                isLoading={isSubmittingWithdraw}
                disabled={isSubmittingWithdraw}
                className="text-xs bg-rose-800 hover:bg-rose-900 border-rose-800 text-white"
              >
                Confirm Withdrawal & Exit
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

