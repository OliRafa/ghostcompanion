from os import getenv

from dotenv import find_dotenv, load_dotenv

_ = load_dotenv(find_dotenv())


class BinanceSettings:
    API_KEY: str = getenv("BINANCE_API_KEY", "")
    SECRET: str = getenv("BINANCE_SECRET", "")


class BlockchainSettings:
    MEMPOOL_BASE_URL: str = getenv("MEMPOOL_BASE_URL", "https://mempool.space/api")


class CoinbaseSettings:
    API_KEY: str = getenv("COINBASE_API_KEY_ID", "")
    SECRET: str = getenv("COINBASE_SECRET", "").replace("\\n", "\n")


class EvmSettings:
    ALCHEMY_API_KEY: str = getenv("ALCHEMY_API_KEY", "")


class GhostfolioSettings:
    BASE_URL: str = f"{getenv('GHOSTFOLIO_BASE_URL', 'https://ghostfol.io')}/api/v1"
    ACCOUNT_TOKEN: str = getenv("GHOSTFOLIO_ACCOUNT_TOKEN", "")


class InteractiveBrokersSettings:
    QUERY: str = getenv("IBKR_QUERY", "")
    TOKEN: str = getenv("IBKR_TOKEN", "")


class TastytradeSettings:
    CLIENT_SECRET: str = getenv("TASTYTRADE_CLIENT_SECRET", "")
    REFRESH_TOKEN: str = getenv("TASTYTRADE_REFRESH_TOKEN", "")


class Settings(GhostfolioSettings, TastytradeSettings):
    CONFIG_PATH: str = getenv("GHOSTCOMPANION_CONFIG", "ghostcompanion.yaml")
    LOG_LEVEL: str = getenv("LOG_LEVEL", "INFO")
    Binance = BinanceSettings
    Blockchain = BlockchainSettings
    Coinbase = CoinbaseSettings
    Evm = EvmSettings
    Ghostfolio = GhostfolioSettings
    InteractiveBrokers = InteractiveBrokersSettings
    Tastytrade = TastytradeSettings
