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
        # ADDED: Set of channel IDs where ALL messages (including text) are threaded
        self.thread_all_channels = set()
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
                
                # ADDED: Load thread_all config
                row_all = conn.execute("SELECT value FROM config WHERE key = 'thread_all_channels'").fetchone()
                if row_all and row_all['value']:
                    ids_all = json.loads(row_all['value'])
                    self.thread_all_channels = set(ids_all)
        except Exception as e:
            print(f"Error loading thread config: {e}")

    def save_threads_config(self):
        """Save the list of active thread channels to the database."""
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                             ('auto_thread_channels', json.dumps(list(self.active_channels))))
                # ADDED: Save thread_all config
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                             ('thread_all_channels', json.dumps(list(self.thread_all_channels))))
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
        # Ensure it's removed from thread_all if being set to standard media-only
        if target_channel.id in self.thread_all_channels:
            self.thread_all_channels.remove(target_channel.id)

        action = "ENABLED"
        color = 0x00FF00

        self.save_threads_config()
        
        # This only sends a message to the Admin who typed the command, not the audit channel
        embed = main_mod.fiery_embed("🧵 THREAD PROTOCOL UPDATED", 
                                    f"Auto-Thread functionality has been **{action}** for {target_channel.mention}.", 
                                    color=color)
        
        await ctx.send(embed=embed)

    # ADDED: Command to thread EVERYTHING (Text + Media)
    @commands.command(name="threadall")
    @commands.has_permissions(administrator=True)
    async def toggle_thread_all(self, ctx, channel: discord.TextChannel = None):
        """Admin command to enable auto-threading for ALL messages on a specific channel."""
        target_channel = channel or ctx.channel
        main_mod = sys.modules['__main__']

        if target_channel.id in self.thread_all_channels:
            embed = main_mod.fiery_embed("🧵 THREAD ALL PROTOCOL", f"Thread-All is already **ACTIVE** for {target_channel.mention}.", color=0xFFFF00)
            return await ctx.send(embed=embed)

        self.thread_all_channels.add(target_channel.id)
        # Ensure it's removed from standard if being set to thread_all
        if target_channel.id in self.active_channels:
            self.active_channels.remove(target_channel.id)

        self.save_threads_config()

        embed = main_mod.fiery_embed("🧵 THREAD ALL PROTOCOL ENABLED", 
                                    f"All messages (Text & Media) will now be threaded in {target_channel.mention}.", 
                                    color=0x00FFFF)
        await ctx.send(embed=embed)

    @commands.command(name="threadoff")
    @commands.has_permissions(administrator=True)
    async def thread_off(self, ctx, channel: discord.TextChannel = None):
        """Admin command to disable auto-threading on a specific channel."""
        target_channel = channel or ctx.channel
        main_mod = sys.modules['__main__']

        # Check both sets
        removed = False
        if target_channel.id in self.active_channels:
            self.active_channels.remove(target_channel.id)
            removed = True
        if target_channel.id in self.thread_all_channels:
            self.thread_all_channels.remove(target_channel.id)
            removed = True

        if removed:
            self.save_threads_config()
            
            embed = main_mod.fiery_embed("🧵 THREAD PROTOCOL DEACTIVATED", 
                                        f"Auto-Thread functionality has been **DISABLED** for {target_channel.mention}.", 
                                        color=0xFF0000)
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=main_mod.fiery_embed("🧵 THREAD PROTOCOL", f"Auto-Thread was not active in {target_channel.mention}.", color=0xFF0000))

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listener that opens a thread ONLY when an image or video is sent in an active channel."""
        if message.author.bot:
            return
        
        is_standard = message.channel.id in self.active_channels
        is_thread_all = message.channel.id in self.thread_all_channels

        if is_standard or is_thread_all:
            # Check for media if in standard mode
            is_media = any(
                (att.content_type and (att.content_type.startswith('image/') or att.content_type.startswith('video/'))) 
                or att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.mov', '.mkv', '.webm'))
                for att in message.attachments
            )

            # Trigger condition: (Standard + Media) OR (ThreadAll)
            should_thread = (is_standard and is_media) or is_thread_all

            if not should_thread:
                return

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
