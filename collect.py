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

# Configuration (This acts as the default if not changed by !audit)
DEFAULT_AUDIT_CHANNEL_ID = 1438810509322223677

# Channel Mapping: ChannelID -> (XP, Flames)
SELFIE_CHANNELS = {
    1300230373053042688: (3000, 5000),
    1300230903984816209: (1000, 2000),
    1300383307623563275: (1500, 1000),
    1300230772980060312: (2500, 2500),
    1300231090384015441: (1000, 100),
    1302575776176279554: (2500, 5000),
    1431243433032290395: (2500, 5000),
    1300382520960880712: (2500, 5000),
    1300382788058484747: (2500, 5000),
    1300382687286263891: (2500, 5000),
    1300382880341692468: (2500, 5000),
    1433609343562944564: (1000, 1500),
    1316710292515717161: (3500, 3500)
}

class Collect(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = DATABASE_PATH
        # ADDED: This variable is what !audit will target and update
        self.AUDIT_CHANNEL_ID = DEFAULT_AUDIT_CHANNEL_ID 
        
        self.hourly_log = {} 
        self.reaction_buffer = {} 
        self.audit_task.start()
        self.vibration_report_task.start()

    def get_db_connection(self):
        return db_module.get_db_connection()

    async def send_immediate_audit(self, user_id, xp, flames, source_desc, channel_name=None):
        """ADDED: Sends an immediate erotic log to the audit channel for every action."""
        # FIXED: Pulling dynamically from self so !audit changes work instantly
        audit_channel = self.bot.get_channel(self.AUDIT_CHANNEL_ID)
        if not audit_channel:
            try:
                audit_channel = await self.bot.fetch_channel(self.AUDIT_CHANNEL_ID)
            except:
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
        
        embed.set_footer(text="🔞 THE MASTER'S EYES ARE EVERYWHERE 🔞")
        
        embed.add_field(name="📝 VOYEUR NOTE", value=f"Asset {user.display_name} has yielded to the exhibition protocol. Their submission is being monetized.", inline=False)
        
        if os.path.exists(image_path):
            await audit_channel.send(file=file, embed=embed)
        else:
            await audit_channel.send(embed=embed)

    def update_user_stats(self, user_id, xp, flames, channel_id=None, is_reaction=False, is_fight=False, hg_kill=0, hg_fb=False, hg_play=False, hg_rank=0, badge=None, ship_partner=None):
        with self.get_db_connection() as conn:
            conn.execute(
                "UPDATE users SET xp = xp + ?, balance = balance + ? WHERE id = ?",
                (xp, flames, user_id)
            )
            conn.commit()
        
        if user_id not in self.hourly_log:
            self.hourly_log[user_id] = {'xp': 0, 'flames': 0, 'pics': {}, 'reactions': 0, 'fights': 0, 'hg_kills': 0, 'hg_first_bloods': 0, 'hg_plays': 0, 'hg_top1': 0, 'hg_top2': 0, 'hg_top3': 0, 'hg_top4': 0, 'hg_top5': 0, 'badges': [], 'ships': []}
        
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
            asyncio.create_task(self.send_immediate_audit(user_id, xp, flames, "Exhibition (Capture)", c_name))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.channel.id in SELFIE_CHANNELS:
            if message.attachments:
                xp, flames = SELFIE_CHANNELS[message.channel.id]
                self.update_user_stats(message.author.id, xp, flames, channel_id=message.channel.id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        self.update_user_stats(payload.user_id, 25, 25, is_reaction=True)

    @tasks.loop(time=[time(hour=21, minute=0, second=0)])
    async def audit_task(self):
        """Sends a massive erotic daily summary every day at 9 PM Lisbon Time."""
        if not self.hourly_log:
            return

        # FIXED: Pulling dynamically from self for !audit support
        audit_channel = self.bot.get_channel(self.AUDIT_CHANNEL_ID)
        if not audit_channel:
            try:
                audit_channel = await self.bot.fetch_channel(self.AUDIT_CHANNEL_ID)
            except:
                return

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
        for user_id, stats in self.hourly_log.items():
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
                    xp_rate, flame_rate = SELFIE_CHANNELS.get(chan_id, (0, 0))
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
        
        # FIXED: Pulling dynamically from self for !audit support
        audit_channel = self.bot.get_channel(self.AUDIT_CHANNEL_ID)
        if not audit_channel:
            try: audit_channel = await self.bot.fetch_channel(self.AUDIT_CHANNEL_ID)
            except: return

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
                    xp_rate, flame_rate = SELFIE_CHANNELS.get(chan_id, (0, 0))
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
        
        # FIXED: Pulling dynamically from self for !audit support
        audit_channel = self.bot.get_channel(self.AUDIT_CHANNEL_ID)
        if not audit_channel:
            try: audit_channel = await self.bot.fetch_channel(self.AUDIT_CHANNEL_ID)
            except: return
        
        embed = discord.Embed(
            title="🕵️ VOYEUR FEED: MASS VIBRATION REPORT",
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
            report_lines.append(f"• {user.mention}: **{count} Vibrations** (Harvested: {total_flames}F / {total_xp}XP)")
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
