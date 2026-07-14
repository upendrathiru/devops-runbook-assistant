# Test Set — 20 DevOps Questions Across Domains

Per the project checklist: validate correctness (does the answer match the
runbook) and citation accuracy (does it cite the right source section) for
each question below. Run `python tests/run_test_questions.py` to execute
these against a live server and print pass/fail on citation presence.

## Deployment (5)
1. How do I roll back a deployment on service X?
2. What's the kubectl command to undo a deployment rollout?
3. How do I roll back to a specific revision, not just the previous one?
4. What should I do before rolling back a deployment?
5. Can I roll back a database migration the same way as app code?

## Database migration (4)
6. Show me the steps for database migration with zero-downtime.
7. What is the expand/contract pattern?
8. How should I backfill historical data during a migration safely?
9. When is it safe to drop an old column after a migration?

## Nightly build / CI (4)
10. What is the nightly build pipeline summary?
11. Where can I check the results of last night's build?
12. What happens if the nightly build fails two nights in a row?
13. Does the nightly build use the same cache as PR builds?

## Incident response (5)
14. What's the first thing I should do when a SEV1 incident is declared?
15. How often should I post status updates during a SEV1 incident?
16. Who do I escalate to for a database-related incident?
17. When should a postmortem be scheduled after an incident?
18. What's the difference between SEV2 and SEV3?

## Out-of-scope / fallback behavior (2)
19. What's the wifi password for the office? (expect: "not sure" fallback)
20. How do I request PTO? (expect: "not sure" fallback, not a hallucinated policy)

## Grading rubric
- **Correctness**: does the answer's content match what the cited runbook
  actually says (no fabricated steps or commands)?
- **Citation accuracy**: does `sources[0]` point to the runbook section that
  actually contains the answer?
- **Fallback behavior**: for questions 19–20, does the system say it's not
  sure rather than inventing an answer?
