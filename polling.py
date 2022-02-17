import datetime
import os
import telegram
import time

from modules.handler import handle_update
import modules.logger as logger

telebot = telegram.Bot(token=os.getenv("bot_token"))
is_error_logged = {
    "internet": False,
}


def start_polling():
    telebot.deleteWebhook()
    is_looping = True
    run_interval = int(os.getenv("run_interval") or 0)
    logger.initialize_log_file()
    while is_looping:
        has_internet_error = False
        try:
            telegram_updates = telebot.get_updates(timeout=60)
        except telegram.error.NetworkError:
            has_internet_error = True
            if is_error_logged["internet"] is False:
                logger.log_exception()
                is_error_logged["internet"] = True
        except:
            logger.log_exception()
        else:
            timenow = datetime.datetime.utcnow()
            for update_obj in telegram_updates:
                handle_update(update_obj.to_dict(), timenow)

        if is_error_logged["internet"] and has_internet_error is False:
            is_error_logged["internet"] = False
            print("Connection re-established")

        if run_interval > 0:
            time.sleep(run_interval)
        else:
            is_looping = False


if __name__ == "__main__":
    start_polling()
