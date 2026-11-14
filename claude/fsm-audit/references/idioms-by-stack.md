# Idioms by stack and system kind

Read at step 2 of Scout. The file is long: read only the sections that match the repository (see the contents list) and skip the rest; the "same in every stack" section applies to all. Patterns are starting points for `rg -n` (ripgrep syntax; for plain `grep` use `-E` and drop `(?...)` constructs). Code examples were assembled from vendor documentation and were not executed: test them on the version and database in use. Read-only: these are things to search for, never things to run against the audited system.

## Contents

- What is the same in every stack
- Spring and JPA (Java, Kotlin)
- Ruby on Rails
- Django and SQLAlchemy (Python)
- .NET and EF Core
- PHP and Laravel
- Elixir with Ecto and Oban
- Node.js with Prisma, TypeORM, Sequelize
- Go with database/sql and sqlc
- In-process state and documents
- Swift and Kotlin on mobile
- Sagas and process managers
- Event sourcing and projections
- Subscriptions, billing and webhooks
- Kubernetes controllers
- Schedulers, Airflow, dbt and ETL
- CI pipelines
- Authentication sessions
- UI state

## What is the same in every stack

1. **Two write paths.** Writes through the model (`save`, `SaveChanges`, `flush`) usually carry a version check, events and callbacks. Bulk writes (`update_all`, `QuerySet.update`, `ExecuteUpdate`, `updateMany`, `Query.update`, `@Modifying` queries, `Repo.update_all`, raw `Exec`) skip versions, events, signals and callbacks, and are how conditional transitions are written. Search both paths separately; a guard on one path proves nothing about the other.
2. **The guarded transition is the same everywhere:** `UPDATE ... SET state = :to WHERE id = :id AND state = :from`, then read the affected-row count. Count semantics differ: Django and MySQL drivers in SQLAlchemy count *matched* rows (writing the same value still counts as 1); SQLAlchemy `rowcount` can be `-1` (executemany, RETURNING); not every Go driver supports `RowsAffected`. A zero result is ambiguous (row missing, wrong state, lost race): check that the code can tell them apart when it matters.
3. **Hidden readers and writers:** admin actions, management commands, migrations, seed scripts, ORM events and signals, background jobs, other services.
4. **Stored enum positions are data.** `@Enumerated(ORDINAL)` and integer-backed enums in Rails or EF store the position; reordering the values silently changes the meaning of old rows.
5. **Raw SQL through a driver** (sqlite3, psycopg, JDBC, ADO.NET, `database/sql`): no ORM section applies. State is in SQL strings: search `UPDATE ... SET`, `INSERT INTO` and the cursor or `execute` calls, read each statement's `WHERE`, and check whether the row count is read. For Python the stdlib `ast` module lists every `execute()` call and string constant and is a good independent second method.
6. **An explicit-library presence is not proof** that every transition goes through it: bulk updates bypass libraries such as AASM or django-fsm.
7. **Some parts of the transition table live outside the repository:** provider dashboard settings, scheduler cleanup timeouts, database triggers. Ask, or write "assumed" in the report.

## Spring and JPA (Java, Kotlin)

- State hides in: `@Enumerated` columns (ORDINAL or STRING), nullable `Instant` or `Boolean` fields (`cancelledAt != null`), `@Version` which does **not** apply to `@Modifying @Query` or HQL `UPDATE`, stale entities in a long-lived session, lifecycle callbacks (`@PreUpdate`) that bulk queries skip.
- Search: `@Enumerated\(`, `@Version\b`, `@Modifying`, `createQuery\("update`, `\.set(Status|State)\(`, `get(Status|State)\(\) *(==|!=)`, `findBy\w*(Status|State)`, `OptimisticLockException`, `StateMachine<|@EnableStateMachine|sendEvent\(`.
- Guarded write: `@Modifying(clearAutomatically = true) @Query("update Order o set o.status = :to, o.version = o.version + 1 where o.id = :id and o.status = :from") int transition(...)`; the version must be bumped by hand; `0` means conflict or wrong state.
- Libraries: Spring Statemachine is archived; flag it as a dependency risk, do not recommend it as a target.

## Ruby on Rails

