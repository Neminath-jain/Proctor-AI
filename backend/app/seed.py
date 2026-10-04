import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.exam import Exam, ExamStatus
from app.models.question import Question, QuestionType

async def seed_data():
    print("[SEED] Checking and seeding initial demo data to Supabase database...")
    async with AsyncSessionLocal() as session:
        # 1. Admin User
        admin_email = "admin@example.com"
        res_admin = await session.execute(select(User).where(User.email == admin_email))
        admin = res_admin.scalar_one_or_none()
        if not admin:
            admin = User(
                id=uuid.uuid4(),
                email=admin_email,
                name="Head Invigilator",
                password_hash=hash_password("Admin123!"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            print(f"Created Admin user: {admin_email} (password: Admin123!)")
        else:
            admin.password_hash = hash_password("Admin123!")
            admin.is_active = True
            await session.commit()
            print(f"Updated Admin user password: {admin_email} (password: Admin123!)")

        # 2. Candidate User
        cand_email = "candidate@example.com"
        res_cand = await session.execute(select(User).where(User.email == cand_email))
        cand = res_cand.scalar_one_or_none()
        if not cand:
            cand = User(
                id=uuid.uuid4(),
                email=cand_email,
                name="Alex Candidate",
                password_hash=hash_password("Candidate123!"),
                role=UserRole.CANDIDATE,
                is_active=True,
            )
            session.add(cand)
            await session.commit()
            print(f"Created Candidate user: {cand_email} (password: Candidate123!)")
        else:
            cand.password_hash = hash_password("Candidate123!")
            cand.is_active = True
            await session.commit()
            print(f"Updated Candidate user password: {cand_email} (password: Candidate123!)")

        # 3. Demo Exam
        res_exam = await session.execute(
            select(Exam).where(Exam.title == "CS301: Computer Systems & Coding Assessment")
        )
        existing_exam = res_exam.scalar_one_or_none()
        if not existing_exam:
            now = datetime.now(timezone.utc)
            exam = Exam(
                id=uuid.uuid4(),
                title="CS301: Computer Systems & Coding Assessment",
                description="Comprehensive midterm examination covering algorithms, data structures, and Python programming with live proctoring enforcement.",
                created_by=admin.id,
                duration_minutes=45,
                start_time=now - timedelta(hours=1),
                end_time=now + timedelta(days=14),
                status=ExamStatus.PUBLISHED.value,
                enable_browser_proctoring=True,
                max_fullscreen_exits=3,
                fullscreen_warning_timeout_seconds=10,
                max_tab_away_seconds=60,
                paste_char_threshold=50,
            )
            session.add(exam)
            await session.commit()
            await session.refresh(exam)

            # Add Questions
            q1 = Question(
                id=uuid.uuid4(),
                exam_id=exam.id,
                type=QuestionType.MCQ.value,
                question_text="What is the average and worst-case time complexity of searching an element in a balanced Binary Search Tree (such as an AVL or Red-Black Tree)?",
                points=5.0,
                order=1,
                is_multiselect=False,
                partial_credit=False,
                options=[
                    {"id": "opt_a", "text": "O(1) average, O(n) worst-case"},
                    {"id": "opt_b", "text": "O(log n) average, O(log n) worst-case"},
                    {"id": "opt_c", "text": "O(n) average, O(n log n) worst-case"},
                    {"id": "opt_d", "text": "O(log n) average, O(n) worst-case"},
                ],
                correct_answer="opt_b",
            )

            q2 = Question(
                id=uuid.uuid4(),
                exam_id=exam.id,
                type=QuestionType.MCQ.value,
                question_text="Which of the following HTTP request methods are designed to be idempotent according to RFC 7231 / RFC 9110 specifications?",
                points=5.0,
                order=2,
                is_multiselect=True,
                partial_credit=True,
                options=[
                    {"id": "opt_get", "text": "GET"},
                    {"id": "opt_post", "text": "POST"},
                    {"id": "opt_put", "text": "PUT"},
                    {"id": "opt_delete", "text": "DELETE"},
                    {"id": "opt_patch", "text": "PATCH"},
                ],
                correct_answer=["opt_get", "opt_put", "opt_delete"],
            )

            q3 = Question(
                id=uuid.uuid4(),
                exam_id=exam.id,
                type=QuestionType.CODING.value,
                question_text="Write a Python function that reads a line of text from standard input, reverses each word in the string individually while keeping their original word order, and prints the result to standard output.\n\nExample:\nInput: Hello World\nOutput: olleH dlroW",
                points=10.0,
                order=3,
                starter_code={
                    "python": 'import sys\n\ndef reverse_words():\n    # Read input from standard input\n    line = sys.stdin.read().strip()\n    # TODO: Reverse each word and print to stdout\n    pass\n\nif __name__ == "__main__":\n    reverse_words()\n'
                },
                allowed_languages=["python"],
                test_cases=[
                    {
                        "input": "Hello World",
                        "expected_output": "olleH dlroW",
                        "is_hidden": False,
                    },
                    {
                        "input": "Online Exam Proctoring System",
                        "expected_output": "enilnO maxE gnirotcorP metsyS",
                        "is_hidden": True,
                    },
                    {
                        "input": "Python",
                        "expected_output": "nohtyP",
                        "is_hidden": True,
                    },
                ],
                time_limit=3,
                memory_limit=128000,
            )

            session.add_all([q1, q2, q3])
            await session.commit()
            print(f"Created Published Exam '{exam.title}' with 3 questions (ID: {exam.id})")
        else:
            print(f"Demo exam already exists: {existing_exam.title}")

        print("Seed check complete!")

if __name__ == "__main__":
    asyncio.run(seed_data())
