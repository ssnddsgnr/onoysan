#!/usr/bin/env python3
"""Validate docs/dev-state.yaml.

ref: workflow#appendix-h, workflow#5

Usage:
    python3 tools/check.py [--git] [--file PATH] [--decisions DIR]

Exit codes: 0 clean, 1 errors found, 2 file missing or unreadable.
Errors are printed one per line as "<path-or-id>: <message>".
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the environment
    print("tools/check.py: PyYAML is required (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "docs" / "dev-state.yaml"
DEFAULT_DECISIONS = ROOT / "docs" / "decisions"

TOP_KEYS = (
    "id", "role", "version", "updated", "goal", "focus", "waiting_on_owner",
    "week_plan", "next_ids", "stages", "tasks", "open_questions", "approvals", "log",
)
GOAL_KEYS = ("id", "name", "why", "scope", "status")
STAGE_KEYS = ("id", "name", "point", "exit_criterion", "status")
TASK_KEYS = (
    "id", "name", "stage", "kind", "priority", "urgency", "status", "assignee",
    "blocked_by", "due", "branch", "pr", "next_step",
)
QUESTION_KEYS = ("id", "question", "blocks", "asked", "answer")
APPROVAL_KEYS = ("date", "word", "subject", "adr")
LOG_KEYS = ("date", "session", "merged_prs", "summary")
MERGED_PR_KEYS = ("number", "title", "task")

GOAL_STATUSES = {"Not started", "In progress", "Paused", "Done"}
STAGE_STATUSES = {"planned", "active", "blocked", "done"}
TASK_STATUSES = {"todo", "in_progress", "blocked", "review", "done"}
KINDS = {"code", "doc", "ops", "human"}
ASSIGNEES = {"owner", "claude-code", "chat"}
PRIORITIES = {"P1", "P2", "P3", "P4"}
URGENCIES = {"U1", "U2", "U3", "U4"}
OWNER_WORDS = {"согласовано", "approve", "согласовано в ADR", "approve decision"}

RE_GOAL = re.compile(r"^G-\d{3}$")
RE_STAGE = re.compile(r"^S\d+$")
RE_TASK = re.compile(r"^T-(\d{3})$")
RE_QUESTION = re.compile(r"^Q-(\d{3})$")
RE_ADR = re.compile(r"^ADR-(\d{3})$")
RE_ADR_FILE = re.compile(r"^(ADR-\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
RE_BRANCH = re.compile(r"^dev/(T-\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)$")
RE_GIT_BRANCH = re.compile(r"^(?:[^/]+/)?dev/(T-\d{3})(?:-|$)")
RE_DUE_REL = re.compile(r"^D\+\d+$")
RE_WEEK = re.compile(r"^(\d{2}\.\d{2}\.\d{4}) – (\d{2}\.\d{2}\.\d{4})$")
MAX_SLUG_WORDS = 5


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps dates as strings so formats can be validated."""


_Loader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return len(value) == 10


def _dmy(value: str) -> datetime | None:
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _num(rx: re.Pattern[str], value: object) -> int | None:
    if not isinstance(value, str):
        return None
    m = rx.match(value)
    return int(m.group(1)) if m else None


