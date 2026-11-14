# Table and findings format

Read when you need the shape of the cards. The canonical form is the report JSON (`report-schema.md`): build the table and the findings directly there. The markdown below is the same content for showing in chat. A fixed format matters: models imitate a concrete structure better than prose, and a checker can only verify what is structured.

## Contents

- Entity card
- Writers inventory
- State by event table
- Pair table for an entity and its job
- Finding card
- Provenance labels
- Severity scale
- Worked example

## Entity card

```
Entity:        <name>
Projection:    <field 1>, <field 2> (state-bearing); excluded: <fields and why>
Other holders: <job rows | lease | cache copy | outbox | marker files | projection | other service>
Domains:       <field 1>: {a, b, c}; <field 2>: {true, false}
Declared:      <product of domains> (informational only)
Reachable:     <count or "not determined"> by <which conditions in code>
```

Never print the declared count without the projection above it.

## Writers inventory

One row per writer. Unit and control are mandatory.

```
Unit: SQL statements and call sites that change <field>    Control: found <known site>
Method 1: rg for field and each value literal              Hits: N
Method 2: ast-grep / Semgrep / schema and triggers         Hits: M
Set difference: only in method 1: ...; only in method 2: ...   (close before concluding)
Not visible to search: dynamic field names, ORM bulk update, SQL from strings, codegen, other services
```

| # | Where (file:line) | Writes | From-guard | Guard result read? | Provenance |
|---|---|---|---|---|---|
| 1 | path/a.go:120 | status -> error | none | n/a | quoted |
| 2 | path/b.py:44 | status -> ready | `WHERE status IN ('processing')` | rows affected ignored | quoted |

## State by event table

Rows are states, columns are events from `event-catalog.md`. Cell values:

- `ALLOWED -> <state>` the code performs the transition
- `FORBIDDEN` the code refuses (say how: error, exception, no-op with log)
- `NO-CHANGE` the event is accepted and changes nothing (idempotent repeat)
- `EMPTY` no code path handles this pair
- `N/A` the pair cannot occur (say why, for example "a failure event cannot arrive for a job nobody claimed"); do not use EMPTY for it

Each cell: value, `file:line`, provenance. Example:

| State \ Event | complete(ok) | complete(error) | retry | restart | late complete |
|---|---|---|---|---|---|
| processing | ALLOWED -> done `a.go:88` quoted | ALLOWED -> failed `a.go:101` quoted | EMPTY | ALLOWED -> pending `w.go:40` quoted | NO-CHANGE `a.go:70` derived |
| done | NO-CHANGE `a.go:60` quoted | **EMPTY** (a late error may overwrite done: no guard at `b.go:12`) | EMPTY | NO-CHANGE | NO-CHANGE |

Then the classification of each EMPTY cell: `ignored-by-design` (leaves a log or counter), `error`, `forgotten`, `unclear`. Add the list of forbidden field combinations ("done without result", "pending with a live lease").

## Pair table for an entity and its job

When the entity has a queue job, lease or copy, add a table of entity state x job state, plus a column for what the copy says. Most missed bugs live in the cells where the entity says one thing and its job says another (entity ready, job dead; entity processing, no live job).

## Finding card

```
ID:           F1
Class:        bug | risk | note
Title:        one line
Claim:        what is wrong, one or two sentences
Path:         event sequence from a legal state to the bad state (numbered)
Evidence:     file:line, verbatim quote (must be findable by grep). For a claim of absence there is no quote: give the search, the files searched, a control hit and the result (`absence`).
Provenance:   quoted | derived | reproduced | unconfirmed
Impact:       severity (scale below) and who sees it; notes carry no severity
Reach:        what must be true for this to happen (configuration, caller, timing)
Known to owners: optional; the code documents this as accepted (a comment is data, not evidence)
Refuted if:   the concrete line or test that would make the scenario impossible
Test idea:    sequence of events and expected final state
Writers seen: the writers inventory rows that matter (the skeptic needs them)
Skeptic:      confirmed | refuted (reason: line or test) | not sure (reason) | not checked
```

## Provenance labels

- `quoted`: the code states it; the quote is verbatim.
- `derived`: inferred by reading several places; say which.
- `reproduced`: a scratch test or trace showed it (only if allowed to run code).
- `unconfirmed`: plausible but not backed; keep out of the bug list.

## Severity scale

1. Data or user content lost for good, or a wrong result that cannot be undone. A silently dropped result that loses data belongs here, not at 4.
2. Wrong result visible to a user or customer.
3. Stuck forever without an alarm.
4. Silent failure with a mild consequence (an ignored counter, a dead field).

1 is the most severe. Rank by consequence first and by visibility second, not by how elegant the bug is. Keep `bug`, `risk` and `note` as separate classes; mixing them inflates the list.

## Worked example (anonymized)

Entity: background job. Projection: `status` (pending, processing, done, dead), `attempts`, `lease_until`.

Writers inventory (unit: SQL statements changing `status`): 6 found, control found; `UPDATE jobs SET status='pending' WHERE status='processing' AND lease_until < now()` (watchdog) has a from-guard but no proof the owner is dead.

Table cell: `done` x `late fail event` = EMPTY: the error handler runs `UPDATE jobs SET status='dead' WHERE id=$1` without `AND status IN ('processing')`.

Finding F1 (bug, severity 2): a late failure from a slow worker overwrites `done` with `dead` after another worker finished. Path: worker A leases job; lease expires; watchdog resets to pending; worker B completes (done); worker A fails and writes dead. Evidence: `jobs.go:211` quote `UPDATE jobs SET status='dead' WHERE id=$1`. Refuted if: a row lock, version column or `status` condition exists in the enclosing transaction. Test: A leases, expire lease, B completes, A fails; expect `done`.
