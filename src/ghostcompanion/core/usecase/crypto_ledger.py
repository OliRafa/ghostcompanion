import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import final

from ghostcompanion.core.entity.lending import LendingBalance
from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.entity.wallet import Wallet

logger = logging.getLogger(__name__)

_NETWORK_FEE_DESCRIPTION = "Network Fee"
_INTEREST_EARNED_DESCRIPTION = "Interest earned"
_INTEREST_DUE_DESCRIPTION = "Interest due"
_BALANCE_CORRECTION_DESCRIPTION = "Balance correction"
# Well above what a lending market pays or charges a year outside of a crisis,
# so only a gap no interest could explain is taken for a missed move.
_MAX_YEARLY_INTEREST = Decimal("0.25")
_SECONDS_PER_YEAR = Decimal(365.25 * 24 * 3600)
# A market's books round every balance change, so its balances drift from the
# sum of the moves by a few of a coin's smallest units.
_ROUNDING = Decimal("0.00001")
_ROUNDING_SHARE = Decimal("0.000001")

# An account, and the lending market a movement happened in on its behalf, if any.
_Party = tuple[str, str | None]


@dataclass
class _Position:
    """What an account's moves in a lending market add up to in one coin, and
    when the last one was."""

    booked: Decimal = Decimal("0")
    moved_at: datetime | None = None

    def could_be_interest(
        self, held: Decimal, rounding: Decimal, observed_at: datetime
    ) -> bool:
        """Interest only grows a position away from nothing, coin supplied as
        much as a debt, and by no more than it plausibly can since the last
        move, rounding aside."""
        accrued = held - self.booked
        side = held if held != 0 else self.booked
        if (accrued > 0) != (side > 0):
            return False

        if self.moved_at is None:
            return abs(accrued) <= rounding
        since = observed_at - self.moved_at
        years = Decimal(since.total_seconds()) / _SECONDS_PER_YEAR
        size = max(abs(held), abs(self.booked))
        return abs(accrued) <= size * _MAX_YEARLY_INTEREST * years + rounding


