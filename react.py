import discord
from discord.ext import commands
import sys
import os
import json

class AutoReact(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Local cache: {channel_id: [emoji_id_or_str, ...]}
        self.react_channels = {}
        self.load_config()

    def load_config(self):
        """Load the auto-react configuration from the database."""
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                row = conn.execute("SELECT value FROM config WHERE key = 'auto_react_config'").fetchone()
                if row and row['value']:
                    # Data stored as {channel_id_string: [emoji_list]}
                    self.react_channels = json.loads(row['value'])
        except Exception as e:
            print(f"Error loading react config: {e}")

    def save_config(self):
        """Save the auto-react configuration to the database."""
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                             ('auto_react_config', json.dumps(self.react_channels)))
                conn.commit()
        except Exception as e:
            print(f"Error saving react config: {e}")

    @commands.command(name="react")
    @commands.has_permissions(administrator=True)
    async def add_react(self, ctx, channel: discord.TextChannel, emoji: str):
        """Admin command to bind an emoji to a channel for auto-reactions on media."""
        main_mod = sys.modules['__main__']
        channel_id = str(channel.id)

        if channel_id not in self.react_channels:
            self.react_channels[channel_id] = []

        if emoji in self.react_channels[channel_id]:
            embed = main_mod.fiery_embed("💢 REACTION PROTOCOL", f"The emoji {emoji} is already bound to {channel.mention}.", color=0xFFFF00)
            return await ctx.send(embed=embed)

        self.react_channels[channel_id].append(emoji)
        self.save_config()

        embed = main_mod.fiery_embed("✅ REACTION PROTOCOL SEALED", 
                                    f"The bot will now auto-react with {emoji} to all media in {channel.mention}.", 
                                    color=0x00FF00)
        await ctx.send(embed=embed)

    @commands.command(name="reactoff")
    @commands.has_permissions(administrator=True)
    async def react_off(self, ctx, channel: discord.TextChannel = None):
        """Admin command to clear all auto-reactions from a channel."""
        main_mod = sys.modules['__main__']
        target_channel = channel or ctx.channel
        channel_id = str(target_channel.id)

        if channel_id in self.react_channels:
            del self.react_channels[channel_id]
            self.save_config()
            embed = main_mod.fiery_embed("🚫 REACTION PROTOCOL PURGED", f"Auto-reactions have been **DISABLED** for {target_channel.mention}.", color=0xFF0000)
        else:
            embed = main_mod.fiery_embed("💢 REACTION PROTOCOL", f"No active reaction protocols found for {target_channel.mention}.", color=0xFFFF00)
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Detects attachments and applies the bound reactions."""
        if message.author.bot:
            return

        channel_id = str(message.channel.id)
        if channel_id in self.react_channels:
            # Check if the message contains an image/video or a link to one
            has_attachment = len(message.attachments) > 0
            has_embed = len(message.embeds) > 0 # Covers some external links that generate image embeds
            
            if has_attachment or has_embed:
                for emoji in self.react_channels[channel_id]:
                    try:
                        # Try to resolve if it's a custom emoji ID or a standard emoji
                        if emoji.isdigit():
                            resolved_emoji = self.bot.get_emoji(int(emoji))
                            if resolved_emoji:
                                await message.add_reaction(resolved_emoji)
                        else:
                            await message.add_reaction(emoji)
                    except Exception as e:
                        print(f"Failed to add reaction {emoji} in {message.channel.id}: {e}")

async def setup(bot):
    await bot.add_cog(AutoReact(bot))
