import logging
from datetime import datetime, timezone
from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.provider.blockchain import BlockchainProvider
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from tests.infra.blockchain_api import InMemoryBlockchainApi
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi
from tests.resources.blockchain.transactions import (
    COINBASE_WITHDRAWAL_TXID,
    COLD_STORAGE_ADDRESS_1,
    COLD_STORAGE_ADDRESS_2,
    CONSOLIDATION_TXID,
    EXTERNAL_RECEIVE_TXID,
    EXTERNAL_SEND_TXID,
    MERCHANT_ADDRESS,
    MIXED_INPUTS_TXID,
    UNCONFIRMED_TXID,
)


class BlockchainProviderFactory:
    @fixture(autouse=True)
    def initialize_provider(self):
        self.wallet = Wallet(
            name="Cold Storage",
            network=Network.BITCOIN,
            addresses=(COLD_STORAGE_ADDRESS_1, COLD_STORAGE_ADDRESS_2),
        )
        self.provider = BlockchainProvider(
            InMemoryBlockchainApi(), MarketPriceAdapter(InMemoryYahooFinanceApi())
        )

    def movement(self, transaction_id: str) -> OnChainMovement:
        movements = self.provider.get_movements(self.wallet)
        return next(x for x in movements if x.transaction_id == transaction_id)


class TestGetMovements(BlockchainProviderFactory):
    def should_return_confirmed_transactions_once_each_oldest_first(self):
        movements = self.provider.get_movements(self.wallet)

        assert [movement.transaction_id for movement in movements] == [
            COINBASE_WITHDRAWAL_TXID,
            EXTERNAL_RECEIVE_TXID,
            EXTERNAL_SEND_TXID,
            CONSOLIDATION_TXID,
            MIXED_INPUTS_TXID,
        ]

    def should_skip_unconfirmed_transactions(self):
        movements = self.provider.get_movements(self.wallet)

        assert UNCONFIRMED_TXID not in [x.transaction_id for x in movements]

    def should_describe_movements_in_wallet_terms(self):
        movement = self.movement(COINBASE_WITHDRAWAL_TXID)

        assert movement.account == "Cold Storage"
        assert movement.symbol == "BTC"
        assert movement.currency == "USD"
        assert movement.executed_at == datetime(2024, 3, 1, 12, tzinfo=timezone.utc)

    def should_price_movements_with_daily_close(self):
        assert self.movement(COINBASE_WITHDRAWAL_TXID).market_unit_price == Decimal(
            "61000"
        )
        assert self.movement(EXTERNAL_SEND_TXID).market_unit_price == Decimal("67000")


class TestReceive(BlockchainProviderFactory):
    def should_credit_only_outputs_to_the_wallet(self):
        movement = self.movement(COINBASE_WITHDRAWAL_TXID)

        assert movement.quantity == Decimal("0.00723422")

    def when_other_party_pays_the_fee_should_charge_no_fee(self):
        movement = self.movement(COINBASE_WITHDRAWAL_TXID)

        assert movement.fee == Decimal("0")
        assert movement.destination_address is None


class TestSend(BlockchainProviderFactory):
    def should_debit_what_left_the_wallet_excluding_change_and_fee(self):
        movement = self.movement(EXTERNAL_SEND_TXID)

        assert movement.quantity == Decimal("-0.005")
        assert movement.fee == Decimal("0.00003422")

    def should_keep_the_destination_address(self):
        movement = self.movement(EXTERNAL_SEND_TXID)

        assert movement.destination_address == MERCHANT_ADDRESS


class TestConsolidation(BlockchainProviderFactory):
    def when_coins_move_between_own_addresses_should_only_charge_the_fee(self):
        movement = self.movement(CONSOLIDATION_TXID)

        assert movement.quantity == Decimal("0")
        assert movement.fee == Decimal("0.00002")
        assert movement.destination_address is None


class TestMixedInputs(BlockchainProviderFactory):
    def should_charge_the_fee_share_of_the_wallet_inputs(self):
        movement = self.movement(MIXED_INPUTS_TXID)

        # 1218000 of the 2000000 input sats are the wallet's: 61% of 10000.
        assert movement.fee == Decimal("0.0000609")
        assert movement.quantity == Decimal("-0.0121191")

    def should_warn_about_unlisted_input_addresses(self, caplog):
        with caplog.at_level(logging.WARNING):
            self.provider.get_movements(self.wallet)

        assert MIXED_INPUTS_TXID in caplog.text
        assert "not listed" in caplog.text
