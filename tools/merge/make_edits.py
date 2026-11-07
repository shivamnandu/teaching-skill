#!/usr/bin/env python3
"""Generate edits.json — the single declarative spec of every difference between the
upstream tree and the merged skill (besides brand-new generated files).

Every text item is validated against the SOURCE right here: `old` must occur exactly
`count` times in that file, otherwise generation fails. The builder applies this spec;
the independent verifier recomputes expected bytes from source + this spec and compares
with the merged tree. Nothing else may differ.
"""
import json
import re
import sys
from pathlib import Path

if len(sys.argv) < 2:
    raise SystemExit("usage: make_edits.py <path to the untouched upstream teaching-skills folder>")
SRC = Path(sys.argv[1])
OUT = Path(__file__).resolve().parent / "edits.json"

MODULES = ["accreditation-mapper", "assessment-architect", "bilingual-courseware", "cohort-analyst",
           "course-designer", "course-publisher", "deck-studio", "lab-forge", "lesson-builder",
           "media-scripter", "student-mentor", "submission-auditor", "ta-coordinator",
           "teaching-pipeline", "teaching-reflector"]

moves = []
for i, m in enumerate(MODULES, 1):
    moves.append({"id": f"R{i:02d}", "kind": "rename", "from": f"{m}/SKILL.md", "to": f"{m}/WORKFLOW.md",
                  "why": "exactly one SKILL.md may exist in a skill (Skills API / claude.ai reject nested "
                         "ones); the module entry file keeps its content under the name WORKFLOW.md"})
RELOC = [
    (".claude-plugin/plugin.json", "upstream/claude-plugin/plugin.json"),
    (".claude-plugin/marketplace.json", "upstream/claude-plugin/marketplace.json"),
    (".github/ISSUE_TEMPLATE/config.yml", "upstream/github/ISSUE_TEMPLATE/config.yml"),
    (".github/ISSUE_TEMPLATE/skill-misbehavior.md", "upstream/github/ISSUE_TEMPLATE/skill-misbehavior.md"),
    (".github/ISSUE_TEMPLATE/skill-request.md", "upstream/github/ISSUE_TEMPLATE/skill-request.md"),
    (".github/workflows/ci.yml", "upstream/github/workflows/ci.yml"),
    ("scripts/build_codex.py", "upstream/dev/build_codex.py"),
    ("tests/test_build_codex.py", "upstream/dev/test_build_codex.py"),
]
WHY_RELOC = {
    ".claude-plugin/plugin.json": "plugin manifest describes the upstream plugin; a live .claude-plugin/ at the "
                                  "skill root would look like a (broken) plugin, so it is archived",
    ".claude-plugin/marketplace.json": "same as plugin.json",
    "scripts/build_codex.py": "upstream release tool: needs git and the upstream SKILL.md layout, so it cannot "
                              "run inside the merged skill; archived unmodified",
    "tests/test_build_codex.py": "tests the Codex generator; needs git + upstream layout; archived unmodified",
}
for i, (a, b) in enumerate(RELOC, 1):
    moves.append({"id": f"L{i:02d}", "kind": "relocate", "from": a, "to": b,
                  "why": WHY_RELOC.get(a, "upstream repository/CI file, not skill runtime; archived unmodified")})


def read(rel):
    return (SRC / rel).read_text(encoding="utf-8")


groups = []


def group(gid, kind, summary, why, items):
    for it in items:
        text = read(it["file"])
        n = text.count(it["old"])
        if n != it["count"]:
            raise SystemExit(f"[{gid}] {it['file']}: expected {it['count']}x of {it['old']!r}, found {n}")
        if it["old"] == it["new"]:
            raise SystemExit(f"[{gid}] no-op edit in {it['file']}")
    groups.append({"id": gid, "kind": kind, "summary": summary, "why": why, "items": items})


def it(file, old, new, count=1):
    return {"file": file, "old": old, "new": new, "count": count}


# ---- C: factual drift corrections (verified against the files) ----------------------------------
group("C1", "correction", "course-designer description says a 6-agent team; the team is 7",
      "course-designer/agents/ has 7 files and its own 'Agent Team (7)' heading (async_designer_agent was "
      "added in upstream v1.2.0 and the description was not updated)",
      [it("course-designer/SKILL.md", "6-agent team covering", "7-agent team covering")])
