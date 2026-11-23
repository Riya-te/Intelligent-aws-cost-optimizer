
import unittest
from datetime import date as real_date
from unittest.mock import patch

from src.cost_explorer import analyze_cost_anomalies


class TestCostAnomalies(unittest.TestCase):

    def setUp(self):
        self.daily_costs = {}

        # Previous 14 days: stable EC2 spending
        for day in range(8, 22):
            date = f"2026-11-{day:02d}"
            self.daily_costs[date] = {"Amazon EC2": 2.0}

        # Yesterday: sudden increase
        self.daily_costs["2026-11-22"] = {
            "Amazon EC2": 20.0
        }

    @patch("src.cost_explorer.get_daily_service_costs")
    @patch("src.cost_explorer.date")
    def test_detects_cost_anomaly(self, mock_date, mock_costs):

        mock_date.today.return_value = real_date(2026, 11, 23)

        mock_costs.return_value = {
            "currency": "USD",
            "daily_costs": self.daily_costs,
            "period": {
                "Start": "2026-10-24",
                "End": "2026-11-23"
            }
        }

        result = analyze_cost_anomalies()

        self.assertEqual(result["analysis_status"], "completed")
        self.assertEqual(result["anomaly_count"], 1)

        self.assertEqual(
            result["anomalies"][0]["service"],
            "Amazon EC2"
        )

    @patch("src.cost_explorer.get_daily_service_costs")
    @patch("src.cost_explorer.date")
    def test_no_anomaly_for_stable_costs(self, mock_date, mock_costs):

        mock_date.today.return_value = real_date(2026, 11, 23)

        stable_costs = {
            f"2026-11-{day:02d}": {"Amazon EC2": 2.0}
            for day in range(8, 23)
        }

        mock_costs.return_value = {
            "currency": "USD",
            "daily_costs": stable_costs,
            "period": {
                "Start": "2026-10-24",
                "End": "2026-11-23"
            }
        }

        result = analyze_cost_anomalies()

        self.assertEqual(result["analysis_status"], "completed")
        self.assertEqual(result["anomaly_count"], 0)

    @patch("src.cost_explorer.get_daily_service_costs")
    @patch("src.cost_explorer.date")
    def test_missing_yesterday_returns_insufficient_data(
        self, mock_date, mock_costs
    ):

        mock_date.today.return_value = real_date(2026, 11, 23)

        # Remove yesterday's billing data
        incomplete_data = dict(self.daily_costs)
        incomplete_data.pop("2026-11-22", None)

        mock_costs.return_value = {
            "currency": "USD",
            "daily_costs": incomplete_data,
            "period": {
                "Start": "2026-10-24",
                "End": "2026-11-23"
            }
        }

        result = analyze_cost_anomalies()

        self.assertEqual(
            result["analysis_status"],
            "insufficient_data"
        )

        self.assertEqual(result["anomaly_count"], 0)

        self.assertIn(
            "2026-11-22",
            result["warning"]
        )


if __name__ == "__main__":
    unittest.main()
