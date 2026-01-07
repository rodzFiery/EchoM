import discord
from discord.ext import commands
import random
import os
from datetime import datetime, timedelta, timezone

# The 100-Tier Rank List (PRESERVED)
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

# 🧬 EROTIC CLASSES DEFINITION (PRESERVED)
CLASSES = {
    "Dominant": {"bonus_flames": 1.20, "bonus_xp": 1.00, "desc": "20% more Flames from all rewards.", "icon": "⛓️"},
    "Submissive": {"bonus_flames": 1.00, "bonus_xp": 1.25, "desc": "25% more Experience (XP/FXP).", "icon": "🫦"},
    "Switch": {"bonus_flames": 1.15, "bonus_xp": 1.15, "desc": "15% more Flames and 15% more XP.", "icon": "🔄"},
    "Exhibitionist": {"bonus_flames": 1.40, "bonus_xp": 0.80, "desc": "40% more Flames, but 20% less XP.", "icon": "📸"}
}

async def handle_work_command(ctx, bot, cmd_name, reward_range, get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active):
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
    nsfw_mult = 2.0 if nsfw_mode_active else 1.0
    
    final_reward = int(base_reward * bonus * h_mult * nsfw_mult)
    
    msg = FieryLexicon.get_economy_msg(cmd_name, ctx.author.display_name, final_reward)
    
    embed = fiery_embed(cmd_name.upper(), f"{msg}\n\n⛓️ **Session Payout:** {final_reward}F\n🫦 **Total XP:** +50\n💳 **New Balance:** {user_upd['balance']}F", color=0xFF4500)
    file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
    await ctx.send(file=file, embed=embed)
