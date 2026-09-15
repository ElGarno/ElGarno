#!/usr/bin/env python3
"""Aggregate GitHub commit history into dashboard data.

Reads bare clones from a repo directory, filters to the owner's own commits,
and writes one JSON file with every series the dashboard renders.
"""
import subprocess, os, json, re, sys, collections
from datetime import datetime, timedelta, timezone

REPO_DIR = sys.argv[1] if len(sys.argv) > 1 else "repos"
OUT = sys.argv[2] if len(sys.argv) > 2 else "dashboard-data.json"
WINDOW_START = "2024-10"
SESSION_GAP = timedelta(hours=2)
SESSION_LEAD = 0.5  # hours of pre-work credited to each session

OWN_MAIL = {"f.woerenkaemper@krombacher.de", "faffi@gmx.de",
            "31306356+elgarno@users.noreply.github.com"}
OWN_NAME = {"faffi", "fabian wörenkämper", "elgarno"}
CLAUDE_MAIL = {"noreply@anthropic.com"}
CLAUDE_MSG = re.compile(r"co-authored-by:\s*claude|generated with \[?claude code", re.I)

VENDOR = re.compile(r"(^|/)(node_modules|dist|build|\.next|vendor|venv|\.venv|site-packages)/|"
                    r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|uv\.lock|poetry\.lock|"
                    r"Cargo\.lock|Gemfile\.lock)$|\.min\.(js|css)$|"
                    r"\.(png|jpg|jpeg|gif|svg|ico|pdf|woff2?|ttf|otf|mp4|mov|zip|parquet|db|sqlite3?|csv|xlsx)$")

CODE_EXT = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
            ".ts": "TypeScript", ".tsx": "TypeScript", ".swift": "Swift", ".go": "Go",
            ".r": "R", ".java": "Java", ".rb": "Ruby", ".sh": "Shell", ".zsh": "Shell",
            ".sql": "SQL", ".css": "CSS", ".scss": "CSS", ".html": "HTML", ".vue": "JavaScript"}
PROSE_EXT = {".md", ".txt", ".rst"}
CONFIG_EXT = {".json", ".yml", ".yaml", ".toml", ".ini", ".cfg"}


def git(repo, *args, binary=False):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True,
                       text=not binary, errors=None if binary else "replace", timeout=600)
    return r.stdout


def collect_commits(repo_dir):
    """One record per own commit, deduplicated across branches."""
    fmt = "\x01%H\x1f%ae\x1f%an\x1f%aI\x1f%B\x02"
    out, seen = [], set()
    for d in sorted(os.listdir(repo_dir)):
        if not d.endswith(".git"):
            continue
        repo, path = d[:-4], os.path.join(repo_dir, d)
        try:
            log = git(path, "log", "--all", "--no-merges", f"--format={fmt}", "--numstat")
        except Exception as e:
            print(f"  skip {repo}: {e}", file=sys.stderr)
            continue
        for chunk in log.split("\x01")[1:]:
            head, _, stats = chunk.partition("\x02")
            parts = head.split("\x1f")
            if len(parts) < 5:
                continue
            sha, email, name, iso, msg = parts[0], parts[1].lower(), parts[2].lower(), parts[3], parts[4]
            if sha in seen:
                continue
            seen.add(sha)
            by_claude_author = email in CLAUDE_MAIL
            if not (email in OWN_MAIL or name in OWN_NAME or by_claude_author):
                continue
            add = dele = 0
            for line in stats.strip().split("\n"):
                f = line.split("\t")
                if len(f) != 3 or f[0] == "-" or VENDOR.search(f[2]):
                    continue
                try:
                    add += int(f[0]); dele += int(f[1])
                except ValueError:
                    pass
            out.append({"repo": repo, "ts": iso, "add": add, "del": dele,
                        "claude": bool(by_claude_author or CLAUDE_MSG.search(msg))})
    out.sort(key=lambda c: c["ts"])
    return out


