import React from 'react';
import { Link } from 'react-router-dom';
import { Card, Badge, Button, Icon } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export const PrivacyPolicy: React.FC = () => {
  useDocumentTitle(
    'Privacy Policy & DPDP Notice — ProctorAI',
    'Plain-language notice under Indias Digital Personal Data Protection Act, 2023 (DPDP Act).'
  );

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-4">
      {/* Header Banner */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 md:p-8 shadow-subtle space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" size="xs" icon="gavel">
            DPDP Act 2023 Compliance
          </Badge>
          <span className="text-xs text-secondary">•</span>
          <span className="text-xs text-secondary">Data Fiduciary Transparency Notice</span>
          <span className="text-xs text-secondary">•</span>
          <span className="text-xs text-secondary">Version 2023.1</span>
        </div>
        <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-primary">
          Privacy Policy & Candidate Data Protection Notice
        </h1>
        <p className="text-sm text-secondary leading-relaxed max-w-3xl">
          Under India&apos;s Digital Personal Data Protection Act, 2023 (DPDP Act 2023), <strong>Proctor AI</strong> acts as the <strong>Data Fiduciary</strong>, and examination candidates act as <strong>Data Principals</strong>. This document explains what personal and biometric data we collect, why we collect it, where it is hosted, how long it is retained, and how you can exercise your statutory rights.
        </p>
        <div className="pt-2 flex flex-wrap gap-2 text-xs text-secondary">
          <span className="font-medium text-primary">Data Hosting:</span>
          <span>AWS ap-south-1 (Mumbai, India)</span>
          <span className="text-outline-variant">|</span>
          <span className="font-medium text-primary">Evidence Retention:</span>
          <span>90 Days</span>
          <span className="text-outline-variant">|</span>
          <span className="font-medium text-primary">Scope:</span>
          <span>Adult Candidates (18+ only)</span>
        </div>
      </div>

      {/* Honest Scope Disclosure */}
      <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/40 flex items-start gap-3">
        <Icon name="verified_user" size={18} className="text-primary mt-0.5 shrink-0" />
        <div className="text-xs leading-relaxed text-secondary">
          <strong className="text-primary font-medium">Project Notice:</strong> Proctor AI is an advanced engineering and portfolio demonstration platform designed to implement real-world privacy architecture. We do not make deceptive corporate claims (such as fake ISO or global enterprise certifications). Our data protection practices directly mirror the statutory mandates of India&apos;s DPDP Act 2023.
        </div>
      </div>

      {/* Section 1: Categories of Personal Data Collected */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-4">
        <div className="border-b border-outline-variant/60 pb-3 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-primary">1. Personal Data We Collect</h2>
            <p className="text-xs text-secondary mt-0.5">
              Strictly limited under the principle of data minimization (Section 6 & 8 of DPDP Act 2023).
            </p>
          </div>
          <Badge variant="neutral" size="xs">Data Categories</Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-2">
            <div className="font-semibold text-primary flex items-center gap-1.5">
              <Icon name="account_circle" size={16} />
              <span>Account & Identity Data</span>
            </div>
            <p className="text-secondary leading-relaxed">
              Your full name, institutional email address, encrypted password hash (bcrypt), and assigned role (Candidate or Administrator).
            </p>
          </div>

          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-2">
            <div className="font-semibold text-primary flex items-center gap-1.5">
              <Icon name="face" size={16} />
              <span>Biometric Face Verification Data</span>
            </div>
            <p className="text-secondary leading-relaxed">
              A 128-dimensional numerical facial embedding vector computed from your pre-exam baseline photo to authenticate that the person sitting for the exam matches the verified candidate. Raw video streams are not stored 24/7.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-2">
            <div className="font-semibold text-primary flex items-center gap-1.5">
              <Icon name="videocam" size={16} />
              <span>Periodic Camera Snapshots</span>
            </div>
            <p className="text-secondary leading-relaxed">
              Intermittent low-resolution camera snapshots captured every 10–15 seconds during an active test to verify candidate presence and room occupancy. We do <strong>not</strong> record continuous 24/7 video streams.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-2">
            <div className="font-semibold text-primary flex items-center gap-1.5">
              <Icon name="mic" size={16} />
              <span>Audio Anomaly Chunks</span>
            </div>
            <p className="text-secondary leading-relaxed">
              Ambient audio is monitored in short in-memory buffers using voice activity detection (VAD). Audio chunks are saved only when anomalies (e.g. secondary voices or background whispers) trigger an integrity flag.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-2">
            <div className="font-semibold text-primary flex items-center gap-1.5">
              <Icon name="tab" size={16} />
              <span>Browser & Environment Telemetry</span>
            </div>
            <p className="text-secondary leading-relaxed">
              Browser window blur events, tab switching timestamps, fullscreen exit attempts, and copy-paste prevention signals. No browsing history outside the exam tab is ever tracked or inspected.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-2">
            <div className="font-semibold text-primary flex items-center gap-1.5">
              <Icon name="quiz" size={16} />
              <span>Assessment Responses & Scores</span>
            </div>
            <p className="text-secondary leading-relaxed">
              Multiple-choice selections, submitted programming code, automated test suite evaluation outcomes, total points, and composite academic trust scores.
            </p>
          </div>
        </div>
      </Card>

      {/* Section 2: Purpose of Processing */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-4">
        <div className="border-b border-outline-variant/60 pb-3">
          <h2 className="text-base font-semibold text-primary">2. Purpose of Processing (Section 4 & 5)</h2>
          <p className="text-xs text-secondary mt-0.5">
            Your personal data is processed solely for lawful, specified purposes directly related to examination administration.
          </p>
        </div>

        <ul className="space-y-3 text-xs text-secondary leading-relaxed">
          <li className="flex items-start gap-2">
            <Icon name="check" size={16} className="text-primary mt-0.5 shrink-0" />
            <span>
              <strong className="text-primary">Identity Authentication:</strong> Matching the pre-exam baseline photo against periodic session snapshots to prevent impersonation or proxy test taking.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Icon name="check" size={16} className="text-primary mt-0.5 shrink-0" />
            <span>
              <strong className="text-primary">Academic Integrity Monitoring:</strong> Flagging suspicious events such as candidate absence, secondary faces in frame, unauthorized audio murmurs, or navigating away from the fullscreen exam environment.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Icon name="check" size={16} className="text-primary mt-0.5 shrink-0" />
            <span>
              <strong className="text-primary">Auditing & Grievance Review:</strong> Providing exam administrators and proctors with timestamped evidence to objectively review flagged sessions when determining final academic standings.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Icon name="close" size={16} className="text-rose-600 mt-0.5 shrink-0" />
            <span>
              <strong className="text-primary">Strict Prohibition:</strong> Your personal, biometric, or telemetry data is <strong>never</strong> sold, rented, monetized, or shared with third-party advertising networks.
            </span>
          </li>
        </ul>
      </Card>

      {/* Section 3: Data Retention & Deletion Schedule */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-4">
        <div className="border-b border-outline-variant/60 pb-3 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-primary">3. Retention Period & Deletion Policy</h2>
            <p className="text-xs text-secondary mt-0.5">
              Personal data is not kept longer than necessary for the purpose for which it was collected.
            </p>
          </div>
          <Badge variant="outline" size="xs">90-Day Policy</Badge>
        </div>

        <div className="space-y-3 text-xs text-secondary leading-relaxed">
          <div className="p-3.5 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-1.5">
            <div className="font-semibold text-primary">Proctoring Evidence (Snapshots & Biometrics): 90 Days</div>
            <p>
              Camera snapshot files, audio anomaly recordings, and facial biometric embedding vectors are automatically scheduled for permanent erasure <strong>90 days</strong> after the exam conclusion. This 90-day window provides sufficient time for institutional grade appeals and audit reviews.
            </p>
          </div>

          <div className="p-3.5 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-1.5">
            <div className="font-semibold text-primary">Academic Scores & Evaluation Transcripts: Statutory Period</div>
            <p>
              Final numerical scores, question responses, and trust score aggregates are retained as part of the student&apos;s institutional educational transcript per statutory academic record-keeping requirements.
            </p>
          </div>

          <div className="p-3.5 rounded-xl border border-outline-variant/60 bg-surface-container-low/20 space-y-1.5">
            <div className="font-semibold text-primary">Audit & Consent Records</div>
            <p>
              Timestamped records of candidate consent (clauses accepted, IP address, user-agent) are preserved to demonstrate regulatory compliance under Section 6 of the DPDP Act 2023.
            </p>
          </div>
        </div>
      </Card>

      {/* Section 4: Data Residency & Hosting */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-4">
        <div className="border-b border-outline-variant/60 pb-3">
          <h2 className="text-base font-semibold text-primary">4. Data Residency & Cross-Border Transfers (Section 16)</h2>
          <p className="text-xs text-secondary mt-0.5">
            Accurate disclosure of server and database infrastructure locations.
          </p>
        </div>

        <div className="space-y-3 text-xs text-secondary leading-relaxed">
          <p>
            In strict compliance with Indian regulatory guidance, Proctor AI stores and processes all candidate personal data, proctoring evidence, and biometric representations within India:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div className="p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/30">
              <div className="font-semibold text-primary">Database Infrastructure</div>
              <div className="text-[11px] text-secondary mt-0.5">
                PostgreSQL hosted on <strong>AWS ap-south-1 (Mumbai, India)</strong> via Supabase cloud infrastructure.
              </div>
            </div>
            <div className="p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/30">
              <div className="font-semibold text-primary">Application & ML Server</div>
              <div className="text-[11px] text-secondary mt-0.5">
                FastAPI application and MediaPipe/InsightFace proctoring services running locally or in Indian cloud zones.
              </div>
            </div>
          </div>
          <p className="text-[11px] text-secondary">
            No personal data is transferred to any foreign jurisdiction restricted by the Central Government of India under Section 16 of the DPDP Act 2023.
          </p>
        </div>
      </Card>

      {/* Section 5: Data Principal Rights */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-4">
        <div className="border-b border-outline-variant/60 pb-3 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-primary">5. Your Rights as a Data Principal</h2>
            <p className="text-xs text-secondary mt-0.5">
              Built-in self-service mechanisms to inspect, correct, and request erasure of your data.
            </p>
          </div>
          <Badge variant="outline" size="xs">DPDP Rights</Badge>
        </div>

        <div className="space-y-4 text-xs">
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
              <Icon name="download" size={16} />
            </div>
            <div className="flex-1 space-y-1">
              <div className="font-semibold text-primary">Right to Access (Section 11)</div>
              <p className="text-secondary leading-relaxed">
                You have the right to obtain a summary of personal data being processed. In Proctor AI, you can click <strong className="text-primary">&ldquo;Download My Personal Data&rdquo;</strong> in the <Link to="/settings" className="text-primary underline">Settings page</Link> at any time to export a full, machine-readable JSON package containing your account details, session histories, violations, and consent logs.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
              <Icon name="edit" size={16} />
            </div>
            <div className="flex-1 space-y-1">
              <div className="font-semibold text-primary">Right to Correction & Updating (Section 12)</div>
              <p className="text-secondary leading-relaxed">
                You have the right to correct inaccurate or misleading personal data. You can directly update your full name and security credentials from the Settings profile interface.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
              <Icon name="delete_forever" size={16} />
            </div>
            <div className="flex-1 space-y-1">
              <div className="font-semibold text-primary">Right to Erasure (Section 12)</div>
              <p className="text-secondary leading-relaxed">
                You may request the deletion of your personal data when it is no longer necessary for the purpose of the exam. Using the <strong className="text-primary">&ldquo;Request Data Erasure&rdquo;</strong> action in Settings, candidates can initiate the immediate purge of biometric vectors and stored webcam snapshots.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
              <Icon name="cancel" size={16} />
            </div>
            <div className="flex-1 space-y-1">
              <div className="font-semibold text-primary">Right to Withdraw Consent (Section 6)</div>
              <p className="text-secondary leading-relaxed">
                Consent must be as easy to withdraw as it was to give. During any active exam, you can click <strong className="text-primary">&ldquo;Withdraw Consent&rdquo;</strong> in the examination toolbar. All camera, microphone, and browser telemetry is halted instantly, and the session is cleanly closed.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 mt-0.5">
              <Icon name="support_agent" size={16} />
            </div>
            <div className="flex-1 space-y-1">
              <div className="font-semibold text-primary">Right of Grievance Redressal (Section 13)</div>
              <p className="text-secondary leading-relaxed">
                If you have questions, disputes, or complaints regarding how your personal data is handled, you may contact our designated Grievance Officer detailed below.
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* Section 6: Processing of Children's Data */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-4">
        <div className="border-b border-outline-variant/60 pb-3 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-primary">6. Processing of Children&apos;s Personal Data (Section 9)</h2>
            <p className="text-xs text-secondary mt-0.5">
              Mandatory restrictions regarding candidates under 18 years of age.
            </p>
          </div>
          <Badge variant="outline" size="xs">18+ Platform Scope</Badge>
        </div>

        <div className="space-y-3 text-xs text-secondary leading-relaxed">
          <p>
            Under Section 9 of the DPDP Act 2023, processing personal data of individuals under 18 requires verifiable parental consent, and tracking or behavioral monitoring directed toward minors is strictly restricted.
          </p>
          <div className="p-3.5 rounded-xl border border-outline-variant/60 bg-surface-container-low/30">
            <strong className="text-primary">Policy Scope:</strong> Proctor AI is engineered exclusively for adult candidates (aged 18 and older) taking university, collegiate, or professional certification examinations. Candidates must affirmatively confirm they are at least 18 years old during account registration.
          </div>
          <p>
            If an institution intends to deploy Proctor AI for high-school students or minors, a separate verifiable parental consent agreement must be executed with the administering educational institution prior to onboarding.
          </p>
        </div>
      </Card>

      {/* Section 7: Reasonable Security Safeguards */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-4">
        <div className="border-b border-outline-variant/60 pb-3">
          <h2 className="text-base font-semibold text-primary">7. Security Safeguards (Section 8)</h2>
          <p className="text-xs text-secondary mt-0.5">
            Technical and organizational measures implemented to safeguard personal data.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-secondary">
          <div className="space-y-1.5 p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/20">
            <div className="font-semibold text-primary">Encryption at Rest & in Transit</div>
            <p className="leading-relaxed">
              All communications are enforced over TLS/HTTPS. PostgreSQL data volumes are encrypted at rest with AES-256 transparent data encryption.
            </p>
          </div>

          <div className="space-y-1.5 p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/20">
            <div className="font-semibold text-primary">Strict Role-Based Access Control (RBAC)</div>
            <p className="leading-relaxed">
              Candidate evidence is never publicly accessible via guessable URLs. All snapshot endpoints enforce authenticated JWT tokens with specific examination auditor authorization.
            </p>
          </div>

          <div className="space-y-1.5 p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/20">
            <div className="font-semibold text-primary">Data Minimization</div>
            <p className="leading-relaxed">
              We store only discrete, low-resolution snapshots and flagged audio clips. No persistent 24/7 video streams are captured. Internal database keys and JWT internals are hidden from user interfaces.
            </p>
          </div>

          <div className="space-y-1.5 p-3 rounded-xl border border-outline-variant/60 bg-surface-container-low/20">
            <div className="font-semibold text-primary">Breach Notification Protocol</div>
            <p className="leading-relaxed">
              In accordance with Section 8(6) of the DPDP Act 2023, if an unauthorized access or security breach occurs affecting candidate data, Proctor AI will notify the Data Protection Board of India and affected candidates without unreasonable delay.
            </p>
          </div>
        </div>
      </Card>

      {/* Section 8: Grievance Officer & Contact */}
      <Card variant="surface" rounded="2xl" className="p-6 md:p-8 space-y-4">
        <div className="border-b border-outline-variant/60 pb-3 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-primary">8. Grievance Redressal & Contact (Section 13)</h2>
            <p className="text-xs text-secondary mt-0.5">
              Contact our designated Data Protection & Grievance Officer.
            </p>
          </div>
          <Badge variant="outline" size="xs">Redressal Mechanism</Badge>
        </div>

        <div className="space-y-3 text-xs text-secondary leading-relaxed">
          <p>
            If you have any grievances, inquiries, or requests regarding the processing of your personal data, or if you believe your rights under the DPDP Act 2023 have been compromised, please write to:
          </p>

          <div className="p-4 rounded-xl border border-outline-variant/60 bg-surface-container-low/40 space-y-2 max-w-lg">
            <div className="text-xs font-semibold text-primary">Data Protection & Grievance Officer</div>
            <div className="text-secondary text-xs">Proctor AI Platform Support & Integrity Division</div>
            <div className="flex items-center gap-2 pt-1">
              <Icon name="mail" size={15} className="text-primary" />
              <a
                href="mailto:grievance@proctorai.edu"
                className="text-primary font-medium hover:underline"
              >
                grievance@proctorai.edu
              </a>
              <span className="text-outline-variant">|</span>
              <a
                href="mailto:privacy@proctorai.local"
                className="text-primary font-medium hover:underline"
              >
                privacy@proctorai.local
              </a>
            </div>
            <div className="text-[11px] text-secondary pt-1">
              Response timeframe: Acknowledgement within <strong>24 hours</strong>; formal resolution within <strong>7 working days</strong>.
            </div>
          </div>

          <div className="pt-2 flex flex-wrap gap-3">
            <Link to="/settings">
              <Button variant="primary" size="sm" icon="settings" className="text-xs">
                Manage Privacy in Settings
              </Button>
            </Link>
            <Link to="/help">
              <Button variant="secondary" size="sm" icon="help" className="text-xs">
                Help & Support Center
              </Button>
            </Link>
          </div>
        </div>
      </Card>
    </div>
  );
};
