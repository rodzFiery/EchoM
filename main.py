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
import worknranks  # ADDED: Integrated separation
import daily as daily_module # FIXED: Import with alias to prevent conflict with commands
import social as social_module # ADDED: Social commands module
import prizes as prizes_module # ADDED: Prizes and Logic module
import database as db_module # ADDED: Centralized Database logic synchronization
import utilis # ADDED: Centralized Utils synchronization
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

# DATABASE PATH handled by db_module for persistence
DATABASE_PATH = db_module.DATABASE_PATH

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

# ===== 2. DATABASE SYSTEM REDIRECTS =====
def get_db_connection():
    # ADDED: Redirect to central db_module
    return db_module.get_db_connection()

# NEW PERSISTENCE HELPERS (Synced with database.py)
def save_game_config():
    global game_edition, nsfw_mode_active
    db_module.save_game_config(game_edition, nsfw_mode_active)

def load_game_config():
    global game_edition, nsfw_mode_active
    # FIXED: Load via db_module
    game_edition, nsfw_mode_active = db_module.load_game_config()

def init_db():
    # FIXED: Initialize via db_module
    db_module.init_db()

init_db()

# ===== 3. CORE HELPERS & AUDIT REDIRECTS =====
async def send_audit_log(user_id, amount, source, xp=0):
    # REDIRECTED TO utilis.py body logic
    await utilis.send_audit_log(bot, AUDIT_CHANNEL_ID, user_id, amount, source, xp)

def fiery_embed(title, description, color=0xFF4500):
    # REDIRECTED TO utilis.py body logic
    return utilis.fiery_embed(bot, nsfw_mode_active, title, description, color)

def get_user(user_id):
    # ADDED: Redirect to central db_module
    return db_module.get_user(user_id)

# --- REDIRECTED TO prizes.py ---
async def update_user_stats_async(user_id, amount=0, xp_gain=0, wins=0, kills=0, deaths=0, source="System"):
    await prizes_module.update_user_stats_async(user_id, amount, xp_gain, wins, kills, deaths, source, get_user, bot, get_db_connection, CLASSES, nsfw_mode_active, send_audit_log)

def update_user_stats(user_id, amount=0, xp_gain=0, wins=0, kills=0, deaths=0):
    prizes_module.update_user_stats(user_id, amount, xp_gain, wins, kills, deaths, get_user, CLASSES, get_db_connection)

# ===== 4. CLASS DETAIL COMMANDS (MOVED TO classes.py) =====

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

# ===== 8. ADMIN COMMANDS (HANDLED BY admin.py) =====
# NSFW, Backup, Reload e Grantbadge foram movidos para admin.py

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

    # CARREGAMENTO AUTOMÁTICO DO ADMIN, CLASSES E EXTENSÕES
    try: 
        if not bot.get_cog("AdminSystem"):
            await bot.load_extension("admin")
            print("✅ LOG: Admin System is ONLINE.")
    except Exception as e: print(f"Admin fail: {e}")

    try: 
        if not bot.get_cog("ClassSystem"):
            await bot.load_extension("classes")
            print("✅ LOG: Class System is ONLINE.")
    except Exception as e: print(f"Class System fail: {e}")

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

make me a report of what this .py have
