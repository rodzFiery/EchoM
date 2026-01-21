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
import aiohttp # ADDED: Required for topgg_poster to function
# REMOVED: import quests (Fixed ModuleNotFoundError)
import worknranks  # ADDED: Integrated separation
import daily as daily_module # FIXED: Import with alias to prevent conflict with commands
import social as social_module # ADDED: Social commands module
import prizes as prizes_module # ADDED: Prizes and Logic module
import database as db_module # ADDED: Centralized Database logic synchronization
import utilis # ADDED: Centralized Utils synchronization
from datetime import datetime, timedelta, timezone
from lexicon import FieryLexicon
from dotenv import load_dotenv

# --- ADDED: WEBHOOK SERVER IMPORTS ---
from flask import Flask, request
import threading

# Impede a criação de pastas __pycache__ para facilitar edições constantes
sys.dont_write_bytecode = True

# ===== 1. INITIAL CONFIGURATION =====
load_dotenv()
# Railway will pull the DISCORD_TOKEN from the Variables tab automatically
TOKEN = os.getenv("DISCORD_TOKEN")
TOPGG_TOKEN = os.getenv("TOPGG_TOKEN") # ADDED: For Top.gg API Authorization
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
AUTO_IGNIS_CHANNEL = 0 # ADDED: Persistence for Automated Pit
AUTO_IGNIS_ROLE = 0    # ADDED: Persistence for Hourly Pings

# Ranks and Classes now sourced from worknranks.py
RANKS = worknranks.RANKS
CLASSES = worknranks.CLASSES

# ===== 2. DATABASE SYSTEM REDIRECTS =====
def get_db_connection():
    # ADDED: Redirect to central db_module
    return db_module.get_db_connection()

# NEW PERSISTENCE HELPERS (Synced with database.py)
def save_game_config():
    global game_edition, nsfw_mode_active, AUTO_IGNIS_CHANNEL, AUTO_IGNIS_ROLE
    db_module.save_game_config(game_edition, nsfw_mode_active)
    # ADDED: Save auto channel and role to config table
    with get_db_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('auto_ignis_channel', ?)", (str(AUTO_IGNIS_CHANNEL),))
        conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('auto_ignis_role', ?)", (str(AUTO_IGNIS_ROLE),))
        conn.commit()

def load_game_config():
    global game_edition, nsfw_mode_active, AUTO_IGNIS_CHANNEL, AUTO_IGNIS_ROLE
    # FIXED: Load via db_module
    game_edition, nsfw_mode_active = db_module.load_game_config()
    # ADDED: Load auto channel and role
    with get_db_connection() as conn:
        row_ch = conn.execute("SELECT value FROM config WHERE key = 'auto_ignis_channel'").fetchone()
        if row_ch: AUTO_IGNIS_CHANNEL = int(row_ch['value'])
        row_rl = conn.execute("SELECT value FROM config WHERE key = 'auto_ignis_role'").fetchone()
        if row_rl: AUTO_IGNIS_ROLE = int(row_rl['value'])

def init_db():
    # FIXED: Initialize via db_module
    db_module.init_db()

init_db()

# ===== 3. CORE HELPERS & AUDIT REDIRECTS =====
async def send_audit_log(user_id, amount, source, xp=0):
    # FIXED: Now pulls from the global AUDIT_CHANNEL_ID that audit.py updates live
    await utilis.send_audit_log(bot, AUDIT_CHANNEL_ID, user_id, amount, source, xp)

def fiery_embed(title, description, color=0xFF4500):
    # REDIRECTED TO utilis.py body logic
    return utilis.fiery_embed(bot, nsfw_mode_active, title, description, color)

def get_user(user_id):
    # ADDED: Redirect to central db_module
    return db_module.get_user(user_id)

# --- REDIRECTED TO prizes.py ---
# FIXED: Updated signature to ensure all 13 arguments from prizes.py are handled correctly
async def update_user_stats_async(user_id, amount=0, xp_gain=0, wins=0, kills=0, deaths=0, source="System", 
                                  get_user_func=None, bot_obj=None, db_func=None, class_dict=None, nsfw=None, audit_func=None):
    
    # Use provided funcs or fall back to globals defined in main.py
    g_user = get_user_func or get_user
    b_obj = bot_obj or bot
    d_func = db_func or get_db_connection
    c_dict = class_dict or CLASSES
    n_mode = nsfw if nsfw is not None else nsfw_mode_active
    a_log = audit_func or send_audit_log

    await prizes_module.update_user_stats_async(user_id, amount, xp_gain, wins, kills, deaths, source, g_user, b_obj, d_func, c_dict, n_mode, a_log)

