from enum import Enum


class TransactionType(Enum):
    BUY = "BUY"
    DIVIDEND = "DIVIDEND"
    FEE = "FEE"
    INTEREST = "INTEREST"
    ITEM = "ITEM"
    LIABILITY = "LIABILITY"
    SELL = "SELL"
