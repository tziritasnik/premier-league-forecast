"""Reproduce a chronological Premier League probability backtest."""
import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from itertools import groupby
from pathlib import Path
from urllib.request import urlopen

SEASONS = ("1920", "2021", "2122", "2223", "2324", "2425", "2526")
OUTCOMES = ("H", "D", "A")
WINDOWS = (5, 10, 20, 38)
PRIOR_MATCHES = 5
ROOT = Path(__file__).resolve().parent


def load_matches(cache):
    cache.mkdir(parents=True, exist_ok=True)
    matches, sources = [], {}
    for season in SEASONS:
        url = f"https://www.football-data.co.uk/mmz4281/{season}/E0.csv"
        path = cache / f"{season}.csv"
        if not path.exists():
            with urlopen(url, timeout=30) as response:
                raw = response.read()
        else:
            raw = path.read_bytes()
        rows = []
        for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace"))):
            if not row.get("Date"):
                continue
            date = datetime.strptime(row["Date"], "%d/%m/%Y").date()
            home, away = row["HomeTeam"], row["AwayTeam"]
            home_goals, away_goals = int(row["FTHG"]), int(row["FTAG"])
            result = "H" if home_goals > away_goals else "A" if away_goals > home_goals else "D"
            if not home or not away or home == away or min(home_goals, away_goals) < 0 or row["FTR"] != result:
                raise ValueError(f"Invalid result in {season}: {row}")
            rows.append((date, season, home, away, home_goals, away_goals, result))
        pairs = {(row[2], row[3]) for row in rows}
        teams = {row[2] for row in rows} | {row[3] for row in rows}
        if len(rows) != 380 or len(pairs) != 380 or len(teams) != 20:
            raise ValueError(f"Expected a complete 20-team season in {path}")
        if not path.exists():
            path.write_bytes(raw)
        matches.extend(rows)
        sources[season] = {"url": url, "matches": len(rows), "sha256": hashlib.sha256(raw).hexdigest()}
    return sorted(matches), sources


def smoothed_mean(values, prior):
    return (sum(values) + PRIOR_MATCHES * prior) / (len(values) + PRIOR_MATCHES)


def poisson_outcomes(home_rate, away_rate):
    def pmf(rate):
        values = [math.exp(-rate)]
        for goals in range(1, 25):
            values.append(values[-1] * rate / goals)
        return values

    probs = [0.0, 0.0, 0.0]
    for home_goals, home_prob in enumerate(pmf(home_rate)):
        for away_goals, away_prob in enumerate(pmf(away_rate)):
            index = 0 if home_goals > away_goals else 2 if home_goals < away_goals else 1
            probs[index] += home_prob * away_prob
    total = sum(probs)
    return tuple(prob / total for prob in probs)


def predict_matches(matches, window):
    history = defaultdict(list)
    results = Counter()
    home_total = away_total = played = 0
    for _, same_day in groupby(matches, key=lambda row: row[0]):
        batch = list(same_day)
        home_prior = (home_total + 50 * 1.5) / (played + 50)
        away_prior = (away_total + 50 * 1.2) / (played + 50)
        neutral = (home_prior + away_prior) / 2
        baseline = tuple((results[label] + 1) / (played + 3) for label in OUTCOMES)
        for row in batch:
            _, _, home, away, *_ = row
            home_form = history[home][-window:]
            away_form = history[away][-window:]
            home_attack = smoothed_mean([gf for gf, _ in home_form], neutral) / neutral
            home_defense = smoothed_mean([ga for _, ga in home_form], neutral) / neutral
            away_attack = smoothed_mean([gf for gf, _ in away_form], neutral) / neutral
            away_defense = smoothed_mean([ga for _, ga in away_form], neutral) / neutral
            model = poisson_outcomes(home_prior * home_attack * away_defense,
                                     away_prior * away_attack * home_defense)
            yield row, baseline, model
        for _, _, home, away, hg, ag, outcome in batch:
            history[home].append((hg, ag))
            history[away].append((ag, hg))
            results[outcome] += 1
            home_total += hg
            away_total += ag
            played += 1


