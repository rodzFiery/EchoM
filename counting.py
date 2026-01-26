import discord
from discord.ext import commands, tasks
import sys
import os
import json
import asyncio
from datetime import datetime, timezone

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Local cache now uses dictionaries keyed by Guild ID
        self.current_counts = {}
        self.last_user_ids = {}
        self.counting_channel_ids = {}
        self.load_config()
        self.weekend_announcer.start()

    def load_config(self):
        """Load counting data from the database config for all guilds."""
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                # Load all guild-specific channels
                c_rows = conn.execute("SELECT key, value FROM config WHERE key LIKE 'counting_channel_%'").fetchall()
                for row in c_rows:
                    guild_part = row['key'].split('_')[-1]
                    if guild_part.isdigit():
                        self.counting_channel_ids[int(guild_part)] = int(row['value'])
                
                # Load all guild-specific states
                s_rows = conn.execute("SELECT key, value FROM config WHERE key LIKE 'counting_state_%'").fetchall()
                for row in s_rows:
                    guild_part = row['key'].split('_')[-1]
                    if guild_part.isdigit():
                        guild_id = int(guild_part)
                        state = json.loads(row['value'])
                        self.current_counts[guild_id] = state.get('count', 0)
                        self.last_user_ids[guild_id] = state.get('last_user', None)
        except: pass

    def _save_state_sync(self, guild_id):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         (f'counting_channel_{guild_id}', str(self.counting_channel_ids.get(guild_id))))
            state = {'count': self.current_counts.get(guild_id, 0), 'last_user': self.last_user_ids.get(guild_id)}
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         (f'counting_state_{guild_id}', json.dumps(state)))
            conn.commit()

    async def save_state(self, guild_id):
        """Save counting state and channel for a specific guild."""
        await asyncio.to_thread(self._save_state_sync, guild_id)

    def _update_high_score_sync(self, count, ruiner_id, guild_id):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS counting_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, score INTEGER, ruiner_id INTEGER, guild_id INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
            except: pass
            conn.execute("INSERT INTO counting_runs (score, ruiner_id, guild_id) VALUES (?, ?, ?)", (count, ruiner_id, guild_id))
            conn.commit()

    async def update_high_score(self, count, ruiner_id, guild_id):
        """Record the run in the high score ledger (Global and Local attribution)."""
        await asyncio.to_thread(self._update_high_score_sync, count, ruiner_id, guild_id)

    def _update_member_stats_sync(self, user_id, guild_id, is_mistake=False):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            try:
                conn.execute("ALTER TABLE users ADD COLUMN count_total INTEGER DEFAULT 0")
                conn.execute("ALTER TABLE users ADD COLUMN count_mistakes INTEGER DEFAULT 0")
                conn.execute("CREATE TABLE IF NOT EXISTS local_counting (user_id INTEGER, guild_id INTEGER, count INTEGER DEFAULT 0, PRIMARY KEY (user_id, guild_id))")
            except: pass
            
            if is_mistake:
                conn.execute("UPDATE users SET count_mistakes = count_mistakes + 1 WHERE id = ?", (user_id,))
            else:
                conn.execute("UPDATE users SET count_total = count_total + 1 WHERE id = ?", (user_id,))
                conn.execute("INSERT INTO local_counting (user_id, guild_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, guild_id) DO UPDATE SET count = count + 1", (user_id, guild_id))
            conn.commit()

    async def update_member_stats(self, user_id, guild_id, is_mistake=False):
        """Updates local/global counting stats for the user profile."""
        await asyncio.to_thread(self._update_member_stats_sync, user_id, guild_id, is_mistake)

    async def check_personal_milestone(self, message):
        """Logic for 50-step personal milestones (50, 100, 150, etc.)."""
        main_mod = sys.modules['__main__']
        user_id = message.author.id
        
        def fetch_total():
            with main_mod.get_db_connection() as conn:
                user = conn.execute("SELECT count_total FROM users WHERE id = ?", (user_id,)).fetchone()
                return user['count_total'] if user else 0
        
        total = await asyncio.to_thread(fetch_total)

        if total > 0 and total % 50 == 0:
            is_weekend = datetime.now().weekday() >= 5
            reward = 40000 if is_weekend else 20000
            theme_title = "🔥 DOUBLE FLAME WEEKEND" if is_weekend else "📜 NEURAL COUNTING CERTIFICATE"
            
            await main_mod.update_user_stats_async(user_id, amount=reward, source=f"Counting Milestone: {total}")
            
            embed = main_mod.fiery_embed(theme_title, 
                                        f"### 🎖️ MILESTONE REACHED: {total}\n"
                                        f"Asset {message.author.mention}, your numerical precision is efficient.\n\n"
                                        f"**Reward Granted:** `{reward:,} Flames` {'(2x Weekend Bonus!)' if is_weekend else ''}\n"
                                        f"**Status:** `Verified & Synchronized`\n\n"
                                        f"\"*The Red Room appreciates your consistency.*\"", color=0xFF4500 if is_weekend else 0x00FF00)
            await message.channel.send(embed=embed)

    async def check_community_milestone(self, message):
        """Logic for community-wide milestones reached in this server (1000, 2000, etc.)."""
        main_mod = sys.modules['__main__']
        guild_id = message.guild.id
        
        def fetch_comm():
            with main_mod.get_db_connection() as conn:
                row = conn.execute("SELECT SUM(count) as total FROM local_counting WHERE guild_id = ?", (guild_id,)).fetchone()
                return row['total'] if row and row['total'] else 0

        total_community = await asyncio.to_thread(fetch_comm)
            
        if total_community > 0 and total_community % 1000 == 0:
            embed = main_mod.fiery_embed("🛰️ SECTOR MILESTONE ACHIEVED",
                                        f"### 🌐 COLLECTIVE PRECISION: {total_community:,}\n"
                                        f"Attention assets of **{message.guild.name}**.\n\n"
                                        f"This sector has successfully synchronized `{total_community:,}` verified numbers into the neural network.\n"
                                        f"Local efficiency has increased. The Red Room is watching.\n\n"
                                        f"**Status:** `Optimization Successful`", color=0x9B59B6)
            await message.channel.send(content="@here", embed=embed)

    async def check_global_goal(self, message):
        """NEW: Logic for Universal Global Goals (50k increments up to 10M)."""
        main_mod = sys.modules['__main__']
        
        def fetch_global():
            with main_mod.get_db_connection() as conn:
                total_global_row = conn.execute("SELECT SUM(count_total) FROM users").fetchone()
                return total_global_row[0] if total_global_row and total_global_row[0] else 0

        total_global = await asyncio.to_thread(fetch_global)
            
        if total_global > 0 and total_global % 50000 == 0 and total_global <= 10000000:
            badge_name = f"Neural Architect: {total_global:,}"
            
            def record_goal():
                with main_mod.get_db_connection() as conn:
                    try:
                        conn.execute("CREATE TABLE IF NOT EXISTS global_milestone_history (id INTEGER PRIMARY KEY AUTOINCREMENT, milestone INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
                    except: pass
                    conn.execute("INSERT INTO global_milestone_history (milestone) VALUES (?)", (total_global,))
                    conn.commit()

            await asyncio.to_thread(record_goal)

            embed = main_mod.fiery_embed("🌍 UNIVERSAL NEURAL SYNC",
                                        f"### 🏆 GLOBAL GOAL REACHED: {total_global:,}\n"
                                        f"The Echo has achieved a massive milestone across all sectors.\n\n"
                                        f"**Global Badge Granted:** `[{badge_name}]`\n"
                                        f"All synchronized assets have been updated with this clearance level.\n\n"
                                        f"*The Red Room has expanded its reach.*", color=0xFFD700)
            await message.channel.send(embed=embed)

    @tasks.loop(minutes=1)
    async def weekend_announcer(self):
        """Task to reliably announce weekend protocol transitions."""
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:
            main_mod = sys.modules['__main__']
            for guild_id, channel_id in self.counting_channel_ids.items():
                channel = self.bot.get_channel(channel_id)
                if not channel: continue
                if now.weekday() == 5: # Saturday
                    await channel.send(embed=main_mod.fiery_embed("🔥 PROTOCOL: DOUBLE FLAMES", "The weekend has arrived. Reward frequencies are now doubled for all assets.", color=0xFF4500))
                elif now.weekday() == 0: # Monday
                    await channel.send(embed=main_mod.fiery_embed("📜 PROTOCOL: STANDARD FREQUENCY", "Weekend cycle completed. Returning to standard neural reward rates.", color=0x00FF00))

    @commands.command(name="globalgoal")
    async def global_goal_progress(self, ctx):
        """Displays the progress toward the next 50,000 global increment."""
        main_mod = sys.modules['__main__']
        def fetch_global_val():
            with main_mod.get_db_connection() as conn:
                total_global_row = conn.execute("SELECT SUM(count_total) FROM users").fetchone()
                return total_global_row[0] if total_global_row and total_global_row[0] else 0
        
        total_global = await asyncio.to_thread(fetch_global_val)
        next_milestone = ((total_global // 50000) + 1) * 50000
        remaining = next_milestone - total_global
        progress_pct = (total_global % 50000) / 50000
        bar = "█" * int(progress_pct * 20) + "░" * (20 - int(progress_pct * 20))
        
        desc = (f"### 🌐 NEURAL SYNCHRONIZATION STATUS\n"
                f"**Total Verified Data:** `{total_global:,}`\n"
                f"**Next Global Goal:** `{next_milestone:,}`\n"
                f"**Data Remaining:** `{remaining:,}`\n\n"
                f"`{bar}` **{progress_pct*100:.1f}%**")
        await ctx.send(embed=main_mod.fiery_embed("GLOBAL GOAL PROGRESS", desc, color=0x3498DB))

    @commands.command(name="goalhistory")
    async def global_goal_history(self, ctx):
        """Displays all previously achieved Universal Global Goals."""
        main_mod = sys.modules['__main__']
        def fetch_h():
            with main_mod.get_db_connection() as conn:
                try: return conn.execute("SELECT milestone, timestamp FROM global_milestone_history ORDER BY milestone DESC").fetchall()
                except: return []

        history = await asyncio.to_thread(fetch_h)
        if not history: return await ctx.send("No global goals achieved yet.")
        desc = "### 🏛️ ARCHIVED NEURAL MILESTONES\n" + "\n".join([f"• **{e['milestone']:,}** — `Verified on {e['timestamp']}`" for e in history])
        await ctx.send(embed=main_mod.fiery_embed("GLOBAL MILESTONE ARCHIVE", desc, color=0xE67E22))

    @commands.command(name="setcounting")
    @commands.has_permissions(administrator=True)
    async def set_counting(self, ctx, channel: discord.TextChannel = None):
        """Sets the channel for the infinite counting game for this server."""
        target = channel or ctx.channel
        guild_id = ctx.guild.id
        self.counting_channel_ids[guild_id] = int(target.id)
        self.current_counts[guild_id] = 0
        self.last_user_ids[guild_id] = None
        await self.save_state(guild_id)
        main_mod = sys.modules['__main__']
        await ctx.send(embed=main_mod.fiery_embed("🔢 COUNTING PROTOCOL INITIALIZED", f"Monitoring {target.mention}. Start from **1**."))

    @commands.command(name="countfix")
    @commands.has_permissions(administrator=True)
    async def count_fix(self, ctx, new_count: int):
        """Emergency Override: Sets the current count manually."""
        guild_id = ctx.guild.id
        self.current_counts[guild_id] = new_count
        # Preserve user chain security
        await self.save_state(guild_id)
        main_mod = sys.modules['__main__']
        await ctx.send(embed=main_mod.fiery_embed("🔧 NEURAL RESYNC", f"Count set to **{new_count}**. Next asset types **{new_count + 1}**."))

    @commands.command(name="countingtop")
    async def counting_top(self, ctx, scope: str = "global"):
        """Shows top runs."""
        main_mod = sys.modules['__main__']
        def fetch_top():
            with main_mod.get_db_connection() as conn:
                if scope.lower() == "local":
                    return conn.execute("SELECT score, ruiner_id FROM counting_runs WHERE guild_id = ? ORDER BY score DESC LIMIT 10", (ctx.guild.id,)).fetchall()
                return conn.execute("SELECT score, ruiner_id FROM counting_runs ORDER BY score DESC LIMIT 10").fetchall()
        
        data = await asyncio.to_thread(fetch_top)
        if not data: return await ctx.send("No records.")
        desc = "### 🏆 TOP NEURAL SEQUENCES\n" + "".join([f"`#{i}` **{r['score']:,}** — <@{r['ruiner_id']}>\n" for i, r in enumerate(data, 1)])
        await ctx.send(embed=main_mod.fiery_embed(f"{scope.upper()} HALL OF FAME", desc))

    @commands.command(name="countinglb")
    async def counting_lb(self, ctx):
        """LOCAL SECTOR LEADERBOARD."""
        main_mod = sys.modules['__main__']
        def fetch_local():
            with main_mod.get_db_connection() as conn:
                return conn.execute("SELECT user_id, count FROM local_counting WHERE guild_id = ? ORDER BY count DESC LIMIT 10", (ctx.guild.id,)).fetchall()
        
        data = await asyncio.to_thread(fetch_local)
        if not data: return await ctx.send("No local data.")
        desc = "### 📊 SECTOR RANKINGS\n" + "".join([f"`#{i}` <@{r['user_id']}> — **{r['count']:,}**\n" for i, r in enumerate(data, 1)])
        await ctx.send(embed=main_mod.fiery_embed("LOCAL LEADERBOARD", desc))

    @commands.command(name="countstats")
    async def countstats(self, ctx, member: discord.Member = None):
        """ULTIMATE NEURAL DOSSIER."""
        target = member or ctx.author
        main_mod = sys.modules['__main__']
        guild_id = ctx.guild.id
        
        def fetch_stats():
            with main_mod.get_db_connection() as conn:
                stats = conn.execute("SELECT count_total, count_mistakes FROM users WHERE id = ?", (target.id,)).fetchone()
                local = conn.execute("SELECT count FROM local_counting WHERE user_id = ? AND guild_id = ?", (target.id, guild_id)).fetchone()
                total_global = conn.execute("SELECT SUM(count_total) FROM users").fetchone()[0] or 1
                # Scalable badge check: only fetch achieved milestones
                milestones = conn.execute("SELECT milestone FROM global_milestone_history ORDER BY milestone DESC").fetchall()
                user_badges = [f"`[Architect {m[0]:,}]`" for m in milestones if (stats['count_total'] if stats else 0) >= m[0]]
                return stats, local, total_global, user_badges

        data, local_data, total_global, badges = await asyncio.to_thread(fetch_stats)
        total = data['count_total'] if data else 0
        acc = (total / (total + (data['count_mistakes'] if data else 0)) * 100) if (total + (data['count_mistakes'] if data else 0)) > 0 else 100.0
        
        desc = (f"### 🧬 AUDIT: {target.display_name.upper()}\n"
                f"**Clearance:** {' '.join(badges[:3]) or 'Standard'}\n\n"
                f"• **Verified Numbers:** `{total:,}`\n"
                f"• **Accuracy:** `{acc:.2f}%`\n"
                f"• **Global Impact:** `{((total / total_global) * 100):.4f}%` of Echo\n\n"
                f"• **Local Sector Contrib:** `{local_data['count'] if local_data else 0:,}`")
        await ctx.send(embed=main_mod.fiery_embed("NEURAL AUDIT REPORT", desc, color=0x3498DB))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        guild_id = message.guild.id
        if guild_id not in self.counting_channel_ids or message.channel.id != self.counting_channel_ids[guild_id]:
            return

        content = message.content.strip()
        if not content.isdigit():
            if not (await self.bot.get_context(message)).valid:
                try: await message.delete()
                except: pass
            return

        number = int(content)
        current_count = self.current_counts.get(guild_id, 0)
        expected = current_count + 1
        last_user_id = self.last_user_ids.get(guild_id)

        if number != expected or message.author.id == last_user_id:
            await self.update_high_score(current_count, message.author.id, guild_id)
            await self.update_member_stats(message.author.id, guild_id, is_mistake=True)
            self.current_counts[guild_id] = 0
            self.last_user_ids[guild_id] = None
            await self.save_state(guild_id)
            await message.channel.send(embed=sys.modules['__main__'].fiery_embed("🚫 RUN RUINED", f"Failed at `{current_count}`. Reset to 0.", color=0xFF0000))
            return

        self.current_counts[guild_id] = number
        self.last_user_ids[guild_id] = message.author.id
        await self.save_state(guild_id)
        await self.update_member_stats(message.author.id, guild_id)
        await self.check_personal_milestone(message)
        await self.check_community_milestone(message)
        await self.check_global_goal(message)
        try: await message.add_reaction("✅")
        except: pass

async def setup(bot):
    await bot.add_cog(Counting(bot))
