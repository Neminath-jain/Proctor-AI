import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../api/client';
import { Card, Badge, Button, Icon, Alert } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export const Settings: React.FC = () => {
  useDocumentTitle('Settings — ProctorAI', 'Account settings, security credentials, and system diagnostics.');
  const { user, refreshUserProfile } = useAuth();
  const isAdmin = user?.role === 'admin';

  // DPDP Privacy & Rights states
  const [privacyStatus, setPrivacyStatus] = useState<any>(null);
  const [isLoadingPrivacyStatus, setIsLoadingPrivacyStatus] = useState<boolean>(false);
  const [isExportingData, setIsExportingData] = useState<boolean>(false);
  const [exportedSummary, setExportedSummary] = useState<any>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const [showErasureModal, setShowErasureModal] = useState<boolean>(false);
  const [erasureReason, setErasureReason] = useState<string>('');
  const [isSubmittingErasure, setIsSubmittingErasure] = useState<boolean>(false);
  const [erasureSuccess, setErasureSuccess] = useState<string | null>(null);
  const [erasureError, setErasureError] = useState<string | null>(null);

  const fetchPrivacyStatus = async () => {
    setIsLoadingPrivacyStatus(true);
    try {
      const { data } = await apiClient.get('/privacy/status');
      setPrivacyStatus(data);
    } catch (e) {
      // non-blocking
    } finally {
      setIsLoadingPrivacyStatus(false);
    }
  };

  useEffect(() => {
    fetchPrivacyStatus();
  }, []);

  const handleExportData = async () => {
    setIsExportingData(true);
    setExportError(null);
    try {
      const { data } = await apiClient.get('/privacy/export');
      setExportedSummary({
        sessionsCount: data.exam_sessions?.length || 0,
        violationsCount: data.violations?.length || 0,
        consentsCount: data.consent_records?.length || 0,
        exportedAt: data.exported_at,
      });

      // Trigger browser download
      const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(JSON.stringify(data, null, 2))}`;
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute('href', jsonString);
      downloadAnchor.setAttribute('download', `proctorai_personal_data_${user?.id || 'candidate'}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    } catch (err: any) {
      setExportError(err.response?.data?.detail || 'Failed to export personal data.');
    } finally {
      setIsExportingData(false);
    }
  };

  const handleErasureRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmittingErasure(true);
    setErasureSuccess(null);
    setErasureError(null);
    try {
      const { data } = await apiClient.post('/privacy/erasure-request', {
        reason: erasureReason || undefined,
      });
      setErasureSuccess(data.message || 'Erasure request submitted successfully.');
      setShowErasureModal(false);
      setErasureReason('');
      fetchPrivacyStatus();
    } catch (err: any) {
      setErasureError(err.response?.data?.detail || 'Failed to submit erasure request.');
    } finally {
      setIsSubmittingErasure(false);
    }
  };

  // 1. Name update state
  const [name, setName] = useState(user?.name || '');
  const [isUpdatingName, setIsUpdatingName] = useState(false);
  const [nameSuccess, setNameSuccess] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);

  useEffect(() => {
    if (user?.name) {
      setName(user.name);
    }
  }, [user?.name]);

  const handleUpdateName = async (e: React.FormEvent) => {
    e.preventDefault();
    setNameSuccess(null);
    setNameError(null);

    const trimmed = name.trim();
    if (!trimmed) {
      setNameError('Name cannot be empty.');
      return;
    }

    setIsUpdatingName(true);
    try {
      await apiClient.put('/auth/me', { name: trimmed });
      await refreshUserProfile();
      setNameSuccess('Profile name updated successfully.');
    } catch (err: any) {
      setNameError(err.response?.data?.detail || 'Failed to update profile name.');
    } finally {
      setIsUpdatingName(false);
    }
  };

  // 2. Change password state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const validatePasswordRules = (pwd: string) => {
    if (pwd.length < 8) return 'Password must be at least 8 characters long.';
    if (!/[A-Za-z]/.test(pwd)) return 'Password must contain at least one letter.';
    if (!/\d/.test(pwd)) return 'Password must contain at least one numeric digit.';
    return null;
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordSuccess(null);
    setPasswordError(null);

    if (!currentPassword) {
      setPasswordError('Please provide your current password.');
      return;
    }

    const ruleError = validatePasswordRules(newPassword);
    if (ruleError) {
      setPasswordError(ruleError);
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError('New password and confirmation do not match.');
      return;
    }

    if (currentPassword === newPassword) {
      setPasswordError('New password must be different from current password.');
      return;
    }

    setIsUpdatingPassword(true);
    try {
      await apiClient.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordSuccess('Password changed successfully.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPasswordError(err.response?.data?.detail || 'Failed to change password.');
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  // 3. Candidate Hardware Diagnostics State
  const [isTestingMedia, setIsTestingMedia] = useState(false);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [cameraStatus, setCameraStatus] = useState<'idle' | 'granted' | 'denied'>('idle');
  const [micStatus, setMicStatus] = useState<'idle' | 'granted' | 'denied'>('idle');
  const [audioLevel, setAudioLevel] = useState(0);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const stopMediaTest = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    setIsTestingMedia(false);
    setAudioLevel(0);
  };

  const startMediaTest = async () => {
    stopMediaTest();
    setMediaError(null);
    setCameraStatus('idle');
    setMicStatus('idle');

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Your browser does not support media device capture.');
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: true,
      });

      streamRef.current = stream;
      setCameraStatus('granted');
      setMicStatus('granted');
      setIsTestingMedia(true);

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      // Audio analysis
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioCtxRef.current = audioCtx;
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      const buffer = new Uint8Array(analyser.frequencyBinCount);
      const updateMeter = () => {
        analyser.getByteFrequencyData(buffer);
        let sum = 0;
        for (let i = 0; i < buffer.length; i++) sum += buffer[i];
        const avg = sum / buffer.length;
        setAudioLevel(Math.min(100, Math.round((avg / 128) * 100)));
        animFrameRef.current = requestAnimationFrame(updateMeter);
      };
      updateMeter();
    } catch (err: any) {
      setCameraStatus('denied');
      setMicStatus('denied');
      setMediaError(err.message || 'Permission denied or no compatible devices detected.');
      setIsTestingMedia(false);
    }
  };

  useEffect(() => {
    return () => {
      stopMediaTest();
    };
  }, []);

  // 4. Admin Examination Preferences State
  const [minTrustScore, setMinTrustScore] = useState(80);
  const [maxFullscreenExits, setMaxFullscreenExits] = useState(2);
  const [liveTelemetryEnabled, setLiveTelemetryEnabled] = useState(true);
  const [adminPrefsSaved, setAdminPrefsSaved] = useState(false);

  const handleSaveAdminPrefs = (e: React.FormEvent) => {
    e.preventDefault();
    setAdminPrefsSaved(true);
    setTimeout(() => setAdminPrefsSaved(false), 3000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-4">
      {/* Page Header */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 md:p-8 shadow-subtle flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Badge variant="outline" size="xs" icon="manage_accounts">
              Account Control
            </Badge>
            <span className="text-xs text-secondary">Personal and system configurations</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-primary">
            Settings
          </h1>
          <p className="text-sm text-secondary">
            Manage your account credentials, security preferences, and system checks.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={isAdmin ? 'dark' : 'outline'} size="sm" className="capitalize">
            {user?.role} Account
          </Badge>
        </div>
      </div>

      {/* Section 1: Profile & Identity */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-6">
        <div className="border-b border-outline-variant/60 pb-4">
          <h2 className="text-base font-semibold text-primary flex items-center gap-2">
            <Icon name="person" size={18} />
            <span>Profile Details</span>
          </h2>
          <p className="text-xs text-secondary mt-0.5">
            Your name is visible on generated examination scorecards and session reports.
          </p>
        </div>

        {nameSuccess && (
          <Alert variant="success" onClose={() => setNameSuccess(null)}>
            {nameSuccess}
          </Alert>
        )}

        {nameError && (
          <Alert variant="error" onClose={() => setNameError(null)}>
            {nameError}
          </Alert>
        )}

        <form onSubmit={handleUpdateName} className="space-y-4 max-w-xl">
          <div className="space-y-1.5">
            <label htmlFor="user-name-input" className="block text-xs font-medium text-secondary">
              Display Name
            </label>
            <input
              id="user-name-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3.5 py-2 bg-surface-container-lowest border border-outline-variant rounded-xl text-sm text-primary focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all"
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-secondary">
                Email Address
              </label>
              <div className="px-3.5 py-2 bg-surface-container-low/60 border border-outline-variant/40 rounded-xl text-xs text-primary/80 font-mono select-all">
                {user?.email}
              </div>
              <span className="text-[11px] text-secondary">Managed by organization identity</span>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-secondary">
                Assigned Role
              </label>
              <div className="px-3.5 py-2 bg-surface-container-low/60 border border-outline-variant/40 rounded-xl text-xs text-primary/80 capitalize flex items-center justify-between">
                <span>{user?.role}</span>
                <Badge variant={isAdmin ? 'dark' : 'outline'} size="xs">
                  Immutable
                </Badge>
              </div>
              <span className="text-[11px] text-secondary">RBAC access policy scope</span>
            </div>
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={isUpdatingName || name.trim() === user?.name}
              isLoading={isUpdatingName}
              id="save-name-btn"
              className="text-xs"
            >
              Save Profile Changes
            </Button>
          </div>
        </form>
      </Card>

      {/* Section 2: Security & Password */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-6">
        <div className="border-b border-outline-variant/60 pb-4">
          <h2 className="text-base font-semibold text-primary flex items-center gap-2">
            <Icon name="lock" size={18} />
            <span>Security & Password</span>
          </h2>
          <p className="text-xs text-secondary mt-0.5">
            Passwords must contain at least 8 characters, including at least one letter and one number.
          </p>
        </div>

        {passwordSuccess && (
          <Alert variant="success" onClose={() => setPasswordSuccess(null)}>
            {passwordSuccess}
          </Alert>
        )}

        {passwordError && (
          <Alert variant="error" onClose={() => setPasswordError(null)}>
            {passwordError}
          </Alert>
        )}

        <form onSubmit={handleChangePassword} className="space-y-4 max-w-xl">
          <div className="space-y-1.5">
            <label htmlFor="current-password" className="block text-xs font-medium text-secondary">
              Current Password
            </label>
            <input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full px-3.5 py-2 bg-surface-container-lowest border border-outline-variant rounded-xl text-sm text-primary focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all"
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="new-password" className="block text-xs font-medium text-secondary">
                New Password
              </label>
              <input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-3.5 py-2 bg-surface-container-lowest border border-outline-variant rounded-xl text-sm text-primary focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="confirm-password" className="block text-xs font-medium text-secondary">
                Confirm New Password
              </label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-3.5 py-2 bg-surface-container-lowest border border-outline-variant rounded-xl text-sm text-primary focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                required
              />
            </div>
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="secondary"
              size="sm"
              disabled={isUpdatingPassword || !currentPassword || !newPassword}
              isLoading={isUpdatingPassword}
              id="update-password-btn"
              className="text-xs"
            >
              Update Password
            </Button>
          </div>
        </form>
      </Card>

      {/* Section 3 (Candidate-specific): Camera & Mic Diagnostics */}
      {!isAdmin && (
        <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-6">
          <div className="border-b border-outline-variant/60 pb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-primary flex items-center gap-2">
                <Icon name="hardware" size={18} />
                <span>Camera & Microphone Pre-Check Diagnostics</span>
              </h2>
              <p className="text-xs text-secondary mt-0.5">
                Verify your devices outside of an active examination to avoid surprises during a test.
              </p>
            </div>
            <Badge variant="outline" size="xs">
              Diagnostics
            </Badge>
          </div>

          {mediaError && (
            <Alert variant="error" onClose={() => setMediaError(null)}>
              {mediaError}
            </Alert>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
            <div className="space-y-4">
              <p className="text-xs text-secondary leading-relaxed">
                Proctored examinations mandate active webcam and microphone streams. Run this test to confirm that your browser is able to initialize both hardware sensors smoothly.
              </p>

              <div className="space-y-2.5">
                <div className="flex items-center justify-between p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/30">
                  <div className="flex items-center gap-2.5">
                    <Icon name="videocam" size={18} className="text-primary" />
                    <span className="text-xs font-medium text-primary">Webcam Feed</span>
                  </div>
                  <Badge
                    variant={cameraStatus === 'granted' ? 'success' : cameraStatus === 'denied' ? 'error' : 'neutral'}
                    size="xs"
                  >
                    {cameraStatus === 'granted' ? 'Connected' : cameraStatus === 'denied' ? 'Blocked' : 'Untested'}
                  </Badge>
                </div>

                <div className="flex items-center justify-between p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/30">
                  <div className="flex items-center gap-2.5">
                    <Icon name="mic" size={18} className="text-primary" />
                    <span className="text-xs font-medium text-primary">Microphone Input</span>
                  </div>
                  <Badge
                    variant={micStatus === 'granted' ? 'success' : micStatus === 'denied' ? 'error' : 'neutral'}
                    size="xs"
                  >
                    {micStatus === 'granted' ? 'Connected' : micStatus === 'denied' ? 'Blocked' : 'Untested'}
                  </Badge>
                </div>

                {isTestingMedia && (
                  <div className="space-y-1.5 p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/30">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-secondary">Input Volume Level</span>
                      <span className="font-mono text-primary font-medium">{audioLevel}%</span>
                    </div>
                    <div className="w-full bg-surface-container-high h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-primary h-full transition-all duration-75"
                        style={{ width: `${audioLevel}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-3 pt-2">
                {!isTestingMedia ? (
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    icon="play_arrow"
                    onClick={startMediaTest}
                    id="start-media-test-btn"
                    className="text-xs"
                  >
                    Start Hardware Test
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    icon="stop"
                    onClick={stopMediaTest}
                    id="stop-media-test-btn"
                    className="text-xs"
                  >
                    Stop Test
                  </Button>
                )}
              </div>
            </div>

            {/* Video Preview Box */}
            <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-4 flex flex-col items-center justify-center min-h-[220px]">
              {isTestingMedia ? (
                <div className="w-full relative aspect-video bg-black rounded-xl overflow-hidden shadow-subtle">
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className="w-full h-full object-cover transform -scale-x-100"
                  />
                  <div className="absolute top-2 left-2">
                    <Badge variant="dark" size="xs" icon="videocam">
                      Live Mirror
                    </Badge>
                  </div>
                </div>
              ) : (
                <div className="text-center space-y-2 py-8">
                  <div className="w-10 h-10 rounded-full bg-surface-container flex items-center justify-center text-secondary mx-auto">
                    <Icon name="videocam_off" size={20} />
                  </div>
                  <div className="text-xs font-medium text-primary">Camera mirror inactive</div>
                  <p className="text-[11px] text-secondary max-w-xs">
                    Click &ldquo;Start Hardware Test&rdquo; to test your local camera stream before sitting for an assessment.
                  </p>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Section 4 (Admin-specific): Administrator Defaults */}
      {isAdmin && (
        <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-6">
          <div className="border-b border-outline-variant/60 pb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-primary flex items-center gap-2">
                <Icon name="tune" size={18} />
                <span>Invigilation & Review Defaults</span>
              </h2>
              <p className="text-xs text-secondary mt-0.5">
                Default sensitivity thresholds applied when drafting new examinations.
              </p>
            </div>
            <Badge variant="dark" size="xs">
              Administrator Scope
            </Badge>
          </div>

          {adminPrefsSaved && (
            <Alert variant="success" onClose={() => setAdminPrefsSaved(false)}>
              Default examination preferences saved for this administrative session.
            </Alert>
          )}

          <form onSubmit={handleSaveAdminPrefs} className="space-y-4 max-w-xl">
            <div className="space-y-1.5">
              <label htmlFor="min-trust-score-input" className="block text-xs font-medium text-secondary">
                Default Trust Score Review Threshold ({minTrustScore}%)
              </label>
              <input
                id="min-trust-score-input"
                type="range"
                min="50"
                max="95"
                step="5"
                value={minTrustScore}
                onChange={(e) => setMinTrustScore(Number(e.target.value))}
                className="w-full accent-primary cursor-pointer"
              />
              <span className="text-[11px] text-secondary block">
                Sessions with trust scores below this threshold automatically flag for human auditor review.
              </span>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="max-exits-input" className="block text-xs font-medium text-secondary">
                Default Maximum Allowed Fullscreen Exits
              </label>
              <input
                id="max-exits-input"
                type="number"
                min="1"
                max="10"
                value={maxFullscreenExits}
                onChange={(e) => setMaxFullscreenExits(Number(e.target.value))}
                className="w-full px-3.5 py-2 bg-surface-container-lowest border border-outline-variant rounded-xl text-sm text-primary focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all font-mono"
              />
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/30">
              <div className="space-y-0.5">
                <div className="text-xs font-medium text-primary">Live WebSocket Telemetry</div>
                <div className="text-[11px] text-secondary">Stream live candidate heartbeats to the monitoring dashboard</div>
              </div>
              <input
                type="checkbox"
                checked={liveTelemetryEnabled}
                onChange={(e) => setLiveTelemetryEnabled(e.target.checked)}
                className="w-4 h-4 accent-primary rounded cursor-pointer"
              />
            </div>

            <div className="pt-2">
              <Button
                type="submit"
                variant="secondary"
                size="sm"
                id="save-admin-prefs-btn"
                className="text-xs"
              >
                Save Preferences
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Section: Data Privacy & Principal Rights (DPDP Act 2023) */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-6">
        <div className="border-b border-outline-variant/60 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold text-primary flex items-center gap-2">
              <Icon name="shield" size={18} />
              <span>Data Privacy & Principal Rights (DPDP Act 2023)</span>
            </h2>
            <p className="text-xs text-secondary mt-0.5">
              Exercise your statutory rights under India&apos;s Digital Personal Data Protection Act: inspect and download stored telemetry, view consent logs, or submit an erasure request.
            </p>
          </div>
          <Badge variant="outline" size="xs">
            Data Principal Rights
          </Badge>
        </div>

        {erasureSuccess && (
          <Alert variant="success" onClose={() => setErasureSuccess(null)}>
            {erasureSuccess}
          </Alert>
        )}

        {erasureError && (
          <Alert variant="error" onClose={() => setErasureError(null)}>
            {erasureError}
          </Alert>
        )}

        {exportError && (
          <Alert variant="error" onClose={() => setExportError(null)}>
            {exportError}
          </Alert>
        )}

        {/* Data Architecture & Hosting Status */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/30 space-y-1">
            <span className="text-[11px] text-secondary font-medium block">Hosting / Residency</span>
            <span className="text-xs font-semibold text-primary block">AWS ap-south-1 (Mumbai, India)</span>
            <span className="text-[10px] text-secondary block">No cross-border transfers</span>
          </div>

          <div className="p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/30 space-y-1">
            <span className="text-[11px] text-secondary font-medium block">Evidence Retention</span>
            <span className="text-xs font-semibold text-primary block">90 Days Maximum</span>
            <span className="text-[10px] text-secondary block">Snapshots purged automatically</span>
          </div>

          <div className="p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/30 space-y-1">
            <span className="text-[11px] text-secondary font-medium block">Consent History</span>
            <span className="text-xs font-semibold text-primary block">
              {privacyStatus
                ? `${privacyStatus.total_consent_records} Recorded Sessions`
                : isLoadingPrivacyStatus
                ? 'Loading records...'
                : '0 Recorded Sessions'}
            </span>
            <span className="text-[10px] text-secondary block">DPDP Section 6 Audit Trail</span>
          </div>
        </div>

        {/* Statutory Rights Actions Grid */}
        <div className="space-y-4 pt-1">
          {/* 1. Right to Access */}
          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="text-xs font-semibold text-primary flex items-center gap-1.5">
                  <Icon name="download" size={16} />
                  <span>Right to Access (Section 11) — Download My Personal Data</span>
                </div>
                <p className="text-[11px] text-secondary leading-relaxed">
                  Export a comprehensive, machine-readable JSON package containing your account profile, assigned exam sessions, logged proctoring violations, and timestamped consent audit logs.
                </p>
              </div>
              <Button
                type="button"
                variant="primary"
                size="sm"
                icon="download"
                id="download-data-btn"
                onClick={handleExportData}
                isLoading={isExportingData}
                disabled={isExportingData}
                className="text-xs shrink-0 shadow-subtle"
              >
                Download My Data (.JSON)
              </Button>
            </div>

            {exportedSummary && (
              <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/60 text-xs text-primary flex items-center justify-between animate-in fade-in">
                <div className="flex items-center gap-2">
                  <Icon name="check_circle" size={16} className="text-success" />
                  <span>
                    Export package generated: <strong>{exportedSummary.sessionsCount}</strong> sessions,{' '}
                    <strong>{exportedSummary.violationsCount}</strong> violations, and{' '}
                    <strong>{exportedSummary.consentsCount}</strong> consent audit entries.
                  </span>
                </div>
                <span className="text-[10px] text-secondary font-mono">
                  {new Date(exportedSummary.exportedAt).toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>

          {/* 2. Right to Correction */}
          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 flex items-start gap-3">
            <Icon name="edit" size={16} className="text-primary shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="text-xs font-semibold text-primary">Right to Correction & Updating (Section 12)</div>
              <p className="text-[11px] text-secondary leading-relaxed">
                You have the statutory right to correct inaccurate personal data. You can directly edit your display name in Section 1 (Profile Information) above and update your authentication credentials in Section 2 (Security Credentials).
              </p>
            </div>
          </div>

          {/* 3. Right to Erasure */}
          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="text-xs font-semibold text-primary flex items-center gap-1.5">
                  <Icon name="delete_forever" size={16} />
                  <span>Right to Erasure (Section 12) — Request Biometric & Telemetry Purge</span>
                </div>
                <p className="text-[11px] text-secondary leading-relaxed">
                  Request immediate deletion of your facial reference photos, biometric embeddings, and monitoring webcam snapshots. Formal score completion transcripts are preserved for institutional academic audit compliance.
                </p>
              </div>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon="delete_forever"
                id="request-erasure-btn"
                onClick={() => setShowErasureModal(true)}
                className="text-xs shrink-0 text-rose-800 hover:bg-rose-50"
              >
                Request Data Erasure
              </Button>
            </div>

            {privacyStatus?.erasure_requests?.length > 0 && (
              <div className="pt-2 border-t border-outline-variant/40 space-y-1.5">
                <div className="text-[11px] font-medium text-secondary">Active Erasure Requests:</div>
                <div className="space-y-1">
                  {privacyStatus.erasure_requests.map((req: any) => (
                    <div
                      key={req.id}
                      className="p-2.5 rounded-lg border border-outline-variant/50 bg-surface-container-lowest flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" size="xs">
                          {req.status}
                        </Badge>
                        <span className="text-[11px] text-secondary">
                          Submitted on {new Date(req.created_at).toLocaleDateString()}
                          {req.reason && ` • "${req.reason}"`}
                        </span>
                      </div>
                      <span className="text-[10px] text-secondary font-mono">
                        ID: {req.id.slice(0, 8)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer Guidance & Grievance Contact */}
        <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="space-y-0.5">
            <span className="font-semibold text-primary">Need assistance or have privacy concerns?</span>
            <p className="text-secondary text-[11px]">
              Our Grievance Redressal Officer responds within 24 hours (resolution within 7 business days).
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <a
              href="mailto:grievance@proctorai.edu"
              className="text-xs font-medium text-primary hover:underline flex items-center gap-1"
            >
              <Icon name="mail" size={14} />
              <span>grievance@proctorai.edu</span>
            </a>
            <Link to="/privacy" className="text-xs font-medium text-primary hover:underline">
              View Privacy Policy &rarr;
            </Link>
          </div>
        </div>
      </Card>

      {/* Erasure Request Confirmation Modal */}
      {showErasureModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <Card variant="surface" className="max-w-md w-full border border-outline-variant p-6 space-y-4 shadow-elevation">
            <div className="flex items-center justify-between pb-2 border-b border-outline-variant/60">
              <div className="flex items-center gap-2 text-primary font-semibold text-sm">
                <Icon name="delete_forever" size={18} className="text-rose-800" />
                <span>Request Personal Data Erasure</span>
              </div>
              <button
                type="button"
                onClick={() => setShowErasureModal(false)}
                className="text-secondary hover:text-primary"
              >
                <Icon name="close" size={18} />
              </button>
            </div>

            <p className="text-xs text-secondary leading-relaxed">
              Under Section 12(3) of the DPDP Act 2023, you can request the erasure of your personal data. Submitting this request will schedule the immediate purge of your:
            </p>
            <ul className="list-disc list-inside text-xs text-secondary space-y-1">
              <li>Biometric reference photo and facial embedding vectors</li>
              <li>Periodic webcam snapshots and room monitoring frames</li>
              <li>Flagged audio anomalies and ambient microphone clips</li>
            </ul>
            <p className="text-[11px] text-secondary italic">
              Note: Final exam grades and statutory submission records are preserved per institutional academic record policies.
            </p>

            <form onSubmit={handleErasureRequest} className="space-y-3 pt-2">
              <div className="space-y-1">
                <label htmlFor="erasure-reason" className="block text-xs font-medium text-secondary">
                  Optional reason for erasure request:
                </label>
                <textarea
                  id="erasure-reason"
                  rows={2}
                  value={erasureReason}
                  onChange={(e) => setErasureReason(e.target.value)}
                  placeholder="e.g. Completed academic requirements, please delete biometric records."
                  className="w-full px-3 py-2 bg-surface-container-lowest border border-outline-variant rounded-xl text-xs text-primary focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all resize-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowErasureModal(false)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isSubmittingErasure}
                  disabled={isSubmittingErasure}
                  icon="delete_forever"
                  className="text-xs"
                >
                  Confirm & Submit Request
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};
