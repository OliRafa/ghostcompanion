from pydantic import BaseModel, ConfigDict, Field


class GhostfolioAccount(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    account_type: str = Field("SECURITIES", alias="accountType", exclude=True)
    balance: float = 0.0
    balance_in_base_currency: float = Field(
        0.0, alias="balanceInBaseCurrency", exclude=True
    )
    comment: str | None = "Managed by GhostCompanion."
    currency: str | None = "USD"
    id: str = Field(default="", exclude=True)
    name: str
    platform_id: str | None = Field(default=None, alias="platformId")
