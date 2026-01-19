import discord
from discord.ext import commands
import sys
import os
import json
import asyncio

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
                    guild_id = int(row['key'].split('_')[-1])
                    self.counting_channel_ids[guild_id] = int(row['value'])
                
                # Load all guild-specific states
                s_rows = conn.execute("SELECT key, value FROM config WHERE key LIKE 'counting_state_%'").fetchall()
                for row in s_rows:
                    guild_id = int(row['key'].split('_')[-1])
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

    def update_high_score(self, count, ruiner_id):
        """Record the run in the high score ledger (Global across all servers)."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS counting_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, score INTEGER, ruiner_id INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
            except: pass
            conn.execute("INSERT INTO counting_runs (score, ruiner_id) VALUES (?, ?)", (count, ruiner_id))
            conn.commit()

    def update_member_stats(self, user_id, is_mistake=False):
        """Updates local/global counting stats for the user profile."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            try:
                conn.execute("ALTER TABLE users ADD COLUMN count_total INTEGER DEFAULT 0")
                conn.execute("ALTER TABLE users ADD COLUMN count_mistakes INTEGER DEFAULT 0")
            except: pass
            
            if is_mistake:
                conn.execute("UPDATE users SET count_mistakes = count_mistakes + 1 WHERE id = ?", (user_id,))
            else:
                conn.execute("UPDATE users SET count_total = count_total + 1 WHERE id = ?", (user_id,))
            conn.commit()

    async def check_personal_milestone(self, message):
        """Logic for 250-step personal milestones (250, 500, 750, etc.)."""
        main_mod = sys.modules['__main__']
        user_id = message.author.id
        
        with main_mod.get_db_connection() as conn:
            user = conn.execute("SELECT count_total FROM users WHERE id = ?", (user_id,)).fetchone()
            total = user['count_total'] if user else 0

        if total > 0 and total % 250 == 0:
            reward = 5000
            # ONLY REPORTING TO AUDIT.PY ON MILESTONE ACHIEVEMENT
            await main_mod.update_user_stats_async(user_id, amount=reward, source=f"Counting Milestone: {total}")
            
            embed = main_mod.fiery_embed("📜 NEURAL COUNTING CERTIFICATE", 
                                        f"### 🎖️ MILESTONE REACHED: {total}\n"
                                        f"Asset {message.author.mention}, your numerical precision is efficient.\n\n"
                                        f"**Reward Granted:** `{reward:,} Flames`\n"
                                        f"**Status:** `Verified & Synchronized`\n\n"
                                        f"*The Red Room appreciates your consistency.*", color=0x00FF00)
            await message.channel.send(embed=embed)

    @commands.command(name="setcounting")
    @commands.has_permissions(administrator=True)
    async def set_counting(self, ctx, channel: discord.TextChannel = None):
        """Sets the channel for the infinite counting game for this server."""
        target = channel or ctx.channel
        guild_id = ctx.guild.id
        self.counting_channel_ids[guild_id] = target.id
        self.save_state(guild_id)
        main_mod = sys.modules['__main__']
        await ctx.send(embed=main_mod.fiery_embed("🔢 COUNTING PROTOCOL INITIALIZED", f"The Echo is now monitoring numbers in {target.mention} for this sector.\nStart from **1**."))

    @commands.command(name="countingtop")
    async def counting_top(self, ctx):
        """Shows the top 10 best counting runs globally (all servers) and who ruined them."""
        main_mod = sys.modules['__main__']
        def fetch_top():
            with main_mod.get_db_connection() as conn:
                return conn.execute("SELECT score, ruiner_id FROM counting_runs ORDER BY score DESC LIMIT 10").fetchall()
        
        data = await asyncio.to_thread(fetch_top)
        if not data:
            return await ctx.send("The archives are empty. No runs recorded yet.")

        desc = "### 🏆 GLOBAL NEURAL SEQUENCES\n"
        for i, row in enumerate(data, 1):
            desc += f"`#{i}` **{row['score']:,}** — Ruined by <@{row['ruiner_id']}>\n"
        
        await ctx.send(embed=main_mod.fiery_embed("GLOBAL COUNTING HALL OF FAME", desc))

    # ===== NEW: THEMED COUNTING STATS COMMAND =====
    @commands.command(name="countstats")
    async def countstats(self, ctx, member: discord.Member = None):
        """ULTIMATE NEURAL AUDIT: Comprehensive report of numerical precision."""
        target = member or ctx.author
        main_mod = sys.modules['__main__']
        
        def fetch_dossier():
            with main_mod.get_db_connection() as conn:
                # Personal Stats
                stats = conn.execute("SELECT count_total, count_mistakes FROM users WHERE id = ?", (target.id,)).fetchone()
                # Personal Rank
                rank = conn.execute("SELECT COUNT(*) + 1 FROM users WHERE count_total > (SELECT count_total FROM users WHERE id = ?)", (target.id,)).fetchone()[0]
                # Highest Ruined Run
                highest = conn.execute("SELECT MAX(score) FROM counting_runs WHERE ruiner_id = ?", (target.id,)).fetchone()[0]
                # Global context
                total_global = conn.execute("SELECT SUM(count_total) FROM users").fetchone()[0] or 1
                return stats, rank, highest, total_global

        data, rank, highest_ruin, total_global = await asyncio.to_thread(fetch_dossier)
        
        total = data['count_total'] if data else 0
        mistakes = data['count_mistakes'] if data else 0
        highest_ruin = highest_ruin or 0
        
        # Logic for calculation
        accuracy = (total / (total + mistakes) * 100) if (total + mistakes) > 0 else 100.0
        contribution = (total / total_global) * 100

        # Tier Logic
        if total > 5000: tier = "Numerical Architect"
        elif total > 1000: tier = "Sequence Guardian"
        elif total > 500: tier = "Efficient Counter"
        else: tier = "Fresh Asset"

        desc = (f"### 🧬 NEURAL AUDIT: {target.display_name.upper()}\n"
                f"*Extracting numerical sequence history from the Echo...*\n\n"
                f"📊 **EFFICIENCY RATING**\n"
                f"```ml\n"
                f"Accuracy: {accuracy:.2f}% | Rank: #{rank}\n"
                f"Tier: {tier}\n"
                f"```\n"
                f"📑 **INDIVIDUAL METRICS**\n"
                f"• **Verified Numbers:** `{total:,}`\n"
                f"• **Neural Errors (Mistakes):** `{mistakes:,}`\n"
                f"• **Highest Run Interrupted:** `{highest_ruin:,}`\n\n"
                f"🔗 **SYSTEM CONTRIBUTION**\n"
                f"You have provided **{contribution:.4f}%** of the total numerical data processed by the Red Room.")

        embed = main_mod.fiery_embed("COUNTING DOSSIER", desc, color=0x3498DB)
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="stats.jpg")
            embed.set_thumbnail(url="attachment://stats.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
            
        guild_id = message.guild.id
        if message.channel.id != self.counting_channel_ids.get(guild_id):
            return

        content = message.content.strip()
        if not content.isdigit():
            return

        main_mod = sys.modules['__main__']
        number = int(content)
        current_count = self.current_counts.get(guild_id, 0)
        expected = current_count + 1
        last_user_id = self.last_user_ids.get(guild_id)

        # Check if user is repeating themselves or sent wrong number
        if number != expected or message.author.id == last_user_id:
            ruined_count = current_count
            self.update_high_score(ruined_count, message.author.id)
            self.update_member_stats(message.author.id, is_mistake=True)
            
            reason = "Wrong number." if number != expected else "You cannot count twice in a row."
            
            desc = (f"### ❌ SEQUENCE TERMINATED\n"
                    f"Asset {message.author.mention} has failed the Echo.\n\n"
                    f"**Reason:** `{reason}`\n"
                    f"**Final Score:** `{ruined_count:,}`\n"
                    f"**Protocol:** Resetting to `0`.\n\n"
                    f"*The Red Room demands a new start.*")
            
            # Reset state for this guild
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

        # Correct number for this guild
        self.current_counts[guild_id] = number
        self.last_user_ids[guild_id] = message.author.id
        self.save_state(guild_id)
        
        # --- STATS & MILESTONE PROTOCOL (Global User Progress) ---
        self.update_member_stats(message.author.id, is_mistake=False)
        await self.check_personal_milestone(message)
        
        try:
            await message.add_reaction("✅")
        except: pass

async def setup(bot):
    await bot.add_cog(Counting(bot))
