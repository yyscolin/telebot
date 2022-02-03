from flask import Flask, request
import datetime
import os
import requests

import modules.mydb as mydb
from modules.handler import handle_update


app = Flask(__name__)


def set_webhook():
    bot_token = os.getenv("bot_token")
    webhook_url = os.getenv("webhook_url")
    set_wh_url = "https://api.telegram.org/bot{}/setWebhook?url={}"
    return requests.get(set_wh_url.format(bot_token, webhook_url))


@app.route("/", methods=["GET", "POST"])
def index():
    if (request.method == "POST"):
        update_dict = request.get_json()
        timenow = datetime.datetime.utcnow()
        handle_update(update_dict, timenow)
    return "Ok"


if __name__ == "__main__":
    webhook_response = set_webhook()
    if webhook_response.status_code == 200:
        app.run(debug=True)
    else:
        print("Error {} in setting up webhook:\n{}".format(
            webhook_response.status_code,
            webhook_response.json()["description"]
        ))
