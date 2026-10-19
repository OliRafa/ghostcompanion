import logging
from datetime import datetime, timezone
from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.account import GhostfolioAccount
from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.usecase.crypto_ledger import CryptoLedger

COLD_STORAGE_ADDRESS = "bc1qcoldstorage00000000000000000000000000001"
HARDWARE_ADDRESS = "bc1qhardware0000000000000000000000000000000001"
MERCHANT_ADDRESS = "bc1qmerchant0000000000000000000000000000000000"
TRANSACTION_ID = "ab" * 32


def at(day: int, month: int = 3, year: int = 2024) -> datetime:
    return datetime(year, month, day, 12, tzinfo=timezone.utc)


def build_trade(
    transaction_type: TransactionType,
    quantity: str,
    unit_price: str,
    executed_at: datetime,
    currency: str = "USD",
) -> Trade:
    return Trade(
        currency=currency,
        executed_at=executed_at,
        fee=Decimal("0"),
        quantity=Decimal(quantity),
        symbol="BTC",
        transaction_type=transaction_type,
        unit_price=Decimal(unit_price),
    )


def build_movement(
    account: str,
    quantity: str,
    executed_at: datetime,
    transaction_id: str | None = TRANSACTION_ID,
    **fields,
) -> OnChainMovement:
    price = fields.pop("market_unit_price", "61000")
    return OnChainMovement(
        account=account,
        currency=fields.pop("currency", "USD"),
        executed_at=executed_at,
        market_unit_price=price and Decimal(price),
        quantity=Decimal(quantity),
        symbol=fields.pop("symbol", "BTC"),
        transaction_id=transaction_id,
        **fields,
    )


class CryptoLedgerFactory:
    @fixture(autouse=True)
    def initialize_ledger(self):
        self.portfolios = {
            name: Portfolio(GhostfolioAccount(name=name))
            for name in ("Coinbase", "Cold Storage", "Hardware")
        }
        self.portfolios["Coinbase"].add_asset(
            "BTC",
            [
                build_trade(TransactionType.BUY, "0.01", "40000", at(10, 1)),
                build_trade(TransactionType.BUY, "0.01", "60000", at(10, 2)),
            ],
        )
        wallets = [
            Wallet(
                name="Cold Storage",
                network=Network.BITCOIN,
                addresses=(COLD_STORAGE_ADDRESS,),
            ),
            Wallet(
                name="Hardware", network=Network.BITCOIN, addresses=(HARDWARE_ADDRESS,)
            ),
        ]
        self.ledger = CryptoLedger(self.portfolios, wallets)

    def trades(self, account: str, description: str | None = None) -> list[Trade]:
        portfolio = self.portfolios[account]
        if not portfolio.has_asset("BTC"):
            return []

        return [
            trade
            for trade in portfolio.get_trades("BTC")
            if description is None or trade.description == description
        ]

    def summary(self, account: str, description: str) -> list[tuple]:
        return [
            (trade.transaction_type, trade.quantity, trade.unit_price, trade.currency)
            for trade in self.trades(account, description)
        ]


