#!/usr/bin/env python3
"""Render assets/stats.svg from live GitHub data (GraphQL, std-lib only).

Environment:
    GH_TOKEN / GITHUB_TOKEN   token used for the GraphQL API (required)
    GH_LOGIN                  GitHub login to render (default: ddd3h)

Usage:
    GH_TOKEN=$(gh auth token) python3 scripts/gen_stats.py [out.svg]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

LOGIN = os.environ.get("GH_LOGIN", "ddd3h")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
API = "https://api.github.com/graphql"
# Languages left out of the "top languages" bars (markup / docs, not code).
LANG_HIDE = {
    s.strip().lower()
    for s in os.environ.get("LANG_HIDE", "HTML,CSS,SCSS,TeX,BibTeX Style,Jupyter Notebook,Makefile").split(",")
    if s.strip()
}

BG = "#05070d"
PANEL = "#0d1117"
PANEL2 = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
WHITE = "#f8fafc"
CYAN = "#38bdf8"
VIOLET = "#a78bfa"
GREEN = "#34d399"
ORANGE = "#fb923c"
PINK = "#f472b6"
YELLOW = "#fbbf24"
MONO = "'JetBrains Mono','Fira Code','SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


def gql(query: str, variables: dict) -> dict:
    if not TOKEN:
        sys.exit("gen_stats: GH_TOKEN / GITHUB_TOKEN is not set")
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{LOGIN}-profile-stats",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())
    if "errors" in payload:
        sys.exit(f"gen_stats: GraphQL errors: {payload['errors']}")
    return payload["data"]


USER_Q = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection { totalRepositoriesWithContributedCommits }
  }
}
"""

REPOS_Q = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

