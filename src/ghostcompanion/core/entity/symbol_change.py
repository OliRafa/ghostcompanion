from pydantic import BaseModel


class SymbolChange(BaseModel):
    old_symbol: str
    new_symbol: str

    def __eq__(self, other) -> bool:
        """To implement 'in' operator"""
        if isinstance(other, str):
            return self.old_symbol == other
