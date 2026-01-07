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

# The 100-Tier Rank List
RANKS = [
    "Unmarked", "Dormant", "Aware", "Stirring", "Curious", "Drawn", "Attuned", "Noticed", "Touched", "Opened",
    "Initiate", "Invited", "Observed", "Evaluated", "Selected", "Guided", "Oriented", "Accepted", "Entered", "Aligned",
    "Receptive", "Willing", "Softened", "Inclined", "Leaning", "Yielding", "Responsive", "Compliant", "Ready", "Offered",
    "Anchored", "Linked", "Tethered", "Bound", "Held", "Secured", "Settled", "Claimed", "Assigned", "Enclosed",
    "Conditioned", "Trained", "Adjusted", "Corrected", "Regulated", "Disciplined", "Rewritten", "Imprinted", "Shaped", "Programmed",
    "Restrained", "Directed", "Commanded", "Ordered", "Governed", "Managed", "Controlled", "Dominated", "Overruled", "Possessed",
    "Loyal", "Faithful", "Dedicated", "Devoted", "Invested", "Subscribed", "Sworn", "Consecrated", "Bound by Oath", "Living Oath",
    "Polished", "Refined", "Cultivated", "Perfected", "Harmonized", "Balanced", "Tempered", "Elevated", "Enhanced", "Idealized",
    "Shadow Rank", "Inner Circle", "Black Seal", "Velvet Chain", "Silent Order", "Crowned", "Exalted", "Absolute Trust", "Total Grant", "Supreme Bond",
    "Dark Ascendant", "Chosen Asset", "Perfect Control", "Living Property", "Total Surrender", "Velvet Sovereign", "Throne-Bound", "Eternal Possession", "Absolute Dominion", "Final Authority"
]

# 🧬 EROTIC CLASSES DEFINITION
CLASSES = {
    "Dominant": {"bonus_flames": 1.20, "bonus_xp": 1.00, "desc": "20% more Flames from all rewards.", "icon": "⛓️"},
    "Submissive": {"bonus_flames": 1.00, "bonus_xp": 1.25, "desc": "25% more Experience (XP/FXP).", "icon": "🫦"},
    "Switch": {"bonus_flames": 1.15, "bonus_xp": 1.15, "desc": "15% more Flames and 15% more XP.", "icon": "🔄"},
    "Exhibitionist": {"bonus_flames": 1.40, "bonus_xp": 0.80, "desc": "40% more Flames, but 20% less XP.", "icon": "📸"}
}

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

        # Quest Table (20 Daily, 20 Weekly)
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
            ("last_casino_slots", "TEXT"), ("last_casino_blackjack", "TEXT"), ("last_casino_roulette", "TEXT"), ("last_casino_dice", "TEXT"), # ADDED: Casino Tracker Columns
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

# --- NEW HELPER: ASSET STAT SCANNER ---
def calculate_item_bonuses(user_id):
    """ADDED: Calculates total Protection and Luck from owned Black Market assets."""
    user = get_user(user_id)
    try:
        titles = json.loads(user['titles'])
    except:
        return 0, 0
        
    total_prot = 0
    total_luck = 0
    
    shop_cog = bot.get_cog("Shop")
    if not shop_cog: 
        return 0, 0
    
    for item_name in titles:
        # Cross-references name with Shop MARKET_DATA via the scanner helper
        item_data, cat, tier = shop_cog.get_item_details(item_name)
        if item_data:
            if cat == "Houses": total_prot += item_data.get("prot", 0)
            if cat == "Pets": total_luck += item_data.get("luck", 0)
            
    return total_prot, total_luck

