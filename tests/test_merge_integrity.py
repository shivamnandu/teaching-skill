"""Merge-integrity tests: the source-independent gates of tools/merge/verify_merge.py, as pytest.

They prove the skill is internally consistent without needing the upstream folder: exactly one
SKILL.md with valid frontmatter, the router agrees with MODE_REGISTRY.md / commands/ / each
module's Modes table, every stated count is true, every reference and link resolves, INDEX.md and
MANIFEST.json agree with the files on disk, and nothing suspicious is shipped. Byte-fidelity
against the untouched upstream tree (gates G01-G04, G21, G27) needs that tree:

    python tools/merge/verify_merge.py --src <upstream folder> --out . --all
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_VM = ROOT / "tools" / "merge" / "verify_merge.py"

_spec = importlib.util.spec_from_file_location("verify_merge", _VM)
vm = importlib.util.module_from_spec(_spec)
sys.modules["verify_merge"] = vm
_spec.loader.exec_module(vm)

CTX = vm.Ctx(ROOT)

# the subprocess gates (registry lint, link checker, validators, pytest itself) are already covered
# by the upstream tests in this folder; the cache-debris gate (G24) is a build-time check only
PACKAGE_GATES = ["G05", "G06", "G07", "G08", "G09", "G10", "G11", "G12", "G13", "G14", "G15",
                 "G16", "G22", "G23", "G26"]


@pytest.mark.parametrize("gate", PACKAGE_GATES)
def test_package_gate(gate):
    status, message = vm.run_gate(gate, CTX)
    assert status == "PASS", f"{gate}: {message}"


def test_exactly_one_skill_md_and_it_is_the_router():
    found = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*")
             if p.is_file() and p.name.lower() == "skill.md" and "__pycache__" not in p.parts]
    assert found == ["SKILL.md"], found


def test_every_module_entry_is_workflow_md():
    modules = vm.modules_of(ROOT)
    assert len(modules) == 15
    for m in modules:
        assert (ROOT / m / "WORKFLOW.md").exists()
        assert not (ROOT / m / "SKILL.md").exists()
