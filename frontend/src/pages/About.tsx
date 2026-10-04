import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, Badge, Button, Icon } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export const About: React.FC = () => {
  useDocumentTitle('About — ProctorAI', 'Platform overview, capabilities, and system user roles.');
  const { isAuthenticated } = useAuth();

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-4">
      {/* Header */}
      <div className="border border-outline-variant/70 bg-surface-container-lowest rounded-2xl p-6 md:p-8 shadow-subtle space-y-3">
        <div className="flex items-center gap-2">
          <Badge variant="outline" size="xs" icon="info">
            Project Overview
          </Badge>
          <span className="text-xs text-secondary">Academic & Portfolio Project</span>
        </div>
        <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-primary">
          About Proctor AI
        </h1>
        <p className="text-sm text-secondary leading-relaxed max-w-3xl">
          Proctor AI is a lightweight online examination and invigilation platform built to explore automated academic integrity enforcement. It combines real-time browser monitoring, video and audio ML proctoring, and automated question evaluation for both multiple-choice and live code execution.
        </p>
      </div>

      {/* What it is: Core Capabilities */}
      <div className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-primary">What the platform does</h2>
          <p className="text-xs text-secondary mt-0.5">
            Designed to conduct fair, structured assessments without intrusive background software.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card variant="surface" rounded="2xl" className="p-5 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                <Icon name="verified_user" size={18} />
              </div>
              <h3 className="text-sm font-semibold text-primary">Browser & Device Tracking</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Enforces continuous fullscreen mode and monitors tab switching or focus loss. If a candidate leaves the exam window, warnings are displayed and an event is logged.
              </p>
            </div>
            <div className="pt-3">
              <span className="text-[11px] text-secondary font-mono">No external plugins required</span>
            </div>
          </Card>

          <Card variant="surface" rounded="2xl" className="p-5 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                <Icon name="videocam" size={18} />
              </div>
              <h3 className="text-sm font-semibold text-primary">Video & Audio Verification</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Uses the candidate’s camera and microphone to detect multiple faces, absence from frame, or sustained speech. Evidence snapshots are captured strictly upon rule events.
              </p>
            </div>
            <div className="pt-3">
              <span className="text-[11px] text-secondary font-mono">MediaPipe + WebRTC Audio</span>
            </div>
          </Card>

          <Card variant="surface" rounded="2xl" className="p-5 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                <Icon name="code" size={18} />
              </div>
              <h3 className="text-sm font-semibold text-primary">MCQ & Coding Assessments</h3>
              <p className="text-xs text-secondary leading-relaxed">
                Supports randomized multiple-choice questions alongside multi-language programming tasks executed against predefined test cases.
              </p>
            </div>
            <div className="pt-3">
              <span className="text-[11px] text-secondary font-mono">Sandboxed Judge0 execution</span>
            </div>
          </Card>
        </div>
      </div>

      {/* User Roles */}
      <div className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-primary">User Roles & Responsibilities</h2>
          <p className="text-xs text-secondary mt-0.5">
            The platform provides distinct workflows for candidates and administrators.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 md:p-6 shadow-subtle space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                <Icon name="school" size={18} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-primary">Candidate</h3>
                <span className="text-[11px] text-secondary">Student / Test Taker</span>
              </div>
            </div>
            <ul className="text-xs text-secondary space-y-2 leading-relaxed">
              <li className="flex items-start gap-2">
                <Icon name="check" size={14} className="text-primary mt-0.5 shrink-0" />
                <span>Runs browser, camera, and microphone diagnostics before starting an assessment.</span>
              </li>
              <li className="flex items-start gap-2">
                <Icon name="check" size={14} className="text-primary mt-0.5 shrink-0" />
                <span>Takes timed assessments in a focused fullscreen environment with clear violation warnings.</span>
              </li>
              <li className="flex items-start gap-2">
                <Icon name="check" size={14} className="text-primary mt-0.5 shrink-0" />
                <span>Reviews immediate question score breakdowns and verified integrity status upon submission.</span>
              </li>
            </ul>
          </div>

          <div className="border border-outline-variant/60 bg-surface-container-lowest rounded-2xl p-5 md:p-6 shadow-subtle space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary">
                <Icon name="security" size={18} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-primary">Administrator</h3>
                <span className="text-[11px] text-secondary">Instructor / Invigilator</span>
              </div>
            </div>
            <ul className="text-xs text-secondary space-y-2 leading-relaxed">
              <li className="flex items-start gap-2">
                <Icon name="check" size={14} className="text-primary mt-0.5 shrink-0" />
                <span>Creates exams, authors question banks, configures test cases, and customizes proctoring rules.</span>
              </li>
              <li className="flex items-start gap-2">
                <Icon name="check" size={14} className="text-primary mt-0.5 shrink-0" />
                <span>Oversees live test sessions in real time with WebSocket-driven violation telemetry.</span>
              </li>
              <li className="flex items-start gap-2">
                <Icon name="check" size={14} className="text-primary mt-0.5 shrink-0" />
                <span>Audits flagged session timelines, reviews snapshot evidence, and issues human-verified verdicts.</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Honest Project Context */}
      <div className="border border-outline-variant/60 bg-surface-container-low/40 rounded-2xl p-5 md:p-6 space-y-2">
        <h3 className="text-sm font-semibold text-primary flex items-center gap-2">
          <Icon name="terminal" size={16} className="text-secondary" />
          <span>Project & Technical Context</span>
        </h3>
        <p className="text-xs text-secondary leading-relaxed">
          This system is developed as an educational and technical portfolio project demonstrating end-to-end web engineering, computer vision proctoring pipelines, sandboxed code compilation, and human-in-the-loop integrity auditing. All candidate data and evidence captures are scoped strictly to the demonstration database.
        </p>
        <div className="pt-3 flex flex-wrap gap-2">
          {isAuthenticated ? (
            <Link to="/dashboard">
              <Button variant="primary" size="sm" icon="dashboard" className="text-xs">
                Go to Dashboard
              </Button>
            </Link>
          ) : (
            <>
              <Link to="/login">
                <Button variant="primary" size="sm" icon="login" className="text-xs">
                  Sign in
                </Button>
              </Link>
              <Link to="/signup">
                <Button variant="secondary" size="sm" className="text-xs">
                  Create account
                </Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
