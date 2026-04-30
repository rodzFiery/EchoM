import discord
from discord.ext import commands
import sys
import importlib
import os
import traceback
import asyncio
from datetime import datetime, timedelta

class HelperSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Storage for ping cooldowns: {role_id: cooldown_minutes}
        self.ping_cooldowns = {}
        # Storage for the last time a role was successfully pinged: {role_id: last_ping_datetime}
        self.last_ping_time = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        """Enforcement listener: Handles pings without deleting messages."""
        if message.author.bot:
            return

        # Check if the message contains any role mentions (even if not pinging yet)
        # We use content check because if the role is unmentionable, 
        # message.role_mentions might be empty.
        for role_id, cooldown_mins in self.ping_cooldowns.items():
            role_tag = f"<@&{role_id}>"
            
            if role_tag in message.content:
                role = message.guild.get_role(role_id)
                if not role:
                    continue

                last_ping = self.last_ping_time.get(role_id)
                allowed = False

                if last_ping is None:
                    allowed = True
                else:
                    elapsed = datetime.now() - last_ping
                    if elapsed >= timedelta(minutes=cooldown_mins):
                        allowed = True

                if allowed:
                    # THE FLASH PING PROTOCOL
                    try:
                        # 1. Make role mentionable
                        await role.edit(mentionable=True)
                        
                        # 2. Send a temporary "Flash" message to trigger the notification
                        # This ensures the ping actually 'hits' the members
                        flash = await message.channel.send(f"🔔 **{role.name} Notification Requested**")
                        
                        # 3. Update the timer
                        self.last_ping_time[role_id] = datetime.now()
                        
                        # 4. Wait a split second and lock it back
                        await asyncio.sleep(1)
                        await role.edit(mentionable=False)
                        await flash.delete()
                        
                    except discord.Forbidden:
                        await message.channel.send("❌ **System Error:** I need 'Manage Roles' to toggle ping status.")
                else:
                    # NOT ALLOWED: We do nothing. 
                    # The message stays, but since the role is unmentionable, 
                    # it appears as text and pings NO ONE.
                    remaining = timedelta(minutes=cooldown_mins) - (datetime.now() - last_ping)
                    mins, secs = divmod(int(remaining.total_seconds()), 60)
                    
                    await message.channel.send(
                        f"⏳ {message.author.mention}, {role.name} is on cooldown. "
                        f"Message sent without notification. Wait `{mins}m {secs}s` for a full ping.",
                        delete_after=7
                    )

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

    @commands.command(name="limit")
    @commands.has_permissions(manage_guild=True)
    async def limit(self, ctx, role: discord.Role, minutes: int):
        """Sets a cooldown timer and forces role to be unmentionable."""
        if minutes < 0:
            return await ctx.send("❌ **Neural error:** Timer cannot be negative.")
        
        self.ping_cooldowns[role.id] = minutes
        
        try:
            # Force the role to be unmentionable by default
            await role.edit(mentionable=False)
            await ctx.send(f"🛡️ **COOLDOWN SECURED:** {role.mention} is now locked. Pings only allowed every `{minutes}`m.")
        except:
            await ctx.send("⚠️ **Note:** Limit set, but I couldn't change the role permissions. Check my role hierarchy.")

    @commands.command(name="unlimit")
    @commands.has_permissions(manage_guild=True)
    async def unlimit(self, ctx, role: discord.Role):
        """Removes the ping cooldown."""
        if role.id in self.ping_cooldowns:
            del self.ping_cooldowns[role.id]
            if role.id in self.last_ping_time:
                del self.last_ping_time[role.id]
            await ctx.send(f"🔓 **COOLDOWN DEACTIVATED:** {role.mention} restored to normal.")
        else:
            await ctx.send(f"ℹ️ **Notice:** No active timer found for {role.mention}.")

    @commands.command(name="checklimits")
    async def checklimits(self, ctx):
        """Displays all active role ping timers."""
        if not self.ping_cooldowns:
            return await ctx.send("📡 **No active timers found in the neural net.**")
        
        lines = []
        for r_id, mins in self.ping_cooldowns.items():
            role = ctx.guild.get_role(r_id)
            role_name = role.name if role else f"Unknown ID: {r_id}"
            lines.append(f"• **{role_name}**: `{mins}m` interval")
        
        await ctx.send("**CURRENT PING CONSTRAINTS:**\n" + "\n".join(lines))

async def setup(bot):
    await bot.add_cog(HelperSystem(bot))
