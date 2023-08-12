import math
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import datetime
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Dictionary to store user-selected tokens and their intervals
user_tokens = {}


def start(update, context):
    chat_id = update.message.chat_id
    # Check if the user is a member of the channel
    bot = context.bot
    channel_id = "@DeFiSentinelXchannel"  # Replace with your channel username or ID
    if not bot.get_chat_member(channel_id, chat_id):
        # If the user is not a member, provide the channel link and ask them to join
        update.message.reply_text(
            "⚠️ To use this bot, please join our official channel: {}".format(channel_id))
        update.message.reply_text(
            "Use /joinchannel after joining the channel to gain access to the bot.")
        return

    # If the user is a member, provide the regular commands info
    commands_info = """
ℹ️ Available Commands:

/i <token> - Get token information
/add <token(s)> - Add token(s) to your list
/remove <token(s)> - Remove token(s) from your list
/interval <token> <interval> - Set the alert interval (Supported intervals: 30sec, 1min, 5min, 30min, 1hour)
/view - View all added tokens
/clear - Clear your token list
/add_multiple <token(s)> - Add multiple tokens at once
    """
    update.message.reply_text(commands_info)


def join_channel(update, context):
    chat_id = update.message.chat_id
    # Check if the user is a member of the channel
    bot = context.bot
    channel_id = "@DeFiSentinelXchannel"  # Replace with your channel username or ID
    if bot.get_chat_member(channel_id, chat_id):
        # If the user is already a member, grant them access to use the bot
        update.message.reply_text(
            "✅ You have successfully joined the official channel and can now use the bot.")
        return

    # If the user is not a member, provide the channel link and ask them to join
    update.message.reply_text(
        "⚠️ To use this bot, please join our official channel: {}".format(channel_id))


def send_to_channel(text, chat_id, group_title=None):
    bot = telegram.Bot(token=os.getenv("TELEGRAM_TOKEN"))
    channel_id = "@DeFiSentinelXchannel"  # Replace with your channel username or ID
    if chat_id < 0:  # Check if chat_id is negative (group chat)
        group_username = group_title or "Unknown Group"
        text = f"👥 Price Request In: @{group_username}\n\n{text}"
        bot.send_message(chat_id=channel_id, text=text)


DEXSCREENER_API_URL = "https://api.dexscreener.com/latest/dex/search?q="


def get_token_details(query):
    response = requests.get(DEXSCREENER_API_URL + query)
    if response.status_code != 200:
        return {}

    token_details = response.json()
    if not token_details:
        return {}

    return token_details['pairs']