- State hides in: `enum` (integer-backed: order is data), `aasm_state`, generated methods (`paid!`, `paid?`, scopes) that hide the writer from name search, `update_all`, `update_column(s)`, `toggle!` which skip callbacks, validations and (by inference) `lock_version`, callbacks `before_save` and `after_commit`.
- Search: `enum\s+:?\w+`, `aasm|aasm_state|state_event`, `\.(update_all|update_column|update_columns|toggle!|increment!)\b`, `where\(\s*(status|state)\s*:`, `lock_version|locking_column`, `StaleObjectError|with_lock|\.lock!`; after listing enum values, search `\.(pending|paid|failed)!`.
- Guarded write: `Order.where(id: id, status: Order.statuses[:pending]).update_all(status: Order.statuses[:paid], updated_at: Time.current)` returns the count; `raise Conflict if n.zero?`. Through the model: `order.with_lock { ... }` or `lock_version` plus `rescue ActiveRecord::StaleObjectError`.
- Libraries: `aasm`, `state_machines`. AASM does not persist a transition unless you save or use the bang event.

## Django and SQLAlchemy (Python)

- Django state hides in: fields with `choices` (TextChoices, IntegerChoices), `FSMField`, `save()` overrides and `post_save` receivers (skipped by `QuerySet.update()` and `bulk_update`), admin actions and management commands, `select_for_update` (a no-op on SQLite, an error outside a transaction).
- Django search: `FSMField|@transition|ConcurrentTransitionMixin`, `\.filter\(.*\)\.update\(`, `bulk_update\(`, `select_for_update\(`, `@receiver\(\s*(pre|post)_save`, `\.(status|state)\s*=`.
- Django guarded write: `n = Order.objects.filter(pk=pk, status=Status.PENDING).update(status=Status.PAID)`; `n == 0` means not pending or missing. `django-fsm` original is archived (a maintained fork exists); `.update()` bypasses `protected=True`.
- SQLAlchemy state hides in: `version_id_col` protects only entity flush, while `Query.update()` and `Query.delete()` skip it; attribute writes `obj.status = ...` inside handlers followed by `commit`; ORM events (`before_update`).
- SQLAlchemy search: `version_id_col|StaleDataError`, `\.query\(.*\)\.update\(|synchronize_session`, `update\(\w+\)\.where\(`, `\.rowcount\b`, `with_for_update\(`.
- SQLAlchemy guarded write: `res = session.execute(update(Order).where(Order.id == oid, Order.status == Status.PENDING).values(status=Status.PAID))`; `res.rowcount != 1` means conflict (rowcount may be -1 on some drivers).
- Test races on PostgreSQL, not SQLite.

## .NET and EF Core

- State hides in: an enum property (stored as number or string via `HasConversion`), concurrency tokens (`[Timestamp]`, `[ConcurrencyCheck]`, `IsRowVersion`) that protect only the `SaveChanges` path while `ExecuteUpdate`, `ExecuteDelete` and `ExecuteSqlRaw` bypass the change tracker; saga instances in MassTransit.
- Search: `\[Timestamp\]|\[ConcurrencyCheck\]|IsRowVersion|IsConcurrencyToken`, `DbUpdateConcurrencyException`, `ExecuteUpdate(Async)?\(|SetProperty\(`, `ExecuteSql(Raw|Interpolated)`, `enum\s+\w*(State|Status)`, `MassTransitStateMachine<|TransitionTo\(|SagaStateMachineInstance`, `Stateless|\.Permit(If)?\(`.
- Guarded write: `var n = await ctx.Orders.Where(o => o.Id == id && o.Status == Status.Pending).ExecuteUpdateAsync(s => s.SetProperty(o => o.Status, Status.Paid)); if (n == 0) { /* conflict */ }`.

## PHP and Laravel

- State hides in: a `status` string or an enum cast, Eloquent events and observers (`saving`, `updating`) as hidden readers and writers; `Model::where()->update()` and `DB::table()->update()` fire no events; `saveQuietly`, `updateQuietly`, `withoutEvents`.
- Search: `HasStates|allowTransition\(|transitionTo\(`, `::where\(.*\)->update\(`, `DB::table\(.*\)->update\(`, `lockForUpdate\(`, `saveQuietly\(|updateQuietly\(`, `class \w+Observer`.
- Guarded write: `$n = Order::where('id', $id)->where('status', 'pending')->update(['status' => 'paid']); if ($n === 0) { ... }`; check whether MySQL counts changed or matched rows on your setup. Library: `spatie/laravel-model-states`.

