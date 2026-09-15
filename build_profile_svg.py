#!/usr/bin/env python3
"""Render a compact banner SVG for the GitHub profile README.

Two files, one per colour scheme, embedded in the README through <picture>.
GitHub serves README images through a proxy: no scripts, no external fonts,
no CSS classes are guaranteed - so every value is a presentation attribute
and the type falls back to whatever monospace the reader has.

Private repositories always appear under a pseudonym here; the profile is public.
"""
import json, sys, os

DATA = sys.argv[1] if len(sys.argv) > 1 else "dashboard-data.json"
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else "."
D = json.load(open(DATA))
T = D["totals"]
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"

THEMES = {
    "light": dict(bg="#fbfbf9", panel="#f2f2ee", line="#dededa", ink="#16170f",
                  muted="#5c5f52", dim="#8a8d80",
                  signed="#2a78d6", session="#86b6ef", manual="#d95926", aqua="#1baf7a",
                  ramp=["#ecece7", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]),
    "dark": dict(bg="#111310", panel="#171914", line="#272b23", ink="#e8e9e2",
                 muted="#9aa093", dim="#6d7366",
                 signed="#3987e5", session="#6da7ec", manual="#d95926", aqua="#199e70",
                 ramp=["#1c1f19", "#143a63", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"]),
}

MONTHS = D["months"]
MLAB = [{"01": "J", "02": "F", "03": "M", "04": "A", "05": "M", "06": "J", "07": "J",
         "08": "A", "09": "S", "10": "O", "11": "N", "12": "D"}[m[5:7]] for m in MONTHS]
DE_M = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
def de(n): return f"{n:,}".replace(",", ".")
def esc(s): return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

alias, n = {}, 0
for row in D["matrix"]:
    if row.get("private"):
        alias[row["repo"]] = "Projekt " + chr(65 + n); n += 1
def label(r): return alias.get(r, r)

W = 880
PAD = 26
ROWS = 10


def txt(x, y, s, size, fill, anchor="start", weight="400", ls=None):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    l = f' letter-spacing="{ls}"' if ls else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}"{a}{l}>{esc(s)}</text>')


def build(theme):
    C = THEMES[theme]
    o = []
    y = PAD + 14

    # header
    o.append(txt(PAD, y, "github · elgarno", 14, C["ink"], weight="600", ls="2.2"))
    o.append(txt(W - PAD, y, f"Stand {T['last_commit']}", 10, C["dim"], anchor="end"))
    y += 12
    o.append(txt(PAD, y, f"{de(T['commits_window'])} Commits in 24 Monaten · {T['repos_window']} Projekte",
                 10.5, C["muted"]))
    y += 14
    o.append(f'<line x1="{PAD}" y1="{y}" x2="{W-PAD}" y2="{y}" stroke="{C["line"]}" stroke-width="1"/>')

    # KPI row
    y += 22
    kpis = [("Commits", de(T["commits_window"]), ""),
            ("Mit Claude Code", f"{T['claude_session_window']/T['commits_window']*100:.0f}", "%"),
            ("Aufwand", de(T["hours_window"]), "h"),
            ("Parallel max.", str(T["peak_parallel"]), "Proj.")]
    cw = (W - 2 * PAD) / 4
    for i, (l, v, u) in enumerate(kpis):
        x = PAD + i * cw
        o.append(txt(x, y, l.upper(), 8.5, C["dim"], ls="1.3"))
        o.append(txt(x, y + 24, v, 26, C["ink"], weight="600"))
        if u:
            o.append(txt(x + len(v) * 15.6 + 5, y + 24, u, 11, C["muted"]))
    y += 42

    # monthly commits
    ch, pad_l = 116, 30
    iw = W - PAD * 2 - pad_l
    step = iw / len(MONTHS); bw = step * 0.62
    mx = 600.0
    base = y + ch
    for gy in (0, 300, 600):
        gy_y = base - (gy / mx) * ch
        o.append(f'<line x1="{PAD+pad_l}" y1="{gy_y:.1f}" x2="{W-PAD}" y2="{gy_y:.1f}" '
                 f'stroke="{C["line"]}" stroke-width="1"/>')
        o.append(txt(PAD + pad_l - 6, gy_y + 3, str(gy), 8, C["dim"], anchor="end"))
    for i in range(len(MONTHS)):
        tot = D["commits_total"][i]
        if not tot: continue
        sg, ss = D["commits_claude"][i], D["commits_claude_session"][i]
        x = PAD + pad_l + i * step + (step - bw) / 2
        cum = 0
        for val, col in ((tot - sg - ss, C["manual"]), (ss, C["session"]), (sg, C["signed"])):
            if val <= 0: continue
            y_top = base - ((cum + val) / mx) * ch
            y_bot = base - (cum / mx) * ch
            gap = 1.5 if cum > 0 and (y_bot - y_top) > 3 else 0
            o.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bw:.1f}" '
                     f'height="{max(y_bot-gap-y_top,0.5):.1f}" fill="{col}" rx="1"/>')
            cum += val
    for i, l in enumerate(MLAB):
        o.append(txt(PAD + pad_l + i * step + step / 2, base + 12, l, 7.5, C["dim"], anchor="middle"))
    seen = set()
    for i, m in enumerate(MONTHS):
        if m[:4] not in seen:
            seen.add(m[:4])
            o.append(txt(PAD + pad_l + i * step + step / 2, base + 22, m[:4], 7.5, C["muted"],
                         anchor="middle", ls="0.7"))
    y = base + 34

    # legend
    lx = PAD
    for col, lab in ((C["signed"], "Claude Code, signiert"), (C["session"], "gleiche Session"),
                     (C["manual"], "ohne Claude-Bezug")):
        o.append(f'<rect x="{lx}" y="{y-7}" width="8" height="8" fill="{col}" rx="1.5"/>')
        o.append(txt(lx + 12, y, lab, 9, C["muted"]))
        lx += 13 + len(lab) * 5.4 + 20
    y += 22

    # activity matrix
    namew = 118
    R = D["matrix"][:ROWS]
    cols = len(MONTHS); mcw = (W - PAD * 2 - namew) / cols; rh = 14
    o.append(txt(PAD, y, "PROJEKT-AKTIVITÄT", 8.5, C["dim"], ls="1.3"))
    y += 10
    for r, row in enumerate(R):
        ry = y + r * rh
        o.append(txt(PAD, ry + rh * 0.72, label(row["repo"])[:19], 8.5, C["ink"]))
        for j, v in enumerate(row["v"]):
            k = 0 if v == 0 else 1 if v < 3 else 2 if v < 8 else 3 if v < 20 else 4 if v < 50 else 5 if v < 120 else 6
            o.append(f'<rect x="{PAD+namew+j*mcw:.1f}" y="{ry:.1f}" width="{mcw-1.5:.1f}" '
                     f'height="{rh-2.5}" fill="{C["ramp"][k]}" rx="1.5"/>')
    y += rh * len(R) + 14

    o.append(f'<line x1="{PAD}" y1="{y}" x2="{W-PAD}" y2="{y}" stroke="{C["line"]}" stroke-width="1"/>')
    y += 14
    o.append(txt(PAD, y, "Private Repositories erscheinen als Projekt A, B, C — Zahlen sind echt.",
                 8.5, C["dim"]))
    o.append(txt(W - PAD, y, f"{de(T['hours_window'])} h geschätzt · {T['sessions_window']} Sessions",
                 8.5, C["dim"], anchor="end"))
    H = y + PAD - 6

    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:.0f}" '
            f'viewBox="0 0 {W} {H:.0f}" role="img" '
            f'aria-label="GitHub-Statistik: {de(T["commits_window"])} Commits in 24 Monaten">'
            f'<rect width="{W}" height="{H:.0f}" fill="{C["bg"]}" rx="6"/>')
    return head + "".join(o) + "</svg>"


for theme in THEMES:
    path = os.path.join(OUTDIR, f"profile-banner-{theme}.svg")
    open(path, "w", encoding="utf-8").write(build(theme))
    print(f"wrote {path} ({os.path.getsize(path)} bytes)")
