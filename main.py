# FIX: Python 3.13 compatibility shim for audioop
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
        import sys
        sys.modules['audioop'] = audioop
    except ImportError:
        pass 

import discord
from discord.ext import commands, tasks
import random
import sqlite3
import os
import ignis
import achievements
import asyncio
import json
import shutil
import sys
# REMOVED: import quests (Fixed ModuleNotFoundError)
import worknranks  # ADDED: Integrated separation
import daily as daily_module # FIXED: Import with alias to prevent conflict with commands
import social as social_module # ADDED: Social commands module
import prizes as prizes_module # ADDED: Prizes and Logic module
from datetime import datetime, timedelta, timezone
from lexicon import FieryLexicon
from dotenv import load_dotenv

# Impede a criação de pastas __pycache__ para facilitar edições constantes
sys.dont_write_bytecode = True

# ===== 1. INITIAL CONFIGURATION =====
load_dotenv()
# Railway will pull the DISCORD_TOKEN from the Variables tab automatically
TOKEN = os.getenv("DISCORD_TOKEN")
AUDIT_CHANNEL_ID = 1438810509322223677 # Seu canal de auditoria
STREAK_ALERTS_CHANNEL_ID = 1438810509322223677 # Red Room Channel for Pings

# --- NEW FEATURE: PERSISTENT STORAGE PATH ---
# This checks if the bot is on Railway (using a volume at /app/data)
# If not, it creates a local 'data' folder so you don't lose stats locally.
if os.path.exists("/app/data"):
    DATABASE_PATH = "/app/data/economy.db"
else:
    if not os.path.exists("data"):
        os.makedirs("data")
    DATABASE_PATH = "data/economy.db"

intents = discord.Intents.all()
# Explicitly forcing Message Content intent in code for Railway stability
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# These will be updated from the database in on_ready
game_edition = 1 
nsfw_mode_active = False # Flag for Grand Exhibition Special Event

# Ranks and Classes now sourced from worknranks.py
RANKS = worknranks.RANKS
CLASSES = worknranks.CLASSES

# ===== 2. DATABASE SYSTEM =====
def get_db_connection():
    # ADDED: Increased timeout to 30s to prevent 'database is locked' errors during heavy combat
    # FIXED: Using DATABASE_PATH for persistence
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

# NEW PERSISTENCE HELPERS
def save_game_config():
    global game_edition, nsfw_mode_active
    with get_db_connection() as conn:
        conn.execute("UPDATE game_config SET game_edition = ?, nsfw_mode = ? WHERE id = 1", 
                     (game_edition, 1 if nsfw_mode_active else 0))
        conn.commit()

def load_game_config():
    global game_edition, nsfw_mode_active
    with get_db_connection() as conn:
        row = conn.execute("SELECT game_edition, nsfw_mode FROM game_config WHERE id = 1").fetchone()
        if row:
            game_edition = row['game_edition']
            nsfw_mode_active = bool(row['nsfw_mode'])