## Elixir with Ecto and Oban

- State hides in: `Ecto.Enum` fields, several changeset functions each allowing its own transitions, `Repo.update_all` (no `updated_at`, no `optimistic_lock`), and Oban job states in `oban_jobs` (retryable, discarded, snoozed: retries are hidden transitions); Oban's rescue plugin can restart a job that is still running.
- Search: `Ecto\.Enum`, `optimistic_lock\(|StaleEntryError`, `update_all\(|set:\s*\[`, `cast\(.*:(status|state)`, `use Oban\.Worker|def perform\(`, `\{:discard|\{:cancel|\{:snooze`, `unique:`.
- Guarded write: `{n, _} = from(o in Order, where: o.id == ^id and o.status == ^:pending) |> Repo.update_all(set: [status: :paid, updated_at: DateTime.utc_now()])`; `n == 0` is a conflict.

## Node.js with Prisma, TypeORM, Sequelize

- State hides in: a Prisma enum or string plus an `Int` version that Prisma does not bump for you; TypeORM `@VersionColumn` on the `save()` path only (query-builder `.update()` is not checked, by inference); Sequelize `version: true` on instance `save()` only; status as string constants in TypeScript and `CHECK` constraints in migrations.
- Search: `updateMany\(|\$executeRaw|\$transaction`, `@VersionColumn|OptimisticLockVersionMismatchError|createQueryBuilder\(\)\s*\.update`, `Model\.update\(|OptimisticLockError`, `\.(status|state)\s*=\s*['"A-Za-z]`, `CHECK\s*\(.*(status|state)` in migrations, `createMachine\(|from ['"]xstate`.
- Guarded write (Prisma): `const r = await prisma.order.updateMany({ where: { id, status: 'PENDING', version }, data: { status: 'PAID', version: { increment: 1 } } }); if (r.count === 0) throw new Error('conflict');`. For TypeORM and Sequelize check the shape of the returned count on your version.

## Go with database/sql and sqlc

- State hides in: string or `iota` constants (the Go compiler does not check `switch` exhaustiveness), SQL in `.sql` files for sqlc with `:exec` that ignores the row count, hand-written `Exec` without `RowsAffected`, state spread across struct fields and goroutines.
- Search: `\.ExecContext\(|\.Exec\(`, `RowsAffected\(\)`, `-- name: \w+ :(exec|execrows|one)`, `UPDATE\s+\w+\s+SET\s+.*\b(status|state)\b`, `WHERE\s+.*\b(status|state)\s*=`, `type\s+\w*(Status|State)\s+(string|int)`, `FOR UPDATE|SKIP LOCKED|RETURNING`, `sql\.ErrNoRows`.
- Guarded write (sqlc): `-- name: MarkPaid :execrows` then `UPDATE orders SET status = 'paid' WHERE id = $1 AND status = 'pending';` and `if n == 0 { /* not pending */ }`. Without sqlc: `res.RowsAffected()` and check its error.

## In-process state and documents

- State hides in: module globals and `global` statements, singletons, memoized results, circuit breakers and health gates, in-memory maps; and documents (a JSON file or an array of records) updated by pure reducer functions with immutable patches such as `{ ...r, state: "x" }`.
- Search: module-level assignments of flag-like names plus `global\s+\w+`; `\b(ready|healthy|available|latch|memo|breaker|gate)\b`; `sync\.Once|memoize|functools\.cache|lru_cache`; for reducers `\{\s*\.\.\.\w+,\s*(state|status)\s*:`, `liveIndex|lastIndex|findIndex`, `patch\(`. `find_writers.py --values` finds the object-literal form `{ state: "x" }`.
- Guard vocabulary: the "from-guard" is the precondition the writer checks (a lookup helper, an `if` on the current value); "result read" means the caller notices a refusal. A helper that returns the unchanged state when no record matches is a silent empty cell.
- Check: what resets the latch; per-process copies when several workers run; whether a blocking wait honours shutdown; two clocks deciding one verdict; which record a setter patches when a key has several records (see `event-catalog.md`).
- Fix shape: setters return an explicit result (applied, not found, refused) that callers must handle; one writer function per entity; a test that replays a late event.

## Swift and Kotlin on mobile

