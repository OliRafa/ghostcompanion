import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.account import GhostfolioAccount
from ghostcompanion.core.entity.lending import LendingBalance
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


def build_market_movement(
    quantity: str, executed_at: datetime, **fields
) -> OnChainMovement:
    return build_movement("DeFi Wallet", quantity, executed_at, market="Aave", **fields)


class LendingFactory:
    @fixture(autouse=True)
    def initialize_ledger(self):
        self.portfolios = {
            "DeFi Wallet": Portfolio(GhostfolioAccount(name="DeFi Wallet"))
        }
        self.ledger = CryptoLedger(self.portfolios, [])

    def booked(self, symbol: str) -> list[tuple]:
        portfolio = self.portfolios["DeFi Wallet"]
        if not portfolio.has_asset(symbol):
            return []
        return [
            (x.transaction_type, x.quantity, x.unit_price, x.description)
            for x in portfolio.get_trades(symbol)
        ]

    def fees(self, symbol: str) -> list[Decimal]:
        return [x.fee for x in self.portfolios["DeFi Wallet"].get_trades(symbol)]

    def balance(self, symbol: str, quantity: str) -> LendingBalance:
        return LendingBalance(
            account="DeFi Wallet",
            currency="USD",
            data_source="YAHOO",
            market="Aave",
            observed_at=at(19, 10, 2026),
            quantity=Decimal(quantity),
            symbol=symbol,
        )


class TestLendingMoves(LendingFactory):
    def when_supplying_should_keep_the_coin_in_the_account(self):
        self.ledger.book(
            [
                build_movement("DeFi Wallet", "-0.004", at(7, 4, 2026), symbol="CBBTC"),
                build_market_movement("0.004", at(7, 4, 2026), symbol="CBBTC"),
            ]
        )

        assert self.booked("CBBTC") == []

    def when_supplying_and_borrowing_at_once_should_not_be_a_swap(self):
        self.ledger.book(
            [
                build_movement("DeFi Wallet", "-0.004", at(7, 4, 2026), symbol="CBBTC"),
                build_market_movement("0.004", at(7, 4, 2026), symbol="CBBTC"),
                build_movement(
                    "DeFi Wallet",
                    "150",
                    at(7, 4, 2026),
                    symbol="USDC",
                    market_unit_price="1",
                    description="Borrowed from Aave",
                ),
                build_market_movement(
                    "-150",
                    at(7, 4, 2026),
                    symbol="DEBT-USDC",
                    market_unit_price="1",
                    description="Borrowed from Aave",
                    debt=True,
                ),
            ]
        )

        assert self.booked("CBBTC") == []
        assert self.booked("USDC") == [
            (TransactionType.BUY, Decimal("150"), Decimal("1"), "Borrowed from Aave")
        ]
        assert self.booked("DEBT-USDC") == [
            (TransactionType.SELL, Decimal("150"), Decimal("1"), "Borrowed from Aave")
        ]

    def when_swapping_collateral_should_swap_it_on_the_market(self):
        self.ledger.book(
            [
                build_market_movement(
                    "-850.42315", at(16, 9, 2026), symbol="USDC", market_unit_price="1"
                ),
                build_market_movement("0.01042117", at(16, 9, 2026), symbol="CBBTC"),
            ]
        )

        assert self.booked("USDC") == [
            (
                TransactionType.SELL,
                Decimal("850.42315"),
                Decimal("1"),
                "Swapped for CBBTC on Aave",
            )
        ]
        assert self.booked("CBBTC") == [
            (
                TransactionType.BUY,
                Decimal("0.01042117"),
                Decimal("850.42315") / Decimal("0.01042117"),
                "Swapped from USDC on Aave",
            )
        ]

    def when_market_sells_collateral_to_repay_should_swap_only_what_it_kept(self):
        self.ledger.book(
            [
                build_market_movement(
                    "-0.01093725",
                    at(5, 10, 2026),
                    symbol="CBBTC",
                    market_unit_price="86400",
                ),
                build_market_movement(
                    "935.6",
                    at(5, 10, 2026),
                    symbol="DEBT-USDC",
                    market_unit_price="1",
                    description="Repaid to Aave",
                    debt=True,
                ),
                build_movement(
                    "DeFi Wallet",
                    "0.00009318",
                    at(5, 10, 2026),
                    symbol="CBBTC",
                    market_unit_price="86400",
                ),
            ]
        )

        assert self.booked("CBBTC") == [
            (
                TransactionType.SELL,
                Decimal("0.01084407"),
                Decimal("86400"),
                "Swapped for DEBT-USDC on Aave",
            )
        ]
        # 0.01084407 CBBTC at 86400 repaid 935.6 of the debt.
        assert self.booked("DEBT-USDC") == [
            (
                TransactionType.BUY,
                Decimal("935.6"),
                Decimal("0"),
                "Swapped from CBBTC on Aave",
            )
        ]
        assert self.fees("DEBT-USDC") == [Decimal("936.927648")]

    def when_market_swaps_debts_should_keep_what_the_wallet_got_apart(self):
        self.ledger.book(
            [
                build_market_movement(
                    "-36.218774",
                    at(12, 5, 2026),
                    symbol="DEBT-USDC",
                    market_unit_price="1",
                    description="Borrowed from Aave",
                    debt=True,
                ),
                build_market_movement(
                    "0.00045",
                    at(12, 5, 2026),
                    symbol="DEBT-CBBTC",
                    market_unit_price="80500",
                    description="Repaid to Aave",
                    debt=True,
                ),
                build_movement(
                    "DeFi Wallet",
                    "0.118352",
                    at(12, 5, 2026),
                    symbol="USDC",
                    market_unit_price="1",
                ),
            ]
        )

        assert [x[3] for x in self.booked("DEBT-USDC")] == [
            "Swapped for DEBT-CBBTC on Aave"
        ]
        assert [x[3] for x in self.booked("DEBT-CBBTC")] == [
            "Swapped from DEBT-USDC on Aave"
        ]
        assert self.booked("USDC") == [
            (TransactionType.BUY, Decimal("0.118352"), Decimal("1"), "Received")
        ]


