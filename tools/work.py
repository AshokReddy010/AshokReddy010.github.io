"""Builds the shared parts of every project page and the /work/ catalogue from projects.json.

    python tools/work.py

For each project folder (<slug>/index.html) it writes, between <!-- wk:top --> and <!-- wk:bottom --> markers:
the site bar, the case header (title, summary, stack, key facts), the strip that introduces the live tool, the case
notes (problem, approach, architecture, findings) and the footer (previous / all work / next). The tool itself, its
charts and its data loading are not touched. Run it again after editing projects.json; it is safe to re-run.
Styles: assets/work.css.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400..600;'
         '1,6..72,400..500&family=Geist:wght@400..700&family=Geist+Mono:wght@400..600&display=swap">')
PROFILE = {"github": "https://github.com/AshokReddy010", "linkedin": "https://www.linkedin.com/in/ashokreddy1",
           "resume": "/Ashok_Reddy_Bhimavarapu_Resume.pdf"}

GROUPS = [
    ("Data quality and reliability", ["data-validation-framework", "data-contract-guard", "pipeline-observability"]),
    ("Analytics and research", ["fund-proxy-voting", "medicare-cost-analysis", "nyc-311-pulse", "olist-analytics-engineering"]),
    ("Experimentation and AI evaluation", ["ab-testing-toolkit", "text-to-sql-eval"]),
]
SHORT = {"fund-proxy-voting": "ESG fund votes", "medicare-cost-analysis": "Medicare costs", "text-to-sql-eval": "SQL Bench",
         "pipeline-observability": "Feed Watch", "data-contract-guard": "Data Contract Guard", "nyc-311-pulse": "NYC 311 Pulse",
         "data-validation-framework": "Data Validation", "olist-analytics-engineering": "Olist analytics",
         "ab-testing-toolkit": "A/B testing toolkit"}
# what the live part is, and how it stays current: (label, facts, refreshes by itself)
LIVE = {
    "nyc-311-pulse": ("Live dashboard", ["Source: NYC Open Data", "Refreshed every morning"], True),
    "pipeline-observability": ("Live status page", ["Six public feeds", "Checked every 3 hours"], True),
    "text-to-sql-eval": ("Live leaderboard", ["Scored by answers, not SQL text", "Re-run every day"], True),
    "data-validation-framework": ("Live console", ["dbt checks on public data", "Validated every day"], True),
    "medicare-cost-analysis": ("Live dashboard", ["Source: CMS public files", "Refreshed every month"], True),
    "fund-proxy-voting": ("Vote explorer", ["Source: SEC Form N-PX", "Three reporting years"], False),
    "olist-analytics-engineering": ("Dashboard", ["Built from dbt models", "Tested on every change"], False),
    "ab-testing-toolkit": ("Runs in your browser", ["The abkit Python package", "Nothing is sent anywhere"], False),
    "data-contract-guard": ("Runs in your browser", ["The real validator, in Python", "Nothing is sent anywhere"], False),
}
DUP = {"fund-proxy-voting", "medicare-cost-analysis", "data-contract-guard", "nyc-311-pulse"}   # the tool repeats the title
ARROW = '<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 10h11m-4-4 4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
EXT = '<svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M6 3.5h6.5V10M12.2 3.8 4 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>'
DOWN = '<svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 3v9.5m-4-4 4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
GH = ('<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 .2a8 8 0 0 0-2.5 15.6c.4 0 .5-.2.5-.4v-1.5c-2.2.5-2.7-1-2.7-1-.4-.9-.9-1.2-.9-1.2-.7-.5.1-.5.1-.5.8.1 1.2.8 1.2.8.7 1.3 1.9.9 2.4.7.1-.5.3-.9.5-1.1-1.8-.2-3.6-.9-3.6-4 0-.9.3-1.6.8-2.1-.1-.2-.4-1 .1-2.1 0 0 .7-.2 2.2.8a7.4 7.4 0 0 1 4 0c1.5-1 2.2-.8 2.2-.8.4 1.1.2 1.9.1 2.1.5.6.8 1.3.8 2.1 0 3.1-1.9 3.8-3.7 4 .3.3.6.8.6 1.5v2.2c0 .2.1.5.6.4A8 8 0 0 0 8 .2Z"/></svg>')
e = html.escape


ACRO = {"llm": "LLM", "sql": "SQL", "api": "API", "ci": "CI", "dbt": "dbt", "sla": "SLA", "ai": "AI", "ml": "ML", "auc": "AUC"}


def key(k):
    w = k.split(" ", 1)
    first = ACRO.get(w[0].lower(), w[0][:1].upper() + w[0][1:])
    return first + (" " + w[1] if len(w) > 1 else "")


def slug_of(p):
    return p["link"].rstrip("/").split("/")[-1]


def area_of(slug):
    return next(g for g, s in GROUPS if slug in s)


def item_html(text):
    m = re.match(r"([A-Z][^:]{1,40}):\s+(.*)", text, re.S)
    return f"<b>{e(m.group(1))}:</b> {e(m.group(2))}" if m else e(text)


def flow_html(flow):
    parts = []
    for k, stage in enumerate(flow):
        boxes = stage if isinstance(stage, list) else [stage]
        if k:
            parts.append(f'<div class="arrow">{ARROW}</div>')
        parts.append('<div class="stage">' + "".join(
            f'<div class="box"><b>{e(b["title"])}</b><span>{e(b.get("text", ""))}</span></div>' for b in boxes) + "</div>")
    return '<div class="wk-flow">' + "".join(parts) + "</div>"


def bar(crumb_title=None, code=None):
    crumb = '<span class="sep">/</span><a href="/work/">Work</a>'
    if crumb_title:
        crumb += f'<span class="sep">/</span><span aria-current="page">{e(crumb_title)}</span>'
    else:
        crumb = '<span class="sep">/</span><span aria-current="page">Work</span>'
    nav = ('<a class="wk-hide-s" href="/work/">All work</a>' if crumb_title else "") + '<a class="wk-hide-s" href="/">Profile</a>'
    if code:
        nav += f'<a class="wk-code" href="{e(code)}" target="_blank" rel="noopener">Code</a>'
    return (f'<div class="wk-bar" role="banner"><div class="wk-wrap"><a class="wk-mark" href="/" aria-label="Ashok Reddy Bhimavarapu, profile">'
            f'<i aria-hidden="true">AR</i><span>Ashok Reddy Bhimavarapu</span></a><nav class="wk-crumb" aria-label="Breadcrumb">{crumb}</nav>'
            f'<nav class="wk-nav" aria-label="Site">{nav}</nav></div></div>')


def top_block(p):
    slug = slug_of(p)
    label, facts, live = LIVE[slug]
    spec = "".join(f"<div><dt>{e(key(k))}</dt><dd>{e(v)}</dd></div>" for k, v in p.get("spec", []))
    tags = "".join(f"<li>{e(t)}</li>" for t in p.get("tags", []))
    pulse = '<span class="wk-pulse" aria-hidden="true"></span>' if live else ""
    return f"""<!-- wk:top -->
{bar(SHORT[slug], p["link"])}
<div class="wk-case" role="region" aria-labelledby="wk-title"><div class="wk-wrap">
<div>
<p class="wk-area">{pulse}<b>{e(area_of(slug))}</b></p>
<h1 class="wk-title" id="wk-title">{e(p["title"]).replace("-", "\u2011")}</h1>
<p class="wk-dek">{e(p["description"])}</p>
<div class="wk-actions"><a class="wk-btn primary" href="#live">{e(p.get("demoLabel") or "Open it")} {DOWN}</a><a class="wk-btn" href="{e(p["link"])}" target="_blank" rel="noopener">{GH} Code on GitHub</a></div>
<ul class="wk-tags" aria-label="Built with">{tags}</ul>
</div>
<div class="wk-spec" role="complementary" aria-label="Key facts"><p class="wk-spec-h">Key facts</p><dl>{spec}</dl></div>
</div></div>
<div class="wk-strip" id="live"><div class="wk-wrap"><b>{pulse}{e(label)}</b>{"".join(f'<span class="wk-meta">{e(f)}</span>' for f in facts)}<a href="#wk-notes">Case notes</a></div></div>
<!-- /wk:top -->"""


def bottom_block(p, prev, nxt):
    cases = p.get("case", [])
    problem = next((c for c in cases if c["heading"].lower() == "problem"), None)
    notes = []
    for c in cases:
        if c is problem:
            continue
        if "flow" in c:
            body = flow_html(c["flow"])
        elif "items" in c:
            body = "<ul>" + "".join(f"<li>{item_html(i)}</li>" for i in c["items"]) + "</ul>"
        else:
            body = f"<p>{e(c.get('text', ''))}</p>"
        wide = " wide" if c.get("wide") or "flow" in c else ""
        notes.append(f'<div class="wk-note{wide}"><h3>{e(c["heading"])}</h3>{body}</div>')
    lead = f"<p>{e(problem['text'])}</p>" if problem and problem.get("text") else ""
    return f"""<!-- wk:bottom -->
