import React, { useState } from 'react';
import { Link, useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { UserRole } from '../types';
import { Button, Icon, Alert } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export const Signup: React.FC = () => {
  useDocumentTitle('Create Account', 'Register a candidate or administrator account on ProctorAI.');
  const { signup, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  // If already authenticated, redirect to role dashboard
  if (isAuthenticated) {
    return <Navigate to={user?.role === 'admin' ? '/admin/exams' : '/dashboard'} replace />;
  }

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>('candidate');
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [privacyAgreed, setPrivacyAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!ageConfirmed) {
      setError('You must confirm you are at least 18 years of age. Under Section 9 of the DPDP Act 2023, Proctor AI is strictly scoped for adult candidates.');
      return;
    }
    if (!privacyAgreed) {
      setError('You must review and agree to the Privacy Policy.');
      return;
    }

    setIsSubmitting(true);

    try {
      await signup(name, email, password, role);
      navigate('/');
    } catch (err: any) {
      setError(
        err.response?.data?.detail || 'Registration failed. Please check the requirements.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto my-8 sm:my-14 px-4 sm:px-6">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
        {/* Left Side: Product Information & Role Clarification Panel */}
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
                Join thousands of students, candidates, and educators in an automated, highly secure testing environment.
              </p>
            </div>

            {/* Core Value Highlights */}
            <div className="space-y-3.5 pt-1">
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="videocam" size={16} />
                </div>
                <div>
                  <div className="text-xs font-semibold text-primary">Real-time video and audio monitoring</div>
                  <div className="text-[11px] text-secondary mt-0.5 leading-relaxed">
                    Automated browser security and live audio/video telemetry.
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
                    Sandboxed evaluation for multi-language coding and multiple-choice tests.
                  </div>
                </div>
              </div>
            </div>

            {/* Account Types Guidance */}
            <div className="p-4 rounded-xl bg-surface-container/60 border border-outline-variant/60 space-y-2.5">
              <div className="text-xs font-semibold text-primary flex items-center gap-1.5">
                <Icon name="info" size={14} className="text-secondary" />
                Choosing your account type
              </div>
              <div className="space-y-2 text-[11px]">
                <div>
                  <span className="font-semibold text-primary">Candidate:</span>{' '}
                  <span className="text-secondary">Take assigned examinations, run system readiness checks, and view verified transcripts.</span>
                </div>
                <div>
                  <span className="font-semibold text-primary">Administrator:</span>{' '}
                  <span className="text-secondary">Create exams, configure security rules, monitor candidate sessions, and perform forensic audits.</span>
                </div>
              </div>
            </div>
          </div>

          <div className="pt-6 mt-6 border-t border-outline-variant/50 flex items-center gap-2 text-[11px] text-secondary">
            <Icon name="verified_user" size={15} className="text-primary shrink-0" />
            <span>Institutional-grade security • WCAG AA accessible</span>
          </div>
        </div>

        {/* Right Side: Account Registration Form Card */}
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
                Create your account
              </h1>
              <p className="text-xs text-secondary mt-1">
                Sign up as a candidate or administrator to access the assessment portal.
              </p>
            </div>

            {error && (
              <div className="mb-5">
                <Alert variant="error" onClose={() => setError(null)}>
                  {error}
                </Alert>
              </div>
            )}

            <form onSubmit={handleSubmit} id="signup-form" className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-secondary mb-1.5" htmlFor="signup-name">
                  Full name
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary flex items-center">
                    <Icon name="person" size={16} />
                  </span>
                  <input
                    id="signup-name"
                    type="text"
                    className="w-full rounded-xl bg-surface-container-low/40 border border-outline-variant/70 pl-9 pr-3.5 py-2.5 text-xs text-primary placeholder:text-secondary/50 focus:outline-none focus:border-primary transition-colors"
                    placeholder="Alex Morgan"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-secondary mb-1.5" htmlFor="signup-email">
                  Email address
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary flex items-center">
                    <Icon name="mail" size={16} />
                  </span>
                  <input
                    id="signup-email"
                    type="email"
                    className="w-full rounded-xl bg-surface-container-low/40 border border-outline-variant/70 pl-9 pr-3.5 py-2.5 text-xs text-primary placeholder:text-secondary/50 focus:outline-none focus:border-primary transition-colors"
                    placeholder="candidate@university.edu"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-secondary mb-1.5" htmlFor="signup-password">
                  Password
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary flex items-center">
                    <Icon name="lock" size={16} />
                  </span>
                  <input
                    id="signup-password"
                    type="password"
                    className="w-full rounded-xl bg-surface-container-low/40 border border-outline-variant/70 pl-9 pr-3.5 py-2.5 text-xs text-primary placeholder:text-secondary/50 focus:outline-none focus:border-primary transition-colors"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
                <span className="text-[11px] text-secondary mt-1 block">
                  Must be at least 8 characters with at least 1 letter and 1 number.
                </span>
              </div>

              <div>
                <label className="block text-xs font-medium text-secondary mb-1.5" htmlFor="signup-role">
                  Account type
                </label>
                <select
                  id="signup-role"
                  className="w-full rounded-xl bg-surface-container-low/40 border border-outline-variant/70 px-3.5 py-2.5 text-xs text-primary focus:outline-none focus:border-primary transition-colors cursor-pointer"
                  value={role}
                  onChange={(e) => setRole(e.target.value as UserRole)}
                >
                  <option value="candidate">Candidate (taking exams)</option>
                  <option value="admin">Administrator (managing exams)</option>
                </select>
              </div>

              {/* DPDP Section 9 Age Confirmation & Privacy Agreement */}
              <div className="space-y-2.5 pt-2 border-t border-outline-variant/50">
                <label className="flex items-start gap-2.5 cursor-pointer text-xs text-secondary group">
                  <input
                    type="checkbox"
                    id="signup-age-confirm"
                    checked={ageConfirmed}
                    onChange={(e) => setAgeConfirmed(e.target.checked)}
                    className="mt-0.5 rounded border-outline-variant text-primary focus:ring-primary h-4 w-4 shrink-0 cursor-pointer"
                  />
                  <span className="leading-relaxed">
                    I confirm that I am <strong className="text-primary font-medium">18 years of age or older</strong>. Proctor AI is strictly scoped for adult candidates under DPDP Act 2023 (Section 9).
                  </span>
                </label>

                <label className="flex items-start gap-2.5 cursor-pointer text-xs text-secondary group">
                  <input
                    type="checkbox"
                    id="signup-privacy-confirm"
                    checked={privacyAgreed}
                    onChange={(e) => setPrivacyAgreed(e.target.checked)}
                    className="mt-0.5 rounded border-outline-variant text-primary focus:ring-primary h-4 w-4 shrink-0 cursor-pointer"
                  />
                  <span className="leading-relaxed">
                    I have read and agree to the <Link to="/privacy" target="_blank" className="text-primary font-medium underline">Privacy Policy & DPDP Notice</Link>, and acknowledge the 90-day evidence retention schedule.
                  </span>
                </label>
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  id="submit-signup-btn"
                  disabled={!ageConfirmed || !privacyAgreed || isSubmitting}
                  isLoading={isSubmitting}
                  className="w-full text-xs font-medium shadow-subtle"
                  icon="arrow_forward"
                  iconPosition="right"
                >
                  Create account
                </Button>
              </div>
            </form>
          </div>

          <div className="text-center mt-6 pt-4 border-t border-outline-variant/40">
            <p className="text-xs text-secondary">
              Already have an account?{' '}
              <Link
                to="/login"
                id="go-to-login-link"
                className="text-primary font-medium hover:underline"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
