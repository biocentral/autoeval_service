import os
import sys
import logging
import argparse

from public_hub_services.utils import Constants
from public_hub_services.main import create_app, run_server


def _setup_directories():
    required_directories = [Constants.LOGGER_DIR]
    for directory in required_directories:
        if not os.path.exists(directory):
            os.makedirs(directory)


def _setup_logging():
    formatter = logging.Formatter(Constants.LOGGER_FORMAT)

    # Create file handler for writing logs to file
    file_handler = logging.FileHandler(Constants.LOGGER_FILE_PATH, encoding='utf8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Create stream handler for console output
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    stream_handler.setStream(sys.stdout)

    # Get the root logger and add handlers
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    # Capture warnings with the logging system
    logging.captureWarnings(True)


_setup_directories()
_setup_logging()


def main():
    parser = argparse.ArgumentParser(description='Biocentral hub server')
    args = parser.parse_args()
    run_server()

if __name__ == '__main__':
    main()
