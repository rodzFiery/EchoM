# FIX: Python 3.13 compatibility shim for audioop
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
        import sys
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
import asyncio # ADDED: Required for the live telemetry loop
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
        
        # ADDED: Hardcoded Master Owner ID for the new account
        self.MASTER_OWNER_ID = 1482648173016252439
        
        # Local cache dict mapping server IDs to their specific admin roles
        self.guild_admin_roles = {}
        
        # Ensure dynamic system configuration schema properties are initialized safely
        with self.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")

    def load_guild_admin_role(self, guild_id):
        """Helper method to load a specific server's administrator role string from tables."""
        guild_key = str(guild_id)
        try:
            with self.get_db_connection() as conn:
                res = conn.execute("SELECT value FROM config WHERE key = ?", (f"admin_role_{guild_key}",)).fetchone()
                self.guild_admin_roles[guild_key] = int(res[0]) if res and res[0] else 0
        except:
            self.guild_admin_roles[guild_key] = 0

    # ADDED: Custom internal check to verify owner status manually
    async def is_master_owner(self, ctx):
        if ctx.author.id == self.MASTER_OWNER_ID:
            return True
        return await self.bot.is_owner(ctx.author)

    # ===== NEW: WAR ROOM TELEMETRY DASHBOARD =====
    @commands.command(aliases=["dashboard"])
    async def warroom(self, ctx):
        """Generates a live, auto-updating telemetry scorecard."""
        if not await self.is_master_owner(ctx):
            embed = self.fiery_embed("Access Denied", "❌ This telemetry panel is classified.")
            return await ctx.send(embed=embed)
            
        embed = self.fiery_embed("📡 WAR ROOM TELEMETRY", "Establishing secure link to mainframe...")
        msg = await ctx.send(embed=embed)
        
        async def update_dashboard():
            while True:
                try:
                    # 1. API Latency
                    latency = round(self.bot.latency * 1000)
                    
                    # 2. Database Size
                    try:
                        db_size = os.path.getsize(self.DATABASE_PATH)
                        db_size_mb = round(db_size / (1024 * 1024), 2)
                    except:
                        db_size_mb = "Unknown"
                        
                    # 3. Active Sessions Protocol
                    import sys
                    main_module = sys.modules.get('__main__')
                    nsfw_active = getattr(main_module, 'nsfw_mode_active', False)
                    basic_active = getattr(main_module, 'basic_nsfw_active', False)
                    session_status = "🔴 Full NSFW" if nsfw_active else "🟠 Basic NSFW" if basic_active else "🟢 Standard / Idle"
                    
                    # 4. Total Flames Circulation
                    try:
                        with self.get_db_connection() as conn:
                            res = conn.execute("SELECT SUM(flames) FROM users").fetchone()
                            total_flames = int(res[0]) if res and res[0] else 0
                    except:
                        total_flames = "Unknown"
                        
                    # Build live embed
                    live_embed = self.fiery_embed("📡 WAR ROOM: LIVE TELEMETRY", "System scorecard auto-updates every 30 seconds.")
                    live_embed.add_field(name="📶 API Latency", value=f"`{latency} ms`", inline=True)
                    live_embed.add_field(name="🗄️ Database Size", value=f"`{db_size_mb} MB`", inline=True)
                    live_embed.add_field(name="🔞 Current Protocol", value=f"**{session_status}**", inline=True)
                    live_embed.add_field(name="🔥 Total Flames in Circulation", value=f"**{total_flames:,}**" if isinstance(total_flames, int) else str(total_flames), inline=False)
                    live_embed.set_footer(text=f"Last Sync: {datetime.now().strftime('%H:%M:%S')} | Deleting this message interrupts signal.")
                    
                    await msg.edit(embed=live_embed)
                    await asyncio.sleep(30)
                except discord.NotFound:
                    # If the message is deleted, break the loop safely to save resources
                    break
                except Exception as e:
                    print(f"Dashboard Error: {e}")
                    await asyncio.sleep(30)
                    
        # Launch the live updating task in the background
        self.bot.loop.create_task(update_dashboard())

    # ===== UPDATED: SET ADMIN ROLE COMMAND (OWNER OR SERVER ADMIN) =====
    @commands.command()
    async def setadminrole(self, ctx, role: discord.Role):
        """Sets the global role that can bypass standard command restrictions."""
        # CHECK: Allow Bot Owner, Server Owner, or Server Administrator
        is_owner = await self.is_master_owner(ctx)
        is_server_owner = ctx.author.id == ctx.guild.owner_id
        is_server_admin = ctx.author.guild_permissions.administrator

        if not (is_owner or is_server_owner or is_server_admin):
            return await ctx.send("❌ **Access Denied:** You must be the Bot Owner, Server Owner, or an Administrator to define the Master Role.")

        guild_key = str(ctx.guild.id)
        self.guild_admin_roles[guild_key] = role.id
        
        # Persist to database config table using a unique server-isolated identifier key
        with self.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"admin_role_{guild_key}", str(role.id)))
            conn.commit()
            
        embed = self.fiery_embed("Security Protocol Updated", f"✅ The role {role.mention} has been granted **Master Access** to administrative commands on this server.")
        await ctx.send(embed=embed)

    # ===== NSFW Special Commands =====
    @commands.command()
    async def nsfwtime(self, ctx):
        # UPDATED: Added Guild Isolation and Role Check
        is_owner = await self.is_master_owner(ctx)
        guild_key = str(ctx.guild.id)
        self.load_guild_admin_role(ctx.guild.id)
        target_role_id = self.guild_admin_roles.get(guild_key, 0)
        has_admin_role = any(role.id == target_role_id for role in ctx.author.roles) if target_role_id != 0 else False
        
        if not (is_owner or ctx.author.id == ctx.guild.owner_id or has_admin_role):
            return await ctx.send("❌ Access Denied: Requires Owner or Admin Role.")

        # FIXED: Removed 'import main' to prevent circular import crash
        import sys
        main_module = sys.modules['__main__']
        main_module.nsfw_mode_active = True
        # NEW: Ensure basic nsfw is off when full nsfw is on
        main_module.basic_nsfw_active = False
        self.save_game_config()
        ext = self.bot.get_cog("FieryExtensions")
        if ext: await ext.trigger_nsfw_start(ctx)

    @commands.command()
    async def nomorensfw(self, ctx):
        # UPDATED: Added Guild Isolation and Role Check
        is_owner = await self.is_master_owner(ctx)
        guild_key = str(ctx.guild.id)
        self.load_guild_admin_role(ctx.guild.id)
        target_role_id = self.guild_admin_roles.get(guild_key, 0)
        has_admin_role = any(role.id == target_role_id for role in ctx.author.roles) if target_role_id != 0 else False
        
        if not (is_owner or ctx.author.id == ctx.guild.owner_id or has_admin_role):
            return await ctx.send("❌ Access Denied: Requires Owner or Admin Role.")

        # FIXED: Removed 'import main' to prevent circular import crash
        import sys
        main_module = sys.modules['__main__']
        main_module.nsfw_mode_active = False
        self.save_game_config()
        embed = self.fiery_embed("NSFW Mode Ended", "The Echogames has closed. Returning to standard Red Room protocols.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)

    # ===== NEW: BASIC NSFW MODE COMMANDS =====
    @commands.command()
    async def basicnsfw(self, ctx):
        """Activates Basic NSFW: First death flashes, Winner picks one victim to flash."""
        is_owner = await self.is_master_owner(ctx)
        guild_key = str(ctx.guild.id)
        self.load_guild_admin_role(ctx.guild.id)
        target_role_id = self.guild_admin_roles.get(guild_key, 0)
        has_admin_role = any(role.id == target_role_id for role in ctx.author.roles) if target_role_id != 0 else False
        
        if not (is_owner or ctx.author.id == ctx.guild.owner_id or has_admin_role):
            return await ctx.send("❌ Access Denied: Requires Owner or Admin Role.")

        import sys
        main_module = sys.modules['__main__']
        main_module.basic_nsfw_active = True
        # Ensure full nsfw is off
        main_module.nsfw_mode_active = False
        self.save_game_config()
        
        embed = self.fiery_embed("Basic NSFW Mode Active", "🔞 **Protocol: Limited Exposure.**\n- First death will automatically flash.\n- The Winner will be granted ONE flash decree.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)

    @commands.command()
    async def nomorebasic(self, ctx):
        """Deactivates Basic NSFW mode."""
        is_owner = await self.is_master_owner(ctx)
        guild_key = str(ctx.guild.id)
        self.load_guild_admin_role(ctx.guild.id)
        target_role_id = self.guild_admin_roles.get(guild_key, 0)
        has_admin_role = any(role.id == target_role_id for role in ctx.author.roles) if target_role_id != 0 else False
        
        if not (is_owner or ctx.author.id == ctx.guild.owner_id or has_admin_role):
            return await ctx.send("❌ Access Denied: Requires Owner or Admin Role.")

        import sys
        main_module = sys.modules['__main__']
        main_module.basic_nsfw_active = False
        self.save_game_config()
        
        embed = self.fiery_embed("Basic NSFW Mode Ended", "Standard Red Room protocols reinstated.")
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)

    @commands.command()
    async def grantbadge(self, ctx, member: discord.Member, badge: str):
        # UPDATED: Added Guild Isolation and Role Check
        is_owner = await self.is_master_owner(ctx)
        guild_key = str(ctx.guild.id)
        self.load_guild_admin_role(ctx.guild.id)
        target_role_id = self.guild_admin_roles.get(guild_key, 0)
        has_admin_role = any(role.id == target_role_id for role in ctx.author.roles) if target_role_id != 0 else False
        
        if not (is_owner or ctx.author.id == ctx.guild.owner_id or has_admin_role):
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

    # ===== UPDATED: FLAMES COMMAND (OWNER ONLY) =====
    @commands.command()
    async def flames(self, ctx, member: discord.Member, amount: int):
        """Master command to grant flames to a user (Bot Owner only)."""
        is_owner = await self.is_master_owner(ctx)

        if not is_owner:
            embed = self.fiery_embed("Access Denied", "❌ Only the Bot Owner holds the keys to the furnace.")
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
    async def backup(self, ctx):
        # UPDATED: Changed from @commands.is_owner() decorator to manual master check
        if not await self.is_master_owner(ctx):
            embed = self.fiery_embed("Access Denied", "❌ This command is reserved for the Bot Owner.")
            return await ctx.send(embed=embed)
            
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
    async def reload(self, ctx, cog_name: str):
        # UPDATED: Changed from @commands.is_owner() decorator to manual master check
        if not await self.is_master_owner(ctx):
            embed = self.fiery_embed("Access Denied", "❌ This command is reserved for the Bot Owner.")
            return await ctx.send(embed=embed)
            
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
