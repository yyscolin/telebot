# Telebot v1.0
Telebot is a simple project which forwards all Telegram messages sent to a bot into a chat (i.e. master chat) and vice-versa.

## Create database table
```
create table updates (
    chat_id int unsigned not null,
    message_id int unsigned not null,
    timestamp timestamp not null,
    payload varchar(1200) not null,
    primary key (chat_id, message_id)
)
```

Grant INSERT and SELECT privileges to the table

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
