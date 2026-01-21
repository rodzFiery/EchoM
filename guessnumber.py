import discord
from discord.ext import commands
import random
import asyncio
import sys
import os # CRITICAL: Added missing import for file checks

class GuessNumber(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="guess")
    async def guess_game(self, ctx, max_range: int = 100):
        """A high-stakes neural guessing protocol. Reward scales with range."""
        # Bridge to check if Arena is running in this channel
        if ctx.channel.id in self.active_battles:
            return await ctx.send("❌ **SURGICAL LOCK:** Cannot initiate guess protocol while the Arena is active in this sector.")
        
        # Access main module for shared helpers
        main = sys.modules['__main__']
        
        secret_number = random.randint(1, max_range)
        attempts = 0
        max_attempts = 7 if max_range <= 100 else 10
        
        embed = main.fiery_embed("🎲 GUESS NUMBER PROTOCOL", 
            f"Neural link established. I am thinking of a number between **1 and {max_range}**.\n"
            f"You have **{max_attempts} attempts** to extract the correct frequency.\n\n"
            f"💰 **Potential Reward:** Up to {max_range * 10} Flames.")
        
        # Image check preserved 100%
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="guess.jpg")
            embed.set_thumbnail(url="attachment://guess.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        while attempts < max_attempts:
            try:
                # Wait 30 seconds for each guess
                msg = await self.bot.wait_for("message", check=check, timeout=30.0)
                attempts += 1
                player_guess = int(msg.content)

                if player_guess == secret_number:
                    # Calculate reward: Scaling based on difficulty (range)
                    reward = random.randint(max_range * 5, max_range * 15)
                    xp_reward = random.randint(100, 500)
                    
                    # MASTER BRIDGE: Passing all 13 arguments to match prizes.py via main.py
                    await main.update_user_stats_async(
                        ctx.author.id, 
                        amount=reward, 
                        xp_gain=xp_reward, 
                        wins=0, kills=0, deaths=0, 
                        source="Guess Win",
                        get_user_func=main.get_user,
                        bot_obj=self.bot,
                        db_func=main.get_db_connection,
                        class_dict=main.CLASSES,
                        nsfw=main.nsfw_mode_active,
                        audit_func=main.send_audit_log
                    )
                    
                    win_emb = main.fiery_embed("✅ PROTOCOL SUCCESS", 
                        f"Congratulations, {ctx.author.mention}. You found the frequency: **{secret_number}**.\n\n"
                        f"💰 **Earned:** {reward:,} Flames\n"
                        f"🔥 **Experience:** +{xp_reward} XP", color=0x00FF00)
                    return await ctx.send(embed=win_emb)

                elif player_guess < secret_number:
                    await ctx.send(f"🔼 **HIGHER.** ({max_attempts - attempts} attempts remaining)")
                else:
                    await ctx.send(f"🔽 **LOWER.** ({max_attempts - attempts} attempts remaining)")

            except asyncio.TimeoutError:
                return await ctx.send(f"⌛ **CONNECTION LOST:** You took too long. The number was **{secret_number}**.")

        fail_emb = main.fiery_embed("❌ PROTOCOL FAILED", 
            f"Attempts exhausted. The correct frequency was **{secret_number}**.\n"
            f"Better luck in the next simulation.", color=0xFF0000)
        await ctx.send(embed=fail_emb)

    # Bridge for the main active_battles check
    @property
    def active_battles(self):
        engine = self.bot.get_cog("IgnisEngine")
        return engine.active_battles if engine else set()

async def setup(bot):
    await bot.add_cog(GuessNumber(bot))
