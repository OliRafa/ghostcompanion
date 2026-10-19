from ghostcompanion.core.entity.symbol_change import SymbolChange
from ghostcompanion.core.entity.token import DEFAULT_TOKENS, Token
from ghostcompanion.core.entity.wallet import Wallet


class InMemoryConfigRepository:
    def __init__(
        self,
        symbol_changes: list[SymbolChange] | None = None,
        wallets: list[Wallet] | None = None,
        tokens: list[Token] | None = None,
    ) -> None:
        self._symbol_changes = symbol_changes or []
        self._wallets = wallets or []
        self._tokens = list(DEFAULT_TOKENS) + (tokens or [])

    def get_symbol_mappings(self) -> list[SymbolChange]:
        return self._symbol_changes

    def get_wallets(self) -> list[Wallet]:
        return self._wallets

    def get_tokens(self) -> list[Token]:
        return self._tokens
