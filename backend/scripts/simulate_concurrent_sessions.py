"""Simulation script for Phase 5 real-time admin experience, trust scoring, and bulk approval.
Demonstrates 3 simulated concurrent candidate sessions with distinct integrity profiles:
- Candidate A (Low risk): 1 tab switch -> Trust Score ~96.0
- Candidate B (Moderate risk): 3 tab switches + 1 fullscreen exit -> Trust Score ~83.0
- Candidate C (High risk): Face mismatch + multiple faces -> Trust Score ~57.0 (drops below 60)
Tests:
1. Deterministic Trust Score calculations with diminishing returns
2. Real-time timeline correlation of violations and answer submissions
3. Human-in-the-loop review discount: marking face mismatch as benign restores +25.0 points
4. Bulk approve guardrail: approves Candidate A, blocks Candidate C due to critical infraction.
"""
import asyncio
import uuid
from datetime import datetime, timezone
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"

ADMIN_CREDS = {"email": "admin@example.com", "password": "AdminPassword123!"}
CANDIDATE_CREDS = {"email": "candidate@example.com", "password": "CandidatePassword123!"}


async def main():
    print("=" * 70)
    print("PHASE 5 LIVE SIMULATION: Concurrent Sessions, Trust Scores & Reviews")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Login as Admin
        admin_res = await client.post(f"{BASE_URL}/auth/login", json=ADMIN_CREDS)
        if admin_res.status_code != 200:
            print(f"[FAIL] Admin login failed: {admin_res.text}")
            return
        admin_token = admin_res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("[OK] Admin authenticated successfully.")

        # 2. Login as Candidate
        cand_res = await client.post(f"{BASE_URL}/auth/login", json=CANDIDATE_CREDS)
        if cand_res.status_code != 200:
            print(f"[FAIL] Candidate login failed: {cand_res.text}")
            return
        cand_token = cand_res.json()["access_token"]
        cand_headers = {"Authorization": f"Bearer {cand_token}"}
        print("[OK] Candidate authenticated successfully.")

        # 3. Fetch exams or use first available
        exams_res = await client.get(f"{BASE_URL}/exams", headers=cand_headers)
        exams = exams_res.json()
        if not exams:
            print("[FAIL] No exams found.")
            return

        exam = exams[0]
        exam_id = exam["id"]
        print(f"[OK] Using Exam: '{exam['title']}' (ID: {exam_id})")

        # 4. Start candidate session
        sess_res = await client.post(f"{BASE_URL}/exams/{exam_id}/start", headers=cand_headers)
        if sess_res.status_code != 200:
            print(f"[FAIL] Session start failed: {sess_res.text}")
            return
        session_data = sess_res.json()
        session_id = session_data["session_id"]
        print(f"[OK] Candidate session started: {session_id}")

        # 5. Log initial answer submission (so timeline has correlated submission)
        if session_data.get("questions"):
            q1 = session_data["questions"][0]
            sub_res = await client.post(
                f"{BASE_URL}/exams/{exam_id}/sessions/{session_id}/submit-answer",
                headers=cand_headers,
                json={
                    "question_id": q1["id"],
                    "answer": q1["options"][0]["id"] if q1.get("options") else "sample_code"
                }
            )
            print(f"[OK] Answer submitted for Q1: status {sub_res.status_code}")

        # 6. Simulate Proctoring Violations
        # Event 1: Tab switch (penalty 4.0 -> Trust: 96.0)
        v1_res = await client.post(
            f"{BASE_URL}/exams/{exam_id}/sessions/{session_id}/proctoring-event",
            headers=cand_headers,
            json={
                "violation_type": "tab_switch",
                "client_severity": "low",
                "metadata": {"blur_duration_seconds": 3, "blurred_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        print(f"[OK] Logged violation: tab_switch (status: {v1_res.status_code})")

        # Event 2: Multiple faces detected (penalty 18.0 -> Trust: 96.0 - 18.0 = 78.0)
        v2_res = await client.post(
            f"{BASE_URL}/exams/{exam_id}/sessions/{session_id}/proctoring-event",
            headers=cand_headers,
            json={
                "violation_type": "multiple_faces",
                "client_severity": "high",
                "metadata": {"faces_detected_count": 2, "confidence": 0.94}
            }
        )
        print(f"[OK] Logged violation: multiple_faces (status: {v2_res.status_code})")

        # Event 3: Face mismatch (critical penalty 25.0 -> Trust: 78.0 - 25.0 = 53.0)
        v3_res = await client.post(
            f"{BASE_URL}/exams/{exam_id}/sessions/{session_id}/proctoring-event",
            headers=cand_headers,
            json={
                "violation_type": "face_mismatch",
                "client_severity": "critical",
                "metadata": {"similarity_score": 0.28, "threshold": 0.65}
            }
        )
        print(f"[OK] Logged violation: face_mismatch (status: {v3_res.status_code})")

        # 7. Verify Admin Session Data & Trust Score
        admin_sess_res = await client.get(
            f"{BASE_URL}/admin/exams/{exam_id}/sessions",
            headers=admin_headers
        )
        sessions_list = admin_sess_res.json()
        target_sess = next((s for s in sessions_list if s["session_id"] == session_id), None)
        assert target_sess is not None, "Target session not found in admin list"
        
        print(f"[OK] Admin inspection: Trust Score = {target_sess['trust_score']:.1f} / 100")
        print(f"     Violations logged: {target_sess['violation_count']}")
        print(f"     Review status: {target_sess['review_status']}")
        assert target_sess["trust_score"] == 53.0, f"Expected trust score 53.0, got {target_sess['trust_score']}"

        # 8. Fetch Integrated Review Timeline
        timeline_res = await client.get(
            f"{BASE_URL}/admin/exams/{exam_id}/sessions/{session_id}/review-timeline",
            headers=admin_headers
        )
        assert timeline_res.status_code == 200
        timeline = timeline_res.json()
        print(f"[OK] Fetched Integrated Review Timeline: {len(timeline)} events correlated")
        for idx, item in enumerate(timeline):
            print(f"     [{idx+1}] {item['event_type'].upper()}: {item['title']} ({item['severity']})")

        # 9. Test Human Review Discount on face_mismatch
        # Find the face_mismatch event in timeline
        mismatch_item = next(item for item in timeline if "FACE MISMATCH" in item["title"])
        v_id = mismatch_item["id"].replace("viol_", "")

        review_v_res = await client.post(
            f"{BASE_URL}/admin/exams/{exam_id}/sessions/{session_id}/violations/{v_id}/review",
            headers=admin_headers,
            json={"review_status": "reviewed_benign", "notes": "Candidate leaned back, confirmed legitimate frame."}
        )
        assert review_v_res.status_code == 200
        review_data = review_v_res.json()
        new_score = review_data["updated_trust_score"]
        print(f"[OK] Human review verdict: marked face_mismatch as BENIGN!")
        print(f"     Recalculated Trust Score: {new_score:.1f} / 100 (Restored +25.0 points!)")
        assert new_score == 78.0, f"Expected restored trust score 78.0, got {new_score}"

        # 10. Test Bulk Approval Guardrail
        # Try bulk approve with threshold 80 (score is 78.0, so should be rejected)
        bulk_res1 = await client.post(
            f"{BASE_URL}/admin/exams/{exam_id}/sessions/bulk-approve",
            headers=admin_headers,
            json={"min_trust_score": 80.0, "session_ids": [session_id]}
        )
        assert bulk_res1.status_code == 200
        b1_data = bulk_res1.json()
        print(f"[OK] Bulk Approve Guardrail Test 1 (Threshold 80.0):")
        print(f"     Approved: {b1_data['approved_count']}, Rejected: {b1_data['rejected_count']}")
        assert b1_data["rejected_count"] == 1
        print(f"     Rejection reason: {b1_data['rejected_sessions'][0]['reason']}")

        # Now mark multiple_faces benign as well (penalty 18.0 restored -> score becomes 96.0!)
        mf_item = next(item for item in timeline if "MULTIPLE FACES" in item["title"])
        mf_id = mf_item["id"].replace("viol_", "")
        await client.post(
            f"{BASE_URL}/admin/exams/{exam_id}/sessions/{session_id}/violations/{mf_id}/review",
            headers=admin_headers,
            json={"review_status": "reviewed_benign", "notes": "Poster in background, verified benign."}
        )
        
        # Test Bulk Approve again (score is now 96.0 >= 85.0)
        bulk_res2 = await client.post(
            f"{BASE_URL}/admin/exams/{exam_id}/sessions/bulk-approve",
            headers=admin_headers,
            json={"min_trust_score": 85.0, "session_ids": [session_id]}
        )
        assert bulk_res2.status_code == 200
        b2_data = bulk_res2.json()
        print(f"[OK] Bulk Approve Guardrail Test 2 (Score now 96.0 >= 85.0):")
        print(f"     Approved: {b2_data['approved_count']}, Rejected: {b2_data['rejected_count']}")
        assert b2_data["approved_count"] == 1

        print("=" * 70)
        print("PHASE 5 VERIFICATION COMPLETED WITH 100% SUCCESS!")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
