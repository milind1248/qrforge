import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "site" / "public"


def _build():
    subprocess.run([sys.executable, str(ROOT / "site" / "build_site.py")], check=True, capture_output=True)


def test_every_page_has_seo_basics():
    _build()
    pages = list(PUB.rglob("*.html"))
    assert len(pages) >= 12
    for f in pages:
        s = f.read_text(encoding="utf-8")
        if f.name == "404.html":
            assert "noindex" in s
            continue
        title = re.search(r"<title>(.*?)</title>", s).group(1)
        desc = re.search(r'name="description" content="(.*?)"', s).group(1)
        assert 20 <= len(title) <= 70, (f.name, len(title))
        assert 50 <= len(desc) <= 160, (f.name, len(desc))
        assert s.count("<h1") == 1, f.name
        assert 'rel="canonical"' in s and 'property="og:image"' in s, f.name
        for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s):
            json.loads(blob)                       # structured data must be valid JSON


def test_sitemap_robots_llms_and_internal_links():
    _build()
    sm = (PUB / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>(.*?)</loc>", sm)
    assert len(locs) >= 12 and len(set(locs)) == len(locs)
    base = re.search(r"<loc>(https?://[^<]*?)/</loc>", sm).group(1)
    for u in locs:                                  # every sitemap URL maps to a built file
        rel = u[len(base):].strip("/")
        assert (PUB / (rel + "/index.html" if not rel.endswith(".html") else rel)).exists() if rel else (PUB / "index.html").exists(), u
    robots = (PUB / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap:" in robots and "GPTBot" in robots and "ClaudeBot" in robots and "Disallow" not in robots
    llms = (PUB / "llms.txt").read_text(encoding="utf-8")
    assert llms.startswith("# QR Sugi") and "\n> " in llms and "llms-full.txt" in llms
    assert (PUB / "og-image.png").stat().st_size > 5000
