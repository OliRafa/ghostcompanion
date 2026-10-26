from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, NamedTuple

from ghostcompanion.core.entity.lending import (
    LendingBalance,
    LendingChange,
    LendingReserve,
)
from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.token import Token
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.ports.evm_chain import EvmChainPort
from ghostcompanion.core.ports.lending_market import LendingMarketPort
from ghostcompanion.core.ports.market_prices import MarketPricePort

_CURRENCY = "USD"
_WEI_PER_ETHER = Decimal(10**18)
# Debts are served by the price proxy, under a symbol of their own so they never
# merge with the coin itself.
_DEBT_PREFIX = "DEBT-"
_DEBT_DATA_SOURCE = "GHOSTFOLIO"
# How far, in a coin's smallest units, the market's principal can be from what
# moved: its books round each balance change.
_ROUNDING_UNITS = 10


class _WalletSide(NamedTuple):
    description: str | None


class _MarketSide(NamedTuple):
    """A change to the coin the market holds for the account, or to what the
    account owes it."""

    debt: bool
    quantity: Decimal
    description: str | None = None
    interest: bool = False


class EvmWalletProvider:
    LENDING_MARKET = "Aave"

    def __init__(
        self,
        evm_chain_api: EvmChainPort,
        market_prices: MarketPricePort,
        lending_market: LendingMarketPort | None = None,
    ):
        self.evm_chain_api = evm_chain_api
        self.market_prices = market_prices
        self.lending_market = lending_market
        self._reserves: dict[Network, dict[str, LendingReserve]] = {}

    def get_movements(
        self, wallet: Wallet, tokens: list[Token]
    ) -> list[OnChainMovement]:
        """One movement per transaction and tracked token, net of what came back
        in the same transaction, on every network the wallet spans."""
        movements = []
        for network in wallet.networks:
            tracked = {x.contract: x for x in tokens if x.network == network}
            reserves = self._get_reserves(network, tracked)
            movements += self._get_network_movements(wallet, network, tracked, reserves)

        return sorted(movements, key=lambda x: x.executed_at)

    def get_lending_balances(
        self, wallet: Wallet, tokens: list[Token]
    ) -> list[LendingBalance]:
        """What the wallet holds in the lending market right now, interest
        included, for every tracked coin the market lends: zero ones too, since
        a position closed with interest still leaves that interest to book."""
        if self.lending_market is None:
            return []

        observed_at = datetime.now(timezone.utc)
        balances = []
        for network in wallet.networks:
            tracked = {x.contract: x for x in tokens if x.network == network}
            reserves = list(self._get_reserves(network, tracked).values())
            for address in wallet.addresses:
                for position in self.lending_market.get_positions(
                    network, address, reserves
                ):
                    token = tracked[position.reserve.asset]
                    for symbol, data_source, quantity in (
                        (token.symbol, token.data_source, position.supplied),
                        (
                            _DEBT_PREFIX + token.symbol,
                            _DEBT_DATA_SOURCE,
                            -position.borrowed,
                        ),
                    ):
                        balances.append(
                            LendingBalance(
                                account=wallet.name,
                                currency=_CURRENCY,
                                data_source=data_source,
                                market=self.LENDING_MARKET,
                                observed_at=observed_at,
                                quantity=quantity,
                                symbol=symbol,
                            )
                        )
        return balances

    def _get_reserves(
        self, network: Network, tracked: dict[str | None, Token]
    ) -> dict[str, LendingReserve]:
        if self.lending_market is None:
            return {}
        if network not in self._reserves:
            assets = sorted(x for x in tracked if x is not None)
            self._reserves[network] = {
                x.asset: x for x in self.lending_market.get_reserves(network, assets)
            }
        return self._reserves[network]

    def _get_network_movements(
        self,
        wallet: Wallet,
        network: Network,
        tracked: dict[str | None, Token],
        reserves: dict[str, LendingReserve],
    ) -> list[OnChainMovement]:
        transfers: dict[str, dict[str, Any]] = {}
        for address in wallet.addresses:
            for direction in ("from", "to"):
                for transfer in self.evm_chain_api.get_asset_transfers(
                    network, address, direction
                ):
                    transfers[transfer["uniqueId"]] = transfer

        by_transaction: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for transfer in transfers.values():
            by_transaction[transfer["hash"].lower()].append(transfer)

        # Every transaction the wallet signs moves its native coin from it, even
        # a zero amount, so these are the ones that may have cost it a fee. The
        # market's own tokens moving tell it acted on the wallet's position,
        # whoever signed for it, and its receipt tells what it did.
        market_tokens = self._market_tokens(reserves)
        candidates = sorted(
            transaction_hash
            for transaction_hash, items in by_transaction.items()
            if any(
                (x["category"] == "external" and self._owns(wallet, x["from"]))
                or (x["rawContract"]["address"] or "").lower() in market_tokens
                for x in items
            )
        )
        receipts = {
            receipt["transactionHash"].lower(): receipt
            for receipt in self.evm_chain_api.get_transaction_receipts(
                network, candidates
            )
        }

        movements = []
        for transaction_hash, items in by_transaction.items():
            receipt = receipts.get(transaction_hash)
            movements += self._adapt_transaction(
                wallet, network, tracked, reserves, transaction_hash, items, receipt
            )

        return movements

    def _adapt_transaction(
        self,
        wallet: Wallet,
        network: Network,
        tracked: dict[str | None, Token],
        reserves: dict[str, LendingReserve],
        transaction_hash: str,
        transfers: list[dict[str, Any]],
        receipt: dict[str, Any] | None,
    ) -> list[OnChainMovement]:
        signed_by_wallet = receipt is not None and self._owns(wallet, receipt["from"])
        fee = self._fee(receipt) if signed_by_wallet else Decimal("0")
        # A failed transaction moved nothing, but its signer still paid the fee.
        succeeded = receipt is None or receipt["status"] == "0x1"

        quantities: dict[Token, Decimal] = defaultdict(Decimal)
        destinations: dict[Token, set[str]] = defaultdict(set)
        # Contracts whose tokens moved in or out of the wallet, tracked or not.
        touched: set[str] = set()
        for transfer in transfers if succeeded else []:
            contract = (transfer["rawContract"]["address"] or "").lower() or None
            if contract and (
                self._owns(wallet, transfer["to"])
                or self._owns(wallet, transfer["from"])
            ):
                touched.add(contract)
            token = tracked.get(contract)
            amount = self._amount(transfer)
            # Untracked contracts are where lookalike tokens and spam live, and
            # anyone can emit a zero-value transfer in the wallet's name.
            if token is None or amount == 0:
                continue
            if self._owns(wallet, transfer["to"]):
                quantities[token] += amount
            if self._owns(wallet, transfer["from"]):
                quantities[token] -= amount
                if not self._owns(wallet, transfer["to"]):
                    destinations[token].add(transfer["to"].lower())

        native = tracked.get(None)
        if fee > 0 and native is not None:
            quantities.setdefault(native, Decimal("0"))

        executed_at = datetime.fromisoformat(transfers[0]["metadata"]["blockTimestamp"])
        prices: dict[Token, Decimal | None] = {}

        def price_of(token: Token) -> Decimal | None:
            if token not in prices:
                prices[token] = self._price(token, executed_at)
            return prices[token]

        movements = []
        # The wallet's coins that went to or came from the market, and how to
        # describe them.
        settled: dict[Token, str | None] = {}
        for change in self._get_lending_changes(wallet, reserves, touched, receipt):
            token = tracked[change.reserve.asset]
            market_movements, wallet_side = self._adapt_lending(
                change,
                wallet.name,
                token,
                quantities.get(token, Decimal("0")),
                price_of(token),
                executed_at,
                transaction_hash,
            )
            movements += market_movements
            if wallet_side is not None:
                settled[token] = wallet_side.description

        for token, quantity in quantities.items():
            if quantity == 0 and not (token is native and fee > 0):
                continue

            movements.append(
                OnChainMovement(
                    account=wallet.name,
                    currency=_CURRENCY,
                    data_source=token.data_source,
                    description=settled.get(token),
                    destination_address=(
                        next(iter(destinations[token]))
                        if token not in settled and len(destinations[token]) == 1
                        else None
                    ),
                    executed_at=executed_at,
                    fee=fee if token is native else Decimal("0"),
                    market_unit_price=price_of(token),
                    quantity=quantity,
                    symbol=token.symbol,
                    transaction_id=transaction_hash,
                )
            )
        return movements

    def _get_lending_changes(
        self,
        wallet: Wallet,
        reserves: dict[str, LendingReserve],
        touched: set[str],
        receipt: dict[str, Any] | None,
    ) -> list[LendingChange]:
        """What the transaction did to the wallet's positions in the market, one
        change per reserve however many of the wallet's addresses it touched."""
        if (
            self.lending_market is None
            or receipt is None
            or not touched & self._market_tokens(reserves)
        ):
            return []

        totals: dict[LendingReserve, dict[str, Decimal]] = defaultdict(
            lambda: defaultdict(Decimal)
        )
        for address in wallet.addresses:
            for change in self.lending_market.get_changes(
                address, list(reserves.values()), receipt
            ):
                for field, amount in change.model_dump(exclude={"reserve"}).items():
                    totals[change.reserve][field] += amount
        return [
            LendingChange(reserve=reserve, **amounts)
            for reserve, amounts in totals.items()
        ]

    def _adapt_lending(
        self,
        change: LendingChange,
        account: str,
        token: Token,
        moved: Decimal,
        price: Decimal | None,
        executed_at: datetime,
        transaction_hash: str,
    ) -> tuple[list[OnChainMovement], _WalletSide | None]:
        """The market's side of a transaction in one reserve, in the wallet's
        account, and, when the wallet's own coin went to or came from the market,
        how to describe it.

        The market's books round, which can leave its principal a few units off
        what actually moved, so what the wallet sent or got is the principal. A
        debt is still owed to the unit, though: what the books added beyond that
        principal is booked apart, as added for nothing, so that repaying it all
        leaves exactly nothing owed.
        """
        market = self.LENDING_MARKET
        tolerance = _ROUNDING_UNITS / Decimal(10) ** change.reserve.decimals
        supplied, borrowed, wallet_side = change.supplied, change.borrowed, None
        rounding = Decimal("0")
        if moved and supplied and abs(supplied + moved) <= tolerance:
            # A move between the wallet and its own position in the market.
            supplied, wallet_side = -moved, _WalletSide(None)
        elif moved and borrowed and abs(borrowed - moved) <= tolerance:
            rounding, borrowed = moved - borrowed, moved
            wallet_side = _WalletSide(_debt_description(market, moved))

        sides = (
            _MarketSide(False, supplied + change.transferred),
            _MarketSide(True, -borrowed, _debt_description(market, borrowed)),
            _MarketSide(False, change.interest_earned, interest=True),
            _MarketSide(True, -change.interest_due, interest=True),
            _MarketSide(
                True, rounding, _rounding_description(market, rounding), interest=True
            ),
        )
        movements = [
            OnChainMovement(
                account=account,
                currency=_CURRENCY,
                data_source=_DEBT_DATA_SOURCE if side.debt else token.data_source,
                debt=side.debt,
                description=side.description,
                executed_at=executed_at,
                interest=side.interest,
                market=market,
                market_unit_price=price,
                quantity=side.quantity,
                symbol=_DEBT_PREFIX + token.symbol if side.debt else token.symbol,
                transaction_id=transaction_hash,
            )
            for side in sides
            if side.quantity != 0
        ]
        return movements, wallet_side

    @staticmethod
    def _market_tokens(reserves: dict[str, LendingReserve]) -> set[str]:
        return {
            token
            for reserve in reserves.values()
            for token in (reserve.supply_token, reserve.debt_token)
        }

    def _price(self, token: Token, executed_at: datetime) -> Decimal | None:
        if token.price_symbol is None:
            return None
        return self.market_prices.get_crypto_price(
            token.price_symbol, _CURRENCY, executed_at, token.network, token.contract
        )

    @staticmethod
    def _amount(transfer: dict[str, Any]) -> Decimal:
        raw = transfer["rawContract"]
        return Decimal(int(raw["value"] or "0x0", 16)) / Decimal(10) ** int(
            raw["decimal"] or "0x12", 16
        )

    @staticmethod
    def _fee(receipt: dict[str, Any]) -> Decimal:
        # On Base, a transaction also pays for posting its data to Ethereum.
        wei = int(receipt["gasUsed"], 16) * int(receipt["effectiveGasPrice"], 16)
        wei += int(receipt.get("l1Fee") or "0x0", 16)
        return Decimal(wei) / _WEI_PER_ETHER

    @staticmethod
    def _owns(wallet: Wallet, address: str | None) -> bool:
        return address is not None and wallet.owns(address)


def _debt_description(market: str, borrowed: Decimal) -> str:
    return f"Borrowed from {market}" if borrowed > 0 else f"Repaid to {market}"


def _rounding_description(market: str, quantity: Decimal) -> str:
    return f"Rounded {'up' if quantity < 0 else 'down'} by {market}"