def update_user_stats(user_id, amount=0, xp_gain=0, wins=0, kills=0, deaths=0):
    prizes_module.update_user_stats(user_id, amount, xp_gain, wins, kills, deaths, get_user, CLASSES, get_db_connection)

# --- AUTOMATIC PAYMENT WEBHOOK (PAYPAL IPN) ---
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def paypal_webhook():
    data = request.form.to_dict()
    if data.get('payment_status') == 'Completed':
        custom = data.get('custom')
        if custom:
            try:
                user_id, plan_name, days = custom.split('|')
                p_date = datetime.now().isoformat()
                with get_db_connection() as conn:
                    # FIX: LOGIC TO ACCUMULATE BUNDLES RATHER THAN OVERWRITE
                    current = conn.execute("SELECT premium_type FROM users WHERE id = ?", (int(user_id),)).fetchone()
                    if not current or current['premium_type'] in ['Free', '', None]:
                        new_val = plan_name
                    else:
                        existing = [p.strip() for p in current['premium_type'].split(',')]
                        if plan_name not in existing:
                            existing.append(plan_name)
                        new_val = ", ".join(existing)

                    conn.execute("UPDATE users SET premium_type = ?, premium_date = ? WHERE id = ?", (new_val, p_date, int(user_id)))
                    conn.commit()
                print(f"✅ [SISTEMA] Premium '{plan_name}' ativado via Webhook para ID {user_id}")
                
                # ADICIONADO: Notificação em tempo real para o usuário no Discord
                user = bot.get_user(int(user_id))
                if user:
                    # FIXED: Use threadsafe call to prevent crash between Flask and Discord Bot
                    bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(user.send(embed=fiery_embed("👑 PREMIUM ACTIVATED", 
                        f"Greetings, {user.mention}. Your payment for **{plan_name}** was processed.\n"
                        f"All elite privileges have been granted to your account.", color=0xFFD700))))
            except Exception as e:
                print(f"❌ [ERRO] Webhook falhou: {e}")
    return "OK", 200

def run_web_server():
    # O Railway usa a porta 8080 por padrão para Networking Público
    port = int(os.environ.get("PORT", 8080))
    try:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"⚠️ Web Server bypass (Address in use): {e}")

# Inicia o servidor em segundo plano apenas se não estiver rodando
if not any(t.name == "FieryWebhook" for t in threading.enumerate()):
    threading.Thread(target=run_web_server, name="FieryWebhook", daemon=True).start()

# --- TOP.GG STATS POSTER PROTOCOL ---
@tasks.loop(minutes=30)
async def topgg_poster():
    """Automatically posts server count to Top.gg every 30 minutes."""
    if not TOPGG_TOKEN:
        return

    url = f"https://top.gg/api/bots/{bot.user.id}/stats"
    headers = {"Authorization": TOPGG_TOKEN}
    payload = {"server_count": len(bot.guilds)}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    print(f"📊 [TOP.GG] Stats synchronized: {len(bot.guilds)} servers.")
                else:
                    print(f"⚠️ [TOP.GG] Update failed: {resp.status}")
        except Exception as e:
            print(f"❌ [TOP.GG] Connection error: {e}")

@bot.event
async def on_guild_join(guild):
    """Trigger update when bot joins a new server."""
    await topgg_poster()

@bot.event
async def on_guild_remove(guild):
    """Trigger update when bot leaves a server."""
    await topgg_poster()

