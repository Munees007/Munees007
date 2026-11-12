#!/usr/bin/env python3
"""Generate themed GitHub stats / top-languages / activity SVG cards.

Reads live data from the GitHub GraphQL API (needs GH_TOKEN) and writes
three SVGs to assets/cards/. Run with --mock to render sample data locally.
"""
import json
import os
import sys
import urllib.request
from datetime import date
from xml.sax.saxutils import escape

USER = os.environ.get("USERNAME", "Munees007")
OUT = os.environ.get("OUT_DIR", "assets/cards")

BG, BORDER = "#111114", "#27272A"
RED, RED2, TEXT, MUTED = "#DC2626", "#EF4444", "#F4F4F5", "#A1A1AA"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
LANG_COLORS = ["#DC2626", "#EF4444", "#F87171", "#FCA5A5", "#A1A1AA", "#52525B"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        nameWithOwner
        isArchived
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def fetch(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload or not payload.get("data", {}).get("user"):
        sys.exit(f"GraphQL error: {payload.get('errors') or 'user not found'}")
    return payload["data"]["user"]


def mock():
    days = [{"date": f"2026-10-{d:02d}", "contributionCount": (d * 7) % 9} for d in range(1, 32)]
    return {
        "pullRequests": {"totalCount": 3},
        "issues": {"totalCount": 1},
        "contributionsCollection": {
            "totalCommitContributions": 100,
            "contributionCalendar": {"totalContributions": 123, "weeks": [{"contributionDays": days}]},
        },
        "repositories": {
            "totalCount": 2,
            "nodes": [
                {"nameWithOwner": "Munees007/demo", "isArchived": False, "stargazerCount": 0, "languages": {"edges": [
                    {"size": 5000, "node": {"name": "TypeScript"}},
                    {"size": 3000, "node": {"name": "C#"}},
                    {"size": 1500, "node": {"name": "CSS"}}]}}
            ],
        },
    }


def frame(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="8" fill="{BG}" stroke="{BORDER}"/>
  <text x="25" y="35" font-family="{FONT}" font-size="18" font-weight="600" fill="{RED2}">{escape(title)}</text>
{body}
</svg>
"""


def stats_card(u):
    cc = u["contributionsCollection"]
    stars = sum(n["stargazerCount"] for n in u["repositories"]["nodes"])
    rows = [
        ("Contributions (last year)", cc["contributionCalendar"]["totalContributions"]),
        ("Commits (last year)", cc["totalCommitContributions"]),
        ("Pull requests", u["pullRequests"]["totalCount"]),
        ("Issues", u["issues"]["totalCount"]),
        ("Public repositories", u["repositories"]["totalCount"]),
        ("Stars earned", stars),
    ]
    body = ""
    for i, (label, val) in enumerate(rows):
        y = 68 + i * 20
        body += (
            f'  <circle cx="30" cy="{y-5}" r="3" fill="{RED}"/>\n'
            f'  <text x="42" y="{y}" font-family="{FONT}" font-size="13" fill="{MUTED}">{escape(label)}</text>\n'
            f'  <text x="440" y="{y}" font-family="{FONT}" font-size="13" font-weight="600" fill="{TEXT}" text-anchor="end">{val:,}</text>\n'
        )
    return frame(495, 195, f"{USER}'s GitHub Stats", body)


def langs_card(u):
    # Optional: skip repos, e.g. EXCLUDE_REPOS="Munees007/old-repo,Munees007/other"
    excluded = {r.strip().lower() for r in os.environ.get("EXCLUDE_REPOS", "").split(",") if r.strip()}
    totals = {}
    print("--- language bytes per repo (shows where each language comes from) ---")
    for repo in u["repositories"]["nodes"]:
        name = repo.get("nameWithOwner", "?")
        langs = {e["node"]["name"]: e["size"] for e in repo["languages"]["edges"]}
        if langs:
            top = ", ".join(f"{k}={v:,}" for k, v in sorted(langs.items(), key=lambda kv: -kv[1])[:4])
            print(f"{name}{' [archived]' if repo.get('isArchived') else ''}{' [EXCLUDED]' if name.lower() in excluded else ''}: {top}")
        if name.lower() in excluded:
            continue
        for k, v in langs.items():
            totals[k] = totals.get(k, 0) + v
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
    total = sum(s for _, s in ranked) or 1
    body = ""
    x = 25.0
    bar_w = 445.0
    for i, (name, size) in enumerate(ranked):
        w = bar_w * size / total
        body += f'  <rect x="{x:.2f}" y="55" width="{max(w,1):.2f}" height="10" fill="{LANG_COLORS[i]}"/>\n'
        x += w
    # round the ends of the bar via a clip
    body = (f'  <clipPath id="bar"><rect x="25" y="55" width="{bar_w}" height="10" rx="5"/></clipPath>\n'
            f'  <g clip-path="url(#bar)">\n{body}  </g>\n')
    for i, (name, size) in enumerate(ranked):
        col, row = i % 2, i // 2
        cx, cy = 25 + col * 225, 92 + row * 26
        body += (
            f'  <circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{LANG_COLORS[i]}"/>\n'
            f'  <text x="{cx+16}" y="{cy}" font-family="{FONT}" font-size="13" fill="{TEXT}">{escape(name)}'
            f'<tspan dx="8" fill="{MUTED}">{size*100/total:.1f}%</tspan></text>\n'
        )
    if not ranked:
        body += f'  <text x="25" y="100" font-family="{FONT}" font-size="13" fill="{MUTED}">No language data yet</text>\n'
    return frame(495, 195, "Top Languages", body)


def activity_card(u):
    days = [d for w in u["contributionsCollection"]["contributionCalendar"]["weeks"]
            for d in w["contributionDays"]]
    days = days[-31:]
    W, H = 900, 300
    L, R, T, B = 55, 30, 60, 45
    pw, ph = W - L - R, H - T - B
    peak = max([d["contributionCount"] for d in days] + [1])
    n = max(len(days) - 1, 1)
    pts = [(L + pw * i / n, T + ph * (1 - d["contributionCount"] / peak)) for i, d in enumerate(days)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{L},{T+ph} {line} {L+pw},{T+ph}"
    body = f'  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{RED}" stop-opacity="0.45"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></linearGradient></defs>\n'
    for k in range(5):
        gy = T + ph * k / 4
        val = round(peak * (1 - k / 4))
        body += (f'  <line x1="{L}" y1="{gy:.1f}" x2="{L+pw}" y2="{gy:.1f}" stroke="{BORDER}" stroke-dasharray="3 4"/>\n'
                 f'  <text x="{L-10}" y="{gy+4:.1f}" font-family="{FONT}" font-size="11" fill="{MUTED}" text-anchor="end">{val}</text>\n')
    body += f'  <polygon points="{area}" fill="url(#g)"/>\n'
    body += f'  <polyline points="{line}" fill="none" stroke="{RED}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>\n'
    for (x, y) in pts:
        body += f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{TEXT}"/>\n'
    for i in range(0, len(days), 5):
        dt = date.fromisoformat(days[i]["date"])
        body += (f'  <text x="{pts[i][0]:.1f}" y="{H-18}" font-family="{FONT}" font-size="11" fill="{MUTED}" text-anchor="middle">'
                 f'{dt.strftime("%b")} {dt.day}</text>\n')
    return frame(W, H, "Contribution Activity (last 31 days)", body)


def main():
    if "--mock" in sys.argv:
        data = mock()
    else:
        token = os.environ.get("GH_TOKEN")
        if not token:
            sys.exit("GH_TOKEN is not set")
        data = fetch(token)
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("stats", stats_card), ("langs", langs_card), ("activity", activity_card)):
        with open(os.path.join(OUT, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(fn(data))
        print("wrote", name)


if __name__ == "__main__":
    main()
