# MERGE NOTES — teaching-skill

Merged on 2026-09-26 from *Teaching Skills* v1.2.0 by Jiaxing Yu (MIT License). `SKILL.md` is the skill itself;
this file is the paper trail: what is different from upstream, how to install the skill, and how the merge
was checked.

## 1. What this is

`teaching-skill` is **one skill** that contains all 15 upstream teaching skills as modules —
89 modes, 76 agent prompts, 30 command recipes, the shared protocols, the
validators and the worked examples. `SKILL.md` is a router: it picks the module for a request, states the
rules that hold everywhere, and tells Claude which file to open next. Each module keeps its complete upstream
workflow, agents, references and templates.

**246 of 279 upstream files are carried into this skill, and nothing is summarized or
paraphrased.** 180 are byte-identical at the same path, 19 are byte-identical but
renamed or moved, and 47 differ only by the registered edits listed in §5. The remaining
33 files are not carried on purpose: 18 compiled `.pyc` caches (derived build debris) and
15 one-line `skills/*` git-symlink stubs, each containing only `../<skill-name>` (redundant when the
skills are modules of one skill). 45 files were generated for the merge: the router, `INDEX.md`,
`MANIFEST.json`, this file, the slash-command wrappers, the merge tooling and one test file.

## 2. Layout

```
teaching-skill/
├── SKILL.md                  the router — the only SKILL.md in the package
├── INDEX.md                  every file, one line each
├── MANIFEST.json             sha256 of every file plus the upstream hash it came from
├── MERGE_NOTES.md            this file
├── MODE_REGISTRY.md          all modes and their commands (upstream file)
├── <15 module folders>/      WORKFLOW.md + agents/ + references/ + templates/  (e.g. course-designer/)
├── shared/                   passport schema, gate protocols, checkpoint protocol, pedagogy, integrity, self-check
├── scripts/                  validators, dashboard, LMS export, document render, registry and link lints
├── commands/                 the command recipes the router reads
├── install/claude-code-commands/   optional wrappers that restore real /ts-* slash commands
├── examples/                 two worked showcase courses (STEM lecture, humanities seminar)
├── docs/ARCHITECTURE.md      pipeline flow, gates, passport data flow
├── tests/                    upstream tests that apply to this layout + merge-integrity tests
├── tools/merge/              how this skill was built and verified (builder, verifier, edit spec, ledger)
├── upstream/                 archived upstream repository files (plugin manifests, CI, Codex builder + its test)
└── README.md, README.zh-CN.md, QUICKSTART.md, CHANGELOG.md, CONTRIBUTING.md, CLAUDE.md, LICENSE, ...
```

## 3. Install and use

- **claude.ai / Claude Desktop:** add `teaching-skill.skill` (a zip file whose single top-level folder is
  `teaching-skill`; an identical `teaching-skill.zip` is provided as well) through your Skills settings.
- **Claude Code:** copy the folder, keeping its name, into your skills directory — Windows PowerShell:
  `Copy-Item -Recurse "<path>\teaching-skill" "$HOME\.claude\skills\teaching-skill"`; macOS/Linux:
  `cp -r <path>/teaching-skill ~/.claude/skills/teaching-skill`. Start a new session.
- **Use it** by asking in plain words ("Design a new course on X for 60 students", "write a midterm blueprint",
  "check these lab reports against my template", 帮我备课) or with an alias: `/teaching-skill ts-exam …`. For the
  short `/ts-exam`-style commands, copy the wrappers in `install/claude-code-commands/` (see its README.md).
- **Python tooling** (optional but recommended): `pip install pyyaml jsonschema` for the validators and the
  dashboard; add `pytest` to run the tests (`requirements-dev.txt`). Pandoc is needed only for DOCX/PDF rendering.
- **Use this skill or the upstream plugin, not both** — installing both would register the same capabilities
  twice.

## 4. Design decisions

