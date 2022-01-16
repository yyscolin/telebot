import datetime
from dotenv import load_dotenv
import mysql.connector
import os
import sys
import telegram
import time


load_dotenv()
master_chat = int(os.getenv("master_chat"))
mydb = mysql.connector.connect(
    host=os.getenv("mysql_host") or "127.0.0.1",
    port=os.getenv("mysql_port") or 3306,
    user=os.getenv("mysql_user"),
    password=os.getenv("mysql_password"),
    database=os.getenv("mysql_database")
)
mycursor = mydb.cursor()
telebot = telegram.Bot(token=os.getenv("bot_token"))


REJECT_MESSAGE_1 = """
You already have {} unreplied message(s) sent within the last {} seconds. Please wait for a response or try again later.
"""
REJECT_MESSAGE_2 = """
You cannot reply to this bot-generated message
"""
SQL_QUERY_1 = """
SELECT from_chat_id, from_message_id FROM forwarded_messages WHERE to_chat_id=%s and to_message_id=%s
"""
SQL_QUERY_2 = """
select chat_id, message_id, replies_count, is_rated, timestamp from messages left join (
    select reply_chat_id, reply_message_id, count(*) as replies_count
    from messages
    where reply_chat_id is not null and reply_message_id is not null
    group by reply_chat_id, reply_message_id
) t1 on messages.chat_id=t1.reply_chat_id and messages.message_id=t1.reply_message_id
"""


new_message_senders = []


def add_to_database(new_update, is_rated, reply_chat_id=None, reply_message_id=None):
    sql_query = "INSERT INTO messages VALUES (%s, %s, %s, %s, %s, %s)"
    mycursor.execute(sql_query, (
        new_update.message.chat_id,
        new_update.message.message_id,
        reply_chat_id,
        reply_message_id,
        is_rated,
        new_update.message.date
    ))
    mydb.commit()


def get_rate_limit_default(timenow):
    timespan = int(os.getenv("rate_limit_timespan") or 86400)
    return {
        "cutoff_time": timenow - datetime.timedelta(seconds=timespan),
        "messages_max": int(os.getenv("rate_limit_max") or 3),
        "messages_sent": 0,
        "timespan": timespan,
    }


def get_rate_limits_list():
    rate_limits = {}
    mycursor.execute("SELECT * FROM rate_limits")
    for [chat_id, limit, timespan] in mycursor.fetchall():
        rate_limits[chat_id] = {
            "cutoff_time": timenow - datetime.timedelta(seconds=timespan),
            "messages_max": limit,
            "messages_sent": 0,
            "timespan": timespan,
        }
    return rate_limits


def get_recorded_updates():
    update_ids = []
    mycursor.execute("select update_id from updates")
    for [update_id] in mycursor.fetchall():
        update_ids.append(update_id)
    return update_ids


def get_reply_target(to_chat_id, to_message_id):
    mycursor.execute(SQL_QUERY_1, (
        to_chat_id,
        to_message_id
    ))
    return mycursor.fetchone()


def is_in_array(haystack, needle):
    for array_element in haystack:
        if array_element == needle:
            return True
    return False


def push_message(from_chat_id, from_message_id, to_chat_id, push_tip, reply_message_id=None):
    telebot.send_message(to_chat_id, push_tip, reply_to_message_id=reply_message_id)
    forward_result = telebot.forward_message(to_chat_id, from_chat_id, from_message_id)
    telebot.send_message(from_chat_id, "Your message has been received.", reply_to_message_id=from_message_id)

    sql_query = "INSERT INTO forwarded_messages VALUES (%s, %s, %s, %s)"
    mycursor.execute(sql_query, (
        from_chat_id,
        from_message_id,
        to_chat_id,
        forward_result.message_id
    ))


def run_cronjob():
    rate_limits = get_rate_limits_list()
    timenow = datetime.datetime.now()

    mycursor.execute(SQL_QUERY_2)
    recorded_messages = mycursor.fetchall()
    for [chat_id, message_id, replies_count, is_rated, timestamp] in recorded_messages:
        if chat_id not in rate_limits:
            rate_limits[chat_id] = get_rate_limit_default(timenow)

        is_in_timespan = timestamp > rate_limits[chat_id]["cutoff_time"]
        if is_in_timespan and is_rated and replies_count is None:
            rate_limits[chat_id]["messages_sent"] += 1

    recorded_updates = get_recorded_updates()
    for new_update in telebot.get_updates(timeout=60):
        update_id = new_update.update_id
        if is_in_array(recorded_updates, update_id):
            continue

        mycursor.execute("insert into updates values (%s, %s)", (update_id, new_update.to_json()))
        mydb.commit()

        if new_update.message is None:
            continue

        chat_id = new_update.message.chat_id
        message_id = new_update.message.message_id

        if new_update.message.text == "/start":
            telebot.send_message(chat_id, "Hi, {}.".format(new_update.message.chat.first_name))
            add_to_database(new_update, False)
            continue

        if new_update.message.text == "/chatid":
            telebot.send_message(chat_id, "This chat ID is {}.".format(chat_id))
            add_to_database(new_update, False)
            continue

        if new_update.message.text == "/new" and chat_id == master_chat:
            if chat_id in new_message_senders:
                telebot.send_message(chat_id, "Your next reply has already been marked as a new message")
            else:
                new_message_senders.append(chat_id)
                telebot.send_message(chat_id, "Your next reply will be a new message instead of a reply")
            add_to_database(new_update, False)
            continue

        reply_to_message = new_update.message.reply_to_message
        if reply_to_message:
            is_bot_sent = reply_to_message.from_user.is_bot
            is_not_forwarded = reply_to_message.forward_from is None
            if is_bot_sent and is_not_forwarded:
                telebot.send_message(chat_id, REJECT_MESSAGE_2, reply_to_message_id=message_id)
                add_to_database(new_update, False)
                continue

        if chat_id not in rate_limits:
            rate_limits[chat_id] = get_rate_limit_default(timenow)

        messages_sent = rate_limits[chat_id]["messages_sent"]
        if messages_sent >= rate_limits[chat_id]["messages_max"]:
            timespan = rate_limits[chat_id]["timespan"]
            reject_message = REJECT_MESSAGE_1.format(messages_sent, timespan)
            telebot.send_message(chat_id, reject_message, reply_to_message_id=message_id)
            add_to_database(new_update, False)
            continue

        if reply_to_message:
            reply_target = get_reply_target(chat_id, reply_to_message.message_id)
            if reply_target is None:
                telebot.send_message(chat_id, "You cannot reply to this message due to an internal server error", reply_to_message_id=message_id)
                add_to_database(new_update, False)
                continue

            (reply_chat_id, reply_message_id) = reply_target
            if chat_id in new_message_senders:
                push_message(chat_id, message_id, reply_chat_id, "You have a new message:")
                new_message_senders.remove(chat_id)
                add_to_database(new_update, True)
                continue

            push_message(chat_id, message_id, reply_chat_id, "You have a reply for this message:", reply_message_id)
            add_to_database(new_update, True, reply_chat_id, reply_message_id)
            continue

        push_message(chat_id, message_id, master_chat, "You have a new message:")
        add_to_database(new_update, True)


while True:
    run_cronjob()
    run_interval = int(os.getenv("run_interval")) or 1
    time.sleep(run_interval)
