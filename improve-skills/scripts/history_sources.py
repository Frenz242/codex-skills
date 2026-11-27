"""Read bounded, repository-scoped GitHub metadata without writing to GitHub."""

import json
import re
import subprocess
from functools import wraps
from urllib.parse import quote


class HistoryGap(Exception):
    """Metadata could not be verified; never pass through raw CLI diagnostics."""


def require_metadata(function):
    @wraps(function)
    def read(*args):
        try:
            return function(*args)
        except (KeyError, TypeError, AttributeError):
            raise HistoryGap("GitHub source metadata is incomplete.") from None
    return read


def github(*args):
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=45,
            check=True, stdin=subprocess.DEVNULL,
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError):
        raise HistoryGap("GitHub source unavailable or unreadable.") from None


def validate_repository(repo):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repo):
        raise HistoryGap("Expected a GitHub repository in owner/name form.")


@require_metadata
def inventory(repo):
    validate_repository(repo)
    fields = "number,state,stateReason,updatedAt"
    rows = github("issue", "list", "--repo", repo, "--state", "all", "--limit", "101", "--json", fields)
    if not isinstance(rows, list) or any(type(row.get("number")) is not int for row in rows):
        raise HistoryGap("Issue inventory could not be verified.")
    return {"ok": True, "issues": rows[:100], "moreAvailable": len(rows) > 100,
            "coverageGaps": ["Inventory is limited to 100 issues."] if len(rows) > 100 else []}


@require_metadata
def repository_metadata(repo):
    validate_repository(repo)
    data = github("repo", "view", repo, "--json", "defaultBranchRef,visibility")
    branch = data["defaultBranchRef"]["name"]
    if not isinstance(branch, str) or not branch:
        raise HistoryGap("Default branch could not be verified.")
    return branch, data["visibility"] == "PUBLIC"


@require_metadata
def inspect_incident(repo, number, default_branch):
    issue = github("issue", "view", str(number), "--repo", repo, "--json",
                   "state,stateReason,closedByPullRequestsReferences")
    if issue["state"] not in ("OPEN", "CLOSED") or not isinstance(issue["closedByPullRequestsReferences"], list):
        raise HistoryGap("Issue disposition could not be verified.")
    disposition = "open" if issue["state"] == "OPEN" else "unknown"
    refs = [("issue", number)]
    for closing in issue["closedByPullRequestsReferences"]:
        origin = closing["repository"]
        if (origin["owner"]["login"] + "/" + origin["name"]).lower() != repo.lower():
            raise HistoryGap("Closing pull request is outside the scoped repository.")
        pr_number = closing["number"]
        if type(pr_number) is not int or pr_number <= 0:
            raise HistoryGap("Closing pull request could not be verified.")
        refs.append(("pr", pr_number))
        pr = github("pr", "view", str(pr_number), "--repo", repo, "--json",
                    "mergedAt,mergeCommit")
        if not pr["mergedAt"] or not pr["mergeCommit"]:
            continue
        commit = pr["mergeCommit"]["oid"]
        if not re.fullmatch("[a-f0-9]{40,64}", commit):
            raise HistoryGap("Merge commit could not be verified.")
        comparison = github("api", f"repos/{repo}/compare/{commit}...{quote(default_branch, safe='')}",
                            "--jq", ".status | @json")
        if comparison not in ("ahead", "behind", "identical", "diverged"):
            raise HistoryGap("Default-branch ancestry could not be verified.")
        if comparison in ("ahead", "identical"):
            refs.append(("merge", commit))
            if issue["state"] == "CLOSED" and issue["stateReason"] == "COMPLETED":
                disposition = "fixed"
    return disposition, refs
