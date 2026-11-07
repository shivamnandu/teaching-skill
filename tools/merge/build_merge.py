#!/usr/bin/env python3
"""Build the `teaching-skill` skill from the upstream *teaching-skills* tree.

    python build_merge.py --src <upstream folder> --out <output folder> [--date YYYY-MM-DD]

What it does (deterministically, from edits.json):
  1. carries every upstream file except the declared exclusions (__pycache__/*.pyc and the
     15 skills/* git-symlink stubs);
  2. renames each module's SKILL.md -> WORKFLOW.md and relocates the upstream repo/CI files
     under upstream/ (see edits.json "moves");
  3. applies the registered text edits (count corrections, entry-file naming, moved-path
     references, two script patches) and the two README banners - nothing else is touched;
  4. generates the router SKILL.md, the /ts-* slash-command wrappers, INDEX.md,
     MERGE_NOTES.md, MANIFEST.json and copies the merge tooling into tools/merge/.

The source folder is only ever read. The output folder is only wiped if it already holds a
previous build (MANIFEST.json for the same skill name).
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_NAME = json.loads((HERE / "edits.json").read_text(encoding="utf-8"))["skill_name"]

MODULE_ORDER = ["teaching-pipeline", "course-designer", "lesson-builder", "assessment-architect",
                "student-mentor", "submission-auditor", "teaching-reflector", "deck-studio",
                "lab-forge", "media-scripter", "course-publisher", "ta-coordinator",
                "accreditation-mapper", "bilingual-courseware", "cohort-analyst"]
STAGE_LABEL = {"1": "1 DESIGN", "2": "2 BUILD", "3": "3 ASSESS", "4": "4 DELIVER", "5": "5 REFLECT",
               "orchestrator": "orchestrator", "support": "cross-cutting support"}
MODE_ROW = re.compile(r"^\|\s*`([a-z][a-z0-9-]*)`\s*\|")
REG_SECTION = re.compile(r"^##\s+([a-z][a-z0-9-]*)\s+\((\d+)\s+modes\)\s+—\s+(.*)$")
TRIGGER = re.compile(r"Triggers on:\s*(.+?)\.?\s*$")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def walk(root):
    out = []
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            out.append(p.relative_to(root).as_posix())
    return out


def is_excluded(rel, spec):
    ex = spec["exclusions"]
    parts = rel.split("/")
    if any(d in parts[:-1] for d in ex["dir_names"]):
        return True
    if any(Path(rel).match(g) for g in ex["globs"]):
        return True
    return any(rel.startswith(pref) for pref in ex["path_prefixes"])


def frontmatter_field(text, key):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    fm = m.group(1)
    if key == "description":
        d = re.search(r'^description:\s*"(.*)"\s*$', fm, re.M) or re.search(r"^description:\s*(.+?)\s*$", fm, re.M)
        return d.group(1) if d else None
    d = re.search(rf"^\s*{key}:\s*(\S+)\s*$", fm, re.M)
    return d.group(1) if d else None


def apply_items(text, items, where):
    for it in items:
        n = text.count(it["old"])
        if n != it["count"]:
            raise SystemExit(f"build error: {where}: expected {it['count']}x {it['old']!r}, found {n}")
        text = text.replace(it["old"], it["new"])
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default="2026-09-26")
    ap.add_argument("--ledger", default=str(HERE.parent / "GATES.md"),
                    help="ledger to ship (sanitized) as tools/merge/GATES.md")
    args = ap.parse_args()
    src, out = Path(args.src).resolve(), Path(args.out).resolve()
    spec = json.loads((HERE / "edits.json").read_text(encoding="utf-8"))

    if not (src / "MODE_REGISTRY.md").exists():
        raise SystemExit(f"{src} does not look like the teaching-skills tree (no MODE_REGISTRY.md)")
    if out == src or src in out.parents or out in src.parents:
        raise SystemExit("output folder must be separate from the source folder")
    if out.exists():
        mf = out / "MANIFEST.json"
        if not (mf.exists() and json.loads(mf.read_text(encoding="utf-8")).get("skill") == SKILL_NAME):
            raise SystemExit(f"{out} exists and is not a previous {SKILL_NAME} build; refusing to wipe it")
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # ---- plan -------------------------------------------------------------------------------
    all_src = walk(src)
    carried = [f for f in all_src if not is_excluded(f, spec)]
    excluded = [f for f in all_src if is_excluded(f, spec)]
    move = {m["from"]: m["to"] for m in spec["moves"]}
    for f in move:
        if f not in carried:
            raise SystemExit(f"move source missing from upstream: {f}")
    dest = {f: move.get(f, f) for f in carried}
    if len(set(dest.values())) != len(dest):
        raise SystemExit("two source files map to the same destination")
    by_file, applied_ids = {}, {}
    for g in spec["groups"]:
        for it in g["items"]:
            by_file.setdefault(it["file"], []).append(it)
            applied_ids.setdefault(it["file"], []).append(g["id"])
    prepend = {p["file"]: p for p in spec["prepends"]}

    # ---- carry + edit -----------------------------------------------------------------------
    records = []
    for f in carried:
        b = (src / f).read_bytes()
        ids = []
        if f in by_file or f in prepend:
            text = b.decode("utf-8")
            if f in by_file:
                text = apply_items(text, by_file[f], f)
                ids += sorted(set(applied_ids[f]))
            if f in prepend:
                text = prepend[f]["text"] + text
                ids.append(prepend[f]["id"])
            nb = text.encode("utf-8")
        else:
            nb = b
        if f in move and move[f].endswith("WORKFLOW.md"):
            ids.insert(0, next(m["id"] for m in spec["moves"] if m["from"] == f))
        elif f in move:
            ids.insert(0, next(m["id"] for m in spec["moves"] if m["from"] == f))
        d = out / dest[f]
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_bytes(nb)
        records.append({"path": dest[f], "bytes": len(nb), "sha256": sha(nb), "origin": "upstream",
                        "source": f, "source_sha256": sha(b), "edits": ids})

    # ---- facts about the merged tree ------------------------------------------------------------
    modules = sorted(d.name for d in out.iterdir() if d.is_dir() and (d / "WORKFLOW.md").exists())
    if sorted(MODULE_ORDER) != modules:
        raise SystemExit(f"module set differs from MODULE_ORDER: {sorted(set(modules) ^ set(MODULE_ORDER))}")
    reg_text = (out / "MODE_REGISTRY.md").read_text(encoding="utf-8")
    tier = {}
    for line in reg_text.splitlines():
        m = REG_SECTION.match(line)
        if m:
            suffix = m.group(3).lower()
            tier[m.group(1)] = ("extension" if ("extension" in suffix or "cross-cutting support" in suffix)
                                else "orchestrator" if "orchestrator" in suffix else "core")
    info = {}
    for m in MODULE_ORDER:
        wf = (out / m / "WORKFLOW.md").read_text(encoding="utf-8")
        modes = [x.group(1) for ln in wf.splitlines() if (x := MODE_ROW.match(ln)) and "_" not in x.group(1)]
        info[m] = {"modes": modes,
                   "agents": len(list((out / m / "agents").glob("*.md"))),
                   "stage": STAGE_LABEL[frontmatter_field(wf, "pipeline_stage")],
                   "tier": tier[m],
                   "triggers": TRIGGER.search(frontmatter_field(wf, "description")).group(1)}
    n_modes = sum(len(v["modes"]) for v in info.values())
    n_agents = sum(v["agents"] for v in info.values())

    cmds = []
    for f in sorted((out / "commands").glob("ts-*.md")):
        t = f.read_text(encoding="utf-8")
        d = re.search(r"^description:\s*(.+)$", t, re.M).group(1).strip()
        s = re.search(r"Trigger the `([a-z-]+)` skill in `([a-z-]+)` mode(?: \(or `([a-z-]+)` (for [^)]*)\))?", t)
        if not s:
            raise SystemExit(f"{f.name}: cannot parse 'Trigger the ... skill in ... mode'")
        purpose = d.split(" — ", 1)[1] if " — " in d else d
        cmds.append({"alias": f.stem, "module": s.group(1), "mode": s.group(2),
                     "alt": s.group(3), "alt_note": s.group(4), "purpose": purpose, "description": d})
    n_alias = len(cmds)

    # ---- router SKILL.md ------------------------------------------------------------------------
    catalog = ["| Module | Role | Modes (all) | Agents |", "|---|---|---|---|"]
    for m in MODULE_ORDER:
        v = info[m]
        modes = " · ".join(f"`{x}`" for x in v["modes"])
        role = v["tier"] if v["tier"] == v["stage"] else f"{v['tier']} · {v['stage']}"
        catalog.append(f"| [`{m}`]({m}/WORKFLOW.md) | {role} | {modes} | {v['agents']} |")
    aliases = ["| Alias | Module | Mode | What it does |", "|---|---|---|---|"]
    for c in cmds:
        mode = f"`{c['mode']}`" + (f" (or `{c['alt']}` {c['alt_note']})" if c["alt"] else "")
        aliases.append(f"| `/{c['alias']}` | {c['module']} | {mode} | {c['purpose']} |")
    kw = ["| Module | Trigger keywords (verbatim from the module's description) |", "|---|---|"]
    for m in MODULE_ORDER:
        kw.append(f"| {m} | {info[m]['triggers']} |")
    tpl = (HERE / "router_template.md").read_text(encoding="utf-8")
    repl = {"SKILL_NAME": SKILL_NAME, "N_MODULES": len(MODULE_ORDER), "N_MODES": n_modes, "N_AGENTS": n_agents,
            "N_ALIASES": n_alias, "MERGE_DATE": args.date, "MODULE_CATALOG": "\n".join(catalog),
            "ALIAS_TABLE": "\n".join(aliases), "KEYWORD_INDEX": "\n".join(kw)}
    for k, v in repl.items():
        tpl = tpl.replace("{{" + k + "}}", str(v))
    if "{{" in tpl:
        raise SystemExit("unreplaced placeholder in router: " + re.search(r"\{\{[^}]*\}\}", tpl).group(0))
    desc = frontmatter_field(tpl, "description")
    if len(desc) > 1024 or "<" in desc or ">" in desc:
        raise SystemExit(f"router description invalid: {len(desc)} chars, angle brackets: {'<' in desc or '>' in desc}")
    (out / "SKILL.md").write_text(tpl, encoding="utf-8", newline="\n")

    # ---- slash-command wrappers -----------------------------------------------------------------
    wdir = out / "install" / "claude-code-commands"
    wdir.mkdir(parents=True)
    for c in cmds:
        body = (f"---\ndescription: {c['description']}\n---\n\n"
                f"Use the `{SKILL_NAME}` skill for this request: route it to the `{c['module']}` module in "
                f"`{c['mode']}` mode"
                + (f" (or `{c['alt']}` {c['alt_note']})" if c["alt"] else "")
                + f" — entry file `{c['module']}/WORKFLOW.md` in the skill's base directory — and follow that "
                f"workflow. The alias recipe is `commands/{c['alias']}.md` there.\n\nRequest: $ARGUMENTS\n")
        (wdir / f"{c['alias']}.md").write_text(body, encoding="utf-8", newline="\n")
    (wdir / "README.md").write_text(
        f"# Real `/ts-*` slash commands for Claude Code\n\n"
        f"The upstream suite shipped {n_alias} slash commands. Inside the merged skill they are *recipes* the "
        f"router reads (`commands/`), reachable as `/{SKILL_NAME} ts-exam …`. If you also want the short "
        f"`/ts-exam`-style commands, copy the wrappers in this folder into your Claude Code commands "
        f"folder:\n\n"
        f"```\n# Windows PowerShell\nCopy-Item \"<path-to>\\{SKILL_NAME}\\install\\claude-code-commands\\ts-*.md\" "
        f"\"$HOME\\.claude\\commands\\\"\n\n# macOS / Linux\ncp <path-to>/{SKILL_NAME}/install/claude-code-commands/ts-*.md "
        f"~/.claude/commands/\n```\n\n"
        f"Each wrapper just hands the request to the `{SKILL_NAME}` skill with the right module and mode, so "
        f"the skill itself must be installed too. They are optional; nothing else depends on them.\n",
        encoding="utf-8", newline="\n")

    # ---- tools + tests --------------------------------------------------------------------------
    tdir = out / "tools" / "merge"
    tdir.mkdir(parents=True)
    for name in ["build_merge.py", "verify_merge.py", "gate_run.py", "make_edits.py", "edits.json",
                 "router_template.md", "notes_template.md"]:
        shutil.copyfile(HERE / name, tdir / name)
    shutil.copyfile(HERE / "test_merge_integrity.py", out / "tests" / "test_merge_integrity.py")
    ledger = Path(args.ledger).read_text(encoding="utf-8")
    ledger = re.sub(r"^- \[x\]", "- [ ]", ledger, flags=re.M)
    ledger = re.sub(r"^VAR (\w+)\s*=.*$", lambda mo: {
        "PY": "VAR PY   = python", "TOOL": "VAR TOOL = tools/merge",
        "SRC": "VAR SRC  = <path to the untouched upstream teaching-skills folder>",
        "OUT": "VAR OUT  = <path to this skill folder>",
        "SC": "VAR SC   = <optional: path to Anthropic's skill-creator folder>"}.get(mo.group(1), mo.group(0)), ledger, flags=re.M)
    ledger = re.sub(r"^  EVIDENCE:.*$", "  EVIDENCE: see MERGE_NOTES.md (Verification record)", ledger, flags=re.M)
    # no absolute path into anyone's home folder may ship (it would leak a username): keep only a <home> placeholder
    ledger = re.sub(r"[A-Za-z]:\\Users\\[^\\\s\"'`]+\\", lambda mo: "<home>\\", ledger)
    ledger = ("<!-- Shipped copy of the verification ledger used for this merge. Paths are placeholders and "
              "tick boxes are reset; results are summarized in MERGE_NOTES.md. -->\n") + ledger
    (tdir / "GATES.md").write_text(ledger, encoding="utf-8", newline="\n")
    n_auto = len(re.findall(r"^  CHECK:", ledger, flags=re.M))
    n_manual = len(re.findall(r"^  MANUAL: yes", ledger, flags=re.M))
    (tdir / "README.md").write_text(
        f"# tools/merge — how this skill was built and checked\n\n"
        f"| File | Purpose |\n|---|---|\n"
        f"| `edits.json` | the complete declarative list of differences from upstream (moves, text edits, banners, declared new files) |\n"
        f"| `make_edits.py` | regenerates `edits.json` from an upstream tree, failing if any expected string is missing |\n"
        f"| `build_merge.py` | builds this skill from an upstream tree (`--src`, `--out`) |\n"
        f"| `router_template.md`, `notes_template.md` | templates for `SKILL.md` and `MERGE_NOTES.md` |\n"
        f"| `verify_merge.py` | independent checker; `--gate G03` etc., or `--all` (provenance gates need `--src`) |\n"
        f"| `gate_run.py` | runs the ledger `GATES.md` ({n_auto} automated gates, {n_manual} manual) |\n\n"
        f"Package-only checks (no upstream needed) run with `python tools/merge/verify_merge.py --out . --package` "
        f"and as `pytest tests/test_merge_integrity.py`. Provenance checks compare against the untouched upstream "
        f"folder: `python tools/merge/verify_merge.py --src <upstream> --out . --all`.\n",
        encoding="utf-8", newline="\n")

    # ---- MERGE_NOTES.md -------------------------------------------------------------------------
    n_unchanged = sum(1 for r in records if r["source"] == r["path"] and r["sha256"] == r["source_sha256"])
    n_moved_only = sum(1 for r in records if r["source"] != r["path"] and r["sha256"] == r["source_sha256"])
    n_changed = sum(1 for r in records if r["sha256"] != r["source_sha256"])
    n_identical = n_unchanged
    n_renamed = sum(1 for m in spec["moves"] if m["kind"] == "rename")
    n_reloc = sum(1 for m in spec["moves"] if m["kind"] == "relocate")
    n_generated = len(spec["new_files"]) + n_alias + 1  # + the wrapper folder's README
    edit_lines = []
    for g in spec["groups"]:
        files = sorted({dest[it["file"]] for it in g["items"]})
        n_files = len(files)
        shown = ", ".join(f"`{x}`" for x in files) if n_files <= 4 else f"{n_files} files"
        edit_lines.append(f"- **{g['id']}** ({len(g['items'])} edit{'s' if len(g['items']) != 1 else ''} in "
                          f"{n_files} file{'s' if n_files != 1 else ''}) — {g['summary']}. *Why:* {g['why']}. "
                          f"Files: {shown}.")
    for p in spec["prepends"]:
        edit_lines.append(f"- **{p['id']}** (1 edit in 1 file) — banner prepended to `{p['file']}`. *Why:* {p['why']}.")
    move_lines = []
    for m in spec["moves"]:
        if m["kind"] == "relocate":
            move_lines.append(f"| {m['id']} | {m['from']} | `{m['to']}` | {m['why']} |")
    notes = (HERE / "notes_template.md").read_text(encoding="utf-8")
    nrepl = {"DATE": args.date, "N_SRC_TOTAL": len(all_src), "N_CARRIED": len(carried),
             "N_EXCLUDED": len(excluded),
             "N_PYC": sum(1 for e in excluded if e.endswith(".pyc")),
             "N_STUBS": sum(1 for e in excluded if e.startswith("skills/")),
             "N_UNCHANGED": n_unchanged, "N_MOVED_ONLY": n_moved_only, "N_CHANGED": n_changed,
             "N_GENERATED": n_generated,
             "GATE_LIST": "\n".join(f"- **{gid}** — {title}" for gid, title in
                                    re.findall(r"^- \[[ x]\] ([A-Z]\d+): (.+)$", ledger, flags=re.M)),
             "N_RENAMED": n_renamed, "N_RELOCATED": n_reloc, "N_MODULES": len(MODULE_ORDER),
             "N_MODES": n_modes, "N_AGENTS": n_agents, "N_ALIASES": n_alias,
             "N_AUTO": n_auto, "N_MANUAL": n_manual, "SKILL_NAME": SKILL_NAME,
             "EDIT_LIST": "\n".join(edit_lines),
             "MOVE_TABLE": "| id | upstream path | now at | why |\n|---|---|---|---|\n" + "\n".join(move_lines)}
    for k, v in nrepl.items():
        notes = notes.replace("{{" + k + "}}", str(v))
    if "{{" in notes:
        raise SystemExit("unreplaced placeholder in notes: " + re.search(r"\{\{[^}]*\}\}", notes).group(0))
    (out / "MERGE_NOTES.md").write_text(notes, encoding="utf-8", newline="\n")

    # ---- INDEX.md -------------------------------------------------------------------------------
    def describe(rel, text):
        name = Path(rel).name
        if rel.endswith(".py"):
            m = re.search(r'^"""(.*?)(?:\n|""")', text, re.S)
            return (m.group(1).strip() if m else "Python script").rstrip(".")
        if rel.endswith(".json"):
            return "JSON Schema for course_passport.yaml" if name == "course_passport.schema.json" else "JSON data"
        if rel.endswith((".yaml", ".yml")):
            first = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("#")), "")
            return first or "YAML"
        if rel.endswith(".html"):
            m = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
            return "HTML: " + (m.group(1).strip() if m else "document")
        if rel.endswith(".md"):
            d = frontmatter_field(text, "description")
            if d and "/agents/" in "/" + rel:
                return d
            if d and rel.startswith("commands/") or d and rel.startswith("install/"):
                return d
            body = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
            h = re.search(r"^#\s+(.+)$", body, re.M)
            title = h.group(1).strip() if h else name
            return f"Module entry: {title}" if name == "WORKFLOW.md" else title
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:3]
        return ("Upstream file: " if name in (".gitignore", "requirements-dev.txt") else "") + "; ".join(lines)

    order_areas = [("Router and documentation (root)", lambda r: "/" not in r),
                   *[(f"Module: {m}", (lambda mm: (lambda r: r.startswith(mm + "/")))(m)) for m in MODULE_ORDER],
                   ("Shared contracts", lambda r: r.startswith("shared/")),
                   ("Command recipes", lambda r: r.startswith("commands/")),
                   ("Claude Code slash-command wrappers", lambda r: r.startswith("install/")),
                   ("Scripts", lambda r: r.startswith("scripts/")),
                   ("Tests", lambda r: r.startswith("tests/")),
                   ("Docs", lambda r: r.startswith("docs/")),
                   ("Examples", lambda r: r.startswith("examples/")),
                   ("Merge tooling", lambda r: r.startswith("tools/")),
                   ("Archived upstream repository files", lambda r: r.startswith("upstream/"))]
    listed = sorted(walk(out))
    idx = [f"# INDEX — every file in the {SKILL_NAME} skill", "",
           "One line per file. Paths are relative to the skill's base directory. Generated by "
           "`tools/merge/build_merge.py`; `INDEX.md` and `MANIFEST.json` themselves are not listed.", ""]
    seen = set()
    for title, pred in order_areas:
        rows = [r for r in listed if pred(r) and r not in ("INDEX.md", "MANIFEST.json") and r not in seen]
        if not rows:
            continue
        idx += [f"## {title}", "", "| File | What it is |", "|---|---|"]
        for r in rows:
            seen.add(r)
            t = (out / r).read_text(encoding="utf-8")
            desc_ = describe(r, t).replace("|", "\\|").replace("\n", " ")
            if len(desc_) > 170:
                desc_ = desc_[:167].rstrip() + "…"
            idx.append(f"| `{r}` | {desc_} |")
        idx.append("")
    leftovers = [r for r in listed if r not in seen and r not in ("INDEX.md", "MANIFEST.json")]
    if leftovers:
        raise SystemExit(f"files not covered by any INDEX area: {leftovers}")
    (out / "INDEX.md").write_text("\n".join(idx) + "\n", encoding="utf-8", newline="\n")

    # ---- MANIFEST.json --------------------------------------------------------------------------
    gen = set(spec["new_files"]) - {"MANIFEST.json"}
    for r in walk(out):
        if r in ("MANIFEST.json",) or r in {x["path"] for x in records}:
            continue
        b = (out / r).read_bytes()
        records.append({"path": r, "bytes": len(b), "sha256": sha(b), "origin": "generated",
                        "source": None, "source_sha256": None, "edits": []})
    records.sort(key=lambda x: x["path"])
    manifest = {"schema": 1, "skill": SKILL_NAME, "generated": args.date, "upstream": spec["upstream"],
                "counts": {"source_files": len(all_src), "carried": len(carried), "excluded": len(excluded),
                           "identical": n_identical, "edited": len(carried) - n_identical,
                           "generated": sum(1 for r in records if r["origin"] == "generated"),
                           "total_in_package": len(records) + 1, "modules": len(MODULE_ORDER),
                           "modes": n_modes, "agents": n_agents, "aliases": n_alias},
                "excluded": excluded, "files": records}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
                                       encoding="utf-8", newline="\n")
    print(f"built {out}\n  carried {len(carried)} of {len(all_src)} source files "
          f"({len(excluded)} excluded), {n_identical} byte-identical, {len(carried) - n_identical} edited/renamed/moved\n"
          f"  modules {len(MODULE_ORDER)}, modes {n_modes}, agents {n_agents}, aliases {n_alias}\n"
          f"  router: {len(tpl.splitlines())} lines, description {len(desc)} chars")


if __name__ == "__main__":
    sys.exit(main())