1. **One router plus lazily loaded modules, not one giant SKILL.md.** The 15 upstream skill bodies total about
   155 KB; a single `SKILL.md` that size would flood the context on every use, and the Skills API and
   claude.ai reject packages containing more than one `SKILL.md`. So each module's entry file is renamed
   `WORKFLOW.md` (the same rename upstream's own Codex generator uses) and only the router registers.
2. **Upstream layout preserved.** Module folders, `shared/`, `scripts/`, `commands/`, `examples/` keep their
   upstream relative paths, so every path convention, script and test keeps working; only what had to change
   was changed, and each change is registered in `tools/merge/edits.json`.
3. **No paraphrase.** Merging by rewriting workflows would silently lose Iron rules the suite relies on.
   The router adds routing, rules that apply everywhere, and pointers; the modules stay verbatim.
4. **The description is the trigger.** It stays under the 1024-character limit, names the core domains and
   carries English and Chinese triggers; the complete keyword list from all modules is in the router (§3.4).
5. **No `allowed-tools` pre-approval.** Running Python and writing the professor's files go through Claude's
   normal permission prompts.
6. **Real slash commands are optional.** A skill cannot ship `/ts-*` commands, so the command recipes stay
   as files the router reads and thin wrappers are provided for anyone who wants the short commands back.

## 5. Every difference from upstream

### 5.1 Not carried

18 `__pycache__/*.pyc` files and 15 `skills/*` stub files — see §1. Gate G01 verifies each stub
is only a `../<skill>` pointer.

### 5.2 Renamed (15)

Each module's entry file: `<module>/SKILL.md` → `<module>/WORKFLOW.md` (content preserved except where §5.4
lists an edit). Reason: a skill may contain exactly one `SKILL.md`.

### 5.3 Relocated (8), content unchanged

| id | upstream path | now at | why |
|---|---|---|---|
| L01 | .claude-plugin/plugin.json | `upstream/claude-plugin/plugin.json` | plugin manifest describes the upstream plugin; a live .claude-plugin/ at the skill root would look like a (broken) plugin, so it is archived |
| L02 | .claude-plugin/marketplace.json | `upstream/claude-plugin/marketplace.json` | same as plugin.json |
| L03 | .github/ISSUE_TEMPLATE/config.yml | `upstream/github/ISSUE_TEMPLATE/config.yml` | upstream repository/CI file, not skill runtime; archived unmodified |
| L04 | .github/ISSUE_TEMPLATE/skill-misbehavior.md | `upstream/github/ISSUE_TEMPLATE/skill-misbehavior.md` | upstream repository/CI file, not skill runtime; archived unmodified |
| L05 | .github/ISSUE_TEMPLATE/skill-request.md | `upstream/github/ISSUE_TEMPLATE/skill-request.md` | upstream repository/CI file, not skill runtime; archived unmodified |
| L06 | .github/workflows/ci.yml | `upstream/github/workflows/ci.yml` | upstream repository/CI file, not skill runtime; archived unmodified |
| L07 | scripts/build_codex.py | `upstream/dev/build_codex.py` | upstream release tool: needs git and the upstream SKILL.md layout, so it cannot run inside the merged skill; archived unmodified |
| L08 | tests/test_build_codex.py | `upstream/dev/test_build_codex.py` | tests the Codex generator; needs git + upstream layout; archived unmodified |

### 5.4 Text edits

Each entry is an exact string replacement, applied a fixed number of times; the build fails if the source
does not match, and gate G03 recomputes the expected bytes from the untouched upstream file to prove that
nothing else changed.

