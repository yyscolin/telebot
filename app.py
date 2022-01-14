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


def add_to_database(new_update):
    sql_query = "INSERT INTO updates VALUES (%s, %s, %s, %s)"
    mycursor.execute(sql_query, (
        new_update.message.chat.id,
        new_update.message.message_id,
        new_update.message.date,
        new_update.__str__()
    ))
    mydb.commit()


def is_in_database(db_list, chat_id, message_id):
    for db_row in db_list:
        is_same_chat = db_row[0] == chat_id
        is_same_message = db_row[1] == message_id
        if is_same_chat and is_same_message:
            return True
    return False


def run_cronjob():
    mycursor.execute("SELECT * FROM updates")
    db_list = mycursor.fetchall()

    for new_update in telebot.get_updates():
        chat_id = new_update.message.chat.id
        message_id = new_update.message.message_id

        if is_in_database(db_list, chat_id, message_id):
            continue

        if new_update.message.text == "/chatid":
            telebot.send_message(chat_id, "This chat ID is {}.".format(chat_id))
            add_to_database(new_update)
            continue

        if chat_id == os.getenv("master_chat") and new_update.message.reply_to_message:
            reply_chat = new_update.message.reply_to_message.forward_from.id
            telebot.forward_message(reply_chat, chat_id, message_id)
            add_to_database(new_update)
            continue
        
        telebot.forward_message(os.getenv("master_chat"), chat_id, message_id)
        add_to_database(new_update)


while True:
    run_cronjob()
    run_interval = int(os.getenv("run_interval")) or 1
    time.sleep(run_interval)
