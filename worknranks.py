import discord
import json
import os
import random
from datetime import datetime, timezone, timedelta

# SHARED CONFIGURATION
RANKS = ["Tribute", "Neophyte", "Slave", "Servant", "Thrall", "Vassal", "Initiate", "Follower", "Devotee", "Acolyte"]
CLASSES = {
    "Dominant": {"bonus": "20% Flames", "desc": "Dictate the flow."},
    "Submissive": {"bonus": "25% XP", "desc": "Absorb the discipline."},
    "Switch": {"bonus": "14% Flames/XP", "desc": "Versatile pleasure."},
    "Exhibitionist": {"bonus": "40% Flames, -20% XP", "desc": "Pure display."}
}

# --- REBUILT ECONOMY HANDLER (ALIGNED) ---
async def handle_work_command(ctx, bot, cmd_name, range_tuple, get_user, update_user_stats_async, fiery_embed, get_db_connection, FieryLexicon, nsfw_mode_active):
    """Universal handler for Work, Beg, Flirt, etc."""
    user_id = ctx.author.id
    u = get_user(user_id)
    now = datetime.now(timezone.utc)
    
    # COOLDOWN CHECK (3 Hours)
    last_key = f"last_{cmd_name}"
    cooldown = timedelta(hours=3)
    
    try:
        # FIXED: Safety get to prevent KeyError on fresh accounts
        last_val = u.get(last_key)
    except (KeyError, AttributeError):
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
    # FIXED: Added safety check for missing class data
    user_class = u.get('class', 'None')
    if user_class == "Dominant": base_flames = int(base_flames * 1.20)
    elif user_class == "Exhibitionist": 
        base_flames = int(base_flames * 1.40)
        base_xp = int(base_xp * 0.80)
    elif user_class == "Submissive": base_xp = int(base_xp * 1.25)
    elif user_class == "Switch":
        base_flames = int(base_flames * 1.14)
        base_xp = int(base_xp * 1.14)

    # --- CARD MASTERY PASSIVE INTEGRATION ---
    with get_db_connection() as conn:
        # Check for Category Masteries (+5% each)
        category_masteries = conn.execute("SELECT COUNT(*) FROM card_mastery WHERE user_id = ? AND mastery_key LIKE 'cat_%'", (user_id,)).fetchone()[0]
        if category_masteries > 0:
            multiplier = 1 + (category_masteries * 0.05)
            base_flames = int(base_flames * multiplier)
        
        # Check for Absolute Mastery (1.5x Global Multiplier)
        absolute_master = conn.execute("SELECT 1 FROM card_mastery WHERE user_id = ? AND mastery_key = 'absolute_master'", (user_id,)).fetchone()
        if absolute_master:
            base_flames = int(base_flames * 1.5)

    # MANDATORY 13-ARGUMENT BRIDGE
    # Filling every slot required by prizes.py to prevent TypeError
    await update_user_stats_async(
        user_id,            # 1: User ID
        base_flames,        # 2: Amount
        base_xp,            # 3: XP Gain
        0,                  # 4: Wins
        0,                  # 5: Kills
        0,                  # 6: Deaths
        cmd_name.capitalize(), # 7: Source
        get_user,           # 8: get_user_func
        bot,                # 9: bot_obj
        get_db_connection,  # 10: db_func
        CLASSES,            # 11: class_dict
        nsfw_mode_active,   # 12: nsfw flag
        None                # 13: audit_func
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
    
    # FIXED: Added safety getters for all user stats to prevent profile crashes
    u_wins = u.get('wins', 0)
    u_kills = u.get('kills', 0)
    u_duel_wins = u.get('duel_wins', 0)
    u_balance = u.get('balance', 0)
    u_level = u.get('level', 1)
    u_xp = u.get('xp', 0)
    u_fiery_xp = u.get('fiery_xp', 0)
    u_deaths = u.get('deaths', 0)
    u_games_played = u.get('games_played', 0)
    u_class = u.get('class', 'None')

    with get_db_connection() as conn:
        wins_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE wins > ?", (u_wins,)).fetchone()
        kills_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE kills > ?", (u_kills,)).fetchone()
        wins_rank = wins_row['r'] if wins_row else "?"
        kills_rank = kills_row['r'] if kills_row else "?"
        
        duel_wins_row = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE duel_wins > ?", (u_duel_wins,)).fetchone()
        duel_rank = duel_wins_row['r'] if duel_wins_row else "?"

        victims = conn.execute("""
            SELECT loser_id, win_count FROM duel_history 
            WHERE winner_id = ? ORDER BY win_count DESC LIMIT 5
        """, (member.id,)).fetchall()
    
    lvl = u.get('fiery_level', 1)
    rank_name = RANKS[lvl-1] if lvl <= 100 else RANKS[-1]
    
    try: titles = json.loads(u.get('titles', '[]'))
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

    embed.add_field(name="❤ Class", value=f"**{u_class}**", inline=False)
    embed.add_field(name="🏅 Badges & Titles", value=badge_display, inline=False)
    embed.add_field(name="👜 Wallet", value=f"**Flames:** {u_balance}\n**Global Level:** {u_level} ({u_xp} XP)", inline=True)
    embed.add_field(name="🔥 Echo Stats", value=f"**Level:** {lvl}\n**Rank:** {rank_name}\n**Total XP:** {u_fiery_xp}", inline=True)
    
    combat = (f"🏆 **Wins:** {u_wins} (Rank #{wins_rank})\n"
              f"⚔️ **Kills:** {u_kills} (Rank #{kills_rank})\n"
              f"🫦 **Duel Wins:** {u_duel_wins} (Rank #{duel_rank})\n"
              f"💀 **Deaths:** {u_deaths}\n"
              f"🎮 **Games Played:** {u_games_played}")
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
    if u.get('spouse'):
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
