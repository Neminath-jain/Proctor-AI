import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { CandidateAvailableExam, MediaVerificationResponse } from '../../types';
import { Button, Badge, Icon, Alert } from '../../components/ui';

export const PreExamCheck: React.FC = () => {
  const { examId } = useParams<{ examId: string }>();
  const navigate = useNavigate();

  const [exam, setExam] = useState<CandidateAvailableExam | null>(null);
  const [isLoadingExam, setIsLoadingExam] = useState(true);

  // DPDP Consent Flow States
  const [consentStage, setConsentStage] = useState<'notice' | 'granted' | 'declined'>('notice');
  const [consentNoticeRead, setConsentNoticeRead] = useState(false);
  const [consentBiometricsAgreed, setConsentBiometricsAgreed] = useState(false);
  const [isSubmittingConsent, setIsSubmittingConsent] = useState(false);
  const [consentAuditId, setConsentAuditId] = useState<string | null>(null);

  // Hardware Calibration States
  const [cameraStatus, setCameraStatus] = useState<'idle' | 'requesting' | 'granted' | 'denied'>('idle');
  const [micStatus, setMicStatus] = useState<'idle' | 'requesting' | 'granted' | 'denied'>('idle');
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [referencePhoto, setReferencePhoto] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const takeSnapshot = useCallback(() => {
    if (!videoRef.current) return null;
    const video = videoRef.current;
    if (video.videoWidth === 0 || video.videoHeight === 0) return null;
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, 640, 480);
    const b64 = canvas.toDataURL('image/jpeg', 0.85);
    setReferencePhoto(b64);
    return b64;
  }, []);

  // 1. Fetch exam info
  useEffect(() => {
    const fetchExam = async () => {
      try {
        const { data } = await apiClient.get<CandidateAvailableExam[]>('/candidate/exams');
        const current = data.find((e) => e.id === examId);
        if (current) {
          setExam(current);
        } else {
          setErrorMessage('Exam not found or you are not authorized to take it.');
        }
      } catch (err: any) {
        setErrorMessage(err.response?.data?.detail || 'Failed to load exam information.');
      } finally {
        setIsLoadingExam(false);
      }
    };
    fetchExam();
  }, [examId]);

  // Clean up media streams and audio context on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
      }
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, []);

  // 2. DPDP Consent Handlers
  const handleGrantConsent = async () => {
    if (!examId) return;
    setIsSubmittingConsent(true);
    setErrorMessage(null);
    try {
      const { data } = await apiClient.post(`/privacy/exams/${examId}/consent`, {
        status: 'granted',
        clauses_consented: [
          'periodic_camera_snapshots',
          'audio_anomaly_chunks',
          'facial_biometrics_reference',
          'browser_integrity_telemetry',
        ],
        notice_version: '2023.1-dpdp',
      });
      setConsentAuditId(data.consent_id || null);
      setConsentStage('granted');
      // Automatically request hardware permissions once consent is recorded
      requestPermissions();
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to record DPDP consent record.');
    } finally {
      setIsSubmittingConsent(false);
    }
  };

  const handleDeclineConsent = async () => {
    if (!examId) return;
    setIsSubmittingConsent(true);
    setErrorMessage(null);
    try {
      await apiClient.post(`/privacy/exams/${examId}/consent`, {
        status: 'declined',
        clauses_consented: [],
        notice_version: '2023.1-dpdp',
      });
      setConsentStage('declined');
    } catch (err: any) {
      setConsentStage('declined');
    } finally {
      setIsSubmittingConsent(false);
    }
  };

  // 3. Media permissions request
  const requestPermissions = async () => {
    setCameraStatus('requesting');
    setMicStatus('requesting');
    setErrorMessage(null);

    // Stop any existing stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
    }

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Your browser does not support webcam/audio capture.');
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: true,
      });

      streamRef.current = stream;
      setCameraStatus('granted');
      setMicStatus('granted');

      // Bind to video element
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current?.play().catch(() => {});
          // Automatically capture reference photo after video stabilizes
          setTimeout(() => {
            takeSnapshot();
          }, 1000);
        };
      }

      // Initialize audio analyzer for visual feedback
      try {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        const audioCtx = new AudioContextClass();
        audioContextRef.current = audioCtx;
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const updateAudio = () => {
          analyser.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
          }
          const average = sum / dataArray.length;
          setAudioLevel(Math.min(100, Math.round((average / 128) * 100)));
          animFrameRef.current = requestAnimationFrame(updateAudio);
        };
        updateAudio();
      } catch (audioErr) {
        console.warn('Audio visualization context warning:', audioErr);
      }
    } catch (err: any) {
      console.error('Media permission error:', err);
      setCameraStatus('denied');
      setMicStatus('denied');
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMessage(
          'Camera and Microphone permissions were denied. Please click the lock or camera icon in your browser address bar to allow permissions, then click Retry.'
        );
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setErrorMessage('No camera or microphone hardware found. Please connect your devices and retry.');
      } else {
        setErrorMessage(err.message || 'Unable to access media devices.');
      }
    }
  };

  const handleEnterExam = async () => {
    if (!examId) return;
    setIsVerifying(true);
    setErrorMessage(null);

    // Make sure we have a reference photo
    let photo = referencePhoto;
    if (!photo && cameraStatus === 'granted') {
      photo = takeSnapshot();
    }

    try {
      // 1. Post verification to backend with reference photo
      const { data } = await apiClient.post<MediaVerificationResponse>(`/candidate/exams/${examId}/verify-media`, {
        camera_granted: cameraStatus === 'granted',
        mic_granted: micStatus === 'granted',
        reference_photo_base64: photo || undefined,
      });

      if (data.face_detected === false) {
        setErrorMessage(
          data.message || 'No face detected in reference photo. Please face the camera directly and retake your photo.'
        );
        setIsVerifying(false);
        return;
      }

      // 2. Stop preview tracks so they don't lock devices for the exam
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
      }
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }

      // 3. Request browser fullscreen
      try {
        if (document.documentElement.requestFullscreen) {
          await document.documentElement.requestFullscreen();
        } else if ((document.documentElement as any).webkitRequestFullscreen) {
          await (document.documentElement as any).webkitRequestFullscreen();
        }
      } catch (fsErr) {
        console.warn('Fullscreen request bypassed by browser security policy:', fsErr);
      }

      // 4. Navigate to exam room
      navigate(`/exams/${examId}/take`);
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to verify media authorization with server.');
      setIsVerifying(false);
    }
  };

  const allVerified = cameraStatus === 'granted' && micStatus === 'granted';

  if (isLoadingExam) {
    return (
      <div className="text-center py-24 text-on-surface-variant flex flex-col items-center gap-3">
        <span className="animate-spin">
          <Icon name="progress_activity" size={32} />
        </span>
        <p className="text-sm">Loading examination environment...</p>
      </div>
    );
  }

  // -------------------------------------------------------------
  // VIEW 1: DPDP Act 2023 Explicit Consent Screen (Pre-Hardware)
  // -------------------------------------------------------------
  if (consentStage === 'notice') {
    return (
      <div className="max-w-3xl mx-auto space-y-6 py-4">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 pb-2 border-b border-outline-variant/60">
          <Link
            to="/exams"
            className="text-xs text-secondary hover:text-primary transition-colors inline-flex items-center gap-1"
          >
            <Icon name="arrow_back" size={14} />
            <span>Back to assessments</span>
          </Link>
          <span className="text-outline-variant text-xs">/</span>
          <span className="text-xs text-secondary">DPDP Consent</span>
        </div>

        {errorMessage && (
          <Alert variant="error" onClose={() => setErrorMessage(null)}>
            {errorMessage}
          </Alert>
        )}

        <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 sm:p-8 space-y-6 shadow-subtle">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" size="xs" icon="gavel">
                DPDP Act 2023 Notice
              </Badge>
              <span className="text-xs text-secondary">•</span>
              <span className="text-xs text-secondary font-medium">Data Fiduciary: Proctor AI</span>
              {exam && (
                <Badge variant="neutral" size="xs">
                  {exam.title}
                </Badge>
              )}
            </div>

            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-primary">
              Examination Proctoring Consent & Notice
            </h1>
            <p className="text-xs sm:text-sm text-secondary leading-relaxed">
              Under Section 6 of India&apos;s <strong>Digital Personal Data Protection Act, 2023 (DPDP Act 2023)</strong>, Proctor AI must obtain your freely given, specific, informed, and unambiguous consent before accessing your hardware or processing proctoring data.
            </p>
          </div>

          {/* Transparent Disclosures Grid */}
          <div className="space-y-3 pt-1">
            <div className="text-xs font-semibold text-primary">Data that will be processed during this examination:</div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3.5 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-1">
                <div className="font-semibold text-primary flex items-center gap-1.5">
                  <Icon name="videocam" size={15} />
                  <span>Periodic Camera Snapshots</span>
                </div>
                <p className="text-secondary leading-relaxed text-[11px]">
                  Discrete low-resolution photos taken every 10–15 seconds to verify presence. <em>We do not record continuous 24/7 video streams.</em>
                </p>
              </div>

              <div className="p-3.5 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-1">
                <div className="font-semibold text-primary flex items-center gap-1.5">
                  <Icon name="face" size={15} />
                  <span>Biometric Face-Match Embedding</span>
                </div>
                <p className="text-secondary leading-relaxed text-[11px]">
                  A 128-dimensional numerical vector extracted from your baseline photo to verify identity against periodic snapshots in-memory.
                </p>
              </div>

              <div className="p-3.5 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-1">
                <div className="font-semibold text-primary flex items-center gap-1.5">
                  <Icon name="mic" size={15} />
                  <span>Audio Anomaly Chunks</span>
                </div>
                <p className="text-secondary leading-relaxed text-[11px]">
                  Short micro-buffers analyzed locally; audio chunks are saved only when anomalies (voice murmurs, secondary speakers) are detected.
                </p>
              </div>

              <div className="p-3.5 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-1">
                <div className="font-semibold text-primary flex items-center gap-1.5">
                  <Icon name="tab" size={15} />
                  <span>Browser Telemetry</span>
                </div>
                <p className="text-secondary leading-relaxed text-[11px]">
                  Fullscreen exits, tab switches, and window blur events are logged to maintain test integrity. No external tabs or files are accessed.
                </p>
              </div>
            </div>
          </div>

          {/* Compliance & Rights Summary Card */}
          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/40 space-y-2 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
              <div>
                <span className="font-semibold text-primary block">Purpose:</span>
                <span className="text-secondary">Identity verification & integrity auditing</span>
              </div>
              <div>
                <span className="font-semibold text-primary block">Retention Period:</span>
                <span className="text-secondary">Strictly 90 days (AWS ap-south-1 Mumbai)</span>
              </div>
              <div>
                <span className="font-semibold text-primary block">Access Scope:</span>
                <span className="text-secondary">Authorized exam administrators only</span>
              </div>
            </div>
            <div className="pt-1 text-[11px] text-secondary border-t border-outline-variant/40">
              Your data is <strong>never</strong> sold, shared with advertisers, or used for automated marketing. You have the statutory right to withdraw consent mid-exam at any time.
            </div>
          </div>

          {/* Un-prechecked Consent Checkboxes */}
          <div className="space-y-3 pt-2 border-t border-outline-variant/60">
            <label className="flex items-start gap-3 cursor-pointer text-xs text-secondary group">
              <input
                type="checkbox"
                id="consent-check-policy"
                checked={consentNoticeRead}
                onChange={(e) => setConsentNoticeRead(e.target.checked)}
                className="mt-0.5 rounded border-outline-variant text-primary focus:ring-primary h-4 w-4 shrink-0 cursor-pointer"
              />
              <span className="leading-relaxed">
                I have reviewed the data collection notice and the <Link to="/privacy" target="_blank" className="text-primary font-medium underline">Proctor AI Privacy Policy</Link>, and acknowledge the 90-day retention and deletion policy.
              </span>
            </label>

            <label className="flex items-start gap-3 cursor-pointer text-xs text-secondary group">
              <input
                type="checkbox"
                id="consent-check-biometrics"
                checked={consentBiometricsAgreed}
                onChange={(e) => setConsentBiometricsAgreed(e.target.checked)}
                className="mt-0.5 rounded border-outline-variant text-primary focus:ring-primary h-4 w-4 shrink-0 cursor-pointer"
              />
              <span className="leading-relaxed">
                I provide <strong className="text-primary font-medium">explicit and voluntary consent</strong> under Section 6 of the DPDP Act 2023 for periodic camera snapshot capture, audio monitoring, and biometric facial comparison for the sole purpose of invigilating this examination.
              </span>
            </label>
          </div>

          {/* Actions */}
          <div className="pt-2 flex flex-col sm:flex-row items-center gap-3">
            <Button
              variant="primary"
              size="md"
              id="grant-dpdp-consent-btn"
              disabled={!consentNoticeRead || !consentBiometricsAgreed || isSubmittingConsent}
              isLoading={isSubmittingConsent}
              onClick={handleGrantConsent}
              icon="verified_user"
              className="w-full sm:w-auto text-xs font-medium shadow-subtle"
            >
              I Consent & Proceed to Hardware Check
            </Button>

            <Button
              variant="secondary"
              size="md"
              id="decline-dpdp-consent-btn"
              disabled={isSubmittingConsent}
              onClick={handleDeclineConsent}
              className="w-full sm:w-auto text-xs"
            >
              Decline Consent
            </Button>

            <Link to="/privacy" className="text-xs text-secondary hover:text-primary sm:ml-auto">
              Learn about DPDP Act 2023 &rarr;
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------
  // VIEW 2: DPDP Consent Declined Screen (Clear, Respectful Notice)
  // -------------------------------------------------------------
  if (consentStage === 'declined') {
    return (
      <div className="max-w-2xl mx-auto space-y-6 py-8">
        <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 sm:p-8 space-y-6 shadow-subtle text-center">
          <div className="w-14 h-14 rounded-full bg-surface-container flex items-center justify-center text-primary mx-auto">
            <Icon name="shield" size={28} />
          </div>

          <div className="space-y-2">
            <Badge variant="outline" size="xs">
              DPDP Section 6 Choice Respected
            </Badge>
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-primary">
              Proctoring Consent Declined
            </h1>
            <p className="text-xs sm:text-sm text-secondary leading-relaxed max-w-lg mx-auto">
              Under India&apos;s Digital Personal Data Protection Act, 2023, data collection cannot occur without your voluntary consent. Because this online examination requires automated identity verification and integrity monitoring, candidates who decline consent cannot enter the digital exam room.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/40 text-xs text-secondary text-left space-y-2">
            <div className="font-semibold text-primary">What you can do next:</div>
            <ul className="list-disc list-inside space-y-1 text-[11px] leading-relaxed">
              <li>If you declined accidentally, you may reconsider and review the consent terms again.</li>
              <li>If you have privacy concerns or require offline accommodation, contact your course administrator.</li>
              <li>No proctoring data, camera snapshots, or audio files were collected from your device.</li>
            </ul>
          </div>

          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button
              variant="primary"
              size="sm"
              icon="replay"
              onClick={() => {
                setConsentNoticeRead(false);
                setConsentBiometricsAgreed(false);
                setConsentStage('notice');
              }}
              className="w-full sm:w-auto text-xs"
            >
              Review & Reconsider Consent
            </Button>

            <Button
              variant="secondary"
              size="sm"
              icon="arrow_back"
              onClick={() => navigate('/exams')}
              className="w-full sm:w-auto text-xs"
            >
              Return to Assessments List
            </Button>
          </div>

          <div className="pt-2 text-xs text-secondary">
            Have questions? Contact our Grievance Officer at{' '}
            <a href="mailto:grievance@proctorai.edu" className="text-primary underline">
              grievance@proctorai.edu
            </a>
          </div>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------
  // VIEW 3: Hardware Calibration & Baseline Photo (Consent Granted)
  // -------------------------------------------------------------
  return (
    <div className="max-w-4xl mx-auto space-y-6 py-4">
      {/* Hardware Calibration Console Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-outline-variant/60">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              to="/exams"
              className="text-xs text-secondary hover:text-primary transition-colors inline-flex items-center gap-1"
            >
              <Icon name="arrow_back" size={14} />
              <span>Back to assessments</span>
            </Link>
            <span className="text-outline-variant text-xs">/</span>
            <span className="text-xs text-secondary">
              Pre-exam check
            </span>
          </div>
          <h1 className="text-xl md:text-2xl font-semibold tracking-tight text-primary">
            Camera & microphone check
          </h1>
        </div>

        <div className="flex items-center gap-2">
          {consentAuditId && (
            <Badge variant="success" size="xs" icon="check_circle">
              DPDP Consent Verified
            </Badge>
          )}
          {exam && (
            <Badge variant="neutral" size="xs" rounded="md" icon="assignment">
              {exam.title}
            </Badge>
          )}
        </div>
      </div>

      {/* DPDP Compliance Micro-Banner */}
      <div className="p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/40 flex items-center justify-between text-xs text-secondary">
        <div className="flex items-center gap-2">
          <Icon name="verified_user" size={15} className="text-primary shrink-0" />
          <span>DPDP Consent active: 90-day retention schedule enforced. You may withdraw consent at any time during the exam.</span>
        </div>
        <Link to="/privacy" className="text-primary underline hover:text-primary/80 shrink-0 hidden sm:inline">
          View Policy
        </Link>
      </div>

      {errorMessage && (
        <Alert variant="error" title="Check error" onClose={() => setErrorMessage(null)}>
          {errorMessage}
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Video Calibration Monitor & VU dB Meter */}
        <div className="lg:col-span-7 space-y-3">
          <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl overflow-hidden shadow-subtle">
            {/* Camera Monitor Frame */}
            <div className="relative aspect-video bg-[#111111] flex items-center justify-center overflow-hidden">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className={`w-full h-full object-cover transform -scale-x-100 ${
                  cameraStatus === 'granted' ? 'block' : 'hidden'
                }`}
              />

              {cameraStatus !== 'granted' && (
                <div className="flex flex-col items-center justify-center p-8 text-center text-white/70 gap-2.5 z-20">
                  <Icon name="videocam_off" size={32} className="text-white/40" />
                  <div className="text-xs font-medium text-white">
                    Camera offline
                  </div>
                  <p className="text-xs text-white/60 max-w-xs">
                    Please allow browser camera permissions to verify your video feed.
                  </p>
                </div>
              )}

              {/* Status overlay tag */}
              <div className="absolute top-3 left-3 z-20">
                {cameraStatus === 'granted' ? (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-black/60 text-white text-xs backdrop-blur-sm">
                    <span className="telemetry-beacon shrink-0" />
                    Camera connected
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-black/60 text-white/70 text-xs backdrop-blur-sm">
                    Waiting for camera
                  </span>
                )}
              </div>
            </div>

            {/* Microphone Volume Meter */}
            <div className="p-4 bg-surface-container-low/40 border-t border-outline-variant/50">
              <div className="flex items-center justify-between text-xs mb-2">
                <div className="flex items-center gap-1.5 font-medium text-primary">
                  <Icon
                    name={micStatus === 'granted' ? 'mic' : 'mic_off'}
                    size={15}
                    className={micStatus === 'granted' ? 'text-success' : 'text-secondary'}
                  />
                  <span>Microphone input level</span>
                </div>
                <span className="text-xs text-secondary tabular-nums font-mono">
                  {Math.round(audioLevel)}% • {audioLevel > 5 ? 'Audio detected' : 'Microphone ready'}
                </span>
              </div>
              <div className="w-full bg-surface-container-highest rounded-full h-2 overflow-hidden flex items-center p-0.5 border border-outline-variant/40">
                <div
                  className="bg-primary h-full rounded-full transition-all duration-75"
                  style={{ width: `${Math.min(100, audioLevel * 1.2)}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right: Checklist & Actions */}
        <div className="lg:col-span-5 space-y-3">
          <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 space-y-4 shadow-subtle">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/50">
              <h2 className="text-xs font-semibold text-primary">
                Pre-exam checklist
              </h2>
            </div>

            <div className="divide-y divide-outline-variant/40 text-xs">
              {/* Webcam Row */}
              <div className="py-2.5 flex items-start gap-3">
                <Icon
                  name={cameraStatus === 'granted' ? 'check_circle' : 'videocam'}
                  size={18}
                  className={`mt-0.5 ${cameraStatus === 'granted' ? 'text-success' : 'text-secondary'}`}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-primary text-xs">Webcam</span>
                    <span
                      className={`text-xs font-medium ${
                        cameraStatus === 'granted' ? 'text-success' : 'text-secondary'
                      }`}
                    >
                      {cameraStatus === 'granted' ? 'Connected' : 'Pending'}
                    </span>
                  </div>
                  <p className="text-xs text-secondary mt-0.5">
                    Your camera will remain active to monitor exam room integrity.
                  </p>
                </div>
              </div>

              {/* Microphone Row */}
              <div className="py-2.5 flex items-start gap-3">
                <Icon
                  name={micStatus === 'granted' ? 'check_circle' : 'mic'}
                  size={18}
                  className={`mt-0.5 ${micStatus === 'granted' ? 'text-success' : 'text-secondary'}`}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-primary text-xs">Microphone</span>
                    <span
                      className={`text-xs font-medium ${
                        micStatus === 'granted' ? 'text-success' : 'text-secondary'
                      }`}
                    >
                      {micStatus === 'granted' ? 'Connected' : 'Pending'}
                    </span>
                  </div>
                  <p className="text-xs text-secondary mt-0.5">
                    Used to detect background noise or unauthorized communication.
                  </p>
                </div>
              </div>

              {/* Fullscreen Row */}
              <div className="py-2.5 flex items-start gap-3">
                <Icon name="fullscreen" size={18} className="mt-0.5 text-primary" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-primary text-xs">Fullscreen mode</span>
                    <span className="text-xs font-medium text-primary">
                      Required
                    </span>
                  </div>
                  <p className="text-xs text-secondary mt-0.5">
                    The exam will lock into fullscreen mode. Exiting fullscreen will be logged.
                  </p>
                </div>
              </div>

              {/* Verification Photo Row */}
              <div className="py-2.5 flex items-start gap-3">
                {referencePhoto ? (
                  <img
                    src={referencePhoto}
                    alt="Biometric baseline"
                    className="w-9 h-9 rounded-lg object-cover border border-outline-variant shadow-subtle shrink-0 mt-0.5"
                  />
                ) : (
                  <Icon
                    name={cameraStatus === 'granted' ? 'face' : 'person'}
                    size={18}
                    className={`mt-0.5 ${cameraStatus === 'granted' ? 'text-primary' : 'text-secondary'}`}
                  />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-primary text-xs">Verification photo</span>
                    <span
                      className={`text-xs font-medium ${
                        referencePhoto ? 'text-success' : 'text-secondary'
                      }`}
                    >
                      {referencePhoto ? 'Captured' : 'Pending'}
                    </span>
                  </div>
                  <p className="text-xs text-secondary mt-0.5">
                    A baseline photo is taken to verify your identity during the session.
                  </p>
                  {cameraStatus === 'granted' && (
                    <button
                      type="button"
                      onClick={() => takeSnapshot()}
                      className="mt-1.5 text-xs text-primary font-medium hover:underline inline-flex items-center gap-1"
                    >
                      <Icon name="photo_camera" size={13} />
                      {referencePhoto ? 'Retake photo' : 'Take photo'}
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="pt-2 space-y-2">
              {!allVerified ? (
                <Button
                  variant="primary"
                  className="w-full text-xs font-medium shadow-subtle"
                  onClick={requestPermissions}
                  isLoading={cameraStatus === 'requesting'}
                  icon="sensors"
                >
                  {cameraStatus === 'denied' ? 'Retry camera permission' : 'Allow camera & microphone'}
                </Button>
              ) : (
                <Button
                  variant="primary"
                  className="w-full text-xs font-medium shadow-subtle"
                  onClick={handleEnterExam}
                  isLoading={isVerifying}
                  icon="fullscreen"
                >
                  Start exam (enter fullscreen)
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
