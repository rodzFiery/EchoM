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
from datetime import datetime, timezone

# Accessing shared logic
import main
import ignis

# Configuration for Automatic Mode
# This will be overridden by the saved config if it exists
AUTO_FIGHT_CHANNEL_ID = 123456789012345678 
LOBBY_DURATION = 1800 # 30 minutes in seconds

class AutoLobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.participants = []

    @discord.ui.button(label="Enter the Red Room ", style=discord.ButtonStyle.danger, emoji="🔞", custom_id="auto_ignis_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("You are already registered for the next cycle, pet.", ephemeral=True)
        
        self.participants.append(interaction.user.id)
        
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="🧙‍♂️ Registered Sinners", value=f"Total: `{len(self.participants)}` sinners ready to be broken.", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

class IgnisAuto(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Load the saved channel ID from main config if available
        import sys
        main_module = sys.modules['__main__']
        # CONNECTION: Link to main.py global configuration variable
        self.auto_channel_id = getattr(main_module, "AUTO_IGNIS_CHANNEL", AUTO_FIGHT_CHANNEL_ID)
        
        self.current_auto_lobby = None
        self.auto_loop.start() # Start the 30-minute cycle

    def cog_unload(self):
        self.auto_loop.cancel()

    @tasks.loop(seconds=LOBBY_DURATION)
    async def auto_loop(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.auto_channel_id)
        if not channel:
            print(f"AUTO_IGNIS: Channel {self.auto_channel_id} not found.")
            return

        # 1. Process the previous lobby if it exists
        if self.current_auto_lobby and len(self.current_auto_lobby.participants) >= 2:
            await channel.send("🔞 **TIME IS UP. THE DOORS LOCK AUTOMATICALLY...**")
            
            # Transfer logic to the IgnisEngine cog
            ignis_engine = self.bot.get_cog("IgnisEngine")
            if ignis_engine:
                # We fetch the edition from main
                import sys
                main_module = sys.modules['__main__']
                edition = getattr(main_module, "game_edition", 1)
                
                # Start the battle using the existing engine logic
                asyncio.create_task(ignis_engine.start_battle(
                    channel, 
                    self.current_auto_lobby.participants, 
                    edition
                ))
                
                # Increment edition in main
                if hasattr(main_module, "game_edition"):
                    main_module.game_edition += 1
                    main_module.save_game_config()
            else:
                await channel.send("❌ Error: IgnisEngine not found. System failure.")
        
        elif self.current_auto_lobby:
            await channel.send("🥀 **Insufficient tributes for the previous cycle. The void remains hungry.**")

        # 2. Start NEW lobby for the next 30 minutes
        self.current_auto_lobby = AutoLobbyView()
        
        embed = main.fiery_embed(
            "🤖 AUTOMATED RED ROOM CYCLE", 
            f"The gates are open for the next **30 minutes**.\n"
            f"Registration is mandatory for those seeking public discipline.",
            color=0x5865F2
        )
        
        image_path = "LobbyTopRight.jpg"
        embed.add_field(name="🧙‍♂️ Registered Sinners", value="Total: `0` souls ready to be broken.", inline=False)
        
        # UPDATED: Real-time footer calculation for 30m precision
        next_run = datetime.now().timestamp() + LOBBY_DURATION
        embed.set_footer(text=f"Next Execution: {datetime.fromtimestamp(next_run).strftime('%H:%M:%S')} (Strict 30m Cycle)")

        if os.path.exists(image_path):
            file = discord.File(image_path, filename="auto_lobby.jpg")
            embed.set_thumbnail(url="attachment://auto_lobby.jpg")
            await channel.send(file=file, embed=embed, view=self.current_auto_lobby)
        else:
            await channel.send(embed=embed, view=self.current_auto_lobby)

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
        
        embed = main.fiery_embed("Auto-Ignis Setup", 
            f"✅ **Automated Pit set to {ctx.channel.mention}.**\n\n"
            f"The Master has claimed this territory. Cycles will run every 30 minutes.\n"
            f"**First cycle starting now...**", color=0x00FF00)
        
        await ctx.send(embed=embed)
        
        # Restart the loop to trigger the first lobby immediately
        self.auto_loop.restart()

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

async def setup(bot):
    await bot.add_cog(IgnisAuto(bot))