async def update_user_stats_async(user_id, amount=0, xp_gain=0, wins=0, kills=0, deaths=0, source="System"):
    user = get_user(user_id)
    u_class = user['class']
    
    ext = bot.get_cog("FieryExtensions")
    global nsfw_mode_active

    # --- ADDED: FUNCTIONAL STAT INTEGRATION ---
    u_prot, u_luck = calculate_item_bonuses(user_id)
    
    # --- ADDED: ANNIVERSARY MULTIPLIER LOGIC ---
    anni_mult = 1.0
    if user['spouse'] and user['marriage_date']:
        try:
            m_date = datetime.strptime(user['marriage_date'], "%Y-%m-%d")
            today = datetime.now()
            if m_date.day == today.day and m_date.month != today.month:
                anni_mult = 2.0 # Ping handled by ship.py, stats handled here
        except: pass

    # MULTIPLIERS: Legendary Heat + NSFW Time Double Bonus
    heat_mult = ext.heat_multiplier if ext else 1.0
    nsfw_mult = 2.0 if nsfw_mode_active else 1.0
    xp_heat_mult = 3.0 if (ext and ext.master_present) else 1.0 
    
    b_flames = CLASSES[u_class]['bonus_flames'] if u_class in CLASSES else 1.0
    b_xp = CLASSES[u_class]['bonus_xp'] if u_class in CLASSES else 1.0
    
    # ADDED: CRITICAL REWARD LOGIC (Pet Luck)
    # Every point of Luck increases the chance by 1% to double the base flames.
    luck_roll = random.randint(1, 100)
    final_luck_mult = 2.0 if luck_roll <= u_luck else 1.0
    
    final_amount = int(amount * b_flames * heat_mult * nsfw_mult * final_luck_mult * anni_mult)
    final_xp = int(xp_gain * b_xp * xp_heat_mult * nsfw_mult * anni_mult)

    # Buffer for recursive reward calls to prevent "Database is locked"
    pending_rewards = []
    tax_paid = 0

    # --- SQL TRANSACTION BLOCK ---
    with get_db_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO quests (user_id) VALUES (?)", (user_id,))
        
        # --- RELATIONSHIP PASSIVE INCOME LOGIC ---
        try:
            rel = conn.execute("SELECT * FROM relationships WHERE user_one = ? OR user_two = ?", (user_id, user_id)).fetchone()
            if rel and final_amount > 0:
                partner_id = rel['user_two'] if rel['user_one'] == user_id else rel['user_one']
                share_rate = rel['passive_income']
                if share_rate > 0:
                    partner_share = int(final_amount * share_rate)
                    conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (partner_share, partner_id))
                    # Log the passive gift to audit
                    await send_audit_log(partner_id, partner_share, f"Shared Income from Asset <@{user_id}>")
        except: pass

        # --- CONTRACT TAX LOGIC ---
        active_contract = conn.execute("SELECT * FROM contracts WHERE submissive_id = ?", (user_id,)).fetchone()
        if active_contract:
            expiry = datetime.fromisoformat(active_contract['expiry'])
            if datetime.now(timezone.utc) < expiry:
                if final_amount > 0:
                    tax_paid = int(final_amount * active_contract['tax_rate'])
                    final_amount -= tax_paid
                    conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (tax_paid, active_contract['dominant_id']))
                    # AUDIT FOR CONTRACT TAX
                    await send_audit_log(active_contract['dominant_id'], tax_paid, f"⛓️ Contract Tax: Extracted from <@{user_id}>")
            else:
                conn.execute("DELETE FROM contracts WHERE submissive_id = ?", (user_id,))
        
        # --- LEGENDARY BLOOD BOUNTY ---
        if kills > 0 and ext and ext.master_present:
             final_amount += 500 

        # --- QUEST REWARD INTEGRATION ---
        if source not in ["Daily Reward", "Weekly Reward"]:
            if kills > 0: 
                conn.execute("UPDATE quests SET d1 = d1 + ?, w2 = w2 + ? WHERE user_id = ?", (kills, kills, user_id))
                q = conn.execute("SELECT d1, w2 FROM quests WHERE user_id = ?", (user_id,)).fetchone()
                if q and q['d1'] == 1: pending_rewards.append(("Daily Reward", 250, 100))
                if q and q['w2'] == 25: pending_rewards.append(("Weekly Reward", 2000, 1000))

            if wins > 0: 
                conn.execute("UPDATE quests SET d6 = d6 + 1, w1 = w1 + 1 WHERE user_id = ?", (user_id,))
                q = conn.execute("SELECT d6, w1 FROM quests WHERE user_id = ?", (user_id,)).fetchone()
                if q and q['d6'] == 1: pending_rewards.append(("Daily Reward", 250, 100))
                if q and q['w1'] == 5: pending_rewards.append(("Weekly Reward", 2000, 1000))

            if source == "Work": 
                conn.execute("UPDATE quests SET d5 = d5 + 1, w5 = w5 + 1 WHERE user_id = ?", (user_id,))
                q = conn.execute("SELECT d5, w5 FROM quests WHERE user_id = ?", (user_id,)).fetchone()
                if q and q['d5'] == 5: pending_rewards.append(("Daily Reward", 250, 100))
                if q and q['w5'] == 30: pending_rewards.append(("Weekly Reward", 2000, 1000))

            if source == "Beg": 
                conn.execute("UPDATE quests SET d4 = d4 + 1, w15 = w15 + 1 WHERE user_id = ?", (user_id,))
                q = conn.execute("SELECT d4, w15 FROM quests WHERE user_id = ?", (user_id,)).fetchone()
                if q and q['d4'] == 5: pending_rewards.append(("Daily Reward", 250, 100))
                if q and q['w15'] == 20: pending_rewards.append(("Weekly Reward", 2000, 1000))

            if source == "Flirt": 
                conn.execute("UPDATE quests SET d11 = d11 + 1, w10 = w10 + 1 WHERE user_id = ?", (user_id,))
                q = conn.execute("SELECT d11, w10 FROM quests WHERE user_id = ?", (user_id,)).fetchone()
                if q and q['d11'] == 5: pending_rewards.append(("Daily Reward", 250, 100))
                if q and q['w10'] == 20: pending_rewards.append(("Weekly Reward", 2000, 1000))
            
            conn.execute("UPDATE quests SET d12 = d12 + 1, w6 = w6 + 1 WHERE user_id = ?", (user_id,))
            q_gen = conn.execute("SELECT d12, w6 FROM quests WHERE user_id = ?", (user_id,)).fetchone()
            if q_gen and q_gen['d12'] == 10: pending_rewards.append(("Daily Reward", 250, 100))
            if q_gen and q_gen['w6'] == 50: pending_rewards.append(("Weekly Reward", 2000, 1000))

        # --- UPDATE MAIN STATS ---
        if ext and amount > 0:
            ext.add_heat(0.5)

        new_xp = user['xp'] + final_xp
        new_level = user['level']
        while new_xp >= (new_level * 1000):
            new_xp -= (new_level * 1000)
            new_level += 1
            
        conn.execute("""UPDATE users SET balance = MAX(0, balance + ?), xp = ?, level = ?, 
                        wins = wins + ?, kills = kills + ?, deaths = deaths + ? 
                        WHERE id = ?""", 
                      (final_amount, new_xp, new_level, wins, kills, deaths, user_id))
        conn.execute("UPDATE global_stats SET total_kills = total_kills + ?, total_deaths = total_deaths + ? WHERE id = 1", (kills, deaths))
        conn.commit()

    # --- POST-TRANSACTION LOGS & RECURSION ---
    # The database connection is CLOSED here, allowing the next calls to succeed
    if (final_amount) != 0 or final_xp > 0:
        await send_audit_log(user_id, final_amount, source, final_xp)
        
    for r_source, r_amount, r_xp in pending_rewards:
        await update_user_stats_async(user_id, amount=r_amount, xp_gain=r_xp, source=r_source)

