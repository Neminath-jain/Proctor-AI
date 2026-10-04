import time
from typing import Any, Dict, List, Optional
import httpx
from fastapi import HTTPException, status

from app.core.config import settings

# Canonical Judge0 Language IDs
LANGUAGE_MAP: Dict[str, int] = {
    "python": 71,  # Python 3.8.1 / 3.x
    "py": 71,
    "javascript": 63,  # Node.js 12.14.0 / 18.x
    "js": 63,
    "nodejs": 63,
    "cpp": 54,  # C++ (GCC 9.2.0)
    "c++": 54,
    "java": 62,  # Java (OpenJDK 13.0.1)
}

# In-memory sliding rate limiter (fallback when redis is offline)
_last_submission_timestamps: Dict[str, float] = {}


def check_rate_limit(session_id: str, min_interval_seconds: float = 5.0) -> None:
    """Ensure candidate does not spam the code execution engine."""
    now = time.time()
    last_time = _last_submission_timestamps.get(str(session_id), 0.0)
    elapsed = now - last_time

    if elapsed < min_interval_seconds:
        wait_seconds = round(min_interval_seconds - elapsed, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {wait_seconds}s before submitting another code execution.",
        )

    _last_submission_timestamps[str(session_id)] = now


async def execute_single_test_case(
    source_code: str,
    language: str,
    stdin: str,
    expected_output: str,
    time_limit: int = 3,
    memory_limit: int = 128000,
) -> Dict[str, Any]:
    # Security hardening: reject oversized payloads and unwhitelisted languages
    if len(source_code) > 65536:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Source code exceeds maximum allowed size of 64KB.",
        )

    lang_key = language.strip().lower()
    if lang_key not in LANGUAGE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Language '{language}' is not supported. Supported languages: {sorted(set(LANGUAGE_MAP.keys()))}",
        )
    language_id = LANGUAGE_MAP[lang_key]

    url = f"{settings.JUDGE0_API_URL.rstrip('/')}/submissions?base64_encoded=false&wait=true"
    payload = {
        "source_code": source_code,
        "language_id": language_id,
        "stdin": stdin,
        "expected_output": expected_output,
        "cpu_time_limit": float(time_limit),
        "memory_limit": int(memory_limit),
    }

    from app.services.quota import QuotaService

    allowed, notice = await QuotaService.check_and_increment_judge0()
    if not allowed:
        return _mock_local_evaluation(
            source_code, language, stdin, expected_output, f"Quota Cap: {notice}"
        )

    try:
        async with httpx.AsyncClient(timeout=float(time_limit + 5)) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code not in (200, 201):
                return _mock_local_evaluation(
                    source_code, language, stdin, expected_output, f"Judge0 returned HTTP {resp.status_code}"
                )
            data = resp.json()

            status_info = data.get("status", {})
            status_id = status_info.get("id", 0)
            status_desc = status_info.get("description", "Unknown")

            # Status 13 is Judge0 Internal Error (e.g. cgroups / box mount failure on Windows WSL2)
            if status_id == 13 or status_id == 0:
                return _mock_local_evaluation(
                    source_code, language, stdin, expected_output, f"Judge0 status {status_id}: {data.get('message', 'Internal Error')}"
                )

            stdout = (data.get("stdout") or "").rstrip()
            stderr = (data.get("stderr") or data.get("compile_output") or "")
            expected_clean = expected_output.rstrip()

            # Status 3 is Accepted in Judge0
            passed = (status_id == 3) or (_outputs_match(stdout, expected_clean) and not stderr)

            return {
                "passed": passed,
                "actual_output": stdout,
                "stderr": stderr if not passed else None,
                "status_description": status_desc,
                "runtime": float(data.get("time") or 0.0),
                "memory": int(data.get("memory") or 0),
            }
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        # Fallback simulation for offline dev/mock mode
        return _mock_local_evaluation(source_code, language, stdin, expected_output, str(exc))


def _outputs_match(actual: str, expected: str) -> bool:
    """Check if outputs match literally or semantically (JSON / whitespace agnostic)."""
    import json
    if actual.strip() == expected.strip():
        return True
    try:
        if json.loads(actual) == json.loads(expected):
            return True
    except Exception:
        pass
    if actual.strip().lower() == expected.strip().lower():
        return True
    return False


