#!/usr/bin/env python3
"""Check generated links, anchors, CSS resources and publication boundaries."""
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids, self.links = set(), []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for key in ("href", "src", "data-full-light", "data-full-dark", "data-search-src"):
            if attrs.get(key):
                self.links.append(attrs[key])


def check_site(site=SITE):
    pages = {p.relative_to(site).as_posix(): Page(p.read_text(encoding="utf-8"))
             for p in site.rglob("*.html")}
    errors, checked = [], 0

    def check(origin, href):
        nonlocal checked
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme == "file" or re.match(r"^[A-Za-z]:", href):
                errors.append(f"{origin}: machine-local URL {href}")
            return
        if href.startswith(("/", "\\")) or "\\" in href:
            errors.append(f"{origin}: non-relative URL {href}")
            return
        # Resolving under a fake repository prefix catches accidental escapes to the domain root.
        resolved = urlsplit(urljoin(f"https://example.test/repository-name/{origin}", href))
        if not resolved.path.startswith("/repository-name/"):
            errors.append(f"{origin}: escaped repository prefix: {href}")
            return
        target = unquote(resolved.path.removeprefix("/repository-name/"))
        if not target or target.endswith("/"):
            target += "index.html"
        file = site / target
        if not file.is_file():
            errors.append(f"{origin}: missing {href}")
        elif parsed.fragment and target in pages and unquote(parsed.fragment) not in pages[target].ids:
            errors.append(f"{origin}: missing anchor {href}")
        checked += 1

    for origin, page in pages.items():
        for href in page.links:
            check(origin, href)
    for css in site.rglob("*.css"):
        for href in re.findall(r"url\([\"']?([^\"')]+)", css.read_text(encoding="utf-8")):
            check(css.relative_to(site).as_posix(), href)
    for script in site.rglob("search.js"):
        text = script.read_text(encoding="utf-8")
        entries = json.loads(text.removeprefix("window.SEARCH_INDEX=").removesuffix(";"))
        origin = (script.parent.parent / "index.html").relative_to(site).as_posix()
        for entry in entries:
            check(origin, entry["p"] + ("#" + entry["a"] if entry.get("a") else ""))
    for path in site.rglob("*"):
        if any(part.startswith("_archive_") or part in {"_system", "notes", "private", "drafts"} for part in path.parts):
            errors.append(f"Private path in site: {path.relative_to(site)}")
    if not pages or "index.html" not in pages or "topics.html" not in pages:
        errors.append("Missing catalog pages; run python tools/build_site.py")
    return errors, len(pages), checked


if __name__ == "__main__":
    errors, count, links = check_site()
    if errors:
        print("\n".join(errors[:80]))
        raise SystemExit(f"FAILED: {len(errors)} errors")
    print(f"OK: {count} HTML pages, {links} local links/resources; repository subpath checked")
