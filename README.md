# 🛡️ Online Exam Proctoring & Assessment Platform

A high-integrity online examination and proctoring platform featuring live anti-cheat monitoring, multiple-choice testing, and sandboxed coding assessments.

---

## 📂 Repository Structure

```
online-exam-proctoring/
├── .env.example              # Template environment configuration (no secrets hardcoded)
├── .gitignore                # Multi-language Git exclusions
├── docker-compose.yml        # Orchestration for all 8 microservices
├── README.md                 # Project documentation & local setup guide
├── docs/
│   └── implementation.md     # Multi-phase roadmap (Phase 1 to Phase 5) & specs
├── docker/
│   ├── docker-compose.yml    # Service-specific compose file
│   ├── judge0.conf           # Judge0 code execution engine configuration
│   └── README.md             # Docker network & service architecture notes
├── backend/                  # FastAPI Application
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini           # Migration settings
│   ├── alembic/              # Database migration revisions
│   ├── app/                  # Application source
│   │   ├── main.py           # FastAPI entrypoint
│   │   ├── core/             # Config, security (JWT/bcrypt), database, RBAC deps
│   │   ├── models/           # SQLAlchemy 2.0 ORM models (UUID PKs)
│   │   ├── schemas/          # Pydantic v2 schemas
│   │   └── api/v1/           # Endpoints: /auth, /health
│   └── tests/                # Automated pytest suite
├── ml-service/               # Lightweight ML Proctoring Skeleton
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       └── main.py           # Health check and proctoring inference stub
└── frontend/                 # React + TypeScript + Vite Web Client
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    └── src/                  # Dark-mode UI with Auth, Health, and RBAC Tester
```

---

## 🚀 Quick Start with Docker Compose

Ensure [Docker Desktop](https://www.docker.com/products/docker-desktop/) is installed and running.

### 1. Configure Environment
```bash
cp .env.example .env
```
*(The default `.env` is pre-configured with secure development defaults.)*

### 2. Start All Services
```bash
docker compose up --build
```

This starts:
- **`frontend`**: [http://localhost:5173](http://localhost:5173) (React + TypeScript Vite app)
- **`backend`**: [http://localhost:8000](http://localhost:8000) (FastAPI Core)
- **`backend docs`**: [http://localhost:8000/docs](http://localhost:8000/docs) (Interactive OpenAPI Swagger)
- **`ml-service`**: [http://localhost:8001](http://localhost:8001) (ML Inference Skeleton)
- **`judge0-server`**: [http://localhost:2358](http://localhost:2358) (Judge0 Code Execution API)
- **`postgres`**: Port 5432 (`exam_proctoring_db`)
- **`redis`**: Port 6379 (Session & cache)
- **`judge0-db`**: Isolated PostgreSQL for Judge0

---

## 🛠️ Running Services Locally (Without Docker)

If you prefer to run services natively on your host machine:

### 1. Backend (FastAPI)
```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run tests:
```bash
pytest
```

### 2. ML Service
```bash
cd ml-service
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 3. Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173).

---

## 🔐 Authentication & Role-Based Access Control (RBAC)

The authentication system employs industry-standard JWTs with short-lived access tokens and long-lived refresh tokens:

| Feature | Specification |
|---|---|
| **Password Hashing** | Bcrypt (12 cost factor rounds) |
| **Password Policy** | $\ge 8$ chars, at least 1 letter and 1 digit |
| **Access Token** | Valid 15 minutes, carries `sub` (User UUID), `email`, `role`, and `type="access"` |
| **Refresh Token** | Valid 7 days, rotated automatically on `/api/v1/auth/refresh` |
| **User Roles** | `candidate`, `grader`, `admin` |

### Key Auth Endpoints
- `POST /api/v1/auth/signup` - Register new user
- `POST /api/v1/auth/login` - Authenticate and retrieve token pair
- `POST /api/v1/auth/refresh` - Exchange refresh token for new access token
- `GET /api/v1/auth/me` - Authenticated user profile
- `GET /api/v1/auth/admin-only` - Protected by `require_roles(UserRole.ADMIN)`
- `GET /api/v1/auth/grader-only` - Protected by `require_roles(UserRole.ADMIN, UserRole.GRADER)`

---

## 🗄️ Database Schema & Alembic Migrations

The database models are written in SQLAlchemy 2.0 with UUIDv4 primary keys to prevent sequence enumeration attacks.

### Core Tables
1. **`users`**: Email, password hash, role (`candidate`/`admin`/`grader`), name, timestamps.
2. **`exams`**: Title, description, created_by (FK), start_time, end_time, duration_minutes, status.
3. **`questions`**: Exam ID (FK), type (`mcq`/`coding`), question_text, options (JSONB), correct_answer, test_cases (JSONB), time_limit, points.
4. **`exam_sessions`**: Exam ID (FK), candidate ID (FK), started_at, submitted_at, status, score.
5. **`submissions`**: Session ID (FK), question ID (FK), answer (JSONB), is_correct, score.
6. **`violation_logs`**: Session ID (FK), violation_type, timestamp, metadata (JSONB), severity (`low`/`medium`/`high`/`critical`).

To apply migrations:
```bash
cd backend
alembic upgrade head
```

---

## 🎨 Design System & WCAG Accessibility Standards

All frontend UI components adhere strictly to WCAG AA / AAA accessibility standards:
- **Contrast Guarantee**: Minimum 4.5:1 contrast for normal text, 3.0:1 for large/bold text; all standard banners achieve WCAG AAA (≥ 11:1).
- **Hard Rule**: Never pair light-tint backgrounds with same-hue mid-tone text. Use either solid saturated backgrounds with white text, or light 50/100 tint backgrounds with deep 950 text.
- **Fixed Indicators**: All status dots and telemetry beacons are strictly bounded to 8px/10px with `shrink-0` to eliminate flexbox stretching.
- For complete token definitions and component guidelines, see [`frontend/src/DESIGN_SYSTEM.md`](file:///frontend/src/DESIGN_SYSTEM.md).

---

## 🗺️ Project Roadmap

Review [`docs/implementation.md`](file:///docs/implementation.md) for the detailed roadmap of all phases:
- **Phase 1**: Foundation & Core Infrastructure *(Complete)*
- **Phase 2**: Exam Creation & Assessment Modules *(Complete)*
- **Phase 3**: Live Automated Proctoring & Anti-Cheat ML Engine *(Complete)*
- **Phase 4**: Real-Time Invigilator Dashboard & WebRTC Audio/Video *(Complete)*
- **Phase 5**: Grading, Analytics, Audit Trail & Enterprise Hardening *(Complete)*
- **Phase 6**: Anti-Cheat Forensic Similarity Engine & Bulk Guardrails *(Complete)*
