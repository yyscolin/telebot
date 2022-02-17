import datetime
import logging
import os
from pathlib import Path
import traceback


def initialize_log_file():
    log_folder = os.getenv("log_folder") or "logs"
    Path(log_folder).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(log_folder, datetime.datetime.now().strftime("%Y-%m-%d") + ".log"),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(funcName)s - line %(lineno)d"
    )


def log_exception():
    traceback.print_exc()
    logging.exception("message")