group("C2", "correction", "assessment-architect description says a 7-agent team; the team is 10",
      "assessment-architect/agents/ has 10 files and 'Agent Team (10)' (grade_analyst, group_designer and "
      "accommodation_designer were added in v1.2.0)",
      [it("assessment-architect/SKILL.md", "7-agent team covering", "10-agent team covering")])
group("C3", "correction", "student-mentor description says a 5-agent team; the team is 6",
      "student-mentor/agents/ has 6 files and 'Agent Team (6)' (integrity_case_agent added in v1.2.0)",
      [it("student-mentor/SKILL.md", "5-agent team covering", "6-agent team covering")])
group("C4", "correction", "teaching-pipeline says 'Seven extension skills'; its own table lists eight",
      "the table directly below the sentence has 8 rows (accreditation-mapper, deck-studio, media-scripter, "
      "lab-forge, course-publisher, ta-coordinator, bilingual-courseware, cohort-analyst) and MODE_REGISTRY "
      "says '8 extensions'",
      [it("teaching-pipeline/SKILL.md", "Seven extension skills attach", "Eight extension skills attach")])
group("C5", "correction", "ARCHITECTURE section 5b says 'Seven extension skills'; its table lists eight",
      "same evidence as C4 (the §5b table has 8 rows)",
      [it("docs/ARCHITECTURE.md", "Seven extension skills layer", "Eight extension skills layer")])
group("C6", "correction", "README.md says 84 modes / 71 agents; the registry, manifests and files say 89 / 76",
      "MODE_REGISTRY totals line, plugin.json, marketplace.json, CHANGELOG v1.2.0 and the filesystem all agree "
      "on 89 modes and 76 agents; the README counts are left over from v1.1.x",
      [it("README.md", "15 skills · 84 modes · 71-agent ensemble", "15 skills · 89 modes · 76-agent ensemble"),
       it("README.md", "for all 84 modes", "for all 89 modes")])
group("C7", "correction", "README.zh-CN.md says 84 modes / 71 agents; the truth is 89 / 76",
      "same evidence as C6 (the Chinese README mirrors the English one)",
      [it("README.zh-CN.md", "15 个技能 · 84 种模式 · 71 个智能体协同", "15 个技能 · 89 种模式 · 76 个智能体协同"),
       it("README.zh-CN.md", "全部 84 种模式见", "全部 89 种模式见")])

group("C8", "correction",
      "Gate 3.5 documentation omits check Q4 from the executable core and check T4 from two check lists",
      "scripts/check_quality_gate.py lists Q4 under 'Executable here' and implements it (keyword scan for AI-detection "
      "tools in artifacts), and shared/quality_gate_protocol.md defines T4 (unresolved-marker scan, added in v1.2.0); "
      "ARCHITECTURE and gate_runner_agent still listed 'Q1/Q2/T1/T2/T4/W1' as the executable core and 'T1-T3'/'T2-T3' "
      "as the transparency checks",
      [it("docs/ARCHITECTURE.md", "(Q1/Q2/T1/T2/T4/W1)", "(Q1/Q2/Q4/T1/T2/T4/W1)"),
       it("docs/ARCHITECTURE.md", "T2–T3 transparency", "T2–T4 transparency"),
       it("teaching-pipeline/agents/gate_runner_agent.md", "# Q1/Q2/T1/T2/T4/W1 executable", "# Q1/Q2/Q4/T1/T2/T4/W1 executable"),
       it("teaching-pipeline/agents/gate_runner_agent.md", "decides Q1/Q2/T1/T2/T4/W1 and marks", "decides Q1/Q2/Q4/T1/T2/T4/W1 and marks"),
       it("teaching-pipeline/agents/gate_runner_agent.md", "3.5: Q1–Q4, T1–T3, U1–U3", "3.5: Q1–Q4, T1–T4, U1–U3")])

