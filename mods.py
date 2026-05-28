import discord
from discord.ext import commands
from datetime import datetime, timezone
import sys

class ModerationLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Core UI Colors matching the premium aesthetic
        self.color_added = 0x2DCE89   # Bright Green
        self.color_removed = 0xED4245 # Deep Red
        self.color_edited = 0xFEE75C  # Vivid Yellow
        self.color_deleted = 0xED4245 # Deep Red

    async def get_config(self, guild_id, key_name):
        """Fetches configuration values from the centralized database."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
            row = conn.execute("SELECT value FROM config WHERE key = ?", (f"{key_name}_{guild_id}",)).fetchone()
            if row:
                return row['value']
        return None

    # --- CONFIGURATION COMMANDS ---

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogroles(self, ctx, channel: discord.TextChannel):
        """Sets the channel for Role update logs."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"log_roles_{ctx.guild.id}", str(channel.id)))
            conn.commit()
        await ctx.send(f"✅ **Role logging** established. Output routed to {channel.mention}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogmessages(self, ctx, channel: discord.TextChannel):
        """Sets the global channel for deleted and edited messages."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"log_messages_{ctx.guild.id}", str(channel.id)))
            conn.commit()
        await ctx.send(f"✅ **Global message logging** established. Output routed to {channel.mention}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogflash(self, ctx, target_channel: discord.TextChannel, log_channel: discord.TextChannel):
        """Sets up the isolated Flash protocol. (Which channel to watch -> Where to send logs)"""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"flash_target_{ctx.guild.id}", str(target_channel.id)))
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"log_flash_{ctx.guild.id}", str(log_channel.id)))
            conn.commit()
        await ctx.send(f"📸 **Flash Protocol** armed. Monitoring {target_channel.mention}, routing ghosts to {log_channel.mention}")

    # --- ROLE MONITORING PROTOCOL ---

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Detects and formats role additions and removals."""
        if before.roles == after.roles:
            return

        log_channel_id = await self.get_config(after.guild.id, "log_roles")
        if not log_channel_id:
            return
        log_channel = self.bot.get_channel(int(log_channel_id))
        if not log_channel:
            return

        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)

        for role in added_roles:
            embed = discord.Embed(color=self.color_added)
            embed.description = f"**{after.mention}**\n\n**Role added**\n{role.mention}"
            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text=f"User ID: {after.id} • {datetime.now(timezone.utc).strftime('%d de %b de %Y %H:%M')}")
            await log_channel.send(embed=embed)

        for role in removed_roles:
            embed = discord.Embed(color=self.color_removed)
            embed.description = f"**{after.mention}**\n\n**Role removed**\n{role.mention}"
            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text=f"User ID: {after.id} • {datetime.now(timezone.utc).strftime('%d de %b de %Y %H:%M')}")
            await log_channel.send(embed=embed)

    # --- MESSAGE MONITORING PROTOCOLS ---

    async def route_message_log(self, guild_id, origin_channel_id):
        """Determines if a message event should go to the Global Log or the isolated Flash Log."""
        flash_target_id = await self.get_config(guild_id, "flash_target")
        
        if flash_target_id and int(flash_target_id) == origin_channel_id:
            log_id = await self.get_config(guild_id, "log_flash")
            return self.bot.get_channel(int(log_id)) if log_id else None
        
        log_id = await self.get_config(guild_id, "log_messages")
        return self.bot.get_channel(int(log_id)) if log_id else None

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Captures deleted messages and media."""
        if message.author.bot:
            return

        log_channel = await self.route_message_log(message.guild.id, message.channel.id)
        if not log_channel:
            return

        embed = discord.Embed(color=self.color_deleted)
        embed.set_author(name=f"@{message.author.name}", icon_url=message.author.display_avatar.url)
        
        desc = f"Message deleted in {message.channel.mention}\n\n"
        if message.content:
            desc += f"**Content**\n{message.content[:2000]}\n"
        
        if message.attachments:
            desc += "\n**Attachments Caught:**\n"
            for att in message.attachments:
                desc += f"📎 [{att.filename}]({att.proxy_url})\n"

        embed.description = desc
        embed.set_footer(text=f"User ID: {message.author.id} • {datetime.now(timezone.utc).strftime('%H:%M')}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Captures edited messages, ignoring simple embed expansions."""
        if before.author.bot or before.content == after.content:
            return

        log_channel = await self.route_message_log(before.guild.id, before.channel.id)
        if not log_channel:
            return

        embed = discord.Embed(color=self.color_edited)
        embed.set_author(name=f"@{before.author.name}", icon_url=before.author.display_avatar.url)
        
        desc = f"[Reply]({after.jump_url}) edited in {before.channel.mention} - [Jump to message]({after.jump_url})\n\n"
        desc += f"**Old**\n{before.content[:1000]}\n\n"
        desc += f"**New**\n{after.content[:1000]}"
        
        embed.description = desc
        embed.set_footer(text=f"User ID: {before.author.id} • {datetime.now(timezone.utc).strftime('%H:%M')}")
        await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ModerationLog(bot))
    print("✅ LOG: Next-Gen Moderation & Flash Protocols ONLINE.")