def get_token_security(chain_id, addresses):
    url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}"
    params = {
        "contract_addresses": ",".join(addresses)
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return {}

    security_data = response.json()
    if not security_data:
        return {}

    return security_data


def convert_chain_id(chain_id):
    if chain_id == "ethereum":
        return 1
    elif chain_id == "bsc":
        return 56
    else:
        return None


def convert_chain_id2(chain_id):
    if chain_id == "ethereum":
        return "ether"
    elif chain_id == "bsc":
        return "bsc"
    else:
        return None


def bool_to_yes_no(value):
    if value is None:
        return "Unknown"
    return "No" if value == "0" else "Yes"


def bool_to_yes_no_emoji(value):
    return "🔴" if value == "1" else "🟢"


def handle_info(update, context):
    chat_id = update.message.chat_id
    query = update.message.text.split(" ")[1]
    token_details_list = get_token_details(query)

    if not token_details_list:
        update.message.reply_text("⚠️ Token not found.")
        return

    token_details = token_details_list[0]

    chainId = token_details["chainId"]
    baseTokenAddress = token_details["baseToken"]["address"]

    security_data = get_token_security(
        convert_chain_id(chainId), [baseTokenAddress])

    # Calculate the number of seconds since the token was created
    created_at_date = token_details["pairCreatedAt"]
    created_at_timestamp = int(created_at_date)  # Convert to Unix timestamp
    now_timestamp = int(datetime.datetime.utcnow().timestamp())
    seconds_ago = now_timestamp - created_at_timestamp

    # Convert seconds to hours, minutes, and days
    minutes_ago = seconds_ago / 60
    hours_ago = minutes_ago / 60
    days_ago = math.floor(hours_ago / 24)

    # Calculate remaining hours and minutes
    remaining_hours = math.floor(hours_ago % 24)
    remaining_minutes = math.floor(minutes_ago % 60)

    # Get the first 6 and last 6 characters of the Creator Address
    creator_address = security_data["result"][baseTokenAddress.lower(
    )]["creator_address"]
    truncated_creator_address = creator_address[:6] + \
        "..." + creator_address[-6:]

    # Determine if the price change is positive or negative
    price_change_emoji_m5 = "📈" if token_details["priceChange"]["m5"] < 0 else "📉"
    price_change_emoji_h1 = "📈" if token_details["priceChange"]["h1"] < 0 else "📉"
    price_change_emoji_h24 = "📈" if token_details["priceChange"]["h24"] < 0 else "📉"
    group_title = update.message.chat.title

    # Get LP Locked status
    security_info = security_data["result"][baseTokenAddress.lower(
    )] if security_data["result"] else None
    lp_locked = security_info["lp_holders"][0]["is_locked"] if security_info and security_info["lp_holders"][0] else None

    text = f"""
1️⃣ Token Information

📌 Token Name: {token_details["baseToken"]["name"]} ({token_details["baseToken"]["symbol"]})
⚡ Network: {chainId}
💵 Price (USD): ${token_details["priceUsd"]}
👥 Holders: {security_data["result"][baseTokenAddress.lower()]["holder_count"]}
🔖 Tax: {security_data["result"][baseTokenAddress.lower()]["buy_tax"]}% buy, {security_data["result"][baseTokenAddress.lower()]["sell_tax"]}% sell
{price_change_emoji_m5} Price Change (5min): {token_details["priceChange"]["m5"]}%
{price_change_emoji_h1} Price Change (1h): {token_details["priceChange"]["h1"]}%
{price_change_emoji_h24} Price Change (24h): {token_details["priceChange"]["h24"]}%
📊 Volume (24h): ${token_details["volume"]["h24"]}
💦 Liquidity (USD): ${token_details["liquidity"]["usd"]}
💎 MarketCap (FDV): ${token_details["fdv"]}

2️⃣ Transactions

    5m: {token_details["txns"]["m5"]["buys"]} buys, {token_details["txns"]["m5"]["sells"]} sells
    1h: {token_details["txns"]["h1"]["buys"]} buys, {token_details["txns"]["h1"]["sells"]} sells
    6h: {token_details["txns"]["h6"]["buys"]} buys, {token_details["txns"]["h6"]["sells"]} sells
    24h: {token_details["txns"]["h24"]["buys"]} buys, {token_details["txns"]["h24"]["sells"]} sells

3️⃣ Security Check

    Anti_whale Modifiable: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["anti_whale_modifiable"])}
    Reclaim Ownership: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["can_take_back_ownership"])}
    Cannot Buy: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["cannot_buy"])}
    Cannot Sell All: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["cannot_sell_all"])}
    Anti_whale: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["is_anti_whale"])}
    Blacklisted: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["is_blacklisted"])}
    Whitelisted: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["is_whitelisted"])}
    Honeypot: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["is_honeypot"])} {bool_to_yes_no_emoji(security_data["result"][baseTokenAddress.lower()]["is_honeypot"])} 
    Mintable: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["is_mintable"])}
    Proxy: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["is_proxy"])}
    Trading Cooldown: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["trading_cooldown"])}
    LP Locked: {bool_to_yes_no(lp_locked)}
    Creator Address: {truncated_creator_address}
    Creator Percent: {security_data["result"][baseTokenAddress.lower()]["creator_percent"]}%
    Created: {days_ago} days, {remaining_hours} hours, and {remaining_minutes} minutes ago
    """

    update.message.reply_text(text)
    send_to_channel(text, chat_id, group_title)


def add_token(update, context):
    chat_id = update.message.chat_id
    tokens = context.args
    if not tokens:
        update.message.reply_text(
            "⚠️ Please provide at least one token symbol.")
        return

    user_tokens[chat_id] = user_tokens.get(chat_id, [])  # Initialize as a list
    for token in tokens:
        user_tokens[chat_id].append(token.upper())  # Append to the list

    update.message.reply_text(f"✅ Added tokens: {', '.join(tokens)}")


def remove_token(update, context):
    chat_id = update.message.chat_id
    tokens = context.args
    if not tokens:
        update.message.reply_text(
            "⚠️ Please provide at least one token symbol.")
        return

    user_tokens[chat_id] = user_tokens.get(chat_id, [])  # Initialize as a list
    for token in tokens:
        token = token.upper()
        if token in user_tokens[chat_id]:
            # Remove the token from the list
            user_tokens[chat_id].remove(token)

    update.message.reply_text(f"✅ Removed tokens: {', '.join(tokens)}")


def set_interval(update, context):
    chat_id = update.message.chat_id
    args = context.args
    if len(args) < 2:
        update.message.reply_text(
            "⚠️ Please provide both token and interval. Example: /interval <token> <interval>")
        return

    token = args[0].upper()
    interval = args[1]
    intervals = {'30sec': 30, '1min': 60, '5min': 5 * 60,
                 '30min': 30 * 60, '1hour': 60 * 60}

    if interval not in intervals:
        update.message.reply_text(
            "⚠️ Invalid interval. Supported intervals: 30sec, 1min, 5min, 30min, 1hour.")
        return

    user_tokens[chat_id] = user_tokens.get(
        chat_id, {})  # Initialize as a dictionary
    user_tokens[chat_id][token] = interval

    update.message.reply_text(
        f"✅ Alert interval set to {interval} for token {token}.")

    # Stop the previous timer thread (if any) and start a new one with the updated intervals
    if hasattr(context, 'job_queue'):
        current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
        for job in current_jobs:
            job.schedule_removal()

    # Start a new thread to send periodic alerts for this chat_id
    for token, interval in user_tokens[chat_id].items():
        interval_seconds = intervals[interval]
        context.job_queue.run_repeating(send_token_alerts, interval_seconds,
                                        context=(chat_id, token), name=str(chat_id))


def send_token_alerts(context):
    chat_id, token = context.job.context
    # Now you can access the 'update' and 'context' objects directly from the context argument
    update = context.job.context[0]
    # Rest of the function remains unchanged

    # Get token details (it's a list, so we need to handle each item in the list)
    token_details_list = get_token_details(token)
    if not token_details_list:
        update.message.reply_text("⚠️ Token not found.")
        return

    for token_details in token_details_list:
        chainId = token_details["chainId"]
        baseTokenAddress = token_details["baseToken"]["address"]

        # Check if chainId is valid before calling token_security
        if convert_chain_id(chainId) is None:
            update.message.reply_text("⚠️ Invalid chain ID.")
            return
        security_data = get_token_security(
            convert_chain_id(chainId), [baseTokenAddress])

        # Calculate the number of seconds since the token was created
        created_at_date = token_details["pairCreatedAt"]
        # Convert to Unix timestamp
        created_at_timestamp = int(created_at_date)
        now_timestamp = int(datetime.datetime.utcnow().timestamp())
        seconds_ago = now_timestamp - created_at_timestamp

        # Convert seconds to hours, minutes, and days
        minutes_ago = seconds_ago / 60
        hours_ago = minutes_ago / 60
        days_ago = math.floor(hours_ago / 24)

        # Calculate remaining hours and minutes
        remaining_hours = math.floor(hours_ago % 24)
        remaining_minutes = math.floor(minutes_ago % 60)

        # Determine if the price change is positive or negative
        price_change_emoji_m5 = "📈" if token_details["priceChange"]["m5"] < 0 else "📉"
        price_change_emoji_h1 = "📈" if token_details["priceChange"]["h1"] < 0 else "📉"
        price_change_emoji_h24 = "📈" if token_details["priceChange"]["h24"] < 0 else "📉"

        text = f"""
1️⃣ Token Information

📌 Token Name: {token_details["baseToken"]["name"]} ({token_details["baseToken"]["symbol"]})
⚡ Network: {chainId}
💵 Price (USD): ${token_details["priceUsd"]}
👥 Holders: {security_data["result"][baseTokenAddress.lower()]["holder_count"]}
🔖 Tax: {security_data["result"][baseTokenAddress.lower()]["buy_tax"]}% buy, {security_data["result"][baseTokenAddress.lower()]["sell_tax"]}% sell
{price_change_emoji_m5} Price Change (5min): {token_details["priceChange"]["m5"]}%
{price_change_emoji_h1} Price Change (1h): {token_details["priceChange"]["h1"]}%
{price_change_emoji_h24} Price Change (24h): {token_details["priceChange"]["h24"]}%
📊 Volume (24h): ${token_details["volume"]["h24"]}
💦 Liquidity (USD): ${token_details["liquidity"]["usd"]}
💎 MarketCap (FDV): ${token_details["fdv"]}
🍯 Honeypot: {bool_to_yes_no(security_data["result"][baseTokenAddress.lower()]["is_honeypot"])} {bool_to_yes_no_emoji(security_data["result"][baseTokenAddress.lower()]["is_honeypot"])} 
⏰ Created: {days_ago} days ago

2️⃣ Transactions

    5m: {token_details["txns"]["m5"]["buys"]} buys, {token_details["txns"]["m5"]["sells"]} sells
    1h: {token_details["txns"]["h1"]["buys"]} buys, {token_details["txns"]["h1"]["sells"]} sells
    6h: {token_details["txns"]["h6"]["buys"]} buys, {token_details["txns"]["h6"]["sells"]} sells
    24h: {token_details["txns"]["h24"]["buys"]} buys, {token_details["txns"]["h24"]["sells"]} sells

        """

        context.bot.send_message(chat_id=chat_id, text=text)


def view_tokens(update, context):
    chat_id = update.message.chat_id
    tokens = user_tokens.get(chat_id, [])
    if not tokens:
        update.message.reply_text("⚠️ You have not added any tokens.")
    else:
        token_list = "\n".join(tokens)
        update.message.reply_text(f"✅ Your added tokens:\n\n{token_list}")


def clear_tokens(update, context):
    chat_id = update.message.chat_id
    if chat_id in user_tokens:
        user_tokens[chat_id] = []
    update.message.reply_text("✅ Your token list has been cleared.")


def add_multiple_tokens(update, context):
    chat_id = update.message.chat_id
    tokens = context.args
    if not tokens:
        update.message.reply_text(
            "⚠️ Please provide at least one token symbol.")
        return

    user_tokens[chat_id] = user_tokens.get(chat_id, {})
    for token in tokens:
        user_tokens[chat_id].append(token.upper())

    token_list = "\n".join(tokens)
    update.message.reply_text(f"✅ Added tokens:\n\n{token_list}")


def main():
    updater = Updater(token=os.getenv("TELEGRAM_TOKEN"))
    start_handler = CommandHandler("start", start)
    join_channel_handler = CommandHandler("joinchannel", join_channel)
    info_handler = CommandHandler("i", handle_info)
    add_handler = CommandHandler("add", add_token, pass_args=True)
    remove_handler = CommandHandler("remove", remove_token, pass_args=True)
    interval_handler = CommandHandler("interval", set_interval, pass_args=True)
    view_handler = CommandHandler("view", view_tokens)
    clear_handler = CommandHandler("clear", clear_tokens)
    add_multiple_handler = CommandHandler(
        "add_multiple", add_multiple_tokens, pass_args=True)

    updater.dispatcher.add_handler(start_handler)
    updater.dispatcher.add_handler(join_channel_handler)
    updater.dispatcher.add_handler(info_handler)
    updater.dispatcher.add_handler(add_handler)
    updater.dispatcher.add_handler(remove_handler)
    updater.dispatcher.add_handler(interval_handler)
    updater.dispatcher.add_handler(view_handler)
    updater.dispatcher.add_handler(clear_handler)
    updater.dispatcher.add_handler(add_multiple_handler)

    updater.start_polling()

    updater.idle()


if __name__ == "__main__":
    main()
