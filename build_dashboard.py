#!/usr/bin/env python3
"""Render dashboard-data.json into a standalone HTML dashboard."""
import json, sys, os

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
ANON = "--anonymize" in sys.argv[1:]
DATA = ARGS[0] if ARGS else "dashboard-data.json"
OUT = ARGS[1] if len(ARGS) > 1 else "commit-dashboard.html"
D = json.load(open(DATA))
T = D["totals"]

# Private repositories get a stable pseudonym when the page is meant to be
# published: the activity pattern stays readable, the project names do not leak.
_alias, _n = {}, 0
for _row in D["matrix"]:
    if _row.get("private") and _row["repo"] not in _alias:
        _alias[_row["repo"]] = "Projekt " + chr(65 + _n); _n += 1
for _e in D["effort"]:
    if len(_e) > 4 and _e[4] and _e[0] not in _alias:
        _alias[_e[0]] = "Projekt " + chr(65 + _n); _n += 1


def label(repo):
    return _alias.get(repo, repo) if ANON else repo

BG, PANEL, LINE, INK, MUTED, DIM = "#111310", "#171914", "#272b23", "#e8e9e2", "#9aa093", "#6d7366"
SIGNED, SESSION, MANUAL, AQUA = "#3987e5", "#6da7ec", "#d95926", "#199e70"
RAMP = ["#1c1f19", "#143a63", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"]
CAT = [SIGNED, MANUAL, AQUA, "#c98500", "#d55181", "#008300", "#9085e9", "#e66767", "#4a4e44"]

MONTHS = D["months"]
MLAB = [{"01": "J", "02": "F", "03": "M", "04": "A", "05": "M", "06": "J", "07": "J",
         "08": "A", "09": "S", "10": "O", "11": "N", "12": "D"}[m[5:7]] for m in MONTHS]
DE_M = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
def mname(m): return f"{DE_M[int(m[5:7])-1]} {m[:4]}"
def de(n): return f"{n:,}".replace(",", ".")
def esc(s): return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                     .replace('"', "&quot;"))


def year_ticks(pad_l, step):
    out, seen = [], set()
    for i, m in enumerate(MONTHS):
        if m[:4] not in seen:
            seen.add(m[:4]); out.append((pad_l + i * step + step / 2, m[:4]))
    return out


def timeline():
    w, h = 1180, 250
    pad_l, pad_b, pad_t = 38, 30, 12
    iw, ih = w - pad_l - 6, h - pad_b - pad_t
    n = len(MONTHS); step = iw / n; bw = step * 0.64
    mx = 600.0
    p = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="Commits pro Monat">']
    for gy in (0, 200, 400, 600):
        y = pad_t + ih - (gy / mx) * ih
        p.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-6}" y2="{y:.1f}" stroke="{LINE}" stroke-width="1"/>')
        p.append(f'<text x="{pad_l-7}" y="{y+3.5:.1f}" text-anchor="end" class="ax">{gy}</text>')
    for i, m in enumerate(MONTHS):
        tot = D["commits_total"][i]
        if tot == 0: continue
        sg, ss = D["commits_claude"][i], D["commits_claude_session"][i]
        mn = tot - sg - ss
        x = pad_l + i * step + (step - bw) / 2
        base = pad_t + ih
        tip = (f"{mname(m)} · {de(tot)} Commits|{de(sg)} signiert · {de(ss)} gleiche Session · "
               f"{de(mn)} ohne Bezug")
        # Segment edges stay on the scale; the 2px separator is taken out of the
        # segment's own height, so the bar top still reads its true total.
        cum = 0
        for val, col in ((mn, MANUAL), (ss, SESSION), (sg, SIGNED)):
            if val <= 0: continue
            y_top = base - ((cum + val) / mx) * ih
            y_bot = base - (cum / mx) * ih
            gap = 2 if cum > 0 and (y_bot - y_top) > 3 else 0
            bh = max(y_bot - gap - y_top, 0.6)
            p.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                     f'fill="{col}" rx="1" data-tip="{esc(tip)}"/>')
            cum += val
        p.append(f'<rect x="{x:.1f}" y="{pad_t}" width="{bw:.1f}" height="{ih:.1f}" '
                 f'fill="transparent" data-tip="{esc(tip)}"/>')
    for i, l in enumerate(MLAB):
        p.append(f'<text x="{pad_l+i*step+step/2:.1f}" y="{h-16}" text-anchor="middle" class="ax">{l}</text>')
    for x, yr in year_ticks(pad_l, step):
        p.append(f'<text x="{x:.1f}" y="{h-3}" text-anchor="middle" class="yr">{yr}</text>')
    p.append('</svg>')
    return "".join(p)