def update_user_stats(user_id, amount=0, xp_gain=0, wins=0, kills=0, deaths=0):
    user = get_user(user_id)
    u_class = user['class']
    b_flames = CLASSES[u_class]['bonus_flames'] if u_class in CLASSES else 1.0
    b_xp = CLASSES[u_class]['bonus_xp'] if u_class in CLASSES else 1.0
    
    final_amount = int(amount * b_flames)
    final_xp = int(xp_gain * b_xp)

    new_xp = user['xp'] + final_xp
    new_level = user['level']
    while new_xp >= (new_level * 1000):
        new_xp -= (new_level * 1000)
        new_level += 1
    with get_db_connection() as conn:
        conn.execute("""UPDATE users SET balance = MAX(0, balance + ?), xp = ?, level = ?, 
                        wins = wins + ?, kills = kills + ?, deaths = deaths + ? 
                        WHERE id = ?""", 
                      (final_amount, new_xp, new_level, wins, kills, deaths, user_id))
        conn.execute("UPDATE global_stats SET total_kills = total_kills + ?, total_deaths = total_deaths + ? WHERE id = 1", (kills, deaths))
        conn.commit()

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
async def handle_work_command(ctx, cmd_name, reward_range):
    # LEGENDARY BLACKOUT CHECK: Disable if lights are out
    ext = bot.get_cog("FieryExtensions")
    if ext and ext.is_blackout:
        return await ctx.send("🌑 **THE LIGHTS ARE OUT.** The machines are dead. You cannot work in the dark. Use `!search`!")

    user = get_user(ctx.author.id)
    now = datetime.now(timezone.utc)
    last_key = f"last_{cmd_name}"
    
    # FIX: Ensure dictionary key exists
    last_time_str = user[last_key] if last_key in user.keys() else None
    last = datetime.fromisoformat(last_time_str) if last_time_str else now - timedelta(hours=3)
    
    if now - last < timedelta(hours=3):
        wait = timedelta(hours=3) - (now - last)
        embed = fiery_embed("Exhaustion Protocol", f"❌ Your body is broken. You cannot perform **{cmd_name}** yet.\n\nRecovery time remaining: **{wait.seconds//3600}h {(wait.seconds//60)%60}m**.", color=0xFF0000)
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        return await ctx.send(file=file, embed=embed)

    base_reward = random.randint(reward_range[0], reward_range[1])
    await update_user_stats_async(ctx.author.id, amount=base_reward, xp_gain=50, source=cmd_name.capitalize())
    
    with get_db_connection() as conn:
        conn.execute(f"UPDATE users SET {last_key} = ? WHERE id = ?", (now.isoformat(), ctx.author.id))
        conn.commit()
    
    user_upd = get_user(ctx.author.id)
    u_class = user_upd['class']
    bonus = CLASSES[u_class]['bonus_flames'] if u_class in CLASSES else 1.0
    h_mult = ext.heat_multiplier if ext else 1.0
    global nsfw_mode_active
    nsfw_mult = 2.0 if nsfw_mode_active else 1.0
    
    final_reward = int(base_reward * bonus * h_mult * nsfw_mult)
    
    msg = FieryLexicon.get_economy_msg(cmd_name, ctx.author.display_name, final_reward)
    
    embed = fiery_embed(cmd_name.upper(), f"{msg}\n\n⛓️ **Session Payout:** {final_reward}F\n🫦 **Total XP:** +50\n💳 **New Balance:** {user_upd['balance']}F", color=0xFF4500)
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

