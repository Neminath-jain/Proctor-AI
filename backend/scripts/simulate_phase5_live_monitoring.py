import asyncio
import json
import uuid
import httpx
import websockets

BASE_HTTP = "http://127.0.0.1:8000/api/v1"
BASE_WS = "ws://127.0.0.1:8000/api/v1"


async def main():
    print("=== PHASE 5 REAL-TIME ADMIN MONITORING VERIFICATION ===")

    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1. Login as Admin
        admin_login_res = await client.post(
            f"{BASE_HTTP}/auth/login",
            data={"username": "admin@example.com", "password": "Admin123!"}
        )
        assert admin_login_res.status_code == 200, f"Admin login failed: {admin_login_res.text}"
        admin_token = admin_login_res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("✓ Logged in as Admin")

        # 2. Get Exams list to find an active exam
        exams_res = await client.get(f"{BASE_HTTP}/admin/exams", headers=admin_headers)
        assert exams_res.status_code == 200
        exams = exams_res.json()
        assert len(exams) > 0, "No exams found in database"
        exam = exams[0]
        exam_id = exam["id"]
        print(f"✓ Using Exam: '{exam['title']}' (ID: {exam_id})")

        # 3. Create or login 3 distinct candidate test accounts
        candidates = []
        for idx in range(1, 4):
            email = f"candidate_p5_{idx}@example.com"
            pwd = "Candidate123!"
            # Try login or signup
            login_res = await client.post(
                f"{BASE_HTTP}/auth/login",
                data={"username": email, "password": pwd}
            )
            if login_res.status_code != 200:
                signup_res = await client.post(
                    f"{BASE_HTTP}/auth/signup",
                    json={"email": email, "name": f"Test Candidate {idx}", "password": pwd, "role": "candidate"}
                )
                assert signup_res.status_code in (200, 201), f"Signup failed for {email}: {signup_res.text}"
                login_res = await client.post(
                    f"{BASE_HTTP}/auth/login",
                    data={"username": email, "password": pwd}
                )
            c_token = login_res.json()["access_token"]
            candidates.append({"email": email, "token": c_token, "index": idx})
            print(f"✓ Candidate {idx} ({email}) ready")

        # 4. Start sessions for each candidate
        sessions = []
        for cand in candidates:
            c_headers = {"Authorization": f"Bearer {cand['token']}"}
            start_res = await client.post(f"{BASE_HTTP}/exams/{exam_id}/start", headers=c_headers)
            if start_res.status_code == 200:
                sess_data = start_res.json()
                sess_id = sess_data["session_id"]
            else:
                # If already started, fetch available exams to find session_id
                avail_res = await client.get(f"{BASE_HTTP}/exams/available", headers=c_headers)
                found = None
                for ex in avail_res.json():
                    if ex["id"] == exam_id and ex.get("session_id"):
                        found = ex["session_id"]
                        break
                assert found, f"Could not find or start session for {cand['email']}"
                sess_id = found
            sessions.append({"candidate": cand, "session_id": sess_id})
            print(f"✓ Candidate {cand['index']} session active: {sess_id}")

        # 5. Connect WebSocket client as Admin
        ws_url = f"{BASE_WS}/admin/ws/exams/{exam_id}?token={admin_token}"
        print(f"Connecting Admin WebSocket: {ws_url}")
        
        async with websockets.connect(ws_url) as ws:
            # Receive initial state
            init_msg = await ws.recv()
            init_data = json.loads(init_msg)
            assert init_data["type"] == "initial_state", f"Expected initial_state, got {init_data}"
            print(f"✓ WebSocket received initial_state ({init_data['active_sessions_count']} active sessions)")

            # 6. Inject violations for Candidate 2 (Minor repeat violations - diminishing returns)
            cand2_headers = {"Authorization": f"Bearer {candidates[1]['token']}"}
            sess2_id = sessions[1]["session_id"]
            
            # Post 3 tab switches
            for i in range(3):
                await client.post(
                    f"{BASE_HTTP}/exams/{exam_id}/sessions/{sess2_id}/violations",
                    headers=cand2_headers,
                    json={
                        "violation_type": "tab_switch",
                        "metadata": {"away_seconds": 3, "switch_count": i + 1}
                    }
                )

            # Receive WebSocket broadcast for Candidate 2
            ws_msg2 = await asyncio.wait_for(ws.recv(), timeout=5.0)
            ws_data2 = json.loads(ws_msg2)
            assert ws_data2["type"] == "violation_event"
            assert ws_data2["session_id"] == sess2_id
            print(f"✓ WebSocket broadcast received for tab_switch: new trust score = {ws_data2['trust_score']}")

            # 7. Inject critical violations for Candidate 3 (Face mismatch)
            cand3_headers = {"Authorization": f"Bearer {candidates[2]['token']}"}
            sess3_id = sessions[2]["session_id"]
            await client.post(
                f"{BASE_HTTP}/exams/{exam_id}/sessions/{sess3_id}/violations",
                headers=cand3_headers,
                json={
                    "violation_type": "face_mismatch",
                    "client_severity": "critical",
                    "metadata": {"similarity": 0.22, "threshold": 0.60}
                }
            )

            # Receive WebSocket broadcast for Candidate 3
            ws_msg3 = await asyncio.wait_for(ws.recv(), timeout=5.0)
            ws_data3 = json.loads(ws_msg3)
            assert ws_data3["type"] == "violation_event"
            assert ws_data3["session_id"] == sess3_id
            assert ws_data3["trust_score"] <= 75.0, f"Expected penalty, got {ws_data3['trust_score']}"
            print(f"✓ WebSocket broadcast received for face_mismatch: trust score = {ws_data3['trust_score']}")

            # 8. Query review timeline for Candidate 3
            timeline_res = await client.get(
                f"{BASE_HTTP}/admin/exams/{exam_id}/sessions/{sess3_id}/review-timeline",
                headers=admin_headers
            )
            assert timeline_res.status_code == 200
            timeline = timeline_res.json()
            assert len(timeline) > 0
            print(f"✓ Review timeline fetched successfully ({len(timeline)} events recorded)")
            
            # Find the face_mismatch violation in timeline
            face_viol = next((item for item in timeline if "FACE MISMATCH" in item["title"]), None)
            assert face_viol, "Could not find face mismatch violation in timeline"
            clean_viol_id = face_viol["id"].replace("viol_", "")

            # 9. Test Human Review: Mark face_mismatch as 'reviewed_benign'
            review_res = await client.post(
                f"{BASE_HTTP}/admin/exams/{exam_id}/sessions/{sess3_id}/violations/{clean_viol_id}/review",
                headers=admin_headers,
                json={"review_status": "reviewed_benign", "notes": "Candidate lighting was temporarily obstructed"}
            )
            assert review_res.status_code == 200
            review_data = review_res.json()
            print(f"✓ Human review applied: Violation marked benign. Recalculated trust score = {review_data['updated_trust_score']}")

            # Verify WebSocket pushed the recalculation
            ws_update_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            ws_update = json.loads(ws_update_msg)
            assert ws_update["type"] == "session_update"
            print(f"✓ WebSocket session update broadcast verified: trust score recalculated in real-time!")

            # 10. Test Bulk Approval with Safety Guardrail
            # Session 1 should qualify (score >= 85), Session 3 may or may not qualify depending on other violations
            bulk_res = await client.post(
                f"{BASE_HTTP}/admin/exams/{exam_id}/sessions/bulk-approve",
                headers=admin_headers,
                json={"min_trust_score": 85.0}
            )
            assert bulk_res.status_code == 200
            bulk_data = bulk_res.json()
            print(f"✓ Bulk Approval Guardrail executed: Approved {bulk_data['approved_count']} sessions, rejected {bulk_data['rejected_count']}")

    print("\n=======================================================")
    print("ALL PHASE 5 REAL-TIME MONITORING VERIFICATIONS PASSED!")
    print("=======================================================")


if __name__ == "__main__":
    asyncio.run(main())
