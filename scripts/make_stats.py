#!/usr/bin/env python3
"""Draws assets/stats.svg and assets/langs.svg from the GitHub GraphQL API.

Run with `gh` signed in as the profile owner so private repositories count
towards the language shares (only the shares are published, never the names):

    python3 scripts/make_stats.py            # calls gh itself
    python3 scripts/make_stats.py stats.json # or reads a saved GraphQL response
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

LOGIN = "EndrexAkoto"
QUERY = """
{ user(login:"EndrexAkoto"){
    followers{totalCount}
    repositories(ownerAffiliations:OWNER, first:100){ totalCount
      nodes{ isFork stargazerCount
        languages(first:10, orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name color } } } } }
    contributionsCollection{ totalCommitContributions restrictedContributionsCount
      totalPullRequestContributions totalIssueContributions totalRepositoriesWithContributedCommits
      contributionCalendar{ totalContributions } } } }
"""

ROOT = Path(__file__).resolve().parent.parent
TEXT, MUTED, ACCENT, BORDER, BG = "#1f2328", "#59636e", "#3987e5", "#d1d9e0", "#ffffff"


def load(path):
    if path:
        return json.loads(Path(path).read_text())["data"]["user"]
    out = subprocess.run(["gh", "api", "graphql", "-f", f"query={QUERY}"], check=True, capture_output=True, text=True)
    return json.loads(out.stdout)["data"]["user"]


def card(width, height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">
<style>text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}}
.t{{font-size:18px;font-weight:600;fill:{ACCENT}}} .l{{font-size:14px;fill:{TEXT}}} .v{{font-size:14px;font-weight:700;fill:{TEXT}}} .m{{font-size:11px;fill:{MUTED}}}</style>
<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="6" fill="{BG}" stroke="{BORDER}"/>
<text x="24" y="38" class="t">{title}</text>
{body}
</svg>
"""


def stats_card(u):
    r, c = u["repositories"], u["contributionsCollection"]
    stars = sum(n["stargazerCount"] for n in r["nodes"])
    commits = c["totalCommitContributions"] + c["restrictedContributionsCount"]
    rows = [
        ("Repositories", r["totalCount"]),
        ("Commits in the last year", commits),
        ("Pull requests in the last year", c["totalPullRequestContributions"]),
        ("Repositories contributed to", c["totalRepositoriesWithContributedCommits"]),
        ("Stars earned", stars),
        ("Followers", u["followers"]["totalCount"]),
    ]
    body = []
    for i, (label, value) in enumerate(rows):
        y = 72 + i * 28
        body.append(f'<text x="24" y="{y}" class="l">{label}</text><text x="396" y="{y}" class="v" text-anchor="end">{value:,}</text>')
    body.append(f'<text x="24" y="{72 + len(rows) * 28}" class="m">Counts public and private work. Updated {date.today():%d %b %Y}.</text>')
    return card(420, 72 + len(rows) * 28 + 20, "GitHub activity", "\n".join(body))


def langs_card(u):
    totals, colors = {}, {}
    for n in u["repositories"]["nodes"]:
        if n["isFork"]:
            continue
        for e in n["languages"]["edges"]:
            name = e["node"]["name"]
            totals[name] = totals.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or MUTED
    total = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
    body, x = [], 24
    for name, size in top:  # one stacked bar
        w = max(2, round(372 * size / total))
        body.append(f'<rect x="{x}" y="56" width="{w}" height="10" fill="{colors[name]}"/>')
        x += w
    for i, (name, size) in enumerate(top):
        col, row = i % 2, i // 2
        y = 96 + row * 26
        x = 24 + col * 190
        body.append(f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{colors[name]}"/>'
                    f'<text x="{x + 18}" y="{y}" class="l">{name}</text>'
                    f'<text x="{x + 170}" y="{y}" class="v" text-anchor="end">{100 * size / total:.1f}%</text>')
    rows = (len(top) + 1) // 2
    body.append(f'<text x="24" y="{96 + rows * 26 + 2}" class="m">By bytes of code across all non-fork repositories, public and private.</text>')
    return card(420, 96 + rows * 26 + 20, "Languages", "\n".join(body))


if __name__ == "__main__":
    user = load(sys.argv[1] if len(sys.argv) > 1 else None)
    (ROOT / "assets" / "stats.svg").write_text(stats_card(user))
    (ROOT / "assets" / "langs.svg").write_text(langs_card(user))
    print("wrote assets/stats.svg and assets/langs.svg")