# ===== 5. EXTENDED ECONOMY COMMANDS (WORK SYSTEM) =====
@bot.command()
@commands.check(lambda ctx: bot.get_cog("PremiumSystem").is_premium().predicate(ctx) if bot.get_cog("PremiumSystem") else True)
async def work(ctx): await worknranks.handle_work_command(ctx, bot, "work", (500, 20000), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def beg(ctx): await worknranks.handle_work_command(ctx, bot, "beg", (500, 20000), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def cumcleaner(ctx): await worknranks.handle_work_command(ctx, bot, "cumcleaner", (800, 20000), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def pimp(ctx): await worknranks.handle_work_command(ctx, bot, "pimp", (800, 20000), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def experiment(ctx): await worknranks.handle_work_command(ctx, bot, "experiment", (500, 20000), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def mystery(ctx): await worknranks.handle_work_command(ctx, bot, "mystery", (100, 20000), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)
@bot.command()
async def flirt(ctx): await worknranks.handle_work_command(ctx, bot, "flirt", (700, 20000), get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active)

# ===== 6. CORE PERIODIC REWARDS SYSTEM (REMOVED TO daily.py) =====

@bot.command()
async def daily(ctx):
    await daily_module.handle_periodic_reward(ctx, "daily", 2500, 15000, 2000, timedelta(days=1), get_user, update_user_stats_async, fiery_embed, get_db_connection)

@bot.command()
async def weekly(ctx):
    await daily_module.handle_periodic_reward(ctx, "weekly", 20000, 90000, 10000, timedelta(days=7), get_user, update_user_stats_async, fiery_embed, get_db_connection)

@bot.command()
async def monthly(ctx):
    await daily_module.handle_periodic_reward(ctx, "monthly", 100000, 450000, 50000, timedelta(days=30), get_user, update_user_stats_async, fiery_embed, get_db_connection)

@bot.command()
async def balance(ctx, member: discord.Member = None):
    target = member or ctx.author
    u = get_user(target.id)
    embed = fiery_embed(f"{target.display_name}'s Vault", f"💰 **Current Balance:** {u['balance']} Flames\n⛓️ **Class:** {u['class']}")
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

# ===== 7. UPDATED PROFILE DOSSIER COMMAND (!me) =====

@bot.command(name="me")
async def me(ctx, member: discord.Member = None):
    """ULTIMATE ASSET DOSSIER: Comprehensive profile integration."""
    target = member or ctx.author
    u = get_user(target.id)
    
    with get_db_connection() as conn:
        # Calculate Rankings
        wins_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE wins > ?", (u['wins'],)).fetchone()
        kills_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE kills > ?", (u['kills'],)).fetchone()
        duel_wins_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE duel_wins > ?", (u['duel_wins'],)).fetchone()
        
        wins_rank = wins_row['r'] if wins_row else "?"
        kills_rank = kills_row['r'] if kills_row else "?"
        duel_rank = duel_wins_row['r'] if duel_wins_row else "?"

        # Fetch Victims from duel_history
        victims = conn.execute("""
            SELECT loser_id, win_count FROM duel_history 
            WHERE winner_id = ? ORDER BY win_count DESC LIMIT 5
        """, (target.id,)).fetchall()

    # Echo Rank Logic
    lvl = u['fiery_level']
    rank_name = RANKS[lvl-1] if lvl <= 100 else RANKS[-1]
    
    # Title/Badge Logic
    try: 
        titles = json.loads(u['titles'])
    except: 
        titles = []
    
    # Check for Last Hangrygames Winner Title
    engine = bot.get_cog("IgnisEngine")
    if nsfw_mode_active and engine and engine.last_winner_id == target.id:
        titles.append("⛓️ HANGRYGAMES LEAD 🔞")

    badge_display = " ".join(titles) if titles else "No badges yet."

    # Ownership Logic
    owner_text = "Free Soul"
    if u['spouse']:
        owner_text = f"Bound to <@{u['spouse']}> (Married)"
    else:
        with get_db_connection() as conn:
            contract_data = conn.execute("SELECT dominant_id FROM contracts WHERE submissive_id = ?", (target.id,)).fetchone()
            if contract_data:
                owner_text = f"Bound to <@{contract_data['dominant_id']}> (Contract)"

    # Embed Creation
    embed = discord.Embed(title=f"😻 {target.display_name}'s Dossier", color=0xFF0000)
    
    # Visual Logic
    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
    else:
        embed.set_thumbnail(url=target.display_avatar.url)

    embed.add_field(name="❤ Class", value=f"**{u['class']}**", inline=False)
    embed.add_field(name="🏅 Badges & Titles", value=badge_display, inline=False)
    embed.add_field(name="👜 Wallet", value=f"**Flames:** {u['balance']:,}\n**Global Level:** {u['level']} ({u['xp']:,} XP)", inline=True)
    embed.add_field(name="🔥 Echo Stats", value=f"**Level:** {lvl}\n**Rank:** {rank_name}\n**Total XP:** {u['fiery_xp']:,}", inline=True)
    
    combat_stats = (f"🏆 **Wins:** {u['wins']} (Rank #{wins_rank})\n"
                    f"⚔️ **Kills:** {u['kills']} (Rank #{kills_rank})\n"
                    f"🫦 **Duel Wins:** {u['duel_wins']} (Rank #{duel_rank})\n"
                    f"💀 **Deaths:** {u['deaths']}\n"
                    f"🎮 **Games Played:** {u['games_played']}")
    embed.add_field(name="⚔️ Echo Hangrygames & Duels", value=combat_stats, inline=False)
    
    # Victim Field
    if victims:
        v_lines = []
        for v in victims:
            v_member = ctx.guild.get_member(v['loser_id'])
            v_name = v_member.display_name if v_member else f"Unknown ({v['loser_id']})"
            v_lines.append(f"• **{v_name}**: {v['win_count']} times")
        embed.add_field(name="🎯 Top 5 Victims (Private Sessions)", value="\n".join(v_lines), inline=False)
    else:
        embed.add_field(name="🎯 Top 5 Victims (Private Sessions)", value="No one has submitted yet.", inline=False)

    embed.add_field(name="🔒 Ownership Status", value=f"**{owner_text}**", inline=False)

    # Achievement Integration
    ach_cog = bot.get_cog("Achievements")
    if ach_cog:
        summary = ach_cog.get_achievement_summary(target.id)
        embed.add_field(name="🏅 Achievements", value=summary, inline=False)
    
    if os.path.exists("LobbyTopRight.jpg"):
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send(embed=embed)

@bot.command()
async def ranking(ctx):
    await social_module.handle_ranking_command(ctx, get_db_connection, fiery_embed)

@bot.command()
async def hall(ctx):
    await social_module.handle_hall_command(ctx, get_db_connection, fiery_embed)

@bot.command()
async def echo(ctx):
    """ULTIMATE OMNI-PROTOCOL GUIDE: TRANSFORMED V8.0"""
    # Page 1: Gameplay & Combat Extensions
    emb1 = fiery_embed("⚔️ COMBAT & ARENA PROTOCOLS", 
        "**Battle Extensions (ignis.py & fight.py)**\n"
        "• `!echostart`: Force immediate Arena execution.\n"
        "• `!lobby`: Open the Red Room combat lobby.\n"
        "• `!join` / `!leave`: Enter or exit the active simulation.\n"
        "• `!fight <@user>`: Trigger a health-bar based 1v1 duel.\n"
        "• `!@user`: Champion's decree (Available only to winners).\n"
        "• `!stats`: View your personal combat lethality records.")

    # Page 2: Social & Economy Extensions
    emb2 = fiery_embed("🫦 SOCIAL & WEALTH PROTOCOLS", 
        "**Economy Extensions (shop.py & ship.py)**\n"
        "• `!shop`: Browse the Black Market for prestige items.\n"
        "• `!buy <item_id>`: Purchase asset upgrades or titles.\n"
        "• `!inv`: View your current asset inventory.\n"
        "• `!ship`: Scan resonance between two assets.\n"
        "• `!marry`: Bind souls permanently for anniversary bonuses.\n"
        "• `!confess`: Send an anonymous link through the neural net.")

    # Page 3: Identity & Ranking
    emb3 = fiery_embed("🏅 IDENTITY & PROGRESSION", 
        "**Status Extensions (levels.py & social.py)**\n"
        "• `!mylevel`: Check your social standing and global XP.\n"
        "• `!ranktop`: View the assets with the highest neural level.\n"
        "• `!ranking`: Global combat leaderboard (Wins/Kills).\n"
        "• `!hall`: The Legacy Museum of record-breaking assets.\n"
        "• `!streaks`: Leaderboard of the most disciplined souls.\n"
        "• `!achievements`: Review your unlocked honor badges.")

    # Page 4: Risk & Utility
    emb4 = fiery_embed("🎲 RISK & NEURAL UTILITIES", 
        "**Minigames & Automation (casino.py & thread.py)**\n"
        "• `!slots` / `!blackjack`: Standard high-risk gambling.\n"
        "• `!roulette` / `!dice`: Luck-based Flame extraction.\n"
        "• `!search`: Scavenge the system for hidden Flames.\n"
        "• `!gallery`: View collected media artifacts from searches.\n"
        "• `!ping`: Measure neural latency to the Master.\n"
        "• `!togglealerts`: Opt-in/out of Streak Guardian pings.")

    # Page 5: Main Core Commands
    emb5 = fiery_embed("📜 MAIN CORE COMMANDS", 
        "**Base Protocols (Direct main.py execution)**\n"
        "• `!me`: Your comprehensive asset dossier/profile.\n"
        "• `!balance`: Check your current vault of Flames.\n"
        "• `!daily` / `!weekly` / `!monthly`: Recurring stipend claims.\n"
        "• `!work`: Professional extraction (Premium only).\n"
        "• `!beg` / `!flirt` / `!pimp`: Various work-tier extractions.\n"
        "• `!mystery`: High-variance gamble on reward amount.")

    # Page 6: Master Protocols
    emb6 = fiery_embed("⚖️ MASTER OVERRIDES (ADMIN)", 
        "**Governance Protocols (admin.py & audit.py)**\n"
        "• `!nsfwtime`: Activate the Grand Exhibition (2x Multiplier).\n"
        "• `!masterpresence`: Force Peak Heat server-wide.\n"
        "• `!echoon`: Global free-premium override toggle.\n"
        "• `!audit <#ch>`: Rebind the Master's Ledger location.\n"
        "• `!setlevelchannel`: Assign level-up broadcast point.\n"
        "• `!reset_arena`: Emergency unlock for stalled sessions.\n"
        "• `!setuproles`: Open the designer suite for custom roles.\n"
        "• `!setup_gateway`: Deploy automatic verification rules.")

    pages = [emb1, emb2, emb3, emb4, emb5, emb6]
    for e in pages:
        if os.path.exists("LobbyTopRight.jpg"):
            e.set_thumbnail(url="attachment://LobbyTopRight.jpg")
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=e)
        else:
            await ctx.send(embed=e)

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

# ===== 9. SYSTEM INTEGRATION =====

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
    
    # --- AUDIT PERSISTENCE RETRIEVAL ---
    try:
        with get_db_connection() as conn:
            # Garante que a tabela config existe
            conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
            row = conn.execute("SELECT value FROM config WHERE key = 'audit_channel'").fetchone()
            if row:
                global AUDIT_CHANNEL_ID
                AUDIT_CHANNEL_ID = int(row['value'])
                print(f"🕵️ PERSISTENCE: Audit Channel restored to {AUDIT_CHANNEL_ID}")
    except Exception as e:
        print(f"Audit restoration fail: {e}")

    if not bot.get_cog("IgnisEngine"):
        await bot.add_cog(ignis.IgnisEngine(bot, update_user_stats_async, get_user, fiery_embed, get_db_connection, RANKS, CLASSES, AUDIT_CHANNEL_ID))
    
    # NEW: Carga EngineControl para habilitar !echostart e !lobby que estão no ignis.py
    if not bot.get_cog("EngineControl"):
        await bot.add_cog(ignis.EngineControl(bot, fiery_embed, save_game_config, get_db_connection))

    if not bot.get_cog("Achievements"):
        await bot.add_cog(achievements.Achievements(bot, get_db_connection, fiery_embed))
    
    load_game_config()
    
    # Start the Guardian Task
    if not streak_guardian.is_running():
        streak_guardian.start()

    # Start the Top.gg Poster Task
    if not topgg_poster.is_running():
        topgg_poster.start()
    
    # FIXED: Re-registering with correct positional arguments for current class signature
    from ignis import LobbyView
    from autoignis import AutoLobbyView
    bot.add_view(LobbyView(None, 0)) # Manual Template
    bot.add_view(AutoLobbyView())     # Automated Template

    # --- REACTION ROLE PERSISTENCE RECOVERY ---
    try:
        with get_db_connection() as conn:
            # FIXED: Creation check added to solve 'no such table' error in logs
            conn.execute("CREATE TABLE IF NOT EXISTS reaction_roles (message_id INTEGER, emoji TEXT, role_id INTEGER)")
            rows = conn.execute("SELECT message_id, emoji, role_id FROM reaction_roles").fetchall()
            mappings = {}
            for row in rows:
                m_id = row['message_id']
                if m_id not in mappings: mappings[m_id] = {}
                mappings[m_id][row['emoji']] = row['role_id']
            
            # STARTUP SHIELD: Prevent import/view failure from blocking boot
            try:
                from reactionrole import ReactionRoleView, DesignerLobby
                bot.add_view(DesignerLobby())
                for m_id, data in mappings.items():
                    bot.add_view(ReactionRoleView(data), message_id=m_id)
            except Exception as e:
                print(f"⚠️ LOG: Reaction Role recovery bypassed (Broken View): {e}")
                
        print(f"📊 PERSISTENCE: {len(mappings)} Reaction Role protocols synchronized.")
    except Exception as e:
        print(f"RR Recovery fail: {e}")

    # CARREGAMENTO AUTOMÁTICO DO ADMIN, CLASSES E EXTENSÕES
    # FIXED: Wrapped in individual try blocks to ensure one crash doesn't stop the economy commands
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

    # INDIVIDUAL SHIELDS FOR EVERY EXTENSION
    try:
        if not bot.get_cog("FieryExtensions"):
            await bot.load_extension("extensions")
    except Exception as e: print(f"Extension fail: {e}")

    try:
        if not bot.get_cog("FieryShip"):
            await bot.load_extension("ship")
    except Exception as e: print(f"Ship fail: {e}")

    try: await bot.load_extension("shop")
    except Exception as e: print(f"Shop fail: {e}")

    try: await bot.load_extension("collect")
    except Exception as e: print(f"Collect fail: {e}")

    try:
        await bot.load_extension("fight")
        print("✅ LOG: Fight System is ONLINE.")
    except Exception as e: print(f"Fight fail: {e}")

    try:
        await bot.load_extension("casino")
        print("✅ LOG: Casino System is ONLINE.")
    except Exception as e: print(f"Casino fail: {e}")
    
    try:
        await bot.load_extension("ask")
        print("✅ LOG: Ask System is ONLINE.")
    except Exception as e: print(f"Ask fail: {e}")

    try:
        await bot.load_extension("premium")
        print("✅ LOG: Premium System is ONLINE.")
    except Exception as e: print(f"Premium fail: {e}")

    try:
        if not bot.get_cog("AuditManager"):
            await bot.load_extension("audit")
            print("✅ LOG: Audit Manager is ONLINE.")
    except Exception as e: print(f"Audit fail: {e}")

    try:
        await bot.load_extension("thread")
        print("✅ LOG: Thread System is ONLINE.")
    except Exception as e: print(f"Thread fail: {e}")

    try:
        await bot.load_extension("levels")
        print("✅ LOG: Text Level System is ONLINE.")
    except Exception as e: print(f"Levels fail: {e}")

    try:
        if not bot.get_cog("AutoReact"):
            await bot.load_extension("react")
            print("✅ LOG: Auto-React System is ONLINE.")
    except Exception as e: print(f"React fail: {e}")

    try:
        if not bot.get_cog("Counting"):
            await bot.load_extension("counting")
            print("✅ LOG: Counting System is ONLINE.")
    except Exception as e: print(f"Counting fail: {e}")

    try:
        if not bot.get_cog("GuessNumber"):
            await bot.load_extension("guessnumber")
            print("✅ LOG: Guess Number System is ONLINE.")
    except Exception as e: print(f"GuessNumber fail: {e}")

    try:
        if not bot.get_cog("ConfessionSystem"):
            await bot.load_extension("confession")
            from confession import ConfessionSubmissionView
            conf_cog = bot.get_cog("ConfessionSystem")
            if conf_cog:
                main_mod = sys.modules['__main__']
                bot.add_view(ConfessionSubmissionView(main_mod, bot, conf_cog.review_channel_id))
            print("✅ LOG: Confession System is ONLINE.")
    except Exception as e: print(f"Confession fail: {e}")

    try:
        await bot.load_extension("reactionrole")
        print("✅ LOG: Reaction Role System is ONLINE.")
    except Exception as e: print(f"RR System fail: {e}")
    
    try:
        await bot.load_extension("autoignis")
        print("✅ LOG: Automated Ignis is ONLINE.")
    except Exception as e: print(f"AutoIgnis fail: {e}")

    try:
        if not bot.get_cog("HelperSystem"):
            await bot.load_extension("helper")
            print("✅ LOG: Helper System (Refresh Protocol) is ONLINE.")
    except Exception as e: print(f"Helper fail: {e}")
    
    await bot.change_presence(activity=discord.Game(name="EchoGames"))
    print(f"✅ LOG: {bot.user} is ONLINE using persistent DB at {DATABASE_PATH}.")
    print(f"📊 PERSISTENCE: Edition #8 | NSFW Mode: {nsfw_mode_active}")

@bot.event
async def on_message(message):
    if message.author.bot: 
        return

    # Process regular commands first
    await bot.process_commands(message)

    ctx = await bot.get_context(message)
    
    # MANDATORY ARCHITECTURAL FIX: 
    # If a command has NO Cog (None), it is a Main Core command (Work, Beg, etc.).
    # The previous logic hit an AttributeError when scanning 'ctx.command.cog_name' on a None object.
    if ctx.valid and ctx.command:
        # Check if it belongs to a Cog. If cog is None, it is a main.py native command.
        if ctx.command.cog is not None:
            try:
                admin_cogs = ["AdminSystem", "AuditManager", "ReactionRoleSystem"]
                if ctx.command.cog_name in admin_cogs:
                    admin_roles = ["Admin", "Moderator"]
                    is_staff = any(role.name in admin_roles for role in getattr(message.author, 'roles', []))
                    if not is_staff and not await bot.is_owner(message.author):
                        await message.reply(embed=fiery_embed("🚫 ACCESS DENIED", "Required: **ADMIN** or **MODERATOR**.", color=0xFF0000))
            except: pass

async def main():
    try:
        async with bot: await bot.start(TOKEN)
    except: pass
    finally:
        if not bot.is_closed(): await bot.close()

if __name__ == "__main__": asyncio.run(main())

STILL NOT WORK. !work, !beg, !flirt, !mystery, !experiment, !pimp and !cumcleaner are dead. FIX IT. KEEP EVERYTHING LINE BY LINE AND NO DELETATION OR OPTIMIZATION. just fix what you need. i think that the problem is in worknranks.py 13 arguments thing. 

RELOAD EVERYTHING I NEED TO SEE THE FINAL PRODUCT FOR BOTH CODES. 

THIS IS MY WORKNRANKS.PY:
import discord
import json
import os
import random
from datetime import datetime, timezone, timedelta

# SHARED CONFIGURATION
RANKS = ["Tribute", "Neophyte", "Slave", "Servant", "Thrall", "Vassal", "Initiate", "Follower", "Devotee", "Acolyte"] # (Extend as needed)
CLASSES = {
    "Dominant": {"bonus": "20% Flames", "desc": "Dictate the flow."},
    "Submissive": {"bonus": "25% XP", "desc": "Absorb the discipline."},
    "Switch": {"bonus": "14% Flames/XP", "desc": "Versatile pleasure."},
    "Exhibitionist": {"bonus": "40% Flames, -20% XP", "desc": "Pure display."}
}

# --- ECONOMY HANDLER ---
async def handle_work_command(ctx, bot, cmd_name, range_tuple, get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active):
    """Universal handler for Work, Beg, Flirt, etc."""
    user_id = ctx.author.id
    u = get_user(user_id)
    now = datetime.now(timezone.utc)
    
    # COOLDOWN CHECK (3 Hours)
    last_key = f"last_{cmd_name}"
    cooldown = timedelta(hours=3)
    
    if u[last_key]:
        last_time = datetime.fromisoformat(u[last_key])
        if now - last_time < cooldown:
            remaining = cooldown - (now - last_time)
            mins = int(remaining.total_seconds() / 60)
            return await ctx.send(embed=fiery_embed("COOLDOWN ACTIVE", f"❌ Your body requires rest. Return in **{mins} minutes**."))

    # PAYOUT CALCULATION
    min_f, max_f = range_tuple
    base_flames = random.randint(min_f, max_f)
    base_xp = random.randint(50, 200)

    # CLASS BONUSES
    if u['class'] == "Dominant": base_flames = int(base_flames * 1.20)
    elif u['class'] == "Exhibitionist": 
        base_flames = int(base_flames * 1.40)
        base_xp = int(base_xp * 0.80)
    elif u['class'] == "Submissive": base_xp = int(base_xp * 1.25)
    elif u['class'] == "Switch":
        base_flames = int(base_flames * 1.14)
        base_xp = int(base_xp * 1.14)

    # UPDATE LEDGER
    await update_user_stats_async(user_id, amount=base_flames, xp_gain=base_xp, source=cmd_name.capitalize())
    
    with get_db_connection() as conn:
        conn.execute(f"UPDATE users SET {last_key} = ? WHERE id = ?", (now.isoformat(), user_id))
        conn.commit()

    # RESPONSE
    lexicon_key = cmd_name.upper()
    response_text = random.choice(getattr(FieryLexicon, lexicon_key, ["You performed your duties."]))
    
    embed = fiery_embed(f"PROTOCOL: {cmd_name.upper()}", 
                        f"{response_text}\n\n"
                        f"💰 **Earned:** {base_flames:,} Flames\n"
                        f"🔥 **Experience:** +{base_xp} XP")
    
    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="work.jpg")
        embed.set_thumbnail(url="attachment://work.jpg")
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send(embed=embed)

# --- PROFILE HANDLER ---
async def handle_me_command(ctx, member, get_user, get_db_connection, fiery_embed, bot, RANKS, nsfw_mode_active):
    member = member or ctx.author
    u = get_user(member.id)
    with get_db_connection() as conn:
        wins_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE wins > ?", (u['wins'],)).fetchone()
        kills_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE kills > ?", (u['kills'],)).fetchone()
        wins_rank = wins_row['r'] if wins_row else "?"
        kills_rank = kills_row['r'] if kills_row else "?"
        
        duel_wins_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE duel_wins > ?", (u['duel_wins'],)).fetchone()
        duel_rank = duel_wins_row['r'] if duel_wins_row else "?"

        victims = conn.execute("""
            SELECT loser_id, win_count FROM duel_history 
            WHERE winner_id = ? ORDER BY win_count DESC LIMIT 5
        """, (member.id,)).fetchall()
    
    lvl = u['fiery_level']
    rank_name = RANKS[lvl-1] if lvl <= 100 else RANKS[-1]
    
    try: titles = json.loads(u['titles'])
    except: titles = []
    
    engine = bot.get_cog("IgnisEngine")
    if nsfw_mode_active and engine and engine.last_winner_id == member.id:
        titles.append("⛓️ ECHOGAMES LEAD 🔞")

    badge_display = " ".join(titles) if titles else "No badges yet."

    embed = discord.Embed(title=f"📜 {member.display_name}'s Dossier", color=0xFF0000)
    
    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
    else:
        embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(name="❤ Class", value=f"**{u['class']}**", inline=False)
    embed.add_field(name="🏅 Badges & Titles", value=badge_display, inline=False)
    embed.add_field(name="👜 Wallet", value=f"**Flames:** {u['balance']}\n**Global Level:** {u['level']} ({u['xp']} XP)", inline=True)
    embed.add_field(name="🔥 Echo Stats", value=f"**Level:** {lvl}\n**Rank:** {rank_name}\n**Total XP:** {u['fiery_xp']}", inline=True)
    
    combat = (f"🏆 **Wins:** {u['wins']} (Rank #{wins_rank})\n"
              f"⚔️ **Kills:** {u['kills']} (Rank #{kills_rank})\n"
              f"🫦 **Duel Wins:** {u['duel_wins']} (Rank #{duel_rank})\n"
              f"💀 **Deaths:** {u['deaths']}\n"
              f"🎮 **Games Played:** {u['games_played']}")
    embed.add_field(name="⚔️ Echo Hangrygames & Duels", value=combat, inline=False)
    
    if victims:
        v_lines = []
        for v in victims:
            v_member = ctx.guild.get_member(v['loser_id'])
            v_name = v_member.display_name if v_member else f"Unknown ({v['loser_id']})"
            v_lines.append(f"• **{v_name}**: {v['win_count']} times")
        embed.add_field(name="🎯 Top 5 Victims (Private Sessions)", value="\n".join(v_lines), inline=False)
    else:
        embed.add_field(name="🎯 Top 5 Victims (Private Sessions)", value="No one has submitted yet.", inline=False)

    owner_text = "Free Soul"
    if u['spouse']:
        owner_text = f"Bound to <@{u['spouse']}> (Married)"
    else:
        with get_db_connection() as conn:
            contract_data = conn.execute("SELECT dominant_id FROM contracts WHERE submissive_id = ?", (member.id,)).fetchone()
            if contract_data:
                owner_text = f"Bound to <@{contract_data['dominant_id']}> (Contract)"
    embed.add_field(name="🔒 Ownership Status", value=f"**{owner_text}**", inline=False)

    ach_cog = bot.get_cog("Achievements")
    if ach_cog:
        summary = ach_cog.get_achievement_summary(member.id)
        embed.add_field(name="🏅 Achievements", value=summary, inline=False)
    
    if os.path.exists("LobbyTopRight.jpg"):
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send(embed=embed)
