Tracking the top 10 banks in Malaysia price peformance
The banks are:
| Rank | Bank / Group                          | Bursa Code  | Common Abbreviation | Notes                                                               |
| ---- | ------------------------------------- | ----------- | ------------------- | ------------------------------------------------------------------- |
| 1    | **Malayan Banking Berhad**            | **1155.KL** | **Maybank**         | Malaysia’s largest bank; full ASEAN presence.                       |
| 2    | **Public Bank Berhad**                | **1295.KL** | **Public Bank**     | Retail & SME leader; best asset quality.                            |
| 3    | **CIMB Group Holdings Berhad**        | **1023.KL** | **CIMB**            | ASEAN universal bank; strong Singapore & Indonesia footprint.       |
| 4    | **Hong Leong Bank Berhad**            | **5819.KL** | **HLB**             | Consumer and mortgage strength; part of Hong Leong Group.           |
| 5    | **RHB Bank Berhad**                   | **1066.KL** | **RHB**             | Fourth-largest banking group; growing ASEAN reach.                  |
| 6    | **AMMB Holdings Berhad**              | **1015.KL** | **AmBank**          | Mid-tier bank; retail + wholesale mix.                              |
| 7    | **Hong Leong Financial Group Berhad** | **1082.KL** | **HLFG**            | Holding co. for HLB, HL Assurance & HL Capital.                     |
| 8    | **Alliance Bank Malaysia Berhad**     | **2488.KL** | **Alliance Bank**   | Mid-sized bank; SME and consumer focus.                             |
| 9    | **Malaysia Building Society Berhad**  | **1171.KL** | **MBSB Bank**       | Islamic bank; retail/affordable housing focus.                      |
| 10   | **Affin Bank Berhad**                 | **5185.KL** | **Affin Bank**      | Diversified; expanding SME & Islamic portfolio.                     |

## Automated chart

Use `update_chart.py` (standard-library only) to download daily adjusted close
prices from Yahoo Finance, normalize them to 1 July 2024, and export an
interactive Chart.js visualization to `top_10_malaysian_banks.html`. The script is
intended to run every weekday at 8 PM Singapore time and skips weekends
automatically. For cron jobs:

```
# Run at 20:00 Singapore time (UTC+8) Monday–Friday
0 12 * * 1-5 /usr/bin/python3 /workspace/MBanks/update_chart.py >> /workspace/MBanks/chart.log 2>&1
```

Use the optional `--force` flag if you need to regenerate the file outside the
scheduled window for testing. When running in an offline environment, pass
`--sample-data sample_data/` to use the bundled synthetic CSV files instead of
downloading live quotes. The sample set now mirrors every Bursa Malaysia trading
day from 1 July 2024 through 20 May 2025 (232 sessions), so the generated
relative-price chart preserves the more-than-200 data points per bank that the
production job accumulates.

If you run the script with live network access, add
`--write-sample-data sample_data/` so the freshly downloaded Yahoo Finance CSV
files are mirrored back into the repository. This keeps the offline fixtures in
sync with the latest market sessions without any extra scripting.

## GitHub Actions automation

The workflow defined in `.github/workflows/update-sample-data.yml` runs every
weekday at 20:05 Singapore time (12:05 UTC). It executes

```
python update_chart.py --write-sample-data sample_data
```

which refreshes the Chart.js dashboard and replaces the CSV fixtures with the
latest Yahoo Finance data. When the run detects changed files, it commits and
pushes them back to the default branch using the repository’s built-in
`GITHUB_TOKEN`. Trigger the workflow manually via the “Run workflow” button if
you need an ad-hoc update outside the scheduled time window.


## Committing everything (including `sample_data/`) to GitHub

1. Clone your GitHub repository or pull the latest changes:
   ```bash
   git clone <your-fork-url>
   cd MBanks
   git pull origin main
   ```
2. Generate or refresh the chart/data as usual (for example,
   `python update_chart.py --write-sample-data sample_data`). This updates both
   `top_10_malaysian_banks.html` and the ten CSVs under `sample_data/` locally.
3. Stage every modified file, including the CSV fixtures:
   ```bash
   git add update_chart.py top_10_malaysian_banks.html sample_data/*.csv
   ```
   You can also stage everything at once with `git add -A` if that is easier.
4. Commit and push the changes back to GitHub so the files live in the cloud:
   ```bash
   git commit -m "Refresh KLSE chart and sample data"
   git push origin main
   ```

You never need to copy/paste file contents manually inside the web UI. Once the
files are committed and pushed, GitHub stores `sample_data/` (and every other
tracked file) alongside the code, so collaborators and GitHub Actions runners
all download the same CSV fixtures automatically.

## Getting all files from GitHub in one shot

If you simply want the current snapshot of every tracked file (all ten CSVs
plus the Python/HTML assets), you have two easy options:

1. **Clone the repository** – this is the best approach if you expect to update
   the files and push changes back later. From a terminal:
   ```bash
   git clone <your-repo-url>
   cd MBanks
   ```
   Git creates a local working copy that already contains
   `sample_data/*.csv`, `update_chart.py`, `top_10_malaysian_banks.html`, and
   `Readme.txt`, so you do not have to download 14 files individually.
2. **Download a ZIP from GitHub** – ideal if you only need a one-time copy.
   Open the repository page in your browser, click the green **Code** button,
   choose **Download ZIP**, and unzip the archive locally. The ZIP contains the
   entire project tree, including the `sample_data/` directory with all ten
   fixtures.

Either method ensures you get the exact same set of files that live in the
cloud GitHub repository without any manual copy/paste work.