def score(predictions, column):
    loss = brier = correct = 0
    for row, baseline, model in predictions:
        probs = (baseline, model)[column]
        actual = OUTCOMES.index(row[-1])
        loss -= math.log(max(probs[actual], 1e-15))
        brier += sum((prob - (i == actual)) ** 2 for i, prob in enumerate(probs))
        correct += probs.index(max(probs)) == actual
    n = len(predictions)
    return {"matches": n, "log_loss": loss / n, "brier": brier / n, "accuracy": correct / n}


def write_predictions(path, predictions):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["date", "season", "home_team", "away_team", "home_goals", "away_goals", "result",
                         "baseline_home", "baseline_draw", "baseline_away", "model_home", "model_draw", "model_away"])
        for row, baseline, model in predictions:
            writer.writerow([*row, *baseline, *model])


def write_outcome_chart(path, predictions):
    """Compare average forecast probabilities with observed frequencies."""
    n = len(predictions)
    means = [
        [sum(pred[column][i] for pred in predictions) / n for i in range(3)]
        for column in (1, 2)
    ]
    means.append([sum(pred[0][-1] == label for pred in predictions) / n for label in OUTCOMES])
    colors = ("#8394AA", "#047D86", "#253A59")
    names = ("Baseline", "Poisson model", "Observed")
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 395" role="img" aria-labelledby="title desc">',
        '<title id="title">Forecast probabilities and observed outcomes</title>',
        '<desc id="desc">Mean home, draw and away probabilities for both models versus the observed rates in 380 matches.</desc>',
        '<rect width="760" height="395" rx="16" fill="#F6F8FC"/>',
        '<g font-family="system-ui, sans-serif" fill="#172942">',
        '<text x="32" y="40" font-size="23" font-weight="700">Forecast probabilities and observed outcomes</text>',
        '<text x="32" y="65" font-size="14">Premier League 2025/26 · 380 held-out matches</text>',
    ]
    for tick in range(0, 51, 10):
        y = 308 - tick * 3.75
        svg.append(f'<path d="M66 {y} H731" stroke="#D5DFEB"/>')
        svg.append(f'<text x="55" y="{y + 4}" text-anchor="end" font-size="12">{tick}%</text>')
    for i, outcome in enumerate(("Home win", "Draw", "Away win")):
        center = 178 + i * 220
        svg.append(f'<text x="{center}" y="335" text-anchor="middle" font-size="15" font-weight="600">{outcome}</text>')
        for j, color in enumerate(colors):
            percent = 100 * means[j][i]
            height = percent * 3.75
            x = center + (j - 1) * 47
            svg.append(f'<rect x="{x - 19}" y="{308-height:.2f}" width="38" height="{height:.2f}" rx="3" fill="{color}"/>')
            svg.append(f'<text x="{x}" y="{300-height:.2f}" text-anchor="middle" font-size="11">{percent:.1f}%</text>')
    for j, (name, color) in enumerate(zip(names, colors)):
        x = 197 + j * 127
        svg.append(f'<rect x="{x}" y="360" width="13" height="13" rx="2" fill="{color}"/>')
        svg.append(f'<text x="{x + 20}" y="371" font-size="13">{name}</text>')
    svg.append("</g></svg>")
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--output", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    matches, sources = load_matches(args.cache)
    validation = {}
    for window in WINDOWS:
        # Stop before the test season when selecting the window.
        history = [row for row in matches if row[1] != SEASONS[-1]]
        predictions = [p for p in predict_matches(history, window) if p[0][1] == SEASONS[-2]]
        validation[window] = score(predictions, 1)
    selected = min(WINDOWS, key=lambda window: validation[window]["log_loss"])
    test = [p for p in predict_matches(matches, selected) if p[0][1] == SEASONS[-1]]
    metrics = {
        "selected_window": selected,
        "validation_season": "2024/25",
        "validation_by_window": validation,
        "test_season": "2025/26",
        "test": {"baseline": score(test, 0), "poisson": score(test, 1)},
        "test_outcomes": dict(Counter(row[-1] for row, _, _ in test)),
        "sources": sources,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    write_predictions(args.output / "predictions.csv", test)
    write_outcome_chart(args.output / "outcomes.svg", test)
    print(json.dumps(metrics["test"], indent=2))
    print(f"Selected window: {selected}. Reports written to {args.output}")


if __name__ == "__main__":
    main()
