import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from dexscreener import DexscreenerClient
from goplus.token import Token
import datetime
import threading
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Dictionary to store user-selected tokens and their intervals
user_tokens = {}


def start(update, context):
    commands_info = """
ℹ️ Available Commands:

/i <token> - Get token information
/add <token(s)> - Add token(s) to your list
/remove <token(s)> - Remove token(s) from your list
/interval <interval> - Set the alert interval (Supported intervals: 30sec, 1min, 5min, 30min, 1hour)
/view - View all added tokens
/clear - Clear your token list
/add_multiple <token(s)> - Add multiple tokens at once
    """
    update.message.reply_text(commands_info)


def get_token_details(query):
    client = DexscreenerClient()
    token_details = client.search_pairs(query)
    return token_details[0]


def convert_chain_id(chain_id):
    if chain_id == "ethereum":
        return 1
    elif chain_id == "bsc":
        return 56
    else:
        return None


def bool_to_yes_no(value):
    if value == "0":
        return "No"
    else:
        return "Yes"


def handle_info(update, context):
    query = update.message.text.split(" ")[1]
    token_details = get_token_details(query)
    chainId = token_details.chain_id
    baseTokenAddress = token_details.base_token.address
    security = Token().token_security(
        chain_id=convert_chain_id(chainId), addresses=[baseTokenAddress])
    # Calculate the number of days since the token was created
    created_at_date = token_details.pair_created_at
    created_at_string = created_at_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    days_ago = (datetime.datetime.utcnow() - created_at_date).days

    # Get the first 6 and last 6 characters of the Creator Address
    creator_address = security.result[baseTokenAddress.lower()].creator_address
    truncated_creator_address = creator_address[:6] + \
        "..." + creator_address[-6:]

    text = f"""
1️⃣ Token Information

📌 Token Name: {token_details.base_token.name} ({token_details.base_token.symbol})
⚡ Network: {chainId}
💵 Price (USD): ${token_details.price_usd}
👥 Holders: {security.result[baseTokenAddress.lower()].holder_count}
🔖 Tax: {security.result[baseTokenAddress.lower()].buy_tax}% buy, {security.result[baseTokenAddress.lower()].sell_tax}% sell
📈 Price Change (24h): {token_details.price_change.h24}%
📊 Volume (24h): ${token_details.volume.h24}
💦 Liquidity (USD): ${token_details.liquidity.usd}
💎 MarketCap (FDV): ${token_details.fdv}

2️⃣ Transactions

    5m: {token_details.transactions.m5.buys} buys, {token_details.transactions.m5.sells} sells
    1h: {token_details.transactions.h1.buys} buys, {token_details.transactions.h1.sells} sells
    6h: {token_details.transactions.h6.buys} buys, {token_details.transactions.h6.sells} sells
    24h: {token_details.transactions.h24.buys} buys, {token_details.transactions.h24.sells} sells

3️⃣ Security Check

    Anti_whale Modifiable: {bool_to_yes_no(security.result[baseTokenAddress.lower()].anti_whale_modifiable)}
    Reclaim Ownership: {bool_to_yes_no(security.result[baseTokenAddress.lower()].can_take_back_ownership)}
    Cannot Buy: {bool_to_yes_no(security.result[baseTokenAddress.lower()].cannot_buy)}
    Cannot Sell All: {bool_to_yes_no(security.result[baseTokenAddress.lower()].cannot_sell_all)}
    Anti_whale: {bool_to_yes_no(security.result[baseTokenAddress.lower()].is_anti_whale)}
    Blacklisted: {bool_to_yes_no(security.result[baseTokenAddress.lower()].is_blacklisted)}
    Whitelisted: {bool_to_yes_no(security.result[baseTokenAddress.lower()].is_whitelisted)}
    Honeypot: {bool_to_yes_no(security.result[baseTokenAddress.lower()].is_honeypot)}
    Mintable: {bool_to_yes_no(security.result[baseTokenAddress.lower()].is_mintable)}
    Proxy: {bool_to_yes_no(security.result[baseTokenAddress.lower()].is_proxy)}
    Trading Cooldown: {bool_to_yes_no(security.result[baseTokenAddress.lower()].trading_cooldown)}
    LP Locked: {bool_to_yes_no(security.result[baseTokenAddress.lower()].lp_holders[0].is_locked)}

    Creator Address: {truncated_creator_address}
    Creator Percent: {security.result[baseTokenAddress.lower()].creator_percent}%

    Created: {days_ago} days ago

    """

    update.message.reply_text(text)


