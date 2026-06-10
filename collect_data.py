#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag

try:
    from playwright.sync_api import sync_playwright
    HAVE_PLAYWRIGHT = True
except Exception:
    HAVE_PLAYWRIGHT = False


OUTDIR = Path("data/raw")
REDDIT_DIR = OUTDIR / "reddit"
REQUEST_TIMEOUT = 40
SLEEP_SECONDS = 1.0
REDDIT_EXPORT_COUNT = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


@dataclass
class SourceSpec:
    name: str
    url: str
    output_name: str
    render: bool = False
    kind: str = "generic"  # generic | reddit_search


SOURCES: List[SourceSpec] = [
    SourceSpec(
        name="ASU Official Off-Campus Housing",
        url="https://offcampushousing.asu.edu/",
        output_name="01_asu_official_offcampus_housing.txt",
        render=True,
    ),
    SourceSpec(
        name="Apartments.com ASU Campus Housing",
        url="https://www.apartments.com/off-campus-housing/az/tempe/arizona-state-university-tempe-campus/",
        output_name="02_apartments_com_asu.txt",
        render=True,
    ),
    SourceSpec(
        name="ForRentUniversity ASU Guide",
        url="https://www.forrentuniversity.com/Arizona-State-University-Tempe-Campus",
        output_name="03_forrent_university_asu.txt",
        render=True,
    ),
    SourceSpec(
        name="College Pads ASU Search",
        url="https://www.rentcollegepads.com/off-campus-housing/asu/search",
        output_name="04_college_pads_asu.txt",
        render=True,
    ),
    SourceSpec(
        name="uHomes Tempe",
        url="https://en.uhomes.com/us/tempe",
        output_name="05_uhomes_tempe.txt",
        render=True,
    ),
    SourceSpec(
        name="Birdeye Reviews",
        url="https://reviews.birdeye.com/the-district-on-apache-161368555711655",
        output_name="06_birdeye_reviews.txt",
        render=True,
    ),
    SourceSpec(
        name="RateMyApartments ASU",
        url="https://www.ratemyapartments.com/ratings/az/arizona-state-university-at-the-tempe-campus",
        output_name="07_ratemyapartments_asu.txt",
        render=True,
    ),
    SourceSpec(
        name="ApartmentList ASU Apartments",
        url="https://www.apartmentlist.com/off-campus-housing/az/asu-apartments-for-rent",
        output_name="08_apartmentlist_asu.txt",
        render=True,
    ),
    SourceSpec(
        name="ApartmentRatings Tempe",
        url="https://www.apartmentratings.com/az/tempe/",
        output_name="09_apartmentratings_tempe.txt",
        render=True,
    ),
    SourceSpec(
        name="Reddit ASU Apartments Search",
        url="https://www.reddit.com/r/ASU/search/?q=apartments",
        output_name="reddit_seed",
        render=True,
        kind="reddit_search",
    ),
    SourceSpec(
        name="Off-Campus Universe Housing Guide 1",
        url="https://www.offcampus-universe.com/post/apartments-near-arizona-state-university-best-off-campus-housing-for-asu-students",
        output_name="11_offcampus_universe_guide_1.txt",
        render=True,
    ),
    SourceSpec(
        name="Off-Campus Universe Housing Guide 2",
        url="https://www.offcampus-universe.com/post/asu-off-campus-housing-guide-apartments-houses-and-subleases-in-tempe",
        output_name="12_offcampus_universe_guide_2.txt",
        render=True,
    ),
]

# Some sites are often easier through a real browser.
BROWSER_ALWAYS = {
    "apartments.com",
    "forrentuniversity.com",
    "apartmentratings.com",
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
}


def ensure_dirs() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    REDDIT_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str, max_len: int = 80) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:max_len] or "document"


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def strip_noise(soup: BeautifulSoup) -> None:
    for tag_name in [
        "script", "style", "noscript", "svg", "canvas", "iframe",
        "header", "footer", "nav", "aside", "form", "button", "input",
        "select", "option", "textarea", "label", "link", "meta",
    ]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for selector in [
        ".cookie", ".cookies", ".cookie-banner", ".cookie-consent",
        ".advert", ".ads", ".ad", ".promo", ".banner",
        ".newsletter", ".subscribe", ".modal", ".popup", ".overlay",
    ]:
        for tag in soup.select(selector):
            try:
                tag.decompose()
            except Exception:
                pass


