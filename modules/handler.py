import datetime
import math
import os
import telegram

import modules.cache as cache
from modules.constants import *
import modules.logger as logger
import modules.mydb as mydb


telebot = telegram.Bot(token=os.getenv("bot_token"))
validity_lifespan = int(os.getenv("validity_lifespan") or 0)


def eval(item, keys):
    for key in keys:
        if type(item) in (dict, tuple, list):
            if key in item:
                item = item[key]
            else:
                return None
        else:
            if hasattr(item, key):
                item = getattr(item, key)
            else:
                return None
    return item


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
        mydb.record_forwarding(
            from_chat_id,
            from_message_id,
            to_chat_id,
            eval(forward_result, ["message_id"])
        )

    if reply_targets is None:
        for chat_id in cache.agent_chats:
            push(chat_id)
    else:
        for (reply_chat_id, reply_message_id) in reply_targets:
            push(reply_chat_id, reply_message_id)

    confirm_message = "Your {} has been received.".format("reply" if reply_targets else "message")
    telebot.send_message(from_chat_id, confirm_message, reply_to_message_id=from_message_id)


def handle_update(update_dict, timenow):
    try:
        update_id = eval(update_dict, ["update_id"])
        if update_id in cache.update_ids:
            return True
        else:
            cache.record_update(update_id, update_dict)

        message = eval(update_dict, ["message"])
        if message is None:
            return True

        chat_id = eval(message, ["chat", "id"])
        message_id = eval(message, ["message_id"])
        message_text = eval(message, ["text"])
        message_date = datetime.datetime.utcfromtimestamp(eval(message, ["date"]))

        if validity_lifespan > 0:
            timediff = timenow - message_date
            if timediff.total_seconds() > validity_lifespan:
                return True

        if eval(message, ["group_chat_created"]):
            # TODO: Leave group chat
            return True

        if message_text == "/start":
            telebot.send_message(chat_id, "Hi, {}.".format(eval(message, ["chat", "first_name"])))
            return True

        if message_text == "/setagent":
            cache.chat_contexts[chat_id] = {"type": "agent_password"}
            telebot.send_message(chat_id, "Please enter the agent password")
            return True

        if chat_id in cache.chat_contexts and cache.chat_contexts[chat_id]["type"] == "agent_password":
            del cache.chat_contexts[chat_id]

            agent_password = os.getenv("agent_password") or "PASSWORD.123"
            if message_text != agent_password:
                telebot.send_message(chat_id, "Wrong agent password entered")
                return True

            telebot.send_message(chat_id, "Setting this chat as an agent chat")
            cache.record_agent(chat_id, message)
            return True

        if cache.char_limit > 0 and len(message_text) > cache.char_limit:
            telebot.send_message(chat_id, REJECT_MESSAGE_4.format(
                cache.char_limit,
                "character" if cache.char_limit == 1 else "characters"
            ), reply_to_message_id=message_id)
            return True

        reply_to_message = eval(message, ["reply_to_message"])
        if reply_to_message:
            is_bot_sent = eval(reply_to_message, ["from", "is_bot"])
            is_forwarded = eval(reply_to_message, ["forward_from"])
            if is_bot_sent and not is_forwarded:
                telebot.send_message(chat_id, REJECT_MESSAGE_2, reply_to_message_id=message_id)
                return True

        cache.add_to_rate_limits(chat_id)
        if chat_id in cache.rate_limits:
            unread_count = len(cache.get_unread_messages(chat_id, timenow))
            if unread_count >= cache.rate_limits[chat_id]["messages_max"]:
                timespan = cache.rate_limits[chat_id]["timespan"]
                reject_message = REJECT_MESSAGE_1.format(
                    unread_count,
                    "message" if unread_count == 1 else "messages",
                    parse_seconds_to_string(timespan)
                )
                telebot.send_message(chat_id, reject_message, reply_to_message_id=message_id)
                return True

        if reply_to_message:
            reply_targets = mydb.get_reply_targets(chat_id, eval(reply_to_message, ["message_id"]))
            if reply_targets is None:
                telebot.send_message(chat_id, REJECT_MESSAGE_3, reply_to_message_id=message_id)
                return True

            push_message(chat_id, message_id, "Reply received for this message:", reply_targets)
            (reply_chat_id, reply_message_id) = reply_targets[0]
            cache.record_message(chat_id, message_id, message_date, reply_chat_id, reply_message_id)
            if reply_chat_id in cache.rate_limits:
                cache.rate_limits[reply_chat_id]["unread_messages"] = list(filter(
                    lambda x: x["message_id"] != reply_message_id,
                    cache.rate_limits[reply_chat_id]["unread_messages"]
                ))
            return True

        if chat_id not in cache.agent_chats:
            push_message(chat_id, message_id, "You have a new message:")
            cache.record_message(chat_id, message_id, message_date)
    except:
        logger.log_exception()
