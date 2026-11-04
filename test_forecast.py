"""Regression tests for probability and backtest behavior."""
import unittest
from datetime import date

from forecast import poisson_outcomes, predict_matches, score


class ForecastTests(unittest.TestCase):
    def test_poisson_probabilities_sum_and_swap(self):
        home, draw, away = poisson_outcomes(2.0, 1.0)
        self.assertAlmostEqual(home + draw + away, 1)
        self.assertGreater(home, away)
        self.assertAlmostEqual(poisson_outcomes(1.0, 2.0)[0], away)

    def test_same_day_and_future_results_do_not_change_forecasts(self):
        day = date(2025, 8, 1)
        later = date(2025, 8, 2)
        first = (day, "2526", "A", "B", 5, 0, "H")
        second = (day, "2526", "C", "D", 1, 1, "D")
        third = (later, "2526", "A", "C", 1, 0, "H")
        forecasts = list(predict_matches([first, second, third], 10))
        changed = list(predict_matches([(*first[:4], 0, 4, "A"), second, third], 10))
        self.assertEqual(forecasts[0][1:], changed[0][1:])
        self.assertEqual(forecasts[1][1:], changed[1][1:])
        self.assertNotEqual(forecasts[2][2], changed[2][2])

    def test_metrics_for_perfect_forecast(self):
        row = (date(2025, 8, 1), "2526", "A", "B", 1, 0, "H")
        self.assertEqual(score([(row, (1, 0, 0), (1, 0, 0))], 1),
                         {"matches": 1, "log_loss": 0, "brier": 0, "accuracy": 1})


if __name__ == "__main__":
    unittest.main()
