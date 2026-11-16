"""Tests for tools/check.py. Run: python3 -m unittest discover -s tools"""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

import check

DATA = Path(__file__).resolve().parent / "testdata"
DECISIONS = DATA / "decisions"


def errors(name: str) -> list[str]:
    checker = check.Checker(check.load(DATA / name), name, DECISIONS)
    return checker.run()


def run_main(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = check.main(list(argv))
    return code, out.getvalue()


def has(errs: list[str], prefix: str, fragment: str) -> bool:
    return any(e.startswith(prefix + ":") and fragment in e for e in errs)


class FixtureTests(unittest.TestCase):
    def test_valid(self) -> None:
        self.assertEqual(errors("valid.yaml"), [])

    def test_duplicate_id(self) -> None:
        self.assertTrue(has(errors("duplicate_id.yaml"), "T-002", "duplicate id"))

    def test_next_ids_behind(self) -> None:
        errs = errors("next_ids_behind.yaml")
        self.assertTrue(has(errs, "next_ids", "task T-003 is not ahead of used T-003"))
        self.assertTrue(has(errs, "next_ids", "adr ADR-031 is not ahead of used ADR-031"))

    def test_blocked_by_cycle(self) -> None:
        errs = errors("blocked_by_cycle.yaml")
        self.assertEqual(sum("blocked_by cycle" in e for e in errs), 1, errs)

    def test_unknown_stage(self) -> None:
        self.assertTrue(has(errors("unknown_stage.yaml"), "T-002", "stage 'S9' does not exist"))

    def test_bad_date(self) -> None:
        errs = errors("bad_date.yaml")
        self.assertTrue(has(errs, "bad_date.yaml", "updated '2026-13-40'"))
        self.assertTrue(has(errs, "T-002", "due '2026-11-17'"))

    def test_missing_merged_prs(self) -> None:
        self.assertTrue(has(errors("missing_merged_prs.yaml"), "log[0]", "missing key merged_prs"))

    def test_branch_task_mismatch(self) -> None:
        self.assertTrue(has(errors("branch_mismatch.yaml"), "T-002", "belongs to T-001"))

    def test_unhashable_values(self) -> None:
        errs = errors("unhashable_values.yaml")
        self.assertTrue(has(errs, "T-002", "kind ['doc', 'code']"))
        self.assertTrue(has(errs, "T-002", "blocked_by item {'id': 'T-003'} is not an id"))
        code, _ = run_main("--file", str(DATA / "unhashable_values.yaml"), "--decisions", str(DECISIONS))
        self.assertEqual(code, 1)


class GitBranchTests(unittest.TestCase):
    def checker(self) -> check.Checker:
        c = check.Checker(check.load(DATA / "valid.yaml"), "valid.yaml", DECISIONS)
        c.run()
        return c

    def test_known_branches_pass(self) -> None:
        branches = ["main", "origin/main", "dev/T-002-second-thing", "origin/dev/T-001-first-thing"]
        self.assertEqual(self.checker().check_branches(branches), [])

    def test_unknown_and_future_branches(self) -> None:
        errs = self.checker().check_branches(["origin/dev/T-007-x", "dev/T-004-next"])
        self.assertTrue(has(errs, "origin/dev/T-007-x", "no task T-007"))
        self.assertTrue(has(errs, "dev/T-004-next", "not below next_ids.task"))


class MainTests(unittest.TestCase):
    def test_exit_codes(self) -> None:
        code, out = run_main("--file", str(DATA / "valid.yaml"), "--decisions", str(DECISIONS))
        self.assertEqual((code, out), (0, ""))
        code, out = run_main("--file", str(DATA / "duplicate_id.yaml"), "--decisions", str(DECISIONS))
        self.assertEqual(code, 1)
        self.assertIn("T-002: duplicate id", out)
        code, _ = run_main("--file", str(DATA / "missing.yaml"))
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
