import discord
from discord.ext import commands
import sys
import os
import json

class AutoThread(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Local set of channel IDs where auto-thread is active
        self.active_channels = set()
        self.load_threads_config()

    def load_threads_config(self):
        """Load the list of active thread channels from the database config table."""
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                row = conn.execute("SELECT value FROM config WHERE key = 'auto_thread_channels'").fetchone()
                if row and row['value']:
                    ids = json.loads(row['value'])
                    self.active_channels = set(ids)
        except Exception as e:
            print(f"Error loading thread config: {e}")

    def save_threads_config(self):
        """Save the list of active thread channels to the database."""
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                             ('auto_thread_channels', json.dumps(list(self.active_channels))))
                conn.commit()
        except Exception as e:
            print(f"Error saving thread config: {e}")

    @commands.command(name="thread")
    @commands.has_permissions(administrator=True)
    async def toggle_thread(self, ctx, channel: discord.TextChannel = None):
        """Admin command to enable auto-threading on a specific channel."""
        target_channel = channel or ctx.channel
        main_mod = sys.modules['__main__']

        if target_channel.id in self.active_channels:
            embed = main_mod.fiery_embed("🧵 THREAD PROTOCOL", f"Auto-Thread is already **ACTIVE** for {target_channel.mention}. Use `!threadoff` to disable it.", color=0xFFFF00)
            return await ctx.send(embed=embed)
        
        self.active_channels.add(target_channel.id)
        action = "ENABLED"
        color = 0x00FF00

        self.save_threads_config()
        
        # This only sends a message to the Admin who typed the command, not the audit channel
        embed = main_mod.fiery_embed("🧵 THREAD PROTOCOL UPDATED", 
                                    f"Auto-Thread functionality has been **{action}** for {target_channel.mention}.", 
                                    color=color)
        
        await ctx.send(embed=embed)

    @commands.command(name="threadoff")
    @commands.has_permissions(administrator=True)
    async def thread_off(self, ctx, channel: discord.TextChannel = None):
        """Admin command to disable auto-threading on a specific channel."""
        target_channel = channel or ctx.channel
        main_mod = sys.modules['__main__']

        if target_channel.id in self.active_channels:
            self.active_channels.remove(target_channel.id)
            self.save_threads_config()
            
            embed = main_mod.fiery_embed("🧵 THREAD PROTOCOL DEACTIVATED", 
                                        f"Auto-Thread functionality has been **DISABLED** for {target_channel.mention}.", 
                                        color=0xFF0000)
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=main_mod.fiery_embed("🧵 THREAD PROTOCOL", f"Auto-Thread was not active in {target_channel.mention}.", color=0xFF0000))

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listener that opens a thread every time a message is sent in an active channel. NO AUDIT LOGS."""
        if message.author.bot:
            return
        
        if message.channel.id in self.active_channels:
            try:
                # Use the first 50 characters of the message as the thread name
                thread_name = f"Session: {message.author.display_name}"
                
                # Automatically creates the thread without any external audit reports
                await message.create_thread(
                    name=thread_name,
                    auto_archive_duration=60 # Archives after 1 hour of inactivity
                )
            except Exception as e:
                # Still print errors to console for your debugging, but not to Discord
                print(f"Failed to create thread in {message.channel.name}: {e}")

async def setup(bot):
    await bot.add_cog(AutoThread(bot))
