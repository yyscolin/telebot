import datetime
from dotenv import load_dotenv
import json
import mysql.connector
import os
import psycopg2

from modules.constants import *


load_dotenv()

# Heroku postgres
mydb_url = os.getenv("DATABASE_URL")
if mydb_url:
    sql_query_4 = SQL_QUERY_4B
    mydb = psycopg2.connect(mydb_url)

# Other databases
else:
    mydb_type = int(os.getenv("mydb_type") or -1)
    mydb_port = os.getenv("mydb_port")
    if mydb_type == 0:
        sql_query_4 = SQL_QUERY_4A
        if mydb_port is None: mydb_port = 3306
    elif mydb_type == 1:
        sql_query_4 = SQL_QUERY_4B
        if mydb_port is None: mydb_port = 5432
    else:
        raise Exception("Invalid database type")
    mydbs = [mysql.connector, psycopg2]
    mydb = mydbs[mydb_type].connect(
        host=os.getenv("mydb_host") or "127.0.0.1",
        port=mydb_port,
        user=os.getenv("mydb_user"),
        password=os.getenv("mydb_password"),
        database=os.getenv("mydb_database")
    )

mycursor = mydb.cursor()


def get_agents():
    agents = []
    mycursor.execute("select chat_id from agents")
    for [chat_id] in mycursor.fetchall():
        agents.append(chat_id)
    return agents


def get_rate_limits():
    rate_limits = []
    mycursor.execute("SELECT * FROM rate_limits")
    for [chat_id, messages_max, timespan] in mycursor.fetchall():
        rate_limits.append((chat_id, messages_max, timespan))
    return rate_limits


def get_updates():
    update_ids = []
    mycursor.execute("select update_id from updates")
    for [update_id] in mycursor.fetchall():
        update_ids.append(update_id)
    return update_ids


def get_messages():
    mycursor.execute(SQL_QUERY_3)
    return mycursor.fetchall()


def get_reply_targets(to_chat_id, to_message_id):
    mycursor.execute(SQL_QUERY_1, (
        to_chat_id,
        to_message_id
    ))
    db_row = mycursor.fetchone()
    if db_row is None:
        return None

    reply_targets = []
    [from_chat_id, from_message_id] = db_row
    reply_targets.append((from_chat_id, from_message_id))

    mycursor.execute(SQL_QUERY_2, (
        from_chat_id,
        from_message_id,
        to_chat_id
    ))
    for [chat_id, message_id] in mycursor.fetchall():
        reply_targets.append((chat_id, message_id))

    return reply_targets


def record_agent(chat_id, is_group, name):
    mycursor.execute(sql_query_4, (chat_id, is_group, name))
    mydb.commit()


def record_forwarding(chat_id, message_id, to_chat_id, to_message_id):
    sql_query = "INSERT INTO forwarded_messages VALUES (%s, %s, %s, %s)"
    mycursor.execute(sql_query, (chat_id, message_id, to_chat_id, to_message_id))
    mydb.commit()


def record_message(chat_id, message_id, timestamp, reply_chat_id, reply_message_id):
    sql_query = "INSERT INTO messages VALUES (%s, %s, %s, %s, %s)"
    mycursor.execute(sql_query, (chat_id, message_id, reply_chat_id, reply_message_id, timestamp))
    mydb.commit()


def record_update(update_id, update_dict):
    mycursor.execute("insert into updates values (%s, %s)", (update_id, json.dumps(update_dict)))
    mydb.commit()
