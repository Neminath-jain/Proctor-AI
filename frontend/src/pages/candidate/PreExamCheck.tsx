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
          // Scale roughly from 0 to 100
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
        <p className="text-sm">Loading proctoring environment...</p>
      </div>
    );
  }

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

        {exam && (
          <div className="flex items-center gap-2">
            <Badge variant="neutral" size="xs" rounded="md" icon="assignment">
              {exam.title}
            </Badge>
          </div>
        )}
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
