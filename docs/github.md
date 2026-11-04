# Repository maintenance

The public project is hosted at [tziritasnik/premier-league-forecast](https://github.com/tziritasnik/premier-league-forecast). Follow the [README](../README.md#reproduce-the-analysis) for the setup and reproduction commands.

The [Tests workflow](https://github.com/tziritasnik/premier-league-forecast/actions/workflows/tests.yml) runs the unit tests with Python 3.12 on pushes and pull requests. For changes to the data pipeline or model, also run the full backtest and review the changes to the committed metrics and chart. Keep the README results and methodology in sync with any intentional changes to the reference results.

Raw season CSVs and generated per-match predictions are excluded from version control. The project fetches source data locally and records its checksums in the metrics report.
