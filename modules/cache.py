import datetime
import os

import modules.mydb as mydb


char_limit = int(os.getenv("char_limit") or 0)
chat_contexts = {}
agent_chats = mydb.get_agents()
update_ids = mydb.get_updates()
rate_limits = {}


def add_to_rate_limits(chat_id, messages_max=None, timespan=None):
    if chat_id not in rate_limits:
        if messages_max is None: messages_max = int(os.getenv("rate_limit_max") or 0)
        if timespan is None: timespan = int(os.getenv("rate_limit_timespan") or 0)
        is_unlimited = chat_id in agent_chats or messages_max == 0 or timespan == 0
        if is_unlimited is False:
            rate_limits[chat_id] = {
                "messages_max": messages_max,
                "unread_messages": [],
                "timespan": timespan,
            }


def get_unread_messages(chat_id, timenow):
    cutoff_time = timenow - datetime.timedelta(seconds=rate_limits[chat_id]["timespan"])
    rate_limits[chat_id]["unread_messages"] = list(filter(
        lambda x: x["timestamp"] > cutoff_time,
        rate_limits[chat_id]["unread_messages"]
    ))
    return rate_limits[chat_id]["unread_messages"]


def record_agent(chat_id, message):
    agent_chats.append(chat_id)
    mydb.record_agent(
        chat_id,
        message["chat"]["type"] == "group",
        message["chat"]["title"] or message["chat"]["username"] or message["chat"]["first_name"]
    )


def record_message(chat_id, message_id, message_date, reply_chat_id=None, reply_message_id=None):
    mydb.record_message(chat_id, message_id, message_date, reply_chat_id, reply_message_id)
    if chat_id in rate_limits:
        rate_limits[chat_id]["unread_messages"].append({
            "message_id": message_id,
            "timestamp": message_date
        })


def record_update(update_id, update_dict):
    update_ids.append(update_id)
    mydb.record_update(update_id, update_dict)


def set_rate_limits():
    for chat_id in agent_chats:
        add_to_rate_limits(chat_id)

    for (chat_id, messages_max, timespan) in mydb.get_rate_limits():
        add_to_rate_limits(chat_id, messages_max, timespan)

    timenow = datetime.datetime.utcnow()
    for [chat_id, message_id, replies_count, timestamp] in mydb.get_messages():
        add_to_rate_limits(chat_id)
        if chat_id in rate_limits:
            timespan = rate_limits[chat_id]["timespan"]
            cutoff_time = timenow - datetime.timedelta(seconds=timespan)
            is_in_timespan = timestamp > cutoff_time
            if is_in_timespan and replies_count is None:
                rate_limits[chat_id]["unread_messages"].append({
                    "message_id": message_id,
                    "timestamp": timestamp
                })


set_rate_limits()
