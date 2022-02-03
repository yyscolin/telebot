import datetime
import logging
import os
from pathlib import Path
import telegram
import time
import traceback

from modules.handler import handle_update
import modules.mydb as mydb


telebot = telegram.Bot(token=os.getenv("bot_token"))
is_error_logged = {
    "internet": False,
}


def initialize_log_file():
    log_folder = os.getenv("log_folder") or "logs"
    Path(log_folder).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(log_folder, datetime.datetime.now().strftime("%Y-%m-%d") + ".log"),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(funcName)s - line %(lineno)d"
    )


def run_polling():
    timenow = datetime.datetime.utcnow()
    for update_obj in telebot.get_updates(timeout=60):
        handle_update(update_obj.to_dict(), timenow)


def start_polling():
    telebot.deleteWebhook()
    is_looping = True
    run_interval = int(os.getenv("run_interval") or 0)
    while is_looping:
        has_internet_error = False
        try:
            initialize_log_file()
            run_polling()
        except telegram.error.NetworkError:
            has_internet_error = True
            if is_error_logged["internet"] is False:
                traceback.print_exc()
                logging.exception("message")
                is_error_logged["internet"] = True
            pass
        except:
            traceback.print_exc()
            logging.exception("message")

        if is_error_logged["internet"] and has_internet_error is False:
            is_error_logged["internet"] = False
            print("Connection re-established")

        if run_interval > 0:
            time.sleep(run_interval)
        else:
            is_looping = False


if __name__ == "__main__":
    start_polling()
