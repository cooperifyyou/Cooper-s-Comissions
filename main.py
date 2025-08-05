## Discord Bot With Trello & Roblox Integration ##

import discord
from discord import app_commands
from discord.ext import commands
import requests
import os
from datetime import datetime

# configurationnnnn #
LOG_CHANNEL_ID = os.environ.get('LOGCHANNELID')  # replace this with your channel you want to have the logs in
TRELLO_KEY = os.environ.get('APIKEY')  # this is your trello API key
TRELLO_TOKEN = os.environ.get('TRELLOTOKEN')  # this is your trello token
TRELLO_BOARD_ID = os.environ.get('BOARDID')  # this is your board id
TRELLO_LIST_ID = os.environ.get('LISTID')  # ths is the game integration list id [Game Integration]
TRELLO_LOG_ID = os.environ.get('TRELLOLOGID') # this is the admin log list id,

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

def add_user(username: str, whobanned: str, reason: str, days: int):
    title = username
    duration = "Permanent" if days == 0 else f"{days} days"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    description = (
        f"**Banned by**: {whobanned}\n"
        f"**Reason**: {reason}\n"
        f"**How Long**: {duration}\n"
        f"**Timestamp**: {timestamp}"
    )

    url = "https://api.trello.com/1/cards"


    params_log = {
        'idList': TRELLO_LOG_ID,
        'name': title,
        'desc': description,
        'key': TRELLO_KEY,
        'token': TRELLO_TOKEN
    }

    params_game = {
        'idList': TRELLO_LIST_ID,
        'name': title,
        'desc': reason,  # only put the reason here for the game stuff
        'key': TRELLO_KEY,
        'token': TRELLO_TOKEN
    }

    response_log = requests.post(url, data=params_log)
    response_game = requests.post(url, data=params_game)

    print("log responsee", response_log.status_code, response_log.text)
    print("game responsee", response_game.status_code, response_game.text)

    return response_log.status_code == 200 and response_game.status_code == 200

def is_user_already_banned(username: str) -> bool:
    url = f"https://api.trello.com/1/lists/{TRELLO_LIST_ID}/cards"
    params = {
        'key': TRELLO_KEY,
        'token': TRELLO_TOKEN
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        print("Failed to fetch Trello cards:", response.text)
        return False  

    cards = response.json()
    for card in cards:
        if card['name'].strip().lower() == username.strip().lower():
            return True
    return False


## ban command
@tree.command(name="ban", description="Ban a Roblox Player From Your Game")
@app_commands.describe(
    username="Roblox Username To Ban", reason="Why you're banning them", days="Ban duration in days (0 = permanent)"
)
async def ban(interaction: discord.Interaction, username: str, reason: str, days: int):
    whobanned = interaction.user.name
    if is_user_already_banned(username):
     await interaction.response.send_message(f"**{username}** is already banned.")
     return 

    if add_user(username, whobanned, reason, days):
        duration_text = "Permanent" if days == 0 else f"{days} days"
        await interaction.response.send_message(
            f"✅ Successfully banned **{username}**."
        )

        embed = discord.Embed(
            title="Ban Command Used",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Banned User", value=f"`{username}`", inline=True)
        embed.add_field(name="Banned By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="How Long", value=duration_text, inline=True)

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=embed)
        else:
            print("the log channel was not found")

    else:
        await interaction.response.send_message(
            f"❌ Failed to ban **{username}**"
        )

@tree.command(name="clearbans", description="Clear all bans from the Trello list")
async def clearbans(interaction: discord.Interaction):
    url = f"https://api.trello.com/1/lists/{TRELLO_LIST_ID}/cards"
    params = {
        'key': TRELLO_KEY,
        'token': TRELLO_TOKEN
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        await interaction.response.send_message("❌ Failed to fetch cards.")
        return

    cards = response.json()
    deleted = 0

    for card in cards:
        delete_url = f"https://api.trello.com/1/cards/{card['id']}"
        delete_resp = requests.delete(delete_url, params=params)
        if delete_resp.status_code == 200:
            deleted += 1

    await interaction.response.send_message(f"🗑️ Cleared {deleted} ban(s) from the list.")

# unban cmd
@tree.command(name="unban", description="Unban a user")
@app_commands.describe(username="Roblox username to unban", reason="Why you're unbanning them")
async def unban(interaction: discord.Interaction, username: str, reason: str):
    url = f"https://api.trello.com/1/lists/{TRELLO_LIST_ID}/cards"
    params = {
        'key': TRELLO_KEY,
        'token': TRELLO_TOKEN
    }

    response = requests.get(url, params=params)
    cards = response.json() if response.status_code == 200 else []

    target_card = None
    for card in cards:
        if card["name"].strip().lower() == username.strip().lower():
            target_card = card
            break

    if not target_card:
        await interaction.response.send_message(f"❌ No ban found for **{username}**.")
        return

    delete_url = f"https://api.trello.com/1/cards/{target_card['id']}"
    delete_response = requests.delete(delete_url, params=params)

    if delete_response.status_code == 200:
        await interaction.response.send_message(f"✅ Sucessfully unbanned **{username}**")

        embed = discord.Embed(
            title="Unban Command Used",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Unbanned User", value=f"`{username}`", inline=True)
        embed.add_field(name="Unbanned By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=embed)
        else:
            print("the log channel was not found")
    else:
        await interaction.response.send_message(f"❌ Failed to unban **{username}**.")

token = os.environ.get("ERM")

@bot.event
async def on_ready():
    await tree.sync()
    print(f"bot is working and is online as {bot.user}")

bot.run(token)

##hi sigmas##
