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

def send_webhook_log(title, description, color=0x00ff00):
    try:
        data = {
            "embeds": [
                {
                    "title": title,
                    "description": description,
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
        }
        requests.post(WEBHOOK_URL, json=data, timeout=10)
    except Exception as e:
        print(f"Webhook send failed: {e}")

def add_user(username: str, whobanned: str, reason: str, days: int):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if days == 0:
        duration = "Permanent"
        title_log = f"{username} [Perm Ban]"
    else:
        duration = str(days)
        title_log = f"{username} [Ban]"
    title = username
    description_log = (
        f"**Banned by**: {whobanned}\n"
        f"**Reason**: {reason}\n"
        f"**How many Days**: {duration}\n"
        f"**Timestamp**: {timestamp}"
    )
    description_game = (
        f"**Reason**: {reason}\n"
        f"**How many Days**: {duration}\n"
        f"**Timestamp**: {timestamp}"
    )
    url = "https://api.trello.com/1/cards"
    params_log = {
        'idList': TRELLO_LOG_ID,
        'name': title_log,
        'desc': description_log,
        'key': TRELLO_KEY,
        'token': TRELLO_TOKEN
    }
    params_game = {
        'idList': TRELLO_LIST_ID,
        'name': title,
        'desc': description_game,
        'key': TRELLO_KEY,
        'token': TRELLO_TOKEN
    }
    try:
        response_log = requests.post(url, data=params_log, timeout=10)
        response_game = requests.post(url, data=params_game, timeout=10)
    except requests.RequestException as e:
        print("failed to create trello card:", e)
        return False
    if response_log.status_code == 200 and response_game.status_code == 200:
        return True
    else:
        print("log response:", response_log.status_code, response_log.text)
        print("game response:", response_game.status_code, response_game.text)
        return False

def is_user_already_banned(username: str) -> bool:
    url = f"https://api.trello.com/1/lists/{TRELLO_LIST_ID}/cards"
    params = {
        'key': TRELLO_KEY,
        'token': TRELLO_TOKEN
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print("failed to fetch the dang trello cards", response.text)
        return False
    cards = response.json()
    for card in cards:
        if card['name'].strip().lower() == username.strip().lower():
            return True
    return False

@tasks.loop(minutes=5)
async def check_expired_bans():
    params = {'key': TRELLO_KEY, 'token': TRELLO_TOKEN}
    url = f"https://api.trello.com/1/lists/{TRELLO_LIST_ID}/cards"
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return
    now = datetime.now(timezone.utc)
    cards = response.json()
    for card in cards:
        desc = card.get('desc', '')
        if "Permanent" in desc or not desc:
            continue
        ban_days = None
        timestamp_str = None
        for line in desc.splitlines():
            if line.lower().startswith("**how many days**") or line.lower().startswith("ban length"):
                try:
                    ban_days = int(line.split(":", 1)[1].strip())
                except Exception:
                    ban_days = 0
            if line.lower().startswith("**timestamp**"):
                try:
                    timestamp_str = line.split(":", 1)[1].strip()
                except Exception:
                    timestamp_str = None
        if ban_days is None or not timestamp_str:
            continue
        try:
            ban_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if now - ban_time >= timedelta(days=ban_days):
            delete_url = f"https://api.trello.com/1/cards/{card['id']}"
            requests.delete(delete_url, params=params)
            log_title = f"{card['name']} [Auto Unban]"
            log_desc = (
                f"**Unbanned by**: Auto Unban\n"
                f"**Reason**: Ban duration expired\n"
                f"**Banned At**: {ban_time.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"**Unbanned At**: {now.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"**How many Days**: {ban_days}"
            )
            log_url = "https://api.trello.com/1/cards"
            create_params = {
                'idList': TRELLO_LOG_ID,
                'name': log_title,
                'desc': log_desc,
                'key': TRELLO_KEY,
                'token': TRELLO_TOKEN
            }
            requests.post(log_url, data=create_params)

@tree.command(name="ban", description="Ban a Roblox Player")
@app_commands.describe(username="Roblox Username To Ban", reason="Why you're banning them", days="Ban duration in days (0 = permanent)")
async def ban(interaction: discord.Interaction, username: str, reason: str, days: int):
    whobanned = interaction.user.name
    send_webhook_log("Command Executed", f"**/ban** by {interaction.user} | Target: {username} | Reason: {reason} | Days: {days}", 0xff0000)
    if is_user_already_banned(username):
        await interaction.response.send_message(f"**{username}** is already banned.")
        return
    if add_user(username, whobanned, reason, days):
        duration_text = "Permanent" if days == 0 else str(days)
        await interaction.response.send_message(f"Successfully banned {username}.")
        embed = discord.Embed(title="Ban Command Used", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Banned User", value=f"`{username}`", inline=True)
        embed.add_field(name="Banned By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="How many Days", value=duration_text, inline=True)
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=embed)
    else:
        await interaction.response.send_message(f"Failed to ban {username}.")

@tree.command(name="unban", description="Unban a user")
@app_commands.describe(username="Roblox username to unban", reason="Why you're unbanning them")
async def unban(interaction: discord.Interaction, username: str, reason: str):
    send_webhook_log("Command Executed", f"**/unban** by {interaction.user} | Target: {username} | Reason: {reason}", 0x00ff00)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    get_url = f"https://api.trello.com/1/lists/{TRELLO_LIST_ID}/cards"
    params = {'key': TRELLO_KEY, 'token': TRELLO_TOKEN}
    response = requests.get(get_url, params=params)
    cards = response.json() if response.status_code == 200 else []
    target_card = None
    for card in cards:
        if card["name"].strip().lower() == username.strip().lower():
            target_card = card
            break
    if not target_card:
        await interaction.response.send_message(f"No ban was found for **{username}**.")
        return
    delete_url = f"https://api.trello.com/1/cards/{target_card['id']}"
    delete_response = requests.delete(delete_url, params=params)
    if delete_response.status_code != 200:
        await interaction.response.send_message(f"Failed to unban {username}.")
        return
    log_title = f"{username} [Unban]"
    log_desc = (
        f"**Unbanned by**: {interaction.user.name}\n"
        f"**Reason**: {reason}\n"
        f"**Timestamp**: {timestamp}"
    )
    add_url = "https://api.trello.com/1/cards"
    create_params = {
        'idList': TRELLO_LOG_ID,
        'name': log_title,
        'desc': log_desc,
        'key': TRELLO_KEY,
        'token': TRELLO_TOKEN
    }
    requests.post(add_url, data=create_params)
    await interaction.response.send_message(f"Successfully unbanned {username}.")
    embed = discord.Embed(title="Unban Command Used", color=discord.Color.green(), timestamp=discord.utils.utcnow())
    embed.add_field(name="Unbanned User", value=f"`{username}`", inline=True)
    embed.add_field(name="Unbanned By", value=interaction.user.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(embed=embed)

@bot.event
async def on_ready():
    await tree.sync()
    check_expired_bans.start()
    send_webhook_log("Bot Status", f"{bot.user} is now online.", 0x0000ff)
    print(f"bot is working and is online as {bot.user}")

@bot.event
async def on_command_error(ctx, error):
    send_webhook_log("Error", f"Error: {error}", 0xff0000)
    print(f"Error: {error}")

token = os.environ.get("ERM")
bot.run(token)
