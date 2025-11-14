"""Create/update the Top 10 Malaysian banks relative price chart.

The script fetches daily price data (Adj Close) for the ten KLSE tickers, normalizes
each time-series to the closing price on 1 July 2024, and writes an HTML page with
an interactive line chart. The job is intended to run every weekday at 8 PM
Singapore time (UTC+8) and can be scheduled via cron or another task runner.

Because the execution environment for this repository may not always have internet
access, the script also supports reading Yahoo Finance–formatted CSV files from a
local folder. This enables testing (`--sample-data sample_data/`) without making
network calls.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, time, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Set, Tuple
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_DATE = date(2024, 7, 1)
SINGAPORE_TZ = timezone(timedelta(hours=8))
PAGE_TITLE = "Top 10 Malaysian Banks Performance with base 1 Jul 2024"
OUTPUT_HTML = Path("top_10_malaysian_banks.html")


@dataclass(frozen=True)
class Bank:
    name: str
    ticker: str


BANKS: Sequence[Bank] = (
    Bank("Malayan Banking Berhad (Maybank)", "1155.KL"),
    Bank("Public Bank Berhad", "1295.KL"),
    Bank("CIMB Group Holdings Berhad", "1023.KL"),
    Bank("Hong Leong Bank Berhad", "5819.KL"),
    Bank("RHB Bank Berhad", "1066.KL"),
    Bank("AMMB Holdings Berhad (AmBank)", "1015.KL"),
    Bank("Hong Leong Financial Group Berhad", "1082.KL"),
    Bank("Alliance Bank Malaysia Berhad", "2488.KL"),
    Bank("Malaysia Building Society Berhad (MBSB)", "1171.KL"),
    Bank("Affin Bank Berhad", "5185.KL"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the weekday/8 PM Singapore execution guard.",
    )
    parser.add_argument(
        "--sample-data",
        type=Path,
        help=(
            "Optional directory containing Yahoo Finance CSV files named <ticker>.csv. "
            "When provided, network downloads are skipped and data is read locally."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_HTML,
        help=f"HTML file to write (default: {OUTPUT_HTML}).",
    )
    parser.add_argument(
        "--write-sample-data",
        type=Path,
        help=(
            "Optional directory to mirror freshly downloaded Yahoo Finance CSV files. "
            "Only applies when network data is used."
        ),
    )
    parser.add_argument(
        "--fallback-sample-data",
        type=Path,
        help=(
            "Optional directory to read previously mirrored CSV files from if a "
            "download fails. Defaults to --write-sample-data when that flag is set."
        ),
    )
    return parser.parse_args()


def ensure_schedule(force: bool) -> None:
    if force:
        return

    now_utc = datetime.now(timezone.utc)
    now_sgt = now_utc.astimezone(SINGAPORE_TZ)
    if now_sgt.weekday() >= 5:
        raise SystemExit("Weekend detected (Sat/Sun). Skipping refresh.")
    if now_sgt.time() < time(hour=20):
        raise SystemExit("It is not yet 8 PM Singapore time. Skipping refresh.")


def yahoo_csv_url(ticker: str) -> str:
    start = datetime(BASE_DATE.year, BASE_DATE.month, BASE_DATE.day, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    params = urlencode(
        {
            "period1": int(start.timestamp()),
            "period2": int(now.timestamp()),
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    return f"https://query1.finance.yahoo.com/v7/finance/download/{ticker}?{params}"


def fetch_remote_csv(ticker: str) -> str:
    url = yahoo_csv_url(ticker)
    with urlopen(url) as response:  # nosec B310 - URL constructed from known base
        return response.read().decode("utf-8")


def parse_csv_rows(text: str) -> "OrderedDict[date, float]":
    rows: "OrderedDict[date, float]" = OrderedDict()
    reader = csv.DictReader(text.splitlines())
    for row in reader:
        if not row or not row.get("Date"):
            continue
        adj_close = row.get("Adj Close") or row.get("Adj Close*")
        if not adj_close or adj_close == "null":
            continue
        try:
            value = float(adj_close)
        except ValueError:
            continue
        try:
            day = datetime.strptime(row["Date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        rows[day] = value
    return rows


def load_prices(
    tickers: Sequence[str],
    sample_dir: Path | None,
    mirror_dir: Path | None,
    fallback_dir: Path | None,
) -> Mapping[str, "OrderedDict[date, float]"]:
    prices: Dict[str, "OrderedDict[date, float]"] = {}
    if mirror_dir and not sample_dir:
        mirror_dir.mkdir(parents=True, exist_ok=True)
    fallback_candidates: List[Path] = []
    seen_dirs: Set[Path] = set()
    for directory in (fallback_dir, mirror_dir):
        if directory and directory not in seen_dirs:
            fallback_candidates.append(directory)
            seen_dirs.add(directory)
    for ticker in tickers:
        if sample_dir:
            csv_path = sample_dir / f"{ticker}.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"Missing sample data file: {csv_path}")
            text = csv_path.read_text(encoding="utf-8")
        else:
            try:
                text = fetch_remote_csv(ticker)
            except URLError as exc:
                text = None
                for directory in fallback_candidates:
                    csv_path = directory / f"{ticker}.csv"
                    if csv_path.exists():
                        print(
                            f"Warning: download failed for {ticker} ({exc}). "
                            f"Falling back to cached data at {csv_path}",
                            file=sys.stderr,
                        )
                        text = csv_path.read_text(encoding="utf-8")
                        break
                if text is None:
                    raise RuntimeError(
                        f"Failed to download data for {ticker}: {exc}. No fallback file present."
                    ) from exc
            if mirror_dir:
                (mirror_dir / f"{ticker}.csv").write_text(text, encoding="utf-8")
        prices[ticker] = parse_csv_rows(text)
    return prices


def compute_relative(prices: Mapping[str, "OrderedDict[date, float]"]) -> Mapping[str, List[Tuple[date, float]]]:
    relative: Dict[str, List[Tuple[date, float]]] = {}
    for ticker, series in prices.items():
        filtered = [(d, v) for d, v in series.items() if d >= BASE_DATE]
        if not filtered:
            raise RuntimeError(f"No data found on or after {BASE_DATE} for {ticker}.")
        filtered.sort(key=lambda item: item[0])
        base_value = None
        for d, v in filtered:
            if d >= BASE_DATE:
                base_value = v
                break
        if base_value is None:
            raise RuntimeError(f"Unable to determine base price for {ticker}.")
        relative[ticker] = [(d, v / base_value) for d, v in filtered]
    return relative


def build_chart_json(relative_prices: Mapping[str, List[Tuple[date, float]]], ticker_to_name: Mapping[str, str]) -> str:
    datasets = []
    palette = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]
    for index, (ticker, points) in enumerate(relative_prices.items()):
        datasets.append(
            {
                "label": ticker_to_name.get(ticker, ticker),
                "borderColor": palette[index % len(palette)],
                "backgroundColor": palette[index % len(palette)],
                "fill": False,
                "data": [
                    {"x": d.isoformat(), "y": round(value, 4)} for d, value in points
                ],
            }
        )
    payload = {
        "datasets": datasets,
        "yTitle": "Relative Price (1 Jul 2024 = 1.0)",
    }
    return json.dumps(payload, indent=2)


def render_html(chart_json: str, updated_at: datetime) -> str:
    timestamp = updated_at.strftime("%d %b %Y %H:%M %Z")
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{PAGE_TITLE}</title>
  <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>
  <script src=\"https://cdn.jsdelivr.net/npm/luxon@3/build/global/luxon.min.js\"></script>
  <script src=\"https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon\"></script>
  <style>
    :root {{ font-family: 'Segoe UI', Tahoma, sans-serif; background:#f4f4f4; }}
    body {{ margin:0; padding:1rem; }}
    h1 {{ text-align:center; }}
    .container {{ max-width:1200px; margin:0 auto; background:#fff; padding:1rem 2rem; box-shadow:0 2px 8px rgba(0,0,0,0.1); }}
    .meta {{ text-align:center; color:#666; margin-bottom:1rem; }}
    canvas {{ width:100%; max-height:600px; }}
  </style>
</head>
<body>
  <div class=\"container\">
    <h1>{PAGE_TITLE}</h1>
    <p class=\"meta\">Last updated: {timestamp}</p>
    <canvas id=\"banksChart\"></canvas>
  </div>
  <script>
    const chartData = {chart_json};
    const ctx = document.getElementById('banksChart').getContext('2d');
    new Chart(ctx, {{
      type: 'line',
      data: {{ datasets: chartData.datasets }},
      options: {{
        responsive: true,
        interaction: {{ mode: 'nearest', axis: 'x', intersect: false }},
        stacked: false,
        scales: {{
          x: {{ type: 'time', time: {{ unit: 'month' }}, title: {{ display: true, text: 'Date' }} }},
          y: {{ title: {{ display: true, text: chartData.yTitle }}, ticks: {{ callback: (value) => value.toFixed(2) }} }}
        }},
        plugins: {{ legend: {{ position: 'bottom' }} }}
      }}
    }});
  </script>
</body>
</html>"""


def save_html(content: str, path: Path) -> None:
    path.write_text(content, encoding="utf-8")


def main() -> None:
    args = parse_args()
    ensure_schedule(force=args.force)

    tickers = [bank.ticker for bank in BANKS]
    ticker_to_name = {bank.ticker: bank.name for bank in BANKS}

    fallback_dir = args.fallback_sample_data or args.write_sample_data
    prices = load_prices(tickers, args.sample_data, args.write_sample_data, fallback_dir)
    relative = compute_relative(prices)
    chart_json = build_chart_json(relative, ticker_to_name)
    html = render_html(chart_json, datetime.now(timezone.utc))
    save_html(html, args.output)

    print(f"Chart updated -> {args.output}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        print(f"Error updating chart: {exc}", file=sys.stderr)
        raise
