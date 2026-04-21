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
- Proton refreshes subscribed calendars periodically (not instantly), but every update you push will show up.

## Updating your watchlist

1. In TradingView, right-click your watchlist → **Export data** → save as `.txt`.
2. Replace `watchlist.txt` in the repo with the new file.
3. Next scheduled run (or a manual trigger) will regenerate the feed.

## Notes

- Events use stable UIDs (hash of ticker+date+quarter), so re-runs update existing events rather than duplicating them.
- The free Finnhub tier allows 60 calls/minute. The script sleeps 1.1s between symbols to stay well under that; for a watchlist of 50 symbols, a run takes about a minute.
- Earnings times (BMO / AMC) are included in the event description. Events themselves are all-day so they show cleanly in every calendar view.
- If a symbol has no upcoming earnings in the 30-day-back / 180-day-forward window, it simply produces no events.
