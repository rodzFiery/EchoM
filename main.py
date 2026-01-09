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
                print(f"Premium activated via Webhook for ID {user_id}")
                
                # ADICIONADO: Notificação em tempo real para o usuário no Discord
                user = bot.get_user(int(user_id))
                if user:
                    # Usamos a loop do bot para enviar a mensagem a partir da thread do Flask
                    bot.loop.create_task(user.send(embed=fiery_embed("PREMIUM ACTIVATED", 
                        f"Greetings, {user.mention}. Your payment for **{plan_name}** was processed.\n"
                        f"All elite privileges have been granted to your account.", color=0xFFD700)))
            except Exception as e:
                print(f"Webhook failed: {e}")
    return "OK", 200

def run_web_server():
    # O Railway usa a porta 8080 por padrão para Networking Público
    port = int(os.environ.get("PORT", 8080))
    try:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Web Server bypass: {e}")

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

    import aiohttp
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    print(f"TOP.GG synchronized: {len(bot.guilds)} servers.")
        except Exception as e:
            print(f"TOP.GG Connection error: {e}")

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

# ===== 6. CORE PERIODIC REWARDS SYSTEM =====
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
    embed = fiery_embed(f"{target.display_name}'s Vault", f"Current Balance: {u['balance']} Flames\nClass: {u['class']}")
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

# ===== 7. PROFILE, RANKING, TITLES & HELP =====
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
async def echo(ctx):
    await social_module.handle_fiery_guide(ctx, fiery_embed)

@bot.command()
async def streaks(ctx):
    await social_module.handle_streaks_command(ctx, get_db_connection, get_user, fiery_embed)

# ===== 🛒 BLACK MARKET & FAVOR =====
@bot.command()
async def buytitle(ctx, *, title_choice: str = None):
    shop = bot.get_cog("ShopSystem")
    if not shop:
        return await ctx.send(embed=fiery_embed("Market Error", "The Black Market is closed."))
    pass

@bot.command()
async def favor(ctx):
    cost = 5000000
    user = get_user(ctx.author.id)
    ext = bot.get_cog("FieryExtensions")
    if user['balance'] < cost:
        return await ctx.send(embed=fiery_embed("Favor Rejected", f"You need {cost:,} Flames."))
    if not ext:
        return await ctx.send(embed=fiery_embed("System Offline", "The Master is unavailable."))
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (cost, ctx.author.id))
        conn.commit()
    await ext.activate_peak_heat(ctx)
    await ctx.send(embed=fiery_embed("MASTER'S FAVOR", "PEAK HEAT IS NOW ACTIVE!", color=0xFF0000))

# ===== 9. SYSTEM INTEGRATION =====
@bot.command()
async def ping(ctx):
    await ctx.send(embed=fiery_embed("Neural Sync", f"Pong! Latency: {round(bot.latency * 1000)}ms"))

@bot.command()
async def togglealerts(ctx):
    u = get_user(ctx.author.id)
    new_status = 0 if u['streak_alerts'] == 1 else 1
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET streak_alerts = ? WHERE id = ?", (new_status, ctx.author.id))
        conn.commit()
    await ctx.send(embed=fiery_embed("ALERT PROTOCOL UPDATED", f"Status: {'ENABLED' if new_status == 1 else 'DISABLED'}"))

@tasks.loop(hours=1)
async def streak_guardian():
    now = datetime.now(timezone.utc)
    channel = bot.get_channel(STREAK_ALERTS_CHANNEL_ID)
    if not channel: return
    with get_db_connection() as conn:
        users = conn.execute("SELECT id, last_daily, last_weekly, last_monthly, daily_streak, weekly_streak, monthly_streak, streak_alerts FROM users").fetchall()
        for u in users:
            if u['streak_alerts'] == 0: continue
            pass

@bot.event
async def on_ready():
    print("--- STARTING SYSTEM INITIALIZATION ---")
    if not bot.get_cog("IgnisEngine"):
        await bot.add_cog(ignis.IgnisEngine(bot, update_user_stats_async, get_user, fiery_embed, get_db_connection, RANKS, CLASSES, AUDIT_CHANNEL_ID))
    if not bot.get_cog("EngineControl"):
        await bot.add_cog(ignis.EngineControl(bot, fiery_embed, save_game_config, get_db_connection))
    if not bot.get_cog("Achievements"):
        await bot.add_cog(achievements.Achievements(bot, get_db_connection, fiery_embed))
    
    load_game_config()
    if not streak_guardian.is_running(): streak_guardian.start()
    if not topgg_poster.is_running(): topgg_poster.start()
    
    # Load extensions
    exts = ["admin", "classes", "extensions", "ship", "shop", "collect", "fight", "casino", "ask", "premium"]
    for ext in exts:
        try:
            await bot.load_extension(ext)
        except Exception as e:
            print(f"Extension Error {ext}: {e}")

    await bot.change_presence(activity=discord.Game(name="Fiery Hangrygames"))
    print(f"ONLINE: {bot.user} | PERSISTENCE: Edition #8")

@bot.event
async def on_message(message):
    if message.author.bot: return
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.invoke(ctx)
    else:
        await bot.process_commands(message)

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
