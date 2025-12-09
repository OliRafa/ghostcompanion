from os import getenv

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


class CoinbaseSettings:
    API_KEY: str = getenv("COINBASE_API_KEY_ID", "")
    SECRET: str = getenv("COINBASE_SECRET", "")


class GhostfolioSettings:
    BASE_URL: str = f"{getenv('GHOSTFOLIO_BASE_URL', 'https://ghostfol.io')}/api/v1"
    ACCOUNT_TOKEN: str = getenv("GHOSTFOLIO_ACCOUNT_TOKEN", "")


class TastytradeSettings:
    CLIENT_SECRET: str = getenv("TASTYTRADE_CLIENT_SECRET", "")
    REFRESH_TOKEN: str = getenv("TASTYTRADE_REFRESH_TOKEN", "")


class Settings(GhostfolioSettings, TastytradeSettings):
    Coinbase = CoinbaseSettings
    Ghostfolio = GhostfolioSettings
    Tastytrade = TastytradeSettings
