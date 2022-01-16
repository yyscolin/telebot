# Telebot v1.0
Telebot is a simple project which forwards all Telegram messages sent to a bot into a chat (i.e. master chat) and vice-versa.

## Create database tables
```
create table updates (
    update_id int unsigned not null primary key,
    payload varchar(1200) not null
);

create table messages (
    chat_id int not null,
    message_id int unsigned not null,
    reply_chat_id int,
    reply_message_id int unsigned,
    timestamp timestamp not null,
    primary key (chat_id, message_id)
);

create table rate_limits (
    chat_id int not null primary key,
    `limit` int unsigned not null,
    timespan int unsigned not null
);

create table forwarded_messages (
    from_chat_id int not null,
    from_message_id int unsigned not null,
    to_chat_id int not null,
    to_message_id int unsigned not null,
    primary key (to_chat_id, to_message_id)
);
```

Grant INSERT and SELECT privileges to the tables

## Create Telegram bot
Go to bot father and create a new bot with `/newbot` command
Disable group privacy with `/setprivacy` command

## Create a virtual environment
Follow the guide:
https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/

To activate virtual environment:
Windows `.\env\Scripts\activate`
Unix `./env/bin/python`

## Install dependencies
Run the following command:
`pip install mysql-connector-python python-dotenv python-telegram-bot`

## Set env variables
Copy .env_sample to .env and fill in the variables
If you do not have your master chat ID yet, type `/chatid` to the bot (while server is running)

## Run the server
Run the application using the command:
`py app.py`
