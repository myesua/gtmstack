import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATE = ROOT / "seo" / "generate.py"


def _build(tmp_path: Path) -> Path:
    out = tmp_path / "site"
    result = subprocess.run(
        [sys.executable, str(GENERATE), "--out", str(out), "--base-url", "https://example.test"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return out


def test_builds_index_and_per_competitor_pages(tmp_path):
    out = _build(tmp_path)
    assert (out / "index.html").exists()
    alternatives = list((out / "alternatives").glob("*.html"))
    versus = list((out / "vs").glob("*.html"))
    assert alternatives, "expected alternative pages"
    assert len(alternatives) == len(versus)
    for f in ("sitemap.xml", "robots.txt", "llms.txt"):
        assert (out / f).exists(), f


def test_pages_have_metadata_valid_schema_and_working_links(tmp_path):
    out = _build(tmp_path)
    for page in out.rglob("*.html"):
        text = page.read_text()
        assert "<title>" in text and 'rel="canonical"' in text
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
            json.loads(html.unescape(raw))
        for href in re.findall(r'href="([^"#]+)"', text):
            if href.startswith("http"):
                continue
            assert (page.parent / href).resolve().exists(), f"{page} -> {href}"
