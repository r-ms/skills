# Verification ladder (optional, opt-in)

Read only if the user asks for more than reading: "prove it", "write tests for the table", "model this". The default of the skill stops at level 1. Levels 2 and above run or generate code and need the user's explicit consent; keep generated files outside the audited repository or in a throwaway copy unless the user says otherwise.

## Contents

- Levels
- Level 2: executable model and property-based tests
- Language tools for level 2
- Pitfalls of model-based tests
- Levels 3 and 4: models of the design and trace checking
- Data as evidence of reachability

## Levels

0. Table and review (the default Scout).
1. Assertions or unit tests generated from the table, one test per cell that matters, with the cell's `file:line` in the test name.
2. A small executable model of the entity plus a stateful property-based test: random event sequences, a comparison with the model after every step, a short shrunk sequence and a seed on failure.
3. Model checking of a protocol design (TLA+, P, Quint, Alloy). It checks the design, not the code.
4. Trace checking: replay real execution traces against a model. Costly.

Go up only when a cheaper level cannot answer the question and the entity is worth it (money, user data, ownership, multi-party protocols).

## Level 2: executable model and property-based tests

- Write the model from the table and the contract, not by copying the implementation; a model copied from the code tests the code against itself and finds nothing. Keep it tiny (a dict, a set, a min).
- One table row is one action: precondition, transition, postcondition.
- Add the events the table calls out that the tool will not invent: crash and restart, lease expiry, repeat delivery, late event, edit from outside. Anything outside the action list is never tested.
- Count how often each action runs and which states are reached; a test that never reaches the interesting state passes for the wrong reason.
- Keep the model immutable; clean state between runs (database, files, cache, globals); save the seed and the failing path in the report.
- Prefer a lightweight model written in the language of the code and run in CI for a small self-contained module; it is the variant with the best reported results in industry (an executable reference model checked against the implementation with random sequences). Do not promise that it covers concurrency.

## Language tools for level 2

| Language | Tool | Notes |
|---|---|---|
| Go | `pgregory.net/rapid` (`StateMachine`, `T.Repeat`) | Active, shrinking, no dependencies; single goroutine for reproducibility. `gopter` has a `commands` package, older. |
| TypeScript / JavaScript | `fast-check` (`commands`, `modelRun`, `asyncModelRun`, `scheduledModelRun`) | Replay needs seed, path and replay path. The async runner is sequential; use the scheduler to explore completion orders. |
| Python | `Hypothesis` (`RuleBasedStateMachine`) | `precondition` and `invariant` do not see bundles; awkward with pytest fixtures and parametrize. |
| Java / JVM | `jqwik` (ActionChain) | The newer API was marked experimental; exact replay of a chain is not guaranteed. |
| Kotlin | no built-in stateful mode found | Write a manual loop over a property test, or use `jqwik` from Kotlin. Weak evidence; verify. |
| Rust | `proptest-state-machine` (`ReferenceStateMachine`, `StateMachineTest`) | Sequential only. `Stateright` checks actor models, not arbitrary code. |
| C# / .NET | `FsCheck` (`Experimental.Machine`) | Experimental namespace, pin the version; model must be immutable. |
| Erlang | `PropEr` (`proper_statem`, `parallel_commands`) | Parallel mode needs `erlang:yield/0` in the code under test. |
| Elixir | `PropCheck.StateM` | Wrapper over PropEr. |
| Haskell | `quickcheck-state-machine` | Includes linearizability checking; check maintenance status. |
| Scala | `ScalaCheck` `Commands` | API changed in 1.12.0; pin the version. |
| C++ | `RapidCheck` (`rc::state`) | Preconditions are rechecked while shrinking. |
| C | none found | Write a manual loop. |

Tool status was read from documentation in 2026; check versions before relying on them.

## Pitfalls of model-based tests

- A green run is not proof. It is random search, not a proof for the real code.
- Mutable models break shrinking and replay.
- State that is not reset between runs makes tests flaky.
- Slow real databases: cap the number of runs; prefer an in-memory fake only if it models the same transitions (a fake that is more permissive than the real system hides bugs).
- Values that differ between test and production (a cache in tests that hid a branch in production) invalidate the model; compare parameter values.

## Levels 3 and 4: models of the design and trace checking

- TLA+ and similar find design errors that tests miss; reported on-boarding is a few weeks per engineer. They check a design, not the code; the link to the code is manual.
- Trace validation of a large production codebase against a specification was reported as impractical in one industrial case (about ten weeks of two engineers, the work was abandoned), because a specification written to explain a design does not match the code structure, and a less abstract model made the state space explode (from tens of thousands to hundreds of thousands of states). The lesson: build the table from events observable in the code, one row per place in the code.
- Offer levels 3 and 4 only for multi-party protocols (replication, consensus, distributed locking) and only on request.

## Data as evidence of reachability

Reading code cannot say which combinations occur. A read-only aggregate on a copy or replica can: count rows by each combination of the state fields (`GROUP BY status, flag_a, flag_b`) and compare with the table's allowed combinations; rows in a forbidden combination are the bug's footprint, zero rows in an allowed one are candidates for dead states. Rules: only with the user's explicit consent and read-only access, never against production without approval, print counts and never row contents, and state that the data shows the past, not what is possible. Process mining over audit logs and passive automata learning from traces (k-tails, RPNI, for example in AALpy) can build a candidate model from logs; treat any learned model as a hypothesis with a stated input alphabet and depth.
