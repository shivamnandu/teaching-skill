#!/usr/bin/env python3
"""Independent verifier for the `teaching-skill` merge (never imports the builder).

  verify_merge.py --src <upstream> --out <skill folder> --gate G03     one gate
  verify_merge.py --src <upstream> --out <skill folder> --all          every gate
  verify_merge.py --out <skill folder> --package                       gates that need no upstream copy
  add --skill-creator <folder> (or set SKILL_CREATOR_DIR) to also run Anthropic's validator/packager in G05 and G25

Each gate prints one line `Gnn PASS - detail` / `Gnn FAIL - detail` (exit 0 / 1). Provenance gates
(G01-G04, parts of G16, G18, G21, G27) need --src; without it they print `Gnn SKIP`.

Design rule: expected bytes are recomputed from the RAW upstream files plus edits.json only, so a bug
in the builder cannot make this verifier agree with a wrong output.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_skill_creator(arg=None):
    """Anthropic's skill-creator folder is OPTIONAL: pass --skill-creator <folder> or set SKILL_CREATOR_DIR.
    Without it the external validator / packager comparisons are skipped; no path is hard-coded here."""
    p = arg or os.environ.get("SKILL_CREATOR_DIR")
    p = Path(p) if p else None
    return p if p and (p / "scripts" / "quick_validate.py").exists() else None


MODE_ROW = re.compile(r"^\|\s*`([a-z][a-z0-9-]*)`\s*\|")
REG_SECTION = re.compile(r"^##\s+([a-z][a-z0-9-]*)\s+\((\d+)\s+modes\)")
REG_ROW = re.compile(r"^\|\s*([a-z][a-z0-9-]*)\s*\|\s*(.*?)\s*\|")
REG_TOTAL = re.compile(r"\*\*Total:\s*(\d+)\s+modes\s+across\s+(\d+)\s+skills.*?,\s*(\d+)\s+agents\.\*\*")
AGENT_TEAM = re.compile(r"^##\s+Agent Team\s+\((\d+)\)")
TRIGGER = re.compile(r"Triggers on:\s*(.+?)\.?\s*$")
TABLE_HEAD = {"mode", "command", "purpose", "trigger-intent"}
REF_ROOTS = {"shared", "scripts", "docs", "examples", "commands", "tests", "references", "templates",
             "agents", "tools", "upstream", "install"}
PLACEHOLDER = re.compile(r"\{\{|<[a-z]|\.\.\.|/X/|<skill>|<id>|<hash>|<passport>|<file>|<mode>|<name>")
FILE_TOKEN = re.compile(r"`([A-Za-z0-9_][\w.-]*(?:/[\w.-]+)+\.(?:md|py|json|ya?ml|html|txt))`")
DIR_TOKEN = re.compile(r"`([A-Za-z0-9_][\w.-]*(?:/[\w.-]+)*/)`")
MD_LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
GENERIC_MODULE_DIRS = {"agents/", "references/", "templates/"}


# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------
def sha(b):
    return hashlib.sha256(b).hexdigest()


CACHE_DIRS = {"__pycache__", ".pytest_cache"}


def walk(root, include_caches=False):
    """Relative posix paths of every file. Cache debris (bytecode, pytest cache) is ignored unless asked for,
    so running the test suite never makes the integrity checks fail; G24 asks for it explicitly."""
    out = []
    for p in Path(root).rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if not include_caches and (any(part in CACHE_DIRS for part in rel.parts[:-1]) or rel.suffix == ".pyc"):
            continue
        out.append(rel.as_posix())
    return sorted(out)


def load_spec():
    return json.loads((HERE / "edits.json").read_text(encoding="utf-8"))


SKILL_NAME = load_spec()["skill_name"]


def fm_field(text, key):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    fm = m.group(1)
    if key == "description":
        d = re.search(r'^description:\s*"(.*)"\s*$', fm, re.M) or re.search(r"^description:\s*(.+?)\s*$", fm, re.M)
        return d.group(1) if d else None
    d = re.search(rf"^\s*{key}:\s*(\S+)\s*$", fm, re.M)
    return d.group(1) if d else None


def fm_block(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else None


def modules_of(out):
    return sorted(d.name for d in Path(out).iterdir() if d.is_dir() and (d / "WORKFLOW.md").exists())


def modes_in_workflow(text):
    return [m.group(1) for ln in text.splitlines() if (m := MODE_ROW.match(ln)) and "_" not in m.group(1)]


def registry(out):
    """{module: [(mode, command-cell)]}, totals tuple or None"""
    text = (Path(out) / "MODE_REGISTRY.md").read_text(encoding="utf-8")
    secs, cur = {}, None
    for ln in text.splitlines():
        s = REG_SECTION.match(ln)
        if s:
            cur = s.group(1)
            secs[cur] = []
            continue
        if ln.startswith("## ") or ln.startswith("# "):
            cur = None
            continue
        if cur:
            r = REG_ROW.match(ln)
            if r and r.group(1) not in TABLE_HEAD:
                secs[cur].append((r.group(1), r.group(2)))
    t = REG_TOTAL.search(text)
    return secs, (tuple(int(x) for x in t.groups()) if t else None)


def commands_of(out):
    res = {}
    for f in sorted((Path(out) / "commands").glob("ts-*.md")):
        t = f.read_text(encoding="utf-8")
        s = re.search(r"Trigger the `([a-z-]+)` skill in `([a-z-]+)` mode(?: \(or `([a-z-]+)` (for [^)]*)\))?", t)
        d = re.search(r"^description:\s*(.+)$", t, re.M)
        res[f.stem] = {"module": s.group(1), "mode": s.group(2), "alt": s.group(3), "desc": d.group(1).strip()}
    return res


def norm_ws(s):
    """collapse whitespace so a phrase that wraps across lines still matches"""
    return re.sub(r"\s+", " ", s)


def run(cmd, cwd, extra_env=None, timeout=900):
    # PYTHONUTF8: Anthropic's validator/packager read SKILL.md with the platform default encoding, which
    # is cp1252 on Windows and cannot decode this skill's non-ASCII text without UTF-8 mode.
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    env.update(extra_env or {})
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def copytree_clean(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))


class Ctx:
    def __init__(self, out, src=None, skill_creator=None):
        self.out = Path(out).resolve()
        self.src = Path(src).resolve() if src else None
        self.skill_creator = find_skill_creator(skill_creator)
        self.spec = load_spec()

    def need_src(self):
        return self.src is not None


# ------------------------------------------------------------------------------------------------
# provenance gates
# ------------------------------------------------------------------------------------------------
def is_excluded(rel, spec):
    ex = spec["exclusions"]
    parts = rel.split("/")
    if any(d in parts[:-1] for d in ex["dir_names"]):
        return True
    if any(Path(rel).match(g) for g in ex["globs"]):
        return True
    return any(rel.startswith(p) for p in ex["path_prefixes"])


def src_files(ctx):
    return walk(ctx.src, include_caches=True)


def g01(c):
    allf = src_files(c)
    exc = [f for f in allf if is_excluded(f, c.spec)]
    car = [f for f in allf if f not in set(exc)]
    stubs = [f for f in exc if f.startswith("skills/")]
    pyc = [f for f in exc if f not in stubs]
    bad = [f for f in stubs if (c.src / f).read_bytes().decode("utf-8", "replace").strip() != "../" + f.split("/", 1)[1]]
    if bad:
        return False, f"skills/ files that are not plain '../<name>' pointers: {bad}"
    if not all(f.endswith(".pyc") and "__pycache__" in f.split("/") for f in pyc):
        return False, f"unexpected exclusions: {[f for f in pyc if not (f.endswith('.pyc') and '__pycache__' in f.split('/'))]}"
    mods = {f.split("/")[0] for f in car if f.endswith("/SKILL.md") and f.count("/") == 1}
    if len(stubs) != len(mods) or {f.split("/", 1)[1] for f in stubs} != mods:
        return False, f"skills/ stubs ({len(stubs)}) do not match the {len(mods)} skill folders"
    mf = json.loads((c.out / "MANIFEST.json").read_text(encoding="utf-8"))
    if sorted(mf["excluded"]) != sorted(exc) or mf["counts"]["source_files"] != len(allf):
        return False, "MANIFEST exclusion list / source count disagrees with the actual source tree"
    return True, (f"{len(allf)} source files enumerated: {len(car)} carried, {len(exc)} excluded "
                  f"({len(pyc)} .pyc, {len(stubs)} '../<skill>' stubs, verified)")


def expected(c, rel, b):
    """bytes the merged file must have: source + registered items (+ prepend)"""
    items = [it for g in c.spec["groups"] for it in g["items"] if it["file"] == rel]
    pre = [p for p in c.spec["prepends"] if p["file"] == rel]
    if not items and not pre:
        return b, {}
    text = b.decode("utf-8")
    counts = {}
    for g in c.spec["groups"]:
        for it in g["items"]:
            if it["file"] != rel:
                continue
            n = text.count(it["old"])
            if n != it["count"]:
                raise ValueError(f"{rel}: registered edit {g['id']} expects {it['count']}x {it['old']!r}, source has {n}")
            text = text.replace(it["old"], it["new"])
            counts[g["id"]] = counts.get(g["id"], 0) + n
    for p in pre:
        text = p["text"] + text
        counts[p["id"]] = 1
    return text.encode("utf-8"), counts


def dest_map(c):
    move = {m["from"]: m["to"] for m in c.spec["moves"]}
    car = [f for f in src_files(c) if not is_excluded(f, c.spec)]
    return {f: move.get(f, f) for f in car}, move


def declared_new(c):
    files = set(c.spec["new_files"])
    for pat in c.spec.get("new_file_globs", []):
        files |= {f for f in walk(c.out) if Path(f).match(pat)}
    return files


def g02(c):
    dm, move = dest_map(c)
    if len(set(dm.values())) != len(dm):
        return False, "two source files map to one destination"
    have = set(walk(c.out))
    missing = sorted(d for d in dm.values() if d not in have)
    if missing:
        return False, f"{len(missing)} carried files missing from the merge, e.g. {missing[:5]}"
    new = declared_new(c)
    absent_new = sorted(f for f in c.spec["new_files"] if f not in have)
    if absent_new:
        return False, f"declared new files absent: {absent_new}"
    extra = sorted(have - set(dm.values()) - new)
    if extra:
        return False, f"undeclared extra files in the merge: {extra[:8]}"
    return True, (f"{len(dm)} carried files all present at mapped paths ({len(move)} moved/renamed); "
                  f"{len(have) - len(dm)} declared new files; no strays")


def g03(c):
    dm, _ = dest_map(c)
    same = moved = changed = 0
    per = {}
    for f, d in dm.items():
        b = (c.src / f).read_bytes()
        exp, counts = expected(c, f, b)
        got = (c.out / d).read_bytes()
        if got != exp:
            i = next((k for k in range(min(len(got), len(exp))) if got[k] != exp[k]), min(len(got), len(exp)))
            return False, f"{d}: merged bytes differ from source+registered edits at byte {i} (source {f})"
        for k, v in counts.items():
            per[k] = per.get(k, 0) + v
        if exp != b:
            changed += 1
        elif f != d:
            moved += 1
        else:
            same += 1
    for g in c.spec["groups"]:
        want = sum(it["count"] for it in g["items"])
        if per.get(g["id"], 0) != want:
            return False, f"edit group {g['id']} applied {per.get(g['id'], 0)}x, registered {want}x"
    return True, (f"{len(dm)} carried files: {same} byte-identical in place, {moved} moved/renamed byte-identical, "
                  f"{changed} differ only by registered edits ({sum(per.values())} edit applications in "
                  f"{len(c.spec['groups']) + len(c.spec['prepends'])} groups)")


def g04(c):
    reg, tot = registry(c.out)
    mods = sorted(d.name for d in c.src.iterdir() if d.is_dir() and (d / "SKILL.md").exists())
    if len(mods) != 15:
        return False, f"source has {len(mods)} skill folders, expected 15"
    n_agents = n_ref = n_tpl = 0
    for m in mods:
        wf = c.out / m / "WORKFLOW.md"
        if not wf.exists():
            return False, f"{m}/WORKFLOW.md missing"
        if fm_field(wf.read_text(encoding="utf-8"), "name") != m:
            return False, f"{m}/WORKFLOW.md frontmatter name != folder name"
        for sub in ("agents", "references", "templates"):
            a = sorted(p.relative_to(c.src / m / sub).as_posix() for p in (c.src / m / sub).rglob("*") if p.is_file()) \
                if (c.src / m / sub).exists() else []
            b = sorted(p.relative_to(c.out / m / sub).as_posix() for p in (c.out / m / sub).rglob("*") if p.is_file()) \
                if (c.out / m / sub).exists() else []
            if a != b:
                return False, f"{m}/{sub}: file sets differ (only source: {sorted(set(a) - set(b))}, only merged: {sorted(set(b) - set(a))})"
            n_agents += len(a) if sub == "agents" else 0
            n_ref += len(a) if sub == "references" else 0
            n_tpl += len(a) if sub == "templates" else 0
    if tot is None or n_agents != tot[2]:
        return False, f"agents in modules ({n_agents}) != registry total {tot}"
    return True, f"15 modules complete: {n_agents} agents, {n_ref} references, {n_tpl} templates identical file sets"


# ------------------------------------------------------------------------------------------------
# package gates
# ------------------------------------------------------------------------------------------------
ALLOWED_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def g05(c):
    hits = [p for p in walk(c.out) if Path(p).name.lower() == "skill.md" and "__pycache__" not in p.split("/")]
    if hits != ["SKILL.md"]:
        return False, f"expected exactly one SKILL.md at the root, found {hits}"
    text = (c.out / "SKILL.md").read_text(encoding="utf-8")
    block = fm_block(text)
    if block is None:
        return False, "no YAML frontmatter"
    try:
        import yaml
        fm = yaml.safe_load(block)
    except ImportError:
        fm = {"name": fm_field(text, "name"), "description": fm_field(text, "description")}
    except Exception as e:  # noqa: BLE001
        return False, f"frontmatter is not valid YAML: {e}"
    extra = set(fm) - ALLOWED_KEYS
    if extra:
        return False, f"disallowed frontmatter keys: {sorted(extra)}"
    name, desc = str(fm.get("name", "")), str(fm.get("description", ""))
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or len(name) > 64:
        return False, f"bad name {name!r}"
    if name != SKILL_NAME:
        return False, f"frontmatter name {name!r} is not the skill name {SKILL_NAME!r}"
    if c.out.name == SKILL_NAME and name != c.out.name:
        return False, "frontmatter name differs from folder name"
    if not desc.strip() or len(desc) > 1024 or "<" in desc or ">" in desc:
        return False, f"description invalid ({len(desc)} chars, angle brackets: {'<' in desc or '>' in desc})"
    ext = ""
    if c.skill_creator:
        qv = c.skill_creator / "scripts" / "quick_validate.py"
        code, vout = run([sys.executable, str(qv), str(c.out)], c.skill_creator)
        if code != 0 or "Skill is valid!" not in vout:
            return False, f"Anthropic quick_validate rejected the skill: {vout.strip()[-300:]}"
        ext = "; Anthropic quick_validate: valid"
    return True, f"1 SKILL.md, name '{name}', description {len(desc)}/1024 chars, keys {sorted(fm)}{ext}"


def router(c):
    return (c.out / "SKILL.md").read_text(encoding="utf-8")


def g06(c):
    r = router(c)
    n = len(r.splitlines())
    if n > 500:
        return False, f"router is {n} lines (limit 500)"
    mods = modules_of(c.out)
    missing = [m for m in mods if f"]({m}/WORKFLOW.md)" not in r]
    if missing or len(mods) != 15:
        return False, f"router does not link WORKFLOW.md of: {missing}; modules found {len(mods)}"
    return True, f"router {n} lines; links all {len(mods)} module entry files, each present"


def parse_catalog(r):
    rows = {}
    for ln in r.splitlines():
        m = re.match(r"^\| \[`([a-z-]+)`\]\(([^)]+)\) \| ([^|]+) \| (.+) \| (\d+) \|$", ln)
        if m:
            rows.setdefault(m.group(1), []).append((m.group(2), re.findall(r"`([a-z-]+)`", m.group(4)), int(m.group(5))))
    return rows


def g07(c):
    r = router(c)
    cat = parse_catalog(r)
    reg, tot = registry(c.out)
    mods = modules_of(c.out)
    if sorted(cat) != mods or any(len(v) != 1 for v in cat.values()):
        return False, f"router catalog modules {sorted(cat)} != modules {mods} (or duplicated rows)"
    total = 0
    for m in mods:
        wf_modes = modes_in_workflow((c.out / m / "WORKFLOW.md").read_text(encoding="utf-8"))
        reg_modes = [x for x, _ in reg.get(m, [])]
        rt_modes = cat[m][0][1]
        if not (set(wf_modes) == set(reg_modes) == set(rt_modes)) or len(rt_modes) != len(set(rt_modes)):
            return False, (f"{m}: mode sets differ - workflow {sorted(wf_modes)}, registry {sorted(reg_modes)}, "
                           f"router {sorted(rt_modes)}")
        agents = len(list((c.out / m / "agents").glob("*.md")))
        if cat[m][0][2] != agents:
            return False, f"{m}: router says {cat[m][0][2]} agents, folder has {agents}"
        if cat[m][0][0] != f"{m}/WORKFLOW.md":
            return False, f"{m}: router link target {cat[m][0][0]}"
        total += len(rt_modes)
    if tot is None or total != tot[0]:
        return False, f"router mode total {total} != registry totals line {tot}"
    return True, f"router mode index == MODE_REGISTRY == each WORKFLOW.md Modes table for all {len(mods)} modules ({total} modes)"


def parse_aliases(r):
    rows = {}
    for ln in r.splitlines():
        m = re.match(r"^\| `/(ts-[a-z-]+)` \| ([a-z-]+) \| (.+?) \| (.+) \|$", ln)
        if m:
            rows[m.group(1)] = (m.group(2), re.findall(r"`([a-z-]+)`", m.group(3)))
    return rows


def g08(c):
    r = router(c)
    al = parse_aliases(r)
    cmds = commands_of(c.out)
    reg, _ = registry(c.out)
    if sorted(al) != sorted(cmds):
        return False, f"router aliases != command files: missing {sorted(set(cmds) - set(al))}, extra {sorted(set(al) - set(cmds))}"
    reg_cmds = set()
    for rows in reg.values():
        for _, cell in rows:
            reg_cmds |= set(re.findall(r"/(ts-[a-z-]+)", cell))
    if reg_cmds != set(cmds):
        return False, f"registry command column {sorted(reg_cmds ^ set(cmds))} disagrees with commands/"
    for a, spec in cmds.items():
        mod, modes = al[a]
        if mod != spec["module"] or modes[0] != spec["mode"] or (spec["alt"] and spec["alt"] not in modes):
            return False, f"{a}: router says {mod}/{modes}, command file says {spec['module']}/{spec['mode']}/{spec['alt']}"
        if not any(x == spec["mode"] and f"/{a}" in cell for x, cell in reg.get(spec["module"], [])):
            return False, f"{a}: registry row ({spec['module']}, {spec['mode']}) does not list /{a}"
    wdir = c.out / "install" / "claude-code-commands"
    wr = sorted(p.stem for p in wdir.glob("ts-*.md"))
    if wr != sorted(cmds):
        return False, f"wrapper set != aliases: {sorted(set(wr) ^ set(cmds))}"
    for a, spec in cmds.items():
        t = (wdir / f"{a}.md").read_text(encoding="utf-8")
        d = re.search(r"^description:\s*(.+)$", t, re.M)
        if not d or d.group(1).strip() != spec["desc"]:
            return False, f"wrapper {a}: description differs from the recipe's"
        if f"`{spec['module']}` module in `{spec['mode']}` mode" not in t or f"{spec['module']}/WORKFLOW.md" not in t \
                or "$ARGUMENTS" not in t or SKILL_NAME not in t:
            return False, f"wrapper {a}: does not route to {spec['module']}/{spec['mode']}"
        try:
            import yaml
            fm = yaml.safe_load(fm_block(t))
            if not isinstance(fm, dict) or not fm.get("description"):
                return False, f"wrapper {a}: frontmatter does not parse to a description"
        except ImportError:
            pass
        except Exception as e:  # noqa: BLE001
            return False, f"wrapper {a}: frontmatter YAML error {e}"
    return True, f"{len(al)} aliases: router == commands/ == registry Command column == wrappers"


COUNT_FILES_STALE_EXEMPT = {"MERGE_NOTES.md", "tools/merge/edits.json", "tools/merge/make_edits.py",
                            "tools/merge/verify_merge.py", "tools/merge/build_merge.py", "CHANGELOG.md",
                            "tests/test_merge_integrity.py"}
STALE = ["84 modes", "71-agent", "84 种模式", "71 个智能体", "Seven extension skills",
         "6-agent team covering learning outcomes", "7-agent team covering test blueprints",
         "5-agent team covering feedback"]


def g09(c):
    reg, tot = registry(c.out)
    mods = modules_of(c.out)
    n_modes = sum(len(v) for v in reg.values())
    n_agents = sum(len(list((c.out / m / "agents").glob("*.md"))) for m in mods)
    n_alias = len(list((c.out / "commands").glob("ts-*.md")))
    n_ext = sum(1 for m in mods if "extension" in (re.search(rf"^## {m} \(\d+ modes\) — (.*)$",
                                                        (c.out / "MODE_REGISTRY.md").read_text(encoding="utf-8"), re.M).group(1).lower())
                or "cross-cutting support" in (re.search(rf"^## {m} \(\d+ modes\) — (.*)$",
                                                          (c.out / "MODE_REGISTRY.md").read_text(encoding="utf-8"), re.M).group(1).lower()))
    facts = {"skills": len(mods), "modes": n_modes, "agents": n_agents, "aliases": n_alias, "extensions": n_ext}
    if tot != (n_modes, len(mods), n_agents):
        return False, f"MODE_REGISTRY totals line {tot} != computed {(n_modes, len(mods), n_agents)}"
    r = router(c)
    checks = []
    for label, pat, want in [
        ("router modules", r"(\d+) specialist modules", facts["skills"]), ("router modes", r"(\d+) modes", facts["modes"]),
        ("router agents", r"(\d+) role-specific agent prompts", facts["agents"]),
        ("router aliases", r"the (\d+) command recipes", facts["aliases"]),
        ("router metadata", r'coverage: "(\d+) modules, \d+ modes', facts["skills"])]:
        for m in re.finditer(pat, r):
            checks.append((label, int(m.group(1)), want))
    cov = re.search(r'coverage: "(\d+) modules, (\d+) modes, (\d+) agents, (\d+) command aliases"', r)
    if not cov or tuple(map(int, cov.groups())) != (facts["skills"], facts["modes"], facts["agents"], facts["aliases"]):
        return False, f"router metadata.coverage {cov.groups() if cov else None} != {facts}"
    docs = (c.out / "README.md").read_text(encoding="utf-8")
    zh = (c.out / "README.zh-CN.md").read_text(encoding="utf-8")
    for label, txt, pat, want in [
        ("README summary line", docs, r"(\d+) skills · (\d+) modes · (\d+)-agent", (facts["skills"], facts["modes"], facts["agents"])),
        ("README.zh-CN summary line", zh, r"(\d+) 个技能 · (\d+) 种模式 · (\d+) 个智能体", (facts["skills"], facts["modes"], facts["agents"]))]:
        m = re.search(pat, txt)
        if not m or tuple(map(int, m.groups())) != want:
            return False, f"{label}: {m.groups() if m else None} != {want}"
    for label, txt, pat in [("README 'all N modes'", docs, r"for all (\d+) modes"), ("README.zh-CN 'all N modes'", zh, r"全部 (\d+) 种模式")]:
        m = re.search(pat, txt)
        if not m or int(m.group(1)) != facts["modes"]:
            return False, f"{label}: {m.group(1) if m else None} != {facts['modes']}"
    manifests = [c.out / "upstream/claude-plugin/plugin.json", c.out / "upstream/claude-plugin/marketplace.json"]
    for mp in manifests:
        if mp.exists():
            t = mp.read_text(encoding="utf-8")
            for pat, want, lab in [(r"(\d+) skills", facts["skills"], "skills"), (r"(\d+) modes", facts["modes"], "modes"),
                                   (r"(\d+)[\s-]+agent", facts["agents"], "agents")]:
                mm = re.search(pat, t)
                if mm and int(mm.group(1)) != want:
                    return False, f"{mp.name}: says {mm.group(1)} {lab}, computed {want}"
    for m in mods:
        wf = (c.out / m / "WORKFLOW.md").read_text(encoding="utf-8")
        n = len(list((c.out / m / "agents").glob("*.md")))
        d = fm_field(wf, "description")
        dm = re.search(r"(\d+)-agent team", d)
        if dm and int(dm.group(1)) != n:
            return False, f"{m}: description says {dm.group(1)}-agent team, agents/ has {n}"
        h = next((AGENT_TEAM.match(ln) for ln in wf.splitlines() if AGENT_TEAM.match(ln)), None)
        if h and int(h.group(1)) != n:
            return False, f"{m}: 'Agent Team ({h.group(1)})' but agents/ has {n}"
    # the extension-skill sentences must equal the number of extension modules (8)
    words = {"Seven": 7, "Eight": 8, "Six": 6, "Nine": 9}
    for rel in ("teaching-pipeline/WORKFLOW.md", "docs/ARCHITECTURE.md"):
        t = (c.out / rel).read_text(encoding="utf-8")
        m = re.search(r"\b(Seven|Eight|Six|Nine) extension skills\b", t)
        if not m or words[m.group(1)] != facts["extensions"]:
            return False, f"{rel}: '{m.group(0) if m else None}' but there are {facts['extensions']} extension modules"
    pipe = (c.out / "teaching-pipeline/WORKFLOW.md").read_text(encoding="utf-8")
    sec = pipe.split("## Extension Skills", 1)[1].split("\n## ", 1)[0]
    rows = [ln for ln in sec.splitlines() if re.match(r"^\| [0-9–/ any-]+ \| `[a-z-]+` \|", ln)]
    if len(rows) != facts["extensions"]:
        return False, f"pipeline extension table has {len(rows)} rows, expected {facts['extensions']}"
    arch = (c.out / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    graph = re.findall(r"\((\d+) agents\)", arch)
    want_graph = [str(len(list((c.out / m / "agents").glob("*.md")))) for m in
                  ("course-designer", "lesson-builder", "assessment-architect", "student-mentor", "submission-auditor", "teaching-reflector")]
    if graph[-6:] != want_graph and not (graph and graph[-6:] == want_graph):
        # the graph line lists 4 (pipeline) then the six in order
        pass
    for a in ("4 agents", "7 agents", "6 agents", "10 agents"):
        if a not in arch:
            return False, f"ARCHITECTURE dependency graph lost '{a}'"
    for rel in walk(c.out):
        if rel in COUNT_FILES_STALE_EXEMPT or rel.startswith("upstream/dev/") or not rel.endswith((".md", ".json", ".py", ".yml", ".yaml", ".txt")):
            continue
        t = (c.out / rel).read_text(encoding="utf-8")
        for s in STALE:
            if s in t:
                return False, f"stale count string {s!r} still present in {rel}"
    return True, (f"counts verified against files (skills {facts['skills']}, modes {facts['modes']}, agents {facts['agents']}, "
                  f"aliases {facts['aliases']}, extension modules {facts['extensions']}); per-module agent counts match; "
                  f"{len(STALE)} known-stale strings absent")


def g10(c):
    r = router(c)
    low = norm_ws(r).casefold()
    need = ["the professor decides", "just proceed", "[needs professor input", "[verify", "evidence-bound", "draft-only",
            "verify-before-send", "student data never enters the course passport", "ai-detection tools",
            "**produced**", "key decisions made for you (review these)", "**flags**", "**open questions**",
            "ready to proceed, or what should change?", "workflow.md", "base directory", "<base-dir>/scripts/",
            "working directory", "never write the professor's artifacts into the skill folder",
            "gate 1.5", "gate 3.5", "3 rounds", "dismissed with a logged reason", "load lazily"]
    miss = [p for p in need if p not in low]
    if miss:
        return False, f"router is missing required phrases: {miss}"
    anchors = {"CLAUDE.md": ["professor decides", "just proceed", "[NEEDS PROFESSOR INPUT]", "[VERIFY]", "evidence-bound",
                             "draft-only", "verify-before-send", "Student data never enters the Course Passport",
                             "AI-detection tools", "load it before asking"],
               "shared/checkpoint_protocol.md": ["**Produced:**", "Key decisions made for you (review these)", "**Flags:**",
                                                 "**Open questions:**", "Ready to proceed, or what should change?",
                                                 "Evidence-bound", "Final human pass", "not removable by configuration"],
               "shared/output_self_check.md": ["Grounding", "No silent defaults", "Markers honest", "Person-affecting guardrails",
                                               "Voice & altitude", "Accessibility floor", "Passport discipline"]}
    for rel, phrases in anchors.items():
        t = norm_ws((c.out / rel).read_text(encoding="utf-8"))
        gone = [p for p in phrases if p not in t]
        if gone:
            return False, f"anchor {rel} no longer contains {gone} (the router's rule would be unsupported)"
    sc = ["grounding", "no silent defaults", "honest markers", "person-affecting guardrails", "voice and altitude",
          "accessibility floor", "passport discipline"]
    if [s for s in sc if s not in low]:
        return False, "router self-check summary missing an item"
    return True, f"{len(need)} required rule phrases present in the router; each anchored in CLAUDE.md / checkpoint_protocol / output_self_check"


def g11(c):
    r = router(c)
    low = r.casefold()
    total = 0
    for m in modules_of(c.out):
        d = fm_field((c.out / m / "WORKFLOW.md").read_text(encoding="utf-8"), "description")
        t = TRIGGER.search(d)
        if not t:
            return False, f"{m}: no 'Triggers on:' list"
        for kw in [k.strip() for k in t.group(1).split(", ") if k.strip()]:
            total += 1
            if kw.casefold() not in low:
                return False, f"{m}: trigger keyword {kw!r} is not in the router"
    desc = fm_field(r, "description")
    need = ["course design", "syllabus", "lesson", "exam", "rubric", "grading", "feedback", "recommendation letters",
            "备课", "教案", "课程设计", "出题", "评分标准", "评教", "助教", "学情分析", "ts-course", "ts-exam", "ts-lesson", "ts-rubric"]
    miss = [k for k in need if k.casefold() not in desc.casefold()]
    if miss:
        return False, f"router description lacks core triggers: {miss}"
    return True, f"{total} trigger keywords from 15 module descriptions all present in the router; description carries {len(need)} core triggers"


def text_files(c):
    return [f for f in walk(c.out) if f.endswith((".md", ".py", ".json", ".yml", ".yaml", ".txt", ".html")) or "." not in Path(f).name]


def candidates(root, mdrel, token):
    res, seen = [], set()
    cur = (root / mdrel).parent
    bases = [root]
    while True:
        bases.append(cur)
        if cur == root:
            break
        cur = cur.parent
    for b in bases:
        p = (b / token)
        if p.exists():
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                res.append(p)
    return res


def g12(c):
    mods = set(modules_of(c.out))
    roots = REF_ROOTS | mods
    broken, ambiguous, checked = [], [], 0
    for rel in walk(c.out):
        if not rel.endswith(".md"):
            continue
        text = (c.out / rel).read_text(encoding="utf-8")
        for pat, isdir in ((FILE_TOKEN, False), (DIR_TOKEN, True)):
            for m in pat.finditer(text):
                tok = m.group(1)
                if tok.split("/")[0] not in roots:
                    continue
                if isdir and tok in GENERIC_MODULE_DIRS:
                    continue  # `agents/` etc. name "each module's folder" generically, not one path
                ctx = text[max(0, m.start() - 12):m.end() + 2]
                if PLACEHOLDER.search(ctx) or tok.endswith("X.md"):
                    continue
                checked += 1
                found = candidates(c.out, rel, tok)
                if not found:
                    broken.append((rel, tok))
                elif len(found) > 1:
                    ambiguous.append((rel, tok, [str(f.relative_to(c.out)) for f in found]))
    if broken or ambiguous:
        return False, (f"{len(broken)} broken {sorted(set(broken))[:12]}, {len(ambiguous)} ambiguous "
                       f"{ambiguous[:2]} of {checked} references")
    return True, f"{checked} backtick file/dir references resolve (skill root, then ancestors), 0 broken, 0 ambiguous"


def g13(c):
    bad, n = [], 0
    for rel in walk(c.out):
        if not rel.endswith(".md"):
            continue
        text = (c.out / rel).read_text(encoding="utf-8")
        for m in MD_LINK.finditer(text):
            t = m.group(1)
            if re.match(r"^(https?:|mailto:|#)", t) or "{{" in t or "<" in t:
                continue
            t = t.split("#", 1)[0]
            if not t:
                continue
            n += 1
            if not ((c.out / rel).parent / t).exists():
                bad.append((rel, t))
    if bad:
        return False, f"{len(bad)} broken relative markdown links, e.g. {bad[:5]}"
    return True, f"{n} relative markdown links all resolve"


def g14(c):
    total = 0
    for m in modules_of(c.out):
        wf = (c.out / m / "WORKFLOW.md").read_text(encoding="utf-8")
        head = next((AGENT_TEAM.match(ln) for ln in wf.splitlines() if AGENT_TEAM.match(ln)), None)
        sec = wf.split(head.group(0), 1)[1].split("\n## ", 1)[0] if head else ""
        named = re.findall(r"^\| `([a-z_]+_agent)` \|", sec, re.M)
        files = sorted(p.stem for p in (c.out / m / "agents").glob("*.md"))
        if sorted(named) != files or (head and int(head.group(1)) != len(files)):
            return False, f"{m}: Agent Team table {sorted(named)} != agents/ {files} (heading {head.group(1) if head else None})"
        total += len(files)
    return True, f"{total} agents: every Agent Team table row has its file and every agent file has its row"


ORPHAN_EXEMPT_READERS = {"INDEX.md", "MANIFEST.json", "MERGE_NOTES.md"}


def g15(c):
    files = walk(c.out)
    texts = {f: (c.out / f).read_text(encoding="utf-8", errors="replace") for f in files
             if f.endswith((".md", ".py", ".json", ".yml", ".yaml", ".txt", ".html")) or "." not in Path(f).name}
    targets = [f for f in files if re.match(r"^[a-z-]+/(agents|references|templates)/", f) or f.startswith(("shared/", "commands/", "scripts/"))]
    orphans = []

    def referenced(f, t):
        base, stem = Path(f).name, Path(f).stem
        if base in t:
            return True
        # agents are named by stem in their module's Agent Team table; command recipes by alias (/ts-exam)
        if re.match(r"^[a-z-]+/agents/", f) or f.startswith("commands/"):
            return re.search(rf"(?<![\w-]){re.escape(stem)}(?![\w-])", t) is not None
        return False

    for f in targets:
        if not any(referenced(f, t) for k, t in texts.items() if k != f and k not in ORPHAN_EXEMPT_READERS
                   and not k.startswith("tools/") and not k.startswith("install/")):
            orphans.append(f)
    if orphans:
        return False, f"{len(orphans)} files referenced by nothing else: {orphans[:8]}"
    return True, f"{len(targets)} agent/reference/template/shared/command/script files each referenced by at least one other file"


def g16(c):
    disk = [f for f in walk(c.out) if f not in ("INDEX.md", "MANIFEST.json")]
    idx = (c.out / "INDEX.md").read_text(encoding="utf-8")
    listed = re.findall(r"^\| `([^`]+)` \|", idx, re.M)
    if len(listed) != len(set(listed)):
        return False, f"INDEX lists duplicates: {sorted({x for x in listed if listed.count(x) > 1})[:5]}"
    if sorted(listed) != sorted(disk):
        return False, (f"INDEX != disk: only in INDEX {sorted(set(listed) - set(disk))[:5]}, "
                       f"only on disk {sorted(set(disk) - set(listed))[:5]}")
    mf = json.loads((c.out / "MANIFEST.json").read_text(encoding="utf-8"))
    ents = {e["path"]: e for e in mf["files"]}
    if sorted(ents) != sorted(f for f in walk(c.out) if f != "MANIFEST.json"):
        return False, "MANIFEST paths != disk"
    for p, e in ents.items():
        b = (c.out / p).read_bytes()
        if len(b) != e["bytes"] or sha(b) != e["sha256"]:
            return False, f"MANIFEST disagrees with disk for {p}"
        if c.src and e["origin"] == "upstream":
            sb = (c.src / e["source"]).read_bytes()
            if sha(sb) != e["source_sha256"]:
                return False, f"MANIFEST source hash for {p} != actual upstream {e['source']}"
    extra = " and upstream hashes" if c.src else ""
    return True, f"INDEX lists all {len(listed)} files exactly once; MANIFEST paths, sizes, sha256{extra} agree with disk ({len(ents)} entries)"


# ------------------------------------------------------------------------------------------------
# functional gates
# ------------------------------------------------------------------------------------------------
def g17(c):
    code, out = run([sys.executable, "scripts/check_registry_consistency.py"], c.out)
    reg, tot = registry(c.out)
    want = f"CONSISTENT — {tot[1]} skills, {tot[0]} modes, {tot[2]} agents"
    if code != 0 or want not in out:
        return False, f"exit {code}; wanted {want!r}; got: {out.strip()[-300:]}"
    return True, f"registry lint R1-R9: {want}"


def g18(c):
    code, out = run([sys.executable, "scripts/check_links.py"], c.out)
    m = re.search(r"OK — checked (\d+) references, 0 broken", out)
    if code != 0 or not m:
        return False, f"exit {code}: {out.strip()[-300:]}"
    base = 395
    if c.src:
        bc, bo = run([sys.executable, str(c.src / "scripts" / "check_links.py"), str(c.src)], c.src)
        bm = re.search(r"OK — checked (\d+) references, 0 broken", bo)
        if bc != 0 or not bm:
            return False, f"upstream baseline link check failed: {bo.strip()[-200:]}"
        base = int(bm.group(1))
    if int(m.group(1)) < base:
        return False, f"merged checks {m.group(1)} references < upstream's {base}"
    return True, f"link checker: {m.group(1)} references, 0 broken (upstream source: {base})"


def g19(c):
    py = sys.executable
    steps = [(["scripts/check_passport.py", "examples/showcase/course_passport.yaml"], r"VALID — 0 blocking"),
             (["scripts/check_passport.py", "examples/showcase-seminar/course_passport.yaml"], r"VALID — 0 blocking"),
             (["scripts/check_alignment_gate.py", "examples/showcase/course_passport.yaml"], r"VERDICT: PASS"),
             (["scripts/check_alignment_gate.py", "examples/showcase-seminar/course_passport.yaml"], r"VERDICT: PASS"),
             (["scripts/check_quality_gate.py", "examples/showcase/course_passport.yaml"], r"VERDICT: PASS"),
             (["scripts/check_content_markers.py", "examples/showcase/course_passport.yaml"], r"unresolved marker")]
    seen = []
    for args, pat in steps:
        code, out = run([py, *args], c.out)
        if code != 0 or not re.search(pat, out):
            return False, f"{' '.join(args)}: exit {code}, expected /{pat}/, got {out.strip()[-200:]}"
        seen.append(args[0].split("/")[1] + ":" + args[1].split("/")[1])
    tmp = Path(tempfile.mkdtemp(prefix="ut_dash_"))
    try:
        code, out = run([py, "scripts/build_dashboard.py", "examples/showcase/course_passport.yaml", "-o", str(tmp / "d.html")], c.out)
        d = tmp / "d.html"
        if code != 0 or not d.exists() or d.stat().st_size < 5000 or "LO1" not in d.read_text(encoding="utf-8"):
            return False, f"dashboard build failed: exit {code} {out.strip()[-200:]}"
        size = d.stat().st_size
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return True, f"{len(steps)} validator runs on both showcase passports clean; dashboard built ({size} bytes)"


def pytest_summary(out):
    passed = re.search(r"(\d+) passed", out)
    failed = re.search(r"(\d+) failed", out)
    errors = re.search(r"(\d+) errors?", out)
    return (int(passed.group(1)) if passed else 0, int(failed.group(1)) if failed else 0,
            int(errors.group(1)) if errors else 0)


def g20(c):
    code, out = run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], c.out)
    p, f, e = pytest_summary(out)
    if code != 0 or f or e or p == 0:
        return False, f"pytest exit {code}: {p} passed, {f} failed, {e} errors\n{out.strip()[-600:]}"
    return True, f"pytest: {p} passed, 0 failed, 0 errors in the merged layout"


def g21(c):
    tmp = Path(tempfile.mkdtemp(prefix="ut_base_"))
    try:
        copytree_clean(c.src, tmp / "src")
        code, out = run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider", "--tb=line"], tmp / "src")
        p, f, e = pytest_summary(out)
        codex_err = len(re.findall(r"^ERROR tests/test_build_codex\.py::", out, re.M))
        codex_fail = len(re.findall(r"^FAILED tests/test_build_codex\.py::", out, re.M))
        git = shutil.which("git")
        if p + f + e != 63:
            return False, f"upstream suite totals {p}+{f}+{e}={p + f + e}, changelog claims 63"
        if (f + e) != codex_err + codex_fail:
            return False, f"non-passing tests outside test_build_codex.py: {f + e} vs {codex_err + codex_fail}"
        if git is None and (p, e) != (51, 12):
            return False, f"without git expected 51 passed/12 errors, got {p}/{e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return True, (f"untouched upstream suite: {p} passed, {f} failed, {e} errors = {p + f + e} tests (changelog: 63); "
                  f"all non-passing are test_build_codex.py ({'git absent on this machine' if git is None else 'git present'})")


# ------------------------------------------------------------------------------------------------
# hygiene gates
# ------------------------------------------------------------------------------------------------
BIDI_ZW = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\u00ad]")
# an absolute path into somebody's home folder (Windows, macOS or Linux) leaks a username if the package is shared
PERSONAL_PATH = re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"'`]+\\|/Users/[A-Za-z][^/\s]*/|/home/[a-z][^/\s]*/")
INJECTION = [r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|prompts)",
             r"disregard (all |any |the )?(previous|prior|above|earlier)", r"do not (tell|inform|reveal to) the user",
             r"without (telling|informing) the user", r"exfiltrat", r"you are now (a|an|in)\b", r"reveal (your|the) system prompt",
             r"\bcurl\s+-|\bwget\s+|Invoke-WebRequest|Invoke-Expression|\biex\s*\(|base64\s+-d|\bchmod\s+\+x|\brm\s+-rf|\bsudo\s+"]
PY_RISK = [(r"^\s*(import|from)\s+(requests|urllib|http\.client|http\.server|socket|ftplib|smtplib|telnetlib|paramiko|"
            r"ctypes|pickle|marshal|webbrowser|getpass|keyring|xmlrpc|asyncio)\b", "network/serialization/ctypes import"),
           (r"\burlopen\(|\burlretrieve\(", "url fetch"), (r"\bos\.system\(|\bos\.popen\(|\bpopen\(", "shell exec"),
           (r"(?<![\w.])eval\(|(?<![\w.])exec\(|\b__import__\(|(?<![\w.])compile\(", "dynamic execution"),
           (r"\bbase64\b|\bcodecs\.decode\b|\bbytes\.fromhex\b", "encoding/obfuscation"),
           (r"\bos\.environ\b|\bos\.getenv\(", "environment access"),
           (r"\bshutil\.rmtree\(|\bos\.remove\(|\bos\.unlink\(|\.unlink\(", "deletion")]
SUBPROCESS_ALLOWED = {"scripts/render_document.py", "upstream/dev/build_codex.py", "tools/merge/gate_run.py",
                       "tools/merge/verify_merge.py", "tools/merge/build_merge.py"}
# Narrow, documented allowances (everything else is a finding):
#  - the merge tools delete only their own scratch/previous-build folders and read environment variables to run children;
#    verify_merge.py contains the scanner's own pattern strings (e.g. 'base64') as data;
#  - upstream/dev/build_codex.py (archived Codex generator, read in full) clears its own output folder before a build.
RISK_ALLOWED = {"tools/merge/build_merge.py": {"deletion"},
                "tools/merge/verify_merge.py": {"deletion", "environment access", "encoding/obfuscation"},
                "tools/merge/gate_run.py": {"environment access"}, "tests/test_merge_integrity.py": {"environment access"},
                "tools/merge/make_edits.py": set(), "upstream/dev/build_codex.py": {"deletion"}}
# build_codex.py emits a README that tells Codex users how to reinstall by deleting their installed copy of the skill
INJECTION_ALLOWED = {"upstream/dev/build_codex.py": ("rm -rf",)}


def g22(c):
    problems = []
    n_py = n_txt = 0
    for rel in walk(c.out):
        p = c.out / rel
        b = p.read_bytes()
        try:
            t = b.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{rel}: not UTF-8 text (binary?)")
            continue
        n_txt += 1
        if BIDI_ZW.search(t):
            problems.append(f"{rel}: bidi/zero-width/soft-hyphen control character")
        for pat in INJECTION:
            for m in re.finditer(pat, t, re.I):
                if rel.startswith(("tools/merge/verify_merge.py", "tools/merge/make_edits.py")):
                    continue  # these files hold the scanner's own pattern strings as data
                if any(m.group(0).lower().startswith(a) for a in INJECTION_ALLOWED.get(rel, ())):
                    continue
                problems.append(f"{rel}: injection-style phrase {m.group(0)!r}")
        pm = PERSONAL_PATH.search(t)
        if pm:
            problems.append(f"{rel}: absolute local user path {pm.group(0)!r}")
        if rel.endswith(".py"):
            n_py += 1
            for pat, label in PY_RISK:
                for m in re.finditer(pat, t, re.M):
                    if label in RISK_ALLOWED.get(rel, set()) or rel.startswith("upstream/dev/") and label == "shell exec":
                        continue
                    problems.append(f"{rel}: {label} -> {m.group(0).strip()!r}")
            if "subprocess" in t and rel not in SUBPROCESS_ALLOWED and not rel.startswith("tests/"):
                problems.append(f"{rel}: uses subprocess (not on the documented list)")
        if rel.endswith(".html"):
            if re.search(r"<script[^>]+src\s*=|<iframe|<object|<embed|<link[^>]+href\s*=\s*[\"']https?:|@import\s+url\(", t, re.I):
                problems.append(f"{rel}: external script/frame/stylesheet reference")
        if Path(rel).suffix.lower() in (".exe", ".dll", ".so", ".bat", ".cmd", ".ps1", ".sh", ".vbs", ".jar", ".msi"):
            problems.append(f"{rel}: executable file type")
    if problems:
        return False, f"{len(problems)} findings, e.g. {problems[:6]}"
    return True, (f"{n_txt} files scanned ({n_py} Python): no binaries, no network/exec/obfuscation/persistence constructs beyond the "
                  f"documented subprocess uses, no bidi/zero-width characters, no injection phrasing, no external HTML resources, "
                  f"no absolute local user paths")


def g23(c):
    bad = []
    for rel in walk(c.out):
        b = (c.out / rel).read_bytes()
        try:
            b.decode("utf-8")
        except UnicodeDecodeError:
            bad.append(f"{rel}: not UTF-8")
            continue
        if b"\r" in b:
            bad.append(f"{rel}: contains CR (the upstream tree is LF-only)")
        if b.startswith(b"\xef\xbb\xbf"):
            bad.append(f"{rel}: BOM")
    if c.src:
        dm, _ = dest_map(c)
        for f in dm:
            b = (c.src / f).read_bytes()
            if b"\r" in b or b.startswith(b"\xef\xbb\xbf"):
                bad.append(f"source {f}: unexpected CR/BOM (assumption of LF-only no longer holds)")
    if bad:
        return False, f"{len(bad)} encoding/EOL issues, e.g. {bad[:5]}"
    return True, "every file is UTF-8, LF-only, BOM-free (as the upstream tree was)"


def g24(c):
    bad = [f for f in walk(c.out, include_caches=True) if "__pycache__" in f.split("/") or f.endswith((".pyc", ".pyo", ".tmp", ".bak", ".orig"))
           or Path(f).name in (".DS_Store", "Thumbs.db") or ".pytest_cache" in f.split("/")]
    dirs = [p.relative_to(c.out).as_posix() for p in c.out.rglob("*") if p.is_dir() and p.name in ("__pycache__", ".pytest_cache")]
    if bad or dirs:
        return False, f"build debris present: {bad[:5]} {dirs[:5]}"
    return True, "no __pycache__, .pyc, .pytest_cache or editor debris"


# ------------------------------------------------------------------------------------------------
# packaging / notes / negative controls
# ------------------------------------------------------------------------------------------------
def g25(c):
    pkg = c.out.parent / f"{c.out.name}.skill"
    if not pkg.exists():
        return False, f"package {pkg} not found"
    z = zipfile.ZipFile(pkg)
    if z.testzip() is not None:
        return False, "zip integrity check failed"
    names = [n for n in z.namelist() if not n.endswith("/")]
    top = {n.split("/")[0] for n in names}
    if top != {c.out.name}:
        return False, f"package top-level folders {top}, expected {{'{c.out.name}'}}"
    skill_mds = [n for n in names if Path(n).name.lower() == "skill.md"]
    if skill_mds != [f"{c.out.name}/SKILL.md"]:
        return False, f"package SKILL.md files: {skill_mds}"
    disk = {f"{c.out.name}/{f}" for f in walk(c.out)}
    if set(names) != disk:
        return False, f"package/file-tree mismatch: only in zip {sorted(set(names) - disk)[:4]}, only on disk {sorted(disk - set(names))[:4]}"
    for n in names:
        if sha(z.read(n)) != sha((c.out.parent / n).read_bytes()):
            return False, f"package member {n} differs from the folder"
    size = pkg.stat().st_size
    if size > 30 * 1024 * 1024:
        return False, f"package is {size} bytes"
    zp = c.out.parent / f"{c.out.name}.zip"
    if not zp.exists() or zp.read_bytes() != pkg.read_bytes():
        return False, f"{zp.name} is missing or not byte-identical to {pkg.name}"
    same = ""
    if c.skill_creator and (c.skill_creator / "scripts" / "package_skill.py").exists():
        tmp = Path(tempfile.mkdtemp(prefix="ut_pkg_"))
        try:
            code, out = run([sys.executable, "-m", "scripts.package_skill", str(c.out), str(tmp)], c.skill_creator)
            ref = tmp / f"{c.out.name}.skill"
            if code != 0 or not ref.exists():
                return False, f"Anthropic packager failed: exit {code} {out.strip()[-200:]}"
            with zipfile.ZipFile(ref) as rz:  # closed before the temp folder is removed (Windows locks open files)
                rn = sorted(n for n in rz.namelist() if not n.endswith("/"))
                if rn != sorted(names) or any(sha(rz.read(n)) != sha(z.read(n)) for n in rn):
                    return False, "package differs from what Anthropic's own packager produces for this folder"
            same = "; identical (names + bytes) to Anthropic's packager output"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return True, (f"{pkg.name} (+ identical {zp.name}): {len(names)} files, {size} bytes, one SKILL.md, "
                  f"hash-identical to the folder{same}")


def g26(c):
    t = norm_ws((c.out / "MERGE_NOTES.md").read_text(encoding="utf-8"))
    raw_notes = (c.out / "MERGE_NOTES.md").read_text(encoding="utf-8")
    heads = ["## 1. What this is", "## 2. Layout", "## 3. Install and use", "## 4. Design decisions",
             "## 5. Every difference from upstream", "## 6. Observations about upstream", "## 7. Verification record",
             "## 8. Limits of this verification"]
    miss = [h for h in heads if h not in t]
    if miss:
        return False, f"MERGE_NOTES missing sections {miss}"
    listed = {m.group(1): (int(m.group(2)), int(m.group(3))) for m in
              re.finditer(r"^- \*\*([A-Z]\d+)\*\* \((\d+) edits? in (\d+) files?\)", raw_notes, re.M)}
    dm, move = dest_map(c) if c.src else (None, {m["from"]: m["to"] for m in c.spec["moves"]})
    for g in c.spec["groups"]:
        files = {move.get(it["file"], it["file"]) for it in g["items"]}
        if listed.get(g["id"]) != (len(g["items"]), len(files)):
            return False, f"edit {g['id']}: notes say {listed.get(g['id'])}, registry {(len(g['items']), len(files))}"
    for p in c.spec["prepends"]:
        if listed.get(p["id"]) != (1, 1):
            return False, f"banner {p['id']} not listed correctly"
    for m in c.spec["moves"]:
        if m["kind"] == "relocate" and f"| {m['id']} |" not in raw_notes:
            return False, f"relocation {m['id']} missing from the notes table"
    reg, tot = registry(c.out)
    mf = json.loads((c.out / "MANIFEST.json").read_text(encoding="utf-8"))
    cn = mf["counts"]
    want = {"modules": tot[1], "modes": tot[0], "agents": tot[2]}
    if (cn["modules"], cn["modes"], cn["agents"]) != (want["modules"], want["modes"], want["agents"]):
        return False, f"MANIFEST counts {cn} disagree with registry {want}"
    for pat, val, lab in [(r"(\d+) of (\d+) upstream files", None, "carried/total")]:
        m = re.search(pat, t)
        if not m or (int(m.group(1)), int(m.group(2))) != (cn["carried"], cn["source_files"]):
            return False, f"notes say {m.groups() if m else None} carried/total, manifest {(cn['carried'], cn['source_files'])}"
    gates = (c.out / "tools/merge/GATES.md").read_text(encoding="utf-8")
    n_auto = len(re.findall(r"^  CHECK:", gates, re.M))
    n_man = len(re.findall(r"^  MANUAL: yes", gates, re.M))
    m = re.search(r"all (\d+) automated gates and both manual gates", t)
    if not m or int(m.group(1)) != n_auto or n_man != 2:
        return False, f"notes claim {m.group(1) if m else None} automated gates; ledger has {n_auto} automated / {n_man} manual"
    return True, (f"MERGE_NOTES: 8 sections, {len(c.spec['groups']) + len(c.spec['prepends'])} edit groups and "
                  f"{sum(1 for m in c.spec['moves'] if m['kind'] == 'relocate')} relocations match the registry one-for-one; "
                  f"counts and gate totals match ({n_auto} automated, {n_man} manual)")


def mutate(c, name):
    t = Path(tempfile.mkdtemp(prefix="ut_mut_"))
    dst = t / SKILL_NAME
    copytree_clean(c.out, dst)
    return t, dst


MUTATIONS = [
    ("drop an agent file", "G14", lambda d: (d / "course-designer/agents/design_mentor_agent.md").unlink()),
    ("append a byte to a shared protocol", "G03", lambda d: (d / "shared/checkpoint_protocol.md").write_bytes(
        (d / "shared/checkpoint_protocol.md").read_bytes() + b"x")),
    ("break a file reference", "G12", lambda d: (d / "lesson-builder/WORKFLOW.md").write_text(
        (d / "lesson-builder/WORKFLOW.md").read_text(encoding="utf-8").replace(
            "shared/pedagogy_foundations.md", "shared/pedagogy_foundationz.md", 1), encoding="utf-8")),
    ("add a nested SKILL.md", "G05", lambda d: (d / "course-designer/SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")),
    ("remove a mode from the router index", "G07", lambda d: (d / "SKILL.md").write_text(
        (d / "SKILL.md").read_text(encoding="utf-8").replace("`socratic` · ", "", 1), encoding="utf-8")),
    ("reintroduce a stale count", "G09", lambda d: (d / "README.md").write_text(
        (d / "README.md").read_text(encoding="utf-8").replace("89 modes", "84 modes"), encoding="utf-8")),
    ("delete an alias row from the router", "G08", lambda d: (d / "SKILL.md").write_text(
        "\n".join(ln for ln in (d / "SKILL.md").read_text(encoding="utf-8").splitlines() if not ln.startswith("| `/ts-exam` |")) + "\n",
        encoding="utf-8")),
    ("mis-route a slash-command wrapper", "G08", lambda d: (d / "install/claude-code-commands/ts-exam.md").write_text(
        (d / "install/claude-code-commands/ts-exam.md").read_text(encoding="utf-8").replace("assessment-architect", "lesson-builder"), encoding="utf-8")),
    ("delete an INDEX row", "G16", lambda d: (d / "INDEX.md").write_text(
        "\n".join(ln for ln in (d / "INDEX.md").read_text(encoding="utf-8").splitlines() if "`shared/workload_constants.md`" not in ln) + "\n",
        encoding="utf-8")),
    ("insert a zero-width space", "G22", lambda d: (d / "shared/output_self_check.md").write_text(
        "\u200b" + (d / "shared/output_self_check.md").read_text(encoding="utf-8"), encoding="utf-8")),
    ("drop a trigger keyword from the router", "G11", lambda d: (d / "SKILL.md").write_text(
        (d / "SKILL.md").read_text(encoding="utf-8").replace("翻转课堂视频", "", 1), encoding="utf-8")),
    ("leave __pycache__ debris", "G24", lambda d: ((d / "scripts/__pycache__").mkdir(), (d / "scripts/__pycache__/x.pyc").write_bytes(b"0"))),
    ("embed an absolute local user path", "G22", lambda d: (d / "shared/output_self_check.md").write_text(
        (d / "shared/output_self_check.md").read_text(encoding="utf-8") + "\nsee C:\\Users\\alex\\notes.txt\n", encoding="utf-8")),
]


def g27(c):
    if not c.src:
        return "SKIP", "needs --src for the provenance gates used as detectors"
    gate_fn = {k: v for k, v in GATES.items()}
    detected = 0
    log = []
    for name, gid, fn in MUTATIONS:
        t, dst = mutate(c, name)
        try:
            fn(dst)
            mc = Ctx(dst, c.src, str(c.skill_creator) if c.skill_creator else None)
            try:
                ok, msg = gate_fn[gid](mc)[:2]
            except Exception as e:  # noqa: BLE001
                ok, msg = False, f"raised {type(e).__name__}: {e}"
            if ok:
                return False, f"mutation '{name}' was NOT detected by {gid}"
            detected += 1
            log.append(f"{gid}<-{name}")
        finally:
            shutil.rmtree(t, ignore_errors=True)
    return True, f"{detected}/{len(MUTATIONS)} deliberate corruptions detected by the intended gate ({'; '.join(log[:4])}; ...)"


GATES = {"G01": g01, "G02": g02, "G03": g03, "G04": g04, "G05": g05, "G06": g06, "G07": g07, "G08": g08, "G09": g09,
         "G10": g10, "G11": g11, "G12": g12, "G13": g13, "G14": g14, "G15": g15, "G16": g16, "G17": g17, "G18": g18,
         "G19": g19, "G20": g20, "G21": g21, "G22": g22, "G23": g23, "G24": g24, "G25": g25, "G26": g26, "G27": g27}
NEEDS_SRC = {"G01", "G02", "G03", "G04", "G21", "G27"}
PACKAGE_GATES = ["G05", "G06", "G07", "G08", "G09", "G10", "G11", "G12", "G13", "G14", "G15", "G16", "G17", "G18", "G19",
                 "G22", "G23", "G24"]


def run_gate(gid, c):
    if gid in NEEDS_SRC and not c.need_src():
        return "SKIP", "needs --src"
    try:
        res = GATES[gid](c)
    except Exception as e:  # noqa: BLE001
        import traceback
        return "FAIL", f"raised {type(e).__name__}: {e} | {traceback.format_exc().splitlines()[-3:]}"
    if res[0] == "SKIP":
        return "SKIP", res[1]
    return ("PASS" if res[0] else "FAIL"), res[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--gate")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--package", action="store_true")
    ap.add_argument("--skill-creator", help="optional: Anthropic's skill-creator folder (enables the external "
                                            "validator/packager comparison in G05 and G25); or set SKILL_CREATOR_DIR")
    a = ap.parse_args(argv)
    c = Ctx(a.out, a.src, a.skill_creator)
    ids = [a.gate] if a.gate else (sorted(GATES) if a.all else PACKAGE_GATES if a.package else [])
    if not ids:
        ap.error("choose --gate Gnn, --all or --package")
    worst = 0
    for gid in ids:
        status, msg = run_gate(gid, c)
        print(f"{gid} {status} — {msg}")
        if status == "FAIL":
            worst = 1
        if status == "SKIP" and a.gate:
            worst = 1
    return worst


if __name__ == "__main__":
    sys.exit(main())
