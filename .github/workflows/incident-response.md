# Runbook: Incident Response

**Scope:** All production incidents (SEV1–SEV4)
**Owner:** DevOps/SRE team
**Last reviewed:** 2026-05-20

## Severity definitions
- **SEV1** — Full outage or critical data loss risk affecting all customers.
- **SEV2** — Major functionality broken or degraded for a significant subset of
  customers.
- **SEV3** — Minor functionality broken, workaround available, limited impact.
- **SEV4** — Cosmetic or low-impact issue, no urgent action needed.

## Immediate response (first 5 minutes)
1. Acknowledge the page/alert.
2. Declare the incident in `#incidents` with severity, service affected, and a
   one-line summary.
3. For SEV1/SEV2: page the incident commander (IC) rotation if not already
   engaged.
4. Start an incident doc (auto-created from the `#incidents` bot `/incident new`
   command) to log timeline, actions, and decisions.

## Investigation
1. Check the service dashboard (Grafana) for error rate, latency, and saturation.
2. Check recent deploys — most incidents correlate with a deploy in the last
   2 hours (`kubectl rollout history` or the deploy log channel).
3. Check upstream/downstream dependency health (status pages, dependency
   dashboards).
4. If a recent deploy is implicated, follow `deployment-rollback.md`.

## Mitigation priorities
1. Stop the bleeding first — roll back, fail over, or disable the feature flag
   before root-causing.
2. Communicate status updates every 15–30 minutes for SEV1/SEV2 in the incident
   channel and status page if customer-facing.
3. Once mitigated, confirm recovery with metrics for at least 15 minutes before
   declaring resolved.

## Resolution & follow-up
1. Declare the incident resolved once metrics are stable and mitigation is
   confirmed.
2. Schedule a postmortem within 2 business days for SEV1/SEV2 (blameless format).
3. File action items from the postmortem as tracked tickets with owners and due
   dates.

## Escalation contacts
- Incident Commander rotation: PagerDuty schedule `ic-primary`.
- Database on-call: PagerDuty schedule `db-oncall`.
- Security incidents: page `#security-oncall` immediately in addition to the
  standard flow — see `security-incident-addendum.md`.
