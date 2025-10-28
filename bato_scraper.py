"""
Simple Bato.to chapter scraper for stacked-image manga pages.

Functions:
- get_image_urls(chapter_url): returns ordered list of image URLs for the chapter.
- download_images(urls, out_dir): downloads images to folder.
- parse_image_urls_from_html(html, base_url): helper to parse HTML (useful for tests).

This is intentionally lightweight and uses requests + BeautifulSoup.
"""
from __future__ import annotations

import os
import time
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from chapter_discovery import get_chapters_from_series, find_chapter_by_number

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}

VALID_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
# keywords to ignore in candidate urls
BLACKLIST_KEYWORDS = ("sprite", "logo", "favicon", "ads")


def _is_valid_image_url(u: str) -> bool:
    if not u:
        return False
    lower = u.lower()
    if any(k in lower for k in BLACKLIST_KEYWORDS):
        return False
    for ext in VALID_EXTS:
        if lower.split("?")[0].endswith(ext):
            return True
    # allow images served without extension (rare) if path contains /cdn/ or /data/
    if "/cdn/" in lower or "/data/" in lower:
        return True
    return False


def parse_image_urls_from_html(html: str, base_url: Optional[str] = None) -> List[str]:
    """Parse HTML and return ordered, unique image URLs.

    Looks for common attributes: data-src, data-lazy-src, src, data-original and srcset.
    Normalizes relative URLs against base_url if provided.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    out: List[str] = []

    for img in soup.find_all("img"):
        url_candidates = []
        # common attributes
        for attr in ("data-src", "data-lazy-src", "data-original", "data-srcset", "data-srcset", "srcset", "src"):
            val = img.get(attr)
            if not val:
                continue
            # if srcset-like, take first url
            if "srcset" in attr or "," in val:
                parts = [p.strip() for p in val.split(",") if p.strip()]
                if parts:
                    # each part can be "url 800w" — take first token
                    first = parts[0].split()[0]
                    url_candidates.append(first)
            else:
                url_candidates.append(val)

        # also check attributes that sometimes hold the image
        for attr in ("data-src-zoom", "data-image"):
            v = img.get(attr)
            if v:
                url_candidates.append(v)

        for raw in url_candidates:
            if not raw:
                continue
            if base_url:
                raw = urljoin(base_url, raw)
            # strip whitespace
            raw = raw.strip()
            if raw in seen:
                continue
            if _is_valid_image_url(raw):
                seen.add(raw)
                out.append(raw)

    # also consider <source> tags (sometimes used inside <picture>)
    for src in soup.find_all("source"):
        val = src.get("srcset") or src.get("src")
        if not val:
            continue
        # pick first url from srcset
        if "," in val:
            val = val.split(",")[0].split()[0]
        if base_url:
            val = urljoin(base_url, val)
        val = val.strip()
        if val not in seen and _is_valid_image_url(val):
            seen.add(val)
            out.append(val)

    return out


def get_image_urls(chapter_url: str, session: Optional[requests.Session] = None, timeout: int = 15) -> List[str]:
    """Fetch chapter page and return ordered image URLs.

    chapter_url: full URL to the chapter page (e.g., a Bato.to chapter)
    session: optional requests.Session
    """
    s = session or requests.Session()
    try:
        r = s.get(chapter_url, headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch {chapter_url}: {e}")

    base = r.url  # after redirects
    urls = parse_image_urls_from_html(r.text, base)

    # Fallback: sometimes pages place images in <div class="page-break"> <img ...>
    # parse_image_urls_from_html already handles all img tags; we simply return.

    # If not enough page images were found in <img>/<source>, search the full page text
    # for absolute image URLs inside scripts or JSON blobs. Use a regex that stops at
    # quotes, spaces or angle brackets to avoid capturing trailing punctuation.
    if not urls or len(urls) < 5:
        import re

        pattern = re.compile(r'https?://[^\s"\'""<>()]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^\s"\'""<>)]*)?', flags=re.IGNORECASE)
        matches = pattern.findall(r.text)

        # Clean and deduplicate matches, prefer media-hosted images (contain '/media/')
        cleaned = []
        for m in matches:
            m = m.strip().rstrip(',;\")\']')
            if base:
                m = urljoin(base, m)
            if m in cleaned:
                continue
            cleaned.append(m)

        # Prefer URLs that look like page images (contain '/media/') and valid extensions
        for m in cleaned:
            if m not in urls and _is_valid_image_url(m):
                # optional heuristic: prefer /media/ paths for manga pages
                if '/media/' in m or len(urls) < 1:
                    urls.append(m)

    return urls


def download_images(urls: List[str], out_dir: str, prefix: Optional[str] = None, session: Optional[requests.Session] = None, limit: Optional[int] = None, delay: float = 0.2) -> List[str]:
    """Download images to out_dir and return list of saved file paths.

    Keeps original filename if possible; otherwise uses numeric prefix.
    """
    os.makedirs(out_dir, exist_ok=True)
    s = session or requests.Session()
    saved = []
    count = 0
    for i, url in enumerate(urls):
        if limit is not None and count >= limit:
            break
        try:
            r = s.get(url, headers=DEFAULT_HEADERS, stream=True, timeout=20)
            r.raise_for_status()
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            continue

        path = urlparse(url).path
        fname = os.path.basename(path)
        if not fname:
            fname = f"page_{i+1}.jpg"
        if prefix:
            fname = f"{prefix}_{fname}"
        out_path = os.path.join(out_dir, fname)

        # avoid overwriting: if exists, add numeric suffix
        if os.path.exists(out_path):
            base, ext = os.path.splitext(out_path)
            k = 1
            while os.path.exists(f"{base}_{k}{ext}"):
                k += 1
            out_path = f"{base}_{k}{ext}"

        with open(out_path, "wb") as fh:
            for chunk in r.iter_content(1024 * 32):
                fh.write(chunk)
        saved.append(out_path)
        count += 1
        time.sleep(delay)

    return saved


def _basename_key(url: str) -> str:
    """Return a normalized basename used to group mirrors of the same image.

    Strips query strings and returns the file basename (e.g., 87981023_1920_2735_569558.webp)
    """
    p = urlparse(url).path
    return os.path.basename(p)


def select_one_per_page(urls: List[str]) -> List[str]:
    """Given a list of image URLs (possibly multiple mirrors per page), pick one URL per
    unique basename and return them ordered by an inferred page index.

    Heuristics:
    - Group by basename (path's final component) to collapse mirrors.
    - Extract the first long integer from the basename (e.g., 87981023) and sort by it.
    - If no integer is found, preserve original order of first occurrence.
    """
    from collections import OrderedDict
    import re

    seen = OrderedDict()
    for u in urls:
        b = _basename_key(u)
        if not b:
            continue
        if b not in seen:
            seen[b] = u

    # Preserve the original order of first occurrence (which usually matches
    # the order in the page's JSON/script). This avoids reordering pages when
    # the numeric ids are not strictly sequential.
    # Also filter out obvious site assets like '/static-assets/'.
    out = []
    # Prefer basenames that look like page images (e.g. 87981023_1920_2735_569558.webp)
    page_re = re.compile(r"\d{7,9}_\d+_\d+_\d+\.(?:jpg|jpeg|png|webp)", re.IGNORECASE)
    pages = []
    others = []
    for b, u in seen.items():
        if '/static-assets/' in u:
            continue
        if page_re.search(b):
            pages.append(u)
        else:
            others.append(u)

    # Return pages first (in original order), then any others.
    return pages + others


def download_and_make_pdf(chapter_url: str, out_pdf_path: str, session: Optional[requests.Session] = None, limit: Optional[int] = None) -> str:
    """Fetch image URLs for chapter_url, select one mirror per page, download them and
    combine into a single PDF saved at out_pdf_path. Returns path to the saved PDF.
    """
    s = session or requests.Session()
    urls = get_image_urls(chapter_url, session=s)
    if not urls:
        raise RuntimeError("No image URLs found")

    chosen = select_one_per_page(urls)
    if limit is not None:
        chosen = chosen[:limit]

    # Prepare output directory for temporary images
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        saved = download_images(chosen, td, prefix="page", session=s, limit=limit)
        if not saved:
            raise RuntimeError("Failed to download images for PDF generation")

        # Convert images to PDF using Pillow
        from PIL import Image

        pil_images = []
        for p in saved:
            try:
                img = Image.open(p)
                # Convert to RGB
                if img.mode in ("RGBA", "LA") or (hasattr(img, "mode") and img.mode != "RGB"):
                    img = img.convert("RGB")
                pil_images.append(img)
            except Exception as e:
                print(f"Warning: failed to open {p} as image: {e}")

        if not pil_images:
            raise RuntimeError("No images could be opened for PDF creation")

        # Ensure output dir exists
        os.makedirs(os.path.dirname(out_pdf_path), exist_ok=True)

        first, rest = pil_images[0], pil_images[1:]
        first.save(out_pdf_path, "PDF", resolution=100.0, save_all=True, append_images=rest)

        return out_pdf_path


def get_latest_chapter(series_id: str, session: Optional[requests.Session] = None):
    """Return the Chapter object for the latest chapter in the series."""
    chapters = get_chapters_from_series(series_id, session)
    if not chapters:
        raise RuntimeError(f"No chapters found for series {series_id}")
    # chapters are sorted by number ascending
    return chapters[-1]


def download_chapter_by_number(series_id: str, chapter_num: float, out_dir: str, make_pdf: bool = True, session: Optional[requests.Session] = None, dry_run: bool = False):
    """Download a specific chapter by number. Returns path to saved artifact.

    If make_pdf is True, creates a PDF under out_dir. Otherwise saves images into a subfolder.
    """
    chap = find_chapter_by_number(series_id, chapter_num, session)
    if not chap:
        raise RuntimeError(f"Chapter {chapter_num} not found for series {series_id}")
    url = chap.get_url(series_id)
    safe_series = series_id.replace('/', '_')
    if make_pdf:
        out_pdf = os.path.join(out_dir, f"{safe_series}_ch_{str(chap.chapter_num).replace('.', '_')}.pdf")
        if dry_run:
            print(f"[dry-run] Would create PDF: {out_pdf} from {url}")
            return out_pdf
        # Skip if already exists
        if os.path.exists(out_pdf) and os.path.getsize(out_pdf) > 1024:
            print(f"Skipping download; PDF already exists: {out_pdf}")
            return out_pdf
        print(f"Downloading chapter {chap.display_name} -> {out_pdf}")
        return download_and_make_pdf(url, out_pdf, session=session)
    else:
        # download images into folder
        out_folder = os.path.join(out_dir, f"{safe_series}_ch_{str(chap.chapter_num).replace('.', '_')}")
        if dry_run:
            print(f"[dry-run] Would download images to: {out_folder} from {url}")
            return out_folder
        # Skip if folder exists and has files
        if os.path.isdir(out_folder) and any(os.scandir(out_folder)):
            print(f"Skipping download; images folder already exists: {out_folder}")
            return out_folder
        print(f"Downloading images for {chap.display_name} -> {out_folder}")
        urls = get_image_urls(url, session=session)
        saved = download_images(urls, out_folder, prefix="page", session=session)
        return out_folder


def download_from_chapter_to_latest(series_id: str, from_chapter: float, out_dir: str, make_pdf: bool = True, session: Optional[requests.Session] = None, dry_run: bool = False):
    """Download all chapters from `from_chapter` up to the latest available.

    Uses the series chapter listing to determine available chapters. If the provided
    from_chapter isn't present, `find_chapter_by_number` will attempt to probe known IDs.
    """
    s = session or requests.Session()
    chapters = get_chapters_from_series(series_id, s)
    if not chapters:
        raise RuntimeError(f"No chapters found for series {series_id}")

    # Resolve starting chapter object
    start_chap = find_chapter_by_number(series_id, from_chapter, s)
    if not start_chap:
        raise RuntimeError(f"Start chapter {from_chapter} could not be resolved")

    # Select chapters with number >= start_chap
    to_download = [c for c in chapters if c.chapter_num >= start_chap.chapter_num]
    if not to_download:
        raise RuntimeError(f"No chapters to download starting from {from_chapter}")

    results = []
    for c in to_download:
        try:
            res = download_chapter_by_number(series_id, c.chapter_num, out_dir, make_pdf=make_pdf, session=s, dry_run=dry_run)
            results.append(res)
        except Exception as e:
            print(f"Error downloading chapter {c.chapter_num}: {e}")
    return results


if __name__ == "__main__":
    # CLI for cron usage: supports --latest and --from
    import argparse

    p = argparse.ArgumentParser(description="Bato.to chapter downloader. Can fetch latest or a range starting from a chapter.")
    p.add_argument("--series", required=True, help="Series ID slug (e.g., 86663-en-grand-blue-dreaming-official)")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--latest", action="store_true", help="Download the latest available chapter")
    group.add_argument("--from", dest="from_chapter", type=float, help="Download from this chapter number up to latest (e.g., 45.5)")

    p.add_argument("--out", "-o", default="downloads", help="Output directory")
    p.add_argument("--no-pdf", dest="pdf", action="store_false", help="Do not generate PDF; save images instead")
    p.add_argument("--dry-run", action="store_true", help="Print actions without downloading")
    args = p.parse_args()

    try:
        if args.latest:
            chap = get_latest_chapter(args.series)
            print(f"Latest chapter: {chap.display_name} -> {chap.get_url(args.series)}")
            download_chapter_by_number(args.series, chap.chapter_num, args.out, make_pdf=args.pdf, dry_run=args.dry_run)

        elif args.from_chapter is not None:
            print(f"Downloading from chapter {args.from_chapter} to latest for series {args.series}")
            download_from_chapter_to_latest(args.series, args.from_chapter, args.out, make_pdf=args.pdf, dry_run=args.dry_run)

    except Exception as e:
        print(f"Error: {e}")