class TestRepayments(LendingFactory):
    def when_borrowing_should_sell_the_debt_at_its_price(self):
        self.ledger.book(
            [
                build_movement(
                    "DeFi Wallet",
                    "150",
                    at(7, 4, 2026),
                    symbol="USDC",
                    market_unit_price="0.9998",
                    description="Borrowed from Aave",
                ),
                build_market_movement(
                    "-150",
                    at(7, 4, 2026),
                    symbol="DEBT-USDC",
                    market_unit_price="0.9998",
                    description="Borrowed from Aave",
                    debt=True,
                ),
            ]
        )

        assert self.booked("DEBT-USDC") == [
            (
                TransactionType.SELL,
                Decimal("150"),
                Decimal("0.9998"),
                "Borrowed from Aave",
            )
        ]
        assert self.fees("DEBT-USDC") == [Decimal("0")]

    def when_repaying_should_buy_the_debt_back_for_nothing_with_its_worth_as_fee(
        self,
    ):
        self.ledger.book(
            [
                build_movement(
                    "DeFi Wallet",
                    "-50",
                    at(8, 4, 2026),
                    symbol="USDC",
                    market_unit_price="1.0002",
                    description="Repaid to Aave",
                ),
                build_market_movement(
                    "50",
                    at(8, 4, 2026),
                    symbol="DEBT-USDC",
                    market_unit_price="1.0002",
                    description="Repaid to Aave",
                    debt=True,
                ),
            ]
        )

        assert self.booked("USDC") == [
            (TransactionType.SELL, Decimal("50"), Decimal("1.0002"), "Repaid to Aave")
        ]
        assert self.booked("DEBT-USDC") == [
            (TransactionType.BUY, Decimal("50"), Decimal("0"), "Repaid to Aave")
        ]
        assert self.fees("DEBT-USDC") == [Decimal("50.01")]

    def when_swapping_debts_should_buy_the_repaid_one_back_for_nothing(self):
        self.ledger.book(
            [
                build_market_movement(
                    "-36.218774",
                    at(12, 5, 2026),
                    symbol="DEBT-USDC",
                    market_unit_price="1",
                    debt=True,
                ),
                build_market_movement(
                    "0.00045",
                    at(12, 5, 2026),
                    symbol="DEBT-CBBTC",
                    market_unit_price="80500",
                    debt=True,
                ),
            ]
        )

        assert self.booked("DEBT-USDC") == [
            (
                TransactionType.SELL,
                Decimal("36.218774"),
                Decimal("1"),
                "Swapped for DEBT-CBBTC on Aave",
            )
        ]
        assert self.booked("DEBT-CBBTC") == [
            (
                TransactionType.BUY,
                Decimal("0.00045"),
                Decimal("0"),
                "Swapped from DEBT-USDC on Aave",
            )
        ]
        assert self.fees("DEBT-CBBTC") == [Decimal("36.218774")]

    def when_buying_a_coin_the_market_holds_should_charge_no_fee(self):
        self.ledger.book(
            [
                build_market_movement(
                    "-850.42315", at(16, 9, 2026), symbol="USDC", market_unit_price="1"
                ),
                build_market_movement("0.01042117", at(16, 9, 2026), symbol="CBBTC"),
            ]
        )

        assert self.fees("CBBTC") == [Decimal("0")]