def count_lines(repo_dir):
    """Lines in each repo's current HEAD, split into code / prose / config.

    Notebooks are parsed so that only code-cell source counts as code -
    stored outputs would otherwise dwarf every real language.
    """
    lang, kind, per_repo = collections.Counter(), collections.Counter(), collections.Counter()
    for d in sorted(os.listdir(repo_dir)):
        if not d.endswith(".git"):
            continue
        repo, path = d[:-4], os.path.join(repo_dir, d)
        try:
            files = git(path, "ls-tree", "-r", "--name-only", "HEAD").split("\n")
        except Exception:
            continue
        for f in files:
            if not f or VENDOR.search(f):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in CODE_EXT and ext not in PROSE_EXT and ext not in CONFIG_EXT and ext != ".ipynb":
                continue
            try:
                blob = git(path, "show", f"HEAD:{f}", binary=True)
            except Exception:
                continue
            if ext == ".ipynb":
                try:
                    nb = json.loads(blob.decode("utf-8", "replace"))
                except Exception:
                    continue
                for cell in nb.get("cells", []):
                    n = len(cell.get("source", []))
                    if cell.get("cell_type") == "code":
                        lang["Python (Notebook)"] += n; kind["code"] += n; per_repo[repo] += n
                    elif cell.get("cell_type") == "markdown":
                        kind["prose"] += n
                continue
            n = blob.count(b"\n")
            if ext in CODE_EXT:
                lang[CODE_EXT[ext]] += n; kind["code"] += n; per_repo[repo] += n
            elif ext in PROSE_EXT:
                kind["prose"] += n
            else:
                kind["config"] += n
    return lang, kind, per_repo


def claude_sessions(commits):
    """Mark commits that share a work session with a signed commit.

    The Co-Authored-By trailer is a lower bound: plenty of Claude Code sessions
    committed without it. A commit inside a <=SESSION_GAP cluster that contains
    at least one signed commit is counted as session-attributed.
    """
    by_repo = collections.defaultdict(list)
    for c in commits:
        by_repo[c["repo"]].append(c)
    for cs in by_repo.values():
        cs.sort(key=lambda c: c["dt"])
        cur = [cs[0]]
        for c in cs[1:]:
            if c["dt"] - cur[-1]["dt"] > SESSION_GAP:
                flag = any(x["claude"] for x in cur)
                for x in cur:
                    x["claude_session"] = flag
                cur = []
            cur.append(c)
        flag = any(x["claude"] for x in cur)
        for x in cur:
            x["claude_session"] = flag


def sessions(dates):
    """Cluster timestamps into work sessions; return (hours, session count)."""
    if not dates:
        return 0.0, 0
    dates = sorted(dates)
    hours, count, start, prev = 0.0, 1, dates[0], dates[0]
    for d in dates[1:]:
        if d - prev > SESSION_GAP:
            hours += (prev - start).total_seconds() / 3600 + SESSION_LEAD
            count += 1
            start = d
        prev = d
    hours += (prev - start).total_seconds() / 3600 + SESSION_LEAD
    return hours, count


