from datetime import date, datetime, timezone
from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.provider.coinbase import CoinbaseProvider
from tests.infra.coinbase_api import InMemoryCoinbaseApi


class CoinbaseProviderFactory:
    @fixture(autouse=True)
    def instantiate_provider(self) -> None:
        self.coinbase_provider = CoinbaseProvider(InMemoryCoinbaseApi())


class TestGetCoins(CoinbaseProviderFactory):
    def should_not_return_fiat_coins(self):
        coins = self.coinbase_provider.get_coins()

        assert "EUR" not in coins

    def when_coin_has_0_balance_but_had_trades_should_return_it(self):
        zero_balance_coin = "ETH"

        coins = self.coinbase_provider.get_coins()

        assert any(coin == zero_balance_coin for coin in coins)

    def should_return_traded_coins_only(self):
        not_traded_coin = "SNX"

        coins = self.coinbase_provider.get_coins()

        assert not any(coin == not_traded_coin for coin in coins)

    def should_return_coins(self):
        coins = self.coinbase_provider.get_coins()

        assert coins == ["ETH", "BTC"]


class TestGetTrades(CoinbaseProviderFactory):
    def should_return_trades_as_buys_and_sells(self):
        trades = self.coinbase_provider.get_trades("BTC")

        assert len(trades) > 0

        assert all(
            trade.transaction_type == TransactionType.BUY
            or trade.transaction_type == TransactionType.SELL
            for trade in trades
        )

    def should_return_sells_as_positive_values(self):
        trades = self.coinbase_provider.get_trades("BTC")
        sells = list(
            filter(lambda x: x.transaction_type == TransactionType.SELL, trades)
        )

        assert all(trade.quantity > 0 for trade in sells)
        assert all(trade.unit_price >= 0 for trade in sells)

    def should_treat_coinbase_trades_as_sells_and_buys(self):
        trade_execution_time = datetime.now()
        trade_execution_time_str = (
            trade_execution_time.isoformat(timespec="seconds") + "Z"
        )
        trade = [
            {
                "amount": {"amount": "-932.0470000", "currency": "ETH"},
                "created_at": trade_execution_time_str,
                "native_amount": {"amount": "-226.08", "currency": "USD"},
                "resource": "transaction",
                "status": "completed",
                "trade": {"payment_method_name": "ETH Wallet"},
                "type": "trade",
            },
            {
                "amount": {"amount": "0.00686577", "currency": "BTC"},
                "created_at": trade_execution_time_str,
                "native_amount": {"amount": "223.90", "currency": "USD"},
                "resource": "transaction",
                "status": "completed",
                "trade": {"payment_method_name": "ETH Wallet"},
                "type": "trade",
            },
        ]
        coinbase_api = InMemoryCoinbaseApi()
        coinbase_api._transactions = trade
        coinbase_provider = CoinbaseProvider(coinbase_api)
        xlm_trades = coinbase_provider.get_trades("ETH")
        assert len(xlm_trades) == 1

        trade = coinbase_provider.get_trades("ETH")[0]
        assert trade.transaction_type == TransactionType.SELL
        assert trade.currency == "USD"
        assert trade.quantity == Decimal("932.0470000")
        assert trade.value == Decimal("226.08")

        trade = coinbase_provider.get_trades("BTC")[0]
        assert trade.transaction_type == TransactionType.BUY
        assert trade.currency == "USD"
        assert trade.quantity == Decimal("0.00686577")
        assert trade.value == Decimal("223.90")

    def should_treat_coinbase_earn_as_buys_with_zero_cost(self):
        trades = self.coinbase_provider.get_trades("ETH")

        trades = list(
            filter(lambda x: x.transaction_type == TransactionType.BUY, trades)
        )
        assert len(trades) == 1

        trade = trades[0]
        assert trade.quantity == Decimal("3.0905425")
        assert trade.value == Decimal("0.0")

    def should_leave_sends_to_movements(self):
        trades = self.coinbase_provider.get_trades("BTC")

        transactions = self.coinbase_provider.coinbase_api.get_transactions("BTC")
        assert len(trades) == sum(1 for x in transactions if x["type"] != "send")


def build_send(
    amount: str,
    native_amount: str,
    network: dict | None = None,
    **fields,
) -> dict:
    return {
        "amount": {"amount": amount, "currency": "BTC"},
        "created_at": "2026-08-21T19:14:38Z",
        "native_amount": {"amount": native_amount, "currency": "USD"},
        "network": network,
        "resource": "transaction",
        "status": "completed",
        "type": "send",
        **fields,
    }


