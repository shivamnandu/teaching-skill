# Pipeline State Machine

The formal definition behind `teaching-pipeline`. The current state is **derived, never
remembered**: it is a pure function of the Course Passport plus today's date plus the
stored academic calendar. Nothing in this file depends on conversation history — that is
what makes the pipeline resumable from a fresh session.

## States

| State | Kind | Meaning |
|-------|------|---------|
| `S0_CONTEXT` | stage | Intake; passport being initialized |
| `S1_DESIGN` | stage | course-designer producing/repairing the design |
| `G1_ALIGNMENT` | gate | Alignment Gate running or awaiting professor acknowledgment |
| `S2_BUILD` | stage | lesson-builder producing the current batch |
| `S3_ASSESS` | stage | assessment-architect producing instruments + integrity-check |
| `G3_QUALITY` | gate | Quality Gate running or awaiting acknowledgment |
| `S4_DELIVER` | loop | The term; one sub-cycle per teaching week |
| `S5_REFLECT` | stage | teaching-reflector eval-analysis + triangulation |
| `S6_IMPROVE` | stage | iteration_coach assembling the iteration record |
| `DORMANT` | rest | Between terms; iteration record written; awaiting `new-term` |

Gate states carry a **round counter** (`round ∈ {1,2,3}`), reset on every PASS.

## Diagram

```
                       mid-entry edges (validate, then enter) ──────────┐
                                                                        │
 ┌──────────┐   ok    ┌──────────┐  done   ┌──────────────┐   pass+ack ▼
 │S0_CONTEXT├────────►│ S1_DESIGN├────────►│ G1_ALIGNMENT ├──────────► S2_BUILD
 └──────────┘  🧑      └──────────┘  🧑     └──────┬───────┘            │ 🧑 per batch
      ▲                     ▲                     │ FAIL (round++)     │ batch done
      │ new course          └─────────────────────┘ round≤3            ▼
      │                       round>3 → professor decision         S3_ASSESS
      │                                                                │ 🧑 per instrument
 ┌────┴────┐   new-term: redesign brief + iteration_history            │ plan covered +
 │ DORMANT │◄────────────────────────────┐                             ▼ integrity-check
 └────┬────┘                             │            FAIL→S2 or S3 ┌──────────┐
      │ `new-term` → S1_DESIGN(redesign) │     ┌────────────────────┤G3_QUALITY│
      └──────────────────────────────────┼─────│──(round≤3; >3 →    └────┬─────┘
                                         │     ▼   professor decision)   │ pass+ack
 ┌──────────┐   🧑    ┌──────────┐  term ends   ┌───────────────────────▼──────┐
 │S6_IMPROVE│◄────────┤S5_REFLECT│◄─────────────┤ S4_DELIVER  (weekly self-loop)│
 └──────────┘         └──────────┘   evals in   │  week N → week N+1 → …       │
                                                │  midcourse offer @ wk 4–6    │
                                                └───────────────────────────────┘
```

## Entry invariants

A passport IS in a state when the state's entry invariants hold and the next state's do
not. Invariants are checked top-down; the first unmet set names the current state.

| State | The passport must contain |
|-------|---------------------------|
| `S0_CONTEXT` | (entry) nothing — no passport, or passport missing confirmed `course` facts / `learner_profile` (unknowns explicit, not blank) |
| `S1_DESIGN` | Stage 0 confirmed: course facts + learner_profile present with `confirmed_by_professor` provenance on the intake record |
| `G1_ALIGNMENT` | Design confirmed: non-empty `learning_outcomes` (each with `bloom_level`), `assessment_plan`, `schedule`; syllabus in `artifacts[]` confirmed; `gates.alignment_gate.status != pass` |
| `S2_BUILD` | `gates.alignment_gate.status == pass` — **hard precondition; no materials before a passed Alignment Gate** |
| `S3_ASSESS` | S2 invariants + the professor's chosen build-ahead batch confirmed in `schedule[].artifact_refs` (just-in-time depth counts; "all 16 weeks" is not required) |
| `G3_QUALITY` | Every `assessment_plan` entry has `artifact_ref` set (or an explicit professor deferral logged) and `ai_resilience ∈ {reviewed, redesigned}`; `gates.quality_gate.status != pass` |
| `S4_DELIVER` | `gates.quality_gate.status == pass` + academic calendar stored + today within term dates |
| `S5_REFLECT` | Today past term end (or professor declares term closed); evaluation data provided by the professor |
| `S6_IMPROVE` | Stage 5 report in `artifacts[]` confirmed |
| `DORMANT` | `iteration_history` entry for the just-ended term, confirmed |

