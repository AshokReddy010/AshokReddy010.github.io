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
<div class="wk-strip" id="live"><div class="wk-wrap"><b>{pulse}{e(label)}</b>{"".join(f'<span class="wk-meta">{e(f)}</span>' for f in facts)}<nav class="wk-jump" aria-label="On this page"><a href="#wk-notes">Case notes</a><a href="#wk-doc">Full write-up</a></nav></div></div>
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
{gallery_html(p)}
{writeup_html(p)}
<div class="wk-foot" role="contentinfo"><div class="wk-wrap">
<nav class="wk-pn" aria-label="More projects"><a class="prev" href="/{slug_of(prev)}/"><small>Previous project</small><b>{e(SHORT[slug_of(prev)])}</b></a><a class="mid" href="/work/"><small>Ashok Reddy Bhimavarapu</small><b>All work</b></a><a class="next" href="/{slug_of(nxt)}/"><small>Next project</small><b>{e(SHORT[slug_of(nxt)])}</b></a></nav>
<div class="wk-sign"><span>Ashok Reddy Bhimavarapu, data analyst in New York</span><nav aria-label="Elsewhere"><a href="/">Profile</a><a href="{PROFILE['github']}" target="_blank" rel="noopener">GitHub</a><a href="{PROFILE['linkedin']}" target="_blank" rel="noopener">LinkedIn</a><a href="{PROFILE['resume']}" target="_blank" rel="noopener">Resume</a></nav></div>
</div></div>
<!-- /wk:bottom -->"""



# ---------------------------------------------------------------- the full write-up, gallery and automation
SRC = ROOT / "work" / "source"          # cached copies, so a rebuild works even when a fetch fails
RAW = "https://raw.githubusercontent.com/AshokReddy010/{slug}/main/{path}"
API = "https://api.github.com/repos/AshokReddy010/{slug}/contents/.github/workflows"
DROP = {"author", "license", "licence"}


def fetch(url, accept=None):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "ashokreddy010-work", **({"Accept": accept} if accept else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def readme_of(slug):
    """The project's README: the clone next to this repo, else GitHub, else the last cached copy."""
    SRC.mkdir(parents=True, exist_ok=True)
    cache = SRC / f"{slug}.md"
    local = ROOT.parent / slug / "README.md"
    text = None
    try:
        text = local.read_text(encoding="utf-8") if local.exists() else fetch(RAW.format(slug=slug, path="README.md"))
    except Exception:
        text = None
    if text:
        cache.write_text(text, encoding="utf-8")
        return text
    return cache.read_text(encoding="utf-8") if cache.exists() else ""


def workflows_of(slug):
    """[(name, what it does, when)] from the project's GitHub Actions files (cached the same way)."""
    cache = SRC / f"{slug}.workflows.json"
    files = {}
    local = ROOT.parent / slug / ".github" / "workflows"
    try:
        if local.exists():
            files = {f.name: f.read_text(encoding="utf-8") for f in sorted(local.glob("*.yml"))}
        else:
            for it in json.loads(fetch(API.format(slug=slug), "application/vnd.github+json")):
                if it["name"].endswith((".yml", ".yaml")):
                    files[it["name"]] = fetch(it["download_url"])
    except Exception:
        files = {}
    if not files:
        return json.loads(cache.read_text()) if cache.exists() else []
    out = []
    for name, y in files.items():
        title = (re.search(r"^name:\s*(.+)$", y, re.M) or [None, name])[1].strip().strip('"')
        notes = []
        for line in y.splitlines():
            if line.startswith("#"):
                notes.append(line.lstrip("# ").strip())
            elif notes or line.startswith("name:"):
                if notes:
                    break
        what = " ".join(notes) or ("Runs every test on every push and pull request." if re.search(r"^\s*(push|pull_request):", y, re.M) else "")
        cron = re.findall(r'cron:\s*"([^"]+)"', y)
        if not what:
            m = re.search(r'cron:\s*"[^"]+"\s*#\s*(.+)$', y, re.M)
            what = (m.group(1).strip()[:1].upper() + m.group(1).strip()[1:] + ".") if m else ""
        when = cron_words(cron[0]) if cron else ("On every push" if re.search(r"^\s*push:", y, re.M) else "By hand")
        out.append([key(title), what, when])
    cache.write_text(json.dumps(out, indent=1))
    return out


def cron_words(c):
    f = c.split()
    if len(f) != 5:
        return "On a schedule"
    mi, h, dom, mon, dow = f
    if h.startswith("*/") and dom == mon == dow == "*":
        return f"Every {h[2:]} hours"
    if dom == mon == dow == "*" and h.isdigit():
        return f"Daily, {int(h):02d}:{int(mi):02d} UTC"
    if dom.isdigit() and mon == dow == "*":
        return f"Monthly, day {dom}"
    if dow != "*" and dom == "*":
        return "Weekly"
    return "On a schedule"