def months_between(first, last):
    out, y, m = [], int(first[:4]), int(first[5:7])
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def main():
    print(f"reading {REPO_DIR} ...")
    commits = collect_commits(REPO_DIR)
    for c in commits:
        c["dt"] = datetime.fromisoformat(c["ts"]).astimezone(timezone.utc)
    last_month = commits[-1]["ts"][:7]
    months = months_between(WINDOW_START, last_month)
    midx = {m: i for i, m in enumerate(months)}
    win = [c for c in commits if c["ts"][:7] in midx]
    claude_sessions(win)

    total = [0] * len(months); claude = [0] * len(months); csess = [0] * len(months)
    active = [set() for _ in months]; started = [0] * len(months)
    matrix = collections.defaultdict(lambda: [0] * len(months))
    for c in win:
        i = midx[c["ts"][:7]]
        total[i] += 1
        claude[i] += c["claude"]
        csess[i] += c["claude_session"] and not c["claude"]
        active[i].add(c["repo"])
        matrix[c["repo"]][i] += 1
    first_seen = {}
    for c in commits:
        first_seen.setdefault(c["repo"], c["ts"][:7])
    for r, m in first_seen.items():
        if m in midx:
            started[midx[m]] += 1

    # effort per repo, all time and in-window
    by_repo = collections.defaultdict(list); by_repo_win = collections.defaultdict(list)
    for c in commits:
        by_repo[c["repo"]].append(c["dt"])
    for c in win:
        by_repo_win[c["repo"]].append(c["dt"])
    effort = {r: sessions(d) for r, d in by_repo.items()}
    effort_win = {r: sessions(d) for r, d in by_repo_win.items()}

    # context switching: distinct repos touched per active day, and switches between
    # consecutive commits on the same day
    per_day = collections.defaultdict(list)
    for c in sorted(win, key=lambda c: c["dt"]):
        per_day[c["dt"].strftime("%Y-%m-%d")].append(c["repo"])
    switch_month = collections.Counter(); day_month = collections.Counter()
    multi_days = 0
    for day, repos in per_day.items():
        m = day[:7]
        day_month[m] += 1
        switch_month[m] += sum(1 for a, b in zip(repos, repos[1:]) if a != b)
        if len(set(repos)) > 1:
            multi_days += 1

    # weekday x hour (local time, Europe/Berlin ~ UTC+1/+2; git stores the offset)
    heat = [[0] * 24 for _ in range(7)]
    for c in win:
        local = datetime.fromisoformat(c["ts"])
        heat[local.weekday()][local.hour] += 1

    print("counting lines ...")
    lang, kind, loc_repo = count_lines(REPO_DIR)

    vis_path = os.path.join(os.path.dirname(os.path.abspath(OUT)), "visibility.json")
    vis = json.load(open(vis_path)) if os.path.exists(vis_path) else {}

    top = sorted(matrix, key=lambda r: -sum(matrix[r]))
    data = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "months": months,
        "commits_total": total,
        "commits_claude": claude,
        "commits_claude_session": csess,
        "active_repos": [len(s) for s in active],
        "repos_started": started,
        "switches_per_day": [round(switch_month[m] / day_month[m], 2) if day_month[m] else 0
                             for m in months],
        "active_days": [day_month[m] for m in months],
        "matrix": [{"repo": r, "v": matrix[r], "total": sum(matrix[r]),
                    "private": bool(vis.get(r, False))} for r in top],
        "effort": sorted(([r, round(h, 1), n, len(by_repo[r]), bool(vis.get(r, False))]
                          for r, (h, n) in effort.items()), key=lambda x: -x[1]),
        "effort_window": sorted(([r, round(h, 1), n] for r, (h, n) in effort_win.items()),
                                key=lambda x: -x[1]),
        "heat": heat,
        "lang": lang.most_common(),
        "line_kinds": dict(kind),
        "loc_repo": loc_repo.most_common(20),
        "totals": {
            "commits_all": len(commits),
            "commits_window": len(win),
            "repos_all": len(by_repo),
            "repos_window": len(matrix),
            "claude_all": sum(c["claude"] for c in commits),
            "claude_window": sum(claude),
            "claude_session_window": sum(claude) + sum(csess),
            "hours_all": round(sum(h for h, _ in effort.values())),
            "hours_window": round(sum(h for h, _ in effort_win.values())),
            "sessions_all": sum(n for _, n in effort.values()),
            "sessions_window": sum(n for _, n in effort_win.values()),
            "active_days_window": len(per_day),
            "multi_repo_days": multi_days,
            "first_commit": commits[0]["ts"][:10],
            "last_commit": commits[-1]["ts"][:10],
            "peak_parallel": max(len(s) for s in active),
            "peak_parallel_month": months[max(range(len(active)), key=lambda i: len(active[i]))],
            "peak_month": months[total.index(max(total))],
            "peak_month_commits": max(total),
            "lines_code": kind["code"],
        },
    }
    json.dump(data, open(OUT, "w"), ensure_ascii=False)
    t = data["totals"]
    print(f"\n{t['commits_all']} commits / {t['repos_all']} repos  ({t['first_commit']} .. {t['last_commit']})")
    print(f"window {months[0]}..{months[-1]}: {t['commits_window']} commits, {t['repos_window']} repos")
    print(f"claude signed: {t['claude_window']} of {t['commits_window']} in window "
          f"({t['claude_window']/t['commits_window']*100:.0f}%)")
    print(f"claude session-attributed: {t['claude_session_window']} "
          f"({t['claude_session_window']/t['commits_window']*100:.0f}%)")
    print(f"effort: {t['hours_all']} h / {t['sessions_all']} sessions all time; "
          f"{t['hours_window']} h / {t['sessions_window']} sessions in window")
    print(f"active days in window: {t['active_days_window']}, of which multi-repo: {t['multi_repo_days']}")
    print(f"peak: {t['peak_month_commits']} commits in {t['peak_month']}; "
          f"{t['peak_parallel']} parallel repos in {t['peak_parallel_month']}")
    print(f"code lines: {t['lines_code']:,} (prose {kind['prose']:,}, config {kind['config']:,})")
    print("languages:", ", ".join(f"{k} {v:,}" for k, v in data["lang"][:8]))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
