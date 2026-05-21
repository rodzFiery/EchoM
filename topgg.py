import discord
from discord.ext import commands
import aiohttp
import os
import db_module

class TopGG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.token = os.getenv("TOPGG_TOKEN")
        self.bot_id = os.getenv("BOT_ID")
        
        # --- ADDED: CENTRALIZED CONTROL LISTS ---
        # 1. Add the exact Class Names of the Cogs you want locked behind a vote.
        # We are using specific commands instead, so this can remain empty.
        self.locked_cogs = [] 
        
        # 2. Add specific command names from main.py (since they don't belong to a Cog)
        self.locked_commands = [
            "daily", "weekly", "monthly", "work", "experiment", "mystery", 
            "cumcleaner", "beg", "flirt", "pimp", "slut", "cuckold", 
            "deepthroat", "spit", "tease", "spank", "slap", "makemedirty", 
            "3some", "dp", "anal", "me", "achievements", "balance", 
            "ranking", "hall", "streaks", "quests", "catch", "pokedex", 
            "collections", "velvetdex", "dice", "blackjack", "roulette", 
            "slots", "bendover", "setclass", "dominant", "submissive", 
            "switch", "exhibitionist", "countstats", "serverstats", 
            "countinglb", "countingtop", "globalgoal", "goalhistory", 
            "ask", "contract", "accept", "ship", "match3some", "flirtyship", 
            "matchme", "shiphistory", "marry", "divorce", "bestfriend", 
            "submit", "lustprofile", "lovescore", "matchmaking", "bondtrial", 
            "torture", "fuck", "duel", "fightecho", "shop", "sell", 
            "inv", "checkbuffs", "limit", "react", "echostart", "flash"
        ]
        
        # 3. Register the Global Interceptor when the bot boots
        self.bot.add_check(self.global_vote_interceptor)

    def cog_unload(self):
        # ADDED: Safely remove the interceptor if you reload the topgg extension
        self.bot.remove_check(self.global_vote_interceptor)

    # --- ADDED: THE GLOBAL INTERCEPTOR ---
    async def global_vote_interceptor(self, ctx):
        """Intercepts every command across all files to enforce the vote lists."""
        if not ctx.command:
            return True
            
        cog_name = ctx.command.cog_name
        command_name = ctx.command.name
        
        # If the command is NOT in our locked lists, let it pass instantly
        if cog_name not in self.locked_cogs and command_name not in self.locked_commands:
            return True 
            
        # If it IS in the locked list, execute the vote check
        voted = await self.has_voted(ctx.author.id)
        if voted:
            # THIS LETS THE COMMAND RUN NORMALLY BECAUSE THEY VOTED
            return True 
            
        # If they haven't voted, block execution and send the visual prompt natively
        target_id = self.bot_id or self.bot.user.id
        embed = self.bot.fiery_embed(
            "🚫 LOCK PROTOCOL: VOTE REQUIRED", 
            f"This neural pathway requires active validation.\n"
            f"Please vote here to unlock this sequence for the next 12 hours:\n"
            f"🔗 https://top.gg/bot/{target_id}/vote"
        )
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)
            
        # Returning False tells the Discord API to abort the command silently
        return False

    async def has_voted(self, user_id):
        """Checks if a user has voted for the bot in the last 12 hours."""
        if not self.token:
            print("⚠️ [TOP.GG] Warning: TOPGG_TOKEN not found in environment.")
            return False
            
        target_id = self.bot_id or self.bot.user.id
        
        url = f"https://top.gg/api/bots/{target_id}/check?userId={user_id}"
        headers = {"Authorization": self.token}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('voted') == 1
                    else:
                        print(f"⚠️ [TOP.GG] API returned status {resp.status}")
            except Exception as e:
                print(f"❌ [TOP.GG] API Check error: {e}")
                return False
        return False

    @commands.command()
    async def checkvote(self, ctx):
        """Checks if the user has voted and rewards them if applicable."""
        voted = await self.has_voted(ctx.author.id)
        
        target_id = self.bot_id or self.bot.user.id
        
        if voted:
            embed = self.bot.fiery_embed("✅ VOTE VERIFIED", "You have voted! Your access to premium perks is active.")
        else:
            embed = self.bot.fiery_embed("❌ VOTE REQUIRED", f"You haven't voted in the last 12 hours.\nVote here to support the system: https://top.gg/bot/{target_id}/vote")
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TopGG(bot))
