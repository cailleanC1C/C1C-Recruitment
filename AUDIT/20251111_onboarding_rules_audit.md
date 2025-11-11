# Onboarding Rules Audit — Welcome Inline Wizard

## Executive summary
The welcome wizard consumes a single `rules` free-text column from the onboarding questions sheet, normalises the rows, and runs a very small rule engine in `modules/onboarding/rules.py`. The engine only matches literal answer tokens and applies two actions: mark other questions optional or skip them entirely. It also reuses the same text for legacy jump/goto logic. Rule evaluation happens both in the rolling inline card experience and the modal catch-up flow; visibility is recomputed after every stored answer and is cached per thread session. Failures in the parser or evaluator are swallowed with conservative defaults, so most bad data degrades to "show everything" without surfacing to end users.

A validation pass runs during schema load and blocks deploy-time cache refresh if it encounters unknown targets or clauses that look like the older goto grammar. Once questions are loaded, runtime code trusts the `rules` payload, logs only a handful of issues (e.g., malformed regexes), and assumes downstream consumers handle required vs. optional decisions based solely on the computed visibility map.

## Data sources
- **Sheet tab & columns** – Rows are fetched from the configured onboarding sheet/tab (`resolve_source()`), normalised to lowercase column keys, and filtered by `flow` (`shared/sheets/onboarding_questions.py:L36-L132` and `L292-L328`). Recognised columns include `flow`, `order`, `qid`, `label`, `type`, `required`, `maxlen`, `validate`, `help`, `note`, and `rules`.
- **Sheet field normalisation** – `required` is coerced from truthy text, `validate`/`help` collapse whitespace, select `note` strings become option lists, and the raw `rules` text is trimmed to single-space tokens (`shared/sheets/onboarding_questions.py:L180-L325`).
- **Schema cache** – The welcome controller consumes the cached `Question` dataclass, which mirrors the sheet fields and preserves the `rules` string verbatim (`modules/onboarding/schema.py:L16-L74`).

### Rule-related fields recognised today
- `Question.rules` – free-text clause string (only field interpreted as visibility/jump rules).
- `Question.required` – base required flag before rule overrides.
- `Question.validate` – optional regex or dropdown token source; used for modal validation.
- `Question.type` / `Question.options` / `Question.note` – inform UI widgets and select validation, indirectly affected by skip/optional outcomes.

## Code entrypoints & flow
1. **Sheet load & validation** – `load_welcome_questions()` pulls cached rows, invokes `validate_rules()`, and raises if any rule target/order is unknown (`modules/onboarding/schema.py:L57-L74`, `modules/onboarding/rules.py:L179-L260`).
2. **Session bootstrap** – Controllers cache per-thread sessions that carry answers and the latest `visibility` map (`modules/onboarding/session_store.py:L16-L84`).
3. **Inline rolling card** – `RollingCardSession._recompute_visibility()` runs `evaluate_visibility()` on construction and after each answer; exceptions zero the map and fall back to "show" (`modules/onboarding/controllers/welcome_controller.py:L200-L206`, `L539-L579`).
4. **Modal flow** – When the modal saves, the controller reuses `evaluate_visibility()` to refresh session state before building follow-up modals or resuming inline steps (`modules/onboarding/controllers/welcome_controller.py:L2217-L2260`).
5. **Navigation jumps** – After each inline answer, `next_index_by_rules()` may redirect to another question based on the same `rules` text (`modules/onboarding/controllers/welcome_controller.py:L565-L576`, `modules/onboarding/rules.py:L292-L359`).
6. **Rendering decisions** – UI helpers drop skipped questions and mark optional ones by consulting the shared visibility map (`modules/onboarding/controllers/welcome_controller.py:L270-L303`, `L1170-L1214`, `modules/onboarding/ui/modal_renderer.py:L37-L99`).

