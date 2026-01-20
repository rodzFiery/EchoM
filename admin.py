# FIX: Python 3.13 compatibility shim for audioop
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
        import sys
        sys.modules['audioop'] = audioop
    except ImportError:
        pass 

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
        
        # ADDED: Load Admin Role from persistence
        import sys
        import main_module = sys.modules['__main__']
        self.ADMIN_ROLE_ID = getattr(main_module, "ADMIN_ROLE_ID", 0)

    # ===== UPDATED: SET ADMIN ROLE COMMAND (OWNER OR SERVER ADMIN) =====
    @commands.command()
    async def setadminrole(self, ctx, role: discord.Role):
        """Sets the global role that can bypass standard command restrictions."""
        # CHECK: Allow Bot Owner OR Server Administrator
        is_owner = await self.bot.is_owner(ctx.author)
        is_server_admin = ctx.author.guild_permissions.administrator

        if not (is_owner or is_server_admin):
            return await ctx.send("❌ **Access Denied:** You must be the Bot Owner or a Server Administrator to define the Master Role.")

        import sys
        main_module = sys.modules['__main__']
        
        self.ADMIN_ROLE_ID = role.id
        main_module.ADMIN_ROLE_ID = role.id
        
        # Persist to database config table
        with self.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('admin_role_id', ?)", (str(role.id),))
            conn.commit()
            
        embed = self.fiery_embed("Security Protocol Updated", f"✅ The role {role.mention} has been granted **Master Access** to administrative commands.")
        await ctx.send(embed=embed)

    # ===== NSFW Special Commands =====
    @commands.command()
    async def nsfwtime(self, ctx):
        # UPDATED: Added Role Check
        is_owner = await self.bot.is_owner(ctx.author)
        has_admin_role = any(role.id == self.ADMIN_ROLE_ID for role in ctx.author.roles) if self.ADMIN_ROLE_ID != 0 else False
        
        if not (is_owner or has_admin_role):
            return await ctx.send("❌ Access Denied: Requires Owner or Admin Role.")

        # FIXED: Removed 'import main' to prevent circular import crash
        import sys
        main_module = sys.modules['__main__']
        main_module.nsfw_mode_active = True
        self.save_game_config()
        ext = self.bot.get_cog("FieryExtensions")
        if ext: await ext.trigger_nsfw_start(ctx)

    @commands.command()
    async def nomorensfw(self, ctx):
        # UPDATED: Added Role Check
        is_owner = await self.bot.is_owner(ctx.author)
        has_admin_role = any(role.id == self.ADMIN_ROLE_ID for role in ctx.author.roles) if self.ADMIN_ROLE_ID != 0 else False
        
        if not (is_owner or has_admin_role):
            return await ctx.send("❌ Access Denied: Requires Owner or Admin Role.")

        # FIXED: Removed 'import main' to prevent circular import crash
        import sys
        main_module = sys.modules['__main__']
        main_module.nsfw_mode_active = False
        self.save_game_config()
        embed = self.fiery_embed("NSFW Mode Ended", "The Echogames has closed. Returning to standard Red Room protocols.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)

    @commands.command()
    async def grantbadge(self, ctx, member: discord.Member, badge: str):
        # UPDATED: Added Role Check
        is_owner = await self.bot.is_owner(ctx.author)
        has_admin_role = any(role.id == self.ADMIN_ROLE_ID for role in ctx.author.roles) if self.ADMIN_ROLE_ID != 0 else False
        
        if not (is_owner or has_admin_role):
            return await ctx.send("❌ Access Denied.")

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

    # ===== UPDATED: FLAMES COMMAND (PERMISSIONS + ROLE BASED) =====
    @commands.command()
    async def flames(self, ctx, member: discord.Member, amount: int):
        """Master command to grant flames to a user based on Admin permissions or role."""
        is_owner = await self.bot.is_owner(ctx.author)
        is_admin = ctx.author.guild_permissions.administrator
        has_admin_role = any(role.id == self.ADMIN_ROLE_ID for role in ctx.author.roles) if self.ADMIN_ROLE_ID != 0 else False

        if not (is_owner or is_admin or has_admin_role):
            embed = self.fiery_embed("Access Denied", "❌ Only those with Administrative authority, the Admin Role, or the Bot Owner hold the keys to the furnace.")
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
                import sys
                main_module = sys.modules['__main__']
                RANKS = main_module.RANKS
                CLASSES = main_module.CLASSES
                AUDIT_CHANNEL_ID = main_module.AUDIT_CHANNEL_ID
                await self.bot.add_cog(ignis.IgnisEngine(self.bot, self.update_user_stats_async, self.get_user, self.fiery_embed, self.get_db_connection, RANKS, CLASSES, AUDIT_CHANNEL_ID))
            elif cog_name.lower() in ["extensions", "ship", "shop", "collect", "fight", "casino", "ask", "autoignis"]:
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