class TestTransfer(CryptoLedgerFactory):
    def transfer(self, quantity: str, day: int = 1, **fields):
        self.ledger.book(
            [
                build_movement("Coinbase", f"-{quantity}", at(day), **fields),
                build_movement("Cold Storage", quantity, at(day + 1)),
            ]
        )

    def should_sell_and_buy_at_the_market_price_when_sent(self):
        self.transfer(
            "0.004", destination_address=COLD_STORAGE_ADDRESS, market_unit_price="62000"
        )

        assert self.summary("Coinbase", "Transfer to Cold Storage") == [
            (TransactionType.SELL, Decimal("0.004"), Decimal("62000"), "USD")
        ]
        assert self.summary("Cold Storage", "Transfer from Coinbase") == [
            (TransactionType.BUY, Decimal("0.004"), Decimal("62000"), "USD")
        ]

    def should_not_depend_on_what_was_paid_for_the_coins(self):
        self.portfolios["Coinbase"].add_trades(
            "BTC", [build_trade(TransactionType.BUY, "0.01", "10000", at(20, 2))]
        )

        self.transfer("0.004")

        assert self.trades("Cold Storage")[0].unit_price == Decimal("61000")

    def should_price_in_the_currency_of_the_sender(self):
        self.transfer("0.004", currency="EUR", market_unit_price="56000")

        assert self.summary("Cold Storage", "Transfer from Coinbase") == [
            (TransactionType.BUY, Decimal("0.004"), Decimal("56000"), "EUR")
        ]

    def should_date_both_sides_when_the_coins_were_sent(self):
        self.transfer("0.004")

        assert self.trades("Coinbase", "Transfer to Cold Storage")[0].executed_at == at(
            1
        )
        assert self.trades("Cold Storage")[0].executed_at == at(1)

    def should_sell_the_network_fee_for_nothing(self):
        self.transfer("0.004", fee=Decimal("0.0001"))

        assert self.summary("Coinbase", "Network Fee") == [
            (TransactionType.SELL, Decimal("0.0001"), Decimal("0"), "USD")
        ]

    def when_coins_move_on_should_use_the_market_price_of_each_move(self):
        self.ledger.book(
            [
                build_movement("Coinbase", "-0.004", at(1)),
                build_movement("Cold Storage", "0.004", at(2)),
                build_movement(
                    "Cold Storage",
                    "-0.003",
                    at(5),
                    "cd" * 32,
                    market_unit_price="64000",
                ),
                build_movement("Hardware", "0.003", at(5), "cd" * 32),
            ]
        )

        assert self.summary("Hardware", "Transfer from Cold Storage") == [
            (TransactionType.BUY, Decimal("0.003"), Decimal("64000"), "USD")
        ]

    def when_only_part_goes_to_own_accounts_should_sell_the_rest_at_market(self):
        self.ledger.book(
            [
                build_movement(
                    "Coinbase",
                    "-0.004",
                    at(1),
                    destination_address=None,
                    market_unit_price="62000",
                ),
                build_movement("Cold Storage", "0.001", at(2)),
            ]
        )

        assert self.summary("Coinbase", "Transfer to Cold Storage") == [
            (TransactionType.SELL, Decimal("0.001"), Decimal("62000"), "USD")
        ]
        assert self.summary("Coinbase", "Sent") == [
            (TransactionType.SELL, Decimal("0.003"), Decimal("62000"), "USD")
        ]

    def when_wallet_sends_to_coinbase_should_use_the_wallet_market_price(self):
        self.ledger.book(
            [
                build_movement(
                    "Cold Storage", "-0.002", at(5), market_unit_price="63000"
                ),
                build_movement("Coinbase", "0.002", at(6), market_unit_price="64000"),
            ]
        )

        assert self.summary("Coinbase", "Transfer from Cold Storage") == [
            (TransactionType.BUY, Decimal("0.002"), Decimal("63000"), "USD")
        ]


class TestMarketMovements(CryptoLedgerFactory):
    def when_coins_come_from_others_should_buy_them_at_market(self):
        self.ledger.book([build_movement("Cold Storage", "0.01", at(5))])

        assert self.summary("Cold Storage", "Received") == [
            (TransactionType.BUY, Decimal("0.01"), Decimal("61000"), "USD")
        ]

    def when_coins_go_to_others_should_sell_them_at_market(self):
        self.ledger.book(
            [
                build_movement(
                    "Coinbase",
                    "-0.004",
                    at(1),
                    destination_address=MERCHANT_ADDRESS,
                    market_unit_price="62000.123456789",
                )
            ]
        )

        assert self.summary("Coinbase", f"Sent to {MERCHANT_ADDRESS}") == [
            (TransactionType.SELL, Decimal("0.004"), Decimal("62000.123456789"), "USD")
        ]

    def when_movements_have_no_transaction_should_not_pair_them(self):
        self.ledger.book(
            [
                build_movement("Coinbase", "-0.004", at(1), transaction_id=None),
                build_movement("Cold Storage", "0.004", at(1), transaction_id=None),
            ]
        )

        assert self.summary("Coinbase", "Sent") == [
            (TransactionType.SELL, Decimal("0.004"), Decimal("61000"), "USD")
        ]
        assert self.summary("Cold Storage", "Received") == [
            (TransactionType.BUY, Decimal("0.004"), Decimal("61000"), "USD")
        ]

    def when_only_fee_was_paid_should_book_only_the_fee(self):
        self.ledger.book(
            [build_movement("Cold Storage", "0", at(1), fee=Decimal("0.00002"))]
        )

        assert self.summary("Cold Storage", None) == [
            (TransactionType.SELL, Decimal("0.00002"), Decimal("0"), "USD")
        ]


class TestUnconfirmedTransfer(CryptoLedgerFactory):
    def when_wallet_side_is_missing_should_wait_for_confirmation(self, caplog):
        with caplog.at_level(logging.WARNING):
            self.ledger.book(
                [
                    build_movement(
                        "Coinbase",
                        "-0.004",
                        at(1),
                        destination_address=COLD_STORAGE_ADDRESS.upper(),
                        fee=Decimal("0.0001"),
                    )
                ]
            )

        assert [trade.description for trade in self.trades("Coinbase")] == [
            None,
            None,
            "Network Fee",
        ]
        assert self.trades("Cold Storage") == []
        assert "isn't confirmed yet" in caplog.text

    def when_wallet_does_not_track_the_coin_should_book_a_sale(self):
        self.ledger.tracked_symbols = {"Cold Storage": {"USDC"}}

        self.ledger.book(
            [
                build_movement(
                    "Coinbase",
                    "-0.004",
                    at(1),
                    destination_address=COLD_STORAGE_ADDRESS,
                )
            ]
        )

        assert self.summary("Coinbase", f"Sent to {COLD_STORAGE_ADDRESS}") == [
            (TransactionType.SELL, Decimal("0.004"), Decimal("61000"), "USD")
        ]


