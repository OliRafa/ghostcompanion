from tastytrade.account import Transaction


class AssetNotFoundException(Exception):
    ...


class TransactionTypeNotFoundException(Exception):
    def __init__(self, transaction: Transaction, *args):
        message = (
            "There's no mapping for the provided transaction type."
            f" Transaction: {transaction}"
        )
        super().__init__(message, *args)


class TradeNotFoundException(Exception):
    ...