def pick_main_container(soup: BeautifulSoup) -> Tag:
    candidates: List[Tag] = []
    for sel in ["main", "article", "[role='main']"]:
        candidates.extend([t for t in soup.select(sel) if isinstance(t, Tag)])

    if not candidates:
        candidates.extend([t for t in soup.select("body, section, div") if isinstance(t, Tag)])

    best = None
    best_len = -1
    for node in candidates:
        txt = node.get_text(" ", strip=True)
        if len(txt) > best_len:
            best_len = len(txt)
            best = node

    if best is not None:
        return best
    if soup.body is not None:
        return soup.body
    return soup


def fetch_html_requests(url: str) -> str:
    resp = SESSION.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def fetch_html_browser(url: str) -> str:
    if not HAVE_PLAYWRIGHT:
        raise RuntimeError("Playwright is not installed.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 2200})
        page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT * 1000)
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
        return html


def fetch_html(url: str, render: bool = False) -> str:
    host = urlparse(url).netloc.lower()
    use_browser = render or host in {
        "apartments.com",
        "www.apartments.com",
        "forrentuniversity.com",
        "www.forrentuniversity.com",
        "apartmentratings.com",
        "www.apartmentratings.com",
        "reddit.com",
        "www.reddit.com",
        "old.reddit.com",
    }

    if use_browser and HAVE_PLAYWRIGHT:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 2200})
                page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT * 1000)
                page.wait_for_timeout(3000)
                html = page.content()
                browser.close()
                return html
        except Exception:
            pass

    resp = SESSION.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text

def extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in [
        "script", "style", "noscript", "svg", "canvas", "iframe",
        "header", "footer", "nav", "aside", "form", "button", "input",
        "select", "option", "textarea", "label", "link", "meta"
    ]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for selector in [
        ".cookie", ".cookies", ".cookie-banner", ".cookie-consent",
        ".advert", ".ads", ".ad", ".promo", ".banner",
        ".newsletter", ".subscribe", ".modal", ".popup", ".overlay"
    ]:
        for tag in soup.select(selector):
            try:
                tag.decompose()
            except Exception:
                pass

    body = soup.body if soup.body else soup
    return normalize_text(body.get_text("\n", strip=True))


