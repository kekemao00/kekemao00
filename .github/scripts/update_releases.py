"""Refresh the "latest releases" block in README.md from the owner's public repos."""

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "kekemao00")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = "README.md"
LIMIT = 5
START, END = "<!-- RELEASES:START -->", "<!-- RELEASES:END -->"
BEIJING = timezone(timedelta(hours=8))


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    repos = get(f"https://api.github.com/users/{OWNER}/repos?type=owner&per_page=100")
    repos = [r for r in repos if not (r["fork"] or r["archived"] or r["private"]) and r["name"] != OWNER]

    releases = []
    for repo in repos:
        for rel in get(f"https://api.github.com/repos/{OWNER}/{repo['name']}/releases?per_page=100"):
            if rel["draft"] or not rel["published_at"]:
                continue
            published = datetime.fromisoformat(rel["published_at"].replace("Z", "+00:00"))
            releases.append((published, repo, rel))
    releases.sort(key=lambda item: item[0], reverse=True)

    now = datetime.now(timezone.utc)
    recent = [r for r in releases if now - r[0] <= timedelta(days=30)]
    # One line per project: a repo that ships several versions in a day
    # would otherwise crowd everything else out of the list.
    latest_per_repo, seen = [], set()
    for item in releases:
        if item[1]["name"] not in seen:
            seen.add(item[1]["name"])
            latest_per_repo.append(item)

    lines = ["| 项目 | 最新版本 | 发布日期 |", "| :-- | :-: | :-: |"]
    for published, repo, rel in latest_per_repo[:LIMIT]:
        day = published.astimezone(BEIJING).strftime("%Y-%m-%d")
        lines.append(
            f"| 🏷️ [**{repo['name']}**]({repo['html_url']}) "
            f"| [`{rel['tag_name']}`]({rel['html_url']}) | {day} |"
        )
    if len(lines) == 2:
        lines.append("| 暂时还没有发布 | – | – |")
    summary = (
        f"<sub>近 30 天在 {len({r[1]['name'] for r in recent})} 个项目里发布了 {len(recent)} 个版本 · "
        "由 GitHub Actions 每 6 小时自动刷新</sub>"
    )
    block = "\n".join([START, *lines, "", summary, END])

    with open(README, encoding="utf-8") as f:
        text = f.read()
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
    if new != text:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)


if __name__ == "__main__":
    main()
