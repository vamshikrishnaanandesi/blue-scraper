#!/usr/bin/env bash
set -euo pipefail

# Entry point for the blue-scraper container.
# Modes:
# - If RUN_ONCE is set to "1" (or non-empty), run the scraper once with provided env vars and exit.
# - If CRON is set to "true", install a cron job using CRON_SCHEDULE to run the scraper regularly and start cron.
# Environment variables:
#   SERIES (required)         - series slug, e.g. 86663-en-grand-blue-dreaming-official
#   CRON                      - when "true", enable cron mode
#   CRON_SCHEDULE             - cron schedule (default: "30 4 * * *")
#   PDF                       - when "false", use --no-pdf to save images instead of PDF (default: true)
#   RUN_ONCE                  - when set, run once and exit
#   DRY_RUN                   - when set to "1", use --dry-run

APP_DIR="/app"
PYTHON=/usr/local/bin/python

: ${SERIES:=""}
: ${CRON_SCHEDULE:="30 4 * * *"}
: ${CRON:="false"}
: ${PDF:="true"}
DRY_RUN_FLAG=""

if [ "${DRY_RUN:-}" = "1" ] || [ "${DRY_RUN:-}" = "true" ]; then
  DRY_RUN_FLAG="--dry-run"
fi

if [ -z "$SERIES" ]; then
  echo "ERROR: environment variable SERIES must be set (e.g. 86663-en-grand-blue-dreaming-official)"
  echo "You can also invoke the container with arguments to run once: docker run --rm blue-scraper:latest python /app/bato_scraper.py --series <slug> --latest"
  exit 2
fi

run_cmd() {
  local mode_flag="$1"
  local out_dir="/data/manga"
  local pdf_flag=""
  if [ "${PDF}" = "false" ] || [ "${PDF}" = "0" ]; then
    pdf_flag="--no-pdf"
  fi
  echo "Running: $PYTHON /app/bato_scraper.py --series ${SERIES} ${mode_flag} --out ${out_dir} ${pdf_flag} ${DRY_RUN_FLAG}"
  exec $PYTHON /app/bato_scraper.py --series "$SERIES" ${mode_flag} --out "$out_dir" ${pdf_flag} ${DRY_RUN_FLAG}
}

if [ "${RUN_ONCE:-}" != "" ] && [ "${RUN_ONCE:-}" != "0" ]; then
  # user requested a single run
  # default to latest if no mode provided
  if [ "${MODE:-}" = "from" ] || [ "${FROM_CHAPTER:-}" != "" ]; then
    # run from a chapter to latest
    if [ "${FROM_CHAPTER:-}" = "" ]; then
      echo "ERROR: FROM_CHAPTER must be set when MODE=from"
      exit 2
    fi
    $PYTHON /app/bato_scraper.py --series "$SERIES" --from "$FROM_CHAPTER" --out "/data/manga" ${pdf_flag:-}
    exit $?
  fi
  # default: latest
  $PYTHON /app/bato_scraper.py --series "$SERIES" --latest --out "/data/manga" ${pdf_flag:-} ${DRY_RUN_FLAG}
  exit $?
fi

if [ "${CRON}" = "true" ]; then
  echo "Setting up cron job: schedule='${CRON_SCHEDULE}' series='${SERIES}'"
  # write cron file
  CRON_FILE=/etc/cron.d/blue-scraper
  mkdir -p /var/log/blue-scraper
  echo "${CRON_SCHEDULE} root ${PYTHON} /app/bato_scraper.py --series ${SERIES} --latest --out /data/manga ${DRY_RUN_FLAG} >> /var/log/blue-scraper/cron.log 2>&1" > ${CRON_FILE}
  chmod 0644 ${CRON_FILE}
  # ensure cron log exists
  touch /var/log/blue-scraper/cron.log
  chmod 0644 /var/log/blue-scraper/cron.log

  echo "Starting cron (foreground)..."
  # Start cron in foreground
  exec cron -f
else
  # If CRON not enabled and not RUN_ONCE, default to running latest once
  echo "Running one-off latest fetch for series ${SERIES}"
  $PYTHON /app/bato_scraper.py --series "$SERIES" --latest --out "/data/manga" ${DRY_RUN_FLAG}
  exit $?
fi
