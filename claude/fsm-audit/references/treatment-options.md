# Treatment options

Read at step 9 of Scout, or when the user asks "should this be an enum?". The audit itself never edits code. Converting to an enum or adding guards is a separate change, made by the user or by a different skill.

## Contents

- The five outcomes
- How to decide
- Guards that work and their limits
- Exhaustiveness checks by language
- Price and reversibility
- Canary

## The five outcomes

Report one per entity, with the reason, the price and how to undo it.

1. **Explicit enum or sum type.** Fields that depend on each other and have meaningless combinations (`paid` and `cancelled` both true; `running` with no start time). One type, one writer function, one transition table. Fits when the rules are stable and the domain is closed.
2. **Independent regions.** Axes that really do not interact (a `notifications_enabled` flag next to an order status). Keep them as separate small fields; do not multiply them. The state count is n + m, not n x m.
3. **Split into entities.** One status column that serves several concepts ("payment status" and "fulfilment status" in one field). Give each concept its own field or table.
4. **Guard.** Rules like "never both", or a domain that keeps changing: a conditional update with the rows-affected result read, a version column, a database `CHECK`, a transition table in code. Softer than a type, cheaper to introduce.
5. **Leave it.** Stable, rare, low impact, or the migration costs more than the bug. Say so and why. "No" is a full answer.

## How to decide

- First ask whether the axes are dependent. Dependent fields go into one enum; independent ones stay apart; different concepts get separate entities.
- Strong types ("make illegal states unrepresentable") are best when rules are stable. Practitioners warn that hard constraints are costly to change when domain rules move, and that some "bad" states must still be representable (for example legacy rows). For changing rules prefer soft enforcement: `CHECK ... NOT VALID`, a guarded update, a violation log.
- Do not decide from the size of the declared state space. The product of independent fields is only an upper bound; the real question is how many combinations the code allows and whether the same rule is re-derived in many places.
- A rule such as "not both at once" is hard to build into a type; use a predicate or a database check.

## Guards that work and their limits

**Conditional update, rows-affected read.**

```sql
UPDATE jobs SET status = 'done', updated_at = now()
WHERE id = $1 AND status = 'processing'
RETURNING id;
```

Zero rows means "forbidden or lost a race": log it with from and to states and return a distinct result. An update whose zero-row result is ignored is still a silent empty cell. In PostgreSQL under Read Committed the `WHERE` is re-checked against the latest row version, so this is an atomic from-check; under Repeatable Read or Serializable the application must retry on serialization errors; for other databases check the isolation semantics.

**Version column (optimistic lock).** Detects concurrent writers; not applied by bulk `update()` calls in some ORMs, which bypass it.

**`CHECK` constraint.** Limits values; it cannot see the previous value, so it cannot express a transition. **Trigger on transitions** is safe under concurrency only with serializable isolation or explicit locking.

**Transition table in code.** One function `transition(from, event) -> (to | refused)` with the table as data, one function that writes the column, and a test or lint that no other statement writes it (with a control proving the search finds the known writer). A table that is data can also drive tests.

**Reaper guard.** A job that returns stuck rows to the queue should prove the owner is dead (heartbeat, lease epoch), not just that time passed. Add a fencing token or epoch to the write itself.

## Exhaustiveness checks by language

These make adding a new state a compile or lint error instead of a silent gap. They see only states modeled as a type, never a string column, a set of flags, a cache key or a marker file; convert to a closed list of constants first.

| Language | Check | Notes |
|---|---|---|
| Go | `exhaustive` linter; `go-check-sumtype` for sealed interfaces | `exhaustive` sees named types with constants only. `go-check-sumtype` treats `default` as covering unless configured; the maintained version is a fork. |
| TypeScript | `@typescript-eslint/switch-exhaustiveness-check`; assigning to `never` in the default branch | Needs type-aware linting configured, or the rule does nothing. |
| Python | `typing.assert_never` with mypy or pyright | Behaviour of `match` differs by checker version; test it. |
| Rust | `match` is exhaustive by compiler; `clippy::wildcard_enum_match_arm` flags `_` arms | The clippy lint is off by default. |
| Kotlin | `when` used as an expression over enum or sealed types, without `else` | A `when` statement need not be exhaustive in older language versions. |
| Java, C#, Swift | sealed types with pattern `switch`; switch expressions; Swift `switch` | Mentioned from general knowledge, not checked in the research behind this skill; verify the language version. |

A `default`, `else` or `_` branch silently turns the check off. A catch-all on a state is a finding unless it raises an error.

## Price and reversibility

For every proposal give: files and call sites touched (count from the writers inventory), whether stored values need a migration, whether the change is visible to users, how to roll back (type-only change is reversible by revert; a schema change needs a down path), and the test that proves the guard (a case that must be red without the change).

## Canary

After adding an exhaustiveness check or a guard, prove it works: add a value to the enum (or call the guarded path from a forbidden state) in a scratch branch and expect a red build or a refused transition. Compilers and linters change behaviour between versions and type-aware rules are often disabled in CI without anyone noticing, so keep the canary as a test.
