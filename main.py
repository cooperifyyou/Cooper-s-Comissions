import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
import os
from datetime import datetime, timezone, timedelta

LOG_CHANNEL_ID = os.environ.get('LOGCHANNELID')
TRELLO_KEY = os.environ.get('APIKEY')
TRELLO_TOKEN = os.environ.get('TRELLOTOKEN')
TRELLO_BOARD_ID = os.environ.get('BOARDID')
TRELLO_LIST_ID = os.environ.get('LISTID')
TRELLO_LOG_ID = os.environ.get('TRELLOLOGID')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

def add_user(username: str, whobanned: str, reason: str, days: int):
    title = username
    title_log = f"{username} [BAN]"
    duration = "Permanent" if days == 0 else f"{days} days"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    description_log = (
        f"**Banned by**: {whobanned}\n"
        f"**Reason**: {reason}\n"
        f"**How Long**: {duration}\n"
        f"**Timestamp**: {timestamp}"
    )

    description_game = (
        f"**Reason**: {reason}\n"
        f"**How Long**: {duration}\n"
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
        print("Error creating Trello card:", e)
        return False

    if response_log.status_code == 200 and response_game.status_code == 200:
        return True
    else:
        print("Log response:", response_log.status_code, response_log.text)
        print("Game response:", response_game.status_code, response_game.text)
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

@tasks.loop(minutes=1)
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
        if "permanent" in desc.lower():
            continue

        ban_days = None
        timestamp_str = None
        for line in desc.splitlines():
            line_lower = line.lower()
            if "how long" in line_lower or "ban length" in line_lower:
                try:
                    ban_days = int(line.split()[-2])
                except:
                    ban_days = 0
            if "timestamp" in line_lower:
                try:
                    timestamp_str = line.split(":", 1)[1].strip()
                except:
                    timestamp_str = None

        if ban_days is None or not timestamp_str:
            continue

        try:
            ban_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        except:
            continue

        if now - ban_time >= timedelta(days=ban_days):
            delete_url = f"https://api.trello.com/1/cards/{card['id']}"
            try:
                requests.delete(delete_url, params=params, timeout=10)
            except requests.RequestException:
                continue

            log_title = f"{card.get('name', 'Unknown')} [AUTO UNBAN]"
            log_desc = (
                f"**Unbanned by**: AUTO UNBAN\n"
                f"**Reason**: Ban duration expired\n"
                f"**Banned At**: {ban_time.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"**Unbanned At**: {now.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"**Duration**: {(now - ban_time).days} days"
            )
            log_url = "https://api.trello.com/1/cards"
            create_params = {
                'idList': TRELLO_LOG_ID,
                'name': log_title,
                'desc': log_desc,
                'key': TRELLO_KEY,
                'token': TRELLO_TOKEN
            }
            try:
                requests.post(log_url, data=create_params, timeout=10)
            except requests.RequestException:
                continue


async def unban_user(session, card, ban_time, unban_time, params):
    """Remove ban card and create log entry."""
    card_id = card['id']
    card_name = card.get('name', 'Unknown User')
    
    # Delete the ban card
    delete_url = f"https://api.trello.com/1/cards/{card_id}"
    try:
        async with session.delete(delete_url, params=params) as response:
            if response.status not in [200, 404]:  # 404 is OK if card was already deleted
                logger.warning(f"Failed to delete card {card_id}: {response.status}")
                return
    except Exception as e:
        logger.error(f"Error deleting card {card_id}: {e}")
        return
    
    # Create log entry
    await create_unban_log(session, card_name, ban_time, unban_time, params)
    logger.info(f"Auto-unbanned user: {card_name}")

async def create_unban_log(session, user_name, ban_time, unban_time, params):
    """Create a log entry for the automatic unban."""
    log_title = f"{user_name} [AUTO UNBAN]"
    log_desc = (
        f"**Unbanned by**: AUTO UNBAN\n"
        f"**Reason**: Ban duration expired\n"
        f"**Banned At**: {ban_time.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"**Unbanned At**: {unban_time.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"**Duration**: {(unban_time - ban_time).days} days"
    )
    
    log_url = "https://api.trello.com/1/cards"
    create_params = {
        'idList': TRELLO_LOG_ID,
        'name': log_title,
        'desc': log_desc,
        **params
    }
    
    try:
        async with session.post(log_url, data=create_params) as response:
            if response.status != 200:
                logger.warning(f"Failed to create log entry: {response.status}")
    except Exception as e:
        logger.error(f"Error creating log entry: {e}")

# Alternative sync version if you prefer
def check_expired_bans_sync():
    """Synchronous version using requests."""
    import requests
    
    params = {'key': TRELLO_KEY, 'token': TRELLO_TOKEN}
    url = f"https://api.trello.com/1/lists/{TRELLO_LIST_ID}/cards"
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Error fetching cards: {e}")
        return
    
    cards = response.json()
    now = datetime.now(timezone.utc)
    
    for card in cards:
        try:
            desc = card.get('desc', '')
            
            if "permanent" in desc.lower():
                continue
            
            ban_info = parse_ban_info(desc)
            if not ban_info:
                continue
            
            ban_days, ban_time = ban_info
            
            if now - ban_time >= timedelta(days=ban_days):
                # Delete ban card
                delete_url = f"https://api.trello.com/1/cards/{card['id']}"
                try:
                    requests.delete(delete_url, params=params, timeout=10)
                except requests.RequestException as e:
                    logger.error(f"Error deleting card: {e}")
                    continue
                
                # Create log entry
                log_title = f"{card.get('name', 'Unknown')} [AUTO UNBAN]"
                log_desc = (
                    f"**Unbanned by**: AUTO UNBAN\n"
                    f"**Reason**: Ban duration expired\n"
                    f"**Banned At**: {ban_time.strftime('%Y-%m-%d %H:%M UTC')}\n"
                    f"**Unbanned At**: {now.strftime('%Y-%m-%d %H:%M UTC')}"
                )
                
                log_params = {
                    'idList': TRELLO_LOG_ID,
                    'name': log_title,
                    'desc': log_desc,
                    **params
                }
                
                try:
                    requests.post("https://api.trello.com/1/cards", data=log_params, timeout=10)
                except requests.RequestException as e:
                    logger.error(f"Error creating log entry: {e}")
                
                logger.info(f"Auto-unbanned: {card.get('name', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Error processing card {card.get('id', 'unknown')}: {e}")

@tree.command(name="ban", description="Ban a Roblox Player From Your Game")
@app_commands.describe(username="Roblox Username To Ban", reason="Why you're banning them", days="Ban duration in days (0 = permanent)")
async def ban(interaction: discord.Interaction, username: str, reason: str, days: int):
    whobanned = interaction.user.name
    if is_user_already_banned(username):
        await interaction.response.send_message(f"**{username}** is already banned.")
        return 
    if add_user(username, whobanned, reason, days):
        duration_text = "Permanent" if days == 0 else f"{days} days"
        await interaction.response.send_message(f"Successfully banned {username}.")
        embed = discord.Embed(title="Ban Command Used", color=discord.Color.red(), timestamp=discord.utils.utcnow())
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
        await interaction.response.send_message(f"Failed to ban {username}.")

@tree.command(name="unban", description="Unban a user")
@app_commands.describe(username="Roblox username to unban", reason="Why you're unbanning them")
async def unban(interaction: discord.Interaction, username: str, reason: str):
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
    log_title = f"{username} [UNBAN]"
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

token = os.environ.get("ERM")

@bot.event
async def on_ready():
    await tree.sync()
    check_expired_bans.start()
    print(f"bot is working and is online as {bot.user}")

bot.run(token)