- **C1** (1 edit in 1 file) — course-designer description says a 6-agent team; the team is 7. *Why:* course-designer/agents/ has 7 files and its own 'Agent Team (7)' heading (async_designer_agent was added in upstream v1.2.0 and the description was not updated). Files: `course-designer/WORKFLOW.md`.
- **C2** (1 edit in 1 file) — assessment-architect description says a 7-agent team; the team is 10. *Why:* assessment-architect/agents/ has 10 files and 'Agent Team (10)' (grade_analyst, group_designer and accommodation_designer were added in v1.2.0). Files: `assessment-architect/WORKFLOW.md`.
- **C3** (1 edit in 1 file) — student-mentor description says a 5-agent team; the team is 6. *Why:* student-mentor/agents/ has 6 files and 'Agent Team (6)' (integrity_case_agent added in v1.2.0). Files: `student-mentor/WORKFLOW.md`.
- **C4** (1 edit in 1 file) — teaching-pipeline says 'Seven extension skills'; its own table lists eight. *Why:* the table directly below the sentence has 8 rows (accreditation-mapper, deck-studio, media-scripter, lab-forge, course-publisher, ta-coordinator, bilingual-courseware, cohort-analyst) and MODE_REGISTRY says '8 extensions'. Files: `teaching-pipeline/WORKFLOW.md`.
- **C5** (1 edit in 1 file) — ARCHITECTURE section 5b says 'Seven extension skills'; its table lists eight. *Why:* same evidence as C4 (the §5b table has 8 rows). Files: `docs/ARCHITECTURE.md`.
- **C6** (2 edits in 1 file) — README.md says 84 modes / 71 agents; the registry, manifests and files say 89 / 76. *Why:* MODE_REGISTRY totals line, plugin.json, marketplace.json, CHANGELOG v1.2.0 and the filesystem all agree on 89 modes and 76 agents; the README counts are left over from v1.1.x. Files: `README.md`.
- **C7** (2 edits in 1 file) — README.zh-CN.md says 84 modes / 71 agents; the truth is 89 / 76. *Why:* same evidence as C6 (the Chinese README mirrors the English one). Files: `README.zh-CN.md`.
- **C8** (5 edits in 2 files) — Gate 3.5 documentation omits check Q4 from the executable core and check T4 from two check lists. *Why:* scripts/check_quality_gate.py lists Q4 under 'Executable here' and implements it (keyword scan for AI-detection tools in artifacts), and shared/quality_gate_protocol.md defines T4 (unresolved-marker scan, added in v1.2.0); ARCHITECTURE and gate_runner_agent still listed 'Q1/Q2/T1/T2/T4/W1' as the executable core and 'T1-T3'/'T2-T3' as the transparency checks. Files: `docs/ARCHITECTURE.md`, `teaching-pipeline/agents/gate_runner_agent.md`.
- **C9** (1 edit in 1 file) — workload_constants.md says the test-blueprint template cites it and that the gate script imports it; neither is true. *Why:* only shared/alignment_gate_protocol.md references workload_constants.md (a search of the whole upstream tree finds no other reference), the blueprint template carries its own exam-item time heuristics and cites nothing, and scripts/check_alignment_gate.py hard-codes the same values (10, 20, 15, 40, 0.25) rather than importing a Markdown file. Found while following the exam workflow in the skill-creator smoke test. Files: `shared/workload_constants.md`.
- **N1** (30 edits in 30 files) — 30 command recipes: 'Skill entry' path points at WORKFLOW.md. *Why:* the module entry file is WORKFLOW.md in the merged skill; SKILL.md there would now be the router. Files: 30 files.
- **N2** (4 edits in 3 files) — teaching-pipeline agents/references: 'SKILL.md' means the module's entry file. *Why:* inside the merged skill a bare SKILL.md is the router, which has different rules; these four mentions cite the pipeline module's own Iron Rules / routing table. Files: `teaching-pipeline/agents/passport_keeper_agent.md`, `teaching-pipeline/agents/pipeline_orchestrator_agent.md`, `teaching-pipeline/references/pipeline_state_machine.md`.
- **N3** (13 edits in 6 files) — docs: statements about a skill's SKILL.md now name WORKFLOW.md. *Why:* keeps MODE_REGISTRY, ARCHITECTURE, CLAUDE, CONTRIBUTING and both READMEs true for the merged layout (ARCHITECTURE's build_codex row keeps 'SKILL.md→WORKFLOW.md' on purpose: it describes that rename). Files: 6 files.
- **P1** (4 edits in 3 files) — references to relocated upstream files now point at their new home. *Why:* build_codex.py and ci.yml moved under upstream/ (see L-moves); without this the docs would name files that no longer exist at those paths. Files: `README.md`, `README.zh-CN.md`, `docs/ARCHITECTURE.md`.
- **S1** (3 edits in 1 file) — scripts/check_links.py accepts WORKFLOW.md skill folders and checks tools/ + upstream/ refs. *Why:* the link checker discovers skill folders by looking for SKILL.md; in the merged layout that file is WORKFLOW.md, so without this patch every skill-relative reference would be skipped as 'external'. Files: `scripts/check_links.py`.
- **S2** (7 edits in 1 file) — scripts/check_registry_consistency.py accepts WORKFLOW.md entry files and finds the archived manifests. *Why:* the registry lint (R1-R9) discovers skills via SKILL.md and reads .claude-plugin/*.json; in the merged layout those are WORKFLOW.md and upstream/claude-plugin/*.json. Files: `scripts/check_registry_consistency.py`.
- **B1** (1 edit in 1 file) — banner prepended to `README.md`. *Why:* the upstream README describes the upstream plugin repo; the banner tells a reader of the merged skill where the truth about this layout lives.
- **B2** (1 edit in 1 file) — banner prepended to `README.zh-CN.md`. *Why:* same as B1, in Chinese.

### 5.5 Files added

The router `SKILL.md`; `INDEX.md`; `MANIFEST.json`; this file; the wrapper folder `install/claude-code-commands/`
(one file per command plus a README); `tests/test_merge_integrity.py`; and `tools/merge/` (builder, verifier,
ledger runner, edit spec, templates, the ledger `GATES.md`, and its README).

## 6. Observations about upstream (left unchanged)

These are things found while merging that are not this merge's to fix; they are recorded so you can decide.

- **`[NEEDS CONTENT: what]` is not scanned.** `deck-studio` marks missing slide content with
  `[NEEDS CONTENT: what]`, but `scripts/check_content_markers.py` only looks for `[NEEDS PROFESSOR INPUT`,
  `[VERIFY` and `[MATERIAL GAP`; a student-facing deck with that placeholder would pass the finalization check.
- **`[MATERIAL GAP` is undocumented.** The checker scans for it, but no protocol, agent or template defines it.
- **`iteration_history` ownership wording is uneven.** The passport schema and `docs/ARCHITECTURE.md` make
  `iteration_coach_agent` the single writer and say other skills hand it evidence; grade analysis says so
  explicitly. But `assessment-architect/agents/item_analyst_agent.md` (step 6) says to "append a condensed
  evidence entry to passport `iteration_history`" and `teaching-reflector/WORKFLOW.md` (Phase 3) says changes are
  "written to passport iteration_history" — the v1.2.0 single-writer change was not rolled out everywhere. Those
  files are unchanged; the router (§2, Passport discipline) tells Claude to follow the schema.
- **The prose passport schema and the JSON Schema differ in two places.** `shared/course_passport_schema.md`
  says `iteration_history[].changes` entries are objects (`{change, source_skill, evidence_ref}`) and lists eight
  assessment types; `shared/course_passport.schema.json` requires strings for `changes` and also allows the types
  `lab` and `other`. Both golden showcase passports use strings, so a passport written to the prose shape would
  fail validation. Unchanged here; the router (§6) tells Claude to write what the JSON Schema accepts.
- **`python3` on Windows.** Upstream commands say `python3`; on Windows use `python` or `py -3`
  (the router says so).
- **Repo-root-relative script paths.** Workflows say `python3 scripts/check_passport.py <passport>` as if run
  from the repository root; installed as a skill, the working directory is the professor's course folder, so
  the router instructs to run them by absolute path from this skill's base directory.
- **Intake question counts differ.** `student-mentor/agents/recommendation_writer_agent.md` lists five core intake
  questions; `student-mentor/references/recommendation_letter_guide.md`, which it points to, lists six (it adds
  logistics). No behavior depends on the difference.
- **No helper for "what week is it?"** `teaching-pipeline/references/pipeline_state_machine.md` defines the current
  week from today's date and the stored calendar, but no script computes it; the agent has to do it by hand.
- **A UTF-8 BOM breaks `export_lms.py`.** Windows PowerShell 5.1's `Set-Content -Encoding UTF8` writes a BOM,
  and `scripts/export_lms.py` then stops with `JSONDecodeError: Unexpected UTF-8 BOM`. Save the question-set
  JSON as UTF-8 without a BOM; with that, GIFT, QTI and Common Cartridge export all worked in the smoke test.
- **`test_build_codex.py` needs `git`.** It shells out to `git rev-parse`; on a machine without git all 12
  of its tests error (this machine: 51 passed, 12 errors on the untouched upstream suite = the changelog's 63).
  It is archived under `upstream/dev/` because it also needs the upstream layout.
- **`CLAUDE.md` loads by itself in Claude Code.** Claude Code adds a `CLAUDE.md` to the context when files in its
  folder are read, so upstream's `CLAUDE.md` (routing discipline and the five non-negotiables) rides along
  whenever this skill's files are read. It agrees with the router (§2 and §3) and adds nothing conflicting.
- **The suite's pedagogy citations are the upstream author's.** They were not re-verified here.

## 7. Verification record

Every claim above is checked by an independent verifier (`tools/merge/verify_merge.py`, which never imports the
builder and recomputes expected bytes from the untouched upstream files). The ledger `tools/merge/GATES.md`
has 28 automated gates and 2 manual gates. At release, all 28 automated gates and both
manual gates were met (the counting rule: exit code 0 **and** the expected success line matched):

- **G01** — The source inventory is complete: every file is enumerated with sha256, and the only exclusions are `__pycache__`/`*.pyc` and the 15 `skills/*` stubs (each stub verified to be just a `../<skill>` pointer).
- **G02** — Every carried source file has a merged counterpart at its mapped path, mappings are collision-free, and the merged tree holds nothing but mapped files plus the declared new files.
- **G03** — Fidelity: each merged file equals its source byte-for-byte, or equals the source with exactly the registered edits applied (each edit applied its registered number of times; no other change anywhere).
- **G04** — All 15 modules are complete: WORKFLOW.md present, frontmatter name equals folder name, and the agents/references/templates file sets equal the source's (76 agents in total).
- **G05** — The package contains exactly one SKILL.md (the router) and Anthropic's own quick_validate accepts it (allowed keys only, name/description limits, no angle brackets).
- **G06** — The router is at most 500 lines and links every one of the 15 modules' WORKFLOW.md, each of which exists.
- **G07** — The router's mode index equals MODE_REGISTRY.md and each module's own Modes table, module by module (89 modes).
- **G08** — The router's alias table equals the 30 command files (alias, module, mode) and the registry's Command column.
- **G09** — Every stated count (skills, modes, agents, aliases, extension skills, per-module agent counts) in the router, READMEs, ARCHITECTURE, manifests and module descriptions equals the count computed from the files, and no known-stale count string survives.
- **G10** — The router carries the standing rules verbatim in substance: the five non-negotiables, the four checkpoint block labels, the two person-affecting constraints, the WORKFLOW.md naming note, and the base-directory rule for running scripts.
- **G11** — Every trigger keyword (English and Chinese) declared in the 15 modules' descriptions appears in the router's keyword index, and the router description names the core domains.
- **G12** — Every backtick file reference in every markdown file resolves under the documented rule (the skill root, then each ancestor folder of the referencing file, which includes its module folder) with zero broken and zero ambiguous.
- **G13** — Every relative markdown link target in every markdown file exists.
- **G14** — Each module's Agent Team table names exactly the agent files present in its agents/ folder (76 agents, both directions).
- **G15** — No orphans: every agent, reference, template, shared, command and script file is referenced from at least one other file besides the generated INDEX/MANIFEST/MERGE_NOTES.
- **G16** — INDEX.md lists every file in the package exactly once, and MANIFEST.json agrees with the disk (paths, byte sizes, sha256, source sha256).
- **G17** — Upstream's registry lint (R1-R9) passes in the merged layout and reports 15 skills, 89 modes, 76 agents.
- **G18** — Upstream's link checker passes in the merged layout with zero broken references and at least as many references checked as the untouched source (395).
- **G19** — The validators run clean on both showcase passports (passport valid, alignment gate not FAIL, quality gate not FAIL on the STEM showcase) and the dashboard builds from the merged layout.
- **G20** — The merged skill's test suite passes with zero failures and zero errors (upstream tests that apply to this layout plus the new merge-integrity tests).
- **G21** — Baseline honesty: on the untouched source, the upstream suite gives 51 passed and 12 errors, all 12 in test_build_codex.py because git is not installed (63 total = the changelog's claim).
- **G22** — Security scan finds no network, credential, persistence, obfuscation or dynamic-execution constructs beyond the documented subprocess calls (pandoc, git), no bidirectional or zero-width control characters, no prompt-injection phrasing, and no absolute local user paths (which would leak a username) in any text file.
- **G23** — Encoding fidelity: every text file decodes as UTF-8, and no file has mixed line endings that its source did not have.
- **G24** — The merged folder contains no build debris (`__pycache__`, `*.pyc`, `.pytest_cache`, `.DS_Store`).
- **G25** — The upload package `teaching-skill.skill` (and its byte-identical `teaching-skill.zip` copy) equals what Anthropic's packager produces for the folder, contains exactly one SKILL.md, and its contents are hash-identical to the folder.
- **G26** — MERGE_NOTES.md exists with its required sections, its edit table matches the registered edits one-for-one, and its stated file counts equal the measured ones.
- **G27** — Negative controls: each deliberate corruption of a scratch copy (drop an agent, flip a byte, break a link, add a nested SKILL.md, corrupt the router mode list, reintroduce a stale count, remove an alias row, embed a local user path) is caught by the gate meant to catch it.
- **G28** — The ledger itself is sound: every runnable gate has a CHECK and a non-trivial EXPECT that names its own gate id, and no gate was silently dropped.
- **M1** — Router prose was re-read against the 15 workflows and the shared protocols; every non-generated statement was traced to a source and each misstatement found was fixed (the trace is recorded in MERGE_NOTES.md section 7).
- **M2** — Final claim audit: the request was re-read; every clause maps to a met gate; counts in the final report were re-measured immediately before reporting.

### Manual review of the router (M1)

Every statement in `SKILL.md` that is not generated from the files was traced to a source. The review found
**one misstatement, since fixed**: the router first listed the executable core of Gate 3.5 as
"Q1, Q2, T1, T2, T4, W1", copied from upstream's docs; `scripts/check_quality_gate.py` also executes Q4, so the
router now says so and the upstream docs are corrected (edit C8). Trace:

| Router statement | Traced to |
|---|---|
| Four checkpoint blocks, "none" instead of omitting, closing question; when a checkpoint fires | `shared/checkpoint_protocol.md` (Checkpoint shape; When a checkpoint fires) |
| "Just proceed" never skips the confirmation and never applies to gates or person-affecting outputs | `teaching-pipeline/WORKFLOW.md` (Iron rule 4), `teaching-pipeline/agents/gate_runner_agent.md`, `teaching-pipeline/agents/pipeline_orchestrator_agent.md` |
| `[NEEDS PROFESSOR INPUT: …]` and `[VERIFY: …]` formats | `course-designer/WORKFLOW.md` (Iron rule 3), `lesson-builder/WORKFLOW.md` (Iron rule 2) |
| Person-affecting scope, evidence-bound, draft-only, non-removable reminder | `shared/checkpoint_protocol.md`, `student-mentor/WORKFLOW.md` (hard rule, Iron rules 1–3), `ta-coordinator/WORKFLOW.md` (Prime rule) |
| Student data never enters the passport; load the passport first; no AI-detection tools; prefer guided mode | `CLAUDE.md` (Routing; Non-negotiables 4–5) |
| Passport discipline (append, provenance, "unknown" is legitimate) | `shared/course_passport_schema.md` (Iron rules 1, 2, 4) |
| Seven-line output self-check | `shared/output_self_check.md` |
| Pedagogy defaults, cite by §, do not re-argue | `shared/pedagogy_foundations.md` (How agents use this file) |
| Gate mechanics: 3 rounds, WARN dismissal, acknowledgment, thresholds in one file | `shared/alignment_gate_protocol.md`, `shared/quality_gate_protocol.md`, `shared/workload_constants.md` |
| Routing-table rows and boundary rules | each module's "Does NOT trigger" table in its `WORKFLOW.md`; `CLAUDE.md` (Routing) |
| Lifecycle diagram, stage and gate names, attach points | `docs/ARCHITECTURE.md` (sections 2, 3, 5b), `teaching-pipeline/WORKFLOW.md` |
| Script table: arguments and which checks each script executes | the scripts' own docstrings and code (`scripts/check_quality_gate.py`: Q1, Q2, Q4, T1, T2, T4, W1) |
| Hand-offs between modules | `docs/ARCHITECTURE.md` (sections 5, 5b) |
| Counts, mode index, alias table, keyword index | generated from the files and verified by G07–G09 and G11 |

### Smoke test with skill-creator's method

On 2026-09-26 three realistic prompts were run inline against this folder: a Chinese request for a midterm exam
under deadline pressure, a "just write my recommendation letter" request, and "is my passport OK?" from a working
folder that is not the skill folder (a showcase passport with two planted defects). 28 expectations were graded
(10, 10 and 8), mostly by script — regexes, re-computed arithmetic, a checksum proving the passport was not edited,
and a check that every quote in the intake ledger is literally in the prompt — and all 28 passed once a bug in the
grader itself (a table regex that skipped two rows) was fixed. The runs were done by the same session that built
the skill, self-graded, and had no no-skill baselines, so they show that the skill can be followed as written, not
that it beats not having it. They exposed three things, all fixed in version 1.0.1: the inaccurate
`workload_constants.md` claim (edit C9), no rule for the checkpoint labels when the professor writes another
language, and no note that the gate script assumes the passport validator ran first. The results are in the folder
teaching-skill-workspace next to this skill; it is not part of the package.

### Security review (skill-inspector method, manual fallback)

On 2026-09-26 the built package was reviewed for safety the way Anthropic's skill-inspector prescribes, with one
difference: its static scanner (SkillSpector) is not installed on the build machine and nothing was installed for
the purpose, so **there is no SkillSpector score and the verdict is a semantic-only review, made with lower
confidence.** Nothing from the package was executed. A separate throw-away scanner searched every file for
network, process-execution, destructive-file, credential/environment, persistence, obfuscation, prompt-steering
and personal-path patterns, and the code around each hit was read. Verdict: **CAUTION (low)**. Nothing malicious
or hidden was found, and the sensitive surface below is documented, needed for the skill's purpose, and under the
user's control.

- **The instructions and the scripts they call** (`SKILL.md`, the 15 modules, `scripts/`): no network calls, no
  credential or home-directory reads, no persistence hooks, no encoded payloads, no wording that hides actions
  or steers later conversations. The only `http(s)` strings are XML and JSON-Schema namespace identifiers and
  links to the upstream project. The few pattern hits that remain are ordinary prose, such as "secretly graded"
  in a diagnostic-design guide.
- **Deliberate command execution:** `scripts/render_document.py` runs Pandoc on a file you name (an argument
  list, no shell, and without Pandoc's `--sandbox`, so render only documents you trust); the `lab-forge`
  module builds and *executes* scaffolds, datasets and autograders in the session and pins their dependencies,
  which is its stated "executed, not assumed" rule, so read what it installs before letting it; the archived
  `upstream/dev/build_codex.py`, which the skill never uses, empties the `-o` folder it is given.
- **Merge tooling** (`tools/merge/`, used by no workflow): `gate_run.py` runs every ledger `CHECK:` line through
  the shell, so never run a ledger you have not read (its docstring says so, and the shipped `GATES.md` carries
  placeholder paths and is not runnable as it is); `build_merge.py` refuses to delete an output folder unless it
  holds the `MANIFEST.json` of an earlier build of this skill; the verifier deletes only temporary folders it
  created itself.
- **The package:** the `.skill` file has a single top-level folder, no absolute, `..` or symlink entries, and its
  contents are identical to the folder; each of the two HTML dashboards has one inline script and no external
  resources.
- **Student data:** the rules keep student data out of the passport and make every student-affecting output a
  draft for the professor (router §2), but a drafted email, letter or feedback still contains whatever the
  professor pasted in, so treat those files as the sensitive records they are.

One finding was fixed in version 1.0.2: three files in `tools/merge/` held the builder's own absolute Windows
paths (the user name and the location of the skill-creator bundle), and the verifier could only find
skill-creator at that hard-coded path. The path is now an argument (`--skill-creator` or `SKILL_CREATOR_DIR`;
`make_edits.py` takes the upstream folder as a required argument), the shipped ledger is redacted, and gate G22
now fails the build if any text file contains an absolute local user path.

Beyond the gates: Anthropic's own `quick_validate.py` accepts the skill, and the `.skill` file is identical to
what Anthropic's `package_skill.py` produces for this folder (gates G05 and G25 make those two comparisons only
when the skill-creator folder is given with `--skill-creator <path>`; without it they check the same rules
themselves). To re-run the checks that need no upstream copy:
`python tools/merge/verify_merge.py --out . --package` and `python -m pytest tests -q`. The provenance gates
need the untouched upstream folder: `python tools/merge/verify_merge.py --src <upstream> --out . --all`.

## 8. Limits of this verification

- "Accurate" here means **lossless, internally consistent and working** — not that the pedagogy literature the
  suite cites was fact-checked.
- The skill was verified structurally and by running its scripts and tests; it has **not** been exercised in a
  live Claude session, and the trigger description was **not** empirically tuned (Anthropic's description
  optimizer was not run). If it under- or over-triggers, adjust the description in `SKILL.md`.
- The slash-command wrappers were checked for structure and routing consistency, not run in Claude Code.
- Verification ran on Windows with Python 3.14 (upstream CI targets Python 3.12). `git`, Node and PowerShell 7
  were not available; Node's absence is why `tools/merge/gate_run.py` (Python) stands in for the unlazy
  skill's missing `gate-check.mjs`.
- If you re-validate or re-package this skill on Windows with Anthropic's skill-creator scripts, run them in
  Python's UTF-8 mode (`$env:PYTHONUTF8 = "1"` in PowerShell): they read `SKILL.md` with the platform default
  encoding (cp1252 on Windows), which cannot decode this skill's Chinese text and arrows. This is how the
  skill was validated and packaged.
