import discord
from discord.ext import commands
import aiohttp
import os
import db_module # Connected to your central database logic

class TopGG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.token = os.getenv("TOPGG_TOKEN")
        self.bot_id = os.getenv("BOT_ID")

    async def has_voted(self, user_id):
        """Checks if a user has voted for the bot in the last 12 hours."""
        if not self.token or not self.bot_id:
            return False
            
        url = f"https://top.gg/api/bots/{self.bot_id}/check?userId={user_id}"
        headers = {"Authorization": self.token}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('voted') == 1
            except Exception as e:
                print(f"❌ [TOP.GG] API Check error: {e}")
                return False
        return False

    @commands.command()
    async def checkvote(self, ctx):
        """Checks if the user has voted and rewards them if applicable."""
        voted = await self.has_voted(ctx.author.id)
        
        # Using your global fiery_embed from main.py
        if voted:
            embed = self.bot.fiery_embed("✅ VOTE VERIFIED", "You have voted!")
        else:
            embed = self.bot.fiery_embed("❌ VOTE REQUIRED", f"You haven't voted in the last 12 hours.\nVote here to support the system: https://top.gg/bot/{self.bot_id}/vote")
        
        # Using your local LobbyTopRight image if available
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TopGG(bot))
