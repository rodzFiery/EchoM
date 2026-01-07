import discord
import random
import json
import os
from datetime import datetime, timezone

def calculate_item_bonuses(user_id, get_user, bot):
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

async def update_user_stats_async(user_id, amount, xp_gain, wins, kills, deaths, source, get_user, bot, get_db_connection, CLASSES, nsfw_mode_active, send_audit_log):
    user = get_user(user_id)
    u_class = user['class']
    
    ext = bot.get_cog("FieryExtensions")
    
    # --- ADDED: FUNCTIONAL STAT INTEGRATION ---
    u_prot, u_luck = calculate_item_bonuses(user_id, get_user, bot)
    
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
    if (final_amount) != 0 or final_xp > 0:
        await send_audit_log(user_id, final_amount, source, final_xp)
        
    for r_source, r_amount, r_xp in pending_rewards:
        await update_user_stats_async(user_id, r_amount, r_xp, 0, 0, 0, r_source, get_user, bot, get_db_connection, CLASSES, nsfw_mode_active, send_audit_log)

def update_user_stats(user_id, amount, xp_gain, wins, kills, deaths, get_user, CLASSES, get_db_connection):
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