group("C9", "correction",
      "workload_constants.md says the test-blueprint template cites it and that the gate script imports it; neither is true",
      "only shared/alignment_gate_protocol.md references workload_constants.md (a search of the whole upstream tree finds "
      "no other reference), the blueprint template carries its own exam-item time heuristics and cites nothing, and "
      "scripts/check_alignment_gate.py hard-codes the same values (10, 20, 15, 40, 0.25) rather than importing a Markdown "
      "file. Found while following the exam workflow in the skill-creator smoke test",
      [it("shared/workload_constants.md",
          "`scripts/check_alignment_gate.py` imports these via its\n"
          "module constants; `shared/alignment_gate_protocol.md` and\n"
          "`assessment-architect/templates/test_blueprint_template.md` cite this file rather than\n"
          "restating the numbers, so there is one place to adjust them.",
          "`scripts/check_alignment_gate.py` mirrors these values in its\n"
          "module constants; `shared/alignment_gate_protocol.md` cites this file rather than\n"
          "restating the numbers, so there is one place to adjust them.")])

# ---- N: entry-file naming (SKILL.md -> WORKFLOW.md) where the text points at a module's entry ------
cmd_items = []
for f in sorted((SRC / "commands").glob("*.md")):
    text = f.read_text(encoding="utf-8")
    hits = re.findall(r"`([a-z-]+)/SKILL\.md`", text)
    if len(hits) != 1:
        raise SystemExit(f"{f.name}: expected exactly one `<skill>/SKILL.md` reference, found {hits}")
    cmd_items.append(it(f"commands/{f.name}", f"`{hits[0]}/SKILL.md`", f"`{hits[0]}/WORKFLOW.md`"))
group("N1", "naming", f"{len(cmd_items)} command recipes: 'Skill entry' path points at WORKFLOW.md",
      "the module entry file is WORKFLOW.md in the merged skill; SKILL.md there would now be the router",
      cmd_items)
group("N2", "naming", "teaching-pipeline agents/references: 'SKILL.md' means the module's entry file",
      "inside the merged skill a bare SKILL.md is the router, which has different rules; these four mentions "
      "cite the pipeline module's own Iron Rules / routing table",
      [it("teaching-pipeline/agents/passport_keeper_agent.md", "(SKILL.md Iron Rule 6)", "(WORKFLOW.md Iron Rule 6)"),
       it("teaching-pipeline/agents/passport_keeper_agent.md", "(SKILL.md Iron Rule 5)", "(WORKFLOW.md Iron Rule 5)"),
       it("teaching-pipeline/agents/pipeline_orchestrator_agent.md", "Apply the SKILL.md routing table",
          "Apply the WORKFLOW.md routing table"),
       it("teaching-pipeline/references/pipeline_state_machine.md", "see SKILL.md routing table",
          "see WORKFLOW.md routing table")])
group("N3", "naming", "docs: statements about a skill's SKILL.md now name WORKFLOW.md",
      "keeps MODE_REGISTRY, ARCHITECTURE, CLAUDE, CONTRIBUTING and both READMEs true for the merged layout "
      "(ARCHITECTURE's build_codex row keeps 'SKILL.md→WORKFLOW.md' on purpose: it describes that rename)",
      [it("MODE_REGISTRY.md", "update the skill's SKILL.md, this registry", "update the skill's WORKFLOW.md, this registry"),
       it("docs/ARCHITECTURE.md", "each skill's\n`SKILL.md`.", "each skill's\n`WORKFLOW.md`."),
       it("docs/ARCHITECTURE.md", "three-places rule (SKILL.md ↔ MODE_REGISTRY", "three-places rule (WORKFLOW.md ↔ MODE_REGISTRY"),
       it("CLAUDE.md", "the skill's `SKILL.md`,", "the skill's `WORKFLOW.md`,"),
       it("CONTRIBUTING.md", "Every skill's `SKILL.md` states", "Every skill's `WORKFLOW.md` states"),
       it("CONTRIBUTING.md", "the skill's `SKILL.md`,", "the skill's `WORKFLOW.md`,"),
       it("CONTRIBUTING.md", "(`SKILL.md` + `agents/`", "(`WORKFLOW.md` + `agents/`"),
       it("README.md", "course-designer/        SKILL.md +", "course-designer/        WORKFLOW.md +"),
       it("README.md", "teaching-pipeline/      SKILL.md +", "teaching-pipeline/      WORKFLOW.md +"),
       it("README.md", "(the `SKILL.md` content)", "(the `WORKFLOW.md` content)"),
       it("README.zh-CN.md", "course-designer/        SKILL.md +", "course-designer/        WORKFLOW.md +"),
       it("README.zh-CN.md", "teaching-pipeline/      SKILL.md +", "teaching-pipeline/      WORKFLOW.md +"),
       it("README.zh-CN.md", "（`SKILL.md` 内容）", "（`WORKFLOW.md` 内容）")])

