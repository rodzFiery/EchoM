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
    
    # Safely handle the cooldown check from the Row object
    try:
        last_val = u[last_key]
    except KeyError:
        last_val = None

    if last_val:
        last_time = datetime.fromisoformat(last_val)
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

    # MANDATORY BRIDGE: Filling all 13 arguments required by prizes.py
    # Args: user_id, amount, xp_gain, wins, kills, deaths, source, get_user_func, bot_obj, db_func, class_dict, nsfw, audit_func
    # send_audit_log is handled via the wrapper in main.py
    await update_user_stats_async(
        user_id, 
        base_flames, 
        base_xp, 
        0, 0, 0, 
        cmd_name.capitalize(),
        get_user,
        bot,
        get_db_connection,
        CLASSES,
        nsfw_mode_active,
        None # Audit log is inherited from main's global scope
    )
    
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
