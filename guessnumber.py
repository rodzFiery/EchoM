import discord
from discord.ext import commands
import random
import sys
import json
import time

class GuessNumber(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_number = random.randint(0, 100)
        self.game_channel_id = None
        self.server_total_tries = 0
        self.start_time = time.time() # Track start of round
        self.round_tries = 0 # Tries for current round
        self.load_config()

    def load_config(self):
        # Using sys.modules to access main bot functions
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                row = conn.execute("SELECT value FROM config WHERE key = 'guess_config'").fetchone()
                if row:
                    data = json.loads(row['value'])
                    self.game_channel_id = data.get('channel_id')
                    self.server_total_tries = data.get('server_tries', 0)
        except Exception as e: 
            print(f"GuessNumber Load Error: {e}")

    def save_config(self):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            data = {'channel_id': self.game_channel_id, 'server_tries': self.server_total_tries}
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         ('guess_config', json.dumps(data)))
            conn.commit()

    @commands.command(name="setguesschannel")
    @commands.has_permissions(administrator=True)
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        """Sets the channel where the bot listens for numbers."""
        self.game_channel_id = (channel or ctx.channel).id
        self.save_config()
        await ctx.send(f"✅ Guessing channel set to <#{self.game_channel_id}>. Target reset!")
        self.target_number = random.randint(0, 100)
        self.start_time = time.time()
        self.round_tries = 0

    @commands.command(name="setguess")
    @commands.has_permissions(administrator=True)
    async def set_guess_by_id(self, ctx, channel_id: int):
        """Alternative command to set the guess channel using a raw ID."""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return await ctx.send("❌ Invalid Channel ID. I cannot find that frequency.")
        self.game_channel_id = channel.id
        self.save_config()
        await ctx.send(f"✅ Guessing system initialized in <#{self.game_channel_id}>.")
        self.target_number = random.randint(0, 100)
        self.start_time = time.time()
        self.round_tries = 0

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not self.game_channel_id or message.channel.id != self.game_channel_id:
            return

        if not message.content.strip().isdigit():
            return

        guess = int(message.content.strip())
        self.server_total_tries += 1
        self.round_tries += 1
        
        main_mod = sys.modules['__main__']
        
        # Update user total tries in DB
        try:
            with main_mod.get_db_connection() as conn:
                conn.execute("UPDATE users SET guess_tries = guess_tries + 1 WHERE id = ?", (message.author.id,))
                conn.commit()
        except Exception as e:
            print(f"DB Update Error: {e}")

        if guess < self.target_number:
            await message.add_reaction("⬆️")
        elif guess > self.target_number:
            await message.add_reaction("⬇️")
        else:
            # WINNER PROTOCOL
            user_data = main_mod.get_user(message.author.id)
            # Fallback to 0 if guess_tries is None to avoid calculation errors
            global_tries = user_data.get('guess_tries') if user_data else 1
            
            # --- CALCULATE RECORDS ---
            time_taken = round(time.time() - self.start_time, 2)
            
            with main_mod.get_db_connection() as conn:
                # Get Global/Server stats
                conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('total_games_played', '0')")
                conn.execute("UPDATE config SET value = CAST(value AS INTEGER) + 1 WHERE key = 'total_games_played'")
                
                # Check for Fastest Record
                record_row = conn.execute("SELECT value FROM config WHERE key = 'fastest_guess'").fetchone()
                new_record = False
                
                if not record_row:
                    new_record = True
                else:
                    try:
                        old_record = json.loads(record_row['value'])
                        if time_taken < float(old_record['time']):
                            new_record = True
                    except:
                        new_record = True

                if new_record:
                    record_data = {'time': time_taken, 'user': message.author.name, 'number': self.target_number}
                    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('fastest_guess', ?)", (json.dumps(record_data),))
                
                stats_row = conn.execute("SELECT value FROM config WHERE key = 'total_games_played'").fetchone()
                total_games = stats_row['value'] if stats_row else 0
                conn.commit()

            # --- WINNER CARD EMBED (ECHO THEMED) ---
            embed = main_mod.fiery_embed("🛰️ NEURAL SYNC: ECHO CERTIFICATE", 
                f"**Frequency matched successfully, {message.author.mention}.**\n"
                f"The Echo has verified your transmission.")
            
            embed.add_field(name="📜 Sync Details", value=(
                f"🎯 **Target Number:** {self.target_number}\n"
                f"⏱️ **Time Taken:** {time_taken}s\n"
                f"🧪 **Round Attempts:** {self.round_tries}"
            ), inline=True)
            
            embed.add_field(name="📊 Global Metrics", value=(
                f"👤 **Your Lifetime Tries:** {global_tries}\n"
                f"🌍 **Global Games Finished:** {total_games}\n"
                f"🏛️ **Server Total Load:** {self.server_total_tries}"
            ), inline=True)

            if new_record:
                embed.add_field(name="🚀 NEW WORLD RECORD", value=f"You are the fastest Echo in history: **{time_taken}s**!", inline=False)

            embed.set_image(url="https://i.imgur.com/your_echo_themed_card.png") # Winner Card Image
            embed.set_footer(text="Verification Code: ECHO-" + str(random.randint(1000, 9999)))
            
            await message.channel.send(embed=embed)
            
            # Reset for next round
            self.target_number = random.randint(0, 100)
            self.start_time = time.time()
            self.round_tries = 0
            self.save_config()

async def setup(bot):
    # ADDED: Critical DB check to prevent "no such column: guess_tries"
    main_mod = sys.modules['__main__']
    try:
        with main_mod.get_db_connection() as conn:
            # Try to add column, will fail gracefully if it exists
            conn.execute("ALTER TABLE users ADD COLUMN guess_tries INTEGER DEFAULT 0")
    except: pass 
    await bot.add_cog(GuessNumber(bot))