class TestSwaps(CryptoLedgerFactory):
    def swap(self, given: dict, got: dict):
        self.ledger.book(
            [
                build_movement("Cold Storage", executed_at=at(2), **given),
                build_movement("Cold Storage", executed_at=at(2), **got),
            ]
        )

    def booked(self, symbol: str) -> list[tuple]:
        portfolio = self.portfolios["Cold Storage"]
        return [
            (x.transaction_type, x.quantity, x.unit_price, x.data_source, x.description)
            for x in portfolio.get_trades(symbol)
        ]

    def should_buy_at_the_price_the_swap_got(self):
        self.swap(
            {"quantity": "-340", "symbol": "USDC", "market_unit_price": "0.9998"},
            {"quantity": "0.005", "symbol": "CBBTC", "data_source": "GHOSTFOLIO"},
        )

        assert self.booked("USDC") == [
            (
                TransactionType.SELL,
                Decimal("340"),
                Decimal("0.9998"),
                "YAHOO",
                "Swapped for CBBTC",
            )
        ]
        # 340 USDC at 0.9998 for 0.005 CBBTC.
        assert self.booked("CBBTC") == [
            (
                TransactionType.BUY,
                Decimal("0.005"),
                Decimal("67986.4"),
                "GHOSTFOLIO",
                "Swapped from USDC",
            )
        ]

    def when_coin_got_has_no_price_should_value_it_from_the_coin_given(self):
        self.swap(
            {"quantity": "-500", "symbol": "USDC", "market_unit_price": "1"},
            {"quantity": "480", "symbol": "ABTC", "market_unit_price": None},
        )

        [(_, quantity, unit_price, _, _)] = self.booked("ABTC")
        assert (quantity, unit_price) == (
            Decimal("480"),
            Decimal("500") / Decimal("480"),
        )

    def when_coin_given_has_no_price_should_value_it_from_the_coin_got(self):
        self.swap(
            {"quantity": "-480", "symbol": "ABTC", "market_unit_price": None},
            {"quantity": "600", "symbol": "USDC", "market_unit_price": "1"},
        )

        [(transaction_type, quantity, unit_price, _, _)] = self.booked("ABTC")
        assert transaction_type == TransactionType.SELL
        assert unit_price * quantity == Decimal("600")

    def when_neither_coin_has_a_price_should_book_nothing(self, caplog):
        with caplog.at_level(logging.WARNING):
            self.swap(
                {"quantity": "-480", "symbol": "ABTC", "market_unit_price": None},
                {"quantity": "1", "symbol": "XYZ", "market_unit_price": None},
            )

        assert self.portfolios["Cold Storage"].get_symbols() == []
        assert "neither" in caplog.text

    def should_still_sell_the_fee_of_a_swap(self):
        self.ledger.book(
            [
                build_movement(
                    "Cold Storage",
                    "0",
                    at(2),
                    symbol="ETH",
                    fee=Decimal("0.0003"),
                ),
                build_movement(
                    "Cold Storage", "-340", at(2), symbol="USDC", market_unit_price="1"
                ),
                build_movement("Cold Storage", "0.005", at(2), symbol="CBBTC"),
            ]
        )

        assert [
            x.description for x in self.portfolios["Cold Storage"].get_trades("ETH")
        ] == ["Network Fee"]
        assert len(self.booked("CBBTC")) == 1


class TestUnpricedCoins(CryptoLedgerFactory):
    def when_coin_has_no_price_outside_a_swap_should_skip_it(self, caplog):
        with caplog.at_level(logging.WARNING):
            self.ledger.book(
                [
                    build_movement(
                        "Cold Storage",
                        "10",
                        at(2),
                        symbol="ABTC",
                        market_unit_price=None,
                    )
                ]
            )

        assert not self.portfolios["Cold Storage"].has_asset("ABTC")
        assert "has no price" in caplog.text


class TestPerCoinPairing(CryptoLedgerFactory):
    def should_pair_a_transfer_only_with_the_same_coin(self):
        self.ledger.book(
            [
                build_movement(
                    "Coinbase", "-100", at(1), symbol="USDC", market_unit_price="1"
                ),
                build_movement(
                    "Cold Storage", "100", at(1), symbol="USDC", market_unit_price="1"
                ),
                build_movement(
                    "Cold Storage", "0", at(1), symbol="ETH", fee=Decimal("0.0001")
                ),
            ]
        )

        assert [
            x.description for x in self.portfolios["Cold Storage"].get_trades("USDC")
        ] == ["Transfer from Coinbase"]
