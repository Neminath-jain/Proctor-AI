import React, { useState } from 'react';
import { Link, useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button, Icon, Alert } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export const Login: React.FC = () => {
  useDocumentTitle('Sign In', 'Sign in to access your proctored examinations and candidate dashboard.');
  const { login, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  // If already authenticated, redirect to role dashboard
  if (isAuthenticated) {
    return <Navigate to={user?.role === 'admin' ? '/admin/exams' : '/dashboard'} replace />;
  }

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(email, password);
      navigate('/');
    } catch (err: any) {
      setError(
        err.response?.data?.detail || 'Authentication failed. Please check your credentials.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickFill = (presetEmail: string, presetPass: string) => {
    setEmail(presetEmail);
    setPassword(presetPass);
  };

  return (
    <div className="max-w-5xl mx-auto my-8 sm:my-14 px-4 sm:px-6">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
        {/* Left Side: Product Information Panel */}
        <div className="lg:col-span-5 flex flex-col justify-between p-6 sm:p-8 rounded-2xl bg-surface-container-low/50 border border-outline-variant/70">
          <div className="space-y-6">
            <div className="flex items-center gap-2">
              <span className="telemetry-beacon shrink-0" />
              <span className="text-xs font-semibold text-secondary tracking-tight">
                ProctorAI Assessment Platform
              </span>
            </div>

            <div>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-primary leading-snug">
                Secure, proctored exams for candidates and institutions
              </h2>
              <p className="text-xs text-secondary mt-2 leading-relaxed">
                An end-to-end evaluation environment engineered for academic integrity, automated code execution, and transparent proctoring.
              </p>
            </div>

            <div className="space-y-4 pt-2">
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="videocam" size={16} />
                </div>
                <div>
                  <div className="text-xs font-semibold text-primary">Real-time video and audio monitoring</div>
                  <div className="text-[11px] text-secondary mt-0.5 leading-relaxed">
                    AI-driven face tracking, multi-person detection, and ambient audio verification during active sessions.
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="code" size={16} />
                </div>
                <div>
                  <div className="text-xs font-semibold text-primary">Instant-graded MCQ and coding assessments</div>
                  <div className="text-[11px] text-secondary mt-0.5 leading-relaxed">
                    Integrated code runner supporting Python, JavaScript, and C++ with automated test case evaluation.
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="monitoring" size={16} />
                </div>
                <div>
                  <div className="text-xs font-semibold text-primary">Live integrity dashboard for administrators</div>
                  <div className="text-[11px] text-secondary mt-0.5 leading-relaxed">
                    Real-time candidate telemetry, deterministic trust scoring, and chronological incident audit review.
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="pt-6 mt-6 border-t border-outline-variant/50 flex items-center gap-2 text-[11px] text-secondary">
            <Icon name="verified_user" size={15} className="text-primary shrink-0" />
            <span>Institutional-grade security • WCAG AA accessible</span>
          </div>
        </div>

        {/* Right Side: Sign-in Form Card */}
        <div className="lg:col-span-7 border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 sm:p-8 shadow-subtle flex flex-col justify-between">
          <div>
            {/* Header with Understated Real-Time Status */}
            <div className="mb-6 pb-5 border-b border-outline-variant/60">
              <div className="flex items-center gap-2 mb-2">
                <span className="telemetry-beacon shrink-0" />
                <span className="text-xs font-medium text-secondary">
                  System operational
                </span>
              </div>
              <h1 className="text-2xl font-semibold tracking-tight text-primary">
                Sign in
              </h1>
              <p className="text-xs text-secondary mt-1">
                Enter your credentials to access your examinations and candidate portal.
              </p>
            </div>

            {error && (
              <div className="mb-5">
                <Alert variant="error" onClose={() => setError(null)}>
                  {error}
                </Alert>
              </div>
            )}

            <form onSubmit={handleSubmit} id="login-form" className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-secondary mb-1.5" htmlFor="login-email">
                  Email address
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary flex items-center">
                    <Icon name="mail" size={16} />
                  </span>
                  <input
                    id="login-email"
                    type="email"
                    className="w-full rounded-xl bg-surface-container-low/40 border border-outline-variant/70 pl-9 pr-3.5 py-2.5 text-xs text-primary placeholder:text-secondary/50 focus:outline-none focus:border-primary transition-colors"
                    placeholder="name@university.edu"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-secondary mb-1.5" htmlFor="login-password">
                  Password
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary flex items-center">
                    <Icon name="lock" size={16} />
                  </span>
                  <input
                    id="login-password"
                    type="password"
                    className="w-full rounded-xl bg-surface-container-low/40 border border-outline-variant/70 pl-9 pr-3.5 py-2.5 text-xs text-primary placeholder:text-secondary/50 focus:outline-none focus:border-primary transition-colors"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  id="submit-login-btn"
                  disabled={isSubmitting}
                  isLoading={isSubmitting}
                  className="w-full text-xs font-medium shadow-subtle"
                  icon="arrow_forward"
                  iconPosition="right"
                >
                  Sign in
                </Button>
              </div>
            </form>

            {/* Demo Credentials Helper */}
            <div className="mt-6 pt-5 border-t border-outline-variant/60">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-secondary">
                  Demo accounts
                </span>
                <span className="text-[11px] text-secondary">
                  Click to autofill
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => handleQuickFill('admin@example.com', 'Admin123!')}
                  id="quick-fill-admin"
                  className="p-2.5 rounded-xl border border-outline-variant/60 bg-surface-container-low/40 hover:bg-surface-container hover:border-primary/40 text-left transition-all group"
                >
                  <div className="text-xs font-medium text-primary flex items-center gap-1.5">
                    <Icon name="shield" size={13} className="text-secondary group-hover:text-primary transition-colors" />
                    Administrator
                  </div>
                  <div className="text-[11px] text-secondary mt-0.5 truncate">
                    admin@example.com
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleQuickFill('candidate@example.com', 'Candidate123!')}
                  id="quick-fill-candidate"
                  className="p-2.5 rounded-xl border border-outline-variant/60 bg-surface-container-low/40 hover:bg-surface-container hover:border-primary/40 text-left transition-all group"
                >
                  <div className="text-xs font-medium text-primary flex items-center gap-1.5">
                    <Icon name="person" size={13} className="text-secondary group-hover:text-primary transition-colors" />
                    Candidate
                  </div>
                  <div className="text-[11px] text-secondary mt-0.5 truncate">
                    candidate@example.com
                  </div>
                </button>
              </div>
            </div>
          </div>

          {/* Account Creation Link */}
          <div className="text-center mt-6 pt-4 border-t border-outline-variant/40">
            <p className="text-xs text-secondary">
              Don't have an account?{' '}
              <Link
                to="/signup"
                id="go-to-signup-link"
                className="text-primary font-medium hover:underline"
              >
                Create account
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
