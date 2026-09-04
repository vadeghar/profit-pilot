import unittest
from datetime import datetime

from backtest.nifty_atm_straddle_adapter import run_day
from strategies.nifty_atm_straddle import Observation


def o(minute, ce, pe):
    return Observation(datetime(2026, 8, 4, 14, minute), 25000, 14, ce, pe)


class AdapterTests(unittest.TestCase):
    def test_full_lifecycle_and_last_candle_fallback(self):
        trade = run_day([
            o(0, 25, 25),
            o(1, 15, 15),
            o(2, 10, 10),
            o(3, 23, 22),
            o(4, 10, 10),
        ])
        self.assertIsNotNone(trade)
        self.assertEqual(trade.ce_lots_bought, 6)
        self.assertEqual(trade.pe_lots_bought, 6)
        self.assertEqual(trade.ce_lots_sold, 6)
        self.assertEqual(trade.pe_lots_sold, 6)
        self.assertEqual(trade.exit_time, datetime(2026, 8, 4, 14, 4))

    def test_no_entry_returns_no_trade(self):
        self.assertIsNone(run_day([o(0, 30, 30), o(1, 31, 31)]))


if __name__ == "__main__":
    unittest.main()
