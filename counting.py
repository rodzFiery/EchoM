import discord
from discord.ext import commands
import sys
import os
import json
import asyncio
from datetime import datetime

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Local cache now uses dictionaries keyed by Guild ID
        self.current_counts = {}
        self.last_user_ids = {}
        self.counting_channel_ids = {}
        self.load_config()

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

    def save_state(self, guild_id):
        """Save counting state and channel for a specific guild."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         (f'counting_channel_{guild_id}', str(self.counting_channel_ids.get(guild_id))))
            state = {'count': self.current_counts.get(guild_id, 0), 'last_user': self.last_user_ids.get(guild_id)}
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         (f'counting_state_{guild_id}', json.dumps(state)))
            conn.commit()

    def update_high_score(self, count, ruiner_id, guild_id):
        """Record the run in the high score ledger (Global and Local attribution)."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS counting_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, score INTEGER, ruiner_id INTEGER, guild_id INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
            except: pass
            # ADDED guild_id to track which server achieved the score
            conn.execute("INSERT INTO counting_runs (score, ruiner_id, guild_id) VALUES (?, ?, ?)", (count, ruiner_id, guild_id))
            conn.commit()

    def update_member_stats(self, user_id, guild_id, is_mistake=False):
        """Updates local/global counting stats for the user profile."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            try:
                conn.execute("ALTER TABLE users ADD COLUMN count_total INTEGER DEFAULT 0")
                conn.execute("ALTER TABLE users ADD COLUMN count_mistakes INTEGER DEFAULT 0")
                # ADDED: Table to track local server contributions
                conn.execute("CREATE TABLE IF NOT EXISTS local_counting (user_id INTEGER, guild_id INTEGER, count INTEGER DEFAULT 0, PRIMARY KEY (user_id, guild_id))")
            except: pass
            
            if is_mistake:
                conn.execute("UPDATE users SET count_mistakes = count_mistakes + 1 WHERE id = ?", (user_id,))
            else:
                conn.execute("UPDATE users SET count_total = count_total + 1 WHERE id = ?", (user_id,))
                # Increment local server contribution
                conn.execute("INSERT INTO local_counting (user_id, guild_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, guild_id) DO UPDATE SET count = count + 1", (user_id, guild_id))
            conn.commit()

    async def check_personal_milestone(self, message):
        """Logic for 50-step personal milestones (50, 100, 150, etc.)."""
        main_mod = sys.modules['__main__']
        user_id = message.author.id
        
        with main_mod.get_db_connection() as conn:
            user = conn.execute("SELECT count_total FROM users WHERE id = ?", (user_id,)).fetchone()
            total = user['count_total'] if user else 0

        # UPDATED: Reward is now 20,000 Flames for every 50 verified numbers
        # ADDED: DOUBLE FLAME WEEKEND (Sat=5, Sun=6)
        if total > 0 and total % 50 == 0:
            is_weekend = datetime.now().weekday() >= 5
            reward = 40000 if is_weekend else 20000
            theme_title = "🔥 DOUBLE FLAME WEEKEND" if is_weekend else "📜 NEURAL COUNTING CERTIFICATE"
            
            # ONLY REPORTING TO AUDIT.PY ON MILESTONE ACHIEVEMENT
            await main_mod.update_user_stats_async(user_id, amount=reward, source=f"Counting Milestone: {total}")
            
            embed = main_mod.fiery_embed(theme_title, 
                                        f"### 🎖️ MILESTONE REACHED: {total}\n"
                                        f"Asset {message.author.mention}, your numerical precision is efficient.\n\n"
                                        f"**Reward Granted:** `{reward:,} Flames` {'(2x Weekend Bonus!)' if is_weekend else ''}\n"
                                        f"**Status:** `Verified & Synchronized`\n\n"
                                        f"f\"*The Red Room appreciates your consistency.*\"", color=0xFF4500 if is_weekend else 0x00FF00)
            await message.channel.send(embed=embed)

    async def check_community_milestone(self, message):
        """Logic for community-wide milestones reached in this server (1000, 2000, etc.)."""
        main_mod = sys.modules['__main__']
        guild_id = message.guild.id
        with main_mod.get_db_connection() as conn:
            row = conn.execute("SELECT SUM(count) as total FROM local_counting WHERE guild_id = ?", (guild_id,)).fetchone()
            total_community = row['total'] if row and row['total'] else 0
            
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
        with main_mod.get_db_connection() as conn:
            total_global_row = conn.execute("SELECT SUM(count_total) FROM users").fetchone()
            total_global = total_global_row[0] if total_global_row and total_global_row[0] else 0
            
        # Milestone trigger every 50,000 up to 10,000,000
        if total_global > 0 and total_global % 50000 == 0 and total_global <= 10000000:
            badge_name = f"Neural Architect: {total_global:,}"
            
            # Record Milestone in History
            with main_mod.get_db_connection() as conn:
                try:
                    conn.execute("CREATE TABLE IF NOT EXISTS global_milestone_history (id INTEGER PRIMARY KEY AUTOINCREMENT, milestone INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
                except: pass
                conn.execute("INSERT INTO global_milestone_history (milestone) VALUES (?)", (total_global,))
                
                # Universal Badge Granting Protocol
                users_to_badge = conn.execute("SELECT id, titles FROM users").fetchall()
                for user in users_to_badge:
                    try: 
                        titles = json.loads(user['titles']) 
                    except: 
                        titles = []
                    if badge_name not in titles:
                        titles.append(badge_name)
                        conn.execute("UPDATE users SET titles = ? WHERE id = ?", (json.dumps(titles), user['id']))
                conn.commit()

            embed = main_mod.fiery_embed("🌍 UNIVERSAL NEURAL SYNC",
                                        f"### 🏆 GLOBAL GOAL REACHED: {total_global:,}\n"
                                        f"The Echo has achieved a massive milestone across all sectors.\n\n"
                                        f"**Global Badge Granted:** `[{badge_name}]`\n"
                                        f"All synchronized assets have been updated with this clearance level.\n\n"
                                        f"*The Red Room has expanded its reach.*", color=0xFFD700)
            await message.channel.send(embed=embed)

    @commands.command(name="globalgoal")
    async def global_goal_progress(self, ctx):
        """Displays the progress toward the next 50,000 global increment."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            total_global_row = conn.execute("SELECT SUM(count_total) FROM users").fetchone()
            total_global = total_global_row[0] if total_global_row and total_global_row[0] else 0
        
        next_milestone = ((total_global // 50000) + 1) * 50000
        remaining = next_milestone - total_global
        progress_pct = (total_global % 50000) / 50000
        
        # Visual Progress Bar
        bar_length = 20
        filled = int(progress_pct * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        desc = (
            f"### 🌐 NEURAL SYNCHRONIZATION STATUS\n"
            f"The Red Room is absorbing numerical frequencies globally.\n\n"
            f"**Total Verified Data:** `{total_global:,}`\n"
            f"**Next Global Goal:** `{next_milestone:,}`\n"
            f"**Data Remaining:** `{remaining:,}`\n\n"
            f"`{bar}` **{progress_pct*100:.1f}%**\n\n"
            f"*Upon reaching the next goal, all active assets will be awarded a new rank badge.*"
        )
        
        await ctx.send(embed=main_mod.fiery_embed("GLOBAL GOAL PROGRESS", desc, color=0x3498DB))

    @commands.command(name="goalhistory")
    async def global_goal_history(self, ctx):
        """Displays all previously achieved Universal Global Goals."""
        main_mod = sys.modules['__main__']
        def fetch_history():
            with main_mod.get_db_connection() as conn:
                try:
                    return conn.execute("SELECT milestone, timestamp FROM global_milestone_history ORDER BY milestone DESC").fetchall()
                except:
                    return []

        history = await asyncio.to_thread(fetch_history)
        if not history:
            return await ctx.send("No global goals have been officially archived yet.")

        desc = "### 🏛️ ARCHIVED NEURAL MILESTONES\n"
        for entry in history:
            dt = datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S').strftime('%d %b %Y')
            desc += f"• **{entry['milestone']:,}** — `Verified on {dt}`\n"

        await ctx.send(embed=main_mod.fiery_embed("GLOBAL MILESTONE ARCHIVE", desc, color=0xE67E22))

    @commands.command(name="setcounting")
    @commands.has_permissions(administrator=True)
    async def set_counting(self, ctx, channel: discord.TextChannel = None):
        """Sets the channel for the infinite counting game for this server."""
        target = channel or ctx.channel
        guild_id = ctx.guild.id
        
        # CRITICAL FIX: Ensure dictionary keys are integers and reset state immediately
        self.counting_channel_ids[guild_id] = int(target.id)
        self.current_counts[guild_id] = 0
        self.last_user_ids[guild_id] = None
        
        self.save_state(guild_id)
        main_mod = sys.modules['__main__']
        await ctx.send(embed=main_mod.fiery_embed("🔢 COUNTING PROTOCOL INITIALIZED", f"The Echo is now monitoring numbers in {target.mention} for this sector.\nStart from **1**."))

    @commands.command(name="countfix")
    @commands.has_permissions(administrator=True)
    async def count_fix(self, ctx, new_count: int):
        """Emergency Override: Sets the current count manually if the system desyncs."""
        guild_id = ctx.guild.id
        self.current_counts[guild_id] = new_count
        self.last_user_ids[guild_id] = None
        self.save_state(guild_id)
        main_mod = sys.modules['__main__']
        await ctx.send(embed=main_mod.fiery_embed("🔧 NEURAL RESYNC", f"Manual override successful. The current count is now **{new_count}**.\nThe next asset must type **{new_count + 1}**."))

    @commands.command(name="countingtop")
    async def counting_top(self, ctx, scope: str = "global"):
        """Shows top runs. Usage: !countingtop [global/local]"""
        main_mod = sys.modules['__main__']
        guild_id = ctx.guild.id
        
        def fetch_top():
            with main_mod.get_db_connection() as conn:
                if scope.lower() == "local":
                    return conn.execute("SELECT score, ruiner_id FROM counting_runs WHERE guild_id = ? ORDER BY score DESC LIMIT 10", (guild_id,)).fetchall()
                return conn.execute("SELECT score, ruiner_id FROM counting_runs ORDER BY score DESC LIMIT 10").fetchall()
        
        data = await asyncio.to_thread(fetch_top)
        if not data:
            return await ctx.send(f"The archives for `{scope}` are empty.")

        title = "GLOBAL HALL OF FAME" if scope.lower() == "global" else f"LOCAL SECTOR RECORDS: {ctx.guild.name}"
        desc = f"### 🏆 {scope.upper()} NEURAL SEQUENCES\n"
        for i, row in enumerate(data, 1):
            desc += f"`#{i}` **{row['score']:,}** — Ruined by <@{row['ruiner_id']}>\n"
        
        await ctx.send(embed=main_mod.fiery_embed(title, desc))

    @commands.command(name="countinglb")
    async def counting_lb(self, ctx):
        """LOCAL SECTOR LEADERBOARD: Ranks assets by their contributions in this server."""
        main_mod = sys.modules['__main__']
        guild_id = ctx.guild.id

        def fetch_lb():
            with main_mod.get_db_connection() as conn:
                # Ensure table exists before querying
                conn.execute("CREATE TABLE IF NOT EXISTS local_counting (user_id INTEGER, guild_id INTEGER, count INTEGER DEFAULT 0, PRIMARY KEY (user_id, guild_id))")
                return conn.execute("""
                    SELECT user_id, count FROM local_counting 
                    WHERE guild_id = ? ORDER BY count DESC LIMIT 10
                """, (guild_id,)).fetchall()

        data = await asyncio.to_thread(fetch_lb)
        if not data:
            return await ctx.send("No numerical data has been synchronized in this sector yet.")

        desc = f"### 📊 SECTOR CONTRIBUTION RANKINGS: {ctx.guild.name.upper()}\n"
        for i, row in enumerate(data, 1):
            desc += f"`#{i}` <@{row['user_id']}> — **{row['count']:,}** verified numbers\n"

        embed = main_mod.fiery_embed("LOCAL COUNTING LEADERBOARD", desc, color=0xFFA500)
        await ctx.send(embed=embed)

    @commands.command(name="countstats")
    async def countstats(self, ctx, member: discord.Member = None):
        """ULTIMATE NEURAL DOSSIER: Comprehensive Dynamic Precision Audit."""
        target = member or ctx.author
        main_mod = sys.modules['__main__']
        guild_id = ctx.guild.id
        
        def fetch_dossier():
            with main_mod.get_db_connection() as conn:
                stats = conn.execute("SELECT count_total, count_mistakes FROM users WHERE id = ?", (target.id,)).fetchone()
                local = conn.execute("SELECT count FROM local_counting WHERE user_id = ? AND guild_id = ?", (target.id, guild_id)).fetchone()
                rank_row = conn.execute("SELECT COUNT(*) + 1 FROM users WHERE count_total > (SELECT COALESCE(count_total, 0) FROM users WHERE id = ?)", (target.id,)).fetchone()
                rank = rank_row[0] if rank_row else "?"
                total_global_row = conn.execute("SELECT SUM(count_total) FROM users").fetchone()
                total_global = total_global_row[0] if total_global_row and total_global_row[0] else 1
                
                # Streak Data
                current_streak = self.current_counts.get(guild_id, 0)
                local_record_row = conn.execute("SELECT MAX(score) FROM counting_runs WHERE guild_id = ?", (guild_id,)).fetchone()
                local_record = local_record_row[0] if local_record_row and local_record_row[0] else 0
                
                # NEW: Sector Ranking Badge Logic (Top 20)
                sector_rank = "?"
                sector_lb = conn.execute("SELECT user_id FROM local_counting WHERE guild_id = ? ORDER BY count DESC", (guild_id,)).fetchall()
                for i, row in enumerate(sector_lb, 1):
                    if row['user_id'] == target.id:
                        sector_rank = i
                        break
                
                return stats, local, rank, total_global, current_streak, local_record, sector_rank

        try:
            data, local_data, rank, total_global, cur_streak, best_streak, s_rank = await asyncio.to_thread(fetch_dossier)
            
            total = data['count_total'] if data and data['count_total'] else 0
            mistakes = data['count_mistakes'] if data and data['count_mistakes'] else 0
            local_count = local_data['count'] if local_data and local_data['count'] else 0
            accuracy = (total / (total + mistakes) * 100) if (total + mistakes) > 0 else 100.0
            flames_earned = (total // 50) * 20000 

            # Badge Assignment
            badge = ""
            if isinstance(s_rank, int) and s_rank <= 20:
                tier = "ELITE" if s_rank <= 5 else "OPERATIVE"
                badge = f"\n🏆 **RANK BADGE:** `[TOP {s_rank}] SECTOR {tier}`"

            desc = (f"### 🧬 NEURAL DOSSIER: {target.display_name.upper()}\n"
                    f"*Processing real-time synchronization data...*{badge}\n\n"
                    f"🌍 **GLOBAL ARCHIVES**\n"
                    f"• **Verified Numbers:** `{total:,}`\n"
                    f"• **Accuracy Rating:** `{accuracy:.2f}%`\n"
                    f"• **Global Rank:** `#{rank}`\n"
                    f"• **Network Impact:** `{((total / total_global) * 100):.4f}%` of Echo\n\n"
                    f"🏙️ **LOCAL SECTOR: {ctx.guild.name.upper()}**\n"
                    f"• **Sector Contribution:** `{local_count:,} inputs` (Rank: `#{s_rank}`)\n"
                    f"• **Current Streak:** `{cur_streak:,}`\n"
                    f"• **Sector High Score:** `{best_streak:,}`\n\n"
                    f"💰 **ECONOMIC IMPACT**\n"
                    f"• **Total Rewards:** `{flames_earned:,} Flames` generated.\n"
                    f"• **Mistakes Logged:** `{mistakes:,}` failed sequences.")

            embed = main_mod.fiery_embed("COUNTING AUDIT REPORT", desc, color=0x3498DB)
            if os.path.exists("LobbyTopRight.jpg"):
                file = discord.File("LobbyTopRight.jpg", filename="stats.jpg")
                embed.set_thumbnail(url="attachment://stats.jpg")
                await ctx.send(file=file, embed=embed)
            else:
                await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ **Neural Audit Failed:** {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
            
        guild_id = message.guild.id
        
        # --- FIX: Ensure memory is updated if cache is empty for this guild ---
        if guild_id not in self.counting_channel_ids:
            self.load_config()

        if guild_id not in self.counting_channel_ids or message.channel.id != self.counting_channel_ids[guild_id]:
            return

        content = message.content.strip()
        if not content.isdigit():
            ctx = await self.bot.get_context(message)
            if not ctx.valid:
                try:
                    await message.delete()
                except: pass
            return

        main_mod = sys.modules['__main__']
        now = datetime.now()
        
        # --- WEEKEND TRANSITION CHECK ---
        if now.hour == 0 and now.minute == 0:
            if now.weekday() == 5: # Saturday Start
                await message.channel.send(embed=main_mod.fiery_embed("🔥 PROTOCOL: DOUBLE FLAMES", "The weekend has arrived. Reward frequencies are now doubled for all assets.", color=0xFF4500))
            elif now.weekday() == 0: # Monday End
                await message.channel.send(embed=main_mod.fiery_embed("📜 PROTOCOL: STANDARD FREQUENCY", "Weekend cycle completed. Returning to standard neural reward rates.", color=0x00FF00))

        number = int(content)
        current_count = self.current_counts.get(guild_id, 0)
        expected = current_count + 1
        last_user_id = self.last_user_ids.get(guild_id)

        if number != expected or message.author.id == last_user_id:
            ruined_count = current_count
            self.update_high_score(ruined_count, message.author.id, guild_id)
            self.update_member_stats(message.author.id, guild_id, is_mistake=True)
            
            reason = "Wrong number." if number != expected else "You cannot count twice in a row."
            
            desc = (f"### ❌ SEQUENCE TERMINATED\n"
                    f"Asset {message.author.mention} has failed the Echo.\n\n"
                    f"**Reason:** `{reason}`\n"
                    f"**Final Score:** `{ruined_count:,}`\n"
                    f"**Protocol:** Resetting to `0`.\n\n"
                    f"*The Red Room demands a new start.*")
            
            self.current_counts[guild_id] = 0
            self.last_user_ids[guild_id] = None
            self.save_state(guild_id)
            
            embed = main_mod.fiery_embed("🚫 RUN RUINED", desc, color=0xFF0000)
            if os.path.exists("LobbyTopRight.jpg"):
                file = discord.File("LobbyTopRight.jpg", filename="reset.jpg")
                embed.set_thumbnail(url="attachment://reset.jpg")
                await message.channel.send(file=file, embed=embed)
            else:
                await message.channel.send(embed=embed)
            return

        self.current_counts[guild_id] = number
        self.last_user_ids[guild_id] = message.author.id
        self.save_state(guild_id)
        
        self.update_member_stats(message.author.id, guild_id, is_mistake=False)
        await self.check_personal_milestone(message)
        await self.check_community_milestone(message)
        await self.check_global_goal(message)
        
        try:
            await message.add_reaction("✅")
        except: pass

async def setup(bot):
    await bot.add_cog(Counting(bot))
