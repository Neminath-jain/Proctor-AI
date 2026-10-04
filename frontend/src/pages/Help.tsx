import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, Badge, Button, Icon } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export const Help: React.FC = () => {
  useDocumentTitle('Help & Guidance — ProctorAI', 'Platform assistance, violation guides, and support resources.');
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [activeTab, setActiveTab] = useState<'candidate' | 'admin'>(isAdmin ? 'admin' : 'candidate');

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-4">
      {/* Header */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 md:p-8 shadow-subtle flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline" size="xs" icon="help">
              Support & Guidelines
            </Badge>
            <span className="text-xs text-secondary">Logged in as {user?.name} ({user?.role})</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-primary">
            Help & Guidelines
          </h1>
          <p className="text-sm text-secondary leading-relaxed">
            Practical instructions, proctoring rules, and administrative workflows.
          </p>
        </div>

        {/* Role Toggle Tabs */}
        <div className="flex items-center bg-surface-container-low p-1 rounded-xl border border-outline-variant/60 shrink-0 self-start md:self-auto">
          <button
            type="button"
            onClick={() => setActiveTab('candidate')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              activeTab === 'candidate'
                ? 'bg-surface-container-lowest text-primary shadow-xs font-semibold'
                : 'text-secondary hover:text-primary'
            }`}
          >
            <Icon name="school" size={14} />
            Candidate Help
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('admin')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              activeTab === 'admin'
                ? 'bg-surface-container-lowest text-primary shadow-xs font-semibold'
                : 'text-secondary hover:text-primary'
            }`}
          >
            <Icon name="security" size={14} />
            Admin Help
          </button>
        </div>
      </div>

      {/* Candidate Guidance Section */}
      {activeTab === 'candidate' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-primary">Candidate Guide & FAQ</h2>
              <p className="text-xs text-secondary mt-0.5">
                Everything you need to know before and during an examination.
              </p>
            </div>
            <Badge variant="neutral" size="xs">
              Candidate View
            </Badge>
          </div>

          <div className="space-y-3">
            {/* Item 1: System Pre-Check */}
            <Card variant="surface" rounded="2xl" className="p-5">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="videocam" size={18} />
                </div>
                <div className="space-y-1.5">
                  <h3 className="text-sm font-semibold text-primary">
                    How does the pre-exam system check work?
                  </h3>
                  <p className="text-xs text-secondary leading-relaxed">
                    Before starting any proctored assessment, you will be guided to a pre-exam verification room. You must grant browser permissions for your <strong>webcam</strong> and <strong>microphone</strong>, verify that your face is centered in the video preview, and confirm that the audio level meter responds when you speak.
                  </p>
                </div>
              </div>
            </Card>

            {/* Item 2: What triggers a violation */}
            <Card variant="surface" rounded="2xl" className="p-5">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="warning" size={18} />
                </div>
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-primary">
                    What triggers a proctoring violation during an exam?
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-xs text-secondary">
                    <div className="border border-outline-variant/60 rounded-xl p-2.5 bg-surface-container-low/30">
                      <strong className="text-primary font-medium block">Fullscreen Exits</strong>
                      Pressing Escape or minimizing the window triggers a countdown banner. Repeated exits will auto-submit the exam.
                    </div>
                    <div className="border border-outline-variant/60 rounded-xl p-2.5 bg-surface-container-low/30">
                      <strong className="text-primary font-medium block">Tab Switching</strong>
                      Switching to another browser tab or opening external applications records a timestamped blur event.
                    </div>
                    <div className="border border-outline-variant/60 rounded-xl p-2.5 bg-surface-container-low/30">
                      <strong className="text-primary font-medium block">Camera Absence / Extra Faces</strong>
                      Leaving the camera frame for multiple consecutive check intervals or having secondary persons visible flags an anomaly.
                    </div>
                    <div className="border border-outline-variant/60 rounded-xl p-2.5 bg-surface-container-low/30">
                      <strong className="text-primary font-medium block">Sustained Audio / Speech</strong>
                      Prolonged vocal speech or conversation during the test registers an audio integrity event.
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            {/* Item 3: Camera/Mic permissions troubleshooting */}
            <Card variant="surface" rounded="2xl" className="p-5">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="settings_voice" size={18} />
                </div>
                <div className="space-y-1.5">
                  <h3 className="text-sm font-semibold text-primary">
                    What if my camera or microphone fails to connect?
                  </h3>
                  <ul className="text-xs text-secondary space-y-1 list-disc pl-4 leading-relaxed">
                    <li>Click the site lock / settings icon next to the URL in your browser bar and verify Camera and Microphone are set to <strong>Allow</strong>.</li>
                    <li>Ensure no other application (e.g. Zoom, Teams, or Meet) is currently using your webcam.</li>
                    <li>Reload the page and test again. You can also re-test anytime from <strong>Settings &rarr; Diagnostics</strong>.</li>
                  </ul>
                </div>
              </div>
            </Card>

            {/* Item 4: Technical failure mid-exam */}
            <Card variant="surface" rounded="2xl" className="p-5">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="wifi_off" size={18} />
                </div>
                <div className="space-y-1.5">
                  <h3 className="text-sm font-semibold text-primary">
                    What happens if my internet disconnects during an assessment?
                  </h3>
                  <p className="text-xs text-secondary leading-relaxed">
                    Your answers are saved automatically as you complete each question. If your connection drops, re-open the exam link as soon as possible. Your remaining time continues counting down on the server, so re-enter immediately to resume.
                  </p>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Admin Guidance Section */}
      {activeTab === 'admin' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-primary">Administrator & Invigilator Guide</h2>
              <p className="text-xs text-secondary mt-0.5">
                Overview of exam creation, live invigilation, and session audits.
              </p>
            </div>
            <Badge variant="dark" size="xs">
              Administrator View
            </Badge>
          </div>

          <div className="space-y-3">
            {/* Item 1: Creating an exam */}
            <Card variant="surface" rounded="2xl" className="p-5">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="add_circle" size={18} />
                </div>
                <div className="space-y-1.5">
                  <h3 className="text-sm font-semibold text-primary">
                    How do I create and publish a new exam?
                  </h3>
                  <p className="text-xs text-secondary leading-relaxed">
                    Navigate to <strong>Console &rarr; Create Exam</strong>. Define the title, description, time limit, and active window. Next, add questions (Multiple Choice or Coding tasks with starter code and test cases). Once at least one question is added, change the status from <em>Draft</em> to <em>Published</em> to open the exam for candidates.
                  </p>
                </div>
              </div>
            </Card>

            {/* Item 2: Reviewing flagged sessions */}
            <Card variant="surface" rounded="2xl" className="p-5">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="policy" size={18} />
                </div>
                <div className="space-y-1.5">
                  <h3 className="text-sm font-semibold text-primary">
                    How do I audit flagged sessions and issue verdicts?
                  </h3>
                  <p className="text-xs text-secondary leading-relaxed">
                    Open the exam’s session roster from the Dashboard or Console. Sessions with trust score reductions or integrity flags are highlighted in the review queue. Click <strong>Audit Session</strong> to inspect the integrated timeline, view snapshot evidence captured at the moment of the flag, and mark violations as <em>Reviewed Benign</em> or <em>Confirmed Cheating</em>.
                  </p>
                </div>
              </div>
            </Card>

            {/* Item 3: Trust score calculation */}
            <Card variant="surface" rounded="2xl" className="p-5">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
                  <Icon name="speed" size={18} />
                </div>
                <div className="space-y-1.5">
                  <h3 className="text-sm font-semibold text-primary">
                    What does the Trust Score mean and how is it calculated?
                  </h3>
                  <p className="text-xs text-secondary leading-relaxed">
                    Every session begins with a maximum trust score of <strong>100%</strong>. Penalties are deducted based on severity: minor tab switches incur small deductions, while critical anomalies (e.g. repeated fullscreen breaches or missing face detections) incur heavier penalties. If an auditor marks a violation as <em>Benign</em>, the penalty is refunded and the score is dynamically restored.
                  </p>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Contact & Support Card */}
      <div className="border border-outline-variant/60 bg-surface-container-low/40 rounded-2xl p-6 shadow-subtle flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-primary flex items-center gap-2">
            <Icon name="support_agent" size={18} />
            <span>Need assistance or found an issue?</span>
          </h3>
          <p className="text-xs text-secondary">
            If you experience unexpected behavior during an assessment, reach out to the examination invigilator.
          </p>
        </div>
        <a
          href="mailto:support@proctorai.local?subject=ProctorAI%20Technical%20Inquiry"
          className="shrink-0"
        >
          <Button variant="secondary" size="sm" icon="mail" className="text-xs font-medium">
            Contact Support
          </Button>
        </a>
      </div>
    </div>
  );
};
