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
LANGS = "languages(first:20, orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name color } } }"
QUERY_USER = f"""
{{ user(login:"{LOGIN}"){{ createdAt followers{{totalCount}}
    contributionsCollection{{ totalCommitContributions restrictedContributionsCount
      totalPullRequestContributions totalRepositoriesWithContributedCommits }} }} }}
"""
QUERY_OWNED = f"""query($endCursor:String){{ user(login:"{LOGIN}"){{
    repositories(ownerAffiliations:OWNER, first:100, after:$endCursor){{ totalCount
      pageInfo{{hasNextPage endCursor}} nodes{{ isFork stargazerCount {LANGS} }} }} }} }}"""
QUERY_CONTRIB = f"""query($endCursor:String){{ user(login:"{LOGIN}"){{
    repositoriesContributedTo(first:100, after:$endCursor, includeUserRepositories:false,
      contributionTypes:[COMMIT,PULL_REQUEST]){{ pageInfo{{hasNextPage endCursor}} nodes{{ isFork {LANGS} }} }} }} }}"""
QUERY_YEAR = """{{ user(login:"%s"){{ contributionsCollection(from:"{y}-01-01T00:00:00Z", to:"{y}-12-31T23:59:59Z"){{
    totalCommitContributions restrictedContributionsCount }} }} }}""" % LOGIN

ROOT = Path(__file__).resolve().parent.parent
# Smaller languages worth naming on the card even when they are a sliver by bytes.
ALSO = {"Swift": "Swift", "Dart": "Dart (Flutter)", "Kotlin": "Kotlin", "C": "C", "C++": "C++",
        "PLpgSQL": "SQL", "Shell": "Shell", "Jupyter Notebook": "Jupyter", "Move": "Move", "Rust": "Rust"}
# Build output and vendored code that GitHub counts as a language but nobody wrote here.
NOISE = {"Cython", "Mako", "Makefile", "CMake", "Dockerfile", "Procfile", "Batchfile", "Go Template", "Brainfuck"}
TEXT, MUTED, ACCENT, BORDER, BG = "#1f2328", "#59636e", "#3987e5", "#d1d9e0", "#ffffff"


def gql(query, paginate=False):
    cmd = ["gh", "api", "graphql"] + (["--paginate"] if paginate else []) + ["-f", f"query={query}"]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    return [json.loads(x) for x in out.replace("}{", "}\n{").splitlines() if x.strip()]


def load(path):
    if path:
        return json.loads(Path(path).read_text())
    u = gql(QUERY_USER)[0]["data"]["user"]
    owned = [n for p in gql(QUERY_OWNED, True) for n in p["data"]["user"]["repositories"]["nodes"]]
    contrib = [n for p in gql(QUERY_CONTRIB, True) for n in p["data"]["user"]["repositoriesContributedTo"]["nodes"]]
    first_year = int(u["createdAt"][:4])
    years = {}
    for y in range(first_year, date.today().year + 1):
        c = gql(QUERY_YEAR.format(y=y))[0]["data"]["user"]["contributionsCollection"]
        years[y] = c["totalCommitContributions"] + c["restrictedContributionsCount"]
    data = {"user": u, "owned": owned, "contributed": contrib, "commits_by_year": years,
            "repo_count": gql(QUERY_OWNED)[0]["data"]["user"]["repositories"]["totalCount"]}
    (ROOT / "stats.json").write_text(json.dumps(data))
    return data


def card(width, height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">
<style>text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}}
.t{{font-size:18px;font-weight:600;fill:{ACCENT}}} .l{{font-size:14px;fill:{TEXT}}} .v{{font-size:14px;font-weight:700;fill:{TEXT}}} .m{{font-size:11px;fill:{MUTED}}}</style>
<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="6" fill="{BG}" stroke="{BORDER}"/>
<text x="24" y="38" class="t">{title}</text>
{body}
</svg>
"""


def stats_card(d):
    u, c = d["user"], d["user"]["contributionsCollection"]
    stars = sum(n["stargazerCount"] for n in d["owned"])
    last_year = c["totalCommitContributions"] + c["restrictedContributionsCount"]
    first_year = min(int(y) for y, n in d["commits_by_year"].items() if n)
    rows = [
        (f"Commits since {first_year}", sum(d["commits_by_year"].values())),
        ("Commits in the last year", last_year),
        ("Pull requests in the last year", c["totalPullRequestContributions"]),
        ("Repositories owned", d["repo_count"]),
        ("Other repositories contributed to", len(d["contributed"])),
        ("Stars earned", stars),
        ("Followers", u["followers"]["totalCount"]),
    ]
    body = []
    for i, (label, value) in enumerate(rows):
        y = 72 + i * 28
        body.append(f'<text x="24" y="{y}" class="l">{label}</text><text x="396" y="{y}" class="v" text-anchor="end">{value:,}</text>')
    body.append(f'<text x="24" y="{72 + len(rows) * 28}" class="m">Counts public and private work. Updated {date.today():%d %b %Y}.</text>')
    return card(420, 72 + len(rows) * 28 + 20, "GitHub activity", "\n".join(body))


def langs_card(d):
    totals, colors = {}, {}
    for n in d["owned"] + d["contributed"]:
        if n["isFork"]:
            continue
        for e in n["languages"]["edges"]:
            name = e["node"]["name"]
            if name in NOISE:
                continue
            totals[name] = totals.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or MUTED
    total = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]  # the bar and the grid
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
    y = 96 + rows * 26 + 2
    also = [label for name, label in ALSO.items() if name in totals and name not in dict(top)]
    body.append(f'<text x="24" y="{y}" class="m">Also in the codebases</text>')
    body.append(f'<text x="24" y="{y + 20}" class="v">{", ".join(also[:5])}</text>')
    body.append(f'<text x="24" y="{y + 40}" class="v">{", ".join(also[5:])}</text>')
    body.append(f'<text x="24" y="{y + 64}" class="m">By bytes of code across every repository I own or commit to, public and private.</text>')
    return card(420, y + 82, "Languages", "\n".join(body))


if __name__ == "__main__":
    data = load(sys.argv[1] if len(sys.argv) > 1 else None)
    (ROOT / "assets" / "stats.svg").write_text(stats_card(data))
    (ROOT / "assets" / "langs.svg").write_text(langs_card(data))
    print("wrote assets/stats.svg and assets/langs.svg")