class ReconcileFactory(LendingFactory):
    def supply(self, quantity: str):
        self.ledger.book(
            [
                build_movement(
                    "DeFi Wallet", f"-{quantity}", at(7, 4, 2026), symbol="CBBTC"
                ),
                build_market_movement(quantity, at(7, 4, 2026), symbol="CBBTC"),
            ]
        )

    def borrow(self, quantity: str):
        self.ledger.book(
            [
                build_market_movement(
                    f"-{quantity}",
                    at(7, 4, 2026),
                    transaction_id="cd" * 32,
                    symbol="DEBT-USDC",
                    market_unit_price="1",
                    description="Borrowed from Aave",
                    debt=True,
                )
            ]
        )

    def interest(self, symbol: str) -> list[tuple]:
        return [x for x in self.booked(symbol) if x[3].startswith("Interest")]

    def corrections(self, symbol: str) -> list[tuple]:
        return [x for x in self.booked(symbol) if x[3] == "Balance correction on Aave"]


class TestInterest(ReconcileFactory):
    def should_book_interest_when_the_market_added_it(self):
        self.ledger.book(
            [
                build_market_movement(
                    "0.613407",
                    at(16, 9, 2026),
                    symbol="USDC",
                    market_unit_price="1",
                    interest=True,
                ),
                build_market_movement(
                    "-5.214877",
                    at(13, 10, 2026),
                    transaction_id="cd" * 32,
                    symbol="DEBT-USDC",
                    market_unit_price="1",
                    interest=True,
                ),
            ]
        )

        assert self.interest("USDC") == [
            (
                TransactionType.BUY,
                Decimal("0.613407"),
                Decimal("0"),
                "Interest earned on Aave",
            )
        ]
        assert self.interest("DEBT-USDC") == [
            (
                TransactionType.SELL,
                Decimal("5.214877"),
                Decimal("0"),
                "Interest due to Aave",
            )
        ]

    def should_date_interest_a_second_before_the_move_it_came_with(self):
        self.ledger.book(
            [
                build_market_movement(
                    "-0.127418",
                    at(18, 6, 2026),
                    symbol="DEBT-USDC",
                    market_unit_price="1",
                    interest=True,
                    debt=True,
                ),
                build_market_movement(
                    "36.346192",
                    at(18, 6, 2026),
                    symbol="DEBT-USDC",
                    market_unit_price="1",
                    description="Repaid to Aave",
                    debt=True,
                ),
            ]
        )

        times = {
            x.description: x.executed_at
            for x in self.portfolios["DeFi Wallet"].get_trades("DEBT-USDC")
        }
        assert times == {
            "Interest due to Aave": at(18, 6, 2026) - timedelta(seconds=1),
            "Repaid to Aave": at(18, 6, 2026),
        }

    def should_keep_interest_apart_from_the_swap_it_came_with(self):
        self.ledger.book(
            [
                build_market_movement(
                    "-850.42315", at(16, 9, 2026), symbol="USDC", market_unit_price="1"
                ),
                build_market_movement(
                    "0.613407",
                    at(16, 9, 2026),
                    symbol="USDC",
                    market_unit_price="1",
                    interest=True,
                ),
                build_market_movement("0.01042117", at(16, 9, 2026), symbol="CBBTC"),
            ]
        )

        assert [x[3] for x in self.booked("USDC")] == [
            "Interest earned on Aave",
            "Swapped for CBBTC on Aave",
        ]

    def should_buy_interest_earned_for_nothing(self):
        self.supply("0.004")

        self.ledger.reconcile([self.balance("CBBTC", "0.0041")])

        assert self.interest("CBBTC") == [
            (
                TransactionType.BUY,
                Decimal("0.0001"),
                Decimal("0"),
                "Interest earned on Aave",
            )
        ]

    def should_sell_interest_due_for_nothing_so_the_debt_grows(self):
        self.borrow("150")

        self.ledger.reconcile([self.balance("DEBT-USDC", "-150.25")])

        assert self.interest("DEBT-USDC") == [
            (
                TransactionType.SELL,
                Decimal("0.25"),
                Decimal("0"),
                "Interest due to Aave",
            )
        ]

    def when_nothing_accrued_should_book_nothing(self):
        self.supply("0.004")

        self.ledger.reconcile(
            [self.balance("CBBTC", "0.004"), self.balance("DEBT-CBBTC", "0")]
        )

        assert self.booked("CBBTC") == []
        assert not self.portfolios["DeFi Wallet"].has_asset("DEBT-CBBTC")

    def when_withdrawn_with_interest_should_catch_up_nothing(self):
        self.supply("0.004")
        self.ledger.book(
            [
                build_market_movement(
                    "0.0002",
                    at(9, 4, 2026),
                    transaction_id="ef" * 32,
                    symbol="CBBTC",
                    interest=True,
                ),
                build_market_movement(
                    "-0.0042", at(9, 4, 2026), transaction_id="ef" * 32, symbol="CBBTC"
                ),
                build_movement(
                    "DeFi Wallet",
                    "0.0042",
                    at(9, 4, 2026),
                    transaction_id="ef" * 32,
                    symbol="CBBTC",
                ),
            ]
        )

        self.ledger.reconcile([self.balance("CBBTC", "0")])

        [(_, quantity, _, _)] = self.interest("CBBTC")
        assert quantity == Decimal("0.0002")
        assert self.corrections("CBBTC") == []

    def should_add_up_the_balances_of_every_network(self):
        self.supply("0.004")

        self.ledger.reconcile(
            [self.balance("CBBTC", "0.003"), self.balance("CBBTC", "0.0015")]
        )

        [(_, quantity, _, _)] = self.interest("CBBTC")
        assert quantity == Decimal("0.0005")

    def should_compare_the_market_only_with_its_own_share_of_the_coin(self):
        self.ledger.book(
            [build_movement("DeFi Wallet", "0.002", at(1, 4, 2026), symbol="CBBTC")]
        )
        self.supply("0.004")

        self.ledger.reconcile([self.balance("CBBTC", "0.0041")])

        [(_, quantity, _, description)] = self.interest("CBBTC")
        assert (quantity, description) == (Decimal("0.0001"), "Interest earned on Aave")

    def should_time_interest_from_the_markets_last_move_not_the_wallets(self):
        self.supply("0.004")
        self.ledger.book(
            [
                build_movement(
                    "DeFi Wallet",
                    "0.001",
                    at(18, 10, 2026),
                    transaction_id="ef" * 32,
                    symbol="CBBTC",
                )
            ]
        )

        self.ledger.reconcile([self.balance("CBBTC", "0.0041")])

        assert self.corrections("CBBTC") == []
        assert len(self.interest("CBBTC")) == 1