## Rule grammar supported today
| Grammar shape | Effect | Notes |
| --- | --- | --- |
| `if <token> skip <targets>` | Marks each resolved target question as `skip` when the source question's answer includes `<token>` (`modules/onboarding/rules.py:L19-L176`). | `<token>` is lower-cased and compared against normalised answer tokens. Targets can be QIDs, order keys, or wildcard prefixes.
| `if <token> make <targets> optional` | Marks targets as `optional` unless already `skip` (`modules/onboarding/rules.py:L19-L176`). | `optional` only downgrades from `show`; it never overrides an existing skip.
| `skip order>=[n] and order<[m]` | Legacy clause recognised only during validation/jump parsing; no runtime action (`modules/onboarding/rules.py:L225-L229`, `L310-L314`). | Treated as a valid clause marker, but no evaluator consumes it today.
| `goto <order>` | Unconditional jump to the first question whose order/QID matches `<order>` (`modules/onboarding/rules.py:L315-L321`). |
| `if <qid> <op> <rhs> goto <order> [else goto <order>]` | Conditional jump using comparison operators (`in, =, !=, <, <=, >, >=`) against the referenced question's stored answer tokens (`modules/onboarding/rules.py:L323-L357`, `L362-L406`). | Right-hand values are trimmed strings; `in` accepts CSV or bracket lists via `_parse_rhs_list()`.

### Operator matrix
| Operator | Meaning | Example clause | Implementation |
| --- | --- | --- | --- |
| `in` | Case-insensitive membership against parsed token list | `if VIBE in [competitive, balanced] goto 305` | `_condition_satisfied()` normalises both sides before matching (`modules/onboarding/rules.py:L392-L406`).
| `=` / `!=` | Equality / inequality on normalised strings | `if REGION = eu goto 210` | Same helper, compares lowered tokens (`modules/onboarding/rules.py:L398-L404`).
| `<`, `<=`, `>`, `>=` | Numeric comparisons on float-cast answers | `if AGE >= 18 goto 250 else goto 999` | Converts both operands to floats; non-numeric answers are ignored (`modules/onboarding/rules.py:L405-L419`).
| *(implicit)* | Literal token match for skip/optional | `if veteran skip 400` | Tokenised answer intersection, no operator syntax (`modules/onboarding/rules.py:L19-L47`).

Answer token extraction supports nested lists, mappings (`{"label":, "value":, "values":}`), and generic iterables; tokens are lower-cased, whitespace collapsed, and hyphen/underscore variants added (`modules/onboarding/rules.py:L50-L88`, `L362-L388`).

## Evaluation model
- **Initial state** – Every question starts with `state = "show"`; visibility maps exist even before any answer is stored (`modules/onboarding/rules.py:L19-L47`).
- **Trigger points** – Inline flow recalculates visibility immediately after storing an answer and before attempting jumps (`modules/onboarding/controllers/welcome_controller.py:L565-L576`). Modal submissions recompute once all payload values are validated and persisted (`modules/onboarding/controllers/welcome_controller.py:L2217-L2254`).
- **Ordering** – Rules are evaluated in sheet order. For each source question, only clauses whose condition token appears in that question's answer are applied (`modules/onboarding/rules.py:L33-L47`). Target resolution prefers explicit QIDs, then exact order keys, then wildcard prefixes (`modules/onboarding/rules.py:L143-L165`).
- **Re-evaluation** – Sessions cache the last visibility map but refresh it after every mutation. `RollingCardSession` also attempts to recompute visibility during initialisation and logs nothing if evaluation fails (`modules/onboarding/controllers/welcome_controller.py:L200-L206`). Session persistence keeps the latest map in memory (`modules/onboarding/session_store.py:L16-L84`).
- **Short-circuiting & fixpoint** – Skip/optional actions are idempotent and applied per clause. There is no iterative fixpoint search; each recomputation starts from a clean `show` map, applies all matching clauses once, and stops. Jump logic (`next_index_by_rules`) processes clauses sequentially and returns the first matching `goto`/`else` without additional reevaluation (`modules/onboarding/rules.py:L292-L359`).
- **Loop protection** – None. Repeated `goto` clauses can bounce between indexes if sheet authors create cycles; the controller simply updates `_current_index` to the returned target and continues (`modules/onboarding/controllers/welcome_controller.py:L565-L576`).

## Required/optional/hidden decision table
| Visibility state | Inline rolling card | Modal text inputs | Post-submit validation |
| --- | --- | --- | --- |
| `show` | Question is rendered; required flag honoured from sheet (`modules/onboarding/controllers/welcome_controller.py:L270-L303`). | Text inputs set `required=True` if the sheet marks the field required (`modules/onboarding/ui/modal_renderer.py:L37-L55`). | Missing select answers flagged if question required (`modules/onboarding/controllers/welcome_controller.py:L2944-L2963`).
| `optional` | Rendered with an "Optional" hint; sheet `required` flag suppressed in runtime checks (`modules/onboarding/controllers/welcome_controller.py:L287-L303`, `L2944-L2959`). | Inputs force `required=False` regardless of sheet flag (`modules/onboarding/ui/modal_renderer.py:L37-L55`). | Modal handler treats blank values as acceptable and skips validation (`modules/onboarding/controllers/welcome_controller.py:L2217-L2238`).
| `skip` | Inline renderer advances past question without showing it (`modules/onboarding/controllers/welcome_controller.py:L270-L278`, `L1170-L1214`). | Skipped questions never appear in modals because `build_modals()` filters them out (`modules/onboarding/ui/modal_renderer.py:L69-L99`). | Downstream summary/required checks ignore them entirely.

