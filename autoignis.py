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
from discord.ext import commands, tasks
import random
import asyncio
import io
import os
import json
import sqlite3
import sys
from PIL import Image, ImageDraw, ImageOps
from datetime import datetime, timezone, timedelta

# Accessing shared logic
import main
import ignis

# Configuration for Automatic Mode
# This will be overridden by the saved config if it exists
AUTO_FIGHT_CHANNEL_ID = 123456789012345678 
LOBBY_DURATION = 1800 # 30 minutes in seconds

class AutoLobbyView(discord.ui.View):
    def __init__(self):
        # FIX: Changed timeout to None so the lobby doesn't "fail" while waiting for players
        super().__init__(timeout=None)
        self.participants = []

    # ADDED: custom_id to make the interaction persistent across bot restarts
    @discord.ui.button(label="Enter the Red Room ", style=discord.ButtonStyle.danger, emoji="🔞", custom_id="auto_ignis_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("You are already registered for the next cycle, pet.", ephemeral=True)
        
        self.participants.append(interaction.user.id)
        
        embed = interaction.message.embeds[0]
        # VISUAL UPDATE: Enhanced Participant Counter
        # FIXED: Converted to triple quotes so layout changes cannot trigger a SyntaxError
        embed.set_field_at(
            0, 
            name="🧙‍♂️ REGISTERED SINNERS", 
            value=f"""```fix\nTOTAL: {len(self.participants)} SOULS\n
```\n*Ready to be broken in the Master's image.*""", 
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=self)

class IgnisAuto(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Load the saved channel ID from main config if available
        import sys
        main_module = sys.modules['__main__']
        
        # PERSISTENCE CHECK: Try to pull from Database via main module's config system
        # This prevents resets during deployment
        self.auto_channel_id = getattr(main_module, "AUTO_IGNIS_CHANNEL", AUTO_FIGHT_CHANNEL_ID)
        self.ping_role_id = getattr(main_module, "AUTO_IGNIS_ROLE", 0)
        self.auto_enabled = True # Default state
        
        # ADDED: Master Owner ID alignment for custom verification checks
        self.MASTER_OWNER_ID = 1482648173016252439
        
        # ADDED: Lock to prevent race conditions (multiple games)
        self._lock = asyncio.Lock()

        # Attempt to refresh from DB if main_module has a database connection helper
        try:
            with main_module.get_db_connection() as conn:
                res = conn.execute("SELECT value FROM config WHERE key = 'auto_ignis_channel'").fetchone()
                if res: self.auto_channel_id = int(res[0])
                res_role = conn.execute("SELECT value FROM config WHERE key = 'auto_ignis_role'").fetchone()
                if res_role: self.ping_role_id = int(res_role[0])
                # PERSISTENT STOP CHECK
                res_enabled = conn.execute("SELECT value FROM config WHERE key = 'auto_ignis_enabled'").fetchone()
                if res_enabled: self.auto_enabled = (res_enabled[0] == 'True')
        except: pass

        self.current_auto_lobby = None
        self.last_processed_window = None 
        
        if self.auto_enabled:
            self.auto_loop.start() # Start the 30-minute cycle

    def cog_unload(self):
        self.auto_loop.cancel()

    # ADDED: Custom internal check to verify owner status manually
    async def is_server_or_bot_owner(self, ctx):
        if ctx.author.id == self.MASTER_OWNER_ID:
            return True
        if ctx.author.id == ctx.guild.owner_id:
            return True
        return await self.bot.is_owner(ctx.author)

    @tasks.loop(seconds=5) # RUN CONCURRENT VERIFICATIONS AT SHORT FREQUENCY FOR THREADLOCKING
    async def auto_loop(self):
        await self.bot.wait_until_ready()
        
        # APPLY LOCK: Only one execution of this block can happen at once
        async with self._lock:
            # CHECK EXCLUSION STATE AT RUNTIME TO PREVENT DUPLICATE THREAD OVERLAPS
            if self.last_processed_window == "running_cycle":
                return

            # FIXED: Added check to prevent 404 NotFound errors on deployment
            if not self.auto_channel_id or self.auto_channel_id == 123456789012345678:
                return

            channel = self.bot.get_channel(self.auto_channel_id)
            if not channel:
                return

            # ENGAGE STATE LOCK INSIDE RUNTIME OBJECTS
            self.last_processed_window = "running_cycle"

            # 2. Start NEW lobby for the next 30 minutes
            self.current_auto_lobby = AutoLobbyView()
            
            lobby_desc = """🔞 **The scent of worn leather and cold iron fills the air.**\n\nBy entering, you submit your soul to the Master's algorithms for the next 30 minutes."""

            embed = main.fiery_embed(
                "🔞 AUTOMATED RED ROOM CYCLE", 
                lobby_desc,
                color=0x5865F2
            )
            
            image_path = "LobbyTopRight.jpg"
            embed.add_field(name="🧙‍♂️ REGISTERED SINNERS", value="""```fix\nTOTAL: 0 SOULS\n```\n*Awaiting the harvest...*""", inline=False)
            
            embed.add_field(
                name="⛓️ Dungeon Protocol",
                value="""• **The Execution:** Once the timer hits zero, the session begins automatically.\n""",
                inline=False
            )
            
            now = datetime.now()
            next_run_time = now + timedelta(seconds=LOBBY_DURATION)

            embed.set_footer(text=f"Registration Closes: {next_run_time.strftime('%H:%M:%S')} (Strict 30m Cycle)")

            content = None
            if self.ping_role_id != 0: 
                content = f"<@&{self.ping_role_id}>"

            if os.path.exists(image_path):
                file = discord.File(image_path, filename="auto_lobby.jpg")
                embed.set_thumbnail(url="attachment://auto_lobby.jpg")
                lobby_msg = await channel.send(content=content, file=file, embed=embed, view=self.current_auto_lobby)
            else:
                lobby_msg = await channel.send(content=content, embed=embed, view=self.current_auto_lobby)

            # SUSPEND RE-RUNS: Force the async processor to hold and collect sign-ups for exactly 30 minutes
            await asyncio.sleep(LOBBY_DURATION)

            # 1. Process the previous lobby if it exists (BEFORE updating window tracker)
            if self.current_auto_lobby:
                # Disable previous view buttons
                for item in self.current_auto_lobby.children:
                    item.disabled = True
                try:
                    await lobby_msg.edit(view=self.current_auto_lobby)
                except:
                    pass

                if len(self.current_auto_lobby.participants) >= 2:
                    ignis_engine = self.bot.get_cog("IgnisEngine")

                    if ignis_engine:
                        await channel.send("🔞 **TIME IS UP. THE DOORS LOCK AUTOMATICALLY...**")
                        
                        import sys
                        main_module = sys.modules['__main__']
                        edition = getattr(main_module, "game_edition", 1)
                        
                        battle_participants = list(self.current_auto_lobby.participants)
                        
                        # FIXED: Used direct keyword await syntax to hold loop execution threads completely until match tasks conclude
                        await ignis_engine.start_battle(
                            channel, 
                            battle_participants, 
                            edition
                        )
                        
                        if hasattr(main_module, "game_edition"):
                            main_module.game_edition += 1
                            main_module.save_game_config()
                    else:
                        await channel.send("❌ Error: IgnisEngine not found. System failure.")
                else:
                    await channel.send("🔞 **Insufficient tributes for the previous cycle. The void remains hungry.**")

            # RE-ENABLE SEQUENTIAL LOOPS BY DROPPING DESIRED FLAGS AFTER COMPLETE ROUND EVALUATIONS
            self.last_processed_window = None

    @auto_loop.before_loop
    async def before_auto_loop(self):
        await self.bot.wait_until_ready()

    @commands.command(name="setauto")
    async def set_auto_channel(self, ctx):
        """Sets the current channel as the Automated Ignis Pit and saves it."""
        # FIXED: Removed is_owner decorator and applied fluid checking to allow both server and bot owners
        if not await self.is_server_or_bot_owner(ctx):
            return await ctx.send("❌ **Access Denied:** This protocol is locked to the Server Owner or Bot Architect.")

        import sys
        main_module = sys.modules['__main__']
        
        self.auto_channel_id = ctx.channel.id
        self.auto_enabled = True
        main_module.AUTO_IGNIS_CHANNEL = ctx.channel.id
        main_module.save_game_config()
        
        try:
            with main_module.get_db_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('auto_ignis_channel', ?)", (str(ctx.channel.id),))
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('auto_ignis_enabled', 'True')")
                conn.commit()
        except: pass
        
        self.last_processed_window = None
        self.current_auto_lobby = None

        # FIXED: Converted to triple quotes here as well to make it structurally bulletproof
        embed = main.fiery_embed(
            "🔞 AUTOMATED RED ROOM: INITIALIZED", 
            """🥀 **Automated Pit set and synchronized.**\n\nThe Master has claimed this territory. Registration is now open for the first cycle.\nThis lobby will close at the next 30-minute mark.""", 
            color=0x00FF00
        )
        
        await ctx.send(embed=embed)
        
        if not self.auto_loop.is_running():
            self.auto_loop.start()
        else:
            self.auto_loop.restart()

    @commands.command(name="autoignis")
    async def set_auto_ping_role(self, ctx, role: discord.Role):
        """Sets the role to be pinged every hour at .00."""
        # FIXED: Removed is_owner decorator and applied fluid checking to allow both server and bot owners
        if not await self.is_server_or_bot_owner(ctx):
            return await ctx.send("❌ **Access Denied:** This protocol is locked to the Server Owner or Bot Architect.")

        import sys
        main_module = sys.modules['__main__']
        self.ping_role_id = role.id
        main_module.AUTO_IGNIS_ROLE = role.id
        main_module.save_game_config()
        try:
            with main_module.get_db_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('auto_ignis_role', ?)", (str(role.id),))
                conn.commit()
        except: pass
        embed = main.fiery_embed("Auto-Ignis Ping Config", f"""🔔 **Lobby pings enabled.**\n\nThe role {role.mention} will now be summoned every hour at `:00` to face the Red Room.""", color=0x00FF00)
        await ctx.send(embed=embed)

    @commands.command(name="stopautoignis")
    async def stop_auto_ignis(self, ctx):
        """Stops the Automated Ignis cycle immediately."""
        # FIXED: Removed is_owner decorator and applied fluid checking to allow both server and bot owners
        if not await self.is_server_or_bot_owner(ctx):
            return await ctx.send("❌ **Access Denied:** This protocol is locked to the Server Owner or Bot Architect.")

        import sys
        main_module = sys.modules['__main__']
        
        self.auto_loop.cancel()
        self.auto_enabled = False
        self.current_auto_lobby = None
        self.last_processed_window = None
        
        try:
            with main_module.get_db_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('auto_ignis_enabled', 'False')")
                conn.commit()
        except: pass

        embed = main.fiery_embed("Auto-Ignis Terminated", """🛑 **The Automated Cycle has been halted.**\n\nThe gears have stopped turning and the registration ledger is cleared. The Master has revoked the automated protocol.""", color=0xFF0000)
        await ctx.send(embed=embed)

    @commands.command(name="autolobby")
    async def autolobby_status(self, ctx):
        """Checks the current souls registered for the Automated Cycle."""
        if not self.current_auto_lobby:
            embed = main.fiery_embed("Automated Lobby", """No active cycle is currently gathering souls.""")
            return await ctx.send(embed=embed)
        participants = self.current_auto_lobby.participants
        if not participants:
            embed = main.fiery_embed("Automated Lobby", """The automated room is currently empty.""")
            return await ctx.send(embed=embed)
        mentions = [f"<@{p_id}>" for p_id in participants]
        embed = main.fiery_embed("Upcoming Souls", f"""Queued for next automated execution:\n\n""" + "\n".join(mentions), color=0x5865F2)
        image_path = "LobbyTopRight.jpg"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="lobby.jpg")
            embed.set_thumbnail(url="attachment://lobby.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(IgnisAuto(bot))
