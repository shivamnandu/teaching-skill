<!-- Shipped copy of the verification ledger used for this merge. Paths are placeholders and tick boxes are reset; results are summarized in MERGE_NOTES.md. -->
# GATES — teaching-skill (merge of teaching-skills v1.2.0)

Request (verbatim): "Go the the following path in downloads folder
"<home>\Downloads\teaching-skills-main\teaching-skills-main" and Merge all the
teaching skills to create a ultimate teaching skill which is 100% accurate and doesn't miss
out on anything"

## Interpretation (recorded so the gates below can be audited against it)

- ONE installable skill named `teaching-skill` (the user asked for the final skill to be named
  "teaching skill" and be upload-ready; Skills names are kebab-case), containing all 15 teaching
  skills as modules, routed by a single `SKILL.md`, delivered as a folder plus one upload file
  `teaching-skill.skill`. Output goes to a NEW folder; the source is read-only.
- "doesn't miss out on anything" = every file in the source folder is carried into the
  merged skill. The only declared exclusions are build debris (`__pycache__`, `*.pyc`) and
  the 15 `skills/*` git-symlink stub files (one-line pointers, redundant in one skill).
- "100% accurate" = (a) lossless: unedited files byte-identical, every edit registered and
  explained; (b) internally consistent: counts true, references resolve, router agrees with
  MODE_REGISTRY and the command files; (c) functional: upstream validators and tests pass in
  the merged layout. It does NOT mean I fact-checked the pedagogy literature cited upstream.
- `/loop` in the invocation args is read as "keep iterating until done", not as a request
  to schedule recurring runs (this is a one-off build).

## Tooling limits (stated, not hidden)

- unlazy's helper scripts (`gate-check.mjs`, `gate-lint.mjs`, `install-hooks.mjs`) and its
  `templates/`, `references/` are NOT installed (the skill folder holds only SKILL.md) and
  Node is not installed. So `gate_run.py` (Python, written for this job) applies unlazy's
  counting rule: a runnable gate is met only if the process exits 0 AND EXPECT matches the
  combined output. No Stop hook is installed.
- Python 3.14 + a scratch venv (pyyaml, jsonschema, pytest) is the verification runtime.
  git, pytest, Node, pwsh are absent from the machine's PATH.

## Variables

VAR PY   = python
VAR TOOL = tools/merge
VAR SRC  = <path to the untouched upstream teaching-skills folder>
VAR OUT  = <path to this skill folder>
VAR SC   = <optional: path to Anthropic's skill-creator folder>

## Part A — nothing is missed, nothing is silently changed

- [ ] G01: The source inventory is complete: every file is enumerated with sha256, and the only exclusions are `__pycache__`/`*.pyc` and the 15 `skills/*` stubs (each stub verified to be just a `../<skill>` pointer).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G01
  EXPECT: ^G01 PASS

- [ ] G02: Every carried source file has a merged counterpart at its mapped path, mappings are collision-free, and the merged tree holds nothing but mapped files plus the declared new files.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G02
  EXPECT: ^G02 PASS

- [ ] G03: Fidelity: each merged file equals its source byte-for-byte, or equals the source with exactly the registered edits applied (each edit applied its registered number of times; no other change anywhere).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G03
  EXPECT: ^G03 PASS

- [ ] G04: All 15 modules are complete: WORKFLOW.md present, frontmatter name equals folder name, and the agents/references/templates file sets equal the source's (76 agents in total).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G04
  EXPECT: ^G04 PASS

## Part B — the router and the numbers are true

- [ ] G05: The package contains exactly one SKILL.md (the router) and Anthropic's own quick_validate accepts it (allowed keys only, name/description limits, no angle brackets).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G05 --skill-creator ${SC}
  EXPECT: ^G05 PASS

- [ ] G06: The router is at most 500 lines and links every one of the 15 modules' WORKFLOW.md, each of which exists.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G06
  EXPECT: ^G06 PASS

- [ ] G07: The router's mode index equals MODE_REGISTRY.md and each module's own Modes table, module by module (89 modes).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G07
  EXPECT: ^G07 PASS

- [ ] G08: The router's alias table equals the 30 command files (alias, module, mode) and the registry's Command column.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G08
  EXPECT: ^G08 PASS

- [ ] G09: Every stated count (skills, modes, agents, aliases, extension skills, per-module agent counts) in the router, READMEs, ARCHITECTURE, manifests and module descriptions equals the count computed from the files, and no known-stale count string survives.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G09
  EXPECT: ^G09 PASS

- [ ] G10: The router carries the standing rules verbatim in substance: the five non-negotiables, the four checkpoint block labels, the two person-affecting constraints, the WORKFLOW.md naming note, and the base-directory rule for running scripts.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G10
  EXPECT: ^G10 PASS