def matrix(rows=14):
    R = D["matrix"][:rows]
    w, rowh, namew = 1180, 21, 210
    cols = len(MONTHS); cw = (w - namew) / cols
    h = rowh * len(R) + 16
    p = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="Projekt-Aktivität pro Monat">']
    for i, row in enumerate(R):
        y = i * rowh
        p.append(f'<text x="0" y="{y+rowh*0.72:.1f}" class="rowlab">{esc(label(row["repo"])[:28])}</text>')
        for j, v in enumerate(row["v"]):
            x = namew + j * cw
            k = 0 if v == 0 else 1 if v < 3 else 2 if v < 8 else 3 if v < 20 else 4 if v < 50 else 5 if v < 120 else 6
            rl = esc(label(row["repo"]))
            tip = f"{rl} · {mname(MONTHS[j])}|{de(v)} Commits" if v else \
                  f"{rl} · {mname(MONTHS[j])}|kein Commit"
            p.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw-2:.1f}" height="{rowh-3}" '
                     f'fill="{RAMP[k]}" rx="1.5" data-tip="{tip}"/>')
    yb = rowh * len(R) + 11
    for i, l in enumerate(MLAB):
        p.append(f'<text x="{namew+i*cw+cw/2-1:.1f}" y="{yb}" text-anchor="middle" class="ax">{l}</text>')
    p.append('</svg>')
    return "".join(p)


def parallel():
    w, h = 560, 150
    pad_l, pad_b, pad_t = 26, 22, 10
    iw, ih = w - pad_l - 6, h - pad_b - pad_t
    v = D["active_repos"]; n = len(v); step = iw / (n - 1); mx = float(max(v) + 1)
    pts = [(pad_l + i * step, pad_t + ih - (x / mx) * ih) for i, x in enumerate(v)]
    d = " ".join(f"{'M' if i==0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    p = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="Parallel aktive Projekte">']
    for gy in range(0, int(mx) + 1, 2):
        y = pad_t + ih - (gy / mx) * ih
        p.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-6}" y2="{y:.1f}" stroke="{LINE}" stroke-width="1"/>')
        p.append(f'<text x="{pad_l-7}" y="{y+3.5:.1f}" text-anchor="end" class="ax">{gy}</text>')
    p.append(f'<path d="{d} L{pts[-1][0]:.1f},{pad_t+ih:.1f} L{pad_l},{pad_t+ih:.1f} Z" fill="{AQUA}" opacity="0.14"/>')
    p.append(f'<path d="{d}" fill="none" stroke="{AQUA}" stroke-width="2" stroke-linejoin="round"/>')
    for i, (x, y) in enumerate(pts):
        tip = (f"{mname(MONTHS[i])}|{v[i]} Projekte · {D['active_days'][i]} aktive Tage · "
               f"{D['switches_per_day'][i]:.1f} Wechsel/Tag")
        p.append(f'<rect x="{x-step/2:.1f}" y="{pad_t}" width="{step:.1f}" height="{ih:.1f}" '
                 f'fill="transparent" data-tip="{esc(tip)}"/>')
    mxi = v.index(max(v))
    p.append(f'<circle cx="{pts[mxi][0]:.1f}" cy="{pts[mxi][1]:.1f}" r="4" fill="{AQUA}"/>')
    for i, l in enumerate(MLAB):
        if i % 2: continue
        p.append(f'<text x="{pad_l+i*step:.1f}" y="{h-8}" text-anchor="middle" class="ax">{l}</text>')
    p.append('</svg>')
    return "".join(p)


