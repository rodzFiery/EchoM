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
        embed.set_field_at(0, name="🧙‍♂️ REGISTERED SINNERS", value=f"```fix\nTOTAL: {len(self.participants)} SOULS\n```\n*Ready to be broken in the Master's image.*", inline=False)
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
        
        # Attempt to refresh from DB if main_module has a database connection helper
        try:
            with main_module.get_db_connection() as conn:
                res = conn.execute("SELECT value FROM config WHERE key = 'auto_ignis_channel'").fetchone()
                if res: self.auto_channel_id = int(res[0])
                res_role = conn.execute("SELECT value FROM config WHERE key = 'auto_ignis_role'").fetchone()
                if res_role: self.ping_role_id = int(res_role[0])
        except: pass

        self.current_auto_lobby = None
        self.auto_loop.start() # Start the 30-minute cycle

    def cog_unload(self):
        self.auto_loop.cancel()

    @tasks.loop(seconds=60) # Changed to 60s check to ensure strict alignment
    async def auto_loop(self):
        await self.bot.wait_until_ready()
        
        # FIX: Strict 30-minute alignment logic (:00 and :30)
        now = datetime.now()
        if now.minute not in [0, 30]:
            return

        channel = self.bot.get_channel(self.auto_channel_id)
        if not channel:
            print(f"AUTO_IGNIS: Channel {self.auto_channel_id} not found.")
            return

        # 1. Process the previous lobby if it exists
        # CRITICAL FIX: Ensure the battle is dispatched BEFORE the lobby object is refreshed
        if self.current_auto_lobby:
            if len(self.current_auto_lobby.participants) >= 2:
                # TRANSFER CHECK: Only start if the manual engine isn't already busy in this channel
                ignis_engine = self.bot.get_cog("IgnisEngine")
                
                # NEW: WAIT PROTOCOL - If a game is still running, wait for it to end
                wait_count = 0
                while ignis_engine and channel.id in ignis_engine.active_battles:
                    if wait_count == 0:
                        await channel.send("⏳ **The previous massacre is still concluding.** New cycle is in queue...")
                    await asyncio.sleep(30) # Check every 30 seconds
                    wait_count += 1
                    if wait_count > 20: # Timeout after 10 mins of waiting
                         break

                if ignis_engine and channel.id not in ignis_engine.active_battles:
                    await channel.send("🔞 **TIME IS UP. THE DOORS LOCK AUTOMATICALLY...**")
                    
                    import sys
                    main_module = sys.modules['__main__']
                    edition = getattr(main_module, "game_edition", 1)
                    
                    # Capture the list to ensure no reference issues during lobby reset
                    battle_participants = list(self.current_auto_lobby.participants)
                    
                    asyncio.create_task(ignis_engine.start_battle(
                        channel, 
                        battle_participants, 
                        edition
                    ))
                    
                    # Increment edition in main
                    if hasattr(main_module, "game_edition"):
                        main_module.game_edition += 1
                        main_module.save_game_config()
                elif ignis_engine and channel.id in ignis_engine.active_battles:
                     await channel.send("⚠️ **Lobby Terminated:** The previous session took too long. Resetting for next cycle.")
                else:
                    await channel.send("❌ Error: IgnisEngine not found. System failure - call dev.rodz.")
            else:
                await channel.send("🔞 **Insufficient tributes for the previous cycle. The void remains hungry.**")

        # 2. Start NEW lobby for the next 30 minutes
        # Registering the View to ensure button persistence
        self.current_auto_lobby = AutoLobbyView()
        
        # ENHANCED INFORMATIVE CONTENT
        lobby_desc = (
            "🔞 **The scent of worn leather and cold iron fills the air.**\n\n"
            "By entering, you submit your soul to the Master's algorithms for the next 30 minutes."
        )

        embed = main.fiery_embed(
            "🔞 AUTOMATED RED ROOM CYCLE", 
            lobby_desc,
            color=0x5865F2
        )
        
        image_path = "LobbyTopRight.jpg"
        # VISUAL UPDATE: High visibility Soul Counter
        embed.add_field(name="🧙‍♂️ REGISTERED SINNERS", value="```fix\nTOTAL: 0 SOULS\n```\n*Awaiting the harvest...*", inline=False)
        
        # NEW INFORMATIVE CONCEPTS
        embed.add_field(
            name="⛓️ Dungeon Protocol",
            value=(
                "• **The Execution:** Once the timer hits zero, the session begins automatically.\n"
            ),
            inline=False
        )
        
        # UPDATED: Real-time footer calculation for 30m precision
        next_run_time = (now + timedelta(minutes=30)).replace(second=0, microsecond=0)
        embed.set_footer(text=f"Next Execution: {next_run_time.strftime('%H:%M:%S')} (Strict 30m Cycle)")

        # ADDED: HOURLY PING LOGIC (Every 1 hour at .00)
        content = None
        if now.minute == 0 and self.ping_role_id != 0:
            content = f"<@&{self.ping_role_id}>"

        if os.path.exists(image_path):
            file = discord.File(image_path, filename="auto_lobby.jpg")
            embed.set_thumbnail(url="attachment://auto_lobby.jpg")
            await channel.send(content=content, file=file, embed=embed, view=self.current_auto_lobby)
        else:
            await channel.send(content=content, embed=embed, view=self.current_auto_lobby)
            
        # Prevent the loop from firing multiple times in the same minute
        await asyncio.sleep(61)

    @auto_loop.before_loop
    async def before_auto_loop(self):
        await self.bot.wait_until_ready()

    @commands.command(name="setauto")
    @commands.is_owner()
    async def set_auto_channel(self, ctx):
        """Sets the current channel as the Automated Ignis Pit and saves it."""
        import sys
        main_module = sys.modules['__main__']
        
        # Update the local reference
        self.auto_channel_id = ctx.channel.id
        
        # CONNECTION: Persist the change in the main module's config
        main_module.AUTO_IGNIS_CHANNEL = ctx.channel.id
        main_module.save_game_config()
        
        # DATABASE PERSISTENCE: Ensure Railway redeploy doesn't reset this
        try:
            with main_module.get_db_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('auto_ignis_channel', ?)", (str(ctx.channel.id),))
                conn.commit()
        except: pass
        
        # --- ADDED: IMMEDIATE LOBBY TRIGGER FOR SETUP ---
        self.current_auto_lobby = AutoLobbyView()
        now = datetime.now()
        
        # Logic to determine next interval for the footer
        if now.minute < 30:
            next_m = 30
        else:
            next_m = 0
            now = now + timedelta(hours=1)
        
        next_run_time = now.replace(minute=next_m, second=0, microsecond=0)

        embed = main.fiery_embed("🔞 AUTOMATED RED ROOM: INITIALIZED", 
            "🥀 **Automated Pit set and synchronized.**\n\n"
            "The Master has claimed this territory. Registration is now open for the first cycle.\n"
            "This lobby will close at the next 30-minute mark.", color=0x00FF00)
        
        embed.add_field(name="🧙‍♂️ REGISTERED SINNERS", value="```fix\nTOTAL: 0 SOULS\n```", inline=False)
        embed.set_footer(text=f"Next Execution: {next_run_time.strftime('%H:%M:%S')} (Synchronization Active)")

        image_path = "LobbyTopRight.jpg"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="auto_lobby.jpg")
            embed.set_thumbnail(url="attachment://auto_lobby.jpg")
            await ctx.send(file=file, embed=embed, view=self.current_auto_lobby)
        else:
            await ctx.send(embed=embed, view=self.current_auto_lobby)
        
        # Restart the loop to keep the background check alive
        self.auto_loop.restart()

    @commands.command(name="autoignis")
    @commands.is_owner()
    async def set_auto_ping_role(self, ctx, role: discord.Role):
        """Sets the role to be pinged every hour at .00."""
        import sys
        main_module = sys.modules['__main__']
        
        self.ping_role_id = role.id
        
        # Persist to main config
        main_module.AUTO_IGNIS_ROLE = role.id
        main_module.save_game_config()

        # DATABASE PERSISTENCE: Ensure Railway redeploy doesn't reset this
        try:
            with main_module.get_db_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('auto_ignis_role', ?)", (str(role.id),))
                conn.commit()
        except: pass
        
        embed = main.fiery_embed("Auto-Ignis Ping Config",
            f"🔔 **Lobby pings enabled.**\n\n"
            f"The role {role.mention} will now be summoned every hour at `:00` to face the Red Room.", color=0x00FF00)
        await ctx.send(embed=embed)

    @commands.command(name="stopautoignis")
    @commands.is_owner()
    async def stop_auto_ignis(self, ctx):
        """Stops the Automated Ignis cycle immediately."""
        if self.auto_loop.is_running():
            self.auto_loop.stop()
            self.current_auto_lobby = None
            embed = main.fiery_embed("Auto-Ignis Terminated", 
                "🛑 **The Automated Cycle has been halted.**\n\n"
                "The gears have stopped turning and the registration ledger is cleared. "
                "The Master has revoked the automated protocol.", color=0xFF0000)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ **The Automated Cycle is not currently running.**", ephemeral=True)

    # ADDED: Specialized Lobby Command for Automated Sessions
    @commands.command(name="autolobby")
    async def autolobby_status(self, ctx):
        """Checks the current souls registered for the Automated Cycle."""
        if not self.current_auto_lobby:
            embed = main.fiery_embed("Automated Lobby", "No active cycle is currently gathering souls.")
            return await ctx.send(embed=embed)
        
        participants = self.current_auto_lobby.participants
        if not participants:
            embed = main.fiery_embed("Automated Lobby", "The automated room is currently empty. No souls have signed yet.")
            return await ctx.send(embed=embed)
        
        mentions = [f"<@{p_id}>" for p_id in participants]
        embed = main.fiery_embed("Upcoming Souls", f"The following sinners are queued for the next automated execution:\n\n" + "\n".join(mentions), color=0x5865F2)
        
        image_path = "LobbyTopRight.jpg"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="lobby.jpg")
            embed.set_thumbnail(url="attachment://lobby.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(IgnisAuto(bot))
