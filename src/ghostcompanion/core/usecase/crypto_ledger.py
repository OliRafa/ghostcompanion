import logging
from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from typing import final

from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.entity.wallet import Wallet

logger = logging.getLogger(__name__)

_NETWORK_FEE_DESCRIPTION = "Network Fee"


@final
class CryptoLedger:
    """Books on-chain movements into the portfolios of the user's accounts.

    Everything trades at the market price of the moment, as Coinbase itself
    accounts for moves in and out of an account: coins leaving one of the user's
    accounts are sold, coins arriving are bought. Movements of one transaction
    between two of the user's accounts are a transfer, sold by the source and
    bought by the destination at the same price. An account giving one coin for
    another in a single transaction swapped them, at the price it got. Network
    fees are sold for nothing.
    """

    def __init__(
        self,
        portfolios: dict[str, Portfolio],
        wallets: list[Wallet],
        tracked_symbols: dict[str, set[str]] | None = None,
    ):
        self.portfolios = portfolios
        self.wallets = wallets
        # What each wallet's own chain data can show; a coin sent to a wallet
        # that doesn't track it will never show up there. None tracks everything.
        self.tracked_symbols = tracked_symbols

    def book(self, movements: list[OnChainMovement]) -> None:
        for transaction in self._group_by_transaction(movements):
            self._book_transaction(transaction)

    @staticmethod
    def _group_by_transaction(
        movements: list[OnChainMovement],
    ) -> Iterable[list[OnChainMovement]]:
        transactions: dict[str, list[OnChainMovement]] = {}
        for movement in movements:
            if movement.transaction_id is None:
                yield [movement]
            else:
                transactions.setdefault(movement.transaction_id, []).append(movement)

        yield from transactions.values()

    def _book_transaction(self, movements: list[OnChainMovement]):
        for movement in movements:
            if movement.fee > 0:
                self._book_network_fee(movement)

        by_symbol: dict[str, list[OnChainMovement]] = defaultdict(list)
        for movement in self._book_swaps([x for x in movements if x.quantity != 0]):
            by_symbol[movement.symbol].append(movement)

        for same_coin in by_symbol.values():
            self._book_coin(same_coin)

    def _book_swaps(self, movements: list[OnChainMovement]) -> list[OnChainMovement]:
        """Books the swaps among the movements and returns the rest."""
        by_account: dict[str, list[OnChainMovement]] = defaultdict(list)
        for movement in movements:
            by_account[movement.account].append(movement)

        rest = []
        for same_account in by_account.values():
            given = [x for x in same_account if x.quantity < 0]
            got = [x for x in same_account if x.quantity > 0]
            if len(given) == 1 and len(got) == 1 and given[0].symbol != got[0].symbol:
                self._book_swap(given[0], got[0])
            else:
                rest += same_account

        return rest

    def _book_swap(self, given: OnChainMovement, got: OnChainMovement):
        # Whichever side has a market price values the other, so a coin with no
        # price of its own (a vault share) takes the one it was swapped at.
        if given.market_unit_price is not None:
            value = -given.quantity * given.market_unit_price
        elif got.market_unit_price is not None:
            value = got.quantity * got.market_unit_price
        else:
            logger.warning(
                f"Transaction {given.transaction_id}: neither {given.symbol} nor"
                f" {got.symbol} has a price, so the swap isn't booked"
            )
            return

        for movement, transaction_type, description in (
            (given, TransactionType.SELL, f"Swapped for {got.symbol}"),
            (got, TransactionType.BUY, f"Swapped from {given.symbol}"),
        ):
            self._add_trade(
                movement.account,
                Trade(
                    currency=movement.currency,
                    dataSource=movement.data_source,
                    description=description,
                    executed_at=given.executed_at,
                    fee=Decimal("0"),
                    quantity=abs(movement.quantity),
                    symbol=movement.symbol,
                    transaction_type=transaction_type,
                    unit_price=value / abs(movement.quantity),
                ),
            )

    def _book_coin(self, movements: list[OnChainMovement]):
        if unpriced := [x for x in movements if x.market_unit_price is None]:
            for movement in unpriced:
                logger.warning(
                    f"Transaction {movement.transaction_id}: {movement.symbol} has no"
                    " price and wasn't part of a swap, so it isn't booked"
                )
            movements = [x for x in movements if x.market_unit_price is not None]

        senders = [x for x in movements if x.quantity < 0]
        receivers = [x for x in movements if x.quantity > 0]
        if len(senders) != 1:
            for sender in senders:
                if not self._is_awaiting_confirmation(sender):
                    self._book_send(sender)
            for receiver in receivers:
                self._book_receipt(receiver)
            return

        [sender] = senders
        own_receivers = [x for x in receivers if x.account != sender.account]
        if not own_receivers and self._is_awaiting_confirmation(sender):
            return

        for receiver in receivers:
            if receiver.account == sender.account:
                self._book_receipt(receiver)

        for receiver in own_receivers:
            self._book_transfer(sender, receiver)

        sent_to_others = -sender.quantity - sum(x.quantity for x in own_receivers)
        if sent_to_others > 0:
            self._book_send(sender, sent_to_others)
        elif sent_to_others < 0:
            logger.warning(
                f"Transaction {sender.transaction_id}: `{sender.account}` sent"
                f" {-sender.quantity} {sender.symbol}, but the receiving accounts got"
                f" {-sender.quantity - sent_to_others}"
            )

    def _book_network_fee(self, movement: OnChainMovement):
        self._add_trade(
            movement.account,
            Trade(
                currency=movement.currency,
                dataSource=movement.data_source,
                description=_NETWORK_FEE_DESCRIPTION,
                executed_at=movement.executed_at,
                fee=Decimal("0"),
                quantity=movement.fee,
                symbol=movement.symbol,
                transaction_type=TransactionType.SELL,
                unit_price=Decimal("0"),
            ),
        )

    def _book_send(self, sender: OnChainMovement, quantity: Decimal | None = None):
        destination = sender.destination_address
        self._add_trade(
            sender.account,
            Trade(
                currency=sender.currency,
                dataSource=sender.data_source,
                description=f"Sent to {destination}" if destination else "Sent",
                executed_at=sender.executed_at,
                fee=Decimal("0"),
                quantity=-sender.quantity if quantity is None else quantity,
                symbol=sender.symbol,
                transaction_type=TransactionType.SELL,
                unit_price=sender.market_unit_price,
            ),
        )

    def _book_receipt(self, receiver: OnChainMovement):
        self._add_trade(
            receiver.account,
            Trade(
                currency=receiver.currency,
                dataSource=receiver.data_source,
                description="Received",
                executed_at=receiver.executed_at,
                fee=Decimal("0"),
                quantity=receiver.quantity,
                symbol=receiver.symbol,
                transaction_type=TransactionType.BUY,
                unit_price=receiver.market_unit_price,
            ),
        )

    def _book_transfer(self, sender: OnChainMovement, receiver: OnChainMovement):
        for account, transaction_type, description in (
            (sender.account, TransactionType.SELL, f"Transfer to {receiver.account}"),
            (receiver.account, TransactionType.BUY, f"Transfer from {sender.account}"),
        ):
            self._add_trade(
                account,
                Trade(
                    currency=sender.currency,
                    dataSource=sender.data_source,
                    description=description,
                    executed_at=sender.executed_at,
                    fee=Decimal("0"),
                    quantity=receiver.quantity,
                    symbol=sender.symbol,
                    transaction_type=transaction_type,
                    unit_price=sender.market_unit_price,
                ),
            )

    def _is_awaiting_confirmation(self, sender: OnChainMovement) -> bool:
        """A send to one of the wallets whose on-chain side isn't there yet."""
        if sender.destination_address is None:
            return False

        wallet = next(
            (x for x in self.wallets if x.owns(sender.destination_address)), None
        )
        if wallet is None or wallet.name == sender.account:
            return False
        if (
            self.tracked_symbols is not None
            and sender.symbol not in self.tracked_symbols.get(wallet.name, set())
        ):
            return False

        logger.warning(
            f"`{sender.account}` sent {-sender.quantity} {sender.symbol} to"
            f" `{wallet.name}`, but the transaction isn't confirmed yet; it'll be"
            " booked once it is"
        )
        return True

    def _add_trade(self, account: str, trade: Trade):
        self.portfolios[account].add_trades(trade.symbol, [trade])
