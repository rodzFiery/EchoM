import discord
import json
import os
import random
from datetime import datetime, timezone

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

    embed = discord.Embed(title=f"😻 {member.display_name}'s Dossier", color=0xFF0000)
    
    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
    else:
        embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(name="❤ Class", value=f"**{u['class']}**", inline=False)
    embed.add_field(name="🏅 Badges & Titles", value=badge_display, inline=False)
    embed.add_field(name=":handbag: Wallet", value=f"**Flames:** {u['balance']}\n**Global Level:** {u['level']} ({u['xp']} XP)", inline=True)
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

async def handle_ranking_command(ctx, get_db_connection, fiery_embed):
    with get_db_connection() as conn:
        top = conn.execute("SELECT id, games_played, wins, kills, first_bloods FROM users WHERE games_played > 0 ORDER BY wins DESC, kills DESC LIMIT 10").fetchall()
    if not top: 
        embed = fiery_embed("Leaderboard", "No records yet.")
        return await ctx.send(embed=embed)

    lines = []
    for i, row in enumerate(top, 1):
        m = ctx.guild.get_member(row['id'])
        name = m.display_name if m else f"Unknown({row['id']})"
        lines.append(f"**#{i} {name}**\n└ 🎮:{row['games_played']} | 🏆:{row['wins']} | ⚔️:{row['kills']} | 🩸:{row['first_bloods']}")
    
    embed = fiery_embed("LEADERBOARD", "\n".join(lines), color=0xFFD700)
    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send(embed=embed)

async def handle_hall_command(ctx, get_db_connection, fiery_embed):
    with get_db_connection() as conn:
        stats = conn.execute("SELECT SUM(wins) as total_wins, SUM(kills) as total_kills, SUM(deaths) as total_deaths FROM users").fetchone()
        most_wealthy = conn.execute("SELECT id, balance FROM users ORDER BY balance DESC LIMIT 1").fetchone()
        bloodiest = conn.execute("SELECT id, first_bloods FROM users ORDER BY first_bloods DESC LIMIT 1").fetchone()

    desc = "### 🏛️ THE HALL OF TRIBUTES\n"
    desc += f"⚔️ **All-Time Echo Hangrygames Wins:** {stats['total_wins'] or 0}\n"
    desc += f"💀 **All-Time Executions:** {stats['total_kills'] or 0}\n"
    desc += f"⚰️ **Total Tributes Fallen:** {stats['total_deaths'] or 0}\n\n"
    
    if most_wealthy:
        desc += f"💰 **Richest Sinner:** <@{most_wealthy['id']}> ({most_wealthy['balance']:,} Flames)\n"
    if bloodiest:
        desc += f"🩸 **Most First bloods:** <@{bloodiest['id']}> ({bloodiest['first_bloods']} times)\n"

    embed = fiery_embed("LEGACY MUSEUM", desc, color=0xFFD700)
    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send(embed=embed)

async def handle_fiery_guide(ctx, fiery_embed):
    emb1 = fiery_embed("ECHO PROTOCOL: THE SLAVE HIERARCHY 💫", 
        "### 🧬 SECTION I: IDENTITY & ROLES\n"
        "*Choose your path or remain a nameless tribute in the pits.*\n\n"
        "🫦 `!setclass` — Claim your erotic path and bonuses.\n"
        "📑 `!me` — Review your Dossier, Rank, and Master's Mark.\n"
        "🏅 `!achievements` — Inspect your scars and milestones.\n"
        "📊 `!ranking` — The hierarchy of elite sinners.\n\n"
        "**Available Roles:**\n"
        "⛓️ **Dominant:** +20% Flames. Dictate the flow.\n"
        "🫦 **Submissive:** +25% XP. Absorb the discipline.\n"
        "🔄 **Switch:** +14% Flames/XP. Versatile pleasure.\n"
        "📸 **Exhibitionist:** +40% Flames, -20% XP. Pure display.")

    emb2 = fiery_embed("ECHO PROTOCOL: THE ARENA & PRIVATE PLEASURES ⚔️", 
        "### ⚔️ SECTION II: COMBAT & SUBMISSION\n"
        "*Procedural 1v1 slaughter or intimate private rivalry.*\n\n"
        "🔥 `!echostart` — Open the pit for new registrations.\n"
        "⛓️ `!lobby` — View the souls currently awaiting their fate.\n"
        "🔞 `!fuck <user>` — Challenge an member to a private BDSM duel.\n"
        "📣 `!@user` — (Winner) Force a **FLASH** decree on your victim.\n")

    emb3 = fiery_embed("ECHO PROTOCOL: LABOR & TRIBUTES 💘", 
        "### 💰 SECTION III: HARVESTING FLAMES\n"
        "*The Red Room runs on effort and obedience. 3h cooldowns apply.*\n\n"
        "👢 `!work` — Polish boots and serve the elite. (500-750F)\n"
        "🛐 `!beg` — Grovel at the feet of power. (500-1500F)\n"
        "💘 `!flirt` — Seduce the lounge patrons. (700-1800F)\n"
        "🧴 `!cumcleaner` — Sanitize the aftermath. (800-1800F)\n"
        "🧪 `!experiment` — Volunteer for sensory trials. (500-2000F)\n"
        "🎭 `!pimp` — Manage assets and contracts. (800-1600F)\n"
        "🎲 `!mystery` — High-risk sensory gamble. (100-3000F)\n\n"
        "**Recurrent Rewards:** `!daily`, `!weekly`, `!monthly` claims.")

    emb4 = fiery_embed("ECHO PROTOCOL: THE VAULT & BONDS 💍", 
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

    emb5 = fiery_embed("ECHO PROTOCOL: THE MASTER'S LEDGER 🎰", 
        "### 🎰 SECTION VI: CASINO & GAMBLING\n"
        "*High-stakes protocols for those who risk it all.*\n\n"
        "🍒 `!slots` — Triple Pleasure Slots (Jackpot x50).\n"
        "🃏 `!blackjack` — Duel the Dealer for the high ground.\n"
        "🎡 `!roulette` — The Wheel of Lust (Numbers pay x35).\n"
        "🎲 `!dice` — Guess the sum of the toss (Reward x8).\n\n"
        "### 🛠️ SECTION VII: SYSTEM PROTOCOLS\n"
        "📜 `!quests` — Progress on 40 active demands.\n"
        "👁️ `!gallery` — Server tension and champion metrics.\n"
        "🔦 `!search` — Recover items during **BLACKOUT** events.\n")

    for e in [emb1, emb2, emb3, emb4, emb5]:
        if os.path.exists("LobbyTopRight.jpg"):
            e.set_thumbnail(url="attachment://LobbyTopRight.jpg")
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=e)
        else:
            await ctx.send(embed=e)

async def handle_streaks_command(ctx, get_db_connection, get_user, fiery_embed):
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
    embed.set_footer(text=footer_text + " | 🔞 ECHO GAMES EDITION 🔞")

    if os.path.exists("LobbyTopRight.jpg"):
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send(embed=embed)