YEAR_Q = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
    }
  }
}
"""


def fetch() -> dict:
    u = gql(USER_Q, {"login": LOGIN})["user"]
    created = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))

    stars, repos, langs = 0, 0, {}
    after = None
    while True:
        page = gql(REPOS_Q, {"login": LOGIN, "after": after})["user"]["repositories"]
        repos = page["totalCount"]
        for node in page["nodes"]:
            stars += node["stargazerCount"]
            for e in node["languages"]["edges"]:
                name = e["node"]["name"]
                if name.lower() in LANG_HIDE:
                    continue
                entry = langs.setdefault(name, {"size": 0, "color": e["node"]["color"] or CYAN})
                entry["size"] += e["size"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]

    commits = 0
    now = dt.datetime.now(dt.timezone.utc)
    year = created.year
    while year <= now.year:
        start = max(created, dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc))
        end = min(now, dt.datetime(year + 1, 1, 1, tzinfo=dt.timezone.utc))
        c = gql(YEAR_Q, {"login": LOGIN, "from": start.isoformat(), "to": end.isoformat()})["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        year += 1

    total = sum(v["size"] for v in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: kv[1]["size"], reverse=True)[:7]
    return {
        "stars": stars,
        "repos": repos,
        "commits": commits,
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "contributed": u["contributionsCollection"]["totalRepositoriesWithContributedCommits"],
        "since": created.year,
        "langs": [(n, v["size"] / total, v["color"]) for n, v in top],
        "synced": now.strftime("%Y-%m-%d %H:%M UTC"),
    }


def n(v: int) -> str:
    return f"{v:,}"


def render(d: dict) -> str:
    W, H = 1200, 330
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub telemetry for {LOGIN}">',
        "<defs>",
        f'<clipPath id="r"><rect width="{W}" height="{H}" rx="16"/></clipPath>',
        f'<linearGradient id="hd" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>',
        '<pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#ffffff" stroke-opacity="0.03"/></pattern>',
        "</defs>",
        '<g clip-path="url(#r)">',
        f'<rect width="{W}" height="{H}" fill="{PANEL}"/>',
        f'<rect width="{W}" height="{H}" fill="url(#grid)"/>',
        f'<rect x="0" y="0" width="{W}" height="3" fill="url(#hd)"/>',
        # header
        f'<text x="32" y="44" font-family="{MONO}" font-size="13" fill="{CYAN}" letter-spacing="3">TELEMETRY</text>',
        f'<text x="152" y="44" font-family="{MONO}" font-size="13" fill="{MUTED}">// github.com/{escape(LOGIN)}</text>',
    ]
    sync = f"sync {d['synced']}"
    sync_w = len(sync) * 6.6
    o.append(
        f'<circle cx="{W - 32 - sync_w - 12:.0f}" cy="40" r="4" fill="{GREEN}"><animate attributeName="opacity" values="1;0.2;1" dur="1.6s" repeatCount="indefinite"/></circle>'
        f'<text x="{W - 32}" y="44" text-anchor="end" font-family="{MONO}" font-size="11" fill="{MUTED}">{escape(sync)}</text>'
    )

    tiles = [
        ("COMMITS", n(d["commits"]), CYAN, f"all time · since {d['since']}"),
        ("PULL REQUESTS", n(d["prs"]), VIOLET, "opened"),
        ("ISSUES", n(d["issues"]), PINK, "filed"),
        ("REPOSITORIES", n(d["repos"]), GREEN, "own, non-fork"),
        ("CONTRIBUTED TO", n(d["contributed"]), YELLOW, "repos, past year"),
        ("STARS", n(d["stars"]), ORANGE, "earned") if d["stars"] else ("FOLLOWERS", n(d["followers"]), ORANGE, "on GitHub"),
    ]
    tw, th, gx, gy = 176, 92, 12, 12
    for i, (label, value, col, sub) in enumerate(tiles):
        r, c = divmod(i, 3)
        x = 32 + c * (tw + gx)
        y = 70 + r * (th + gy)
        beg = 0.15 + i * 0.12
        o.append(
            f'<g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.6s" begin="{beg:.2f}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" values="0 14;0 0" dur="0.6s" begin="{beg:.2f}s" fill="freeze"/>'
            f'<rect x="{x}" y="{y}" width="{tw}" height="{th}" rx="12" fill="{PANEL2}" stroke="{BORDER}"/>'
            f'<rect x="{x}" y="{y + 14}" width="3" height="{th - 28}" rx="1.5" fill="{col}"/>'
            f'<text x="{x + 18}" y="{y + 26}" font-family="{MONO}" font-size="10.5" fill="{MUTED}" letter-spacing="1.5">{label}</text>'
            f'<text x="{x + 18}" y="{y + 60}" font-family="{MONO}" font-size="28" font-weight="700" fill="{WHITE}">{value}</text>'
            f'<text x="{x + 18}" y="{y + 78}" font-family="{SANS}" font-size="11" fill="{MUTED}">{escape(sub)}</text>'
            f"</g>"
        )

    # languages
    lx, ly = 632, 70
    bw = 400
    o.append(f'<text x="{lx}" y="{ly + 4}" font-family="{MONO}" font-size="10.5" fill="{MUTED}" letter-spacing="1.5">TOP LANGUAGES  ·  code bytes across own repos</text>')
    rows = d["langs"]
    rh = 27
    for i, (name, frac, col) in enumerate(rows):
        y = ly + 22 + i * rh
        w = max(3.0, bw * frac)
        beg = 0.4 + i * 0.1
        o.append(
            f'<text x="{lx}" y="{y + 12}" font-family="{SANS}" font-size="12.5" fill="{TEXT}">{escape(name)}</text>'
            f'<rect x="{lx + 110}" y="{y + 2}" width="{bw}" height="12" rx="6" fill="{PANEL2}"/>'
            f'<rect x="{lx + 110}" y="{y + 2}" width="{w:.1f}" height="12" rx="6" fill="{col}">'
            f'<animate attributeName="width" values="0;{w:.1f}" dur="1.1s" begin="{beg:.2f}s" fill="freeze"/></rect>'
            f'<text x="{lx + 110 + bw + 12}" y="{y + 12}" font-family="{MONO}" font-size="11.5" fill="{MUTED}">{frac * 100:5.1f}%</text>'
        )
    o.append("</g>")
    o.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="16" fill="none" stroke="{BORDER}"/>')
    o.append("</svg>")
    return "".join(o)


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "stats.svg")
    data = fetch()
    svg = render(data)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {out}: {json.dumps({k: v for k, v in data.items() if k != 'langs'})}")


if __name__ == "__main__":
    main()
