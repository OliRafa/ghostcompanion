import logging
import sys
from os import getenv


def configure_logging(log_level: str | None = None) -> None:
    """Configure application logging.

    Sets up logging to output to stdout with a standard format.
    Configures third-party library log levels based on the application log level.

    Parameters
    ----------
    log_level : str | None
        Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        If None, uses LOG_LEVEL environment variable or defaults to INFO.
    """
    if log_level is None:
        log_level = getenv("LOG_LEVEL", "INFO")

    level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger configuration
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    # Configure third-party libraries
    # Suppress noisy libraries by default, allow full output in DEBUG mode
    third_party_level = logging.WARNING if level != logging.DEBUG else logging.DEBUG

    logging.getLogger("urllib3").setLevel(third_party_level)
    logging.getLogger("requests").setLevel(third_party_level)
    logging.getLogger("tastytrade").setLevel(third_party_level)
    logging.getLogger("yfinance").setLevel(third_party_level)
