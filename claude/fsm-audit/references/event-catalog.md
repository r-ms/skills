# Event catalog

Read at step 4 of Scout. The usual mistake is a table with only the happy-path events. Real bugs live in the events below. For each class: the question to ask, and where to look in code.

## Contents

- Core classes
- Identity and history
- In-process latches and memos
- Where state lives in two places
- Time and cold start
- Read errors
- How sure are we about this list

## Core classes

**Repeat and layers of retries.** Ask: what happens if this handler runs twice? How many layers retry the same call? Look for: retry decorators and loops (`retry`, `backoff`, `tenacity`, `while true` with sleep) at several levels of one call chain; no cap, no jitter, no budget; a side effect under a retry with no idempotency key. Retries multiply across layers.

**Restart between two writes.** Ask: if the process dies after write A and before write B, what does the system look like on restart, and who repairs it? Look for functions that do several writes or an external call in a row with no marker of which step finished.

**Late or out-of-order event.** Ask: can an old event arrive after a newer state was reached? Look for handlers that set the status straight from the event type (`paid` from a `paid` event) without checking the current status; ordering by a coarse `created_at`; webhooks (providers do not promise order).

**Second writer.** Ask: who else writes this field? Look for: the main handler, a retry path, an admin action, a migration, a script, another service, a watchdog.

**Expired lease and zombie writer.** Ask: can the holder of a lease or lock write after it expired (pause, network stall)? Looking at the clock right before writing does not help. Look for lock or lease with a TTL followed by a write that does not check owner or epoch in the write itself (no `WHERE owner = ? AND epoch = ?`, no version number). The pattern `if still_leader(): write()` is check-then-act, not protection.

**Owner name is not a fencing token.** If a write is guarded by owner identity only (`WHERE owner = ?`), a stale run of the same owner (same worker name) still matches the new lease after a reap and re-claim. Ask whether the guard compares an attempt number, epoch or lease id. Look for `owner` guards without a counter that changes on each claim.

**Watchdog or reaper as writer.** Ask: how does this job prove the owner is dead, or does it only know time passed? Look for `UPDATE ... SET status='pending' WHERE status='running' AND started_at < now() - X`. A reaper that acts on elapsed time alone creates a second writer if the original is alive. Add a row "owner alive, reaper thinks dead" for every reaper.

**Poison message with no terminal exit.** Ask: is there a terminal status after the attempts are exhausted? Look for a loop "failed -> back to pending" with no attempt counter and no final `dead`/`failed`, queues with no dead-letter path, retry policies with no maximum attempts or expiry.

**Resurrection of a terminal state.** Ask: can an event move `done`, `cancelled` or `paid` back to something earlier? Look for writes into a terminal state's field without a from-guard, and for "heal" or "retry" paths that reset terminal rows.

## Identity and history

**Update addressed by key when a key can have several records.** Ask: when the same key is enqueued again after a terminal state, which record does each setter patch (the live one, the last one, the first)? Look for setters that locate the record by key plus a state predicate and others that use "last index" or "first match"; a flag such as `notified` or `outcome_sent` written to the wrong record means a final message is never sent or is sent twice. Check for history rows or soft-deleted rows that share the key.

**Record identity inside pure reducers.** For state held as a document or array with immutable patches, the guard is a lookup helper. Ask: what does the helper do on no match (silent no-op), on several matches, and does the caller notice?

## In-process latches and memos

State that lives in module globals, singletons or caches inside one process: a "ready" latch, a memo of an external fact, a circuit breaker, a health gate.

**Memo of an external fact with no invalidation.** Ask: what clears the flag when the fact changes (the server died, the token expired, the file was removed)? A latch set to true once and never reset keeps work going to a dead dependency. Look for a flag assigned in one branch and never assigned the opposite value.

**Two clocks or timers for one verdict.** Ask: do two timeouts or rules decide the same question and can they disagree (a force-open after one timeout while another path still waits)? Look for several places computing "is it available" from different inputs.

**Blocking wait versus shutdown.** Ask: does a long wait or retry loop read the shutdown signal? Look for sleeps and polling loops that never check a stop flag.

**Probe that stops after the latch is set.** Ask: once the flag is true, does anything keep probing? Look for health checks guarded by `if not ready`.

**Per-process copies.** With several worker processes each holds its own copy of the flag; ask whether they can disagree and what coordinates them.

**Reach depends on configuration.** Pool, profile, flag and environment values decide whether a branch exists in production. Record the condition under which the finding applies (`reach`) and name the configuration you could not read.

## Where state lives in two places

**Two stores, one fact.** A write to the database followed by a publish, an HTTP call, a file or a cache key change is not atomic. Ask: what does the system see if it fails between them? Look for both steps in one function with no outbox and no reconciler.

**Cache or copy as second state.** Ask: who writes the cache, who invalidates, what happens when a read-miss races with a write-invalidate? Look for `get, miss, read db, set` with no version or token; invalidation on some write paths and not on others; a cache write after an async event.

**Stale snapshot inside a message.** Ask: does the handler act on a copy of the record carried in the message or event instead of re-reading? Look for objects, DTOs or JSON copies put on a queue; the handler should take an id, read the current state and check the from-state.

**Entity versus its job.** The entity says `processing` and the job row is dead, or the entity is `ready` and the job failed afterwards. Build the pair table (see `table-and-findings-format.md`).

## Time and cold start

**Timers as events.** TTLs, ETAs, cron, delayed sends, lease and visibility timeouts. Ask: can the timer fire twice, or after the state has moved on? Look for `eta`, `countdown`, `delay`, `schedule_at`, `run_after`, TTL values next to a lease or broker timeout. A delayed event that lives longer than the lease horizon gets duplicated. Compare the lease TTL with the worst-case handler duration.

**Stuck states without an exit.** Every non-terminal status (queued, pending, running, processing) needs its own way out by time. "Queued, nobody took it" and "running, the worker vanished" are two different stalls with different timers. Look for non-terminal statuses with no entry timestamp and no timeout.

**Cold start and empty cache.** Ask: what does the machine do right after a restart with an empty cache or in-memory map, and with a partly stale one? Look for a cache or in-memory dictionary on which correctness (not only speed) depends, with no recompute path.

**Feedback loops.** A state that only a restart can leave: retries without a budget plus a cache that cannot refill within the same timeout. Look for refill paths that must fit the same timeout as ordinary requests and for clients that retry without limits.

## Read errors

**"Could not read" treated as "absent".** Ask: after a failed read (storage error, timeout, permission), does the code behave as if the thing does not exist and act on that (delete, recreate, mark failed, skip)? Look for `if err != nil { return false }` right after a stat, key lookup, query or API call with no distinction of the error type; `except Exception: return None`; a result folded into a boolean. An unknown value of a status should be an error, not a default.

## How sure are we about this list

- Retries, restarts, late events, second writers, caches as second state, leases and zombies, reapers, outbox gaps, timers and cold start are described in vendor documentation and engineering literature (see `evidence-base.md`).
- "State is a combination of fields", "silent empty cell is a defect" and "read error read as absent" are practice from real audits, not established results. In particular silence is the default in many state machine designs (unhandled events are dropped), which is why step 6 classifies instead of flagging.
- Do not claim more than that in a report.