class TestGetMovements(CoinbaseProviderFactory):
    def movements_for(self, *transactions: dict) -> list:
        self.coinbase_provider.coinbase_api._transactions = list(transactions)
        return self.coinbase_provider.get_movements("BTC")

    def when_sending_on_chain_should_debit_amount_net_of_fee(self):
        [movement] = self.movements_for(
            build_send(
                "-0.00724451",
                "-558.74",
                {
                    "hash": "AB" * 32,
                    "network_name": "bitcoin",
                    "status": "pending",
                    "transaction_fee": {"amount": "0.00001029", "currency": "BTC"},
                },
                to={"address": "bc1qdestination", "resource": "address"},
            )
        )

        assert movement.account == "Coinbase"
        assert movement.quantity == Decimal("-0.00723422")
        assert movement.fee == Decimal("0.00001029")
        assert movement.destination_address == "bc1qdestination"
        assert movement.transaction_id == "ab" * 32
        assert movement.market_unit_price == Decimal("558.74") / Decimal("0.00724451")
        assert movement.currency == "USD"
        assert movement.executed_at == datetime(
            2026, 8, 21, 19, 14, 38, tzinfo=timezone.utc
        )

    def when_receiving_on_chain_should_credit_amount(self):
        [movement] = self.movements_for(
            build_send(
                "0.01",
                "600.00",
                {"hash": "cd" * 32, "network_name": "bitcoin", "status": "confirmed"},
            )
        )

        assert movement.quantity == Decimal("0.01")
        assert movement.fee == Decimal("0")
        assert movement.destination_address is None
        assert movement.market_unit_price == Decimal("60000")

    def when_send_is_off_chain_should_have_no_transaction_id(self):
        [movement] = self.movements_for(
            build_send(
                "-0.01",
                "-600.00",
                {"status": "off_blockchain"},
                to={"email": "someone@example.com", "resource": "email"},
            )
        )

        assert movement.transaction_id is None
        assert movement.quantity == Decimal("-0.01")

    def when_fee_is_paid_in_another_coin_should_charge_it_separately(self):
        movements = self.movements_for(
            build_send(
                "-0.01",
                "-600.00",
                {
                    "hash": "ef" * 32,
                    "transaction_fee": {"amount": "0.001", "currency": "ETH"},
                },
                to={"address": "bc1qdestination", "resource": "address"},
            )
        )

        assert [(x.symbol, x.quantity, x.fee) for x in movements] == [
            ("BTC", Decimal("-0.01"), Decimal("0")),
            ("ETH", Decimal("0"), Decimal("0.001")),
        ]

    def should_ignore_coinbase_earn_rewards(self):
        movements = self.movements_for(
            build_send("0.01", "600.00", **{"from": {"name": "Coinbase Earn"}})
        )

        assert movements == []

    def should_ignore_sends_that_did_not_complete(self):
        movements = self.movements_for(
            build_send("-0.01", "-600.00", {"hash": "ab" * 32}, status="canceled")
        )

        assert movements == []

    def should_ignore_trades(self):
        movements = self.movements_for(
            {**build_send("-0.01", "-600.00"), "type": "sell"},
        )

        assert movements == []


class TestGetCurrentCashBalance(CoinbaseProviderFactory):
    def should_return_cash_balance_with_default_currency(self):
        result = self.coinbase_provider.get_current_cash_balance()

        assert result.currency == "USD"
        assert result.date == date.today()

    def should_use_provided_currency(self):
        result = self.coinbase_provider.get_current_cash_balance("EUR")

        assert result.currency == "EUR"

    def should_return_cash_balance_from_api(self):
        # Default cash balance is 1000.00 in InMemoryCoinbaseApi
        result = self.coinbase_provider.get_current_cash_balance()

        assert result.amount == Decimal("1000.00")

    def should_handle_zero_balance(self):
        self.coinbase_provider.coinbase_api.set_cash_balance(Decimal("0"))
        result = self.coinbase_provider.get_current_cash_balance()

        assert result.amount == Decimal("0")

    def should_handle_negative_balance(self):
        self.coinbase_provider.coinbase_api.set_cash_balance(Decimal("-500.00"))
        result = self.coinbase_provider.get_current_cash_balance()

        assert result.amount == Decimal("-500.00")
