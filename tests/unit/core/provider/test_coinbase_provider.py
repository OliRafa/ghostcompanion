from datetime import datetime
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
        assert trade.quantity == Decimal("6.4136277")
        assert trade.value == Decimal("0.0")

    def should_treat_networks_fees_as_sells_with_zero_gain(self):
        trades = self.coinbase_provider.get_trades("BTC")

        network_fees = list(filter(lambda x: x.description == "Network Fee", trades))

        assert all(
            trade.transaction_type == TransactionType.SELL for trade in network_fees
        )
        assert all(trade.value == Decimal("0") for trade in network_fees)

        assert network_fees[0].quantity == Decimal("0.00001790")