def save_text(path: Path, title: str, source_url: str, body: str, extra: Optional[str] = None) -> None:
    lines = [
        f"TITLE: {title}",
        f"SOURCE_URL: {source_url}",
    ]
    if extra:
        lines.append(extra)
    lines.append("")
    lines.append(body.strip())
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_manifest(rows: List[dict]) -> None:
    with (OUTDIR / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source_name", "source_url", "output_file", "notes"])
        writer.writeheader()
        writer.writerows(rows)


def to_old_reddit_search(url: str) -> str:
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    q["restrict_sr"] = ["on"]
    q["sort"] = ["relevance"]
    q["t"] = ["all"]
    q["limit"] = ["25"]
    return urlunparse(parsed._replace(
        netloc="old.reddit.com",
        path="/r/ASU/search",
        query=urlencode(q, doseq=True),
    ))


def extract_reddit_search_threads(search_url: str, max_threads: int = 5) -> list[dict]:
    html = fetch_html(to_old_reddit_search(search_url), render=True)
    soup = BeautifulSoup(html, "html.parser")

    threads = []
    seen = set()

    # Old Reddit search results usually expose thread titles as a.title
    for a in soup.select("a.title"):
        href = a.get("href", "")
        title = normalize_text(a.get_text(" ", strip=True))

        if "/comments/" not in href:
            continue
        if href.startswith("/"):
            href = "https://old.reddit.com" + href
        if href in seen:
            continue

        seen.add(href)
        threads.append({"title": title or "reddit_thread", "url": href})

        if len(threads) >= max_threads:
            break

    return threads

def extract_reddit_thread(thread_url: str) -> str:
    parsed = urlparse(thread_url)
    thread_url = urlunparse(parsed._replace(netloc="old.reddit.com"))

    html = fetch_html(thread_url, render=True)
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.select_one("a.title") or soup.select_one("h1")
    title = normalize_text(title_tag.get_text(" ", strip=True)) if title_tag else "Reddit thread"

    lines = [
        f"REDDIT THREAD TITLE: {title}",
        f"THREAD_URL: {thread_url}",
        "",
    ]

    # Post body
    post_body = None
    for sel in [
        "div.expando div.md",
        "div.thing.link div.usertext-body div.md",
        "div.usertext-body > div.md",
    ]:
        post_body = soup.select_one(sel)
        if post_body:
            break

    lines.append("POST:")
    lines.append(normalize_text(post_body.get_text("\n", strip=True)) if post_body else "[not found]")
    lines.append("")
    lines.append("COMMENTS:")

    comments = soup.select("div.comment")
    if not comments:
        lines.append("[No comments found or comments were hidden.]")
        return normalize_text("\n".join(lines))

    for idx, comment in enumerate(comments, start=1):
        author = comment.select_one("a.author")
        score = comment.select_one("span.score")
        body = comment.select_one("div.md")

        body_txt = normalize_text(body.get_text("\n", strip=True)) if body else ""
        if not body_txt:
            continue

        lines.append(f"COMMENT {idx}:")
        lines.append(f"Author: {normalize_text(author.get_text(' ', strip=True)) if author else '[deleted]'}")
        if score:
            lines.append(f"Score: {normalize_text(score.get_text(' ', strip=True))}")
        lines.append(body_txt)
        lines.append("")

    return normalize_text("\n".join(lines))


def export_generic_source(spec: SourceSpec, manifest_rows: List[dict]) -> None:
    print(f"[generic] {spec.name}")
    try:
        html = fetch_html(spec.url, render=spec.render)
        text = extract_visible_text(html)
    except Exception as e:
        text = f"ERROR_EXTRACTING_SOURCE: {e}"

    outpath = OUTDIR / spec.output_name
    save_text(outpath, spec.name, spec.url, text, extra="DOC_TYPE: raw_page_text")
    manifest_rows.append(
        {
            "source_name": spec.name,
            "source_url": spec.url,
            "output_file": str(outpath),
            "notes": "raw page text",
        }
    )


def export_reddit_source(spec, manifest_rows):
    print(f"[reddit-search] {spec.name}")
    outdir = REDDIT_DIR
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        threads = extract_reddit_search_threads(spec.url, max_threads=REDDIT_EXPORT_COUNT)
    except Exception as e:
        fallback = outdir / "reddit_search_error.txt"
        save_text(fallback, spec.name, spec.url, f"ERROR: {e}", extra="DOC_TYPE: reddit_search_error")
        manifest_rows.append({
            "source_name": spec.name,
            "source_url": spec.url,
            "output_file": str(fallback),
            "notes": f"ERROR: {e}",
        })
        return

    if not threads:
        fallback = outdir / "reddit_search_no_threads.txt"
        save_text(fallback, spec.name, spec.url, "No Reddit threads were found in the search results page.", extra="DOC_TYPE: reddit_search_no_threads")
        manifest_rows.append({
            "source_name": spec.name,
            "source_url": spec.url,
            "output_file": str(fallback),
            "notes": "no threads found",
        })
        return

    for i, thread in enumerate(threads, start=1):
        print(f"  -> thread {i}/{len(threads)}: {thread['title']}")
        try:
            text = extract_reddit_thread(thread["url"])
        except Exception as e:
            text = f"ERROR: {e}"

        filename = f"reddit_{i:02d}_{slugify(thread['title'])}.txt"
        outpath = outdir / filename
        save_text(outpath, thread["title"], thread["url"], text, extra="DOC_TYPE: reddit_thread_post_and_comments")
        manifest_rows.append({
            "source_name": f"{spec.name} :: {thread['title']}",
            "source_url": thread["url"],
            "output_file": str(outpath),
            "notes": "reddit thread with comments",
        })
        time.sleep(SLEEP_SECONDS)


def main() -> None:
    ensure_dirs()
    manifest_rows: List[dict] = []

    for spec in SOURCES:
        try:
            if spec.kind == "reddit_search":
                export_reddit_source(spec, manifest_rows)
            else:
                export_generic_source(spec, manifest_rows)
            time.sleep(SLEEP_SECONDS)
        except Exception as e:
            print(f"[error] {spec.name}: {e}")
            err_path = OUTDIR / f"{slugify(spec.output_name)}_ERROR.txt"
            save_text(err_path, spec.name, spec.url, f"ERROR: {e}")
            manifest_rows.append(
                {
                    "source_name": spec.name,
                    "source_url": spec.url,
                    "output_file": str(err_path),
                    "notes": f"ERROR: {e}",
                }
            )

    write_manifest(manifest_rows)
    print(f"\nDone. Files written to: {OUTDIR.resolve()}")
    print(f"Manifest: {(OUTDIR / 'manifest.csv').resolve()}")
    if not HAVE_PLAYWRIGHT:
        print("Playwright is not installed, so browser rendering was unavailable.")


if __name__ == "__main__":
    main()