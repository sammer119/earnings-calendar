# Earnings Calendar Feed

Auto-generates an `.ics` calendar feed of earnings dates for stocks in a TradingView watchlist, and publishes it via GitHub Pages so Proton Calendar (or any calendar app) can subscribe and stay in sync.

## How it works

1. `watchlist.txt` contains your TradingView watchlist (exported from TradingView).
2. `generate_earnings_ics.py` fetches earnings dates from Finnhub for each symbol.
3. The script writes `docs/earnings.ics`.
4. GitHub Pages serves the file at a public URL.
5. Proton Calendar subscribes to that URL and refreshes automatically.
6. A scheduled GitHub Action re-runs the script daily.

## One-time setup

### 1. Get a free Finnhub API key
Sign up at <https://finnhub.io/> → copy your API key from the dashboard.

### 2. Create the GitHub repo
- Create a new public repo (can be private, but Pages on private repos requires a paid plan).
- Upload these files: `generate_earnings_ics.py`, `watchlist.txt`, `.github/workflows/update-earnings.yml`, and an empty `docs/` folder (or let the first run create it).

### 3. Add the API key as a secret
Repo → **Settings → Secrets and variables → Actions → New repository secret**
- Name: `FINNHUB_API_KEY`
- Value: your Finnhub key

### 4. Enable GitHub Pages
Repo → **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: `main` / folder: `/docs`
- Save. Your feed will be live at `https://<username>.github.io/<repo>/earnings.ics`

### 5. Run the workflow once
Actions tab → **Update earnings calendar** → **Run workflow**.
This generates the first version of `earnings.ics` and commits it.

### 6. Subscribe in Proton Calendar
- Web: **Calendars → Add calendar → Add calendar from URL** → paste the GitHub Pages URL.
- Proton syncs subscribed calendars roughly every 24 hours. For an immediate refresh, remove and re-add the calendar.

## Updating your watchlist

1. In TradingView, click the **table icon** (Advanced View) at the top of your watchlist → **three-dot menu** → **Export...** → save as `.txt`.
2. Replace `watchlist.txt` in the repo with the new file.
3. Next scheduled run (or a manual trigger via the Actions tab) will regenerate the feed.

Lines starting with `###` are TradingView section headers and are ignored by the script.

## Notes

- Events use stable UIDs (hash of ticker + date + quarter), so re-runs update existing events rather than duplicating them.
- Past earnings drop off naturally as they roll out of Finnhub's return window; removed tickers disappear on the next sync.
- The free Finnhub tier allows 60 calls/minute. The script sleeps 1.1s between symbols to stay well under that; a watchlist of 50 symbols takes about a minute.
- Finnhub's free tier has limited coverage for non-US exchanges — LSE, MIL, TSX etc. may return no events.
- Earnings timing (BMO / AMC / TBD) appears in the event description. Events are all-day so they render cleanly across all calendar views.
- If a symbol has no upcoming earnings in the 30-day-back / 180-day-forward window, it produces no events.
