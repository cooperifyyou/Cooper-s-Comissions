import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
import os
from datetime import datetime, timezone, timedelta

LOG_CHANNEL_ID = 1366528013029740594
TRELLO_KEY = os.environ.get('APIKEY')
TRELLO_TOKEN = os.environ.get('TRELLOTOKEN')
TRELLO_BOARD_ID = os.environ.get('BOARDID')
TRELLO_LIST_ID = os.environ.get('LISTID')
TRELLO_LOG_ID = os.environ.get('TRELLOLOGID')
WEBHOOK_URL = "https://discord.com/api/webhooks/1376012325945086053/ig1SrrTy2JUPF6uWo4PyQXi0smpeANYGqAmEAZducDL5cmDtECBmqli5hmNSd1vPI-rZ"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree


def send_dev_webhook(action, username, actor, success, trello_response):
    """Send a developer log to the webhook."""
    embed = {
        "title": f"{action} Command Used",
        "color": 0xff0000 if action.lower() == "ban" else 0x00ff00,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {"name": "User", "value": f"`{username}`", "inline": True},
            {"name": "Action By", "value": f"`{actor}`", "inline": True},
            {"name": "Successful", "value": "Yes" if success else "No", "inline": False},
            {"name": "Trello Response", "value": f"```{trello_response}```", "inline": False}
        ]
    }
    try:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
    except Exception as e:
        print(f"Webhook send failed: {e}")


def add_user(username: str, whobanned: str, reason: str, days: int):
    """Ban a user by adding them to Trello."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    duration = "Permanent" if days == 0 else str(days)
    title_log = f"{username} [Perm Ban]" if days == 0 else f"{username} [Ban]"
    title = username

    desc_log = (
        f"**Banned by**: {whobanned}\n"
        f"**Reason**: {reason}\n"
        f"**How many Days**: {duration}\n"
        f"**Timestamp**: {timestamp}"
    )
    desc_game = (
        f"**Reason**: {reason}\n"
        f"**How many Days**: {duration}\n"
        f"**Timestamp**: {timestamp}"
    )

    url = "https://api.trello.com/1/cards"
    params_log = {'idList': TRELLO_LOG_ID, 'name': title_log, 'desc': desc_log, 'key': TRELLO_KEY, 'token': TRELLO_TOKEN}
    params_game = {'idList': TRELLO_LIST_ID, 'name': title, 'desc': desc_game, 'key': TRELLO_KEY, 'token': TRELLO_TOKEN}

    try:
        resp_log = requests.post(url, data=params_log, timeout=10)
        resp_game = requests.post(url, data=params_game, timeout=10)
        return resp_log, resp_game
    except requests.RequestException as e:
        return None, str(e)


def is_user_already_banned(username: str):
    """Check if a user is already banned."""
    url = f"https://api.trello.com/1/lists/{TRELLO_LIST_ID}/cards"
    params = {'key': TRELLO_KEY, 'token': TRELLO_TOKEN}
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        return False, resp.text
    cards = resp.json()
    for card in cards:
        if card['name'].strip().lower() == username.strip().lower():
            return True, resp.text
    return False, resp.text


@tree.command(name="ban", description="Ban a Roblox Player")
@app_commands.describe(username="Roblox Username To Ban", reason="Why you're banning them", days="Ban duration in days (0 = permanent)")
async def ban(interaction: discord.Interaction, username: str, reason: str, days: int):
    whobanned = interaction.user.name
    already_banned, trello_resp = is_user_already_banned(username)

    if already_banned:
        await interaction.response.send_message(f"**{username}** is already banned.")
        send_dev_webhook("Ban", username, whobanned, False, trello_resp)
        return

    resp_log, resp_game = add_user(username, whobanned, reason, days)
    if resp_log and resp_game and resp_log.status_code == 200 and resp_game.status_code == 200:
        await interaction.response.send_message(f"Successfully banned {username}.")
        send_dev_webhook("Ban", username, whobanned, True, f"LOG: {resp_log.text}\nGAME: {resp_game.text}")
    else:
        error_msg = f"LOG: {getattr(resp_log, 'text', resp_log)}\nGAME: {getattr(resp_game, 'text', resp_game)}"
        await interaction.response.send_message(f"Failed to ban {username}.")
        send_dev_webhook("Ban", username, whobanned, False, error_msg)


@tree.command(name="unban", description="Unban a user")
@app_commands.describe(username="Roblox username to unban", reason="Why you're unbanning them")
async def unban(interaction: discord.Interaction, username: str, reason: str):
    whounbanned = interaction.user.name
    params = {'key': TRELLO_KEY, 'token': TRELLO_TOKEN}
    get_url = f"https://api.trello.com/1/lists/{TRELLO_LIST_ID}/cards"
    resp = requests.get(get_url, params=params)

    if resp.status_code != 200:
        await interaction.response.send_message("Failed to fetch bans.")
        send_dev_webhook("Unban", username, whounbanned, False, resp.text)
        return

    cards = resp.json()
    target_card = next((c for c in cards if c["name"].strip().lower() == username.strip().lower()), None)

    if not target_card:
        await interaction.response.send_message(f"No ban found for **{username}**.")
        send_dev_webhook("Unban", username, whounbanned, False, resp.text)
        return

    delete_url = f"https://api.trello.com/1/cards/{target_card['id']}"
    del_resp = requests.delete(delete_url, params=params)

    if del_resp.status_code != 200:
        await interaction.response.send_message(f"Failed to unban {username}.")
        send_dev_webhook("Unban", username, whounbanned, False, del_resp.text)
        return

    log_title = f"{username} [Unban]"
    log_desc = (
        f"**Unbanned by**: {whounbanned}\n"
        f"**Reason**: {reason}\n"
        f"**Timestamp**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    create_params = {'idList': TRELLO_LOG_ID, 'name': log_title, 'desc': log_desc, 'key': TRELLO_KEY, 'token': TRELLO_TOKEN}
    log_resp = requests.post("https://api.trello.com/1/cards", data=create_params)

    await interaction.response.send_message(f"Successfully unbanned {username}.")
    send_dev_webhook("Unban", username, whounbanned, True, f"DELETE: {del_resp.text}\nLOG: {log_resp.text}")


@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot is online as {bot.user}")


token = os.environ.get("ERM")
bot.run(token)
