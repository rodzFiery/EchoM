import discord
import random
import os
from datetime import datetime, timedelta, timezone

async def handle_periodic_reward(ctx, reward_type, min_amt, max_amt, xp_amt, cooldown_delta, get_user, update_user_stats_async, fiery_embed, get_db_connection):
    user = get_user(ctx.author.id)
    now = datetime.now(timezone.utc)
    db_col = f"last_{reward_type}"
    streak_col = f"{reward_type}_streak"
    
    # FIX: Safe access to sqlite3.Row data
    last_str = user[db_col] if db_col in user.keys() else None
    current_streak = user[streak_col] if streak_col in user.keys() and user[streak_col] else 0
    
    last_time = datetime.fromisoformat(last_str) if last_str else now - (cooldown_delta + timedelta(seconds=1))
    
    # Check for Cooldown
    if now - last_time < cooldown_delta:
        remaining = cooldown_delta - (now - last_time)
        hours, remainder = divmod(int(remaining.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        embed = fiery_embed("DENIAL PROTOCOL", f"❌ Your **{reward_type}** tribute is not yet ripe for harvesting.\n\n*The Master demands patience. Return in:* **{hours}h {minutes}m**.", color=0xFF0000)
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            return await ctx.send(file=file, embed=embed)
        return await ctx.send(embed=embed)

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
    
    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send(embed=embed)
