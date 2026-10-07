import logging
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
    bought by the destination at the same price. Network fees are sold for
    nothing.
    """

    def __init__(self, portfolios: dict[str, Portfolio], wallets: list[Wallet]):
        self.portfolios = portfolios
        self.wallets = wallets

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

        logger.warning(
            f"`{sender.account}` sent {-sender.quantity} {sender.symbol} to"
            f" `{wallet.name}`, but the transaction isn't confirmed yet; it'll be"
            " booked once it is"
        )
        return True

    def _add_trade(self, account: str, trade: Trade):
        self.portfolios[account].add_trades(trade.symbol, [trade])