def _abs(slug, url, kind):
    if re.match(r"^(https?:|mailto:|#|data:)", url):
        return url
    url = url.lstrip("./")
    return RAW.format(slug=slug, path=url) if kind == "img" else f"https://github.com/AshokReddy010/{slug}/blob/main/{url}"


def writeup(slug):
    """README rendered for the page: title, badges, author and licence sections dropped; links made absolute;
    headings moved down two levels under the page's own heading. Returns (toc, html)."""
    import markdown
    md = readme_of(slug)
    if not md.strip():
        return [], ""
    lines = md.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    md = "\n".join(l for l in lines if not re.search(r"(badge\.svg|img\.shields\.io)", l))
    parts = re.split(r"(?m)^(?=## )", md)
    md = "".join(x for x in parts if not (x.startswith("## ") and x[3:].split("\n")[0].strip().lower() in DROP))
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists", "toc"],
                             extension_configs={"toc": {"slugify": lambda v, sep: "wk-" + re.sub(r"[^a-z0-9]+", "-", v.lower()).strip("-")}})
    for a, b in (("h4", "h6"), ("h3", "h5"), ("h2", "h4")):
        body = body.replace(f"<{a}", f"<{b}").replace(f"</{a}>", f"</{b}>")
    body = body.replace("<h4", "<h3").replace("</h4>", "</h3>").replace("<h5", "<h4").replace("</h5>", "</h4>").replace("<h6", "<h5").replace("</h6>", "</h5>")
    body = re.sub(r'<img ([^>]*?)src="([^"]+)"', lambda m: f'<img loading="lazy" {m.group(1)}src="{_abs(slug, m.group(2), "img")}"', body)
    body = re.sub(r'<a href="([^"]+)"', lambda m: f'<a href="{_abs(slug, m.group(1), "a")}"', body)
    body = re.sub(r"<thead>\s*<tr>(?:\s*<th[^>]*>\s*</th>)+\s*</tr>\s*</thead>", "", body)      # tables with no header
    body = re.sub(r"<table>", '<div class="wk-table"><table>', body).replace("</table>", "</table></div>")
    body = re.sub(r"<p>(<img [^>]+>)</p>", r'<figure>\1</figure>', body)
    toc = re.findall(r'<h3 id="([^"]+)">(.*?)</h3>', body)
    return [(i, re.sub(r"<[^>]+>", "", t)) for i, t in toc], body


def gallery_html(p):
    shots = p.get("shots") or []
    if not shots:
        return ""
    figs = "".join(f'<figure><a href="/{e(x["image"])}" target="_blank" rel="noopener"><img src="/{e(x["image"])}" alt="{e(x.get("caption", ""))}" loading="lazy"></a>'
                   f'<figcaption>{e(x.get("caption", ""))}</figcaption></figure>' for x in shots)
    return (f'<div class="wk-gallery" role="region" aria-labelledby="wk-gal-h"><div class="wk-wrap"><div class="wk-sec-head"><h2 id="wk-gal-h">In pictures</h2>'
            f'<p>Screens from the live page and the analysis. Select one to see it full size.</p></div><div class="wk-figs n{min(len(shots), 3)}">{figs}</div></div></div>')


def writeup_html(p):
    slug = slug_of(p)
    toc, body = writeup(slug)
    if not body:
        return ""
    jobs = workflows_of(slug)
    nav = "".join(f'<li><a href="#{e(i)}">{t}</a></li>' for i, t in toc)
    auto = "".join(f'<li><b>{e(n)}</b><span class="when">{e(w)}</span><span>{e(d)}</span></li>' for n, d, w in jobs)
    return f"""<div class="wk-doc" id="wk-doc" role="region" aria-labelledby="wk-doc-h"><div class="wk-wrap">
<div class="wk-sec-head"><h2 id="wk-doc-h">The full write-up</h2><p>Everything in the project's documentation: the findings with their numbers, how it works, how to run it and where its limits are. Kept in step with GitHub every day.</p></div>
<div class="wk-doc-grid">
<nav class="wk-toc" aria-label="On this page"><p>On this page</p><ol>{nav}</ol>
<div class="wk-auto"><p>Automation</p><ul>{auto}</ul></div>
<a class="wk-btn" href="{e(p["link"])}" target="_blank" rel="noopener">{GH} Repository</a></nav>
<article class="wk-prose">{body}</article>
</div></div></div>
<script>(function () {{
  var links = [].slice.call(document.querySelectorAll('.wk-toc ol a')); if (!links.length || !('IntersectionObserver' in window)) return;
  var by = {{}}; links.forEach(function (a) {{ by[a.getAttribute('href').slice(1)] = a; }});
  var io = new IntersectionObserver(function (es) {{ es.forEach(function (x) {{ if (x.isIntersecting) {{ links.forEach(function (a) {{ a.classList.remove('on'); }}); var a = by[x.target.id]; if (a) a.classList.add('on'); }} }}); }}, {{ rootMargin: '-90px 0px -70% 0px' }});
  Object.keys(by).forEach(function (id) {{ var h = document.getElementById(id); if (h) io.observe(h); }});
}})();</script>"""


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
