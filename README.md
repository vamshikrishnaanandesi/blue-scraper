```markdown
# blue-scraper

A tiny scraper to extract stacked manga page images from chapter pages (designed for sites like Bato.to).

Requirements

- Python 3.8+
- requests
- beautifulsoup4
- Pillow (for PDF generation)

Install:

```bash
python3 -m pip install -r requirements.txt
```

Usage:

```bash
# direct chapter URL (legacy behavior)
python3 run_scraper.py "https://bato.si/title/.../vol_x_ch_y" --download -o out_dir

# new cron-friendly mode (preferred)
python3 /path/to/bato_scraper.py --series <series-slug> --latest --out /data/manga

# download a specific chapter (supports half-chapters like 45.5)
python3 /path/to/bato_scraper.py --series <series-slug> --from 45.5 --out /data/manga

# options:
# --no-pdf    : save images instead of generating a PDF
# --dry-run   : print planned actions without downloading (useful for testing / cron logs)
```

Examples

```bash
# Download the latest chapter as a PDF (good for cron)
python3 /home/ubuntu/blue-scraper/bato_scraper.py \
	--series 86663-en-grand-blue-dreaming-official --latest --out /home/ubuntu/manga

# Dry-run: see what would be downloaded
python3 /home/ubuntu/blue-scraper/bato_scraper.py --series 86663-en-grand-blue-dreaming-official --latest --dry-run

# Download all chapters from 45.5 up to the latest
python3 /home/ubuntu/blue-scraper/bato_scraper.py --series 86663-en-grand-blue-dreaming-official --from 45.5 --out /home/ubuntu/manga

# Save images (no PDF)
python3 /home/ubuntu/blue-scraper/bato_scraper.py --series 86663-en-grand-blue-dreaming-official --latest --no-pdf --out /home/ubuntu/manga
```

Notes

- This tool is a lightweight scraper for personal/educational use. Respect site terms and robots.txt and avoid heavy scraping.
- If a site uses Cloudflare or other anti-bot protections it may block requests; consider using session headers, retries, or manual cookies where permitted.

Cron / automation notes

- Use the absolute path to the Python interpreter in your virtualenv when running from cron. For example, if you use a venv at `/home/ubuntu/blue-scraper/.venv`, the command could be:

```bash
/home/ubuntu/blue-scraper/.venv/bin/python3 /home/ubuntu/blue-scraper/bato_scraper.py --series 86663-en-grand-blue-dreaming-official --latest --out /home/ubuntu/manga
```

- Recommended minimal crontab example (runs daily at 04:30):

```cron
30 4 * * * /home/ubuntu/blue-scraper/.venv/bin/python3 /home/ubuntu/blue-scraper/bato_scraper.py --series 86663-en-grand-blue-dreaming-official --latest --out /home/ubuntu/manga >> /home/ubuntu/blue-scraper/cron.log 2>&1
```

- The script will skip downloading if the target PDF already exists (non-empty) or if the images folder already contains files. Use `--dry-run` to verify behavior before scheduling. If you need to re-download, consider adding a `--force` flag (not currently implemented) or remove the existing artifact before cron runs.

Troubleshooting

- If downloads fail due to HTTP restrictions (Cloudflare, captchas, 403/429), try:
	- Adding or customizing headers in the script.
	- Increasing timeouts or adding retries.
	- Running manually to resolve any interactive challenges.

- If PDFs aren't being created, ensure `Pillow` is installed and the `requirements.txt` includes it.
```
