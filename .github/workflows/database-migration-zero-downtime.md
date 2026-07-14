# Runbook: Zero-Downtime Database Migration

**Service scope:** PostgreSQL-backed services
**Owner:** Backend/DevOps team
**Last reviewed:** 2026-04-18

## When to use this runbook
Use this procedure whenever a schema change (new column, type change, table split,
index change) must be deployed to a live production database without taking the
service offline.

## Core principle: expand/contract
All zero-downtime migrations follow the expand → migrate → contract pattern so that
old and new application code can run against the schema simultaneously during rollout.

## Steps

### 1. Expand phase
1. Add new columns/tables as **nullable** or with safe defaults — never add a
   NOT NULL column without a default in a single step.
2. Deploy this migration alone; do not combine with application code changes.
3. Run migration with `alembic upgrade head` (or the service's migration tool)
   during a low-traffic window, though it should be safe at any time since it's
   purely additive.
4. Verify replication lag stays under 5 seconds during migration
   (`SELECT now() - pg_last_xact_replay_timestamp();` on replicas).

### 2. Dual-write / backfill phase
1. Deploy application code that writes to **both** old and new columns/tables.
2. Backfill historical data in small batches (e.g. 5,000 rows at a time) to avoid
   long locks:
   `UPDATE table SET new_col = old_col WHERE id BETWEEN :start AND :end;`
3. Monitor query latency and lock waits (`pg_stat_activity`) throughout backfill.
4. Confirm backfill completeness with a row-count / checksum comparison between
   old and new columns.

### 3. Migrate reads phase
1. Deploy application code that reads from the new column/table, still writing to
   both.
2. Monitor error rates and correctness for 24–48 hours before proceeding.

### 4. Contract phase
1. Deploy application code that stops writing to the old column/table.
2. After a safe observation window (recommend 1 week), drop the old column/table
   in a separate migration.
3. Never drop a column in the same deploy that stops using it — always leave a
   rollback window.

## Rollback guidance
- Expand-phase migrations (additive) are safe to leave in place even if the app
  rollback happens — do not reverse them urgently.
- Never run a "contract" migration (drop column/table) until you are fully
  confident no code path depends on it, including analytics/reporting jobs.

## Common pitfalls
- Adding an index without `CONCURRENTLY` will lock the table — always use
  `CREATE INDEX CONCURRENTLY`.
- Large backfills without batching can cause replica lag and timeouts.
- Skipping the observation window between phases is the most common cause of
  production incidents from migrations.
