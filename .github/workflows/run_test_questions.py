"""
Fires the 20 test questions from test_questions.md at a running server and
reports whether each got a cited answer vs. a "not sure" fallback.
This is a smoke test for citation presence, not a semantic correctness
grader — a human should still spot-check answers against the source runbooks
per the grading rubric in test_questions.md.

Usage: python run_test_questions.py [base_url]
"""
import sys
import requests

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

QUESTIONS = [
    "How do I roll back a deployment on service X?",
    "What's the kubectl command to undo a deployment rollout?",
    "How do I roll back to a specific revision, not just the previous one?",
    "What should I do before rolling back a deployment?",
    "Can I roll back a database migration the same way as app code?",
    "Show me the steps for database migration with zero-downtime.",
    "What is the expand/contract pattern?",
    "How should I backfill historical data during a migration safely?",
    "When is it safe to drop an old column after a migration?",
    "What is the nightly build pipeline summary?",
    "Where can I check the results of last night's build?",
    "What happens if the nightly build fails two nights in a row?",
    "Does the nightly build use the same cache as PR builds?",
    "What's the first thing I should do when a SEV1 incident is declared?",
    "How often should I post status updates during a SEV1 incident?",
    "Who do I escalate to for a database-related incident?",
    "When should a postmortem be scheduled after an incident?",
    "What's the difference between SEV2 and SEV3?",
    "What's the wifi password for the office?",
    "How do I request PTO?",
]

EXPECT_FALLBACK = {"What's the wifi password for the office?", "How do I request PTO?"}


def main():
    session = requests.post(f"{BASE_URL}/api/session", json={"user_id": "test-runner"}).json()
    session_id = session["session_id"]

    passed, failed = 0, 0
    for q in QUESTIONS:
        resp = requests.post(f"{BASE_URL}/api/chat", json={
            "question": q, "session_id": session_id, "user_id": "test-runner"
        }).json()
        answer = resp.get("answer", "")
        sources = resp.get("sources", [])
        is_fallback = "not sure" in answer.lower()

        if q in EXPECT_FALLBACK:
            ok = is_fallback
        else:
            ok = bool(sources) and not is_fallback

        status = "PASS" if ok else "FAIL"
        passed += ok
        failed += not ok
        top_source = f"{sources[0]['title']} > {sources[0]['section']}" if sources else "(none)"
        print(f"[{status}] {q}\n         -> top source: {top_source}\n")

    print(f"--- {passed}/{len(QUESTIONS)} passed, {failed} failed ---")


if __name__ == "__main__":
    main()