<div class="wk-notes" id="wk-notes" role="region" aria-labelledby="wk-notes-h"><div class="wk-wrap">
<div class="wk-notes-head"><h2 id="wk-notes-h">Case notes</h2>{lead}</div>
<div class="wk-grid{" solo" if len(notes) == 1 else ""}">{"".join(notes)}</div>
</div></div>
<div class="wk-foot" role="contentinfo"><div class="wk-wrap">
<nav class="wk-pn" aria-label="More projects"><a class="prev" href="/{slug_of(prev)}/"><small>Previous project</small><b>{e(SHORT[slug_of(prev)])}</b></a><a class="mid" href="/work/"><small>Ashok Reddy Bhimavarapu</small><b>All work</b></a><a class="next" href="/{slug_of(nxt)}/"><small>Next project</small><b>{e(SHORT[slug_of(nxt)])}</b></a></nav>
<div class="wk-sign"><span>Ashok Reddy Bhimavarapu, data analyst in New York</span><nav aria-label="Elsewhere"><a href="/">Profile</a><a href="{PROFILE['github']}" target="_blank" rel="noopener">GitHub</a><a href="{PROFILE['linkedin']}" target="_blank" rel="noopener">LinkedIn</a><a href="{PROFILE['resume']}" target="_blank" rel="noopener">Resume</a></nav></div>
</div></div>
<!-- /wk:bottom -->"""


def put(s, name, block, anchor_re, where):
    """Replace an existing marker block, or insert the block at the anchor."""
    pat = re.compile(rf"<!-- wk:{name} -->.*?<!-- /wk:{name} -->", re.S)
    if pat.search(s):
        return pat.sub(lambda _: block, s, count=1)
    m = re.search(anchor_re, s, re.S)
    if not m:
        raise SystemExit(f"anchor for wk:{name} not found")
    return s[:m.start()] + block + s[m.start():] if where == "before" else s[:m.start()] + block + s[m.end():]


def page(p, prev, nxt):
    slug = slug_of(p)
    f = ROOT / slug / "index.html"
    s = f.read_text(encoding="utf-8")
    s = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/css2[^"]*">', lambda _: FONTS, s, count=1)
    s = s.replace('<link rel="stylesheet" href="/assets/ds.css">', '<link rel="stylesheet" href="/assets/work.css">')
    if "/assets/work.css" not in s:
        s = s.replace("</head>", '<link rel="stylesheet" href="/assets/work.css">\n</head>', 1)
    s = re.sub(r"<body[^>]*>", f'<body class="wk wk-{slug}{" wk-dup" if slug in DUP else ""}">', s, count=1)
    s = put(s, "top", top_block(p), r'<div class="ds-bar">.*?</div></div>\s*\n', "replace")
    s = re.sub(r'<nav class="ds-foot".*?</nav>\s*\n', "", s, count=1, flags=re.S)
    s = put(s, "bottom", bottom_block(p, prev, nxt), r"</body>", "before")
    f.write_text(s, encoding="utf-8")
    return slug


def hub(projects):
    by = {slug_of(p): p for p in projects}
    live_n = sum(1 for s in by if LIVE[s][2])
    browser_n = sum(1 for s in by if LIVE[s][0] == "Runs in your browser")
    groups = []
    for g, slugs in GROUPS:
        items = []
        for s in slugs:
            p = by[s]
            shot = (p.get("shots") or [{}])[0].get("image")
            img = (f'<a class="wk-shot" href="/{s}/" tabindex="-1" aria-hidden="true"><img src="/{e(shot)}" alt="" loading="lazy"></a>'
                   if shot else f'<a class="wk-shot" href="/{s}/" tabindex="-1" aria-hidden="true"><img src="/work/shots/{s}.jpg" alt="" loading="lazy"></a>')
            mini = "".join(f"<div><dt>{e(key(k))}</dt><dd>{e(v)}</dd></div>" for k, v in p.get("spec", [])[:4])
            label, facts, live = LIVE[s]
            pulse = '<span class="wk-pulse" aria-hidden="true"></span>' if live else ""
            items.append(f"""<article class="wk-item" data-group="{e(g)}">
