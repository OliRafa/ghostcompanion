from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from tastytrade_ghostfolio.core.entity.portfolio import Portfolio


class GhostfolioAccount(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    account_id: Optional[str] = Field(None, alias="id", exclude=True)
    account_type: str = Field("SECURITIES", alias="accountType", exclude=True)
    balance: float = 0.0
    balance_in_base_currency: float = Field(
        0.0, alias="balanceInBaseCurrency", exclude=True
    )
    comment: Optional[str] = "Created by Tastytrade-Ghostfolio."
    currency: str = "USD"
    id: Optional[str] = Field(None, exclude=True)
    name: str
    platform_id: Optional[str] = Field(None, alias="platformId")
    portfolio: Optional[Portfolio] = Field(None, exclude=True)

    def add_portfolio(self, portfolio: Portfolio):
        self.portfolio = portfolio
