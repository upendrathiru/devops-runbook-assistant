# Runbook: Nightly Build Pipeline

**Pipeline scope:** CI/CD nightly build & regression suite (Jenkins job `nightly-full-build`)
**Owner:** DevOps/CI team
**Last reviewed:** 2026-06-02

## Summary
The nightly build pipeline runs every day at 02:00 UTC. It performs a full clean
build of all services, runs the full regression + integration test suite (unlike
the fast subset run on every PR), builds container images, and publishes them to
the internal registry tagged `nightly-YYYYMMDD`.

## Stages
1. **Checkout** — pulls `main` branch for all repos in the monorepo/service list.
2. **Dependency install** — clean install (no cache) to catch dependency drift.
3. **Build** — compiles/builds all services in parallel (max 8 concurrent jobs).
4. **Unit tests** — full unit test suite, all services.
5. **Integration tests** — spins up a docker-compose environment with test
   databases and runs cross-service integration tests (~45 min).
6. **Image build & scan** — builds Docker images, runs vulnerability scan
   (Trivy), fails the pipeline on any CRITICAL CVE.
7. **Publish** — pushes images to the internal registry with `nightly-<date>` tag
   and updates the `nightly-latest` alias tag.
8. **Report** — posts a summary to #ci-nightly Slack channel with pass/fail
   counts, duration, and links to logs.

## Where to check results
- Jenkins: `https://ci.internal/job/nightly-full-build/`
- Slack summary: posted daily around 03:30–04:00 UTC in `#ci-nightly`.
- Full logs retained for 30 days in the Jenkins job artifacts.

## Failure triage
1. Check the Slack summary for which stage failed first (stages run in order;
   later stages don't run if an earlier one fails).
2. **Build failures** — usually a merge that broke compilation; check most recent
   merges to `main` since last successful nightly.
3. **Test failures** — check if failure is a known flaky test (see
   `flaky-tests-registry.md`) before treating as a real regression.
4. **Image scan failures** — check the Trivy report for the CVE; coordinate with
   the owning team on a patched base image or dependency bump.
5. If nightly fails two nights in a row, it becomes a P2 ticket automatically
   assigned to the CI on-call rotation.

## Common pitfalls
- Nightly uses a clean cache, so failures here that don't reproduce on PR builds
  are often dependency version drift, not code bugs.
- The nightly tag is used by the QA team for manual exploratory testing — a
  broken nightly blocks their testing, so failures should be triaged same-day.