<div><p class="wk-area">{pulse}<b>{e(label)}</b>&nbsp;&nbsp;<span>{e(facts[-1])}</span></p><h3><a href="/{s}/">{e(p["title"])}</a></h3><p>{e(p["description"])}</p>
<div class="wk-links"><a class="wk-btn primary" href="/{s}/">Open the case</a><a class="wk-btn" href="{e(p["link"])}" target="_blank" rel="noopener">{GH} Code</a></div></div>
<dl class="wk-mini">{mini}</dl>
{img}
</article>""")
        groups.append(f'<section class="wk-group" data-group="{e(g)}"><h2><span>{e(g)}</span><span>{len(slugs)}</span></h2>{"".join(items)}</section>')
    filt = '<button type="button" aria-pressed="true" data-f="">All<span>9</span></button>' + "".join(
        f'<button type="button" aria-pressed="false" data-f="{e(g)}">{e(g)}<span>{len(s)}</span></button>' for g, s in GROUPS)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Work | Ashok Reddy Bhimavarapu</title>
<meta name="description" content="Nine data projects by Ashok Reddy Bhimavarapu, each built end to end on real public data, with tested pipelines and a live page you can use.">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta property="og:title" content="Work | Ashok Reddy Bhimavarapu"><meta property="og:image" content="https://ashokreddy010.github.io/social-card.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{FONTS}
<link rel="stylesheet" href="/assets/work.css">
</head>
<body class="wk wk-hub">
{bar()}
<section class="wk-hub-head"><div class="wk-wrap">
<div><h1>Work</h1>
<div class="wk-hub-stats"><div><b>9</b><span>projects, built end to end</span></div><div><b>{live_n}</b><span>refresh themselves</span></div><div><b>{browser_n}</b><span>run in your browser</span></div></div></div>
<p>Each project starts from real public data and ends in something you can use: a tested pipeline, a published finding, and a live page. Open any case for the problem, the approach, the architecture and what I found.</p>
</div></section>
<main class="wk-wrap">
<div class="wk-filter" role="group" aria-label="Filter by area">{filt}</div>
{"".join(groups)}
</main>
<footer class="wk-foot"><div class="wk-wrap"><div class="wk-sign"><span>Ashok Reddy Bhimavarapu, data analyst in New York</span><nav aria-label="Elsewhere"><a href="/">Profile</a><a href="{PROFILE['github']}" target="_blank" rel="noopener">GitHub</a><a href="{PROFILE['linkedin']}" target="_blank" rel="noopener">LinkedIn</a><a href="{PROFILE['resume']}" target="_blank" rel="noopener">Resume</a></nav></div></div></footer>
<script>
document.querySelectorAll('.wk-filter button').forEach(function (b) {{
  b.addEventListener('click', function () {{
    var f = b.dataset.f;
    document.querySelectorAll('.wk-filter button').forEach(function (x) {{ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); }});
    document.querySelectorAll('.wk-group').forEach(function (g) {{ g.hidden = !!f && g.dataset.group !== f; }});
  }});
}});
</script>
</body>
</html>
"""


def main():
    projects = json.loads((ROOT / "projects.json").read_text(encoding="utf-8"))
    n = len(projects)
    for k, p in enumerate(projects):
        print("page:", page(p, projects[(k - 1) % n], projects[(k + 1) % n]))
    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "work" / "index.html").write_text(hub(projects), encoding="utf-8")
    print("hub: work/index.html")


if __name__ == "__main__":
    main()
