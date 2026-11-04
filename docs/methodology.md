# Data and methodology

## Data

The source is the Premier League `E0.csv` file in each season’s [Football-Data.co.uk England archive](https://www.football-data.co.uk/englandm.php). Each file contains one row per fixture. The pipeline checks for 380 unique directed fixtures, 20 teams, nonnegative scores, and consistent result labels for each season. Raw files stay in a local cache. The report records SHA-256 hashes so readers can identify differences if the source revises a CSV.

| Role | Seasons | File codes |
| --- | --- | --- |
| Initial history | 2019/20 through 2023/24 | 1920, 2021, 2122, 2223, 2324 |
| Validation | 2024/25 | 2425 |
| Final test | 2025/26 | 2526 |

| Source field | Meaning | Pipeline use |
| --- | --- | --- |
| Date | Match date, day/month/year | Chronological order and same-date batches |
| HomeTeam, AwayTeam | Club names | Identify each club’s prior matches |
| FTHG, FTAG | Full-time goals | Update scoring and conceding history after each date |
| FTR | H = home win, D = draw, A = away win | Verify score-derived labels and evaluate predictions |

The generated predictions CSV includes fixture date, season code, teams, score, and result, followed by the baseline and Poisson probabilities for home win, draw, and away win. The match score and outcome are retrospective evaluation fields.

## Models

- **Running league frequencies.** Each outcome starts with one pseudocount. Before each fixture date, divide the count for an outcome by the total for all three outcomes.
- **Rolling Poisson goals.** For each team, calculate goals scored and conceded per match over the chosen number of prior fixtures. Shrink each mean toward the prior league goals per team using five pseudomatches, then divide by that league mean to get relative attack and defensive weakness. Multiply the league home scoring rate by home attack and away defensive weakness to get the expected home goals. Use the league away rate, away attack, and home defensive weakness for the away estimate. The league scoring rates start with 50 pseudomatches at 1.5 home and 1.2 away goals. Multiply the two Poisson score probabilities across the 0–24 goals grid, sum by result, and normalize.

## Evaluation

Both models learn from the same chronological sequence. At each date, every prediction is emitted before any match that day updates the histories. This uses only information from earlier dates and avoids relying on kickoff times. The test season simulates repeated forecasting with results from earlier test dates available. The 2025/26 results play no role in lookback selection.

| Lookback | 2024/25 validation log loss |
| ---: | ---: |
| 5 | 1.0331 |
| 10 | 1.0063 |
| 20 | 0.9876 |
| 38 | 0.9829 |

## Limitations

- The 38-match window was the largest tested. The analysis does not establish that 38 is an optimal lookback.
- The model assumes goal counts are conditionally independent, which can miss low-scoring dependence and game-state effects. In the final test the model underpredicted draws in aggregate and never gave a draw the highest probability.
- The model has no lineup, injury, rest, or schedule-strength features. It treats matches from different seasons alike when they fall inside the window and has limited history for promoted clubs.
- The test spans one season. A broader evaluation would use several rolling test seasons, a stronger team-rating baseline, and calibration by outcome. The outcome chart checks average probabilities only.
