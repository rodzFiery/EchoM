import discord
from discord.ext import commands
import sys
import os
import json
import asyncio

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Local cache for current count and high scores
        self.current_count = 0
        self.last_user_id = None
        self.counting_channel_id = None
        self.load_config()

    def load_config(self):
        """Load counting data from the database config."""
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                # Load channel
                c_row = conn.execute("SELECT value FROM config WHERE key = 'counting_channel'").fetchone()
                if c_row: self.counting_channel_id = int(c_row['value'])
                
                # Load current state
                s_row = conn.execute("SELECT value FROM config WHERE key = 'counting_state'").fetchone()
                if s_row:
                    state = json.loads(s_row['value'])
                    self.current_count = state.get('count', 0)
                    self.last_user_id = state.get('last_user', None)
        except: pass

    def save_state(self):
        """Save counting state and channel."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         ('counting_channel', str(self.counting_channel_id)))
            state = {'count': self.current_count, 'last_user': self.last_user_id}
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         ('counting_state', json.dumps(state)))
            conn.commit()

    def update_high_score(self, count, ruiner_id):
        """Record the run in the high score ledger."""
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
        """Sets the channel for the infinite counting game."""
        target = channel or ctx.channel
        self.counting_channel_id = target.id
        self.save_state()
        main_mod = sys.modules['__main__']
        await ctx.send(embed=main_mod.fiery_embed("🔢 COUNTING PROTOCOL INITIALIZED", f"The Echo is now monitoring numbers in {target.mention}.\nStart from **1**."))

    @commands.command(name="countingtop")
    async def counting_top(self, ctx):
        """Shows the top 10 best counting runs and who ruined them."""
        main_mod = sys.modules['__main__']
        def fetch_top():
            with main_mod.get_db_connection() as conn:
                return conn.execute("SELECT score, ruiner_id FROM counting_runs ORDER BY score DESC LIMIT 10").fetchall()
        
        data = await asyncio.to_thread(fetch_top)
        if not data:
            return await ctx.send("The archives are empty. No runs recorded yet.")

        desc = "### 🏆 TOP 10 NEURAL SEQUENCES\n"
        for i, row in enumerate(data, 1):
            desc += f"`#{i}` **{row['score']:,}** — Ruined by <@{row['ruiner_id']}>\n"
        
        await ctx.send(embed=main_mod.fiery_embed("COUNTING HALL OF FAME", desc))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.channel.id != self.counting_channel_id:
            return

        content = message.content.strip()
        if not content.isdigit():
            return

        main_mod = sys.modules['__main__']
        number = int(content)
        expected = self.current_count + 1

        # Check if user is repeating themselves or sent wrong number
        if number != expected or message.author.id == self.last_user_id:
            ruined_count = self.current_count
            self.update_high_score(ruined_count, message.author.id)
            self.update_member_stats(message.author.id, is_mistake=True)
            
            reason = "Wrong number." if number != expected else "You cannot count twice in a row."
            
            desc = (f"### ❌ SEQUENCE TERMINATED\n"
                    f"Asset {message.author.mention} has failed the Echo.\n\n"
                    f"**Reason:** `{reason}`\n"
                    f"**Final Score:** `{ruined_count:,}`\n"
                    f"**Protocol:** Resetting to `0`.\n\n"
                    f"*The Red Room demands a new start.*")
            
            # Reset state
            self.current_count = 0
            self.last_user_id = None
            self.save_state()
            
            embed = main_mod.fiery_embed("🚫 RUN RUINED", desc, color=0xFF0000)
            if os.path.exists("LobbyTopRight.jpg"):
                file = discord.File("LobbyTopRight.jpg", filename="reset.jpg")
                embed.set_thumbnail(url="attachment://reset.jpg")
                await message.channel.send(file=file, embed=embed)
            else:
                await message.channel.send(embed=embed)
            return

        # Correct number
        self.current_count = number
        self.last_user_id = message.author.id
        self.save_state()
        
        # --- STATS & MILESTONE PROTOCOL ---
        self.update_member_stats(message.author.id, is_mistake=False)
        await self.check_personal_milestone(message)
        
        # Award 100 Flames per correct count and report to audit.py system
        reward = 100
        await main_mod.update_user_stats_async(message.author.id, amount=reward, source="Counting Contribution")
        
        try:
            await message.add_reaction("✅")
        except: pass

async def setup(bot):
    await bot.add_cog(Counting(bot))
