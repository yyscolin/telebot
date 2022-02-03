# Telebot v1.0
Telebot is a simple project which forwards all Telegram messages sent to a bot into a chat (i.e. master chat) and vice-versa.

## Create database tables
```
create table agents (
    chat_id int not null primary key,
    is_group boolean not null default false,
    name varchar(120) not null
);

create table updates (
    update_id int not null primary key,
    payload varchar(1200) not null
);

create table messages (
    chat_id int not null,
    message_id int not null,
    reply_chat_id int,
    reply_message_id int,
    timestamp timestamp not null,
    primary key (chat_id, message_id)
);

create table rate_limits (
    chat_id int not null primary key,
    max_messages int not null default 0,
    timespan int not null default 0
);

create table forwarded_messages (
    from_chat_id int not null,
    from_message_id int not null,
    to_chat_id int not null,
    to_message_id int not null,
    primary key (to_chat_id, to_message_id)
);
```

Grant SELECT, INSERT, UPDATE, DELETE privileges to the tables

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
`pip install python-dotenv python-telegram-bot`
For webhook strategy only (not needed for polling strategy):
`pip install flask`

For MySql:
`pip install mysql-connector-python`
For Postgresql:
`pip install psycopg2`

## Running the server locally
- Copy .env_sample to .env and fill in the variables
- Run the application using either of the commands below:
`py polling.py`
`py webhook.py`

## Deployment to Heroku
- Install Heroku CLI from their website:
`https://devcenter.heroku.com/articles/heroku-command-line`
- Login via CLI (remember to add executable folder to PATH):
`heroku login`
- Add the Heroku remote:
`heroku git:remote -a <project_name>`
- Create `Procfile` file with either of the following as its content:
`web: gunicorn app:polling`
`web: gunicorn app:webhook`
- Install the Heroku dependency:
`pip install gunicorn`
- Define libraries used for Heroku:
`pip freeze > requirements.txt`
- Create a seperate branch for Heroku and commit the two created files
- Push to Heroku:
`git push heroku master`

## Learn your commands
### Register as chat agent
Type `/setagent` to the chat bot and enter the agent password when prompted
