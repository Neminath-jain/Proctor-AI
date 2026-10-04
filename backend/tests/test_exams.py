from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_exam_crud_and_validation(async_client: AsyncClient):
    # 1. Create admin and login
    admin_signup = {
        "email": "exam_admin@example.com",
        "name": "Prof Admin",
        "password": "Password123",
        "role": "admin",
    }
    await async_client.post("/api/v1/auth/signup", json=admin_signup)
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "exam_admin@example.com", "password": "Password123"},
    )
    admin_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Candidate attempt to create exam -> 403
    cand_signup = {
        "email": "unauth_cand@example.com",
        "name": "Unauthorized Candidate",
        "password": "Password123",
        "role": "candidate",
    }
    await async_client.post("/api/v1/auth/signup", json=cand_signup)
    c_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "unauth_cand@example.com", "password": "Password123"},
    )
    cand_token = c_login.json()["access_token"]
    cand_headers = {"Authorization": f"Bearer {cand_token}"}

    now = datetime.now(timezone.utc)
    exam_payload = {
        "title": "Computer Science 101",
        "description": "Midterm Examination",
        "duration_minutes": 60,
        "start_time": (now - timedelta(days=1)).isoformat(),
        "end_time": (now + timedelta(days=7)).isoformat(),
        "status": "draft",
    }
    cand_post = await async_client.post("/api/v1/admin/exams", json=exam_payload, headers=cand_headers)
    assert cand_post.status_code == 403

    # 3. Create exam as Admin in draft status -> 201
    create_res = await async_client.post("/api/v1/admin/exams", json=exam_payload, headers=headers)
    assert create_res.status_code == 201
    exam_data = create_res.json()
    exam_id = exam_data["id"]
    assert exam_data["status"] == "draft"

    # 4. Validation: Attempt to publish exam with 0 questions -> 400 Bad Request
    pub_res = await async_client.put(
        f"/api/v1/admin/exams/{exam_id}",
        json={"status": "published"},
        headers=headers,
    )
    assert pub_res.status_code == 400
    assert "at least one question" in pub_res.json()["detail"].lower()

    # 5. Add an MCQ question
    mcq_payload = {
        "type": "mcq",
        "question_text": "Which data structure uses LIFO ordering?",
        "points": 5.0,
        "order": 1,
        "is_multiselect": False,
        "partial_credit": False,
        "options": [
            {"id": "opt_queue", "text": "Queue"},
            {"id": "opt_stack", "text": "Stack"},
            {"id": "opt_tree", "text": "Binary Tree"},
        ],
        "correct_answer": "opt_stack",
    }
    mcq_res = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json=mcq_payload,
        headers=headers,
    )
    assert mcq_res.status_code == 201
    assert mcq_res.json()["correct_answer"] == "opt_stack"

    # 6. Add a Coding question
    coding_payload = {
        "type": "coding",
        "question_text": "Write a function that reads two numbers and prints their sum.",
        "points": 10.0,
        "order": 2,
        "starter_code": {
            "python": "import sys\n# Read a and b and print sum\n",
            "javascript": "const fs = require('fs');\n",
        },
        "allowed_languages": ["python", "javascript"],
        "test_cases": [
            {"input": "2 3", "expected_output": "5", "is_hidden": False},
            {"input": "10 20", "expected_output": "30", "is_hidden": True},
        ],
        "time_limit": 3,
        "memory_limit": 128000,
    }
    code_res = await async_client.post(
        f"/api/v1/admin/exams/{exam_id}/questions",
        json=coding_payload,
        headers=headers,
    )
    assert code_res.status_code == 201

    # 7. Publish exam now that it has 2 questions -> 200 OK
    pub_success = await async_client.put(
        f"/api/v1/admin/exams/{exam_id}",
        json={"status": "published"},
        headers=headers,
    )
    assert pub_success.status_code == 200
    assert pub_success.json()["status"] == "published"
    assert pub_success.json()["question_count"] == 2
    assert pub_success.json()["total_points"] == 15.0
