import discord
from discord.ext import commands
import random
import sys
from datetime import timedelta
import worknranks

class WinSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Configuration: (Min Flames, Max Flames), XP
        self.payouts = {
            "slut": ((30000, 60000), 1500),
            "cuckold": ((30000, 60000), 1000),
            "deepthroat": ((30000, 60000), 2500),
            "spit": ((30000, 60000), 1200),
            "tease": ((30000, 60000), 1800),
            "spank": ((30000, 60000), 1500),
            "slap": ((30000, 60000), 1200),
            "makemedirty": ((30000, 60000), 2000),
            "3some": ((30000, 60000), 2500),
            "dp": ((30000, 60000), 2500),
            "anal": ((30000, 60000), 2200),
            "bendover": ((30000, 60000), 1800)
        }
        self.cooldown = timedelta(hours=3)

    async def execute_win_command(self, ctx, cmd_name):
        import main
        from lexicon import FieryLexicon
        
        # Pull globals from main
        nsfw = getattr(main, "nsfw_mode_active", False) or getattr(main, "basic_nsfw_active", False)
        
        flame_range, xp_amt = self.payouts[cmd_name]
        
        await worknranks.handle_work_command(
            ctx, 
            self.bot, 
            cmd_name, 
            flame_range, 
            main.get_user, 
            main.update_user_stats_async, 
            main.fiery_embed, 
            main.get_db_connection, 
            FieryLexicon, 
            nsfw,
            xp_override=xp_amt,
            custom_cooldown=self.cooldown
        )

    @commands.command(name="slut")
    async def slut(self, ctx):
        await self.execute_win_command(ctx, "slut")

    @commands.command(name="cuckold")
    async def cuckold(self, ctx):
        await self.execute_win_command(ctx, "cuckold")

    @commands.command(name="deepthroat")
    async def deepthroat(self, ctx):
        await self.execute_win_command(ctx, "deepthroat")

    @commands.command(name="spit")
    async def spit(self, ctx):
        await self.execute_win_command(ctx, "spit")

    @commands.command(name="tease")
    async def tease(self, ctx):
        await self.execute_win_command(ctx, "tease")

    @commands.command(name="spank")
    async def spank(self, ctx):
        await self.execute_win_command(ctx, "spank")

    @commands.command(name="slap")
    async def slap(self, ctx):
        await self.execute_win_command(ctx, "slap")

    @commands.command(name="makemedirty")
    async def makemedirty(self, ctx):
        await self.execute_win_command(ctx, "makemedirty")

    @commands.command(name="3some")
    async def threesome(self, ctx):
        await self.execute_win_command(ctx, "3some")

    @commands.command(name="dp")
    async def dp(self, ctx):
        await self.execute_win_command(ctx, "dp")

    @commands.command(name="anal")
    async def anal(self, ctx):
        await self.execute_win_command(ctx, "anal")

    @commands.command(name="bendover")
    async def bendover(self, ctx):
        await self.execute_win_command(ctx, "bendover")

async def setup(bot):
    await bot.add_cog(WinSystem(bot))
