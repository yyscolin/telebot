import datetime
from dotenv import load_dotenv
import math
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
You already have {} unreplied {} sent within the last {}. Please wait for a response or try again later.
"""
REJECT_MESSAGE_2 = """
You cannot reply to this bot-generated message
"""
REJECT_MESSAGE_3 = """
You cannot reply to this message due to an internal server error
"""
SQL_QUERY_1A = """
SELECT from_chat_id, from_message_id
FROM forwarded_messages
WHERE to_chat_id=%s and to_message_id=%s
"""
SQL_QUERY_1B = """
SELECT to_chat_id, to_message_id
FROM forwarded_messages
WHERE from_chat_id=%s and from_message_id=%s and to_chat_id != %s
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


agent_chats = []
chat_contexts = {}


def get_rate_limit_default(timenow):
    messages_max = int(os.getenv("rate_limit_max") or 0)
    timespan = int(os.getenv("rate_limit_timespan") or 0)
    return parse_rate_limit(timenow, messages_max, timespan)


def get_rate_limits_list(timenow):
    global agent_chats
    rate_limits = {}
    mycursor.execute("SELECT * FROM rate_limits")
    for [chat_id, messages_max, timespan] in mycursor.fetchall():
        if chat_id not in agent_chats:
            rate_limits[chat_id] = parse_rate_limit(timenow, messages_max, timespan)
    return rate_limits


def get_recorded_updates():
    update_ids = []
    mycursor.execute("select update_id from updates")
    for [update_id] in mycursor.fetchall():
        update_ids.append(update_id)
    return update_ids


def get_reply_targets(to_chat_id, to_message_id):
    mycursor.execute(SQL_QUERY_1A, (
        to_chat_id,
        to_message_id
    ))
    db_row = mycursor.fetchone()
    if db_row is None:
        return None

    reply_targets = []
    [from_chat_id, from_message_id] = db_row
    reply_targets.append((from_chat_id, from_message_id))

    mycursor.execute(SQL_QUERY_1B, (
        from_chat_id,
        from_message_id,
        to_chat_id
    ))
    for [chat_id, message_id] in mycursor.fetchall():
        reply_targets.append((chat_id, message_id))

    return reply_targets


def parse_rate_limit(timenow, messages_max, timespan):
    is_unlimited = messages_max == 0 or timespan == 0
    return False if is_unlimited else {
        "cutoff_time": timenow - datetime.timedelta(seconds=timespan),
        "messages_max": messages_max,
        "messages_sent": 0,
        "timespan": timespan,
    }


def parse_seconds_to_string(seconds):
    strings = []
    days = math.floor(seconds / 86400)
    hours = math.floor(seconds % 86400 / 3600)
    mins = math.floor(seconds % 86400 % 3600 / 60)
    secs = math.floor(seconds % 86400 % 3600 % 60)
    if days > 0:
        strings.append("{} day{}".format(days, "s" if days != 1 else ""))
    if hours > 0:
        strings.append("{} hour{}".format(hours, "s" if hours != 1 else ""))
    if mins > 0:
        strings.append("{} minute{}".format(mins, "s" if mins != 1 else ""))
    if secs > 0:
        strings.append("{} second{}".format(secs, "s" if secs != 1 else ""))
    return " and ".join(strings)


def push_message(from_chat_id, from_message_id, push_tip, reply_targets=None):
    def push(to_chat_id, reply_message_id=None):
        telebot.send_message(to_chat_id, push_tip, reply_to_message_id=reply_message_id)
        forward_result = telebot.forward_message(to_chat_id, from_chat_id, from_message_id)
        sql_query = "INSERT INTO forwarded_messages VALUES (%s, %s, %s, %s)"
        mycursor.execute(sql_query, (
            from_chat_id,
            from_message_id,
            to_chat_id,
            forward_result.message_id
        ))
        mydb.commit()

    if reply_targets is None:
        for chat_id in agent_chats:
            push(chat_id)
    else:
        for (reply_chat_id, reply_message_id) in reply_targets:
            push(reply_chat_id, reply_message_id)

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
    mydb.commit()


def update_agent_chats():
    global agent_chats
    updated_agent_chats = []
    mycursor.execute("select chat_id from agents")
    for [chat_id] in mycursor.fetchall():
        updated_agent_chats.append(chat_id)
    agent_chats = updated_agent_chats


def run_cronjob():
    global agent_chats
    update_agent_chats()
    timenow = datetime.datetime.utcnow()
    rate_limits = get_rate_limits_list(timenow)

    mycursor.execute(SQL_QUERY_2)
    recorded_messages = mycursor.fetchall()
    for [chat_id, message_id, replies_count, timestamp] in recorded_messages:
        if chat_id in agent_chats:
            continue

        if chat_id not in rate_limits:
            rate_limits[chat_id] = get_rate_limit_default(timenow)

        if rate_limits[chat_id] is False:
            continue

        is_in_timespan = timestamp > rate_limits[chat_id]["cutoff_time"]
        if is_in_timespan and replies_count is None:
            rate_limits[chat_id]["messages_sent"] += 1

    recorded_updates = get_recorded_updates()
    validity_lifespan = int(os.getenv("validity_lifespan")) or 30
    for new_update in telebot.get_updates(timeout=60):
        update_id = new_update.update_id
        if update_id in recorded_updates:
            continue

        mycursor.execute("insert into updates values (%s, %s)", (update_id, new_update.to_json()))
        mydb.commit()

        new_message = new_update.message
        if new_message is None:
            continue

        if new_message.group_chat_created:
            # TODO: Leave group chat
            continue

        timediff = timenow - new_update.message.date.replace(tzinfo=None)
        if timediff.total_seconds() > validity_lifespan:
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

            if rate_limits[chat_id] is not False:
                messages_sent = rate_limits[chat_id]["messages_sent"]
                if messages_sent >= rate_limits[chat_id]["messages_max"]:
                    timespan = rate_limits[chat_id]["timespan"]
                    reject_message = REJECT_MESSAGE_1.format(
                        messages_sent,
                        "message" if messages_sent == 1 else "messages",
                        parse_seconds_to_string(timespan)
                    )
                    telebot.send_message(chat_id, reject_message, reply_to_message_id=message_id)
                    continue
                rate_limits[chat_id]["messages_sent"] += 1

        if reply_to_message:
            reply_targets = get_reply_targets(chat_id, reply_to_message.message_id)
            if reply_targets is None:
                telebot.send_message(chat_id, REJECT_MESSAGE_3, reply_to_message_id=message_id)
                continue

            push_message(chat_id, message_id, "Reply received for this message:", reply_targets)
            (reply_chat_id, reply_message_id) = reply_targets[0]
            record_message(new_message, reply_chat_id, reply_message_id)
            continue

        if chat_id not in agent_chats:
            push_message(chat_id, message_id, "You have a new message:")
            record_message(new_message)


while True:
    try:
        run_cronjob()
    except Exception as error:
        print(error)
    run_interval = int(os.getenv("run_interval")) or 1
    time.sleep(run_interval)
