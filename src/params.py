admin_chat_id = None  # Get your user id, e.g. ask @FalconGate_Bot /get_my_id
tor_pwd = None  # None is default. If you set one up at your tor config you need to provide it here
token = ""  # Get your token by chatting with Telegram's @BotFather

if (admin_chat_id == None) or (len(token) == 0):
    raise ValueError("Admin chat id or token not set!")