import React, { useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button, Badge, Icon, StatusDot } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export const Home: React.FC = () => {
  useDocumentTitle(
    'ProctorAI — Secure Online Examination Platform',
    'Remote examinations with real-time integrity monitoring, in-browser coding assessments, and automated scoring.'
  );

  const { isAuthenticated, user, isLoading } = useAuth();
  const [activeAudienceTab, setActiveAudienceTab] = useState<'candidate' | 'institution'>('candidate');

  // Redirect authenticated users to their corresponding dashboard
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to={user?.role === 'admin' ? '/admin/exams' : '/dashboard'} replace />;
  }

  return (
    <div className="space-y-16 pb-12">
      {/* 1. Hero Section */}
      <section className="relative pt-6 md:pt-12 text-center max-w-4xl mx-auto space-y-6">
        {/* Subtle dot-grid texture & ambient glow behind hero */}
        <div className="pointer-events-none absolute inset-0 -top-8 -z-10 overflow-hidden">
          <div className="hero-dot-grid absolute inset-0 opacity-60" />
          <div className="hero-radial-glow absolute inset-0" />
        </div>

        {/* Understated Status Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-zinc-200/80 bg-white/80 backdrop-blur-sm text-[11px] sm:text-xs text-zinc-600 shadow-xs">
          <StatusDot variant="emerald" ping />
          <span className="font-medium text-zinc-900">Automated Exam Integrity</span>
          <span className="text-zinc-300">•</span>
          <span className="text-zinc-500">Multi-signal proctoring & instant evaluation</span>
        </div>

        {/* Primary Headline with tracking-[-0.025em] */}
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-semibold tracking-[-0.025em] text-zinc-900 leading-[1.14] sm:leading-[1.16]">
          Secure online exams, <br className="hidden sm:inline" />
          proctored end to end.
        </h1>

        {/* Subheading with text-zinc-500 */}
        <p className="text-base sm:text-lg text-zinc-500 max-w-2xl mx-auto leading-relaxed">
          Remote assessments with real-time integrity monitoring — including camera,
          audio, and browser focus tracking — plus built-in multiple-choice and
          hands-on coding evaluations.
        </p>

        {/* Hero CTAs */}
        <div className="flex flex-wrap items-center justify-center gap-3 pt-3">
          <Link to="/signup">
            <Button
              variant="primary"
              size="lg"
              icon="arrow_forward"
              iconPosition="right"
              id="hero-create-account-btn"
            >
              Create account
            </Button>
          </Link>
          <Link to="/login">
            <Button
              variant="secondary"
              size="lg"
              icon="login"
              id="hero-sign-in-btn"
            >
              Sign in
            </Button>
          </Link>
        </div>

        {/* Interactive Experience Preview Mock */}
        <div className="pt-8">
          <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg shadow-subtle overflow-hidden text-left">
            {/* Window Top Bar */}
            <div className="px-5 py-3 border-b border-outline-variant/60 bg-surface-container-low flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div className="flex gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-outline-variant" />
                  <span className="w-2.5 h-2.5 rounded-full bg-outline-variant" />
                  <span className="w-2.5 h-2.5 rounded-full bg-outline-variant" />
                </div>
                <span className="font-medium text-secondary ml-2">
                  Proctored Assessment Session
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="telemetry-beacon shrink-0" />
                <span className="font-mono text-[11px] text-secondary">
                  Live Monitoring Active
                </span>
              </div>
            </div>

            {/* Split Preview Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-outline-variant/60">
              {/* Question & Assessment Area */}
              <div className="lg:col-span-2 p-6 space-y-4">
                <div className="flex items-center justify-between text-xs text-secondary">
                  <span className="font-medium text-primary">Question 3 of 12</span>
                  <span>Time Remaining: 42:15</span>
                </div>
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-primary">
                    Two Sum Problem (Coding Assessment)
                  </h3>
                  <p className="text-xs text-secondary leading-relaxed">
                    Given an array of integers <code className="px-1.5 py-0.5 rounded bg-surface-container text-primary font-mono text-[11px]">nums</code> and an integer <code className="px-1.5 py-0.5 rounded bg-surface-container text-primary font-mono text-[11px]">target</code>, return indices of the two numbers such that they add up to target.
                  </p>
                </div>

                <div className="p-3.5 rounded-md bg-surface-container font-mono text-xs text-primary leading-relaxed border border-outline-variant/50">
                  <div className="text-secondary mb-1"># In-browser execution with real-time test verification</div>
                  <div><span className="text-secondary">def</span> <span className="font-semibold">two_sum</span>(nums: list[int], target: int) -&gt; list[int]:</div>
                  <div className="pl-4">seen = &#123;&#125;</div>
                  <div className="pl-4">for i, num in enumerate(nums):</div>
                  <div className="pl-8">diff = target - num</div>
                  <div className="pl-8">if diff in seen: return [seen[diff], i]</div>
                  <div className="pl-8">seen[num] = i</div>
                  <div className="pl-4">return []</div>
                </div>

                <div className="flex items-center gap-2 pt-1 text-xs">
                  <Badge variant="dark" size="xs" icon="check_circle">
                    All 4 Test Cases Passed
                  </Badge>
                  <span className="text-secondary text-[11px]">Execution time: 48ms</span>
                </div>
              </div>

              {/* Integrity Telemetry Sidebar */}
              <div className="p-6 bg-surface-container-low/30 space-y-4">
                <div className="text-xs font-semibold text-primary flex items-center justify-between">
                  <span>Proctoring Signals</span>
                  <Badge variant="neutral" size="xs">
                    Score: 98 / 100
                  </Badge>
                </div>

                <div className="space-y-2.5 text-xs">
                  <div className="p-2.5 rounded-md bg-surface-container-lowest border border-outline-variant/60 flex items-center justify-between">
                    <span className="text-secondary flex items-center gap-2">
                      <Icon name="videocam" size={16} className="text-primary" />
                      Camera Presence
                    </span>
                    <span className="text-primary font-medium">Single Face</span>
                  </div>

                  <div className="p-2.5 rounded-md bg-surface-container-lowest border border-outline-variant/60 flex items-center justify-between">
                    <span className="text-secondary flex items-center gap-2">
                      <Icon name="mic" size={16} className="text-primary" />
                      Ambient Audio
                    </span>
                    <span className="text-primary font-medium">Quiet Room</span>
                  </div>

                  <div className="p-2.5 rounded-md bg-surface-container-lowest border border-outline-variant/60 flex items-center justify-between">
                    <span className="text-secondary flex items-center gap-2">
                      <Icon name="fullscreen" size={16} className="text-primary" />
                      Fullscreen Lock
                    </span>
                    <span className="text-primary font-medium">Locked</span>
                  </div>

                  <div className="p-2.5 rounded-md bg-surface-container-lowest border border-outline-variant/60 flex items-center justify-between">
                    <span className="text-secondary flex items-center gap-2">
                      <Icon name="tab" size={16} className="text-primary" />
                      Tab Focus
                    </span>
                    <span className="text-primary font-medium">Focused (0 exits)</span>
                  </div>
                </div>

                <p className="text-[11px] text-secondary leading-tight pt-1">
                  Integrity telemetry is evaluated server-side throughout active sessions.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. How It Works Section */}
      <section id="how-it-works" className="space-y-8 max-w-5xl mx-auto scroll-mt-24">
        <div className="text-center space-y-2">
          <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-primary">
            How ProctorAI works
          </h2>
          <p className="text-sm sm:text-base text-secondary max-w-xl mx-auto">
            A transparent and respectful workflow designed for both candidates and evaluators.
          </p>
        </div>

        {/* Audience Toggle Tabs */}
        <div className="text-center">
          <div className="inline-flex p-1 rounded-full border border-outline-variant/70 bg-surface-container-low mt-4">
            <button
              type="button"
              onClick={() => setActiveAudienceTab('candidate')}
              className={`px-5 py-1.5 rounded-full text-xs font-medium transition-all ${
                activeAudienceTab === 'candidate'
                  ? 'bg-primary text-on-primary shadow-subtle'
                  : 'text-secondary hover:text-primary'
              }`}
            >
              For Candidates
            </button>
            <button
              type="button"
              onClick={() => setActiveAudienceTab('institution')}
              className={`px-5 py-1.5 rounded-full text-xs font-medium transition-all ${
                activeAudienceTab === 'institution'
                  ? 'bg-primary text-on-primary shadow-subtle'
                  : 'text-secondary hover:text-primary'
              }`}
            >
              For Institutions & Admins
            </button>
          </div>
        </div>

        {/* Audience Content */}
        {activeAudienceTab === 'candidate' ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-6 shadow-subtle space-y-3">
              <div className="w-8 h-8 rounded-md bg-surface-container flex items-center justify-center text-primary font-semibold text-xs">
                1
              </div>
              <h3 className="text-sm font-semibold text-primary">Pre-exam system check</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Complete a guided 30-second check to confirm your camera, microphone, and browser permissions are configured correctly.
              </p>
            </div>

            <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-6 shadow-subtle space-y-3">
              <div className="w-8 h-8 rounded-md bg-surface-container flex items-center justify-center text-primary font-semibold text-xs">
                2
              </div>
              <h3 className="text-sm font-semibold text-primary">Take your assessment</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Work through multiple-choice and coding questions in a clean, distraction-free interface with clear countdown timers.
              </p>
            </div>

            <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-6 shadow-subtle space-y-3">
              <div className="w-8 h-8 rounded-md bg-surface-container flex items-center justify-center text-primary font-semibold text-xs">
                3
              </div>
              <h3 className="text-sm font-semibold text-primary">Instant automated results</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Receive immediate confirmation upon submission, with objective test case scoring and performance breakdown.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-6 shadow-subtle space-y-3">
              <div className="w-8 h-8 rounded-md bg-surface-container flex items-center justify-center text-primary font-semibold text-xs">
                1
              </div>
              <h3 className="text-sm font-semibold text-primary">Create assessments</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Build mixed exams with multiple-choice questions and real coding challenges supporting multiple programming languages.
              </p>
            </div>

            <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-6 shadow-subtle space-y-3">
              <div className="w-8 h-8 rounded-md bg-surface-container flex items-center justify-center text-primary font-semibold text-xs">
                2
              </div>
              <h3 className="text-sm font-semibold text-primary">Monitor live sessions</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Track candidate progress in real time with continuous telemetry updates and automated violation detection.
              </p>
            </div>

            <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-6 shadow-subtle space-y-3">
              <div className="w-8 h-8 rounded-md bg-surface-container flex items-center justify-center text-primary font-semibold text-xs">
                3
              </div>
              <h3 className="text-sm font-semibold text-primary">Objective review & audit</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Review sessions flagged with low trust scores, inspect timestamped incident evidence, and run anti-cheat similarity scans.
              </p>
            </div>
          </div>
        )}
      </section>

      {/* 3. Core Features Section */}
      <section id="features" className="space-y-8 max-w-5xl mx-auto scroll-mt-24">
        <div className="text-center space-y-2">
          <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-primary">
            Built for assessment integrity
          </h2>
          <p className="text-sm sm:text-base text-secondary max-w-xl mx-auto">
            Practical safeguards that protect exam credibility without creating unnecessary friction for candidates.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Card 1 */}
          <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-6 md:p-7 shadow-subtle flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="w-9 h-9 rounded-md bg-surface-container flex items-center justify-center text-primary">
                <Icon name="videocam" size={20} />
              </div>
              <h3 className="text-base font-semibold text-primary">
                Live Video & Audio Verification
              </h3>
              <p className="text-xs sm:text-sm text-secondary leading-relaxed">
                Periodic visual presence checks verify candidate identity and ensure no secondary individuals are present. Calibrated audio monitoring detects sustained background conversation.
              </p>
            </div>
            <div className="pt-2 flex flex-wrap gap-2 text-[11px] text-secondary">
              <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/50">Face presence checks</span>
              <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/50">Ambient noise analysis</span>
            </div>
          </div>

          {/* Card 2 */}
          <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-6 md:p-7 shadow-subtle flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="w-9 h-9 rounded-md bg-surface-container flex items-center justify-center text-primary">
                <Icon name="tab" size={20} />
              </div>
              <h3 className="text-base font-semibold text-primary">
                Browser Focus & Deterrents
              </h3>
              <p className="text-xs sm:text-sm text-secondary leading-relaxed">
                Enforced fullscreen mode and focus tracking record any navigation away from the exam tab. Rapid clipboard paste events are monitored to deter unauthorized external copy-pasting.
              </p>
            </div>
            <div className="pt-2 flex flex-wrap gap-2 text-[11px] text-secondary">
              <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/50">Fullscreen enforcement</span>
              <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/50">Tab-switch tracking</span>
            </div>
          </div>

          {/* Card 3 */}
          <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-6 md:p-7 shadow-subtle flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="w-9 h-9 rounded-md bg-surface-container flex items-center justify-center text-primary">
                <Icon name="code" size={20} />
              </div>
              <h3 className="text-base font-semibold text-primary">
                Integrated Coding Assessments
              </h3>
              <p className="text-xs sm:text-sm text-secondary leading-relaxed">
                Candidates write, execute, and debug code directly in the browser across Python, JavaScript, Java, and C++. Solutions are automatically graded against public and hidden test cases.
              </p>
            </div>
            <div className="pt-2 flex flex-wrap gap-2 text-[11px] text-secondary">
              <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/50">Isolated sandbox execution</span>
              <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/50">Automated test grading</span>
            </div>
          </div>

          {/* Card 4 */}
          <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-6 md:p-7 shadow-subtle flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="w-9 h-9 rounded-md bg-surface-container flex items-center justify-center text-primary">
                <Icon name="shield" size={20} />
              </div>
              <h3 className="text-base font-semibold text-primary">
                Real-Time Review & Trust Scoring
              </h3>
              <p className="text-xs sm:text-sm text-secondary leading-relaxed">
                A unified trust score synthesizes multiple behavioral signals into an objective confidence metric. Reviewers can inspect timestamped logs and mark benign incidents without unfair penalties.
              </p>
            </div>
            <div className="pt-2 flex flex-wrap gap-2 text-[11px] text-secondary">
              <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/50">Human-in-the-loop review</span>
              <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/50">Objective score calculation</span>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Trust & Credibility Section */}
      <section id="fairness" className="border border-outline-variant/70 bg-surface-container-lowest rounded-lg p-8 md:p-10 shadow-subtle max-w-5xl mx-auto space-y-6 scroll-mt-24">
        <div className="max-w-2xl space-y-2">
          <h2 className="text-xl sm:text-2xl font-semibold tracking-tight text-primary">
            Fairness, transparency, and data privacy
          </h2>
          <p className="text-xs sm:text-sm text-secondary leading-relaxed">
            Integrity monitoring should build confidence, not create anxiety. Our platform is designed with clear principles to respect candidate privacy while safeguarding academic standards.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-2">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-primary font-semibold text-xs">
              <Icon name="verified" size={16} />
              <span>Strict Server Validation</span>
            </div>
            <p className="text-xs text-secondary leading-relaxed">
              Timers, randomized question sequences, test cases, and scores are managed strictly server-side. Nothing relies on client trust.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2 text-primary font-semibold text-xs">
              <Icon name="supervisor_account" size={16} />
              <span>Human-in-the-Loop</span>
            </div>
            <p className="text-xs text-secondary leading-relaxed">
              Automated signals surface alerts for educator review rather than issuing automated disqualifications or expulsions.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2 text-primary font-semibold text-xs">
              <Icon name="lock" size={16} />
              <span>Session-Only Telemetry</span>
            </div>
            <p className="text-xs text-secondary leading-relaxed">
              Media permissions and telemetry are active exclusively during active exam windows and cease immediately when you submit.
            </p>
          </div>
        </div>
      </section>

      {/* 5. Final CTA Section */}
      <section className="border border-outline-variant/70 bg-surface-container-low rounded-lg p-8 md:p-12 text-center max-w-4xl mx-auto space-y-5 shadow-subtle">
        <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-primary">
          Ready to get started?
        </h2>
        <p className="text-xs sm:text-sm text-secondary max-w-md mx-auto leading-relaxed">
          Create an account to join scheduled assessments or sign in to access your administrative exam console.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link to="/signup">
            <Button
              variant="primary"
              size="lg"
              icon="arrow_forward"
              iconPosition="right"
              id="cta-create-account-btn"
              className="shadow-subtle"
            >
              Create account
            </Button>
          </Link>
          <Link to="/login">
            <Button
              variant="secondary"
              size="lg"
              icon="login"
              id="cta-sign-in-btn"
            >
              Sign in
            </Button>
          </Link>
        </div>
      </section>

      {/* 6. Footer */}
      <footer className="pt-8 border-t border-outline-variant/50 max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-secondary">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-md bg-primary text-on-primary flex items-center justify-center">
            <Icon name="verified_user" size={13} />
          </div>
          <span className="font-semibold text-primary">ProctorAI</span>
          <span className="text-outline-variant">•</span>
          <span>Secure online examination platform</span>
        </div>

        <div className="flex items-center gap-5">
          <Link to="/login" className="hover:text-primary transition-colors">
            Sign in
          </Link>
          <Link to="/signup" className="hover:text-primary transition-colors">
            Create account
          </Link>
          <a
            href="mailto:support@proctorai.edu"
            className="hover:text-primary transition-colors flex items-center gap-1"
          >
            <span>Support</span>
            <Icon name="open_in_new" size={12} />
          </a>
        </div>
      </footer>
    </div>
  );
};