def add_token(update, context):
    chat_id = update.message.chat_id
    tokens = context.args
    if not tokens:
        update.message.reply_text(
            "⚠️ Please provide at least one token symbol.")
        return

    user_tokens[chat_id] = user_tokens.get(chat_id, [])
    for token in tokens:
        user_tokens[chat_id].append(token.upper())

    update.message.reply_text(f"✅ Added tokens: {', '.join(tokens)}")


def remove_token(update, context):
    chat_id = update.message.chat_id
    tokens = context.args
    if not tokens:
        update.message.reply_text(
            "⚠️ Please provide at least one token symbol.")
        return

    user_tokens[chat_id] = user_tokens.get(chat_id, [])
    for token in tokens:
        token = token.upper()
        if token in user_tokens[chat_id]:
            user_tokens[chat_id].remove(token)

    update.message.reply_text(f"✅ Removed tokens: {', '.join(tokens)}")


def set_interval(update, context):
    chat_id = update.message.chat_id
    interval = context.args[0]
    intervals = {'30sec': 30, '1min': 60, '5min': 5 * 60,
                 '30min': 30 * 60, '1hour': 60 * 60}

    if interval not in intervals:
        update.message.reply_text(
            "⚠️ Invalid interval. Supported intervals: 30sec, 1min, 5min, 30min, 1hour.")
        return

    user_tokens[chat_id] = user_tokens.get(chat_id, [])
    user_tokens[chat_id] = [t.upper() for t in user_tokens[chat_id]]
    update.message.reply_text(
        f"✅ Alert interval set to {interval}. You will receive alerts for tokens: {', '.join(user_tokens[chat_id])}.")

    # Stop the previous timer thread (if any) and start a new one with the updated interval
    if hasattr(context, 'job_queue'):
        current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
        for job in current_jobs:
            job.schedule_removal()

    # Start a new thread to send periodic alerts for this chat_id
    interval_seconds = intervals[interval]
    context.job_queue.run_repeating(send_token_alerts, interval_seconds,
                                    context=(chat_id, interval_seconds), name=str(chat_id))


def send_token_alerts(context):
    chat_id, interval_seconds = context.job.context
    for token in user_tokens.get(chat_id, []):
        token_details = get_token_details(token)
        chainId = token_details.chain_id
        baseTokenAddress = token_details.base_token.address
        security = Token().token_security(
            chain_id=convert_chain_id(chainId), addresses=[baseTokenAddress])
        # Calculate the number of days since the token was created
        created_at_date = token_details.pair_created_at
        created_at_string = created_at_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        days_ago = (datetime.datetime.utcnow() - created_at_date).days

        text = f"""
1️⃣ Token Information

📌 Token Name: {token_details.base_token.name} ({token_details.base_token.symbol})
⚡ Network: {chainId}
💵 Price (USD): ${token_details.price_usd}
👥 Holders: {security.result[baseTokenAddress.lower()].holder_count}
🔖 Tax: {security.result[baseTokenAddress.lower()].buy_tax}% buy, {security.result[baseTokenAddress.lower()].sell_tax}% sell
📈 Price Change (24h): {token_details.price_change.h24}%
📊 Volume (24h): ${token_details.volume.h24}
💦 Liquidity (USD): ${token_details.liquidity.usd}
💎 MarketCap (FDV): ${token_details.fdv}

2️⃣ Transactions

    5m: {token_details.transactions.m5.buys} buys, {token_details.transactions.m5.sells} sells
    1h: {token_details.transactions.h1.buys} buys, {token_details.transactions.h1.sells} sells
    6h: {token_details.transactions.h6.buys} buys, {token_details.transactions.h6.sells} sells
    24h: {token_details.transactions.h24.buys} buys, {token_details.transactions.h24.sells} sells

3️⃣ Security Check
       
    Honeypot: {bool_to_yes_no(security.result[baseTokenAddress.lower()].is_honeypot)}
    Created: {days_ago} days ago
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

    user_tokens[chat_id] = user_tokens.get(chat_id, [])
    for token in tokens:
        user_tokens[chat_id].append(token.upper())

    token_list = "\n".join(tokens)
    update.message.reply_text(f"✅ Added tokens:\n\n{token_list}")


def main():
    updater = Updater(token=os.getenv("TELEGRAM_TOKEN"))
    start_handler = CommandHandler("start", start)
    info_handler = CommandHandler("i", handle_info)
    add_handler = CommandHandler("add", add_token, pass_args=True)
    remove_handler = CommandHandler("remove", remove_token, pass_args=True)
    interval_handler = CommandHandler("interval", set_interval, pass_args=True)
    view_handler = CommandHandler("view", view_tokens)
    clear_handler = CommandHandler("clear", clear_tokens)
    add_multiple_handler = CommandHandler(
        "add_multiple", add_multiple_tokens, pass_args=True)

    updater.dispatcher.add_handler(start_handler)
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