## Error handling & logging
- **Schema validation** – `validate_rules()` collects unresolved targets/orders and adds explicit error strings. The loader raises `ValueError`, preventing cache refresh if any rule clause is malformed (`modules/onboarding/rules.py:L179-L260`, `modules/onboarding/schema.py:L67-L74`).
- **Unknown targets at runtime** – `_apply_action()` silently ignores IDs not present in the initial state. Because validation is sheet-driven, unresolved targets simply no-op without logging (`modules/onboarding/rules.py:L168-L176`).
- **Evaluator failures** – Rolling card inline capture logs a warning when recomputation fails but otherwise leaves visibility empty (`modules/onboarding/controllers/welcome_controller.py:L200-L206`, `L1148-L1199`). Modal saves wrap `evaluate_visibility()` without guards, so exceptions would bubble; no dedicated logging exists there.
- **Regex/validation errors** – Bad sheet regexes are logged as warnings but do not block answers (`modules/onboarding/controllers/welcome_controller.py:L672-L699`, `L18-L53`).
- **Diagnostics & telemetry** – Optional `diag` hooks emit events when regex branches fire and when answers are recorded; core logging uses human-readable strings such as "Welcome — modal_submit_ok" or the rolling card `_log_event` lines (`modules/onboarding/controllers/welcome_controller.py:L2240-L2269`, `L615-L627`).
- **Legacy clause handling** – Range skip/goto clauses that fail to parse simply mark the rule set invalid; runtime ignores them silently if they slip through (`modules/onboarding/rules.py:L225-L260`, `L310-L359`).

## Gaps vs v1.1 spec (anticipated `show_if` / `require_if`)
1. Only literal token matches are supported for visibility; there is no structured predicate language or multi-condition AND/OR logic (`modules/onboarding/rules.py:L33-L47`).
2. Optional vs required overrides are limited to a single `optional` downgrade; there is no ability to explicitly re-require a question once marked optional or to express `require_if` on a different source question (`modules/onboarding/rules.py:L168-L176`).
3. Jump logic and visibility share a single `rules` text field, so `goto` syntax conflicts with visibility clauses and forces the parser to ignore anything it cannot classify (`modules/onboarding/rules.py:L113-L133`, `L292-L359`).
4. There is no cycle detection or guard against infinite jump loops when multiple `goto` clauses refer to each other (`modules/onboarding/rules.py:L292-L359`).
5. Error reporting is minimal; most invalid visibility clauses degrade silently to "show" without surfacing to moderators or logs (`modules/onboarding/rules.py:L113-L176`, `modules/onboarding/controllers/welcome_controller.py:L200-L206`).

## Appendix
### Call graph (simplified)
```
Sheets (onboarding_questions) -> schema.load_welcome_questions
                                     |-- validate_rules
WelcomeController
  |-- RollingCardSession
  |     |-- rules.evaluate_visibility
  |     |-- rules.next_index_by_rules
  |
  |-- Modal submit -> rules.evaluate_visibility -> build_modals
  |-- Summary/render -> _visible_state helpers
SessionStore.SessionData.visibility (shared cache)
```

### Key function signatures
- `evaluate_visibility(questions, answers) -> dict[str, dict[str, str]]` (`modules/onboarding/rules.py:L19-L47`).
- `validate_rules(questions) -> list[str]` (`modules/onboarding/rules.py:L179-L260`).
- `next_index_by_rules(current_idx, questions, answers_by_qid) -> Optional[int]` (`modules/onboarding/rules.py:L292-L359`).
- `RollingCardSession._recompute_visibility()` / `_store_answer_and_advance()` orchestrate inline re-evaluation (`modules/onboarding/controllers/welcome_controller.py:L200-L206`, `L539-L579`).
- `WelcomeQuestionnaireModal` constructor enforces optional vs required inputs (`modules/onboarding/ui/modal_renderer.py:L37-L55`).