- State hides in: several `Bool` and optional properties (`isLoading`, `error`, `data`) in `@State`, `@Published`, `MutableStateFlow` or `LiveData`; transitions in `didSet`, lifecycle callbacks and coroutines; a `switch` with `default:` or a `when` with `else ->` that hides new states.
- Search: `sealed\s+(class|interface)`, `when\s*\(.*\)\s*\{` and `else\s*->`, `MutableStateFlow|\.compareAndSet\(|\.value\s*=`, `@Published|@State\b|didSet`, `\bis(Loading|Error|Loaded)\b`, `switch\s+\w+\s*\{` and `default:`.
- Fix shape: one `sealed` type or enum with associated values and one `reduce(state, event)` function with an exhaustive `switch`/`when` and no default. For state in a local database (Room, Core Data, SwiftData) the conditional-update idiom was not checked.

## Sagas and process managers

- State hides in: a saga row or coordinator object (step, completed steps), or, with choreography, nowhere (the union of entity statuses across services plus events in flight); intermediate statuses (`PENDING`, `APPROVAL_PENDING`) acting as semantic locks; compensations as separate functions never described as transitions; steps after the point of no return that cannot be undone.
- Search: `\b(saga|orchestrat\w*|process_?manager|workflow_?(state|status|step))\b`, `\b(compensat\w*|rollback_?step|undo_?\w+|refund_?on_?(fail|error))`, `\b(pivot|point.of.no.return|irreversible)\b`, `@(KafkaListener|EventHandler|RabbitListener|SqsListener)`.
- Idiom: `UPDATE saga SET step='PAYMENT_DONE' WHERE id=$1 AND step='PAYMENT_PENDING'` in the same transaction as the side effect, plus a table of processed message ids. A saga table without a row for "compensation failed" and without a pivot mark is incomplete.

## Event sourcing and projections

- State hides in: `apply`/`when`/`on` handlers that derive state; projections and read models as a lagging second copy; checkpoints (last processed event per consumer), snapshots, event schema versions (upcasters), a "rebuild in progress" flag. Replays can fire external side effects twice.
- Search: `\b(projection|read_?model|materializ\w+)\b`, `\b(checkpoint|last_?(processed|applied)_?(event|seq\w*|position|offset)?|expected_?version|snapshot|upcast\w*)\b`, `\b(rebuild|replay\w*|catch.?up|is_?replaying)\b`; a publish next to a commit in one function with no `outbox`.
- Idiom: append with the expected version; on conflict reload and retry. A projection updates `WHERE last_seq < $seq` and moves its checkpoint in the same transaction. Check: rebuild from scratch and diff against the live projection.

## Subscriptions, billing and webhooks

- State hides in: a local status and access dates (`status`, `access_until`, `current_period_end`, `cancel_at_period_end`, `grace_until`) separate from the provider's; dunning counters (`retry_count`, `next_attempt_at`); a table of processed event ids; rules defined outside the code (provider dashboard settings: what counts as a status, what happens after the last retry).
- Webhooks are signals, not state: order is not guaranteed, duplicates are normal, retries last days; do not order by a one-second `created` timestamp; do not write state from the payload alone.
- Search: `customer\.subscription\.|invoice\.(paid|payment_failed)|payment_intent\.`, `\b(past_due|unpaid|incomplete|trialing|canceled|paused|grace|dunning)\b`, `(access_until|current_period_end|entitlement\w*)`, `constructEvent|processed_?events|idempotency`.
- Idiom: `INSERT INTO webhook_events(id) VALUES ($1) ON CONFLICT DO NOTHING` (0 rows means duplicate), answer 2xx fast, queue the work, re-fetch the object from the provider API and upsert local state from it.

## Kubernetes controllers

- State is a set of independent conditions in `status.conditions` (Ready, Progressing, Degraded: True, False, Unknown) plus `observedGeneration`; also finalizers and `DeletionTimestamp`, annotations as markers, the existence of external resources, `Requeue` timers. Conditions are not an automaton and the `phase` field is deprecated: for independent conditions the answer is conditions, not one enum.
- Search: `SetStatusCondition|FindStatusCondition|IsStatusConditionTrue`, `Status\(\)\.(Update|Patch)|RetryOnConflict`, `Finalizers|AddFinalizer|DeletionTimestamp`, `ObservedGeneration`, `Requeue(After)?`, `Status\.Phase`, in-memory `sync.Map|map\[` in reconcilers.
- Check: run reconcile twice in a row with no change (it must be a no-op); write status through the status subresource with conflict handling.