@bot.command()
async def work(ctx): await handle_work_command(ctx, "work", (500, 750))
@bot.command()
async def beg(ctx): await handle_work_command(ctx, "beg", (500, 1500))
@bot.command()
async def cumcleaner(ctx): await handle_work_command(ctx, "cumcleaner", (800, 1800))
@bot.command()
async def pimp(ctx): await handle_work_command(ctx, "pimp", (800, 1600))
@bot.command()
async def experiment(ctx): await handle_work_command(ctx, "experiment", (500, 2000))
@bot.command()
async def mystery(ctx): await handle_work_command(ctx, "mystery", (100, 3000))
@bot.command()
async def flirt(ctx): await handle_work_command(ctx, "flirt", (700, 1800))

# ===== 6. CORE PERIODIC REWARDS SYSTEM (STREAK UPGRADE) =====

async def handle_periodic_reward(ctx, reward_type, min_amt, max_amt, xp_amt, cooldown_delta):
    user = get_user(ctx.author.id)
    now = datetime.now(timezone.utc)
    db_col = f"last_{reward_type}"
    streak_col = f"{reward_type}_streak"
    last_str = user[db_col]
    current_streak = user[streak_col] if user[streak_col] else 0
    
    last_time = datetime.fromisoformat(last_str) if last_str else now - (cooldown_delta + timedelta(seconds=1))
    
    # Check for Cooldown
    if now - last_time < cooldown_delta:
        remaining = cooldown_delta - (now - last_time)
        hours, remainder = divmod(int(remaining.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        embed = fiery_embed("DENIAL PROTOCOL", f"❌ Your **{reward_type}** tribute is not yet ripe for harvesting.\n\n*The Master demands patience. Return in:* **{hours}h {minutes}m**.", color=0xFF0000)
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        return await ctx.send(file=file, embed=embed)

    # Streak Reset Logic (Broken Toy)
    # If more than 2x cooldown has passed, user failed the discipline
    reset_limit = cooldown_delta * 2
    if now - last_time > reset_limit and last_str is not None:
        current_streak = 0
        reset_msg = f"⛓️ **STREAK RESET:** You failed your {reward_type} discipline. You have been punished; your streak is back to zero."
    else:
        current_streak += 1
        reset_msg = f"🔥 **STREAK ADVANCED:** Your consistency pleases the Red Room."

    # Multiplier: 5% extra per streak level
    streak_bonus = 1.0 + (current_streak * 0.05)
    base_reward = random.randint(min_amt, max_amt)
    streaked_reward = int(base_reward * streak_bonus)
    
    # Using the async updater to handle multipliers and audit logs
    await update_user_stats_async(ctx.author.id, amount=streaked_reward, xp_gain=xp_amt, source=f"{reward_type.capitalize()} Streak")
    
    with get_db_connection() as conn:
        conn.execute(f"UPDATE users SET {db_col} = ?, {streak_col} = ? WHERE id = ?", (now.isoformat(), current_streak, ctx.author.id))
        conn.commit()

    # Get updated balance for the embed
    user_after = get_user(ctx.author.id)
    
    # Sexualized Flavor messages
    flavor = {
        "daily": [
            "You kneel before the altar of greed. Here is your daily allowance, pet.", 
            "A daily taste of submission. Open wide for your reward.", 
            "The Master strokes your head as you claim your daily tribute."
        ],
        "weekly": [
            "A week of service. Your collar is fitting perfectly. Claim your weekly prize.", 
            "Seven days of chains. Seven days of hunger. Here is your weekly feast.", 
            "The Red Room grows warmer with your weekly consistency."
        ],
        "monthly": [
            "One month of total possession. You are becoming a masterwork.", 
            "Ascension is slow, but a month of discipline deserves a grand payment.", 
            "Thirty days of submission. The Master grants you the highest honors."
        ]
    }
    
    embed = fiery_embed(f"🎁 {reward_type.upper()} PROTOCOL SEALED", random.choice(flavor[reward_type]), color=0xFFD700)
    
    embed.add_field(name="💰 Harvested Flames", value=f"**+{streaked_reward}** Flames", inline=True)
    embed.add_field(name="💦 Neural Imprint", value=f"**+{xp_amt}** XP", inline=True)
    embed.add_field(name="🧬 Streak Status", value=f"**Current Streak:** {current_streak}\n**Bonus Multiplier:** x{streak_bonus:.2f}", inline=True)
    embed.add_field(name="📢 System Log", value=reset_msg, inline=False)
    embed.add_field(name="💳 Vault Balance", value=f"**{user_after['balance']:,}** Flames", inline=False)
    
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

@bot.command()
async def daily(ctx):
    await handle_periodic_reward(ctx, "daily", 400, 800, 150, timedelta(days=1))

@bot.command()
async def weekly(ctx):
    await handle_periodic_reward(ctx, "weekly", 2500, 5000, 1000, timedelta(days=7))

@bot.command()
async def monthly(ctx):
    await handle_periodic_reward(ctx, "monthly", 12000, 20000, 5000, timedelta(days=30))

@bot.command()
async def balance(ctx, member: discord.Member = None):
    target = member or ctx.author
    u = get_user(target.id)
    embed = fiery_embed(f"{target.display_name}'s Vault", f"💰 **Current Balance:** {u['balance']} Flames\n⛓️ **Class:** {u['class']}")
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)

# ===== 7. PROFILE, RANKING, TITLES & HELP =====
@bot.command()
async def me(ctx, member: discord.Member = None):
    member = member or ctx.author
    u = get_user(member.id)
    with get_db_connection() as conn:
        wins_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE wins > ?", (u['wins'],)).fetchone()
        kills_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE kills > ?", (u['kills'],)).fetchone()
        wins_rank = wins_row['r'] if wins_row else "?"
        kills_rank = kills_row['r'] if kills_row else "?"
        
        # --- ADDED: DUELIST RANK CALCULATION ---
        duel_wins_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE duel_wins > ?", (u['duel_wins'],)).fetchone()
        duel_rank = duel_wins_row['r'] if duel_wins_row else "?"

        # --- ADDED: TOP 5 VICTIMS LOGIC ---
        victims = conn.execute("""
            SELECT loser_id, win_count FROM duel_history 
            WHERE winner_id = ? ORDER BY win_count DESC LIMIT 5
        """, (member.id,)).fetchall()
    
    lvl = u['fiery_level']
    rank_name = RANKS[lvl-1] if lvl <= 100 else RANKS[-1]
    
    try: titles = json.loads(u['titles'])
    except: titles = []
    
    # Legend Lead Temp Display
    engine = bot.get_cog("IgnisEngine")
    global nsfw_mode_active
    if nsfw_mode_active and engine and engine.last_winner_id == member.id:
        titles.append("⛓️ HANGRYGAMES LEAD 🔞")

    badge_display = " ".join(titles) if titles else "No badges yet."

    embed = discord.Embed(title=f"<:FIERY_heart_devilred:1329474462365777920> {member.display_name}'s Dossier", color=0xFF0000)
    
    # Mandatory Image
    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
    else:
        embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(name="<:FIERY_ad_colours:1331585411637706833> Class", value=f"**{u['class']}**", inline=False)
    embed.add_field(name="<:FIERY_fp_engarde:1357452255447613651> Badges & Titles", value=badge_display, inline=False)
    embed.add_field(name=":handbag: Wallet", value=f"**Flames:** {u['balance']}\n**Global Level:** {u['level']} ({u['xp']} XP)", inline=True)
    embed.add_field(name="🔥 Fiery Stats", value=f"**Level:** {lvl}\n**Rank:** {rank_name}\n**Total XP:** {u['fiery_xp']}", inline=True)
    
    # UPDATED: Private Duel Stats added to Combat Recap
    combat = (f"🏆 **Arena Wins:** {u['wins']} (Rank #{wins_rank})\n"
              f"⚔️ **Arena Kills:** {u['kills']} (Rank #{kills_rank})\n"
              f"🫦 **Duel Wins:** {u['duel_wins']} (Rank #{duel_rank})\n"
              f"💀 **Arena Deaths:** {u['deaths']}\n"
              f"🎮 **Games Played:** {u['games_played']}")
    embed.add_field(name="⚔️ Fiery Hangrygames & Duels", value=combat, inline=False)
    
    # --- ADDED: VICTIM LIST DISPLAY ---
    if victims:
        v_lines = []
        for v in victims:
            v_member = ctx.guild.get_member(v['loser_id'])
            v_name = v_member.display_name if v_member else f"Unknown ({v['loser_id']})"
            v_lines.append(f"• **{v_name}**: {v['win_count']} times")
        embed.add_field(name="⛓️ Top 5 Victims (Private Sessions)", value="\n".join(v_lines), inline=False)
    else:
        embed.add_field(name="⛓️ Top 5 Victims (Private Sessions)", value="No one has submitted yet.", inline=False)

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

# --- FIERY GUIDE INJECTION START ---
@bot.command()
async def fiery(ctx):
    """Protocol Zero: The Complete Fiery Bot Manual."""
    
    # Tier 1: Identity & Classes
    emb1 = fiery_embed("FIERY PROTOCOL: THE SLAVE HIERARCHY 🧬", 
        "### 🧬 SECTION I: IDENTITY & ROLES\n"
        "*Choose your path or remain a nameless tribute in the pits.*\n\n"
        "🫦 `!setclass` — Claim your erotic path and bonuses.\n"
        "📑 `!me` — Review your Dossier, Rank, and Master's Mark.\n"
        "🏅 `!achievements` — Inspect your scars and milestones.\n"
        "📊 `!ranking` — The hierarchy of elite sinners.\n\n"
        "**Available Roles:**\n"
        "⛓️ **Dominant:** +20% Flames. Dictate the flow.\n"
        "🫦 **Submissive:** +25% XP/FXP. Absorb the discipline.\n"
        "🔄 **Switch:** +15% Flames/XP. Versatile pleasure.\n"
        "📸 **Exhibitionist:** +40% Flames, -20% XP. Pure display.")

    # Tier 2: Arena & Combat
    emb2 = fiery_embed("FIERY PROTOCOL: THE ARENA & PRIVATE PLEASURES ⚔️", 
        "### ⚔️ SECTION II: COMBAT & SUBMISSION\n"
        "*Procedural 1v1 slaughter or intimate private rivalry.*\n\n"
        "🔥 `!fierystart` — Open the pit for new registrations.\n"
        "⛓️ `!lobby` — View the souls currently awaiting their fate.\n"
        "🔞 `!fuck <user>` — Challenge an asset to a private BDSM duel.\n"
        "📣 `!@user` — (Winner) Force a **FLASH** decree on your victim.\n"
        "📸 `!flash` — Review the gallery of recent public humiliations.\n"
        "🆘 `!reset_arena` — Admin override for locked cages.")

    # Tier 3: Economy & Labor
    emb3 = fiery_embed("FIERY PROTOCOL: LABOR & TRIBUTES ⛓️", 
        "### 💰 SECTION III: HARVESTING FLAMES\n"
        "*The Red Room runs on effort and obedience. 3h cooldowns apply.*\n\n"
        "👢 `!work` — Polish boots and serve the elite. (500-750F)\n"
        "🛐 `!beg` — Grovel at the feet of power. (500-1500F)\n"
        "🫦 `!flirt` — Seduce the lounge patrons. (700-1800F)\n"
        "🧴 `!cumcleaner` — Sanitize the aftermath. (800-1800F)\n"
        "🧪 `!experiment` — Volunteer for sensory trials. (500-2000F)\n"
        "🎭 `!pimp` — Manage assets and contracts. (800-1600F)\n"
        "🎲 `!mystery` — High-risk sensory gamble. (100-3000F)\n\n"
        "**Recurrent Rewards:** `!daily`, `!weekly`, `!monthly` claims.")

    # Tier 4: Black Market & Contracts
    emb4 = fiery_embed("FIERY PROTOCOL: THE VAULT & BONDS 💍", 
        "### 🛒 SECTION IV: THE BLACK MARKET\n"
        "*Prestige assets, soul-binding items, and legacy artifacts.*\n\n"
        "🏰 `!shop` — Browse the boutique (Houses, Pets, Rings, Toys).\n"
        "💰 `!buy` — Finalize your claim on a Supreme asset.\n"
        "🏛️ `!hall` — The Museum of Tributes & All-Time records.\n"
        "❤️ `!ship` — Check compatibility with another soul (+69% bonus).\n"
        "🔭 `!matchmaking` — The Voyeur scans for high-tension pairs.\n\n"
        "### 💍 SECTION V: CONTRACTS & OWNERSHIP\n"
        "📜 `!contract <user> <price>` — Offer a 24-hour collar of service.\n"
        "✅ `!accept` — Seal the bond. *Owners take 20% tax automatically.*")

    # Tier 5: World Events & Master Ops
    emb5 = fiery_embed("FIERY PROTOCOL: THE MASTER'S LEDGER 🎰", 
        "### 🎰 SECTION VI: CASINO & GAMBLING\n"
        "*High-stakes protocols for those who risk it all.*\n\n"
        "🍒 `!slots` — Triple Pleasure Slots (Jackpot x50).\n"
        "🃏 `!blackjack` — Duel the Dealer for the high ground.\n"
        "🎡 `!roulette` — The Wheel of Lust (Numbers pay x35).\n"
        "🎲 `!dice` — Guess the sum of the toss (Reward x8).\n\n"
        "### 🛠️ SECTION VII: SYSTEM PROTOCOLS\n"
        "📜 `!quests` — Progress on 40 active demands.\n"
        "👁️ `!gallery` — Server tension and champion metrics.\n"
        "🔦 `!search` — Recover items during **BLACKOUT** events.\n"
        "📟 `!ping` — Measure neural latency to the Red Room.")

    # Sending the guide as a sequence of high-quality embeds
    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        for e in [emb1, emb2, emb3, emb4, emb5]:
            e.set_thumbnail(url="attachment://LobbyTopRight.jpg")
            await ctx.send(embed=e)
    else:
        for e in [emb1, emb2, emb3, emb4, emb5]:
            await ctx.send(embed=e)

# --- FIERY GUIDE INJECTION END ---

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

@bot.command()
async def hall(ctx):
    """The Museum of Tributes: Global all-time records."""
    with get_db_connection() as conn:
        stats = conn.execute("SELECT SUM(wins) as total_wins, SUM(kills) as total_kills, SUM(deaths) as total_deaths FROM users").fetchone()
        most_wealthy = conn.execute("SELECT id, balance FROM users ORDER BY balance DESC LIMIT 1").fetchone()
        bloodiest = conn.execute("SELECT id, first_bloods FROM users ORDER BY first_bloods DESC LIMIT 1").fetchone()

    desc = "### 🏛️ THE HALL OF TRIBUTES\n"
    desc += f"⚔️ **All-Time Arena Wins:** {stats['total_wins'] or 0}\n"
    desc += f"💀 **All-Time Executions:** {stats['total_kills'] or 0}\n"
    desc += f"⚰️ **Total Tributes Fallen:** {stats['total_deaths'] or 0}\n\n"
    
    if most_wealthy:
        desc += f"💰 **Richest Sinner:** <@{most_wealthy['id']}> ({most_wealthy['balance']:,} Flames)\n"
    if bloodiest:
        desc += f"🩸 **Most Humiliated (FB):** <@{bloodiest['id']}> ({bloodiest['first_bloods']} times)\n"

    embed = fiery_embed("LEGACY MUSEUM", desc, color=0xFFD700)
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

@bot.command()
async def ranking(ctx):
    with get_db_connection() as conn:
        top = conn.execute("SELECT id, games_played, wins, kills, first_bloods FROM users WHERE games_played > 0 ORDER BY wins DESC, kills DESC LIMIT 10").fetchall()
    if not top: 
        embed = fiery_embed("Leaderboard", "No records yet.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        return await ctx.send(file=file, embed=embed)

    lines = []
    for i, row in enumerate(top, 1):
        m = ctx.guild.get_member(row['id'])
        name = m.display_name if m else f"Unknown({row['id']})"
        lines.append(f"**#{i} {name}**\n└ 🎮:{row['games_played']} | 🏆:{row['wins']} | ⚔️:{row['kills']} | 🩸:{row['first_bloods']}")
    
    embed = fiery_embed("LEADERBOARD", "\n".join(lines), color=0xFFD700)
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

# --- GLOBAL STREAK LEADERBOARD COMMAND START ---
@bot.command()
async def streaks(ctx):
    """GLOBAL STREAK LEADERBOARD: Displays the elite disciplined assets across Daily, Weekly, and Monthly tiers."""
    with get_db_connection() as conn:
        top_daily = conn.execute("SELECT id, daily_streak FROM users WHERE daily_streak > 0 ORDER BY daily_streak DESC LIMIT 5").fetchall()
        top_weekly = conn.execute("SELECT id, weekly_streak FROM users WHERE weekly_streak > 0 ORDER BY weekly_streak DESC LIMIT 5").fetchall()
        top_monthly = conn.execute("SELECT id, monthly_streak FROM users WHERE monthly_streak > 0 ORDER BY monthly_streak DESC LIMIT 5").fetchall()

    embed = fiery_embed("NEURAL PERSISTENCE: GLOBAL SINNER DISCIPLINE", 
                        "The Master tracks every cycle of submission. Consistency is the only path to the throne.")

    def format_rank(rows, streak_type):
        if not rows: return "The pit is silent in this tier."
        lines = []
        for i, row in enumerate(rows, 1):
            member = ctx.guild.get_member(row['id'])
            name = member.display_name if member else f"Asset {row['id']}"
            icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "⛓️"
            bonus = int(row[f'{streak_type}_streak'] * 5)
            lines.append(f"{icon} **{name}**: {row[f'{streak_type}_streak']} counts (+{bonus}% bonus)")
        return "\n".join(lines)

    embed.add_field(name="🫦 Daily Submission Streaks", value=format_rank(top_daily, "daily"), inline=False)
    embed.add_field(name="⛓️ Weekly Service Streaks", value=format_rank(top_weekly, "weekly"), inline=False)
    embed.add_field(name="👑 Monthly Absolute Devotion", value=format_rank(top_monthly, "monthly"), inline=False)

    u = get_user(ctx.author.id)
    footer_text = f"Your Discipline: D:{u['daily_streak']} | W:{u['weekly_streak']} | M:{u['monthly_streak']}"
    embed.set_footer(text=footer_text + " | 🔞 FIERY HANGRYGAMES EDITION 🔞")

    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)
# --- GLOBAL STREAK LEADERBOARD COMMAND END ---

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
