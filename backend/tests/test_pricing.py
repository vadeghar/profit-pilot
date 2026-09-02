import unittest

from strategies.pricing import black_scholes_price, implied_volatility, option_delta


class PricingTests(unittest.TestCase):
    def test_at_the_money_call_price(self):
        price = black_scholes_price(100, 100, 1, 0, 0, 0.2, "CE")
        self.assertAlmostEqual(price, 7.9656, places=3)

    def test_at_the_money_put_price(self):
        price = black_scholes_price(100, 100, 1, 0, 0, 0.2, "PE")
        self.assertAlmostEqual(price, 7.9656, places=3)

    def test_implied_volatility_round_trip(self):
        price = black_scholes_price(100, 105, 0.5, 0.06, 0.01, 0.3, "CE")
        iv = implied_volatility(price, 100, 105, 0.5, 0.06, 0.01, "CE")
        self.assertIsNotNone(iv)
        self.assertAlmostEqual(iv, 0.3, places=5)

    def test_call_and_put_delta(self):
        call = option_delta(100, 100, 1, 0, 0, 0.2, "CE")
        put = option_delta(100, 100, 1, 0, 0, 0.2, "PE")
        self.assertAlmostEqual(call, 0.5398, places=3)
        self.assertAlmostEqual(put, -0.4602, places=3)

    def test_invalid_price_is_rejected(self):
        iv = implied_volatility(150, 100, 100, 1, 0, 0, "CE")
        self.assertIsNone(iv)


if __name__ == "__main__":
    unittest.main()