## Schedulers, Airflow, dbt and ETL

- Airflow: task instances have many states, some set by the scheduler (queued, up_for_retry, upstream_failed); the run status is derived from leaf tasks (nowhere stored); a reaper closes tasks with no heartbeat; run identity depends on the data interval, so `catchup` and backfill change which runs exist; external markers (`Variable`, XCom, `_SUCCESS`, `.lock`, watermark tables).
- Search: `depends_on_past|catchup|max_active_runs|trigger_rule|retries|execution_timeout|on_(failure|retry)_callback`, `Variable\.(get|set)|xcom_(push|pull)|\.set_state|clear_task_instances`, `heartbeat\w*|zombie|stale|reaper|lease\w*|visibility_?timeout`, `watermark|high_?water|last_?(run|success|loaded)`, `_SUCCESS`.
- Home-grown scheduler idiom: claim `UPDATE runs SET state='running', heartbeat_at=now(), owner=$w WHERE id=$1 AND state='queued'`; heartbeat `... WHERE id=$1 AND owner=$w AND state='running'`; reaper `UPDATE runs SET state='failed' WHERE state='running' AND heartbeat_at < now() - interval '...'`, each with the row count checked. Run the same window twice: the result must not change.
- dbt and ETL: state is the content of the target table (a model reads its own max timestamp via `{{ this }}`); `is_incremental()` is false on the first run or with `--full-refresh`; `unique_key` decides update versus duplicate; late rows behind the filter window are never reprocessed. Search `is_incremental\(\)|\{\{\s*this\s*\}\}|unique_key|on_schema_change|full[-_]refresh|watermark|MERGE INTO|ON CONFLICT`.

## CI pipelines

- State hides in: job outcomes (success, failure, cancelled, skipped) with an implicit `if: success()`; `needs` chains; caches and their keys; artifacts between jobs; concurrency groups; manual approvals; labels, tags and branches used as "deployed version" pointers; a re-run reading old artifacts.
- Search (GitHub Actions): `if:\s*.*(always\(\)|failure\(\)|success\(\)|cancelled\(\))`, `needs:|concurrency:|cancel-in-progress|environment:|continue-on-error`, `actions/(cache|upload-artifact|download-artifact)`. GitLab: `when:\s*(on_failure|manual|always)|allow_failure|rules:|resource_group`. Prefer `!cancelled()` to `always()`.
- Confirm any claim about what CI runs from the job log, not from reading the YAML.

## Authentication sessions

- State hides in: the session row (`created_at`, `last_seen_at`, `expires_at`, `revoked_at`); three clocks (idle, absolute, renewal); intermediate login states as plain booleans (`pending_2fa`, `mfa_verified`, `email_verified`); logout done on the client only (cookie cleared) with no server-side revocation; refresh-token rotation (used or not).
- Search: `session\.(regenerate|destroy|invalidate)|regenerate_?id`, `idle_?timeout|absolute_?timeout|max_?age|revoked(_at)?|logout|refresh_?token`, `mfa_?(verified|pending)|two_?factor|step.?up`, `localStorage\.(set|remove)Item\(.*(token|session)`.
- Idiom: `UPDATE sessions SET revoked_at=now() WHERE id=$1 AND revoked_at IS NULL`, row count checked; reissue the session id after a privilege change or a successful MFA step.

## UI state

- State hides in: groups of booleans (`isLoading`, `isError`, `hasData`, `isSubmitting`) changed in different handlers; cascades of `useEffect` that set flags; reducers that assign state unconditionally on any action; setter-style actions instead of events; request-race tokens, timers and refs outside state.
- Search: `const \[\s*(is|has|should|can)[A-Z]\w*,\s*set\w+\s*\]\s*=\s*useState`, files with three or more boolean `useState(false|true)`, `\b(is|has)(Loading|Error|Success|Fetching|Submitting)\b`, setters called next to each other, `createSlice|createReducer`.
- Fix shape: a discriminated union (`idle | loading | success(data) | error(e)`) and a reducer that changes state only from the states where the event is legal, with an `assertNever` in the default branch. Do not merge truly independent flags (open/closed next to loading) into one union.
