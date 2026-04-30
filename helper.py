import discord
from discord.ext import commands, tasks
import sys
import importlib
import os
import traceback
import asyncio
import json
from datetime import datetime, timedelta

class HelperSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "ping_limits.json"
        self.purge_file = "auto_purge_configs.json"
        # Storage for ping cooldowns: {role_id: cooldown_minutes}
        self.ping_cooldowns = self.load_persistent_limits()
        # Storage for auto-purge: {channel_id: minutes}
        self.purge_configs = self.load_purge_configs()
        # Storage for the last time a role was successfully pinged: {role_id: last_ping_datetime}
        self.last_ping_time = {}
        
        self.auto_purge_loop.start()

    def load_persistent_limits(self):
        """Loads limits from the JSON file on startup."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                    # Convert string keys from JSON back to integers
                    return {int(k): v for k, v in data.items()}
            except:
                return {}
        return {}

    def save_persistent_limits(self):
        """Saves current limits to the JSON file."""
        with open(self.data_file, "w") as f:
            json.dump(self.ping_cooldowns, f)

    def load_purge_configs(self):
        """Loads auto-purge configurations from JSON."""
        if os.path.exists(self.purge_file):
            try:
                with open(self.purge_file, "r") as f:
                    data = json.load(f)
                    return {int(k): v for k, v in data.items()}
            except:
                return {}
        return {}

    def save_purge_configs(self):
        """Saves auto-purge configurations to JSON."""
        with open(self.purge_file, "w") as f:
            json.dump(self.purge_configs, f)

    @tasks.loop(minutes=1)
    async def auto_purge_loop(self):
        """Background task to scrub channels based on set timers."""
        for channel_id, minutes in self.purge_configs.items():
            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue
            
            try:
                cutoff = datetime.now(timezone.utc if hasattr(datetime, 'now') else None) - timedelta(minutes=minutes)
                # Purge messages older than the specified minutes
                await channel.purge(before=cutoff, check=lambda m: not m.pinned)
            except Exception as e:
                print(f"⚠️ Auto-Purge Fail in {channel_id}: {e}")

    @auto_purge_loop.before_loop
    async def before_purge(self):
        await self.bot.wait_until_ready()

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

    @commands.command(name="autopurge")
    @commands.has_permissions(manage_channels=True)
    async def autopurge(self, ctx, time_setting: str = None):
        """Sets automatic message scrubbing for this channel. Options: 5m, 10m, 15m, 1h, 2h, off"""
        if not time_setting:
            return await ctx.send("❓ **Usage:** `!autopurge <5m/10m/15m/1h/2h/off>`")

        time_setting = time_setting.lower()
        
        if time_setting == "off":
            if ctx.channel.id in self.purge_configs:
                del self.purge_configs[ctx.channel.id]
                self.save_purge_configs()
                return await ctx.send("🧹 **AUTO-PURGE DISABLED** for this sector.")
            return await ctx.send("ℹ️ Auto-purge is not active here.")

        mapping = {
            "5m": 5, "10m": 10, "15m": 15,
            "1h": 60, "2h": 120
        }

        if time_setting not in mapping:
            return await ctx.send("❌ **Invalid Timer.** Choose: 5m, 10m, 15m, 1h, 2h, or off.")

        minutes = mapping[time_setting]
        self.purge_configs[ctx.channel.id] = minutes
        self.save_purge_configs()

        embed = discord.Embed(
            title="🧹 AUTO-PURGE ACTIVATED",
            description=f"This channel is now under a scrubbing protocol.\nAll messages older than **{time_setting}** will be automatically deleted.",
            color=0x3498DB
        )
        embed.set_footer(text="Pinned messages are safe from the scrub.")
        await ctx.send(embed=embed)

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
        self.save_persistent_limits()
        
        try:
            # Force the role to be unmentionable by default
            await role.edit(mentionable=False)
            await ctx.send(f"🛡️ **COOLDOWN SECURED:** {role.mention} is now locked. Pings only allowed every `{minutes}`m. (Saved Forever)")
        except:
            await ctx.send("⚠️ **Note:** Limit set and saved, but I couldn't change the role permissions.")

    @commands.command(name="unlimit")
    @commands.has_permissions(manage_guild=True)
    async def unlimit(self, ctx, role: discord.Role):
        """Removes the ping cooldown."""
        if role.id in self.ping_cooldowns:
            # Logic stays line by line as requested
            del self.ping_cooldowns[role.id]
            self.save_persistent_limits()
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
