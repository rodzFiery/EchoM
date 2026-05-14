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

# REMOVED: Hardcoded SELFIE_CHANNELS dictionary. Logic moved to Database.

class Collect(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = DATABASE_PATH
        # ADDED: Initialized as None; will be pulled dynamically from guild_config (audit.py)
        self.AUDIT_CHANNEL_ID = None 
        
        self.hourly_log = {} 
        self.reaction_buffer = {} 
        self.audit_task.start()
        self.vibration_report_task.start()
        # NEW: Ensure the collect table exists on startup
        self._init_collect_db()

    def _init_collect_db(self):
        """Creates the persistence table for admin-defined collect channels."""
        with self.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS collect_channels (channel_id INTEGER PRIMARY KEY, xp_rate INTEGER, flame_rate INTEGER)")
            conn.commit()

    def get_db_connection(self):
        return db_module.get_db_connection()

    async def sync_audit_channel(self, guild_id):
        """NEW: Internal helper to pull the channel set by audit.py from the database."""
        try:
            with self.get_db_connection() as conn:
                res = conn.execute("SELECT value FROM guild_config WHERE guild_id = ? AND key = 'audit_channel'", (guild_id,)).fetchone()
                if res:
                    self.AUDIT_CHANNEL_ID = int(res[0])
                    return self.bot.get_channel(self.AUDIT_CHANNEL_ID) or await self.bot.fetch_channel(self.AUDIT_CHANNEL_ID)
        except:
            pass
        return None

    @commands.command(name="collectaudit")
    @commands.has_permissions(administrator=True)
    async def collectaudit(self, ctx, channel: discord.TextChannel, xp: int = 25000, flames: int = 50000):
        """ADMIN ONLY: Sets a channel as a collection stage with custom XP/Flame rates (Defaults to 25k/50k)."""
        with self.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO collect_channels (channel_id, xp_rate, flame_rate) VALUES (?, ?, ?)", 
                         (channel.id, xp, flames))
            conn.commit()
        
        main_mod = sys.modules['__main__']
        
        # FIXED: Reward admin with separate calls to avoid TypeError in update_user_stats_async
        try:
            await main_mod.update_user_stats_async(ctx.author.id, amount=50000, source="Collection Stage Calibration")
            with self.get_db_connection() as conn:
                conn.execute("UPDATE users SET xp = xp + ? WHERE id = ?", (25000, ctx.author.id))
                conn.commit()
        except:
            pass
        
        embed = main_mod.fiery_embed("🛰️ COLLECTION STAGE INITIALIZED", 
            f"The Master has added {channel.mention} to the voyeur network.\n\n"
            f"**Member Reward XP:** +{xp}\n"
            f"**Member Reward Flames:** +{flames}\n\n"
            f"🎁 **Master's Bounty:** {ctx.author.mention} rewarded with **25,000 XP** and **50,000 Flames** for calibration.", color=0x00FF00)
        await ctx.send(embed=embed)

    async def send_immediate_audit(self, guild_id, user_id, xp, flames, source_desc, channel_name=None):
        """ADDED: Sends an immediate erotic log to the audit channel for every action."""
        # FIXED: Pulling dynamically from the DB table managed by audit.py
        audit_channel = await self.sync_audit_channel(guild_id)
        if not audit_channel:
            return
        
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
            if user_id not in self.reaction_buffer: self.reaction_buffer[user_id] = {'guild_id': guild_id, 'count': 0}
            self.reaction_buffer[user_id]['count'] += 1
        
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
        
        # NEW: Dynamic check against the database instead of a hardcoded list
        with self.get_db_connection() as conn:
            row = conn.execute("SELECT xp_rate, flame_rate FROM collect_channels WHERE channel_id = ?", (message.channel.id,)).fetchone()
        
        if row:
            if message.attachments:
                xp, flames = row['xp_rate'], row['flame_rate']
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

        # Separate logs by guild
        guild_groups = {}
        for uid, stats in self.hourly_log.items():
            gid = stats['guild_id']
            if gid not in guild_groups: guild_groups[gid] = {}
            guild_groups[gid][uid] = stats

        for guild_id, logs in guild_groups.items():
            # SYNC: Pull the audit channel from audit.py configuration
            audit_channel = await self.sync_audit_channel(guild_id)
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
                        with self.get_db_connection() as conn:
                            rates = conn.execute("SELECT xp_rate, flame_rate FROM collect_channels WHERE channel_id = ?", (chan_id,)).fetchone()
                        xp_rate, flame_rate = (rates['xp_rate'], rates['flame_rate']) if rates else (0, 0)
                        calc_details.append(f"📸 **#{chan_name}:** `{count}` posts × ({flame_rate}F / {xp_rate}XP) = **{total_f:,}F / {total_x:,}XP**")

                calculation_resume = "\n".join(calc_details) if calc_details else "_No passive extraction detected._"
                game_report = ""
                if stats.get('fights', 0) > 0: game_report += f"\n⚔️ **1v1 Fights Initiated:** {stats['fights']}"
                if stats.get('hg_plays', 0) > 0:
                    placements = [f"🥇x{stats['hg_top1']}", f"🥈x{stats['hg_top2']}", f"🥉x{stats['hg_top3']}", f"🏅x{stats['hg_top4']}", f"🎖️x{stats['hg_top5']}"]
                    game_report += f"\n🏹 **HG:** {stats['hg_plays']} Plays | 💀 {stats['hg_kills']} Kills | 🏆 { ' | '.join([p for p in placements if 'x0' not in p]) }"
                
                status_report = ""
                if stats.get('ships'): status_report += f"\n💖 **High-Lust Ships:** {', '.join(stats['ships'])}"
                if stats.get('badges'): status_report += f"\n🏅 **Achievements:** {', '.join(stats['badges'])}"

                embed.add_field(name=f"👤 {user.name.upper() if user else 'Unknown Asset'}", value=f"💰 **Total Extracted Flames:** `{stats['flames']:,}`\n⛓️ **Total Obedience XP Won:** `+{stats['xp']:,}`\n📊 **Extraction Breakdown:**\n{calculation_resume}\n━━━━━━━━━━━━━━{game_report}{status_report}\n\n*The Master has confirmed your daily extraction value.*", inline=False)

            embed.set_footer(text="🔞 THE DAILY LEDGER IS SEALED 🔞")
            content = "⛓️ **DAILY HARVEST PINGS:** " + ", ".join(ping_list)
            if file: await audit_channel.send(content=content, embed=embed, file=file)
            else: await audit_channel.send(content=content, embed=embed)
        
        self.hourly_log.clear()

    @commands.command()
    @commands.is_owner()
    async def trigger_audit(self, ctx):
        """Triggers the Master's Ledger summary immediately WITHOUT clearing the daily log."""
        if not self.hourly_log:
            return await ctx.send("The sensors are clear. No new activity to report in the ledger.")
        
        # SYNC: Dynamically find where audit.py says to post
        audit_channel = await self.sync_audit_channel(ctx.guild.id)
        if not audit_channel: return

        image_path = "LobbyTopRight.jpg"
        file = None
        embed = discord.Embed(title="🌅 THE MASTER'S MANUAL CLIMAX: OVERRIDE 🌅", description="Current accumulation report follows.", color=0x8b0000, timestamp=datetime.now(timezone.utc))

        if os.path.exists(image_path):
            file = discord.File(image_path, filename="harvest_manual.jpg")
            embed.set_thumbnail(url="attachment://harvest_manual.jpg")

        for user_id, stats in self.hourly_log.items():
            if stats['guild_id'] != ctx.guild.id: continue
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            embed.add_field(name=f"👤 {user.name.upper() if user else 'Asset'}", value=f"💰 **Accumulated Flames:** `{stats['flames']:,}`\n⛓️ **Accumulated XP:** `+{stats['xp']:,}`", inline=False)

        if file: await audit_channel.send(embed=embed, file=file)
        else: await audit_channel.send(embed=embed)

    @tasks.loop(hours=3.0)
    async def vibration_report_task(self):
        """Groups all reaction activity from the last 3 hours into one erotic audit log."""
        if not self.reaction_buffer: return
        
        guild_vibe_groups = {}
        for uid, data in self.reaction_buffer.items():
            gid = data['guild_id']
            if gid not in guild_vibe_groups: guild_vibe_groups[gid] = []
            guild_vibe_groups[gid].append((uid, data['count']))

        for guild_id, reactions in guild_vibe_groups.items():
            # SYNC: Pull the audit channel from audit.py configuration
            audit_channel = await self.sync_audit_channel(guild_id)
            if not audit_channel: continue
            
            embed = discord.Embed(title="🕵️ VELVET FEED: MASS REACTIONS REPORT", description="Reaction display report follows.", color=0x800080, timestamp=datetime.now(timezone.utc))
            image_path = "LobbyTopRight.jpg"
            if os.path.exists(image_path):
                file = discord.File(image_path, filename="vibe_report.jpg")
                embed.set_thumbnail(url="attachment://vibe_report.jpg")
            
            report_lines = []
            for user_id, count in reactions:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                report_lines.append(f"• {user.mention}: **{count} REACTIONS** (Harvested: {count*25}F / {count*25}XP)")
            
            embed.description += "\n\n" + "\n".join(report_lines)
            if os.path.exists(image_path): await audit_channel.send(file=file, embed=embed)
            else: await audit_channel.send(embed=embed)
            
        self.reaction_buffer.clear()

    @audit_task.before_loop
    @vibration_report_task.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Collect(bot))