class Checker:
    def __init__(self, data: Any, path: str, decisions: Path) -> None:
        self.data: Any = data
        self.path = path
        self.decisions = decisions
        self.errors: list[str] = []

    def err(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def _keys(self, item: object, keys: tuple[str, ...], where: str) -> bool:
        if not isinstance(item, dict):
            self.err(where, "must be a mapping")
            return False
        ok = True
        for key in keys:
            if key not in item:
                self.err(where, f"missing key {key}")
                ok = False
        return ok

    def _ids(self, where: str, key: str, value: object) -> list[str]:
        """Return the string items of a list of ids; report anything else."""
        if not isinstance(value, list):
            self.err(where, f"{key} must be a list")
            return []
        good = []
        for item in value:
            if isinstance(item, str):
                good.append(item)
            else:
                self.err(where, f"{key} item {item!r} is not an id")
        return good

    def _list(self, key: str) -> list:
        value = self.data.get(key)
        if value is None:
            return []
        if not isinstance(value, list):
            self.err(self.path, f"{key} must be a list")
            return []
        return value

    def _enum(self, where: str, key: str, value: object, allowed: set[str]) -> None:
        if not isinstance(value, str) or value not in allowed:
            self.err(where, f"{key} {value!r} is not one of {sorted(allowed)}")

    # -- sections -----------------------------------------------------------

    def run(self) -> list[str]:
        if not isinstance(self.data, dict):
            self.err(self.path, "must be a mapping")
            return self.errors
        self._keys(self.data, TOP_KEYS, self.path)
        d = self.data
        if "updated" in d and not _iso_date(d["updated"]):
            self.err(self.path, f"updated {d['updated']!r} is not YYYY-MM-DD")
        if "version" in d and (not isinstance(d["version"], int) or d["version"] < 1):
            self.err(self.path, "version must be a positive integer")
        self.check_goal()
        stages = self.check_stages()
        tasks = self.check_tasks(stages)
        questions = self.check_questions(tasks)
        self.check_blockers(tasks, questions)
        self.check_week_plan(tasks)
        adrs = self.adr_files()
        self.check_approvals(adrs)
        self.check_log(tasks)
        self.check_next_ids(tasks, questions, adrs)
        return self.errors

    def check_goal(self) -> None:
        goal = self.data.get("goal")
        if goal is None or not self._keys(goal, GOAL_KEYS, "goal"):
            return
        if not RE_GOAL.match(str(goal["id"])):
            self.err("goal", f"id {goal['id']!r} is not G-NNN")
        self._enum(str(goal["id"]), "status", goal["status"], GOAL_STATUSES)

    def check_stages(self) -> dict[str, dict]:
        stages: dict[str, dict] = {}
        for i, stage in enumerate(self._list("stages")):
            where = str(stage.get("id")) if isinstance(stage, dict) and stage.get("id") else f"stages[{i}]"
            if not self._keys(stage, STAGE_KEYS, where):
                continue
            sid = stage["id"]
            if not isinstance(sid, str) or not RE_STAGE.match(sid):
                self.err(where, "id is not S<n>")
                continue
            if sid in stages:
                self.err(where, "duplicate id")
            stages[sid] = stage
            self._enum(where, "status", stage["status"], STAGE_STATUSES)
        return stages

    def check_tasks(self, stages: dict[str, dict]) -> dict[str, dict]:
        tasks: dict[str, dict] = {}
        for i, task in enumerate(self._list("tasks")):
            where = str(task.get("id")) if isinstance(task, dict) and task.get("id") else f"tasks[{i}]"
            if not self._keys(task, TASK_KEYS, where):
                continue
            tid = task["id"]
            if _num(RE_TASK, tid) is None:
                self.err(where, "id is not T-NNN")
                continue
            if tid in tasks:
                self.err(where, "duplicate id")
            tasks[tid] = task
            if not isinstance(task["stage"], str) or task["stage"] not in stages:
                self.err(where, f"stage {task['stage']!r} does not exist")
            self._enum(where, "kind", task["kind"], KINDS)
            self._enum(where, "priority", task["priority"], PRIORITIES)
            self._enum(where, "urgency", task["urgency"], URGENCIES)
            self._enum(where, "status", task["status"], TASK_STATUSES)
            self._enum(where, "assignee", task["assignee"], ASSIGNEES)
            task["blocked_by"] = self._ids(where, "blocked_by", task["blocked_by"])
            due = task["due"]
            if not isinstance(due, str) or not (_dmy(due) or RE_DUE_REL.match(due)):
                self.err(where, f"due {due!r} is not DD.MM.YYYY, DD.MM.YYYY HH:MM or D+N")
            branch = task["branch"]
            if branch is not None:
                m = RE_BRANCH.match(str(branch))
                if not m:
                    self.err(where, f"branch {branch!r} is not dev/T-NNN-<slug>")
                elif m.group(1) != tid:
                    self.err(where, f"branch {branch!r} belongs to {m.group(1)}")
                elif len(m.group(2).split("-")) > MAX_SLUG_WORDS:
                    self.err(where, f"branch slug has more than {MAX_SLUG_WORDS} words")
            pr = task["pr"]
            if pr is not None and (not isinstance(pr, int) or pr < 1):
                self.err(where, f"pr {pr!r} must be a positive integer or null")
            if task["status"] == "done" and task["kind"] in ("code", "doc") and pr is None:
                self.err(where, "done code/doc task has no pr")
        return tasks

    def check_questions(self, tasks: dict[str, dict]) -> dict[str, dict]:
        questions: dict[str, dict] = {}
        for i, q in enumerate(self._list("open_questions")):
            where = str(q.get("id")) if isinstance(q, dict) and q.get("id") else f"open_questions[{i}]"
            if not self._keys(q, QUESTION_KEYS, where):
                continue
            qid = q["id"]
            if _num(RE_QUESTION, qid) is None:
                self.err(where, "id is not Q-NNN")
                continue
            if qid in questions:
                self.err(where, "duplicate id")
            questions[qid] = q
            if not _iso_date(q["asked"]):
                self.err(where, f"asked {q['asked']!r} is not YYYY-MM-DD")
            q["blocks"] = blocks = self._ids(where, "blocks", q["blocks"])
            for tid in blocks:
                if tid not in tasks:
                    self.err(where, f"blocks {tid!r} which does not exist")
        return questions

    def check_blockers(self, tasks: dict[str, dict], questions: dict[str, dict]) -> None:
        blocks_count: dict[str, int] = {}
        for tid, task in tasks.items():
            for b in task["blocked_by"]:
                if b not in tasks:
                    self.err(tid, f"blocked_by {b!r} does not exist")
                    continue
                if b == tid:
                    continue  # reported as a cycle below
                blocks_count[b] = blocks_count.get(b, 0) + 1
                mine, theirs = _dmy(str(task["due"])), _dmy(str(tasks[b]["due"]))
                if mine and theirs and mine < theirs:
                    self.err(tid, f"due {task['due']} is before its blocker {b} due {tasks[b]['due']}")
        for b, n in sorted(blocks_count.items()):
            if n >= 2 and tasks[b]["urgency"] not in ("U1", "U2"):
                self.err(b, f"blocks {n} tasks but urgency is {tasks[b]['urgency']}, needs U1 or U2")
        question_blocks = {
            t for q in questions.values() if q.get("answer") is None for t in q["blocks"]
        }
        for tid, task in tasks.items():
            if task["status"] == "blocked" and not task["blocked_by"] and tid not in question_blocks:
                self.err(tid, "status blocked without a blocker or an open question")
        self._cycles(tasks)

    def _cycles(self, tasks: dict[str, dict]) -> None:
        white, grey, black = 0, 1, 2
        color = {t: white for t in tasks}
        reported: set[frozenset[str]] = set()

        def visit(node: str, stack: list[str]) -> None:
            color[node] = grey
            stack.append(node)
            for nxt in tasks[node]["blocked_by"]:
                if nxt not in tasks:
                    continue
                if color[nxt] == grey:
                    cycle = stack[stack.index(nxt):] + [nxt]
                    key = frozenset(cycle)
                    if key not in reported:
                        reported.add(key)
                        self.err(nxt, "blocked_by cycle " + " -> ".join(cycle))
                elif color[nxt] == white:
                    visit(nxt, stack)
            stack.pop()
            color[node] = black

        for t in tasks:
            if color[t] == white:
                visit(t, [])

    def check_week_plan(self, tasks: dict[str, dict]) -> None:
        wp = self.data.get("week_plan")
        if wp is None or not self._keys(wp, ("week", "approved", "items"), "week_plan"):
            return
        m = RE_WEEK.match(str(wp["week"]))
        if not m or not all(_dmy(g) for g in m.groups()):
            self.err("week_plan", f"week {wp['week']!r} is not DD.MM.YYYY – DD.MM.YYYY")
        if not isinstance(wp["approved"], bool):
            self.err("week_plan", "approved must be true or false")
        for tid in self._ids("week_plan", "items", wp["items"]):
            if tid not in tasks:
                self.err("week_plan", f"item {tid!r} does not exist")

    def adr_files(self) -> dict[str, Path]:
        adrs: dict[str, Path] = {}
        if not self.decisions.is_dir():
            return adrs
        for f in sorted(self.decisions.iterdir()):
            if not f.name.startswith("ADR-"):
                continue
            m = RE_ADR_FILE.match(f.name)
            if not m:
                self.err(f"docs/decisions/{f.name}", "file name is not ADR-NNN-<slug>.md")
                continue
            if m.group(1) in adrs:
                self.err(f"docs/decisions/{f.name}", f"duplicate {m.group(1)}")
            adrs[m.group(1)] = f
        return adrs

    def check_approvals(self, adrs: dict[str, Path]) -> None:
        for i, a in enumerate(self._list("approvals")):
            where = f"approvals[{i}]"
            if not self._keys(a, APPROVAL_KEYS, where):
                continue
            if not _iso_date(a["date"]):
                self.err(where, f"date {a['date']!r} is not YYYY-MM-DD")
            self._enum(where, "word", a["word"], OWNER_WORDS)
            if a["adr"] is not None:
                if _num(RE_ADR, a["adr"]) is None:
                    self.err(where, f"adr {a['adr']!r} is not ADR-NNN")
                elif a["adr"] not in adrs:
                    self.err(where, f"adr {a['adr']} has no file in docs/decisions")

    def check_log(self, tasks: dict[str, dict]) -> None:
        for i, entry in enumerate(self._list("log")):
            where = f"log[{i}]"
            if not self._keys(entry, LOG_KEYS, where):
                continue
            if not _iso_date(entry["date"]):
                self.err(where, f"date {entry['date']!r} is not YYYY-MM-DD")
            prs = entry["merged_prs"]
            if not isinstance(prs, list):
                self.err(where, "merged_prs must be a list")
                continue
            for j, pr in enumerate(prs):
                pw = f"{where}.merged_prs[{j}]"
                if self._keys(pr, MERGED_PR_KEYS, pw) and (not isinstance(pr["task"], str) or pr["task"] not in tasks):
                    self.err(pw, f"task {pr['task']!r} does not exist")

    def check_next_ids(self, tasks: dict, questions: dict, adrs: dict) -> None:
        nxt = self.data.get("next_ids")
        if nxt is None or not self._keys(nxt, ("task", "question", "adr"), "next_ids"):
            return
        for key, rx, used in (
            ("task", RE_TASK, tasks),
            ("question", RE_QUESTION, questions),
            ("adr", RE_ADR, adrs),
        ):
            n = _num(rx, nxt[key])
            if n is None:
                self.err("next_ids", f"{key} {nxt[key]!r} has the wrong format")
                continue
            for uid in used:
                u = _num(rx, uid)
                if u is not None and u >= n:
                    self.err("next_ids", f"{key} {nxt[key]} is not ahead of used {uid}")

    # -- git ----------------------------------------------------------------

    def check_branches(self, branches: list[str]) -> list[str]:
        tasks = {
            t["id"]: t for t in self.data.get("tasks") or []
            if isinstance(t, dict) and isinstance(t.get("id"), str)
        }
        ids = self.data.get("next_ids")
        nxt = _num(RE_TASK, ids.get("task")) if isinstance(ids, dict) else None
        for name in branches:
            m = RE_GIT_BRANCH.match(name.strip())
            if not m:
                continue
            tid = m.group(1)
            if tid not in tasks:
                self.err(name, f"branch has no task {tid} in dev-state")
            if nxt is not None and _num(RE_TASK, tid) >= nxt:
                self.err(name, f"branch task {tid} is not below next_ids.task")
        return self.errors


def git_branches(cwd: Path) -> list[str]:
    out = subprocess.run(
        ["git", "branch", "-a", "--format=%(refname:short)"],
        cwd=cwd, capture_output=True, text=True, check=True,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_Loader)  # noqa: S506 - SafeLoader subclass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate docs/dev-state.yaml")
    parser.add_argument("--git", action="store_true", help="also check dev/T-NNN-* branches")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--decisions", type=Path, default=None)
    args = parser.parse_args(argv)

    path = args.file
    decisions = args.decisions or (path.resolve().parent / "decisions")
    try:
        shown = str(path.resolve().relative_to(ROOT))
    except ValueError:
        shown = str(path)
    try:
        data = load(path)
    except (OSError, yaml.YAMLError) as exc:
        print(f"{shown}: cannot read: {exc}".splitlines()[0])
        return 2

    checker = Checker(data, shown, decisions)
    errors = checker.run()
    if args.git and isinstance(data, dict):
        try:
            branches = git_branches(path.resolve().parent)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"git: cannot list branches: {exc}")
            return 2
        errors = checker.check_branches(branches)
    for line in errors:
        print(line)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
