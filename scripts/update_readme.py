"""Keeps the profile README in sync with the account's public repos.

Touches only:
  - the "Repos-N" badge count
  - the block between <!-- AUTO:NEW-REPOS:START --> and <!-- AUTO:NEW-REPOS:END -->
    (public repos that are not linked anywhere else in the README yet)
  - the block between <!-- AUTO:RECENT:START --> and <!-- AUTO:RECENT:END -->
    (most recently updated repos)
Everything else in the README is left exactly as written.
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone

USER = os.environ.get("GH_USER", "H7modi77")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = os.environ.get("README_PATH", "README.md")
RECENT_N = 5


def api(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-readme"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get_repos():
    repos, page = [], 1
    while True:
        batch = api(f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    return [r for r in repos if not r["fork"] and not r["private"] and r["name"].lower() != USER.lower()]


def ago(iso):
    d = datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.days >= 30:
        n = d.days // 30; return f"{n} month{'s' if n > 1 else ''} ago"
    if d.days >= 1:
        return f"{d.days} day{'s' if d.days > 1 else ''} ago"
    h = d.seconds // 3600
    if h >= 1:
        return f"{h} hour{'s' if h > 1 else ''} ago"
    return "just now"


def pretty(name):
    return name.replace("-", " ").replace("_", " ")


def set_block(text, tag, body):
    start, end = f"<!-- AUTO:{tag}:START -->", f"<!-- AUTO:{tag}:END -->"
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pat.search(text):
        print(f"marker {tag} not found, skipping", file=sys.stderr)
        return text
    return pat.sub(lambda m: f"{start}\n{body}\n{end}", text)


def strip_blocks(text):
    return re.sub(r"<!-- AUTO:(\w|-)+:START -->.*?<!-- AUTO:(\w|-)+:END -->", "", text, flags=re.S)


def main():
    repos = get_repos()
    text = open(README, encoding="utf-8").read()

    # 1) repo count badge
    text = re.sub(r"(badge/Repos-)\d+", rf"\g<1>{len(repos)}", text)

    # 2) public repos not mentioned anywhere in the hand-written part
    linked = {m.lower() for m in re.findall(rf"github\.com/{USER}/([\w.\-]+)", strip_blocks(text), flags=re.I)}
    new = sorted([r for r in repos if r["name"].lower() not in linked], key=lambda r: r["created_at"], reverse=True)
    if new:
        rows = ["### 🆕 New Repositories", "", "| Project | What's inside |", "|---|---|"]
        for r in new:
            desc = (r["description"] or "").replace("|", "/") or "-"
            rows.append(f"| [**{pretty(r['name'])}**]({r['html_url']}) | {desc} |")
        body = "\n".join(rows)
    else:
        body = ""
    text = set_block(text, "NEW-REPOS", body)

    # 3) recently updated
    recent = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:RECENT_N]
    lines = [f"- [**{pretty(r['name'])}**]({r['html_url']}) · updated {ago(r['pushed_at'])}" for r in recent]
    text = set_block(text, "RECENT", "\n".join(lines))

    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"{len(repos)} public repos | {len(new)} not listed yet")


if __name__ == "__main__":
    main()
