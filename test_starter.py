"""Тесты recommend_price.

Запуск из каталога с этими файлами:

    python -m unittest test_starter.py
"""

import asyncio
import unittest
from decimal import Decimal

from starter import recommend_price, sample_fetch_offers


def _offer(seller, price, delivery_days):
    return {
        "seller": seller,
        "price": Decimal(price),
        "delivery_days": delivery_days,
    }


def _fetch(status, offers):
    async def fetch_offers():
        return {"status": status, "offers": offers}

    return fetch_offers


class RecommendPriceTest(unittest.IsolatedAsyncioTestCase):
    async def test_sample_calculation_applies_discounted_competitor(self):
        result = await recommend_price(
            sample_fetch_offers,
            current_price=Decimal("4900.00"),
            min_price=Decimal("4500.00"),
        )

        self.assertEqual(
            result,
            {
                "price": Decimal("4728.00"),
                "decision": "APPLY",
                "reason": "Цена в допустимых пределах",
            },
        )

    async def test_timeout_and_source_failure_hold_current_price(self):
        async def slow():
            await asyncio.sleep(1)
            return {"status": "success", "offers": [_offer("PARTS", "100.00", 1)]}

        async def broken():
            raise ConnectionError("площадка недоступна")

        current = Decimal("4900.00")
        cases = [
            (
                slow,
                0.05,
                "Источник не ответил вовремя",
            ),
            (
                broken,
                2.0,
                "Не удалось получить предложения",
            ),
            (
                _fetch("error", [_offer("PARTS", "100.00", 1)]),
                2.0,
                "Статус источника не success",
            ),
            (
                _fetch("partial", [_offer("PARTS", "100.00", 1)]),
                2.0,
                "Статус источника не success",
            ),
        ]
        for fetch_offers, timeout_s, reason in cases:
            with self.subTest(reason=reason):
                result = await recommend_price(
                    fetch_offers,
                    current,
                    Decimal("4500.00"),
                    timeout_s=timeout_s,
                )
                self.assertEqual(
                    result,
                    {"price": current, "decision": "HOLD", "reason": reason},
                )

    async def test_no_suitable_offers_hold_even_below_min_price(self):
        fetch_offers = _fetch(
            "success",
            [
                _offer("myshop", "100.00", 1),
                _offer("MyShop", "200.00", 2),
                _offer("SLOW", "100.00", 7),
                _offer("UNKNOWN", "100.00", None),
            ],
        )
        current = Decimal("4000.00")

        result = await recommend_price(
            fetch_offers,
            current,
            Decimal("4500.00"),
        )

        self.assertEqual(
            result,
            {
                "price": current,
                "decision": "HOLD",
                "reason": "Нет подходящих предложений",
            },
        )

    async def test_rounds_down_to_kopeck_and_not_under_min_price(self):
        rounded = await recommend_price(
            _fetch("success", [_offer("PARTS", "100.10", 6)]),
            Decimal("100.10"),
            Decimal("50.00"),
        )
        self.assertEqual(rounded["price"], Decimal("98.59"))
        self.assertEqual(rounded["decision"], "APPLY")

        clamped = await recommend_price(
            _fetch("success", [_offer("PARTS", "100.00", 0)]),
            Decimal("4700.00"),
            Decimal("4500.00"),
        )
        self.assertEqual(
            clamped,
            {
                "price": Decimal("4500.00"),
                "decision": "APPLY",
                "reason": "Цена в допустимых пределах",
            },
        )

    async def test_thirty_percent_boundary_both_directions(self):
        cases = [
            ("710.66", Decimal("700.00"), "APPLY"),
            ("710.65", Decimal("699.99"), "REVIEW"),
            ("1319.80", Decimal("1300.00"), "APPLY"),
            ("1319.81", Decimal("1300.01"), "REVIEW"),
        ]
        for competitor, expected_price, decision in cases:
            with self.subTest(competitor=competitor):
                result = await recommend_price(
                    _fetch("success", [_offer("PARTS", competitor, 1)]),
                    Decimal("1000.00"),
                    Decimal("100.00"),
                )
                self.assertEqual(result["price"], expected_price)
                self.assertEqual(result["decision"], decision)


if __name__ == "__main__":
    unittest.main()
