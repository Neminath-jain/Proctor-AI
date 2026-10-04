# Proctor AI — Architecture & Technical Documentation

> **Complete system documentation for Proctor AI**: a high-integrity, automated online examination and proctoring platform featuring real-time anti-cheat telemetry, sandboxed coding execution, and full compliance with India's Digital Personal Data Protection (DPDP) Act, 2023.

---

## Table of Contents
1. [Executive Summary & Purpose](#1-executive-summary--purpose)
2. [Complete Technology Stack](#2-complete-technology-stack)
3. [System Architecture & Data Flow](#3-system-architecture--data-flow)
4. [Backend Architecture & API Reference](#4-backend-architecture--api-reference)
5. [Database Architecture & Entity Models](#5-database-architecture--entity-models)
6. [Frontend Architecture & User Experience](#6-frontend-architecture--user-experience)
7. [AI & ML Proctoring Engine](#7-ai--ml-proctoring-engine)
8. [Sandboxed Code Execution Engine (Judge0)](#8-sandboxed-code-execution-engine-judge0)
9. [DPDP Act 2023 Compliance & Security Safeguards](#9-dpdp-act-2023-compliance--security-safeguards)
10. [Step-by-Step Setup & Deployment Guide](#10-step-by-step-setup--deployment-guide)
11. [Environment Variables Reference](#11-environment-variables-reference)

---

## 1. Executive Summary & Purpose

Remote assessments frequently face integrity challenges, including proxy test taking, unauthorized background aids, communication with third parties, and tab switching. Traditional solutions often require invasive rootkit-style desktop software that compromises candidate privacy and introduces platform compatibility issues.

**Proctor AI** was built from scratch to solve these challenges through a **browser-native, privacy-first, automated proctoring platform**:
- **Zero Desktop Installs:** Entirely browser-based utilizing standard HTML5 Web APIs (MediaStream, Web Audio API, Fullscreen API, WebSockets).
- **Multi-Modal Anti-Cheat Telemetry:** Intermittent webcam frame verification, Voice Activity Detection (VAD) audio anomaly monitoring, and aggressive browser focus/fullscreen tracking.
- **Dual Assessment Modalities:** Evaluates both Multiple-Choice Questions (MCQ) with automatic grading and multi-language live programming challenges evaluated inside isolated Docker containers.
- **Dynamic Trust Scoring:** Calculates a real-time integrity index ($0\% - 100\%$) per candidate, automatically categorizing sessions as Clean, Suspicious, or Flagged for administrator audit.
- **DPDP Act 2023 Compliant:** Operates as a transparent Data Fiduciary under Indian data protection law, providing explicit pre-exam consent flows, candidate data export, and biometric erasure queues.

---

## 2. Complete Technology Stack

```mermaid
graph TD
    Client[React 18 + TypeScript + Vite SPA] -->|HTTPS / REST API| Core[FastAPI Core Gateway :8000]
    Client -->|WSS / WebSockets| WS[FastAPI Telemetry Streamer :8000]
    Core -->|SQLAlchemy 2.0 Async| DB[(PostgreSQL 16 Database)]
    Core -->|Cache & Rate Limit| Redis[(Redis 7 Cache)]
    Core -->|HTTP Microservice| ML[ML Proctoring Service :8001]
    Core -->|HTTP REST Client| Judge0[Judge0 CE Code Engine :2358]
    Judge0 -->|Isolated Workers| Sandboxes[Ephemeral Docker Code Runners]
```

### 2.1 Frontend Client
- **Core:** React 18, TypeScript, Vite.
- **Styling & Design System:** Custom Linear/Vercel-inspired monochrome design system with CSS custom properties (`index.css`), Tailwind CSS utility classes, WCAG AA/AAA contrast ratios, and zero external component bloat.
- **Code Editor:** `@monaco-editor/react` (VS Code editor engine for syntax highlighting, multi-language support, and tab-key traps).
- **Icons & Typography:** Google Material Symbols & Google Fonts (Inter / Outfit).
- **Routing & State:** `react-router-dom` v6, React Context API (`AuthContext`), Axios HTTP client with request/response interceptors.

### 2.2 Backend API Core
- **Runtime:** Python 3.11 / 3.12 with asynchronous ASGI pipeline (`uvloop` / `asyncio`).
- **Web Framework:** FastAPI with automatic OpenAPI (Swagger) generation.
- **Database & ORM:** PostgreSQL 16 using **SQLAlchemy 2.0 AsyncIO** with `asyncpg` driver.
- **Migrations:** Alembic for version-controlled, reversible schema migrations.
- **Security & RBAC:** JWT authentication (`pyjwt`), password hashing with `bcrypt` (12 rounds), role-based dependency injection.
- **Abuse Prevention:** Custom sliding-window rate limiter with exponential failure backoff (`rate_limit.py`).

### 2.3 Auxiliary Services
- **Redis 7:** In-memory store for session states, heartbeat telemetry, and distributed rate limiting.
- **ML Proctoring Service:** Python microservice running MediaPipe / InsightFace for facial landmark verification and Silero VAD for audio speech detection.
- **Judge0 CE (v1.13.1):** Industrial-grade sandboxed code execution engine running inside unprivileged Docker containers with strict CPU, memory, and timeout constraints.

---

## 3. System Architecture & Data Flow

### 3.1 End-to-End Candidate Exam Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Candidate
    participant FE as Frontend Client
    participant API as FastAPI Backend
    participant ML as ML Service
    participant J0 as Judge0 Engine
    participant DB as PostgreSQL DB

    Candidate->>FE: Logs into Portal
    FE->>API: POST /api/v1/auth/login
    API-->>FE: JWT Access & Refresh Tokens

    Candidate->>FE: Selects Exam & Clicks "Take Exam"
    FE->>Candidate: Renders DPDP Consent Notice Screen
    Candidate->>FE: Actively checks clauses & Clicks "I Consent"
    FE->>API: POST /api/v1/privacy/exams/{id}/consent
    API->>DB: Logs timestamped consent record

    FE->>Candidate: Prompts Camera/Mic Calibration
    Candidate->>FE: Captures baseline verification photo
    FE->>API: POST /api/v1/candidate/exams/{id}/verify-media

    FE->>API: POST /api/v1/candidate/exams/{id}/start
    API-->>FE: Initializes session (Trust Score 100%)

    loop During Active Exam Window
        FE->>API: Periodic Snapshot (every 10-15s)
        API->>ML: Facial verification against baseline
        ML-->>API: Status (verified / missing / multi-face)
        FE->>API: Window Blur / Fullscreen Exit event
        API->>DB: Records violation & Deducts Trust Score points
        Candidate->>FE: Runs code test case
        FE->>API: POST /questions/{id}/run-code
        API->>J0: Executes code in isolated container
        J0-->>FE: Output stdout / stderr / passed status
    end

    Candidate->>FE: Clicks "Finish Exam"
    FE->>API: POST /candidate/sessions/{id}/submit
    API->>J0: Evaluates against hidden test cases
    API->>DB: Computes final score & archives session
    API-->>FE: Returns final transcript & violation review
```

---

## 4. Backend Architecture & API Reference

The backend exposes a modular REST API grouped under `/api/v1`:

### 4.1 Authentication & Profile (`/api/v1/auth`)
| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/signup` | Public | Register candidate or administrator (requires 18+ confirmation). |
| `POST` | `/auth/login` | Public | Authenticate credentials; returns access & refresh JWT tokens. |
| `POST` | `/auth/refresh` | Public | Exchange valid refresh token for a new access token. |
| `GET` | `/auth/me` | Authenticated | Retrieve current user profile and role details. |
| `PUT` | `/auth/me` | Authenticated | Update user display name (Right to Correction). |
| `POST` | `/auth/change-password` | Authenticated | Update user credentials with current password validation. |

### 4.2 Candidate Exam Engine (`/api/v1/candidate`)
| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/candidate/exams` | Candidate | List published, active examinations available to candidate. |
| `POST` | `/candidate/exams/{id}/verify-media` | Candidate | Pre-exam verification of camera, mic, and baseline photo. |
| `POST` | `/candidate/exams/{id}/start` | Candidate | Initialize examination session, randomize questions, lock timer. |
| `POST` | `/candidate/sessions/{id}/questions/{qid}/answer` | Candidate | Auto-save answer selection or draft code for a question. |
| `POST` | `/candidate/sessions/{id}/questions/{qid}/run-code` | Candidate | Execute code against visible test cases via Judge0. |
| `POST` | `/candidate/sessions/{id}/violations` | Candidate | Report client-side integrity event (fullscreen exit, tab blur). |
| `POST` | `/candidate/sessions/{id}/proctor/frame` | Candidate | Upload periodic camera snapshot for ML face verification. |
| `POST` | `/candidate/sessions/{id}/proctor/audio` | Candidate | Upload audio anomaly clip for VAD sound evaluation. |
| `POST` | `/candidate/sessions/{id}/submit` | Candidate | Final exam submission and automated scoring. |
| `GET` | `/candidate/sessions/{id}/result` | Candidate | Retrieve final grade transcript, question review, and trust score. |

### 4.3 Administrator Invigilation & Management (`/api/v1/admin`)
| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/admin/exams` | Admin | List all drafted and published exams with management status. |
| `POST` | `/admin/exams` | Admin | Create a new examination with duration and proctoring rules. |
| `GET` | `/admin/exams/{id}` | Admin | Fetch exam details including full question bank and starter code. |
| `PUT` | `/admin/exams/{id}` | Admin | Update exam parameters, invigilation sensitivity, or publish state. |
| `DELETE`| `/admin/exams/{id}` | Admin | Delete drafted examination. |
| `POST` | `/admin/exams/{id}/questions` | Admin | Add MCQ or Coding question with test cases to exam. |
| `GET` | `/admin/exams/{id}/sessions` | Admin | List candidate sessions with live status and trust scores. |
| `GET` | `/admin/exams/overview/summary` | Admin | Real-time overview metrics bar (total exams, active sessions, flags). |
| `POST` | `/admin/sessions/{id}/review` | Admin | Audit action: Approve, Reject, or Flag candidate session. |
| `WS` | `/admin/ws/exams/{id}/monitor` | Admin | Live WebSocket feed streaming real-time candidate heartbeats. |

### 4.4 DPDP Act 2023 Compliance Router (`/api/v1/privacy`)
| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `POST` | `/privacy/exams/{id}/consent` | Candidate | Record affirmative consent before proctoring starts. |
| `POST` | `/privacy/exams/{id}/withdraw-consent` | Candidate | Withdraw consent mid-session, halting all telemetry instantly. |
| `GET` | `/privacy/export` | Candidate | **Right to Access:** Download full personal data package (JSON). |
| `POST` | `/privacy/erasure-request` | Candidate | **Right to Erasure:** Schedule immediate purge of biometrics & snapshots. |
| `GET` | `/privacy/status` | Candidate | Retrieve candidate consent history and erasure request status. |

---

## 5. Database Architecture & Entity Models

The PostgreSQL database utilizes UUID primary keys across all tables to prevent enumeration attacks:

```mermaid
erDiagram
    User ||--o{ ExamSession : sits_for
    User ||--o{ ConsentRecord : grants
    User ||--o{ DataErasureRequest : submits
    Exam ||--o{ Question : contains
    Exam ||--o{ ExamSession : instantiates
    Exam ||--o{ ConsentRecord : applies_to
    ExamSession ||--o{ SessionAnswer : records
    ExamSession ||--o{ ViolationLog : incurs
    Question ||--o{ SessionAnswer : answered_in

    User {
        uuid id PK
        string email UK
        string name
        string role
        string password_hash
        boolean is_active
        timestamp created_at
    }

    Exam {
        uuid id PK
        string title
        text description
        integer duration_minutes
        boolean enable_browser_proctoring
        boolean enable_video_proctoring
        boolean enable_audio_proctoring
        integer max_fullscreen_exits
        float min_trust_score
        boolean is_published
    }

    ExamSession {
        uuid id PK
        uuid exam_id FK
        uuid candidate_id FK
        timestamp started_at
        timestamp submitted_at
        string status
        float score
        float trust_score
        string review_status
        text terminated_reason
    }

    ViolationLog {
        uuid id PK
        uuid session_id FK
        string violation_type
        string severity
        float trust_score_penalty
        text evidence_path
        timestamp created_at
    }

    ConsentRecord {
        uuid id PK
        uuid candidate_id FK
        uuid exam_id FK
        string status
        string notice_version
        json clauses_consented
        string ip_address
        integer retention_days
        timestamp created_at
    }

    DataErasureRequest {
        uuid id PK
        uuid candidate_id FK
        string status
        text reason
        timestamp requested_at
        timestamp processed_at
    }
```

---

## 6. Frontend Architecture & User Experience

The web application is structured around two dedicated user experiences and a public compliance suite:

### 6.1 Candidate Flow
1. **Assessments Dashboard (`/exams`):** Displays enrolled tests, schedule windows, time limits, and rule badges.
2. **Pre-Exam Consent & Calibration (`/exams/:id/check`):**
   - **Step 1 — DPDP Notice:** Displays the 4 data categories, 90-day retention schedule, AWS Mumbai hosting, and requires two affirmative, un-prechecked checkboxes.
   - **Step 2 — Hardware Calibration:** Activates webcam mirror, live VU dB microphone input meter, and captures the baseline verification photo.
   - **Step 3 — Fullscreen Lock:** Prompts browser fullscreen before entering the exam room.
3. **Live Exam Room (`/exams/:id/take`):**
   - **Split-Screen Workspace:** Left panel renders the question prompt, test case indicators, and submission controls; right panel renders Monaco code editor (with syntax highlighting and run buttons) or radio MCQ cards.
   - **Picture-in-Picture Mirror:** Draggable, minimizable webcam stream showing live connection telemetry.
   - **Anti-Cheat Guards:** Listeners for `fullscreenchange`, `blur`, `visibilitychange`, and context-menu disablement.
   - **Privacy Action:** "Withdraw Consent" button in the toolbar allows candidates to halt proctoring at any point.
4. **Exam Result & Transcript (`/exams/:id/result`):**
   - Score breakdown, test case pass/fail ratios, and an interactive violation timeline.

### 6.2 Administrator Console
1. **Exam Console (`/admin/exams`):** Comprehensive table with status filters, publishing toggles, and direct links to live sessions.
2. **Exam Builder (`/admin/exams/create` & `/builder`):** Visual question composer with Markdown previews, MCQ options manager, and multi-language coding test case editor (visible vs hidden).
3. **Session Audit Console (`/admin/exams/:id/sessions`):**
   - Filter candidate sessions by status (`clean`, `suspicious`, `flagged`).
   - Inspect individual violation logs, snapshot timestamps, and candidate biometric baseline comparison scores.
   - Execute audit rulings: **Approve Session**, **Reject Session**, or **Request Manual Interview**.
4. **Overview Bar (`AdminOverview.tsx`):** Real-time summary metric cards showing total exams, active candidates, and flagged audits.

### 6.3 Public & Statutory Pages
- **Home (`/`):** Plain-language product overview and feature demonstration.
- **About (`/about`):** Honest portfolio/student engineering disclosure.
- **Help (`/help`):** System compatibility tester, FAQ accordion, and student grievance contact.
- **Privacy Policy (`/privacy`):** Comprehensive DPDP Act 2023 transparency notice.
- **Settings (`/settings`):** Name updating, password change, hardware test mirror, invigilation threshold defaults, and the DPDP Data Principal Rights center (Download JSON, Request Erasure).

---

## 7. AI & ML Proctoring Engine

### 7.1 Facial Verification Pipeline
1. **Baseline Registration:** Before entering the test room, the candidate captures a clear frontal reference snapshot.
2. **Vector Extraction:** An in-memory 128-dimensional facial embedding is computed.
3. **Periodic Sampling:** Every 10–15 seconds, a low-resolution canvas snapshot ($320 \times 240$) is captured and posted to `/proctor/frame`.
4. **Cosine Similarity:** The snapshot embedding is compared against the baseline vector.
   $$\text{Similarity} = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\| \|\mathbf{B}\|}$$
5. **Anomaly Classification:**
   - $\text{Similarity} < 0.60$: Face mismatch (potential proxy test-taker).
   - $0 \text{ faces detected}$: Candidate absence.
   - $> 1 \text{ faces detected}$: Secondary occupant present in room.

### 7.2 Voice Activity Detection (VAD)
1. Ephemeral audio chunks ($2 - 4$ seconds) are buffered locally using the Web Audio API.
2. Silero VAD analyzes audio energy and speech probability distributions.
3. Chunks below human vocal energy thresholds are discarded immediately.
4. Chunks containing distinct multi-vocal frequencies trigger an audio anomaly violation.

### 7.3 Trust Score Formula
Every candidate starts with a Trust Score of $100.0\%$. Violations reduce this score dynamically:

$$\text{Trust Score} = 100 - \sum (\text{Violation Count}_i \times \text{Weight}_i)$$

| Incident Type | Penalty Weight | Trigger Condition |
| :--- | :--- | :--- |
| **Fullscreen Exit** | $-5\%$ per exit | Window leaves OS fullscreen mode |
| **Tab / Window Blur** | $-3\%$ per event | Candidate clicks outside the browser tab |
| **Candidate Absence** | $-15\%$ per event | No face detected for $> 15$ seconds |
| **Secondary Face Detected** | $-20\%$ per event | Multiple human faces identified in frame |
| **Voice / Whisper Anomaly** | $-8\%$ per event | Sustained unauthorized speech detected |
| **Media Track Revoked** | $-25\%$ per event | Candidate turns off webcam or microphone |

*If Trust Score drops below the exam's review threshold (default $70\%$), the session is automatically flagged for mandatory administrator review.*

---

## 8. Sandboxed Code Execution Engine (Judge0)

Proctor AI integrates an isolated instance of Judge0 Community Edition to evaluate code safely:

1. **Multi-Language Support:** Python (`id: 71`), JavaScript/Node (`id: 63`), C++ (`id: 54`), and Java (`id: 62`).
2. **Execution Isolation:** Runs inside rootless Docker containers without access to the host network or internal database ports.
3. **Execution Limits:**
   - **CPU Time Limit:** $2.0 \text{ seconds}$.
   - **Memory Limit:** $128 \text{ MB}$.
   - **Max Output Size:** $10 \text{ KB}$ (mitigates infinite loop buffer attacks).
4. **Dual Test Suite Execution:**
   - **Visible Test Cases:** Run interactively on candidate request for debugging and feedback.
   - **Hidden Test Cases:** Executed securely upon final submission; inputs/outputs are never transmitted to the client browser.

---

## 9. DPDP Act 2023 Compliance & Security Safeguards

Proctor AI implements statutory requirements under India's Digital Personal Data Protection Act, 2023:

```
DPDP Compliance Checklist:
[✔] Data Fiduciary & Data Principal Roles Formally Defined
[✔] Explicit, Un-prechecked Consent Flow Before Hardware Activation (Section 6)
[✔] Mid-Session Consent Withdrawal Halting Telemetry Instantly (Section 6(4))
[✔] Evidentiary Timestamped Consent Logging in PostgreSQL (Section 6(7))
[✔] Data Minimization: Periodic Snapshots Only, No 24/7 Continuous Video (Section 8)
[✔] AWS ap-south-1 (Mumbai, India) Data Residency (Section 16)
[✔] 90-Day Evidence Retention Schedule with Automatic Purge
[✔] Right to Access: Machine-Readable Personal Data Export (.JSON) (Section 11)
[✔] Right to Correction: Profile & Credential Modification (Section 12)
[✔] Right to Erasure: Biometric & Snapshot Deletion Queue (Section 12(3))
[✔] Children's Data Restriction: Mandatory 18+ Verification at Signup (Section 9)
[✔] Grievance Redressal Mechanism & Officer Contact (Section 13)
[✔] Documented 4-Phase Breach Notification Protocol (Section 8(6))
```

### Incident Response & Breach Notification Protocol
In compliance with Section 8(6) of the DPDP Act 2023:
1. **Phase 1 (0–2h):** Revoke active JWT tokens, isolate affected database pools, freeze audit logs.
2. **Phase 2 (2–24h):** Forensic scoping of affected Data Principals and exposed data elements.
3. **Phase 3 (Within 72h):** Formal notification dispatched to the **Data Protection Board of India (DPBI)** and registered emails sent to affected candidates with mitigation instructions.
4. **Phase 4 (1–7d):** System patching, firewall re-configuration, and published post-mortem report.

---

## 10. Step-by-Step Setup & Deployment Guide

### 10.1 Prerequisites
- **Node.js:** v18.0.0 or higher
- **Python:** v3.10 or v3.11
- **Docker Desktop:** Installed and running (for Postgres, Redis, and Judge0)
- **Git**

---

### 10.2 Option A: Local Development Setup (Recommended)

#### Step 1: Start Infrastructure Containers (PostgreSQL, Redis, Judge0)
```powershell
# From the project root directory
docker compose up -d postgres redis judge0-server judge0-db judge0-workers
```

#### Step 2: Configure & Run FastAPI Backend
```powershell
cd backend

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies (including greenlet for async SQLAlchemy)
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*API will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000) and Swagger docs at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).*

#### Step 3: Configure & Run React Frontend
```powershell
cd ..\frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
*Frontend will be live at [http://localhost:5173](http://localhost:5173).*

---

### 10.3 Default Demo Accounts

| Role | Email | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@example.com` | `Admin123!` | Full access to Exam Builder, Sessions Console, and Audit Rulings |
| **Candidate** | `candidate@example.com` | `Candidate123!` | Assessment taking, DPDP Consent, Hardware Check, Data Export |

---

## 11. Environment Variables Reference

### Backend Configuration (`backend/.env`)
```ini
# Application Mode
PROJECT_NAME="Online Exam Proctoring Platform"
API_V1_STR="/api/v1"
DEBUG=True
SECRET_KEY="replace-with-a-cryptographically-secure-random-key"

# Database Configuration (PostgreSQL / Supabase)
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres_password
POSTGRES_DB=exam_proctoring_db
DATABASE_URL=postgresql+asyncpg://postgres:postgres_password@localhost:5432/exam_proctoring_db

# Redis Cache & Sessions
REDIS_URL=redis://localhost:6379/0

# Auxiliary Services
ML_SERVICE_URL=http://localhost:8001
JUDGE0_API_URL=http://localhost:2358

# DPDP & Retention Configuration
DPDP_RETENTION_DAYS=90
DATA_RESIDENCY_REGION="AWS ap-south-1 (Mumbai, India)"
GRIEVANCE_EMAIL="grievance@proctorai.edu"
```

### Frontend Configuration (`frontend/.env`)
```ini
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

---

*Proctor AI — Engineering reliable, privacy-first assessment systems.*
