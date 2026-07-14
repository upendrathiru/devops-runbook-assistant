# Runbook: Rolling Back a Deployment

**Service scope:** All services deployed via the standard CD pipeline (e.g. service-x, service-y, service-payments).
**Owner:** Platform/DevOps team
**Last reviewed:** 2026-05-01

## When to use this runbook
Use this procedure when a newly deployed release is causing errors, elevated latency,
failed health checks, or a spike in 5xx responses, and the fastest safe recovery is
reverting to the last known-good version.

## Pre-checks
1. Confirm the incident/alert in the monitoring dashboard (Grafana > Service Health).
2. Identify the last known-good release tag from the deployment history
   (`kubectl rollout history deployment/<service-name> -n <namespace>`).
3. Notify the on-call channel (#incidents) that a rollback is starting.

## Rollback steps (Kubernetes-based services)
1. Check current rollout status:
   `kubectl rollout status deployment/<service-name> -n <namespace>`
2. Roll back to the previous revision:
   `kubectl rollout undo deployment/<service-name> -n <namespace>`
   - To roll back to a specific revision instead of the immediate previous one:
     `kubectl rollout undo deployment/<service-name> --to-revision=<N> -n <namespace>`
3. Watch the rollout complete:
   `kubectl rollout status deployment/<service-name> -n <namespace> --timeout=180s`
4. Verify health:
   - Check `/healthz` endpoint returns 200.
   - Confirm error rate and latency return to baseline in Grafana within 5 minutes.
5. Update the incident channel with rollback confirmation and current service status.

## Rollback steps (service X specific — blue/green)
Service X uses blue/green deployment behind the load balancer.
1. In the deployment console, select the previous "green" (stable) target group.
2. Shift traffic weight back to 100% stable / 0% new via the load balancer console.
3. Confirm traffic shift completed (check active target group in LB dashboard).
4. Terminate or freeze the bad "blue" instances after 15 minutes of stable traffic
   (do not terminate immediately — keep for post-incident diagnostics).

## Post-rollback
1. File an incident report with root cause, timeline, and rollback actions taken.
2. Freeze further deploys to the affected service until root cause is understood.
3. Add a regression test covering the failure if applicable.

## Common pitfalls
- Rolling back database migrations is **not** covered by this runbook — see
  `database-migration-zero-downtime.md`. Do not blindly roll back app code if a
  forward-incompatible DB migration has already run.
- Rollback does not undo consumed queue messages or already-sent side effects
  (emails, webhooks) — check downstream systems separately.
