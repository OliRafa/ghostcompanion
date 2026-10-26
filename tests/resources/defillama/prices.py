"""Synthetic DefiLlama price points, keyed by DefiLlama coin, seconds away from
some of the fixture transactions' moments, as DefiLlama's points are. Moments
without a point nearby (the Bitcoin send of 2024-06-02, say) exercise the fallback
to Yahoo's daily close."""

PRICE_POINTS: dict[str, dict[str, float]] = {
    "coingecko:bitcoin": {
        "2021-07-14T09:12:48+00:00": 32740.15,
        "2024-03-01T12:00:05+00:00": 61534.12,
    },
    "ethereum:0x0000000000000000000000000000000000000000": {
        "2024-01-05T18:44:41+00:00": 2247.18,
    },
    "base:0x0000000000000000000000000000000000000000": {
        "2026-04-02T18:19:47+00:00": 2064.3,
    },
    "base:0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": {
        "2026-04-02T18:23:08+00:00": 0.9997,
    },
    "base:0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": {
        "2026-04-02T19:00:09+00:00": 68120.4,
        "2026-09-17T08:41:23+00:00": 76318.55,
    },
}
