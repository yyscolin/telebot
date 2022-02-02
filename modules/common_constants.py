REJECT_MESSAGE_1 = """
You already have {} unreplied {} sent within the last {}. Please wait for a response or try again later.
"""
REJECT_MESSAGE_2 = """
You cannot reply to this bot-generated message
"""
REJECT_MESSAGE_3 = """
You cannot reply to this message due to an internal server error
"""
REJECT_MESSAGE_4 = """
You cannot send a message with more than {} {}
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
select chat_id, message_id, replies_count, timestamp
from messages left join (
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
