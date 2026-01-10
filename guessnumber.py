import discord
from discord.ext import commands
import random
import sys
import json

class GuessNumber(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_number = random.randint(0, 100)
        self.game_channel_id = None
        self.server_total_tries = 0
        self.load_config()

    def load_config(self):
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                row = conn.execute("SELECT value FROM config WHERE key = 'guess_config'").fetchone()
                if row:
                    data = json.loads(row['value'])
                    self.game_channel_id = data.get('channel_id')
                    self.server_total_tries = data.get('server_tries', 0)
        except: pass

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

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not self.game_channel_id or message.channel.id != self.game_channel_id:
            return

        if not message.content.isdigit():
            return

        guess = int(message.content)
        self.server_total_tries += 1
        
        main_mod = sys.modules['__main__']
        # Update user total tries in DB
        with main_mod.get_db_connection() as conn:
            conn.execute("UPDATE users SET guess_tries = guess_tries + 1 WHERE id = ?", (message.author.id,))
            conn.commit()

        if guess < self.target_number:
            await message.add_reaction("⬆️")
        elif guess > self.target_number:
            await message.add_reaction("⬇️")
        else:
            # WINNER PROTOCOL
            user_data = main_mod.get_user(message.author.id)
            global_tries = user_data.get('guess_tries', 1)
            
            embed = main_mod.fiery_embed("🎉 NEURAL SYNC ACHIEVED", 
                f"Congratulations {message.author.mention}!\n\n"
                f"You found the frequency: **{self.target_number}**\n"
                f"--- STATISTICS ---\n"
                f"👤 **Your Global Tries:** {global_tries}\n"
                f"🌍 **Server Total Tries:** {self.server_total_tries}")
            
            embed.set_image(url="https://i.imgur.com/your_winner_card_placeholder.png") # Winner Card
            embed.set_footer(text="A new frequency is being generated...")
            
            await message.channel.send(embed=embed)
            
            # Reset for next round
            self.target_number = random.randint(0, 100)
            self.save_config()

async def setup(bot):
    # ADDED: Critical DB check to prevent "no such column: guess_tries"
    main_mod = sys.modules['__main__']
    try:
        with main_mod.get_db_connection() as conn:
            conn.execute("ALTER TABLE users ADD COLUMN guess_tries INTEGER DEFAULT 0")
    except: pass # Column already exists
    await bot.add_cog(GuessNumber(bot))
