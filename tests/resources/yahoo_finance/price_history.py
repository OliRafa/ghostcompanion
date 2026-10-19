"""Synthetic daily closes, keyed by Yahoo ticker, sparse on purpose: lookups on days
in between exercise the "latest close before" fallback. Like Yahoo, crypto closes
are indexed in UTC."""

PRICE_HISTORIES: dict[str, tuple[str, dict[str, float]]] = {
    "BTC-USD": (
        "UTC",
        {
            "2020-01-01": 7200.0,
            "2020-06-01": 9500.0,
            "2024-01-01": 42000.0,
            "2024-03-01": 61000.0,
            "2024-06-01": 67000.0,
            "2026-04-01": 68000.0,
            "2026-07-01": 65000.0,
        },
    ),
    "ETH-USD": ("UTC", {"2024-01-01": 2300.0, "2026-04-01": 2050.0}),
    "USDC-USD": ("UTC", {"2024-01-01": 1.0, "2026-04-01": 0.9998}),
}
