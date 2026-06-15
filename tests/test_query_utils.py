import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.query_utils import average_cycle_days, month_bounds, months_ago_start


class QueryUtilsTest(unittest.TestCase):
    def test_months_ago_start_uses_requested_window(self):
        now = datetime(2026, 6, 15, tzinfo=timezone.utc)

        self.assertEqual(months_ago_start(1, now), datetime(2026, 6, 1, tzinfo=timezone.utc))
        self.assertEqual(months_ago_start(3, now), datetime(2026, 4, 1, tzinfo=timezone.utc))
        self.assertEqual(months_ago_start(12, now), datetime(2025, 7, 1, tzinfo=timezone.utc))

    def test_month_bounds_handles_leap_year(self):
        start, end = month_bounds(2024, 2)

        self.assertEqual(start, datetime(2024, 2, 1, tzinfo=timezone.utc))
        self.assertEqual(end.day, 29)

    def test_average_cycle_days_ignores_invalid_items(self):
        items = [
            SimpleNamespace(
                created_at=datetime(2026, 6, 1),
                completed_at=datetime(2026, 6, 3),
            ),
            SimpleNamespace(
                created_at=datetime(2026, 6, 5, tzinfo=timezone.utc),
                completed_at=datetime(2026, 6, 6, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                created_at=datetime(2026, 6, 7),
                completed_at=datetime(2026, 6, 6),
            ),
        ]

        self.assertEqual(average_cycle_days(items), 1.5)


if __name__ == "__main__":
    unittest.main()
