import discord
from discord.ext import commands
import sys
import importlib
import os
import traceback
import asyncio

class HelperSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Added storage for ping limits: {role_id: limit_count}
        self.ping_limits = {}

    @commands.command(name="echopurge")
    @commands.has_permissions(manage_messages=True)
    async def echopurge(self, ctx, amount: int):
        """Deletes a specified number of messages from the channel."""
        if amount < 1:
            return await ctx.send("❌ **Neural error:** Minimum purge value is 1.", delete_after=5)
        
        if amount > 100:
            amount = 100

        deleted = await ctx.channel.purge(limit=amount + 1)
        
        confirm = await ctx.send(f"扫 **ECHO PURGE COMPLETE:** `{len(deleted)-1}` messages scrubbed from history.")
        await asyncio.sleep(5)
        try:
            await confirm.delete()
        except:
            pass

    @commands.command(name="refresh")
    @commands.is_owner()
    async def refresh(self, ctx):
        """Hot-reloads all extensions and synchronizes the database link."""
        msg = await ctx.send("🔄 **RECALIBRATING NEURAL NET...**")
        
        try:
            local_modules = ['utilis', 'database', 'prizes', 'worknranks', 'daily', 'social']
            for mod in local_modules:
                if mod in sys.modules:
                    importlib.reload(sys.modules[mod])
            
            import database as db_module
            db_module.init_db() 
            
            extensions = [
                "admin", "classes", "extensions", "ship", "shop", "collect", 
                "fight", "casino", "ask", "premium", "audit", "thread", 
                "levels", "react", "counting", "guessnumber", "reactionrole", 
                "autoignis", "confession", "helper", "cards", "win", "emoji", "packs"
            ]

            reloaded = []
            failed = []

            for ext in extensions:
                try:
                    await self.bot.reload_extension(ext)
                    reloaded.append(f"✅ {ext}")
                except commands.ExtensionNotLoaded:
                    try:
                        await self.bot.load_extension(ext)
                        reloaded.append(f"✅ {ext}")
                    except Exception as e:
                        failed.append(f"❌ {ext} (Load Fail: {e})")
                except Exception as e:
                    failed.append(f"❌ {ext} (Reload Fail: {e})")

            from utilis import fiery_embed
            main_mod = sys.modules['__main__']
            nsfw = getattr(main_mod, 'nsfw_mode_active', False)
            
            status_report = "**Synchronized:**\n" + (", ".join(reloaded) if reloaded else "None")
            if failed:
                status_report += "\n\n**Failed Protocols:**\n" + "\n".join(failed)

            embed = fiery_embed(self.bot, nsfw, "⚙️ SYSTEM REFRESH COMPLETE", 
                                f"Neural links restored.\n\n{status_report}\n\n**Database:** Persistent & Online.", 
                                color=0x00FF00)
            
            await msg.edit(content=None, embed=embed)
            print(f"✅ LOG: Manual Refresh triggered by {ctx.author}. Database re-initialized.")

        except Exception as e:
            await msg.edit(content=f"❌ **SYSTEM RECOVERY FAILED:** `{e}`")

    @commands.command(name="debug_cmd")
    @commands.is_owner()
    async def debug_cmd(self, ctx, command_name: str):
        """DEBUGGER: Tests why a specific command (like flirt) might not be working."""
        cmd = self.bot.get_command(command_name)
        
        if not cmd:
            return await ctx.send(f"❌ **Command `{command_name}` not found in the neural net.** It might not be loaded.")
        
        cog_name = cmd.cog_name if cmd.cog_name else "Main Core"
        checks = cmd.checks
        
        report = [
            f"🔍 **DEBUG REPORT: `!{command_name}`**",
            f"• **Status:** Registered",
            f"• **Source Cog:** `{cog_name}`",
            f"• **Enabled:** {cmd.enabled}",
            f"• **Hidden:** {cmd.hidden}",
            f"• **Has Checks:** {len(checks) > 0}"
        ]
        
        await ctx.send("\n".join(report))

    # --- NEW ADDITIONS START HERE ---

    @commands.command(name="limitflash")
    @commands.has_permissions(manage_guild=True)
    async def limitflash(self, ctx, role: discord.Role, amount: int):
        """Sets a ping limit for a specific role. Use: !limitflash @role 15"""
        if amount < 0:
            return await ctx.send("❌ **Neural error:** Limit cannot be negative.")
        
        # Store the limit in the cog's dictionary
        self.ping_limits[role.id] = amount
        
        await ctx.send(f"⚡ **FLASH LIMIT SET:** Role {role.mention} is now capped at `{amount}` pings per cycle.")

    @commands.command(name="checklimits")
    async def checklimits(self, ctx):
        """Displays all active role ping limits."""
        if not self.ping_limits:
            return await ctx.send("📡 **No active ping limits found in the neural net.**")
        
        lines = []
        for r_id, amt in self.ping_limits.items():
            role = ctx.guild.get_role(r_id)
            role_name = role.mention if role else f"Unknown ID: {r_id}"
            lines.append(f"• {role_name}: `{amt}`")
        
        await ctx.send("**CURRENT PING CONSTRAINTS:**\n" + "\n".join(lines))

async def setup(bot):
    await bot.add_cog(HelperSystem(bot))
