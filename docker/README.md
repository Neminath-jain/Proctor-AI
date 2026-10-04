# Docker Setup & Service Architecture

This directory houses the containerization configurations for the Online Exam Proctoring and Assessment Platform.

## 📦 Container Services

1. **`postgres`**: PostgreSQL 16 Alpine
   - App database name: `exam_proctoring_db`
   - Port: `5432`
   - Persistent volume: `postgres_data`

2. **`redis`**: Redis 7 Alpine
   - Port: `6379`
   - Persistent volume: `redis_data`
   - Used for token blacklisting, caching, and future WebRTC/proctoring pub/sub.

3. **`judge0-server`**: Judge0 CE API server
   - Port: `2358`
   - Mounts `docker/judge0.conf`
   - Sandbox engine running with `privileged: true`

4. **`judge0-workers`**: Judge0 CE worker process
   - Mounts `docker/judge0.conf`
   - Processes asynchronous code evaluation jobs

5. **`judge0-db`**: Dedicated PostgreSQL instance for Judge0
   - Prevents Judge0 internal tables from cluttering the exam application database
   - Exposed internally to `judge0-server` and `judge0-workers`

6. **`backend`**: FastAPI application
   - Port: `8000`
   - Hot-reloading enabled via bind-mount `./backend:/app`
   - Interactive OpenAPI documentation at `http://localhost:8000/docs`

7. **`ml-service`**: Lightweight Python service
   - Port: `8001`
   - Hot-reloading enabled via bind-mount `./ml-service:/app`
   - Interactive docs at `http://localhost:8001/docs`

8. **`frontend`**: React + TypeScript (Vite)
   - Port: `5173`
   - Hot module replacement (HMR) enabled via bind-mount `./frontend:/app`
