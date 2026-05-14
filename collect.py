import discord
from discord.ext import commands, tasks
import sqlite3
import os
import sys
import asyncio
from datetime import datetime, timedelta, timezone, time

# FIXED: Synchronizing with main.py centralized db_module logic
import database as db_module
DATABASE_PATH = db_module.DATABASE_PATH

# Configuration (Initial fallback)
DEFAULT_AUDIT_CHANNEL_ID = 1438810509322223677

# Channel Mapping: ChannelID -> (XP, Flames)
SELFIE_CHANNELS = {
    1498251137164247042: (30000, 50000),
    1498251226943324193: (3000, 5000),
    1498251273709948978: (3000, 5000),
    1498251451510689812: (3000, 5000),
    1498251498579296256: (3000, 5000),
    1498291545357418556: (30000, 50000),
    1498598774300475483: (30000, 50000),
    1498253401744740363: (30000, 50000),
    1498253651922259998: (30000, 50000),
    1498253678019350649: (30000, 50000),
    1498253716388712619: (30000, 50000),
    1498253749246889985: (30000, 50000),
    1498253587099160626: (3000, 5000)
}

class Collect(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = DATABASE_PATH
        # ADDED: This variable is what !audit will target and update
        self.AUDIT_CHANNEL_ID = DEFAULT_AUDIT_CHANNEL_ID 
        
        self.hourly_log = {} 
        self.reaction_buffer = {} 
        
        # --- NEW: INITIALIZE TABLES AND SYNC HANDCODED CHANNELS ---
        with self.get_db_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS collect_channels (
                            channel_id INTEGER PRIMARY KEY, 
                            guild_id INTEGER, 
                            xp_rate INTEGER, 
                            flame_rate INTEGER)""")
            
            # Ensure guild_config exists for the audit sync logic
            conn.execute("""CREATE TABLE IF NOT EXISTS guild_config (
                            guild_id INTEGER, 
                            key TEXT, 
                            value TEXT, 
                            PRIMARY KEY (guild_id, key))""")
            
            # Auto-sync handcoded channels to DB (using hardcoded primary guild ID)
            main_guild_id = 1131610405102432296 
            
            # Sync Selfie Channels
            for cid, (xp, fl) in SELFIE_CHANNELS.items():
                conn.execute("INSERT OR IGNORE INTO collect_channels VALUES (?, ?, ?, ?)", (cid, main_guild_id, xp, fl))
            
            # Sync Audit Channel (Like Selfie Channels)
            conn.execute("INSERT OR IGNORE INTO guild_config (guild_id, key, value) VALUES (?, 'audit_channel', ?)", 
                         (main_guild_id, str(DEFAULT_AUDIT_CHANNEL_ID)))
            
            conn.commit()

        self.audit_task.start()
        self.vibration_report_task.start()

    def get_db_connection(self):
        return db_module.get_db_connection()

    async def get_dynamic_audit_id(self, guild_id):
        """FIX: Pulls the channel set by !audit from the database."""
        try:
            with self.get_db_connection() as conn:
                row = conn.execute("SELECT value FROM guild_config WHERE guild_id = ? AND key = 'audit_channel'", (guild_id,)).fetchone()
                if row: return int(row[0])
        except:
            pass
        return DEFAULT_AUDIT_CHANNEL_ID

    @commands.command(name="collectadmin")
    @commands.has_permissions(administrator=True)
    async def set_collect_channel(self, ctx, channel: discord.TextChannel):
        """Admin command to establish a new collection stage for this server."""
        xp_reward = 20000
        flame_reward = 50000
        
        with self.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO collect_channels (channel_id, guild_id, xp_rate, flame_rate) VALUES (?, ?, ?, ?)",
                         (channel.id, ctx.guild.id, xp_reward, flame_reward))
            conn.commit()
            
        main_mod = sys.modules['__main__']
        embed = main_mod.fiery_embed("🛰️ COLLECTION STAGE CALIBRATED", 
            f"Stage {channel.mention} is now linked to the Red Room frequencies.\n\n"
            f"**Server:** {ctx.guild.name}\n"
            f"**Yield:** `{flame_reward}` Flames / `{xp_reward}` XP per submission.", color=0x00FF00)
        await ctx.send(embed=embed)

    async def send_immediate_audit(self, guild_id, user_id, xp, flames, source_desc, channel_name=None):
        """ADDED: Sends an immediate erotic log to the audit channel for every action."""
        # FIXED: Fetching dynamic ID from database
        chan_id = await self.get_dynamic_audit_id(guild_id)
        audit_channel = self.bot.get_channel(chan_id) or await self.bot.fetch_channel(chan_id)
        
        if not audit_channel:
            return
        
        # FIXED: Ensuring user is a Discord object, not a DB row
        guild = self.bot.get_guild(guild_id)
        user = None
        if guild:
            user = guild.get_member(user_id)
        
        if not user:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
        
        embed = discord.Embed(
            title="🕵️ VOYEUR FEED: ACTIVITY DETECTED",
            description=f"The sensors in the Red Room have picked up a new display of obedience.",
            color=0x8b0000,
            timestamp=datetime.now(timezone.utc)
        )
        
        image_path = "LobbyTopRight.jpg"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="audit_thumb.jpg")
            embed.set_thumbnail(url="attachment://audit_thumb.jpg")
        
        target_info = f"Stage: **#{channel_name}**" if channel_name else "Interaction: **Universal**"
        
        embed.add_field(name="📜 Name", value=user.mention, inline=True)
        embed.add_field(name="📜 Protocol", value=source_desc, inline=True)
        embed.add_field(name="📍 Location", value=target_info, inline=True)
        embed.add_field(name="💰 Harvest", value=f"+{flames} Flames | +{xp} XP", inline=False)
        
        embed.set_footer(text="🔞 Velvet'S EYES ARE EVERYWHERE 🔞")
        
        embed.add_field(name="📝 VOYEUR NOTE", value=f"Asset {user.display_name} has yielded to the exhibition protocol. Their submission is being monetized.", inline=False)
        
        if os.path.exists(image_path):
            await audit_channel.send(file=file, embed=embed)
        else:
            await audit_channel.send(embed=embed)

    def update_user_stats(self, guild_id, user_id, xp, flames, channel_id=None, is_reaction=False, is_fight=False, hg_kill=0, hg_fb=False, hg_play=False, hg_rank=0, badge=None, ship_partner=None):
        with self.get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET xp = xp + ?, balance = balance + ? WHERE id = ?",
                (xp, flames, user_id)
            )
            conn.commit()
        
        if user_id not in self.hourly_log:
            self.hourly_log[user_id] = {'guild_id': guild_id, 'xp': 0, 'flames': 0, 'pics': {}, 'reactions': 0, 'fights': 0, 'hg_kills': 0, 'hg_first_bloods': 0, 'hg_plays': 0, 'hg_top1': 0, 'hg_top2': 0, 'hg_top3': 0, 'hg_top4': 0, 'hg_top5': 0, 'badges': [], 'ships': []}
        
        self.hourly_log[user_id]['xp'] += xp
        self.hourly_log[user_id]['flames'] += flames
        
        if is_reaction:
            self.hourly_log[user_id]['reactions'] += 1
            self.reaction_buffer[user_id] = self.reaction_buffer.get(user_id, 0) + 1
        
        if is_fight: self.hourly_log[user_id]['fights'] += 1
        if hg_kill > 0: self.hourly_log[user_id]['hg_kills'] += hg_kill
        if hg_fb: self.hourly_log[user_id]['hg_first_bloods'] += 1
        if hg_play: self.hourly_log[user_id]['hg_plays'] += 1
        
        if hg_rank == 1: self.hourly_log[user_id]['hg_top1'] += 1
        elif hg_rank == 2: self.hourly_log[user_id]['hg_top2'] += 1
        elif hg_rank == 3: self.hourly_log[user_id]['hg_top3'] += 1
        elif hg_rank == 4: self.hourly_log[user_id]['hg_top4'] += 1
        elif hg_rank == 5: self.hourly_log[user_id]['hg_top5'] += 1
        
        if badge: self.hourly_log[user_id]['badges'].append(badge)
        if ship_partner: self.hourly_log[user_id]['ships'].append(ship_partner)
        
        if channel_id:
            if channel_id not in self.hourly_log[user_id]['pics']:
                self.hourly_log[user_id]['pics'][channel_id] = 0
            self.hourly_log[user_id]['pics'][channel_id] += 1
            
            chan = self.bot.get_channel(channel_id)
            c_name = chan.name if chan else str(channel_id)
            asyncio.create_task(self.send_immediate_audit(guild_id, user_id, xp, flames, "Exhibition (Capture)", c_name))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
            
        # FIXED: Look up channel settings in DB to allow independent server stages
        with self.get_db_connection() as conn:
            row = conn.execute("SELECT xp_rate, flame_rate FROM collect_channels WHERE channel_id = ?", (message.channel.id,)).fetchone()
            
        if row:
            if message.attachments:
                xp, flames = row[0], row[1]
                self.update_user_stats(message.guild.id, message.author.id, xp, flames, channel_id=message.channel.id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id or not payload.guild_id:
            return
        self.update_user_stats(payload.guild_id, payload.user_id, 25, 25, is_reaction=True)

    @tasks.loop(time=[time(hour=21, minute=0, second=0)])
    async def audit_task(self):
        """Sends a massive erotic daily summary every day at 9 PM Lisbon Time."""
        if not self.hourly_log:
            return

        # FIXED: Multi-guild summary logic
        guild_groups = {}
        for uid, stats in self.hourly_log.items():
            gid = stats['guild_id']
            if gid not in guild_groups: guild_groups[gid] = {}
            guild_groups[gid][uid] = stats

        for guild_id, logs in guild_groups.items():
            chan_id = await self.get_dynamic_audit_id(guild_id)
            audit_channel = self.bot.get_channel(chan_id) or await self.bot.fetch_channel(chan_id)
            if not audit_channel: continue

            image_path = "LobbyTopRight.jpg"
            file = None
            
            embed = discord.Embed(
                title="🌅 THE MASTER'S DAILY CLIMAX: 09:00 PM 🌅",
                description="The sun sets over the dungeon. The daily ledger is finalized. Every groan, every fight, and every display of skin has been calculated.",
                color=0x8b0000, 
                timestamp=datetime.now(timezone.utc)
            )

            if os.path.exists(image_path):
                file = discord.File(image_path, filename="harvest.jpg")
                embed.set_thumbnail(url="attachment://harvest.jpg")

            ping_list = []
            for user_id, stats in logs.items():
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                user_mention = user.mention if user else f"Subject {user_id}"
                ping_list.append(user_mention)
                
                calc_details = []
                if stats.get('reactions', 0) > 0:
                    calc_details.append(f"🫦 **Reactions:** `{stats['reactions']}` × (25F / 25XP) = **{stats['reactions']*25:,}**")
                
                if stats.get('pics'):
                    for chan_id, count in stats['pics'].items():
                        chan = self.bot.get_channel(chan_id)
                        chan_name = chan.name if chan else f"Stage {chan_id}"
                        # Look up rate in DB for precise calculation
                        with self.get_db_connection() as conn:
                            rate = conn.execute("SELECT xp_rate, flame_rate FROM collect_channels WHERE channel_id = ?", (chan_id,)).fetchone()
                        
                        xp_rate, flame_rate = rate if rate else (0, 0)
                        total_f = count * flame_rate
                        total_x = count * xp_rate
                        calc_details.append(f"📸 **#{chan_name}:** `{count}` posts × ({flame_rate}F / {xp_rate}XP) = **{total_f:,}F / {total_x:,}XP**")

                calculation_resume = "\n".join(calc_details) if calc_details else "_No passive extraction detected._"
                game_report = ""
                if stats.get('fights', 0) > 0:
                    game_report += f"\n⚔️ **1v1 Fights Initiated:** {stats['fights']}"
                
                if stats.get('hg_plays', 0) > 0:
                    placements = []
                    if stats.get('hg_top1', 0) > 0: placements.append(f"🥇x{stats['hg_top1']}")
                    if stats.get('hg_top2', 0) > 0: placements.append(f"🥈x{stats['hg_top2']}")
                    if stats.get('hg_top3', 0) > 0: placements.append(f"🥉x{stats['hg_top3']}")
                    if stats.get('hg_top4', 0) > 0: placements.append(f"🏅x{stats['hg_top4']} (4th)")
                    if stats.get('hg_top5', 0) > 0: placements.append(f"🎖️x{stats['hg_top5']} (5th)")
                    placement_str = " | ".join(placements) if placements else "No Top 5 finishes"

                    game_report += f"\n🏹 **Hunger Games:** {stats['hg_plays']} Plays | 💀 {stats['hg_kills']} Kills"
                    if stats.get('hg_first_bloods', 0) > 0:
                        game_report += f" | 🩸 **FB:** {stats['hg_first_bloods']}"
                    game_report += f"\n🏆 **Placements:** {placement_str}"
                
                status_report = ""
                if stats.get('ships'):
                    status_report += f"\n💖 **High-Lust Ships (75%+):** {', '.join(stats['ships'])}"
                if stats.get('badges'):
                    status_report += f"\n🏅 **Achievements/Tiers:** {', '.join(stats['badges'])}"

                value = (
                    f"💰 **Total Extracted Flames:** `{stats['flames']:,}`\n"
                    f"⛓️ **Total Obedience XP Won:** `+{stats['xp']:,}`\n"
                    f"📊 **Extraction Breakdown:**\n{calculation_resume}\n"
                    f"━━━━━━━━━━━━━━"
                    f"{game_report}"
                    f"{status_report}\n\n"
                    f"*The Master has confirmed your daily extraction value.*"
                )
                embed.add_field(name=f"👤 {user.name.upper() if user else 'Unknown Asset'}", value=value, inline=False)

            embed.set_footer(text="🔞 THE DAILY LEDGER IS SEALED 🔞")
            content = "⛓️ **DAILY HARVEST PINGS:** " + ", ".join(ping_list)
            if file:
                await audit_channel.send(content=content, embed=embed, file=file)
            else:
                await audit_channel.send(content=content, embed=embed)
        
        self.hourly_log.clear()

    @commands.command()
    @commands.is_owner()
    async def trigger_audit(self, ctx):
        """Triggers the Master's Ledger summary immediately WITHOUT clearing the daily log."""
        if not self.hourly_log:
            return await ctx.send("The sensors are clear. No new activity to report in the ledger.")
        
        await ctx.send("Master detected. Generating immediate synchronization report...")
        
        # FIXED: Pulling dynamic ID from database
        chan_id = await self.get_dynamic_audit_id(ctx.guild.id)
        audit_channel = self.bot.get_channel(chan_id) or await self.bot.fetch_channel(chan_id)
        if not audit_channel:
            return

        image_path = "LobbyTopRight.jpg"
        file = None
        embed = discord.Embed(
            title="🌅 THE MASTER'S MANUAL CLIMAX: OVERRIDE 🌅",
            description="Manual override engaged. Current accumulation report follows.",
            color=0x8b0000, timestamp=datetime.now(timezone.utc)
        )

        if os.path.exists(image_path):
            file = discord.File(image_path, filename="harvest_manual.jpg")
            embed.set_thumbnail(url="attachment://harvest_manual.jpg")

        ping_list = []
        for user_id, stats in self.hourly_log.items():
            if stats['guild_id'] != ctx.guild.id: continue
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            user_mention = user.mention if user else f"Subject {user_id}"
            ping_list.append(user_mention)
            
            calc_details = []
            if stats.get('reactions', 0) > 0:
                calc_details.append(f"🫦 **Reactions:** `{stats['reactions']}` × (25F / 25XP) = **{stats['reactions']*25:,}**")
            
            if stats.get('pics'):
                for chan_id, count in stats['pics'].items():
                    chan = self.bot.get_channel(chan_id)
                    chan_name = chan.name if chan else f"Stage {chan_id}"
                    
                    with self.get_db_connection() as conn:
                        rate = conn.execute("SELECT xp_rate, flame_rate FROM collect_channels WHERE channel_id = ?", (chan_id,)).fetchone()
                    
                    xp_rate, flame_rate = rate if rate else (0, 0)
                    total_f = count * flame_rate
                    total_x = count * xp_rate
                    calc_details.append(f"📸 **#{chan_name}:** `{count}` posts × ({flame_rate}F / {xp_rate}XP) = **{total_f:,}F / {total_x:,}XP**")

            calculation_resume = "\n".join(calc_details) if calc_details else "_No passive extraction detected._"
            game_report = ""
            if stats.get('fights', 0) > 0: game_report += f"\n⚔️ **1v1 Fights Initiated:** {stats['fights']}"
            if stats.get('hg_plays', 0) > 0:
                placements = []
                if stats.get('hg_top1', 0) > 0: placements.append(f"🥇x{stats['hg_top1']}")
                if stats.get('hg_top2', 0) > 0: placements.append(f"🥈x{stats['hg_top2']}")
                if stats.get('hg_top3', 0) > 0: placements.append(f"🥉x{stats['hg_top3']}")
                if stats.get('hg_top4', 0) > 0: placements.append(f"🏅x{stats['hg_top4']} (4th)")
                if stats.get('hg_top5', 0) > 0: placements.append(f"🎖️x{stats['hg_top5']} (5th)")
                placement_str = " | ".join(placements) if placements else "No Top 5 finishes"
                game_report += f"\n🏹 **Hunger Games:** {stats['hg_plays']} Plays | 💀 {stats['hg_kills']} Kills"
                if stats.get('hg_first_bloods', 0) > 0: game_report += f" | 🩸 **FB:** {stats['hg_first_bloods']}"
                game_report += f"\n🏆 **Placements:** {placement_str}"
            
            status_report = ""
            if stats.get('ships'): status_report += f"\n💖 **Ships:** {', '.join(stats['ships'])}"
            if stats.get('badges'): status_report += f"\n🏅 **Badges:** {', '.join(stats['badges'])}"

            value = (
                f"💰 **Accumulated Flames:** `{stats['flames']:,}`\n"
                f"⛓️ **Accumulated XP:** `+{stats['xp']:,}`\n"
                f"📊 **Breakdown:**\n{calculation_resume}\n"
                f"━━━━━━━━━━━━━━"
                f"{game_report}"
                f"{status_report}\n\n"
                f"*Data will reset at 9 PM Lisbon.*"
            )
            embed.add_field(name=f"👤 {user.name.upper() if user else 'Unknown Asset'}", value=value, inline=False)

        content = "⛓️ **MANUAL SYNC PINGS:** " + ", ".join(ping_list)
        if file: await audit_channel.send(content=content, embed=embed, file=file)
        else: await audit_channel.send(content=content, embed=embed)

    @tasks.loop(hours=3.0)
    async def vibration_report_task(self):
        """Groups all reaction activity from the last 3 hours into one erotic audit log."""
        if not self.reaction_buffer:
            return
        
        # FIXED: Summary uses dynamic ID based on the first buffered user's guild
        first_user = next(iter(self.reaction_buffer))
        gid = self.hourly_log.get(first_user, {}).get('guild_id', 0)
        chan_id = await self.get_dynamic_audit_id(gid)
        audit_channel = self.bot.get_channel(chan_id) or await self.bot.fetch_channel(chan_id)
        
        if not audit_channel: return
        
        embed = discord.Embed(
            title="🕵️ VELVET FEED: MASS REACTIONS REPORT",
            description="The internal sensors have reached capacity. Reaction display report follows.",
            color=0x800080, timestamp=datetime.now(timezone.utc)
        )
        image_path = "LobbyTopRight.jpg"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="vibe_report.jpg")
            embed.set_thumbnail(url="attachment://vibe_report.jpg")
        report_lines = []
        for user_id, count in self.reaction_buffer.items():
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            total_flames, total_xp = count * 25, count * 25
            report_lines.append(f"• {user.mention}: **{count} REACTIONS** (Harvested: {total_flames}F / {total_xp}XP)")
        embed.description += "\n\n" + "\n".join(report_lines)
        embed.set_footer(text="🔞 YOUR WATCHFUL EYES ARE NOTED 🔞")
        if os.path.exists(image_path): await audit_channel.send(file=file, embed=embed)
        else: await audit_channel.send(embed=embed)
        self.reaction_buffer.clear()

    @audit_task.before_loop
    @vibration_report_task.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Collect(bot))
