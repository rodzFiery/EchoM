import discord
from discord.ext import commands
import os

class ClassSystem(commands.Cog):
    def __init__(self, bot, CLASSES, get_user, fiery_embed, get_db_connection):
        self.bot = bot
        self.CLASSES = CLASSES
        self.get_user = get_user
        self.fiery_embed = fiery_embed
        self.get_db_connection = get_db_connection

    async def send_class_details(self, ctx, class_name):
        """Helper to send class profile details"""
        data = self.CLASSES[class_name]
        desc = (f"**{data['icon']} {class_name.upper()} CLASS DETAILS**\n\n"
                f"🔥 **Flame Bonus:** +{int((data['bonus_flames']-1)*100)}%\n"
                f"💦 **Experience Bonus:** +{int((data['bonus_xp']-1)*100)}%\n\n"
                f"*\"{data['desc']}\"*\n\n"
                f"Use `!setclass {class_name}` to claim this role.")
        
        embed = self.fiery_embed(f"{class_name} Class Profile", desc, color=0xFF0000)
        
        # ADDED STAT OVERVIEW TO CLASS DESC
        u_raw = self.get_user(ctx.author.id)
        # FIXED: Ensure u is treated as a dict or empty dict to avoid NoneType errors
        u = dict(u_raw) if u_raw else {}
        u_balance = u.get('balance', 0)
        u_level = u.get('level', 1)
        embed.add_field(name="⛓️ Current Standing", value=f"Balance: {u_balance}F\nLevel: {u_level}", inline=False)
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

    @commands.command()
    async def dominant(self, ctx): await self.send_class_details(ctx, "Dominant")
    
    @commands.command()
    async def submissive(self, ctx): await self.send_class_details(ctx, "Submissive")
    
    @commands.command()
    async def switch(self, ctx): await self.send_class_details(ctx, "Switch")
    
    @commands.command()
    async def exhibitionist(self, ctx): await self.send_class_details(ctx, "Exhibitionist")

    @commands.command()
    async def setclass(self, ctx, choice: str = None):
        if not choice or choice.capitalize() not in self.CLASSES:
            options = "\n".join([f"**{k}**: {v['desc']}" for k,v in self.CLASSES.items()])
            embed = self.fiery_embed("Dungeon Hierarchy", f"Choose your path, little asset:\n\n{options}\n\nType `!<classname>` for details.", color=0x800000)
            if os.path.exists("LobbyTopRight.jpg"):
                file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
                return await ctx.send(file=file, embed=embed)
            return await ctx.send(embed=embed)
            
        with self.get_db_connection() as conn:
            conn.execute("UPDATE users SET class = ? WHERE id = ?", (choice.capitalize(), ctx.author.id))
            conn.commit()
        
        u_raw = self.get_user(ctx.author.id)
        u = dict(u_raw) if u_raw else {}
        u_level = u.get('level', 1)
        embed = self.fiery_embed("Class Claimed", f"✅ You are now bound to the **{choice.capitalize()}** path.\n\nYour submission level is currently **{u_level}**.", color=0x00FF00)
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

async def setup(bot):
    import sys
    # FIXED: Better way to get main variables without circular import errors
    main = sys.modules['__main__']
    await bot.add_cog(ClassSystem(
        bot, 
        main.CLASSES, 
        main.get_user, 
        main.fiery_embed, 
        main.get_db_connection
    ))
