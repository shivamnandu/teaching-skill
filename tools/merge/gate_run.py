#!/usr/bin/env python3
"""Minimal ledger runner with unlazy's counting rule (stand-in for the absent gate-check.mjs).

A runnable gate is MET only when its process exits 0 AND its EXPECT regex matches the
combined stdout+stderr. Evidence (definition digest, exit code, output fingerprint, output
head, timestamp) is written to GATES.evidence.json next to the ledger. Manual gates are
met only when a non-pending EVIDENCE line is recorded. Abandoned gates (ABANDON: id reason)
are terminal but never count as met.

SECURITY: every CHECK line is run through the shell (shell=True) with your user's permissions. Read a ledger
before running it and never run one from a source you do not trust. The copy shipped as tools/merge/GATES.md
uses placeholder paths: it documents how the merge was verified and is not runnable as-is.

Usage:
  gate_run.py [--ledger GATES.md] [--only G01,G02] [--mark] [--lint] [--timeout 900]
Exit: 0 = every gate met (manual gates need evidence) · 1 = unmet/abandoned/pending · 2 = error
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_LEDGER = HERE.parent / "GATES.md"

GATE_LINE = re.compile(r"^- \[( |x)\] ([A-Z]\d+): (.+)$")
VAR_LINE = re.compile(r"^VAR (\w+)\s*=\s*(.+?)\s*$")
FIELD = re.compile(r"^\s+(CHECK|EXPECT|MANUAL|EVIDENCE|CWD):\s*(.*)$")
ABANDON = re.compile(r"^ABANDON:\s*([A-Z]\d+)\s+(\S.*)$")


def parse(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    variables, gates, abandoned, cur = {}, [], {}, None
    for i, line in enumerate(lines):
        m = VAR_LINE.match(line)
        if m:
            variables[m.group(1)] = m.group(2)
            continue
        m = ABANDON.match(line)
        if m:
            abandoned[m.group(1)] = m.group(2)
            continue
        m = GATE_LINE.match(line)
        if m:
            cur = {"id": m.group(2), "title": m.group(3), "checked": m.group(1) == "x",
                   "line": i, "fields": {}}
            gates.append(cur)
            continue
        m = FIELD.match(line)
        if m and cur is not None:
            cur["fields"][m.group(1)] = m.group(2)
            continue
        if line.strip() and not line.startswith(" ") and not line.startswith("-"):
            cur = None  # a non-indented paragraph or heading ends the current gate block
    return variables, gates, abandoned


def expand(text, variables):
    def sub(m):
        key = m.group(1)
        if key not in variables:
            raise KeyError(f"undefined variable ${{{key}}}")
        return variables[key]
    return re.sub(r"\$\{(\w+)\}", sub, text)


def digest(gate):
    f = gate["fields"]
    blob = "\n".join([f.get("CHECK", ""), f.get("EXPECT", ""), f.get("CWD", "")])
    return "v1:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def lint(path):
    variables, gates, abandoned = parse(path)
    problems = []
    if not gates:
        problems.append("ledger has no gates")
    seen = set()
    runnable = manual = 0
    for g in gates:
        gid, f = g["id"], g["fields"]
        if gid in seen:
            problems.append(f"{gid}: duplicate id")
        seen.add(gid)
        if f.get("MANUAL", "").lower() == "yes":
            manual += 1
            if "EVIDENCE" not in f:
                problems.append(f"{gid}: manual gate has no EVIDENCE line")
            continue
        runnable += 1
        if not f.get("CHECK"):
            problems.append(f"{gid}: runnable gate has no CHECK")
        exp = f.get("EXPECT", "")
        if not exp:
            problems.append(f"{gid}: runnable gate has no EXPECT")
        elif exp.strip() in {".*", ".+", "^", "$", "PASS", "OK"}:
            problems.append(f"{gid}: EXPECT '{exp}' is trivially satisfiable")
        elif gid != "G28" and gid not in exp:
            problems.append(f"{gid}: EXPECT does not name its own gate id (a stray PASS from "
                            f"another gate could satisfy it)")
        else:
            try:
                re.compile(exp)
            except re.error as e:
                problems.append(f"{gid}: EXPECT is not a valid regex ({e})")
        if f.get("CHECK"):
            try:
                expand(f["CHECK"], variables)
            except KeyError as e:
                problems.append(f"{gid}: {e}")
    for aid in abandoned:
        if aid not in seen:
            problems.append(f"ABANDON references unknown gate {aid}")
    if problems:
        print("LEDGER LINT FAIL — " + "; ".join(problems))
        return 1
    print(f"LEDGER LINT PASS — {len(gates)} gates ({runnable} runnable, {manual} manual), "
          f"{len(abandoned)} abandoned")
    return 0


def run_gate(gate, variables, timeout):
    f = gate["fields"]
    cmd = expand(f["CHECK"], variables)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env,
                           cwd=f.get("CWD") or None)
        out = (r.stdout or "") + (r.stderr or "")
        code = r.returncode
    except subprocess.TimeoutExpired as e:
        out, code = f"TIMEOUT after {timeout}s\n{(e.stdout or b'')!r}", 124
    matched = bool(re.search(f["EXPECT"], out, re.MULTILINE))
    return {"id": gate["id"], "title": gate["title"], "command": cmd, "exit": code,
            "matched": matched, "met": code == 0 and matched,
            "definition_digest": digest(gate),
            "output_sha256": hashlib.sha256(out.encode("utf-8")).hexdigest(),
            "output_head": out[:1600], "seconds": round(time.time() - t0, 1),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ap.add_argument("--only", default="")
    ap.add_argument("--mark", action="store_true", help="tick [x] on met gates in the ledger")
    ap.add_argument("--lint", action="store_true")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args(argv)
    if args.lint:
        return lint(args.ledger)

    try:
        variables, gates, abandoned = parse(args.ledger)
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    ev_path = Path(args.ledger).with_name("GATES.evidence.json")
    evidence = json.loads(ev_path.read_text(encoding="utf-8")) if ev_path.exists() else {}

    print("Commands below were authored for this ledger (approved by the author, not inherited).")
    for g in gates:
        gid, f = g["id"], g["fields"]
        if only and gid not in only:
            continue
        if gid in abandoned:
            print(f"{gid}  ABANDONED  {abandoned[gid]}")
            continue
        if f.get("MANUAL", "").lower() == "yes":
            continue
        print(f"\n>>> {gid}: {expand(f['CHECK'], variables)}")
        res = run_gate(g, variables, args.timeout)
        evidence[gid] = res
        first = next((ln for ln in res["output_head"].splitlines() if ln.startswith(gid)), "")
        print(f"    exit={res['exit']} matched={res['matched']} -> "
              f"{'MET' if res['met'] else 'UNMET'} ({res['seconds']}s)  {first[:200]}")
    ev_path.write_text(json.dumps(evidence, indent=1, ensure_ascii=False), encoding="utf-8")

    # tally (uses stored evidence so --only runs still report the whole ledger)
    met = unmet = pending = 0
    rows = []
    for g in gates:
        gid, f = g["id"], g["fields"]
        if gid in abandoned:
            state = "ABANDONED"
        elif f.get("MANUAL", "").lower() == "yes":
            ev = f.get("EVIDENCE", "").strip()
            state = "MET" if ev and ev != "(pending)" else "PENDING"
        else:
            e = evidence.get(gid)
            if e and e.get("definition_digest") == digest(g) and e.get("met"):
                state = "MET"
            elif e and e.get("definition_digest") == digest(g):
                state = "UNMET"
            else:
                state = "NOT-RUN"
        rows.append((gid, state))
    for gid, state in rows:
        if state == "MET":
            met += 1
        elif state == "ABANDONED":
            pass
        elif state == "PENDING" or state == "NOT-RUN":
            pending += 1
        else:
            unmet += 1
    ab = sum(1 for _, s in rows if s == "ABANDONED")
    print("\n" + " ".join(f"{gid}:{s}" for gid, s in rows))
    print(f"\nTALLY  met={met}  unmet={unmet}  not-run/pending={pending}  abandoned={ab}  "
          f"total={len(rows)}")

    if args.mark:
        text = Path(args.ledger).read_text(encoding="utf-8").splitlines()
        done = {gid for gid, s in rows if s == "MET"}
        for g in gates:
            ln = text[g["line"]]
            text[g["line"]] = re.sub(r"^- \[[ x]\]", "- [x]" if g["id"] in done else "- [ ]", ln)
        Path(args.ledger).write_text("\n".join(text) + "\n", encoding="utf-8", newline="\n")
    return 0 if (unmet == 0 and pending == 0 and ab == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