Within `S4_DELIVER`, the sub-state is the **calendar week**: `current_week = f(today,
calendar)`, honoring stored breaks. The weekly cycle's own position (built-through week,
midcourse offered/declined) is read from `schedule[].artifact_refs` and the passport's
midcourse record.

## Transitions

| # | From | To | Trigger | Guard / notes |
|---|------|----|---------|---------------|
| T1 | `S0_CONTEXT` | `S1_DESIGN` | intake checkpoint confirmed | passport initialized; calendar asked once and stored |
| T2 | `S1_DESIGN` | `G1_ALIGNMENT` | design checkpoints confirmed | course-designer `full` or `redesign` complete |
| T3 | `G1_ALIGNMENT` | `S2_BUILD` | verdict PASS + professor ack | `alignment_gate.status = pass`; round counter reset |
| T4 | `G1_ALIGNMENT` | `S1_DESIGN` | verdict FAIL | `round++`; carry findings; max 3 |
| T5 | `G1_ALIGNMENT` | `S2_BUILD` | round > 3 | escalate-as-decision: professor's recorded choice closes the gate |
| T6 | `S2_BUILD` | `S2_BUILD` | batch confirmed, more batches requested now | build-ahead depth is the professor's choice |
| T7 | `S2_BUILD` | `S3_ASSESS` | chosen batch depth reached + checkpoint | remaining weeks build just-in-time inside S4 |
| T8 | `S3_ASSESS` | `G3_QUALITY` | all plan entries built/deferred + integrity-check run | per-instrument checkpoints confirmed |
| T9 | `G3_QUALITY` | `S4_DELIVER` | verdict PASS + professor ack | `quality_gate.status = pass` |
| T10 | `G3_QUALITY` | `S2_BUILD` / `S3_ASSESS` | verdict FAIL | route to the stage that produced the blocked artifact; `round++`; max 3 |
| T11 | `G3_QUALITY` | `S4_DELIVER` | round > 3 | escalate-as-decision, recorded |
| T12 | `S4_DELIVER` | `S4_DELIVER` | weekly self-loop: week N cycle closes | just-in-time `lesson-builder` `week-batch` for next unbuilt week; `student-mentor` on demand only; `midcourse` offered once at week 4–6 |
| T13 | `S4_DELIVER` | `S5_REFLECT` | term ends (calendar) or professor closes the term | evals may arrive later; state waits at S5 entry until they do |
| T14 | `S5_REFLECT` | `S6_IMPROVE` | eval-analysis checkpoint confirmed | |
| T15 | `S6_IMPROVE` | `DORMANT` | iteration record confirmed + written | redesign brief saved |
| T16 | `DORMANT` | `S1_DESIGN` | `new-term` mode | **the term edge**: course-designer `redesign` with iteration_history evidence + redesign brief attached; new term's calendar asked and stored |
| T17 | (outside) | any stage | `mid-entry` | validate existing materials into the passport (align-check for designs), then enter the first state whose invariants fail — see WORKFLOW.md routing table |

Mid-entry edges (T17) land *before* the gates they precede: imported designs still face
`G1_ALIGNMENT`; imported materials still face `G3_QUALITY`. Exception: a course already
mid-term enters `S4_DELIVER` directly — retroactive gates run only on request, because
blocking a running course on an audit serves no one.

## Resumption algorithm

Run by `passport_keeper_agent` at the start of every fresh session:

```
resume(passport_path, today):
  1. p ← load(passport_path); validate schema; reconcile hand-edits by asking
  2. if p.calendar missing → ask once, store (never invent term dates)
  3. state ← first state (top-down) whose entry invariants fail,
             stepped back to the state being *worked*, i.e.:
             the latest state whose invariants HOLD and whose exit
             transition has not fired
  4. if state == S4_DELIVER:
        week ← week_of(today, p.calendar)            # honoring breaks
        built_through ← max W with artifact_refs ≠ []
        next_action ← build W(week+lead) if built_through < week+lead
                      else weekly CHECK for week
        if 4 ≤ week ≤ 6 and midcourse not offered → include midcourse offer
  5. pending ← artifacts[] entries lacking confirmed_by_professor
               + gate states awaiting acknowledgment
  6. report: state, week (if in term), pending, next_action   # status shape
  7. dispatch next_action via pipeline_orchestrator_agent on confirmation
```

Two invariant properties the algorithm preserves:

- **Determinism:** the same passport + the same date always resumes to the same state.
  If two states' invariants are ambiguous, the passport is missing a confirmation —
  surface the pending confirmation; do not guess.
- **No silent advancement:** resumption never fires a transition by itself. It lands
  *in* a state and proposes the next action; only a professor confirmation moves the
  machine.
