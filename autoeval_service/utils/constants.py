import os
import datetime

from typing import Final
from pathlib import Path


class Constants:
    LOGGER_DIR = os.environ.get("LOGGER_DIR", "logs")
    LOGGER_FILE_PATH: Final[str] = str(
        Path(f"{LOGGER_DIR}/server_logs-{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log").absolute())
    LOGGER_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(message)s"

    SERVER_DEFAULT_PORT = 12999
