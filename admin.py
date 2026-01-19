import discord
from discord.ext import commands
import shutil
import os
import json
import importlib
from datetime import datetime

class AdminSystem(commands.Cog):
    def __init__(self, bot, db_path, fiery_embed, save_game_config, get_user, get_db_connection, update_user_stats_async):
        self.bot = bot
        self.DATABASE_PATH = db_path
        self.fiery_embed = fiery_embed
        self.save_game_config = save_game_config
        self.get_user = get_user
        self.get_db_connection = get_db_connection
        self.update_user_stats_async = update_user_stats_async

    # ===== NSFW Special Commands =====
    @commands.command()
    @commands.is_owner()
    async def nsfwtime(self, ctx):
        # FIXED: Removed 'import main' to prevent circular import crash
        # Accessible via the bot instance directly to change the global state
        import sys
        main_module = sys.modules['__main__']
        main_module.nsfw_mode_active = True
        self.save_game_config()
        ext = self.bot.get_cog("FieryExtensions")
        if ext: await ext.trigger_nsfw_start(ctx)

    @commands.command()
    @commands.is_owner()
    async def nomorensfw(self, ctx):
        # FIXED: Removed 'import main' to prevent circular import crash
        import sys
        main_module = sys.modules['__main__']
        main_module.nsfw_mode_active = False
        self.save_game_config()
        embed = self.fiery_embed("NSFW Mode Ended", "The Echogames has closed. Returning to standard Red Room protocols.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)

    @commands.command()
    @commands.is_owner()
    async def grantbadge(self, ctx, member: discord.Member, badge: str):
        u = self.get_user(member.id)
        try: titles = json.loads(u['titles'])
        except: titles = []
        
        if badge not in titles:
            titles.append(badge)
            with self.get_db_connection() as conn:
                conn.execute("UPDATE users SET titles = ? WHERE id = ?", (json.dumps(titles), member.id))
                conn.commit()
            embed = self.fiery_embed("Badge Granted", f"✅ Granted badge **{badge}** to {member.display_name}")
        else:
            embed = self.fiery_embed("Badge Conflict", "User already has this badge.")
        
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)

    # ===== ADDED: FLAMES COMMAND =====
    @commands.command()
    async def flames(self, ctx, member: discord.Member, amount: int):
        """Staff/Owner command to grant flames to a user."""
        # Role checking for Staff, King, Boss, Owner, Familiar keywords
        staff_keywords = ["staff", "king", "boss", "owner", "familiar"]
        is_staff = any(any(key in role.name.lower() for key in staff_keywords) for role in ctx.author.roles)
        is_owner = await self.bot.is_owner(ctx.author)

        if not (is_staff or is_owner):
            embed = self.fiery_embed("Access Denied", "❌ Only the Elite or Staff hold the keys to the furnace.")
            return await ctx.send(embed=embed)

        try:
            await self.update_user_stats_async(member.id, amount=amount, source="Master's Decree")
            embed = self.fiery_embed("Flames Dispatched", f"🔥 The Master has funneled **{amount:,} Flames** into {member.mention}'s vault.")
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed)
        except Exception as e:
            await ctx.send(f"❌ **Failed to update ledger:** {e}")

    # ===== MAINTENANCE & RELOAD =====
    @commands.command()
    @commands.is_owner()
    async def backup(self, ctx):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{self.DATABASE_PATH}.backup_{timestamp}"
        try:
            shutil.copy2(self.DATABASE_PATH, backup_name)
            embed = self.fiery_embed("Database Backup", f"✅ Saved in persistence volume as `{backup_name}`")
        except Exception as e:
            embed = self.fiery_embed("Backup Failure", f"❌ **ERROR:** {e}")
        
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, cog_name: str):
        try:
            if cog_name.lower() == "achievements":
                await self.bot.reload_extension("achievements")
            elif cog_name.lower() == "ignis":
                import ignis
                await self.bot.remove_cog("IgnisEngine")
                importlib.reload(ignis)
                # Recarregamento complexo preservando referências
                import sys
                main_module = sys.modules['__main__']
                RANKS = main_module.RANKS
                CLASSES = main_module.CLASSES
                AUDIT_CHANNEL_ID = main_module.AUDIT_CHANNEL_ID
                await self.bot.add_cog(ignis.IgnisEngine(self.bot, self.update_user_stats_async, self.get_user, self.fiery_embed, self.get_db_connection, RANKS, CLASSES, AUDIT_CHANNEL_ID))
            elif cog_name.lower() in ["extensions", "ship", "shop", "collect", "fight", "casino", "ask"]:
                await self.bot.reload_extension(cog_name.lower())
            else:
                embed = self.fiery_embed("Reload Error", f"❌ Cog `{cog_name}` not found.")
                return await ctx.send(embed=embed)
            
            embed = self.fiery_embed("Reload Success", f"🔥 **{cog_name.upper()}** reloaded!")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ **ERROR:** {e}")

async def setup(bot):
    import sys
    main_module = sys.modules['__main__']
    DATABASE_PATH = main_module.DATABASE_PATH
    fiery_embed = main_module.fiery_embed
    save_game_config = main_module.save_game_config
    get_user = main_module.get_user
    get_db_connection = main_module.get_db_connection
    update_user_stats_async = main_module.update_user_stats_async
    await bot.add_cog(AdminSystem(bot, DATABASE_PATH, fiery_embed, save_game_config, get_user, get_db_connection, update_user_stats_async))
