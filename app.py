import datetime
from dotenv import load_dotenv
import mysql.connector
import os
import sys
import telegram
import time


load_dotenv()
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
select chat_id, message_id, replies_count, timestamp from messages left join (
    select reply_chat_id, reply_message_id, count(*) as replies_count
    from messages
    where reply_chat_id is not null and reply_message_id is not null
    group by reply_chat_id, reply_message_id
) t1 on messages.chat_id=t1.reply_chat_id and messages.message_id=t1.reply_message_id
"""
SQL_QUERY_3 = """
insert into agents values (%s, %s, %s) as vals
on duplicate key update
is_group=vals.is_group,
name=vals.name
"""


chat_contexts = {}


def get_agent_chats():
    agent_chats = []
    mycursor.execute("select chat_id from agents")
    for [chat_id] in mycursor.fetchall():
        agent_chats.append(chat_id)
    return agent_chats


def get_rate_limit_default(timenow):
    timespan = int(os.getenv("rate_limit_timespan") or 86400)
    return {
        "cutoff_time": timenow - datetime.timedelta(seconds=timespan),
        "messages_max": int(os.getenv("rate_limit_max") or 3),
        "messages_sent": 0,
        "timespan": timespan,
    }


def get_rate_limits_list(agent_chats):
    rate_limits = {}
    mycursor.execute("SELECT * FROM rate_limits")
    for [chat_id, limit, timespan] in mycursor.fetchall():
        if chat_id not in agent_chats:
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


def push_message(from_chat_id, from_message_id, to_chat_ids, push_tip, reply_message_id=None):
    for chat_id in to_chat_ids:
        telebot.send_message(chat_id, push_tip, reply_to_message_id=reply_message_id)
        forward_result = telebot.forward_message(chat_id, from_chat_id, from_message_id)
        sql_query = "INSERT INTO forwarded_messages VALUES (%s, %s, %s, %s)"
        mycursor.execute(sql_query, (
            from_chat_id,
            from_message_id,
            chat_id,
            forward_result.message_id
        ))
        mydb.commit()

    telebot.send_message(from_chat_id, "Your message has been received.", reply_to_message_id=from_message_id)


def record_agent(new_message):
    mycursor.execute(SQL_QUERY_3, (
        new_message.chat_id,
        new_message.chat.type == "group",
        new_message.chat.title or new_message.chat.username or new_message.chat.first_name
    ))
    mydb.commit()


def record_message(new_message, reply_chat_id=None, reply_message_id=None):
    sql_query = "INSERT INTO messages VALUES (%s, %s, %s, %s, %s)"
    mycursor.execute(sql_query, (
        new_message.chat_id,
        new_message.message_id,
        reply_chat_id,
        reply_message_id,
        new_message.date
    ))
    # time_delta = datetime.utcnow() - new_message.date.replace(tzinfo=None)
    # print(time.time(), type(time.time()))
    # timestamp = new_message.date.utcnow().timestamp()
    # print(timestamp, int(timestamp))
    mydb.commit()


def run_cronjob():
    agent_chats = get_agent_chats()
    rate_limits = get_rate_limits_list(agent_chats)
    timenow = datetime.datetime.now()

    mycursor.execute(SQL_QUERY_2)
    recorded_messages = mycursor.fetchall()
    for [chat_id, message_id, replies_count, timestamp] in recorded_messages:
        if chat_id not in agent_chats:
            if chat_id not in rate_limits:
                rate_limits[chat_id] = get_rate_limit_default(timenow)

            is_in_timespan = timestamp > rate_limits[chat_id]["cutoff_time"]
            if is_in_timespan and replies_count is None:
                rate_limits[chat_id]["messages_sent"] += 1

    recorded_updates = get_recorded_updates()
    for new_update in telebot.get_updates(timeout=60):
        update_id = new_update.update_id
        if is_in_array(recorded_updates, update_id):
            continue

        mycursor.execute("insert into updates values (%s, %s)", (update_id, new_update.to_json()))
        mydb.commit()

        new_message = new_update.message
        if new_message is None or new_message.group_chat_created:
            continue

        chat_id = new_message.chat_id
        message_id = new_message.message_id

        if new_message.text == "/start":
            telebot.send_message(chat_id, "Hi, {}.".format(new_message.chat.first_name))
            continue

        if new_message.text == "/setagent":
            chat_contexts[chat_id] = {"type": "agent_password"}
            telebot.send_message(chat_id, "Please enter the agent password")
            continue

        if chat_id in chat_contexts and chat_contexts[chat_id]["type"] == "agent_password":
            del chat_contexts[chat_id]

            agent_password = os.getenv("agent_password") or "PASSWORD.123"
            if new_message.text != agent_password:
                telebot.send_message(chat_id, "Wrong agent password entered")
                continue

            telebot.send_message(chat_id, "Setting this chat as an agent chat")
            record_agent(new_message)
            continue

        reply_to_message = new_message.reply_to_message
        if reply_to_message:
            is_bot_sent = reply_to_message.from_user.is_bot
            is_not_forwarded = reply_to_message.forward_from is None
            if is_bot_sent and is_not_forwarded:
                telebot.send_message(chat_id, REJECT_MESSAGE_2, reply_to_message_id=message_id)
                continue

        if chat_id not in agent_chats:
            if chat_id not in rate_limits:
                rate_limits[chat_id] = get_rate_limit_default(timenow)

            messages_sent = rate_limits[chat_id]["messages_sent"]
            if messages_sent >= rate_limits[chat_id]["messages_max"]:
                timespan = rate_limits[chat_id]["timespan"]
                reject_message = REJECT_MESSAGE_1.format(messages_sent, timespan)
                telebot.send_message(chat_id, reject_message, reply_to_message_id=message_id)
                continue

        if reply_to_message:
            reply_target = get_reply_target(chat_id, reply_to_message.message_id)
            if reply_target is None:
                telebot.send_message(chat_id, "You cannot reply to this message due to an internal server error", reply_to_message_id=message_id)
                continue

            (reply_chat_id, reply_message_id) = reply_target
            to_chat_ids = agent_chats if reply_chat_id in agent_chats else [reply_chat_id]
            push_message(chat_id, message_id, to_chat_ids, "You have a reply for this message:", reply_message_id)
            record_message(new_message, reply_chat_id, reply_message_id)
            continue

        push_message(chat_id, message_id, agent_chats, "You have a new message:")
        record_message(new_message)


while True:
    run_cronjob()
    run_interval = int(os.getenv("run_interval")) or 1
    time.sleep(run_interval)