class TestBalanceCorrection(ReconcileFactory):
    def when_coin_supplied_shrank_should_correct_the_balance(self, caplog):
        self.supply("0.004")

        with caplog.at_level(logging.WARNING):
            self.ledger.reconcile([self.balance("CBBTC", "0.003")])

        assert self.corrections("CBBTC") == [
            (
                TransactionType.SELL,
                Decimal("0.001"),
                Decimal("0"),
                "Balance correction on Aave",
            )
        ]
        assert self.interest("CBBTC") == []
        assert "`DeFi Wallet` holds 0.003 CBBTC in Aave" in caplog.text
        assert "may have gone unread" in caplog.text

    def when_debt_shrank_should_correct_the_balance(self):
        self.borrow("150")

        self.ledger.reconcile([self.balance("DEBT-USDC", "-100")])

        assert self.corrections("DEBT-USDC") == [
            (
                TransactionType.BUY,
                Decimal("50"),
                Decimal("0"),
                "Balance correction on Aave",
            )
        ]

    def when_more_than_interest_could_explain_should_correct_the_balance(self):
        # 0.002 on 0.004 in six months is far more than any market pays.
        self.supply("0.004")

        self.ledger.reconcile([self.balance("CBBTC", "0.006")])

        assert self.corrections("CBBTC") == [
            (
                TransactionType.BUY,
                Decimal("0.002"),
                Decimal("0"),
                "Balance correction on Aave",
            )
        ]

    def when_position_was_never_moved_should_correct_the_balance(self):
        self.ledger.reconcile([self.balance("CBBTC", "0.5")])

        assert self.corrections("CBBTC") == [
            (
                TransactionType.BUY,
                Decimal("0.5"),
                Decimal("0"),
                "Balance correction on Aave",
            )
        ]

    def when_rounding_leaves_dust_should_correct_it_without_warning(self, caplog):
        self.supply("0.004")

        with caplog.at_level(logging.WARNING):
            self.ledger.reconcile([self.balance("CBBTC", "0.00399999")])

        assert self.corrections("CBBTC") == [
            (
                TransactionType.SELL,
                Decimal("0.00000001"),
                Decimal("0"),
                "Balance correction on Aave",
            )
        ]
        assert caplog.text == ""