def init_db():
    with get_db_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS global_stats (id INTEGER PRIMARY KEY, total_games INTEGER DEFAULT 0)""")
        
        # NEW TABLE FOR PERSISTENT SETTINGS
        conn.execute("""CREATE TABLE IF NOT EXISTS game_config (
            id INTEGER PRIMARY KEY, 
            game_edition INTEGER DEFAULT 1, 
            nsfw_mode INTEGER DEFAULT 0
        )""")
        conn.execute("INSERT OR IGNORE INTO game_config (id, game_edition, nsfw_mode) VALUES (1, 1, 0)")
        
        # Contract System Table
        conn.execute("""CREATE TABLE IF NOT EXISTS contracts (
            dominant_id INTEGER, 
            submissive_id INTEGER, 
            expiry TEXT, 
            tax_rate REAL DEFAULT 0.2,
            PRIMARY KEY (submissive_id)
        )""")
        
        # ADDED: DUEL HISTORY TABLE (Tracks Victims of !fuck)
        conn.execute("""CREATE TABLE IF NOT EXISTS duel_history (
            winner_id INTEGER,
            loser_id INTEGER,
            win_count INTEGER DEFAULT 0,
            PRIMARY KEY (winner_id, loser_id)
        )""")

        # Quest Table Re-Integrated into init_db
        q_cols = ["user_id INTEGER PRIMARY KEY"]
        for i in range(1, 21): q_cols.append(f"d{i} INTEGER DEFAULT 0")
        for i in range(1, 21): q_cols.append(f"w{i} INTEGER DEFAULT 0")
        q_cols.append("last_reset TEXT")
        conn.execute(f"CREATE TABLE IF NOT EXISTS quests ({', '.join(q_cols)})")

        required_columns = [
            ("balance", "INTEGER DEFAULT 500"), ("xp", "INTEGER DEFAULT 0"),
            ("fiery_xp", "INTEGER DEFAULT 0"), ("fiery_level", "INTEGER DEFAULT 1"),
            ("level", "INTEGER DEFAULT 1"), ("wins", "INTEGER DEFAULT 0"), 
            ("kills", "INTEGER DEFAULT 0"), ("deaths", "INTEGER DEFAULT 0"), 
            ("duel_wins", "INTEGER DEFAULT 0"), # ADDED: Separate stat for !fuck wins
            ("bio", "TEXT DEFAULT 'A tribute.'"), ("last_daily", "TEXT"), 
            ("last_weekly", "TEXT"), ("last_monthly", "TEXT"), ("class", "TEXT DEFAULT 'None'"),
            ("last_work", "TEXT"), ("last_beg", "TEXT"), ("last_cumcleaner", "TEXT"), 
            ("last_pimp", "TEXT"), ("last_experiment", "TEXT"), ("last_mystery", "TEXT"), 
            ("last_flirt", "TEXT"), ("first_bloods", "INTEGER DEFAULT 0"), 
            ("games_played", "INTEGER DEFAULT 0"), ("top_2", "INTEGER DEFAULT 0"), 
            ("top_3", "INTEGER DEFAULT 0"), ("top_4", "INTEGER DEFAULT 0"), 
            ("top_5", "INTEGER DEFAULT 0"), ("current_win_streak", "INTEGER DEFAULT 0"), 
            ("max_win_streak", "INTEGER DEFAULT 0"), ("current_kill_streak", "INTEGER DEFAULT 0"), 
            ("max_kill_streak", "INTEGER DEFAULT 0"), ("titles", "TEXT DEFAULT '[]'"),
            ("spouse", "INTEGER DEFAULT NULL"), ("marriage_date", "TEXT DEFAULT NULL"), # ADDED: Marriage Logic
            ("last_daily_streak", "TEXT"), ("last_weekly_streak", "TEXT"), ("last_monthly_streak", "TEXT"),
            ("daily_streak", "INTEGER DEFAULT 0"), ("weekly_streak", "INTEGER DEFAULT 0"), ("monthly_streak", "INTEGER DEFAULT 0"), # ADDED: STREAK COLUMNS
            ("streak_alerts", "INTEGER DEFAULT 1") # ADDED: TOGGLE ALERT COLUMN
        ]

        cursor = conn.execute("PRAGMA table_info(users)")
        existing_cols = [row[1] for row in cursor.fetchall()]

        for col_name, col_type in required_columns:
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                except: pass

        cursor_gs = conn.execute("PRAGMA table_info(global_stats)")
        existing_gs = [row[1] for row in cursor_gs.fetchall()]
        gs_cols = [("total_kills", "INTEGER DEFAULT 0"), ("total_deaths", "INTEGER DEFAULT 0"), ("first_deaths", "INTEGER DEFAULT 0")]
        for c_n, c_t in gs_cols:
            if c_n not in existing_gs:
                try: conn.execute(f"ALTER TABLE global_stats ADD COLUMN {c_n} {c_t}")
                except: pass
                
        conn.execute("INSERT OR IGNORE INTO global_stats (id) VALUES (1)")
        conn.commit()

init_db()

# ===== 3. CORE HELPERS & AUDIT =====
async def send_audit_log(user_id, amount, source, xp=0):
    channel = bot.get_channel(AUDIT_CHANNEL_ID)
    if not channel: return
    try:
        user = await bot.fetch_user(user_id)
        # --- NEW EROTIC AUDIT STYLE ---
        embed = discord.Embed(
            title="🕵️ THE MASTER'S LEDGER: TRANSACTION RECORDED", 
            description=f"A new vibration in the pit. Asset {user.mention} has processed a transaction.",
            color=0x8B0000, 
            timestamp=datetime.now(timezone.utc)
        )
        
        image_path = "LobbyTopRight.jpg"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="ledger_logo.jpg")
            embed.set_thumbnail(url="attachment://ledger_logo.jpg")
        else:
            embed.set_thumbnail(url=user.display_avatar.url)
            file = None
            
        embed.add_field(name="🫦 Ident: Asset", value=user.mention, inline=True)
        embed.add_field(name="⛓️ Source: Protocol", value=f"**{source}**", inline=True)
        
        # Details with Emojis
        val_flames = f"🔥 **+{amount}** Flames added to vault." if amount >= 0 else f"📉 **{amount}** Flames extracted."
        embed.add_field(name="💰 Currency Flow", value=val_flames, inline=False)
        
        if xp > 0:
            embed.add_field(name="💦 Neural Imprint (XP)", value=f"**+{xp}** experience units synchronized.", inline=False)
        
        embed.set_footer(text="🔞 THE RED ROOM RECORDS EVERYTHING 🔞")
        
        if file:
            await channel.send(file=file, embed=embed)
        else:
            await channel.send(embed=embed)
    except Exception as e: 
        print(f"Audit Log Error: {e}")

def fiery_embed(title, description, color=0xFF4500):
    # DYNAMIC COLOR: During Master Presence or NSFW Mode, all embeds turn Blood Red
    global nsfw_mode_active
    ext = bot.get_cog("FieryExtensions")
    if (ext and ext.master_present) or nsfw_mode_active:
        color = 0x8B0000 
    
    embed = discord.Embed(title=f"🔥 {title.upper()} 🔥", description=description, color=color)
    
    # FIXED: Mandatory Image Integration on ALL embeds
    if os.path.exists("LobbyTopRight.jpg"):
        embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
        
    embed.set_footer(text="🔞 FIERY HANGRYGAMES EDITION 🔞")
    embed.timestamp = datetime.now(timezone.utc)
    return embed

def get_user(user_id):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            conn.execute("INSERT INTO users (id) VALUES (?)", (user_id,))
            conn.commit()
            return get_user(user_id)
        return user

# --- REDIRECTED TO prizes.py ---
async def update_user_stats_async(user_id, amount=0, xp_gain=0, wins=0, kills=0, deaths=0, source="System"):
    await prizes_module.update_user_stats_async(user_id, amount, xp_gain, wins, kills, deaths, source, get_user, bot, get_db_connection, CLASSES, nsfw_mode_active, send_audit_log)

def update_user_stats(user_id, amount=0, xp_gain=0, wins=0, kills=0, deaths=0):
    prizes_module.update_user_stats(user_id, amount, xp_gain, wins, kills, deaths, get_user, CLASSES, get_db_connection)

# ===== 4. CLASS DETAIL COMMANDS =====
async def send_class_details(ctx, class_name):
    data = CLASSES[class_name]
    desc = (f"**{data['icon']} {class_name.upper()} CLASS DETAILS**\n\n"
            f"🔥 **Flame Bonus:** +{int((data['bonus_flames']-1)*100)}%\n"
            f"💦 **Experience Bonus:** +{int((data['bonus_xp']-1)*100)}%\n\n"
            f"*\"{data['desc']}\"*\n\n"
            f"Use `!setclass {class_name}` to claim this role.")
    
    embed = fiery_embed(f"{class_name} Class Profile", desc, color=0xFF0000)
    
    # ADDED STAT OVERVIEW TO CLASS DESC
    u = get_user(ctx.author.id)
    embed.add_field(name="⛓️ Current Standing", value=f"Balance: {u['balance']}F\nLevel: {u['level']}", inline=False)
    
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

@bot.command()
async def dominant(ctx): await send_class_details(ctx, "Dominant")
@bot.command()
async def submissive(ctx): await send_class_details(ctx, "Submissive")
@bot.command()
async def switch(ctx): await send_class_details(ctx, "Switch")
@bot.command()
async def exhibitionist(ctx): await send_class_details(ctx, "Exhibitionist")

@bot.command()
async def setclass(ctx, choice: str = None):
    if not choice or choice.capitalize() not in CLASSES:
        options = "\n".join([f"**{k}**: {v['desc']}" for k,v in CLASSES.items()])
        embed = fiery_embed("Dungeon Hierarchy", f"Choose your path, little asset:\n\n{options}\n\nType `!<classname>` for details.", color=0x800000)
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        return await ctx.send(file=file, embed=embed)
        
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET class = ? WHERE id = ?", (choice.capitalize(), ctx.author.id))
        conn.commit()
    
    u = get_user(ctx.author.id)
    embed = fiery_embed("Class Claimed", f"✅ You are now bound to the **{choice.capitalize()}** path.\n\nYour submission level is currently **{u['level']}**.", color=0x00FF00)
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

# ===== 5. EXTENDED ECONOMY COMMANDS (WORK SYSTEM) =====
@bot.command()
async def work(ctx): await worknranks.handle_work_command(ctx, bot, "work", (500, 750), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def beg(ctx): await worknranks.handle_work_command(ctx, bot, "beg", (500, 1500), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def cumcleaner(ctx): await worknranks.handle_work_command(ctx, bot, "cumcleaner", (800, 1800), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def pimp(ctx): await worknranks.handle_work_command(ctx, bot, "pimp", (800, 1600), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def experiment(ctx): await worknranks.handle_work_command(ctx, bot, "experiment", (500, 2000), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def mystery(ctx): await worknranks.handle_work_command(ctx, bot, "mystery", (100, 3000), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def flirt(ctx): await worknranks.handle_work_command(ctx, bot, "flirt", (700, 1800), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)

# ===== 6. CORE PERIODIC REWARDS SYSTEM (REMOVED TO daily.py) =====

@bot.command()
async def daily(ctx):
    await daily_module.handle_periodic_reward(ctx, "daily", 400, 800, 150, timedelta(days=1), get_user, update_user_stats_async, fiery_embed, get_db_connection)

@bot.command()
async def weekly(ctx):
    await daily_module.handle_periodic_reward(ctx, "weekly", 2500, 5000, 1000, timedelta(days=7), get_user, update_user_stats_async, fiery_embed, get_db_connection)

@bot.command()
async def monthly(ctx):
    await daily_module.handle_periodic_reward(ctx, "monthly", 12000, 20000, 5000, timedelta(days=30), get_user, update_user_stats_async, fiery_embed, get_db_connection)

@bot.command()
async def balance(ctx, member: discord.Member = None):
    target = member or ctx.author
    u = get_user(target.id)
    embed = fiery_embed(f"{target.display_name}'s Vault", f"💰 **Current Balance:** {u['balance']} Flames\n⛓️ **Class:** {u['class']}")
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

# ===== 7. PROFILE, RANKING, TITLES & HELP (MOVED TO social.py) =====

@bot.command()
async def me(ctx, member: discord.Member = None):
    await social_module.handle_me_command(ctx, member, get_user, get_db_connection, fiery_embed, bot, RANKS, nsfw_mode_active)

@bot.command()
async def ranking(ctx):
    await social_module.handle_ranking_command(ctx, get_db_connection, fiery_embed)

@bot.command()
async def hall(ctx):
    await social_module.handle_hall_command(ctx, get_db_connection, fiery_embed)

@bot.command()
async def fiery(ctx):
    await social_module.handle_fiery_guide(ctx, fiery_embed)

# --- GLOBAL STREAK LEADERBOARD COMMAND START (MOVED TO social.py) ---
@bot.command()
async def streaks(ctx):
    await social_module.handle_streaks_command(ctx, get_db_connection, get_user, fiery_embed)
# --- GLOBAL STREAK LEADERBOARD COMMAND END ---

# ===== 🛒 BLACK MARKET & LEGACY MUSEUM ADDITIONS =====

@bot.command()
async def buytitle(ctx, *, title_choice: str = None):
    """Market purchase command for prestige titles."""
    shop = bot.get_cog("ShopSystem")
    if not shop:
        embed = fiery_embed("Market Error", "❌ The Black Market is currently closed.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        return await ctx.send(file=file, embed=embed)
    pass

@bot.command()
async def favor(ctx):
    """Bribe the Master to force Peak Heat."""
    cost = 5000000
    user = get_user(ctx.author.id)
    ext = bot.get_cog("FieryExtensions")
    
    if user['balance'] < cost:
        embed = fiery_embed("Favor Rejected", f"❌ Master's Favor is expensive. You need {cost:,} Flames.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        return await ctx.send(file=file, embed=embed)
    
    if not ext:
        embed = fiery_embed("System Offline", "❌ The Master is currently unavailable.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        return await ctx.send(file=file, embed=embed)

    with get_db_connection() as conn:
        conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (cost, ctx.author.id))
        conn.commit()
    
    await ext.activate_peak_heat(ctx)
    embed = fiery_embed("MASTER'S FAVOR", f"🔥 <@{ctx.author.id}> has bribed the Master. **PEAK HEAT IS NOW ACTIVE!**", color=0xFF0000)
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

# ===== NSFW Special Commands =====
@bot.command()
@commands.is_owner()
async def nsfwtime(ctx):
    global nsfw_mode_active
    nsfw_mode_active = True
    save_game_config() # ADDED PERSISTENCE
    ext = bot.get_cog("FieryExtensions")
    if ext: await ext.trigger_nsfw_start(ctx)

@bot.command()
@commands.is_owner()
async def nomorensfw(ctx):
    global nsfw_mode_active
    nsfw_mode_active = False
    save_game_config() # ADDED PERSISTENCE
    embed = fiery_embed("NSFW Mode Ended", "The exhibition has closed. Returning to standard Red Room protocols.")
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

@bot.command()
@commands.is_owner()
async def grantbadge(ctx, member: discord.Member, badge: str):
    u = get_user(member.id)
    try: titles = json.loads(u['titles'])
    except: titles = []
    
    if badge not in titles:
        titles.append(badge)
        with get_db_connection() as conn:
            conn.execute("UPDATE users SET titles = ? WHERE id = ?", (json.dumps(titles), member.id))
            conn.commit()
        embed = fiery_embed("Badge Granted", f"✅ Granted badge **{badge}** to {member.display_name}")
    else:
        embed = fiery_embed("Badge Conflict", "User already has this badge.")
    
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

# ===== 8. MAINTENANCE & AUDIT =====
@bot.command()
@commands.is_owner()
async def backup(ctx):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{DATABASE_PATH}.backup_{timestamp}"
    try:
        shutil.copy2(DATABASE_PATH, backup_name)
        embed = fiery_embed("Database Backup", f"✅ Saved in persistence volume as `{backup_name}`")
    except Exception as e:
        embed = fiery_embed("Backup Failure", f"❌ **ERROR:** {e}")
    
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

@bot.command()
@commands.is_owner()
async def reload(ctx, cog_name: str):
    try:
        import importlib
        if cog_name.lower() == "achievements":
            await bot.reload_extension("achievements")
        elif cog_name.lower() == "ignis":
            await bot.remove_cog("IgnisEngine")
            importlib.reload(ignis)
            await bot.add_cog(ignis.IgnisEngine(bot, update_user_stats_async, get_user, fiery_embed, get_db_connection, RANKS, CLASSES, AUDIT_CHANNEL_ID))
        elif cog_name.lower() == "lexicon":
            await bot.remove_cog("Lexicon")
            import lexicon
            importlib.reload(lexicon)
        elif cog_name.lower() == "extensions":
            await bot.reload_extension("extensions")
        elif cog_name.lower() == "ship":
            await bot.reload_extension("ship")
        elif cog_name.lower() == "shop":
            await bot.reload_extension("shop")
        elif cog_name.lower() == "collect":
            await bot.reload_extension("collect")
        elif cog_name.lower() == "fight":
            await bot.reload_extension("fight")
        elif cog_name.lower() == "casino":
            await bot.reload_extension("casino")
        elif cog_name.lower() == "ask":
            await bot.reload_extension("ask")
        else:
            embed = fiery_embed("Reload Error", f"❌ Cog `{cog_name}` not found.")
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            return await ctx.send(file=file, embed=embed)
        
        embed = fiery_embed("Reload Success", f"🔥 **{cog_name.upper()}** reloaded!")
    except Exception as e:
        embed = fiery_embed("Reload Failure", f"❌ **ERROR:** {e}")
    
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

# ===== 9. SYSTEM INTEGRATION =====
@bot.command()
async def fierystart(ctx):
    global game_edition
    image_path = "LobbyTopRight.jpg"
    embed = discord.Embed(title=f"Fiery's Hangrygames Edition # {game_edition}", 
                          description="The hellgates are about to open, little pets. Submit to the registration.", color=0xFF0000)
    
    view = ignis.LobbyView(ctx.author, game_edition)
    engine = bot.get_cog("IgnisEngine")
    if engine: engine.current_lobby = view

    if os.path.exists(image_path):
        file = discord.File(image_path, filename="lobby_thumb.jpg")
        embed.set_thumbnail(url="attachment://lobby_thumb.jpg")
        embed.add_field(name="<:FIERY_sym_dick:1314898974360076318> 0 Sinners Ready", value="The air is thick with anticipation.", inline=False)
        await ctx.send(file=file, embed=embed, view=view)
    else:
        embed.set_thumbnail(url="https://i.imgur.com/Gis6f9V.gif")
        embed.add_field(name="<:FIERY_sym_dick:1314898974360076318> 0 Sinners Ready", value="\u200b", inline=False)
        await ctx.send(embed=embed, view=view)
    
    game_edition += 1
    save_game_config() # ADDED PERSISTENCE

@bot.command()
async def lobby(ctx):
    engine = bot.get_cog("IgnisEngine")
    if not engine or not engine.current_lobby:
        embed = fiery_embed("Lobby Status", "No active registration in progress. The pit is closed.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        return await ctx.send(file=file, embed=embed)
    
    participants = engine.current_lobby.participants
    if not participants:
        embed = fiery_embed("Lobby Status", "The room is empty. No one has offered their body yet.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        return await ctx.send(file=file, embed=embed)
    
    mentions = [f"<@{p_id}>" for p_id in participants]
    embed = fiery_embed("Active Tributes", f"The following souls are bound for Edition #{engine.current_lobby.edition}:\n\n" + "\n".join(mentions), color=0x00FF00)
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

# EMERGENCY RAILWAY DEBUG COMMAND
@bot.command()
async def ping(ctx):
    embed = fiery_embed("Neural Sync", f"🏓 Pong! Neural Latency: **{round(bot.latency * 1000)}ms**")
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

# --- STREAK GUARDIAN PROTOCOL START ---
@bot.command()
async def togglealerts(ctx):
    """Toggles whether you receive public pings from the Streak Guardian."""
    u = get_user(ctx.author.id)
    new_status = 0 if u['streak_alerts'] == 1 else 1
    
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET streak_alerts = ? WHERE id = ?", (new_status, ctx.author.id))
        conn.commit()
    
    status_text = "ENABLED" if new_status == 1 else "DISABLED"
    embed = fiery_embed("ALERT PROTOCOL UPDATED", f"Public Guardian pings for your soul are now **{status_text}**.")
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

@tasks.loop(hours=1)
async def streak_guardian():
    """Background task to ping assets in-server before their streaks reset."""
    now = datetime.now(timezone.utc)
    channel = bot.get_channel(STREAK_ALERTS_CHANNEL_ID)
    if not channel: return

    with get_db_connection() as conn:
        users = conn.execute("SELECT id, last_daily, last_weekly, last_monthly, daily_streak, weekly_streak, monthly_streak, streak_alerts FROM users").fetchall()
        
        for u in users:
            if u['streak_alerts'] == 0: continue # User opted out
            
            member_id = u['id']
            # Protocol: Daily (Only for streaks >= 5)
            if u['last_daily'] and u['daily_streak'] >= 5:
                last_d = datetime.fromisoformat(u['last_daily'])
                if timedelta(hours=45) <= (now - last_d) < timedelta(hours=46):
                    await send_streak_ping(channel, member_id, "Daily", "45 hours")

            # Protocol: Weekly (Ping 3h before 14-day limit)
            if u['last_weekly'] and u['weekly_streak'] > 0:
                last_w = datetime.fromisoformat(u['last_weekly'])
                limit = timedelta(days=14)
                if (limit - timedelta(hours=3)) <= (now - last_w) < (limit - timedelta(hours=2)):
                    await send_streak_ping(channel, member_id, "Weekly", "13 days and 21 hours")

            # Protocol: Monthly (Ping 3h before 60-day limit)
            if u['last_monthly'] and u['monthly_streak'] > 0:
                last_m = datetime.fromisoformat(u['last_monthly'])
                limit = timedelta(days=60)
                if (limit - timedelta(hours=3)) <= (now - last_m) < (limit - timedelta(hours=2)):
                    await send_streak_ping(channel, member_id, "Monthly", "59 days and 21 hours")

async def send_streak_ping(channel, user_id, tier, elapsed):
    """Sends a public ping in the alert channel."""
    embed = fiery_embed("⚠️ STREAK VIBRATION: DISCIPLINE REQUIRED", 
                        f"Asset <@{user_id}>, your consistent submission is at risk.\n\n"
                        f"It has been **{elapsed}** since your last **{tier}** claim. "
                        f"In **3 hours**, your progress will be purged.\n\n"
                        f"⛓️ **Submit your tribute now.**", color=0xFFCC00)
    
    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="alert.jpg")
        embed.set_thumbnail(url="attachment://alert.jpg")
        await channel.send(content=f"<@{user_id}>", file=file, embed=embed)
    else:
        await channel.send(content=f"<@{user_id}>", embed=embed)
# --- STREAK GUARDIAN PROTOCOL END ---

@bot.event
async def on_ready():
    print("--- STARTING SYSTEM INITIALIZATION ---")
    
    if not bot.get_cog("IgnisEngine"):
        await bot.add_cog(ignis.IgnisEngine(bot, update_user_stats_async, get_user, fiery_embed, get_db_connection, RANKS, CLASSES, AUDIT_CHANNEL_ID))
    
    if not bot.get_cog("Achievements"):
        await bot.add_cog(achievements.Achievements(bot, get_db_connection, fiery_embed))
    
    load_game_config()
    
    # Start the Guardian Task
    if not streak_guardian.is_running():
        streak_guardian.start()
    
    bot.add_view(ignis.LobbyView(None, None))

    try:
        if not bot.get_cog("FieryExtensions"):
            await bot.load_extension("extensions")
    except Exception as e:
        print(f"Failed to load extensions: {e}")

    try:
        if not bot.get_cog("FieryShip"):
            await bot.load_extension("ship")
    except Exception as e:
        print(f"Failed to load ship extension: {e}")

    try:
        await bot.load_extension("shop")
    except Exception as e:
        print(f"Failed to load shop extension: {e}")

    try:
        await bot.load_extension("collect")
    except Exception as e:
        print(f"Failed to load collect extension: {e}")

    try:
        await bot.load_extension("fight")
        print("✅ LOG: Fight System is ONLINE.")
    except Exception as e:
        print(f"Failed to load fight extension: {e}")

    # --- ADDED: CASINO EXTENSION LOADING ---
    try:
        await bot.load_extension("casino")
        print("✅ LOG: Casino System is ONLINE.")
    except Exception as e:
        print(f"Failed to load casino extension: {e}")
    
    # --- ADDED: ASK EXTENSION LOADING ---
    try:
        await bot.load_extension("ask")
        print("✅ LOG: Ask System is ONLINE.")
    except Exception as e:
        print(f"Failed to load ask extension: {e}")
    
    await bot.change_presence(activity=discord.Game(name="Fiery Hangrygames"))
    print(f"✅ LOG: {bot.user} is ONLINE using persistent DB at {DATABASE_PATH}.")
    print(f"📊 PERSISTENCE: Edition #{game_edition} | NSFW Mode: {nsfw_mode_active}")

@bot.event
async def on_message(message):
    if message.author.bot: 
        return
    
    # CRITICAL ADDITION: High Priority processing for Railway latency
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.invoke(ctx)
    else:
        # Standard fallback for non-command messages
        await bot.process_commands(message)

async def main():
    try:
        async with bot: 
            await bot.start(TOKEN)
    except KeyboardInterrupt:
        pass
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__": 
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
