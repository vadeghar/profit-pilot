import unittest
from datetime import date, datetime

from strategies.nifty_atm_straddle import NiftyAtmStraddleStrategy, Observation, StraddleExitReason, StraddleState


def obs(h, m, spot=25012, vix=14, ce=24, pe=25):
    return Observation(datetime(2026, 8, 3, h, m), spot, vix, ce, pe)


class NiftyAtmStraddleTests(unittest.TestCase):
    def test_eligibility_and_atm_lock(self):
        s = NiftyAtmStraddleStrategy()
        self.assertEqual(s.eligible(date(2026, 8, 2), "BACKTEST", False), "NOT_APPLICABLE")
        self.assertEqual(s.eligible(date(2026, 8, 3), "DEPLOY", False), "NOT_DEPLOYED_NON_EXPIRY_DAY")
        self.assertEqual(s.on_observation(obs(13, 59)), [])
        actions = s.on_observation(obs(14, 1, spot=25041, ce=25, pe=24))
        self.assertEqual([(a.kind, a.ce_lots, a.pe_lots) for a in actions], [("BUY", 2, 2)])
        self.assertEqual(s.runtime.locked_atm_strike, 25050)

    def test_averaging_targets_and_cost_exit(self):
        s = NiftyAtmStraddleStrategy()
        s.on_observation(obs(14, 0))
        self.assertEqual(s.on_observation(obs(14, 5, ce=15, pe=15))[0].kind, "BUY")
        self.assertEqual(s.runtime.state, StraddleState.AFTER_2A)
        self.assertEqual(s.on_observation(obs(14, 10, ce=10, pe=10))[0].kind, "BUY")
        self.assertEqual(s.runtime.state, StraddleState.AFTER_2B)
        target = s.on_observation(obs(14, 15, ce=23, pe=22))[0]
        self.assertEqual((target.kind, target.ce_lots, target.pe_lots), ("SELL", 3, 3))
        close = s.on_observation(obs(14, 20, ce=10, pe=10))[0]
        self.assertEqual(close.reason, StraddleExitReason.COST_EXIT.value)

    def test_hard_stop_precedes_force_exit(self):
        s = NiftyAtmStraddleStrategy()
        s.on_observation(obs(14, 0))
        stop = s.on_observation(obs(14, 1, ce=4, pe=4))[0]
        self.assertEqual(stop.reason, StraddleExitReason.HARD_STOP_LOSS.value)
        self.assertEqual(s.runtime.state, StraddleState.CLOSED)

        s = NiftyAtmStraddleStrategy()
        s.on_observation(obs(14, 0))
        force = s.on_observation(obs(15, 35, ce=100, pe=100))[0]
        self.assertEqual(force.reason, StraddleExitReason.TIME_EXIT.value)


if __name__ == "__main__":
    unittest.main()
