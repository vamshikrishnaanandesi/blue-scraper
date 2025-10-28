"""CLI runner for bato_scraper.py"""
from __future__ import annotations

import argparse
import os
from bato_scraper import get_image_urls, download_images, download_and_make_pdf
from chapter_discovery import get_chapter_url


def main():
    p = argparse.ArgumentParser(description="Bato.to chapter image scraper")
    p.add_argument("--url", help="Direct chapter URL to scrape (optional)")
    p.add_argument("--series", help="Series ID (e.g., 86663-en-grand-blue-dreaming-official)")
    p.add_argument("--chapter", type=float, help="Chapter number (e.g., 45.5)")
    p.add_argument("--download", "-d", action="store_true", help="Download images")
    p.add_argument("--pdf", action="store_true", help="Download images and combine into a PDF in workspace results/")
    p.add_argument("--out", "-o", default="downloads", help="Output directory")
    p.add_argument("--limit", "-n", type=int, default=None, help="Limit number of images to download")
    args = p.parse_args()

    # Get chapter URL either directly or via discovery
    if args.url:
        chapter_url = args.url
    elif args.series and args.chapter is not None:
        try:
            chapter_url = get_chapter_url(args.series, args.chapter)
        except Exception as e:
            print(f"Failed to find chapter: {e}")
            return 1
    else:
        print("Error: Must provide either --url or both --series and --chapter")
        return 1

    print(f"Fetching images from: {chapter_url}")
    urls = get_image_urls(chapter_url)
    print(f"Found {len(urls)} images")
    for u in urls:
        print(u)

    if args.download and urls:
        os.makedirs(args.out, exist_ok=True)
        saved = download_images(urls, args.out, prefix="page", limit=args.limit)
        print(f"Downloaded {len(saved)} images to {os.path.abspath(args.out)}")

    if args.pdf:
        # results folder inside the blue-scraper package directory
        results_dir = os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(results_dir, exist_ok=True)
        # generate a filename from the chapter slug
        slug = os.path.basename(args.url.rstrip("/"))
        out_pdf = os.path.join(results_dir, f"{slug}.pdf")
        print(f"Generating PDF to: {out_pdf}")
        try:
            pdfp = download_and_make_pdf(args.url, out_pdf, limit=args.limit)
            print(f"PDF saved to {pdfp}")
        except Exception as e:
            print(f"Failed to create PDF: {e}")


if __name__ == "__main__":
    main()
