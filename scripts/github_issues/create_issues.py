#!/usr/bin/env python3
"""Publish the IncidentIQ development plan as GitHub issues.

Issues are created through the GitHub CLI (`gh`), so they are authored by the
account `gh` is logged in as. The script refuses to run unless that account is
OWNER from issues_data.py (Maheesh09).

What it creates, in both repositories:
  * labels      type (dev / qa / devops), priority, size, area
  * milestones  one per roadmap step
  * issues      every task in issues_data.py, in dependency order
  * epics       one tracking issue per step in the backend repo, listing the
                step's issues from both repos

Usage:
  python create_issues.py --dry-run                     # validate, list everything
  python create_issues.py --dry-run --preview plan.md   # also write every body to a file
  python create_issues.py                               # create everything
  python create_issues.py --repo backend                # one repo only
  python create_issues.py --step 2 --step 3             # selected roadmap steps only
  python create_issues.py --assign-me                   # assign new issues to yourself
  python create_issues.py --link-sub-issues             # also attach issues to epics as sub-issues

Re-running is safe: an issue whose exact title already exists in the repo
(open or closed) is skipped and its number is reused for cross references.
Do not rename titles in issues_data.py after publishing, or you will get
duplicates.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issues_data as data  # noqa: E402

TYPE_PREFIX = {"dev": "Dev", "qa": "QA", "devops": "DevOps"}
PLACEHOLDER = re.compile(r"\{\{(ref|be|fe):([^}]+)\}\}")
CREATE_DELAY_SECONDS = 2.0  # stay well under GitHub's content-creation rate limit


# --------------------------------------------------------------------------- gh

class GhError(RuntimeError):
    pass


def gh(*args: str, stdin: str = "") -> str:
    proc = subprocess.run(
        ["gh", *args],
        input=stdin.encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise GhError(f"gh {' '.join(args[:3])} ... failed:\n{err}")
    return proc.stdout.decode("utf-8", "replace").strip()


def slug(repo: str) -> str:
    return f"{data.OWNER}/{data.REPOS[repo]['name']}"


# ----------------------------------------------------------------------- model

def full_title(item: dict) -> str:
    if item["kind"] == "epic":
        return f"[Epic] {item['title']}"
    return f"[{TYPE_PREFIX[item['type']]}] {item['title']}"


def build_items() -> list[dict]:
    items = []
    for raw in data.ISSUES:
        item = dict(raw)
        item["kind"] = "issue"
        items.append(item)
    for raw in data.EPICS:
        item = dict(raw)
        item["kind"] = "epic"
        item["key"] = f"EPIC-{raw['step']}"
        item["repo"] = "backend"
        items.append(item)
    return items


def text_fields(item: dict) -> list[str]:
    out = []
    for field in ("summary", "why", "current", "notes", "goal", "done_when"):
        if item.get(field):
            out.append(item[field])
    for field in ("tasks", "acceptance", "files"):
        out.extend(item.get(field) or [])
    return out


def referenced_keys(item: dict) -> list[str]:
    keys = list(item.get("depends") or [])
    for text in text_fields(item):
        keys += [m.group(2) for m in PLACEHOLDER.finditer(text) if m.group(1) == "ref"]
    return keys


def validate(items: list[dict]) -> None:
    errors = []
    label_names = {name for name, _, _ in data.LABELS}
    keys = [i["key"] for i in items]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        errors.append(f"duplicate keys: {sorted(dupes)}")
    titles = [(i["repo"], full_title(i)) for i in items]
    dupe_titles = {t for t in titles if titles.count(t) > 1}
    if dupe_titles:
        errors.append(f"duplicate titles: {sorted(dupe_titles)}")

    position = {k: n for n, k in enumerate(keys)}
    for item in items:
        k = item["key"]
        if item["repo"] not in data.REPOS:
            errors.append(f"{k}: unknown repo {item['repo']}")
        if item["step"] not in data.MILESTONES:
            errors.append(f"{k}: unknown step {item['step']}")
        if item["kind"] == "issue":
            if item.get("type") not in TYPE_PREFIX:
                errors.append(f"{k}: type must be one of {list(TYPE_PREFIX)}")
            for field in ("title", "summary", "tasks", "acceptance", "priority", "size"):
                if not item.get(field):
                    errors.append(f"{k}: missing {field}")
            for label in labels_for(item):
                if label not in label_names:
                    errors.append(f"{k}: label '{label}' is not defined in LABELS")
        for ref in referenced_keys(item):
            if ref not in position:
                errors.append(f"{k}: references unknown key {ref}")
            elif position[ref] >= position[k]:
                errors.append(f"{k}: references {ref}, which comes later in the plan")
    if errors:
        raise SystemExit("issues_data.py is invalid:\n  " + "\n  ".join(errors))


def labels_for(item: dict) -> list[str]:
    if item["kind"] == "epic":
        return ["epic", f"priority: {item['priority']}"]
    labels = [
        f"type: {item['type']}",
        f"priority: {item['priority']}",
        f"size: {item['size']}",
    ]
    labels += [f"area: {a}" for a in item.get("areas") or []]
    labels += list(item.get("labels") or [])
    return labels


# ----------------------------------------------------------------- rendering

class Renderer:
    def __init__(self, items: list[dict], numbers: dict[str, int]):
        self.by_key = {i["key"]: i for i in items}
        self.numbers = numbers  # key -> issue number (only for issues on GitHub)

    def ref(self, key: str, from_repo: str, with_title: bool = False) -> str:
        target = self.by_key[key]
        number = self.numbers.get(key)
        if number is None:
            text = f"`{key}` (not created yet)"
        elif target["repo"] == from_repo:
            text = f"#{number}"
        else:
            text = f"{slug(target['repo'])}#{number}"
        if with_title:
            text += f" {full_title(target)}"
        return text

    def file_link(self, repo: str, path: str) -> str:
        meta = data.REPOS[repo]
        shown = path.split("#", 1)[0]
        url = f"https://github.com/{data.OWNER}/{meta['name']}/blob/{meta['branch']}/{path}"
        return f"[`{shown}`]({url})"

    def expand(self, text: str, from_repo: str) -> str:
        def sub(m: re.Match) -> str:
            kind, value = m.group(1), m.group(2).strip()
            if kind == "ref":
                return self.ref(value, from_repo)
            return self.file_link("backend" if kind == "be" else "frontend", value)

        return PLACEHOLDER.sub(sub, clean(text))

    def issue_body(self, item: dict) -> str:
        repo = item["repo"]
        milestone = data.MILESTONES[item["step"]]["title"]
        x = lambda t: self.expand(t, repo)  # noqa: E731
        parts = [
            f"> **Type:** {TYPE_PREFIX[item['type']]} · **Milestone:** {milestone} · "
            f"**Priority:** {item['priority']} · **Size:** {item['size']}",
            "## Summary\n" + x(item["summary"]),
        ]
        if item.get("why"):
            parts.append("## Why\n" + x(item["why"]))
        if item.get("current"):
            parts.append("## Current state\n" + x(item["current"]))
        parts.append("## Tasks\n" + checklist(x(t) for t in item["tasks"]))
        parts.append("## Acceptance criteria\n" + checklist(x(t) for t in item["acceptance"]))
        if item.get("files"):
            parts.append("## Files\n" + bullets(x(f) for f in item["files"]))
        deps = item.get("depends") or []
        parts.append(
            "## Depends on\n"
            + (bullets(self.ref(d, repo, with_title=True) for d in deps) if deps else "Nothing. This can start now.")
        )
        if item.get("notes"):
            parts.append("## Notes\n" + x(item["notes"]))
        if item.get("commit"):
            parts.append("## Suggested commit message\n```\n" + clean(item["commit"]) + "\n```")
        parts.append(f"<sub>Source: DEVELOPMENT_PLAN.md, {milestone}. Key `{item['key']}`.</sub>")
        return "\n\n".join(parts) + "\n"

    def epic_body(self, epic: dict, items: list[dict]) -> str:
        x = lambda t: self.expand(t, "backend")  # noqa: E731
        children = [i for i in items if i["kind"] == "issue" and i["step"] == epic["step"]]
        parts = [
            f"> **Milestone:** {data.MILESTONES[epic['step']]['title']} · **Priority:** {epic['priority']}",
            "## Goal\n" + x(epic["goal"]),
            "## Done when\n" + x(epic["done_when"]),
        ]
        for repo in data.REPOS:
            mine = [c for c in children if c["repo"] == repo]
            if not mine:
                continue
            lines = []
            for c in mine:
                if c["key"] in self.numbers:
                    lines.append(f"- [ ] {self.ref(c['key'], 'backend')}")
                else:
                    lines.append(f"- [ ] {full_title(c)} (`{c['key']}`, not created yet)")
            parts.append(f"## {slug(repo)}\n" + "\n".join(lines))
        parts.append("Work through the issues top to bottom; each one lists what it depends on.")
        return "\n\n".join(parts) + "\n"


def clean(text: str) -> str:
    """Dedent, then join hard-wrapped prose lines (GitHub renders every newline in
    an issue body as a line break). Tables, lists and code blocks are kept as is."""
    text = textwrap.dedent(text).strip("\n").rstrip()
    out, in_code = [], False
    for paragraph in text.split("\n\n"):
        lines = paragraph.split("\n")
        if any(l.lstrip().startswith("```") for l in lines):
            in_code = not in_code if sum(l.lstrip().startswith("```") for l in lines) % 2 else in_code
            out.append(paragraph)
        elif in_code or any(l.lstrip().startswith(("|", "- ", "* ", "#", ">")) for l in lines):
            out.append(paragraph)
        else:
            out.append(" ".join(l.strip() for l in lines))
    return "\n\n".join(out)


def checklist(lines) -> str:
    return "\n".join("- [ ] " + indent_continuation(l) for l in lines)


def bullets(lines) -> str:
    return "\n".join("- " + indent_continuation(l) for l in lines)


def indent_continuation(text: str) -> str:
    return text.replace("\n", "\n  ")


# ------------------------------------------------------------------ GitHub ops

def check_account() -> None:
    login = gh("api", "user", "--jq", ".login")
    if login.lower() != data.OWNER.lower():
        raise SystemExit(
            f"gh is logged in as '{login}', expected '{data.OWNER}'.\n"
            f"Run `gh auth switch -u {data.OWNER}` (or `gh auth login`) and unset GH_TOKEN/GITHUB_TOKEN if set."
        )
    print(f"Authenticated as {login}; issues will be authored by this account.")


def existing_issue_numbers(repo: str) -> dict[str, int]:
    raw = gh("issue", "list", "-R", slug(repo), "--state", "all", "--limit", "2000",
             "--json", "number,title")
    return {row["title"]: row["number"] for row in json.loads(raw or "[]")}


def ensure_labels(repo: str) -> None:
    for name, color, description in data.LABELS:
        gh("label", "create", name, "-R", slug(repo), "--color", color,
           "--description", description, "--force")
    print(f"  labels ready in {slug(repo)} ({len(data.LABELS)})")


def ensure_milestones(repo: str, steps: set[int]) -> None:
    raw = gh("api", f"repos/{slug(repo)}/milestones?state=all&per_page=100")
    have = {m["title"] for m in json.loads(raw or "[]")}
    for step, m in data.MILESTONES.items():
        if step not in steps or m["title"] in have:
            continue
        gh("api", "-X", "POST", f"repos/{slug(repo)}/milestones",
           "-f", f"title={m['title']}", "-f", f"description={clean(m['description'])}")
        print(f"  milestone created in {slug(repo)}: {m['title']}")


def create_issue(item: dict, body: str, assign_me: bool) -> int:
    args = ["issue", "create", "-R", slug(item["repo"]), "--title", full_title(item),
            "--body-file", "-", "--milestone", data.MILESTONES[item["step"]]["title"]]
    for label in labels_for(item):
        args += ["--label", label]
    if assign_me and item["kind"] == "issue":
        args += ["--assignee", "@me"]
    url = gh(*args, stdin=body).splitlines()[-1].strip()
    return int(url.rstrip("/").rsplit("/", 1)[1])


def link_sub_issue(epic_number: int, child: dict, child_number: int) -> None:
    child_id = gh("api", f"repos/{slug(child['repo'])}/issues/{child_number}", "--jq", ".id")
    try:
        gh("api", "-X", "POST", f"repos/{slug('backend')}/issues/{epic_number}/sub_issues",
           "-F", f"sub_issue_id={child_id}")
    except GhError as e:
        if "already" not in str(e).lower():
            print(f"    warning: could not link {child['key']} to epic #{epic_number}: {e}")


# ------------------------------------------------------------------------ main

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="validate and print, write nothing to GitHub")
    p.add_argument("--preview", metavar="FILE", help="write every rendered issue to a Markdown file")
    p.add_argument("--repo", choices=["backend", "frontend", "all"], default="all")
    p.add_argument("--step", type=int, action="append", help="limit to roadmap step(s); repeatable")
    p.add_argument("--no-epics", action="store_true", help="skip the per-step tracking issues")
    p.add_argument("--assign-me", action="store_true", help="assign created issues to the gh account")
    p.add_argument("--link-sub-issues", action="store_true", help="attach issues to their epic as GitHub sub-issues")
    p.add_argument("--offline", action="store_true", help="with --dry-run: do not call GitHub at all")
    args = p.parse_args()

    if args.offline and not args.dry_run:
        raise SystemExit("--offline only works together with --dry-run")

    items = build_items()
    validate(items)

    repos = list(data.REPOS) if args.repo == "all" else [args.repo]
    steps = set(args.step) if args.step else set(data.MILESTONES)
    selected = [
        i for i in items
        if i["repo"] in repos and i["step"] in steps and not (args.no_epics and i["kind"] == "epic")
    ]

    # Numbers of issues already on GitHub, in both repos (needed for cross-repo refs).
    numbers: dict[str, int] = {}
    if not args.offline:
        check_account()
        for repo in data.REPOS:
            existing = existing_issue_numbers(repo)
            for item in items:
                if item["repo"] == repo and full_title(item) in existing:
                    numbers[item["key"]] = existing[full_title(item)]

    # Every reference must be satisfiable: created earlier in this run, or already on GitHub.
    selected_keys = {i["key"] for i in selected}
    missing = sorted({
        f"{i['key']} -> {ref}"
        for i in selected if i["kind"] == "issue"
        for ref in referenced_keys(i)
        if ref not in selected_keys and ref not in numbers
    })
    if missing and not args.dry_run:
        raise SystemExit(
            "These references point at issues that are neither on GitHub nor selected in this run.\n"
            "Run without --repo/--step filters, or create the dependencies first:\n  " + "\n  ".join(missing)
        )

    renderer = Renderer(items, numbers)
    counts = {"created": 0, "skipped": 0}
    preview: list[str] = []

    if not args.dry_run:
        print("\nPreparing repositories")
        for repo in repos:
            ensure_labels(repo)
            ensure_milestones(repo, steps)

    print(f"\n{'Planning' if args.dry_run else 'Creating'} {len(selected)} items\n")
    for item in selected:
        is_epic = item["kind"] == "epic"
        body = renderer.epic_body(item, items) if is_epic else renderer.issue_body(item)
        title = full_title(item)
        tag = f"{item['repo']:<8} {item['key']:<8}"
        preview.append(
            f"# {slug(item['repo'])}: {title}\n\n"
            f"Labels: {', '.join(labels_for(item))}  \n"
            f"Milestone: {data.MILESTONES[item['step']]['title']}\n\n{body}\n---\n"
        )

        if item["key"] in numbers:
            if is_epic and not args.dry_run:
                gh("issue", "edit", str(numbers[item["key"]]), "-R", slug("backend"), "--body-file", "-", stdin=body)
                print(f"  updated  {tag} #{numbers[item['key']]:<4} {title}")
            else:
                print(f"  exists   {tag} #{numbers[item['key']]:<4} {title}")
            counts["skipped"] += 1
        elif args.dry_run:
            print(f"  would    {tag}       {title}")
        else:
            number = create_issue(item, body, args.assign_me)
            numbers[item["key"]] = number
            counts["created"] += 1
            print(f"  created  {tag} #{number:<4} {title}")
            time.sleep(CREATE_DELAY_SECONDS)

        if is_epic and args.link_sub_issues and not args.dry_run:
            for child in items:
                if child["kind"] == "issue" and child["step"] == item["step"] and child["key"] in numbers:
                    link_sub_issue(numbers[item["key"]], child, numbers[child["key"]])

    if args.preview:
        Path(args.preview).write_text("\n".join(preview), encoding="utf-8")
        print(f"\nPreview written to {Path(args.preview).resolve()}")

    if args.dry_run:
        by_type: dict[str, int] = {}
        for i in selected:
            t = "epic" if i["kind"] == "epic" else i["type"]
            by_type[t] = by_type.get(t, 0) + 1
        print(f"\nDry run: {len(selected)} items ({', '.join(f'{v} {k}' for k, v in sorted(by_type.items()))}). "
              f"{counts['skipped']} already exist. Nothing was written.")
        if missing:
            print("Unresolved references (fine for a dry run, would block a filtered live run):\n  " + "\n  ".join(missing))
    else:
        print(f"\nDone: {counts['created']} created, {counts['skipped']} already existed.")


if __name__ == "__main__":
    try:
        main()
    except GhError as e:
        raise SystemExit(str(e))
    except FileNotFoundError:
        raise SystemExit("GitHub CLI not found. Install it from https://cli.github.com and run `gh auth login`.")
