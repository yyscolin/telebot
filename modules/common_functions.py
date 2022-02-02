import os


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


def get_rate_limit_default():
    messages_max = int(os.getenv("rate_limit_max") or 0)
    timespan = int(os.getenv("rate_limit_timespan") or 0)
    is_unlimited = messages_max == 0 or timespan == 0
    return False if is_unlimited else {
        "messages_max": messages_max,
        "unread_messages": [],
        "timespan": timespan,
    }