def switches():
    """Project switches per active day, per month."""
    w, h = 560, 128
    pad_l, pad_b, pad_t = 26, 20, 10
    iw, ih = w - pad_l - 6, h - pad_b - pad_t
    v = D["switches_per_day"]; n = len(v); step = iw / n; bw = step * 0.6
    mx = max(max(v), 1.0) * 1.12
    p = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="Projektwechsel je aktivem Tag">']
    for gy in (0, 1, 2):
        if gy > mx: continue
        y = pad_t + ih - (gy / mx) * ih
        p.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-6}" y2="{y:.1f}" stroke="{LINE}" stroke-width="1"/>')
        p.append(f'<text x="{pad_l-7}" y="{y+3.5:.1f}" text-anchor="end" class="ax">{gy}</text>')
    for i, val in enumerate(v):
        x = pad_l + i * step + (step - bw) / 2
        yb = pad_t + ih
        tip = (f"{mname(MONTHS[i])}|{val:.1f} Wechsel je aktivem Tag · "
               f"{D['active_days'][i]} aktive Tage")
        if val > 0:
            bh = (val / mx) * ih
            p.append(f'<rect x="{x:.1f}" y="{yb-bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                     f'fill="{AQUA}" rx="1" data-tip="{esc(tip)}"/>')
        p.append(f'<rect x="{x:.1f}" y="{pad_t}" width="{bw:.1f}" height="{ih:.1f}" '
                 f'fill="transparent" data-tip="{esc(tip)}"/>')
    for i, l in enumerate(MLAB):
        if i % 2: continue
        p.append(f'<text x="{pad_l+i*step+step/2:.1f}" y="{h-6}" text-anchor="middle" class="ax">{l}</text>')
    p.append('</svg>')
    return "".join(p)


def effort(n=12):
    E = D["effort"][:n]; rest = D["effort"][n:]
    rows = [[label(e[0]), e[1], e[2], e[3]] for e in E]
    if rest:
        rows.append(["%d weitere Projekte" % len(rest), round(sum(r[1] for r in rest), 1),
                     sum(r[2] for r in rest), sum(r[3] for r in rest)])
    w, rowh, namew = 560, 22, 215
    mx = E[0][1]; bwmax = w - namew - 54
    h = rowh * len(rows)
    p = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="Aufwand je Projekt">']
    for i, (name, hrs, sess, cm) in enumerate(rows):
        y = i * rowh; bh = rowh - 9
        last = rest and i == len(rows) - 1
        p.append(f'<text x="0" y="{y+bh*0.8:.1f}" class="rowlab{" dim" if last else ""}">{esc(name[:28])}</text>')
        L = max((hrs / mx) * bwmax, 1)
        tip = f"{esc(name)}|{hrs:.0f} h · {sess} Sessions · {de(cm)} Commits"
        p.append(f'<rect x="{namew}" y="{y:.1f}" width="{L:.1f}" height="{bh}" '
                 f'fill="{DIM if last else SIGNED}" rx="2.5" data-tip="{esc(tip)}"/>')
        p.append(f'<text x="{namew+L+8:.1f}" y="{y+bh*0.8:.1f}" class="barval">{hrs:.0f} h</text>')
    p.append('</svg>')
    return "".join(p)


def heatmap():
    days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    w, cell, namew, top = 560, 0, 30, 14
    cw = (w - namew) / 24; ch = 19
    h = ch * 7 + top + 4
    mx = max(max(r) for r in D["heat"])
    p = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="Commits nach Wochentag und Stunde">']
    for hh in range(0, 24, 3):
        p.append(f'<text x="{namew+hh*cw+cw/2:.1f}" y="{top-4}" text-anchor="middle" class="ax">{hh}</text>')
    for r, day in enumerate(days):
        y = top + r * ch
        p.append(f'<text x="0" y="{y+ch*0.72:.1f}" class="rowlab">{day}</text>')
        for c in range(24):
            v = D["heat"][r][c]
            k = 0 if v == 0 else min(6, 1 + int((v / mx) ** 0.55 * 5.99))
            tip = f"{day} {c:02d}–{c+1:02d} Uhr|{de(v)} Commits"
            p.append(f'<rect x="{namew+c*cw:.1f}" y="{y:.1f}" width="{cw-1.5:.1f}" height="{ch-2}" '
                     f'fill="{RAMP[k]}" rx="1.5" data-tip="{tip}"/>')
    p.append('</svg>')
    return "".join(p)


def languages():
    L = [(k, v) for k, v in D["lang"] if v > 0]
    tot = sum(v for _, v in L)
    w, h = 1180, 17
    p = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="Codezeilen nach Sprache">']
    x = 0.0
    for i, (name, v) in enumerate(L):
        seg = (v / tot) * w
        p.append(f'<rect x="{x:.1f}" y="0" width="{max(seg-2,1):.1f}" height="{h}" '
                 f'fill="{CAT[i%len(CAT)]}" rx="2" data-tip="{esc(name)}|{de(v)} Zeilen · {v/tot*100:.1f} %"/>')
        x += seg
    p.append('</svg>')
    leg = "".join(f'<div class="lg"><span class="sw" style="background:{CAT[i%len(CAT)]}"></span>'
                  f'<span>{esc(k)}</span><span class="lgv">{de(v)}</span></div>'
                  for i, (k, v) in enumerate(L))
    return "".join(p) + f'<div class="legrid">{leg}</div>'


KPIS = [
    ("Commits", de(T["commits_window"]), "",
     f"{de(T['commits_all'])} seit {T['first_commit'][:4]} · {T['repos_window']} Repos aktiv"),
    ("Mit Claude Code", f"{T['claude_session_window']/T['commits_window']*100:.0f}", "%",
     f"{T['claude_window']/T['commits_window']*100:.0f} % signiert, Rest über Session zugeordnet"),
    ("Geschätzter Aufwand", de(T["hours_window"]), "h",
     f"{T['sessions_window']} Sessions an {T['active_days_window']} Tagen"),
    ("Parallel maximal", str(T["peak_parallel"]), "Projekte",
     f"{mname(T['peak_parallel_month'])} · {T['multi_repo_days']} Tage mit Projektwechsel"),
]

kpi_html = "".join(
    f'<div class="kpi"><div class="kl">{l}</div>'
    f'<div class="kv">{v}<span class="ku">{u}</span></div><div class="ks">{s}</div></div>'
    for l, v, u, s in KPIS)

LK = D["line_kinds"]

HTML = f'''<meta charset="utf-8">
<title>Zwei Jahre Commits</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
  :root {{
    --bg:{BG}; --panel:{PANEL}; --line:{LINE}; --ink:{INK}; --muted:{MUTED}; --dim:{DIM};
    --signed:{SIGNED}; --session:{SESSION}; --manual:{MANUAL}; --aqua:{AQUA};
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:"IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size:13px; -webkit-font-smoothing:antialiased;
    font-variant-numeric:tabular-nums;
  }}
  .wrap {{ max-width:1300px; margin:0 auto; padding-block:30px 44px; padding-left:22px; padding-right:22px;
           display:flex; flex-direction:column; gap:20px; }}
  .top {{ display:flex; flex-wrap:wrap; gap:14px; justify-content:space-between; align-items:flex-end;
          border-bottom:1px solid var(--line); padding-bottom:15px; }}
  h1 {{ font-size:15px; font-weight:600; letter-spacing:0.17em; text-transform:uppercase; margin:0; }}
  .sub {{ font-size:11px; color:var(--dim); margin-top:6px; line-height:1.6; }}
  .meta {{ font-size:10.5px; color:var(--dim); text-align:right; line-height:1.7; }}
  .kpis {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:1px;
           background:var(--line); border:1px solid var(--line); }}
  .kpi {{ background:var(--bg); padding:15px 17px; }}
  .kl {{ font-size:9.5px; letter-spacing:0.13em; text-transform:uppercase; color:var(--dim); }}
  .kv {{ font-size:32px; font-weight:600; margin-top:8px; letter-spacing:-0.025em; line-height:1; }}
  .ku {{ font-size:13px; color:var(--muted); margin-left:5px; font-weight:400; letter-spacing:0; }}
  .ks {{ font-size:10.5px; color:var(--muted); margin-top:7px; line-height:1.5; }}
  .card {{ border:1px solid var(--line); padding:16px 18px 14px; display:flex; flex-direction:column; gap:12px; }}
  .chead {{ display:flex; flex-wrap:wrap; gap:10px; justify-content:space-between; align-items:baseline; }}
  .ct {{ font-size:10.5px; letter-spacing:0.14em; text-transform:uppercase; color:var(--muted); }}
  .cnote {{ font-size:10.5px; color:var(--dim); }}
  .leg {{ display:flex; flex-wrap:wrap; gap:15px; font-size:10.5px; color:var(--muted); align-items:center; }}
  .sw {{ width:9px; height:9px; border-radius:2px; display:inline-block; flex:none; }}
  .leg span.sw {{ margin-right:6px; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  .chart {{ width:100%; height:auto; display:block; overflow:visible; }}
  .ax {{ font-size:8.5px; fill:var(--dim); }}
  .yr {{ font-size:8.5px; fill:var(--muted); letter-spacing:0.09em; }}
  .rowlab {{ font-size:10px; fill:var(--ink); }}
  .rowlab.dim {{ fill:var(--dim); }}
  .barval {{ font-size:10px; fill:var(--muted); }}
  .legrid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:7px 20px; font-size:10.5px; }}
  .lg {{ display:flex; align-items:center; gap:7px; }}
  .lgv {{ margin-left:auto; color:var(--dim); }}
  [data-tip] {{ cursor:crosshair; }}
  #tip {{ position:fixed; pointer-events:none; opacity:0; transition:opacity .09s;
          background:#05060420; background:#050604; border:1px solid var(--line);
          padding:7px 10px; font-size:11px; line-height:1.5; z-index:9; max-width:280px;
          box-shadow:0 6px 22px rgba(0,0,0,.55); }}
  #tip b {{ display:block; font-weight:600; color:var(--ink); }}
  #tip span {{ color:var(--muted); }}
  footer {{ border-top:1px solid var(--line); padding-top:14px; font-size:10.5px;
            color:var(--dim); line-height:1.75; }}
  footer b {{ color:var(--muted); font-weight:500; }}
  @media (max-width:820px) {{
    .kpis {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
    .grid2 {{ grid-template-columns:1fr; }}
    .meta {{ text-align:left; }}
  }}
</style>

<div class="wrap">
  <div class="top">
    <div>
      <h1>github · elgarno</h1>
      <div class="sub">{de(T['commits_window'])} Commits in 24 Monaten, {T['repos_window']} Repositories · Gesamthistorie {de(T['commits_all'])} Commits seit {T['first_commit']}</div>
    </div>
    <div class="meta">Stand {T['last_commit']}<br>ohne Forks · ohne Obsidian-Vault<br>eigene Commits, ohne Merges</div>
  </div>

  <div class="kpis">{kpi_html}</div>

  <div class="card">
    <div class="chead">
      <div class="ct">Commits pro Monat</div>
      <div class="leg">
        <span><span class="sw" style="background:{SIGNED}"></span>Claude Code, signiert</span>
        <span><span class="sw" style="background:{SESSION}"></span>gleiche Session</span>
        <span><span class="sw" style="background:{MANUAL}"></span>ohne Claude-Bezug</span>
      </div>
    </div>
    {timeline()}
    <div class="cnote">Ab Dezember 2025 kippt das Verhältnis. Spitze: {de(T['peak_month_commits'])} Commits im {mname(T['peak_month'])} — mehr als die Jahre 2021 bis 2023 zusammen.</div>
  </div>

  <div class="card">
    <div class="chead">
      <div class="ct">Projekt-Aktivität · Commits je Monat</div>
      <div class="cnote">Top {min(14,len(D['matrix']))} von {T['repos_window']} Projekten</div>
    </div>
    {matrix()}
  </div>

  <div class="grid2">
    <div class="card">
      <div class="chead"><div class="ct">Parallel aktive Projekte</div></div>
      {parallel()}
      <div class="cnote">An {T['multi_repo_days']} von {T['active_days_window']} aktiven Tagen wurde an mehr als einem Projekt committet.</div>
      <div class="chead" style="margin-top:4px"><div class="ct">Projektwechsel je aktivem Tag</div></div>
      {switches()}
      <div class="cnote">Ein Wechsel ist ein aufeinanderfolgendes Commit-Paar in verschiedenen Repositories am selben Tag.</div>
    </div>
    <div class="card">
      <div class="chead"><div class="ct">Aufwand je Projekt</div><div class="cnote">Gesamthistorie</div></div>
      {effort()}
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <div class="chead"><div class="ct">Wann committet wird</div><div class="cnote">Wochentag × Stunde, Ortszeit</div></div>
      {heatmap()}
    </div>
    <div class="card">
      <div class="chead"><div class="ct">Codezeilen nach Sprache</div><div class="cnote">{de(LK['code'])} Zeilen Code</div></div>
      {languages()}
      <div class="cnote">Dazu {de(LK['prose'])} Zeilen Prosa (Markdown, Notebook-Text) und {de(LK['config'])} Zeilen Konfiguration — getrennt ausgewiesen, weil sie sonst jede Sprache überdecken.</div>
    </div>
  </div>

  <footer>
    <b>Methode.</b> Bare-Clones aller eigenen GitHub-Repositories, Forks und der Obsidian-Vault ausgenommen. Gezählt werden Commits der eigenen Autoren-Identitäten ohne Merge-Commits, über alle Branches dedupliziert.<br>
    <b>Aufwand.</b> Commits werden zu Sessions geclustert (Lücke über 2 h beginnt eine neue Session); je Session sind 30 Minuten Vorlauf eingerechnet. Das ist eine Schätzung, keine Zeiterfassung — Arbeit ohne Commit fehlt darin.<br>
    <b>Claude-Anteil.</b> {de(T['claude_window'])} Commits tragen einen <i>Co-Authored-By: Claude</i>-Trailer. Das ist die Untergrenze: viele Sessions haben ohne Trailer committet. Als zweite Stufe gilt ein Commit als zugeordnet, wenn er in derselben Session wie ein signierter Commit liegt — zusammen {de(T['claude_session_window'])} Commits.<br>
    {"<b>Projektnamen.</b> Private Repositories erscheinen als <i>Projekt A, B, C …</i> — Aktivität und Aufwand sind echt, nur die Namen sind ersetzt.<br>" if ANON else ""}<b>Zeilen.</b> Stand des aktuellen HEAD, ohne node_modules, Lockfiles, Binärdateien und Build-Artefakte. Notebooks zählen nur mit dem Quelltext ihrer Code-Zellen, nicht mit gespeicherten Ausgaben.
  </footer>
</div>

<div id="tip" role="status" aria-live="polite"></div>
<script>
(function () {{
  var tip = document.getElementById("tip");
  function show(e, t) {{
    var i = t.indexOf("|");
    tip.innerHTML = "<b></b><span></span>";
    tip.firstChild.textContent = i < 0 ? t : t.slice(0, i);
    tip.lastChild.textContent = i < 0 ? "" : t.slice(i + 1);
    tip.style.opacity = "1";
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var x = e.clientX + 14, y = e.clientY - h - 12;
    if (x + w > window.innerWidth - 8) x = e.clientX - w - 14;
    if (y < 8) y = e.clientY + 18;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }}
  document.addEventListener("mousemove", function (e) {{
    var el = e.target.closest ? e.target.closest("[data-tip]") : null;
    if (el) show(e, el.getAttribute("data-tip"));
    else tip.style.opacity = "0";
  }}, {{ passive: true }});
  document.addEventListener("mouseleave", function () {{ tip.style.opacity = "0"; }});
}})();
</script>
'''

open(OUT, "w").write(HTML)
print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")
