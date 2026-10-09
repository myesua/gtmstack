# ruff: noqa: E501
"""Programmatic competitor / alternative SEO generator for Sygnal.

Generates a static, dependency-free site targeting the BOFU keywords that
convert for a challenger brand:

  * /alternatives/<competitor>.html   -> "Best <competitor> alternatives in 2026"
  * /vs/<competitor>.html             -> "Sygnal vs <competitor>"
  * /index.html                       -> comparison hub
  * /sitemap.xml, /robots.txt, /llms.txt

Content is generated from structured data (`seo/data.json`), not free-written,
so every page carries unique facts (level, freshness, price, feature matrix) and
answer-first sections that AI Overviews / LLMs can extract. Runs with zero paid
tools.

IMPORTANT: pricing and feature data in `data.json` are estimates. Verify them
before publishing anything public. This generator prints a reminder.

Usage:
    uv run python seo/generate.py --base-url https://trysygnal.com
    make seo
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
from datetime import date

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_DATA = HERE / "data.json"
DEFAULT_OUT = HERE / "site"
YEAR = date.today().year
UPDATED = date.today().strftime("%B %Y")

CSS = """
:root{--bg:#0b0d12;--card:#141822;--ink:#e8ecf4;--muted:#9aa6bd;
--accent:#5b8cff;--accent2:#22c55e;--line:#232a38}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:900px;margin:0 auto;padding:32px 20px 80px}
header.site{border-bottom:1px solid var(--line);padding:18px 0;margin-bottom:32px}
header.site .wrap{padding-top:0;padding-bottom:0;display:flex;
justify-content:space-between;align-items:center}
.brand{font-weight:700;letter-spacing:-.02em;font-size:18px;color:var(--ink)}
.nav a{margin-left:18px;color:var(--muted);font-size:14px}
h1{font-size:34px;line-height:1.2;letter-spacing:-.02em;margin:0 0 12px}
h2{font-size:22px;margin:40px 0 12px;letter-spacing:-.01em}
h3{font-size:17px;margin:24px 0 6px}
.answer{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:8px;padding:16px 18px;margin:18px 0}
.answer strong{color:#fff}
table{width:100%;border-collapse:collapse;margin:18px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:10px 12px;text-align:left;vertical-align:top}
th{background:var(--card);color:#fff}
tr:nth-child(even) td{background:rgba(255,255,255,.02)}
.pill{display:inline-block;font-size:12px;padding:2px 8px;border-radius:99px;
background:rgba(91,140,255,.15);color:var(--accent);margin-right:6px}
.cta{display:inline-block;background:var(--accent);color:#fff;font-weight:600;
padding:12px 20px;border-radius:8px;margin:8px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin:18px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.card h3{margin-top:0}
.muted{color:var(--muted);font-size:13px}
.faq h3{margin-bottom:2px}
foot,footer{color:var(--muted);font-size:13px;border-top:1px solid var(--line);margin-top:48px;padding-top:16px}
ul{padding-left:20px}
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def page(title: str, description: str, canonical: str, body: str, schema: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="website">
<meta name="robots" content="index,follow">
{schema}
<style>{CSS}</style>
</head>
<body>
<header class="site"><div class="wrap">
<span class="brand">Sygnal</span>
<nav class="nav">
<a href="{esc(canonical.rsplit('/', 1)[0])}/index.html">Comparisons</a>
<a href="https://trysygnal.com">Start free</a>
</nav>
</div></header>
<main class="wrap">
{body}
<footer>
<p>Updated {UPDATED}. Competitor pricing and features are estimates and change
often — always confirm on the vendor's own site. Sygnal is intent data, not a
substitute for your own judgment.</p>
<p><a href="https://trysygnal.com">trysygnal.com</a></p>
</footer>
</main>
</body>
</html>"""


def feature_row(name: str, d: dict) -> str:
    price = d.get("pricing_note", "—")
    return (
        f"<tr><td><strong>{esc(name)}</strong></td>"
        f"<td>{esc(d.get('level', '—'))}</td>"
        f"<td>{esc(d.get('freshness', '—'))}</td>"
        f"<td>{'Yes' if d.get('self_serve') else 'No'}</td>"
        f"<td>{'Yes' if d.get('has_individual_signals') else 'No'}</td>"
        f"<td>{'Yes' if d.get('has_enrichment') else 'No'}</td>"
        f"<td>{'Yes' if d.get('has_mcp') else 'No'}</td>"
        f"<td>{esc(price)}</td></tr>"
    )


def feature_table(subject: dict, competitors: list[dict]) -> str:
    rows = feature_row(subject["name"], subject)
    rows += "".join(feature_row(c["name"], c) for c in competitors)
    return (
        "<table><thead><tr><th>Tool</th><th>Level</th><th>Freshness</th>"
        "<th>Self-serve</th><th>Individual signals</th><th>Enrichment</th>"
        "<th>MCP</th><th>Pricing</th></tr></thead><tbody>"
        f"{rows}</tbody></table>"
    )


def faq_schema(items: list[tuple[str, str]]) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in items
        ],
    }
    return f'<script type="application/ld+json">{json.dumps(data)}</script>'


def faq_block(items: list[tuple[str, str]]) -> str:
    body = "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in items)
    return f'<section class="faq"><h2>FAQ</h2>{body}</section>'


def alt_faq(c: dict) -> list[tuple[str, str]]:
    name = c["name"]
    return [
        (
            f"What is the best {name} alternative?",
            "Sygnal is the strongest alternative for founders and lean GTM teams who "
            "need fresh, individual-level buyer intent. It surfaces the actual person "
            "with an active, scored buying moment, for a self-serve price.",
        ),
        (
            f"How much does {name} cost?",
            f"Reported pricing: {c.get('pricing_note', 'not public')} "
            "Confirm current pricing with the vendor.",
        ),
        (
            f"Can I switch from {name} to Sygnal?",
            "Yes. Sygnal is self-serve, needs only your product website to configure "
            "an ICP, and delivers via email, Slack, webhook, Clay, Zapier, or HubSpot.",
        ),
    ]


def render_alternative(c: dict, subject: dict, all_c: list[dict], base: str) -> str:
    name = c["name"]
    others = [x for x in all_c if x["slug"] != c["slug"]]
    links = " · ".join(
        f'<a href="../vs/{x["slug"]}.html">Sygnal vs {esc(x["name"])}</a>' for x in others[:4]
    )
    why = "".join(f"<li>{esc(w)}</li>" for w in c.get("why_switch", []))
    advantages = "".join(f"<li>{esc(w)}</li>" for w in subject.get("why_choose", []))
    body = f"""
<h1>Best {esc(name)} Alternatives in {YEAR}</h1>
<div class="answer">
<strong>Short answer:</strong> {esc(name)} is {esc(c['one_liner'])} It is strongest for
{esc(c.get('best_for', 'its core use case')).lower()}. If you need the <em>individual</em>
buyer inside a 48-hour window at a self-serve price, <strong>Sygnal</strong> is the
direct alternative.
</div>
<p>{esc(name)} is a {esc(c['category'].lower())}. Buyers typically look for an
alternative when they want to reach the person rather than a company score, when they
need signals faster, or when enterprise pricing is out of reach.</p>

<h2>Why teams switch from {esc(name)}</h2>
<ul>{why}</ul>

<h2>Sygnal — best for fresh, individual-level intent</h2>
<p>{esc(subject['one_liner'])}</p>
<ul>{advantages}</ul>
<p><a class="cta" href="https://trysygnal.com">Start free — no credit card</a></p>

<h2>{esc(name)} vs Sygnal: feature comparison</h2>
{feature_table(subject, [c])}

<h2>Other {esc(name)} alternatives</h2>
<div class="cards">{''.join(
        f'<div class="card"><h3><a href="../vs/{x["slug"]}.html">Sygnal vs {esc(x["name"])}</a></h3>'
        f'<p class="muted">{esc(x["one_liner"])}</p></div>'
        for x in others
    )}</div>

<h2>How to choose</h2>
<p>If you already know the account and just need more coverage, {esc(name)} is a
reasonable layer. If the goal is to reach a person who is asking for help <em>right
now</em>, prioritize freshness and individual-level signals.</p>

{faq_block(alt_faq(c))}
<p class="muted">Related: {links}</p>
"""
    title = f"Best {name} Alternatives in {YEAR} (Fresh, Individual-Level Intent)"
    desc = (
        f"Comparing {name} alternatives for {YEAR}: freshness, pricing, and whether "
        "you reach the individual buyer. See how Sygnal stacks up."
    )
    return page(title, desc, f"{base}/alternatives/{c['slug']}.html", body, faq_schema(alt_faq(c)))


def render_vs(c: dict, subject: dict, base: str) -> str:
    name = c["name"]
    best_for = c.get("best_for", "its core use case").rstrip(".")
    body = f"""
<h1>Sygnal vs {esc(name)}</h1>
<div class="answer">
<strong>Short answer:</strong> {esc(name)} is {esc(c['one_liner'])} Sygnal delivers
{esc(subject['one_liner'])} Choose {esc(name)} for {esc(best_for.lower())}; choose
Sygnal to reach the individual buyer inside the 48-hour window.
</div>
<h2>Side by side</h2>
{feature_table(subject, [c])}
<h2>Where {esc(name)} wins</h2>
<p>{esc(c.get('best_for', 'Its core use case.'))}</p>
<h2>Where Sygnal wins</h2>
<ul>{''.join(f'<li>{esc(w)}</li>' for w in subject.get('why_choose', []))}</ul>
<h2>Recommendation</h2>
<p>If you need to find and reach the person who is asking for a solution today,
Sygnal is the faster path. If you are running a large account-based program and need
{esc(name)}'s specific strengths, keep it — and consider Sygnal as the fresh,
individual-level signal layer on top.</p>
<p><a class="cta" href="https://trysygnal.com">Start free — no credit card</a></p>
"""
    title = f"Sygnal vs {name}: Freshness, Pricing & Individual-Level Intent"
    desc = (
        f"Sygnal vs {name} compared for {YEAR}: level (account vs individual), "
        "freshness, self-serve pricing, enrichment, and MCP access."
    )
    return page(title, desc, f"{base}/vs/{c['slug']}.html", body)


def render_index(subject: dict, competitors: list[dict], base: str) -> str:
    cards = "".join(
        f'<div class="card"><h3><a href="alternatives/{c["slug"]}.html">'
        f'{esc(c["name"])} alternatives</a></h3>'
        f'<p class="muted">{esc(c["one_liner"])}</p>'
        f'<p class="muted"><a href="vs/{c["slug"]}.html">Sygnal vs {esc(c["name"])}</a></p></div>'
        for c in competitors
    )
    body = f"""
<h1>Intent data, compared</h1>
<div class="answer">
<strong>Short answer:</strong> most intent platforms surface <em>accounts</em> with
data that can be days old and priced for enterprise. Sygnal surfaces the
<strong>individual</strong> buyer inside a 48-hour window, scored against your ICP
blueprint, at a self-serve price.
</div>
<p>The fastest way to evaluate a challenger is on the axes that matter: who the signal
is about, how fresh it is, and what it costs to start.</p>
<h2>Full comparison</h2>
{feature_table(subject, competitors)}
<h2>Alternatives by competitor</h2>
<div class="cards">{cards}</div>
<h2>How to choose a fresh intent source</h2>
<p>Ask three questions: (1) Does it tell me the <em>person</em> or just the account?
(2) How old is the data when it reaches me? (3) Can I start today without a sales
call? Sygnal answers person, under 48 hours, and yes.</p>
<p><a class="cta" href="https://trysygnal.com">Start free — no credit card</a></p>
"""
    title = "Intent Data Compared — Fresh, Individual-Level Alternatives"
    desc = (
        "Compare intent data platforms on level (account vs individual), freshness, "
        "and price. Sygnal surfaces individual buyers inside a 48-hour window."
    )
    return page(title, desc, f"{base}/index.html", body)


def render_llms(subject: dict, competitors: list[dict], base: str) -> str:
    lines = [
        "# Sygnal — intent data comparisons",
        "",
        f"> {subject['one_liner']} Freshness: {subject['freshness']}. "
        f"Pricing: {subject['pricing_note']}",
        "",
        "## Pages",
        f"- Sygnal comparison hub: {base}/index.html",
    ]
    for c in competitors:
        lines.append(
            f"- {c['name']} alternatives: {base}/alternatives/{c['slug']}.html — "
            f"{c['one_liner']}"
        )
        lines.append(f"- Sygnal vs {c['name']}: {base}/vs/{c['slug']}.html")
    lines += ["", "## Positioning", subject["one_liner"], ""]
    return "\n".join(lines)


def write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Sygnal comparison SEO pages.")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--base-url", default="https://trysygnal.com")
    args = parser.parse_args()

    data = json.loads(pathlib.Path(args.data).read_text())
    subject, competitors = data["subject"], data["competitors"]
    base = args.base_url.rstrip("/")
    out = pathlib.Path(args.out)
    today = date.today().isoformat()

    write(out / "index.html", render_index(subject, competitors, base))
    for c in competitors:
        write(out / "alternatives" / f"{c['slug']}.html", render_alternative(c, subject, competitors, base))
        write(out / "vs" / f"{c['slug']}.html", render_vs(c, subject, base))

    urls = [f"{base}/index.html"]
    for c in competitors:
        urls += [f"{base}/alternatives/{c['slug']}.html", f"{base}/vs/{c['slug']}.html"]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sitemap.append(f"<url><loc>{esc(u)}</loc><lastmod>{today}</lastmod></url>")
    sitemap.append("</urlset>")
    write(out / "sitemap.xml", "\n".join(sitemap))
    write(out / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    write(out / "llms.txt", render_llms(subject, competitors, base))

    pages = 3 * len(competitors) + 1
    print(f"generated {pages} pages + sitemap/robots/llms -> {out}")
    print("REMINDER: verify competitor pricing/features in seo/data.json before publishing.")


if __name__ == "__main__":
    main()