@final
class CryptoLedger:
    """Books on-chain movements into the portfolios of the user's accounts.

    Everything trades at the market price of the moment, as Coinbase itself
    accounts for moves in and out of an account: coins leaving one of the user's
    accounts are sold, coins arriving are bought. Movements of one transaction
    between two of the user's accounts are a transfer, sold by the source and
    bought by the destination at the same price. An account giving one coin for
    another in a single transaction swapped them, at the price it got. Network
    fees are sold for nothing, and so is interest due on a debt, while interest
    earned is bought for nothing: neither was paid for with the user's money. A
    debt is repaid by buying it back for nothing, with what repaid it as a fee.

    What a lending market holds for an account, or what the account owes it, is
    still the account's: moving coins between the two moves nothing, and what
    the market does with them is booked in the account, naming the market.
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
        self._positions: dict[tuple[str, str, str], _Position] = defaultdict(_Position)

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
            if movement.interest and movement.quantity != 0:
                self._book_interest(movement)

        by_symbol: dict[str, list[OnChainMovement]] = defaultdict(list)
        for movement in self._book_swaps(
            [x for x in movements if x.quantity != 0 and not x.interest]
        ):
            by_symbol[movement.symbol].append(movement)

        for same_coin in by_symbol.values():
            self._book_coin(same_coin)

    def _book_swaps(self, movements: list[OnChainMovement]) -> list[OnChainMovement]:
        """Books the swaps among the movements and returns the rest."""
        by_party: dict[_Party, list[OnChainMovement]] = defaultdict(list)
        for movement in movements:
            by_party[_party(movement)].append(movement)

        rest = []
        for same_party in by_party.values():
            parts = [self._split_transfer(x, movements) for x in same_party]
            candidates = [remainder for _, remainder in parts if remainder is not None]
            given = [x for x in candidates if x.quantity < 0]
            got = [x for x in candidates if x.quantity > 0]
            if len(given) == 1 and len(got) == 1 and given[0].symbol != got[0].symbol:
                self._book_swap(given[0], got[0])
                rest += [transferred for transferred, _ in parts if transferred]
            else:
                rest += same_party

        return rest

    @staticmethod
    def _split_transfer(
        movement: OnChainMovement, movements: list[OnChainMovement]
    ) -> tuple[OnChainMovement | None, OnChainMovement | None]:
        """Splits a movement into what of it is one side of a transfer and the
        rest, which may be part of a swap.

        A coin that moves the other way in another of the user's accounts, or
        between an account and a market, is one side of a transfer, even when the
        same transaction trades another. Only as much as the other side moved is
        transferred, though, as when a market sells collateral to repay a debt
        and sends what's left to the wallet.
        """
        counterpart = -sum(
            (
                x.quantity
                for x in movements
                if x.symbol == movement.symbol
                and _party(x) != _party(movement)
                and (x.quantity > 0) != (movement.quantity > 0)
            ),
            Decimal("0"),
        )
        if counterpart == 0:
            return None, movement
        if abs(counterpart) >= abs(movement.quantity):
            return movement, None
        return (
            movement.model_copy(update={"quantity": counterpart}),
            movement.model_copy(update={"quantity": movement.quantity - counterpart}),
        )

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

        where = _on(given.market)
        for movement, transaction_type, description in (
            (given, TransactionType.SELL, f"Swapped for {got.symbol}{where}"),
            (got, TransactionType.BUY, f"Swapped from {given.symbol}{where}"),
        ):
            unit_price, fee = _price_and_fee(movement, transaction_type, value)
            self._add_trade(
                movement.account,
                movement.market,
                Trade(
                    currency=movement.currency,
                    dataSource=movement.data_source,
                    description=description,
                    executed_at=given.executed_at,
                    fee=fee,
                    quantity=abs(movement.quantity),
                    symbol=movement.symbol,
                    transaction_type=transaction_type,
                    unit_price=unit_price,
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
        own_receivers = [x for x in receivers if _party(x) != _party(sender)]
        if not own_receivers and self._is_awaiting_confirmation(sender):
            return

        for receiver in receivers:
            if _party(receiver) == _party(sender):
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

    def reconcile(self, balances: list[LendingBalance]) -> None:
        """Books what accounts hold in a lending market beyond what their
        movements add up to: the interest accrued since, which moves no coin.

        Call it after `book`, with every balance, zero ones included, since
        withdrawing or repaying more than the principal leaves the interest to
        book with nothing left in the market.

        A gap interest can't explain, because it shrinks the position or is
        more than it could have earned or owed since its last move, means a move
        went unread. It's still booked, so holdings match the market, but as a
        balance correction, with a warning.
        """
        totals: dict[tuple[str, str, str], list[LendingBalance]] = defaultdict(list)
        for balance in balances:
            totals[(balance.account, balance.market, balance.symbol)].append(balance)

        for (account, market, symbol), same_holding in totals.items():
            balance = same_holding[0]
            held = sum(x.quantity for x in same_holding)
            position = self._positions[(account, market, symbol)]
            accrued = held - position.booked
            if accrued == 0:
                continue

            description = _interest_description(accrued, market)
            rounding = _rounding(held, position.booked)
            if not position.could_be_interest(held, rounding, balance.observed_at):
                description = f"{_BALANCE_CORRECTION_DESCRIPTION} on {market}"
                if abs(accrued) > rounding:
                    logger.warning(
                        f"`{account}` holds {held} {symbol} in {market}, but its"
                        f" moves there add up to {position.booked}: booking the"
                        f" {accrued:+} difference as a balance correction, since"
                        " interest can't explain it. A move may have gone unread."
                    )
            self._book_for_nothing(
                account,
                market,
                balance.currency,
                balance.data_source,
                balance.observed_at,
                symbol,
                accrued,
                description,
            )

    def _book_interest(self, movement: OnChainMovement):
        # Ghostfolio orders activities of the same second at random. What the
        # market added accrued up to the move it came with, so dating it a second
        # earlier always counts it first: repaying a debt in full then never
        # looks like repaying more than was owed.
        self._book_for_nothing(
            movement.account,
            movement.market,
            movement.currency,
            movement.data_source,
            movement.executed_at - timedelta(seconds=1),
            movement.symbol,
            movement.quantity,
            movement.description
            or _interest_description(movement.quantity, movement.market),
        )

    def _book_for_nothing(
        self,
        account: str,
        market: str,
        currency: str,
        data_source: str,
        executed_at: datetime,
        symbol: str,
        quantity: Decimal,
        description: str,
    ):
        """Buys coins that came for nothing (`quantity` positive) or sells those
        that went for nothing (negative), as a debt growing does."""
        # Not also as an INTEREST activity: Ghostfolio files those under a manual
        # asset of its own naming, so the next import couldn't find it again.
        self._add_trade(
            account,
            market,
            Trade(
                currency=currency,
                dataSource=data_source,
                description=description,
                executed_at=executed_at,
                fee=Decimal("0"),
                quantity=abs(quantity),
                symbol=symbol,
                transaction_type=(
                    TransactionType.BUY if quantity > 0 else TransactionType.SELL
                ),
                unit_price=Decimal("0"),
            ),
        )

    def _book_network_fee(self, movement: OnChainMovement):
        self._add_trade(
            movement.account,
            movement.market,
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
            sender.market,
            Trade(
                currency=sender.currency,
                dataSource=sender.data_source,
                description=sender.description
                or (f"Sent to {destination}" if destination else "Sent"),
                executed_at=sender.executed_at,
                fee=Decimal("0"),
                quantity=-sender.quantity if quantity is None else quantity,
                symbol=sender.symbol,
                transaction_type=TransactionType.SELL,
                unit_price=sender.market_unit_price,
            ),
        )

    def _book_receipt(self, receiver: OnChainMovement):
        unit_price, fee = _price_and_fee(
            receiver,
            TransactionType.BUY,
            receiver.quantity * receiver.market_unit_price,
        )
        self._add_trade(
            receiver.account,
            receiver.market,
            Trade(
                currency=receiver.currency,
                dataSource=receiver.data_source,
                description=receiver.description or "Received",
                executed_at=receiver.executed_at,
                fee=fee,
                quantity=receiver.quantity,
                symbol=receiver.symbol,
                transaction_type=TransactionType.BUY,
                unit_price=unit_price,
            ),
        )

    def _book_transfer(self, sender: OnChainMovement, receiver: OnChainMovement):
        if sender.account == receiver.account:
            # The account's coins went into a market or came out of it: they
            # never stopped being the account's, so only the market's share moved.
            for party, quantity in (
                (sender, -receiver.quantity),
                (receiver, receiver.quantity),
            ):
                self._track(
                    party.account,
                    party.market,
                    party.symbol,
                    quantity,
                    sender.executed_at,
                )
            return

        for party, transaction_type, description in (
            (sender, TransactionType.SELL, f"Transfer to {receiver.account}"),
            (receiver, TransactionType.BUY, f"Transfer from {sender.account}"),
        ):
            self._add_trade(
                party.account,
                party.market,
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

    def _add_trade(self, account: str, market: str | None, trade: Trade):
        self.portfolios[account].add_trades(trade.symbol, [trade])
        sign = 1 if trade.transaction_type == TransactionType.BUY else -1
        self._track(
            account, market, trade.symbol, sign * trade.quantity, trade.executed_at
        )

    def _track(
        self,
        account: str,
        market: str | None,
        symbol: str,
        quantity: Decimal,
        executed_at: datetime,
    ):
        # Only what a market holds is checked against it later.
        if market is None:
            return
        position = self._positions[(account, market, symbol)]
        position.booked += quantity
        if position.moved_at is None or executed_at > position.moved_at:
            position.moved_at = executed_at


def _party(movement: OnChainMovement) -> _Party:
    return movement.account, movement.market


def _on(market: str | None) -> str:
    return f" on {market}" if market else ""


def _price_and_fee(
    movement: OnChainMovement, transaction_type: TransactionType, value: Decimal
) -> tuple[Decimal, Decimal]:
    """What to book a trade of `movement` at, given what it was worth.

    A debt bought back, which repays it, is bought for nothing with its worth
    as a fee. Ghostfolio measures a sale against the average of the buys since
    the holding was last at zero, so buying a debt back at its price would turn
    every later borrow, a sale of the debt, into a loss of that price.
    """
    if movement.debt and transaction_type == TransactionType.BUY:
        return Decimal("0"), value
    return value / abs(movement.quantity), Decimal("0")


def _interest_description(quantity: Decimal, market: str) -> str:
    if quantity > 0:
        return f"{_INTEREST_EARNED_DESCRIPTION} on {market}"
    return f"{_INTEREST_DUE_DESCRIPTION} to {market}"


def _rounding(held: Decimal, booked: Decimal) -> Decimal:
    return _ROUNDING + max(abs(held), abs(booked)) * _ROUNDING_SHARE