# ---- P: path references to files that moved -----------------------------------------------------
group("P1", "path", "references to relocated upstream files now point at their new home",
      "build_codex.py and ci.yml moved under upstream/ (see L-moves); without this the docs would name "
      "files that no longer exist at those paths",
      [it("README.md", "`scripts/build_codex.py`", "`upstream/dev/build_codex.py`"),
       it("README.zh-CN.md", "`scripts/build_codex.py`", "`upstream/dev/build_codex.py`"),
       it("docs/ARCHITECTURE.md", "`scripts/build_codex.py`", "`upstream/dev/build_codex.py`"),
       it("docs/ARCHITECTURE.md", "`.github/workflows/ci.yml`", "`upstream/github/workflows/ci.yml`")])

# ---- S: script patches (make upstream's own lint work when the entry file is WORKFLOW.md) ------------
group("S1", "script-patch", "scripts/check_links.py accepts WORKFLOW.md skill folders and checks tools/ + upstream/ refs",
      "the link checker discovers skill folders by looking for SKILL.md; in the merged layout that file is "
      "WORKFLOW.md, so without this patch every skill-relative reference would be skipped as 'external'",
      [it("scripts/check_links.py", 'SKIP_DIRS = {".git", "dist", "node_modules"}\n',
          'SKIP_DIRS = {".git", "dist", "node_modules"}\n'
          "# A skill's entry file: SKILL.md (upstream layout) or WORKFLOW.md (merged single-skill layout).\n"
          'ENTRY_NAMES = ("WORKFLOW.md", "SKILL.md")\n'),
       it("scripts/check_links.py", '"references", "templates", "agents"}', '"references", "templates", "agents", "tools", "upstream"}'),
       it("scripts/check_links.py", 'if d.is_dir() and (d / "SKILL.md").exists()}',
          'if d.is_dir() and any((d / n).exists() for n in ENTRY_NAMES)}')])
group("S2", "script-patch",
      "scripts/check_registry_consistency.py accepts WORKFLOW.md entry files and finds the archived manifests",
      "the registry lint (R1-R9) discovers skills via SKILL.md and reads .claude-plugin/*.json; in the merged "
      "layout those are WORKFLOW.md and upstream/claude-plugin/*.json",
      [it("scripts/check_registry_consistency.py",
          'TABLE_HEADER_CELLS = {"mode", "command", "purpose", "trigger-intent"}\n',
          'TABLE_HEADER_CELLS = {"mode", "command", "purpose", "trigger-intent"}\n\n'
          "# A skill's entry file: SKILL.md (upstream layout) or WORKFLOW.md (merged single-skill layout).\n"
          'ENTRY_NAMES = ("WORKFLOW.md", "SKILL.md")\n\n\n'
          "def entry_file(skill_dir):\n"
          "    for name in ENTRY_NAMES:\n"
          "        if (skill_dir / name).exists():\n"
          "            return skill_dir / name\n"
          "    return None\n"),
       it("scripts/check_registry_consistency.py",
          '                        if d.is_dir() and (d / "SKILL.md").exists())',
          "                        if d.is_dir() and entry_file(d))"),
       it("scripts/check_registry_consistency.py", 'modes = skill_modes(d / "SKILL.md")',
          "modes = skill_modes(entry_file(d))"),
       it("scripts/check_registry_consistency.py", "f\"R2: {name} mode mismatch — only in SKILL.md: {only_skill or '—'}; \"",
          "f\"R2: {name} mode mismatch — only in {entry_file(d).name}: {only_skill or '—'}; \""),
       it("scripts/check_registry_consistency.py", 'declared_agents = skill_agent_count(d / "SKILL.md")',
          "declared_agents = skill_agent_count(entry_file(d))"),
       it("scripts/check_registry_consistency.py", 'f"R4: {name} SKILL.md declares Agent Team ({declared_agents}), "',
          'f"R4: {name} {entry_file(d).name} declares Agent Team ({declared_agents}), "'),
       it("scripts/check_registry_consistency.py",
          '    plugin_p = root / ".claude-plugin" / "plugin.json"\n'
          '    market_p = root / ".claude-plugin" / "marketplace.json"\n',
          "    # upstream keeps the manifests in .claude-plugin/; the merged skill archives them under\n"
          "    # upstream/claude-plugin/ (so nothing mistakes the skill root for a plugin)\n"
          '    manifest_dir = next((c for c in (root / ".claude-plugin", root / "upstream" / "claude-plugin")\n'
          '                         if c.is_dir()), root / ".claude-plugin")\n'
          '    plugin_p = manifest_dir / "plugin.json"\n'
          '    market_p = manifest_dir / "marketplace.json"\n')])

