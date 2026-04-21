"""
Generate an ICS calendar feed of earnings dates for tickers in a TradingView
watchlist export, using Finnhub as the data source.

Inputs:
  - watchlist.txt   (TradingView export: one symbol per line, may include exchange prefix)
  - FINNHUB_API_KEY environment variable

Output:
  - docs/earnings.ics  (served by GitHub Pages)
"""

import os
import sys
import re
import time
import hashlib
import datetime as dt
from pathlib import Path

import requests

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")
if not FINNHUB_API_KEY:
    print("ERROR: FINNHUB_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)

# Look ahead this many days for upcoming earnings
LOOKAHEAD_DAYS = 180
# Also include recent past earnings so the calendar keeps history
LOOKBACK_DAYS = 30

# Event timing (in US Eastern time, so it auto-adjusts for DST)
# BMO = earnings typically drop ~8:30am ET, ~1hr before NYSE open
# AMC = earnings typically drop ~4:15pm ET, just after NYSE close
# TBD = noon ET as a neutral placeholder
BMO_TIME = (8, 30)    # 8:30am ET  -> 1:30pm UK (winter) / 1:30pm UK (summer via BST)
AMC_TIME = (16, 15)   # 4:15pm ET  -> 9:15pm UK
TBD_TIME = (12, 0)    # 12:00pm ET -> 5:00pm UK
EVENT_DURATION_MIN = 30

WATCHLIST_PATH = Path("watchlist.txt")
OUTPUT_PATH = Path("docs/earnings.ics")

FINNHUB_URL = "https://finnhub.io/api/v1/calendar/earnings"


def parse_watchlist(path: Path) -> list[str]:
    """
    Parse a TradingView watchlist .txt export.
    Lines look like:  NASDAQ:AAPL   or   AAPL   or   ###SectionHeader
    We strip exchange prefixes and skip section headers / blanks.
    """
    symbols: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("###") or line.startswith("#"):
            continue
        # Strip exchange prefix like "NASDAQ:" or "LSE:"
        if ":" in line:
            line = line.split(":", 1)[1]
        # Finnhub uses plain tickers; strip anything weird
        line = re.sub(r"[^A-Z0-9.\-]", "", line.upper())
        if line:
            symbols.append(line)
    # Deduplicate, preserve order
    seen = set()
    unique = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def fetch_earnings(symbol: str, date_from: str, date_to: str) -> list[dict]:
    """Fetch earnings events for one symbol from Finnhub."""
    params = {
        "symbol": symbol,
        "from": date_from,
        "to": date_to,
        "token": FINNHUB_API_KEY,
    }
    try:
        r = requests.get(FINNHUB_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json() or {}
        return data.get("earningsCalendar") or []
    except requests.RequestException as e:
        print(f"  ! {symbol}: request failed ({e})", file=sys.stderr)
        return []


def ics_escape(text: str) -> str:
    """Escape text for ICS per RFC 5545."""
    return (
        text.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n")
    )


def build_event(evt: dict) -> str | None:
    """Build a single VEVENT block from a Finnhub earnings record."""
    symbol = evt.get("symbol")
    date_str = evt.get("date")
    if not symbol or not date_str:
        return None

    hour = evt.get("hour", "")  # 'bmo', 'amc', 'dmh', or ''
    hour_label = {
        "bmo": "Before Market Open",
        "amc": "After Market Close",
        "dmh": "During Market Hours",
    }.get(hour, "Time TBD")
    hour_emoji = {
        "bmo": "🌅",
        "amc": "🌝",
        "dmh": "🔔",
    }.get(hour, "⏰")

    # Pick the event start time based on earnings timing
    start_hm = {
        "bmo": BMO_TIME,
        "amc": AMC_TIME,
        "dmh": TBD_TIME,
    }.get(hour, TBD_TIME)

    eps_est = evt.get("epsEstimate")
    eps_act = evt.get("epsActual")
    rev_est = evt.get("revenueEstimate")
    rev_act = evt.get("revenueActual")
    quarter = evt.get("quarter")
    year = evt.get("year")

    summary = f"{hour_emoji} {symbol} Earnings"
    if quarter and year:
        summary += f" (Q{quarter} {year})"

    desc_lines = [f"Symbol: {symbol}", f"Timing: {hour_label}"]
    if quarter and year:
        desc_lines.append(f"Quarter: Q{quarter} {year}")
    if eps_est is not None:
        desc_lines.append(f"EPS Estimate: {eps_est}")
    if eps_act is not None:
        desc_lines.append(f"EPS Actual: {eps_act}")
    if rev_est is not None:
        desc_lines.append(f"Revenue Estimate: {rev_est:,}")
    if rev_act is not None:
        desc_lines.append(f"Revenue Actual: {rev_act:,}")
    description = ics_escape("\n".join(desc_lines))

    # Stable UID so re-runs update rather than duplicate the event.
    uid_seed = f"{symbol}-{date_str}-{quarter}-{year}"
    uid = hashlib.sha1(uid_seed.encode()).hexdigest() + "@earnings-feed"

    dtstamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # Build timed event anchored to America/New_York so it auto-adjusts for DST
    event_date = dt.date.fromisoformat(date_str)
    start_dt = dt.datetime.combine(
        event_date, dt.time(start_hm[0], start_hm[1])
    )
    end_dt = start_dt + dt.timedelta(minutes=EVENT_DURATION_MIN)
    dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
    dtend = end_dt.strftime("%Y%m%dT%H%M%S")

    return "\r\n".join([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;TZID=America/New_York:{dtstart}",
        f"DTEND;TZID=America/New_York:{dtend}",
        f"SUMMARY:{ics_escape(summary)}",
        f"DESCRIPTION:{description}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ])


def vtimezone_block() -> str:
    """
    Minimal VTIMEZONE definition for America/New_York.
    Required by RFC 5545 when using TZID references.
    """
    return "\r\n".join([
        "BEGIN:VTIMEZONE",
        "TZID:America/New_York",
        "BEGIN:STANDARD",
        "DTSTART:19701101T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU",
        "TZOFFSETFROM:-0400",
        "TZOFFSETTO:-0500",
        "TZNAME:EST",
        "END:STANDARD",
        "BEGIN:DAYLIGHT",
        "DTSTART:19700308T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU",
        "TZOFFSETFROM:-0500",
        "TZOFFSETTO:-0400",
        "TZNAME:EDT",
        "END:DAYLIGHT",
        "END:VTIMEZONE",
    ])


def build_calendar(events: list[str]) -> str:
    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//earnings-feed//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Earnings (TradingView Watchlist)",
        "X-WR-CALDESC:Auto-generated earnings dates from Finnhub",
        "X-PUBLISHED-TTL:PT6H",
    ]
    return "\r\n".join(header + [vtimezone_block()] + events + ["END:VCALENDAR"]) + "\r\n"


def main() -> int:
    if not WATCHLIST_PATH.exists():
        print(f"ERROR: {WATCHLIST_PATH} not found", file=sys.stderr)
        return 1

    symbols = parse_watchlist(WATCHLIST_PATH)
    if not symbols:
        print("ERROR: no symbols parsed from watchlist", file=sys.stderr)
        return 1

    today = dt.date.today()
    date_from = (today - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    date_to = (today + dt.timedelta(days=LOOKAHEAD_DAYS)).isoformat()

    print(f"Fetching earnings for {len(symbols)} symbols ({date_from} -> {date_to})")

    all_events: list[str] = []
    for i, sym in enumerate(symbols, 1):
        records = fetch_earnings(sym, date_from, date_to)
        kept = 0
        for rec in records:
            block = build_event(rec)
            if block:
                all_events.append(block)
                kept += 1
        print(f"  [{i}/{len(symbols)}] {sym}: {kept} event(s)")
        # Finnhub free tier = 60 calls/min; sleep to stay well under
        time.sleep(1.1)

    ics = build_calendar(all_events)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(ics, encoding="utf-8")

    print(f"\nWrote {len(all_events)} events to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
