"""Unit tests for the NetOps Incident Bot static web dashboard assets."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

WEB_DIR = Path(__file__).resolve().parent.parent / "incidentbot" / "web"
INDEX_HTML = WEB_DIR / "index.html"
APP_JS = WEB_DIR / "app.js"
STYLE_CSS = WEB_DIR / "style.css"


class _AssetHTMLParser(HTMLParser):
    """Collects element IDs, stylesheet links, script sources, and data-severity values."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.data_severities: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        elem_id = attr_map.get("id")
        if elem_id:
            self.ids.add(elem_id)

        if tag == "link" and attr_map.get("rel") == "stylesheet":
            href = attr_map.get("href")
            if href is not None:
                self.stylesheets.append(href)

        if tag == "script":
            src = attr_map.get("src")
            if src is not None:
                self.scripts.append(src)

        sev = attr_map.get("data-severity")
        if sev:
            self.data_severities.add(sev)


class TestWebDashboardAssets(unittest.TestCase):
    """Validate static HTML, CSS, and JS dashboard assets."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.html_text = INDEX_HTML.read_text(encoding="utf-8") if INDEX_HTML.exists() else ""
        cls.js_text = APP_JS.read_text(encoding="utf-8") if APP_JS.exists() else ""
        cls.css_text = STYLE_CSS.read_text(encoding="utf-8") if STYLE_CSS.exists() else ""

    def test_assets_exist_and_non_empty(self) -> None:
        for asset in (INDEX_HTML, APP_JS, STYLE_CSS):
            self.assertTrue(asset.is_file(), f"Missing web asset: {asset}")
            content = asset.read_text(encoding="utf-8").strip()
            self.assertGreater(len(content), 0, f"Web asset is empty: {asset}")

    def test_index_html_references_local_static_assets(self) -> None:
        parser = _AssetHTMLParser()
        parser.feed(self.html_text)
        self.assertIn("/static/style.css", parser.stylesheets)
        self.assertIn("/static/app.js", parser.scripts)

    def test_no_external_cdn_links_or_urls(self) -> None:
        external_pattern = re.compile(r"https?://", re.IGNORECASE)
        for name, text in (
            ("index.html", self.html_text),
            ("app.js", self.js_text),
            ("style.css", self.css_text),
        ):
            self.assertIsNone(
                external_pattern.search(text),
                f"External http(s) URL found in {name}; dashboard must be fully self-contained.",
            )

    def test_index_html_contains_required_dashboard_sections(self) -> None:
        parser = _AssetHTMLParser()
        parser.feed(self.html_text)

        required_ids = {
            "health-badge",
            "health-status-text",
            "total-events-count",
            "open-incidents-count",
            "last-updated",
            "count-critical",
            "count-high",
            "count-medium",
            "count-low",
            "incidents-table",
            "incidents-tbody",
            "detail-modal",
            "detail-meta-grid",
            "detail-events-table",
            "detail-events-tbody",
            "resolve-incident-btn",
        }
        missing = required_ids - parser.ids
        self.assertEqual(missing, set(), f"Missing required element IDs in index.html: {sorted(missing)}")
        self.assertEqual(parser.data_severities, {"critical", "high", "medium", "low"})

    def test_app_js_api_endpoints_and_polling(self) -> None:
        self.assertIn("/api/health", self.js_text)
        self.assertIn("/api/incidents?status=open", self.js_text)
        self.assertIn("/api/incidents/", self.js_text)
        self.assertIn("/resolve", self.js_text)
        self.assertIn("encodeURIComponent", self.js_text)
        self.assertIn("5000", self.js_text)
        self.assertIn("setInterval", self.js_text)
        self.assertIn("POST", self.js_text)

    def test_app_js_uses_safe_dom_text_rendering(self) -> None:
        self.assertIn("textContent", self.js_text)
        for unsafe_api in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            self.assertNotIn(
                unsafe_api,
                self.js_text,
                f"Unsafe DOM/JS API {unsafe_api!r} found in app.js",
            )

    def test_severity_styles_defined_for_all_levels(self) -> None:
        for sev in ("critical", "high", "medium", "low"):
            self.assertIn(f".severity-{sev}", self.css_text)
            self.assertIn(f".badge-{sev}", self.css_text)
            self.assertIn(f'"{sev}"', self.js_text)


if __name__ == "__main__":
    unittest.main()