# ---- B: banners (prepended) --------------------------------------------------------------------
prepends = [
    {"id": "B1", "file": "README.md", "why": "the upstream README describes the upstream plugin repo; the banner tells a "
                                             "reader of the merged skill where the truth about this layout lives",
     "text": ("> **Merged-skill note.** This is the upstream *Teaching Skills* README, kept as published apart\n"
              "> from the count and naming corrections logged in [MERGE_NOTES.md](MERGE_NOTES.md). In the merged\n"
              "> `teaching-skill` skill the 15 skills are modules of one skill: start at\n"
              "> [SKILL.md](SKILL.md) (the router). Each module's entry file is `WORKFLOW.md` (not `SKILL.md`) and\n"
              "> the plugin/CI files are archived under `upstream/`. Install steps for the merged skill are in\n"
              "> [MERGE_NOTES.md](MERGE_NOTES.md), not below.\n\n")},
    {"id": "B2", "file": "README.zh-CN.md", "why": "same as B1, in Chinese",
     "text": ("> **合并技能说明。** 本文件是上游 *Teaching Skills* 的中文 README，除 [MERGE_NOTES.md](MERGE_NOTES.md)\n"
              "> 记录的数量与命名更正外保持原样。在合并后的 `teaching-skill` 技能中，15 个技能是同一技能的模块：\n"
              "> 请从 [SKILL.md](SKILL.md)（路由入口）开始。各模块的入口文件为 `WORKFLOW.md`（而非 `SKILL.md`），\n"
              "> 插件/CI 文件归档在 `upstream/` 下。合并技能的安装步骤见 [MERGE_NOTES.md](MERGE_NOTES.md)，而非下文。\n\n")},
]

new_files = [
    "SKILL.md", "INDEX.md", "MANIFEST.json", "MERGE_NOTES.md",
    "tests/test_merge_integrity.py",
    "tools/merge/README.md", "tools/merge/build_merge.py", "tools/merge/verify_merge.py",
    "tools/merge/gate_run.py", "tools/merge/make_edits.py", "tools/merge/edits.json",
    "tools/merge/router_template.md", "tools/merge/notes_template.md", "tools/merge/GATES.md",
]
# generated one-per-command wrappers (plus their README) for real /ts-* slash commands in Claude Code
new_file_globs = ["install/claude-code-commands/*.md"]

spec = {
    "version": 1,
    "skill_name": "teaching-skill",
    "upstream": {"name": "teaching-skills", "version": "1.2.0", "author": "Jiaxing Yu", "license": "MIT",
                 "repository": "https://github.com/YujxZJCN/teaching-skills"},
    "exclusions": {"dir_names": ["__pycache__"], "globs": ["*.pyc"], "path_prefixes": ["skills/"],
                   "why": {"__pycache__/*.pyc": "compiled bytecode caches (derived build debris)",
                           "skills/": "15 git-symlink stub files, each just '../<skill>' — redundant when the "
                                      "skills are modules of one skill (verified by gate G01)"}},
    "moves": moves,
    "groups": groups,
    "prepends": prepends,
    "new_files": new_files,
    "new_file_globs": new_file_globs,
}
OUT.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
n_items = sum(len(g["items"]) for g in groups)
print(f"wrote {OUT}: {len(moves)} moves, {len(groups)} groups / {n_items} text items, "
      f"{len(prepends)} banners, {len(new_files)} declared new files")
