import datetime
import os

from modules.common_functions import *
import modules.mysql as mydb


def get_rate_limits():
    rate_limits = {}
    for (chat_id, messages_max, timespan) in mydb.get_rate_limits():
        is_unlimited = messages_max == 0 or timespan == 0
        if chat_id not in agent_chats:
            rate_limits[chat_id] = False if is_unlimited else {
                "messages_max": messages_max,
                "unread_messages": [],
                "timespan": timespan,
            }

    timenow = datetime.datetime.utcnow()
    for [chat_id, message_id, replies_count, timestamp] in mydb.get_messages():
        if chat_id not in agent_chats:
            if chat_id not in rate_limits: rate_limits[chat_id] = get_rate_limit_default()
            if rate_limits[chat_id] is not False:
                timespan = rate_limits[chat_id]["timespan"]
                cutoff_time = timenow - datetime.timedelta(seconds=timespan)
                is_in_timespan = timestamp > cutoff_time
                if is_in_timespan and replies_count is None:
                    rate_limits[chat_id]["unread_messages"].append({
                        "message_id": message_id,
                        "timestamp": timestamp
                    })

    return rate_limits


char_limit = int(os.getenv("char_limit") or 0)
chat_contexts = {}
agent_chats = mydb.get_agents()
rate_limits = get_rate_limits()