- [ ] G11: Every trigger keyword (English and Chinese) declared in the 15 modules' descriptions appears in the router's keyword index, and the router description names the core domains.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G11
  EXPECT: ^G11 PASS

## Part C — references, agents, index

- [ ] G12: Every backtick file reference in every markdown file resolves under the documented rule (the skill root, then each ancestor folder of the referencing file, which includes its module folder) with zero broken and zero ambiguous.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G12
  EXPECT: ^G12 PASS

- [ ] G13: Every relative markdown link target in every markdown file exists.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G13
  EXPECT: ^G13 PASS

- [ ] G14: Each module's Agent Team table names exactly the agent files present in its agents/ folder (76 agents, both directions).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G14
  EXPECT: ^G14 PASS

- [ ] G15: No orphans: every agent, reference, template, shared, command and script file is referenced from at least one other file besides the generated INDEX/MANIFEST/MERGE_NOTES.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G15
  EXPECT: ^G15 PASS

- [ ] G16: INDEX.md lists every file in the package exactly once, and MANIFEST.json agrees with the disk (paths, byte sizes, sha256, source sha256).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G16
  EXPECT: ^G16 PASS

## Part D — it works

- [ ] G17: Upstream's registry lint (R1-R9) passes in the merged layout and reports 15 skills, 89 modes, 76 agents.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G17
  EXPECT: ^G17 PASS

- [ ] G18: Upstream's link checker passes in the merged layout with zero broken references and at least as many references checked as the untouched source (395).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G18
  EXPECT: ^G18 PASS

- [ ] G19: The validators run clean on both showcase passports (passport valid, alignment gate not FAIL, quality gate not FAIL on the STEM showcase) and the dashboard builds from the merged layout.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G19
  EXPECT: ^G19 PASS

- [ ] G20: The merged skill's test suite passes with zero failures and zero errors (upstream tests that apply to this layout plus the new merge-integrity tests).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G20
  EXPECT: ^G20 PASS

- [ ] G21: Baseline honesty: on the untouched source, the upstream suite gives 51 passed and 12 errors, all 12 in test_build_codex.py because git is not installed (63 total = the changelog's claim).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G21
  EXPECT: ^G21 PASS

## Part E — hygiene and safety

- [ ] G22: Security scan finds no network, credential, persistence, obfuscation or dynamic-execution constructs beyond the documented subprocess calls (pandoc, git), no bidirectional or zero-width control characters, no prompt-injection phrasing, and no absolute local user paths (which would leak a username) in any text file.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G22
  EXPECT: ^G22 PASS

- [ ] G23: Encoding fidelity: every text file decodes as UTF-8, and no file has mixed line endings that its source did not have.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G23
  EXPECT: ^G23 PASS

- [ ] G24: The merged folder contains no build debris (`__pycache__`, `*.pyc`, `.pytest_cache`, `.DS_Store`).
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G24
  EXPECT: ^G24 PASS

## Part F — packaging, notes, and the verifier's own honesty

- [ ] G25: The upload package `teaching-skill.skill` (and its byte-identical `teaching-skill.zip` copy) equals what Anthropic's packager produces for the folder, contains exactly one SKILL.md, and its contents are hash-identical to the folder.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G25 --skill-creator ${SC}
  EXPECT: ^G25 PASS

- [ ] G26: MERGE_NOTES.md exists with its required sections, its edit table matches the registered edits one-for-one, and its stated file counts equal the measured ones.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G26
  EXPECT: ^G26 PASS

- [ ] G27: Negative controls: each deliberate corruption of a scratch copy (drop an agent, flip a byte, break a link, add a nested SKILL.md, corrupt the router mode list, reintroduce a stale count, remove an alias row, embed a local user path) is caught by the gate meant to catch it.
  CHECK: ${PY} ${TOOL}\verify_merge.py --src ${SRC} --out ${OUT} --gate G27
  EXPECT: ^G27 PASS

- [ ] G28: The ledger itself is sound: every runnable gate has a CHECK and a non-trivial EXPECT that names its own gate id, and no gate was silently dropped.
  CHECK: ${PY} ${TOOL}\gate_run.py --lint
  EXPECT: ^LEDGER LINT PASS

## Part G — manual (no command can decide these)

- [ ] M1: Router prose was re-read against the 15 workflows and the shared protocols; every non-generated statement was traced to a source and each misstatement found was fixed (the trace is recorded in MERGE_NOTES.md section 7).
  MANUAL: yes
  EVIDENCE: see MERGE_NOTES.md (Verification record)

- [ ] M2: Final claim audit: the request was re-read; every clause maps to a met gate; counts in the final report were re-measured immediately before reporting.
  MANUAL: yes
  EVIDENCE: see MERGE_NOTES.md (Verification record)