def _mock_local_evaluation(
    source_code: str,
    language: str,
    stdin: str,
    expected_output: str,
    error_note: str,
) -> Dict[str, Any]:
    """
    Intelligent evaluation fallback when Judge0 sandbox daemon is offline or experiencing cgroups failure.
    Supports both standard console stdout scripts and LeetCode-style function signatures (e.g. def twoSum).
    """
    if language.lower() in ("python", "py"):
        try:
            import io
            import sys
            import inspect
            import re
            import json

            captured_stdout = io.StringIO()
            fake_stdin = io.StringIO(stdin)
            old_stdout = sys.stdout
            old_stdin = sys.stdin
            sys.stdout = captured_stdout
            sys.stdin = fake_stdin

            exec_globals: Dict[str, Any] = {}

            try:
                exec(source_code, exec_globals)
            except Exception as e:
                return {
                    "passed": False,
                    "actual_output": None,
                    "stderr": f"Syntax / Runtime Error: {e}",
                    "status_description": "Runtime Error",
                    "runtime": 0.01,
                    "memory": 5000,
                }
            finally:
                sys.stdout = old_stdout
                sys.stdin = old_stdin

            out = captured_stdout.getvalue().rstrip()

            # If stdout is empty, check if candidate defined a function (LeetCode-style submission)
            if not out:
                user_funcs = [
                    (k, v) for k, v in exec_globals.items()
                    if callable(v) and not k.startswith("__") and getattr(v, "__module__", "") in ("__main__", None, "")
                ]

                if user_funcs:
                    fn_name, fn = user_funcs[-1]
                    sig = inspect.signature(fn)
                    param_names = list(sig.parameters.keys())

                    call_args: List[Any] = []
                    call_kwargs: Dict[str, Any] = {}

                    # Case A: stdin contains assignments, e.g. "nums = [3, 2, 4], target = 6"
                    if param_names and any(f"{p}" in stdin for p in param_names) and "=" in stdin:
                        call_scope: Dict[str, Any] = dict(exec_globals)
                        pattern = r',\s*(?=(?:' + '|'.join(re.escape(p) for p in param_names) + r')\s*=)'
                        for part in re.split(pattern, stdin.strip()):
                            if part.strip():
                                try:
                                    exec(part.strip(), call_scope)
                                except Exception:
                                    pass
                        call_kwargs = {p: call_scope[p] for p in param_names if p in call_scope}
                    else:
                        # Case B: line-by-line inputs or json values
                        lines = [l.strip() for l in stdin.strip().splitlines() if l.strip()]
                        for line in lines:
                            try:
                                val = json.loads(line)
                            except Exception:
                                try:
                                    val = eval(line, exec_globals)
                                except Exception:
                                    val = line
                            call_args.append(val)

                    try:
                        if call_kwargs:
                            ret = fn(**call_kwargs)
                        elif call_args:
                            ret = fn(*call_args[:len(param_names)])
                        else:
                            ret = fn()

                        if ret is not None:
                            if isinstance(ret, (list, dict)):
                                out = json.dumps(ret)
                            else:
                                out = str(ret)
                    except Exception as call_err:
                        return {
                            "passed": False,
                            "actual_output": None,
                            "stderr": f"Error calling {fn_name}: {call_err}",
                            "status_description": "Runtime Error",
                            "runtime": 0.01,
                            "memory": 5000,
                        }

            passed = _outputs_match(out, expected_output)
            return {
                "passed": passed,
                "actual_output": out,
                "stderr": None if passed else f"Expected: '{expected_output.strip()}', Got: '{out}'",
                "status_description": "Accepted" if passed else "Wrong Answer",
                "runtime": 0.01,
                "memory": 5000,
            }
        except Exception as e:
            return {
                "passed": False,
                "actual_output": None,
                "stderr": str(e),
                "status_description": "Runtime Error",
                "runtime": 0.01,
                "memory": 5000,
            }

    return {
        "passed": False,
        "actual_output": None,
        "stderr": f"Code execution service unavailable ({error_note})",
        "status_description": "Engine Offline",
        "runtime": 0.0,
        "memory": 0,
    }


async def evaluate_code_against_test_cases(
    source_code: str,
    language: str,
    test_cases: List[Dict[str, Any]],
    time_limit: int = 3,
    memory_limit: int = 128000,
) -> List[Dict[str, Any]]:
    """Evaluate candidate code against multiple test cases sequentially."""
    results: List[Dict[str, Any]] = []

    for index, tc in enumerate(test_cases):
        tc_in = tc.get("input", "")
        tc_expected = tc.get("expected_output", "")
        is_hidden = tc.get("is_hidden", False)

        res = await execute_single_test_case(
            source_code=source_code,
            language=language,
            stdin=tc_in,
            expected_output=tc_expected,
            time_limit=time_limit,
            memory_limit=memory_limit,
        )

        results.append({
            "test_case_index": index,
            "passed": res["passed"],
            "input": "" if is_hidden else tc_in,
            "expected_output": "" if is_hidden else tc_expected,
            "actual_output": res["actual_output"] if not is_hidden else ("[Hidden]" if not res["passed"] else "[Passed]"),
            "stderr": res.get("stderr"),
            "runtime": res.get("runtime"),
            "memory": res.get("memory"),
            "status_description": res.get("status_description", "Unknown"),
            "is_hidden": is_hidden,
        })

    return results
