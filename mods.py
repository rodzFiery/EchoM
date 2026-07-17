import discord
from discord.ext import commands
from datetime import datetime, timezone
import sys
import io
import aiohttp

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
                # FIXED: Handles both tuple configurations and dict row_factories safely
                try:
                    return row['value']
                except:
                    return row[0]
        return None

    # --- CONFIGURATION COMMANDS ---

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogroles(self, ctx, channel: discord.TextChannel):
        """Sets the channel for Role update logs."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"log_roles_{ctx.guild.id}", str(channel.id)))
            conn.commit()
        await ctx.send(f"✅ **Role logging** established. Output routed to {channel.mention}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogmessages(self, ctx, channel: discord.TextChannel):
        """Sets the global channel for deleted and edited messages."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"log_messages_{ctx.guild.id}", str(channel.id)))
            conn.commit()
        await ctx.send(f"✅ **Global message logging** established. Output routed to {channel.mention}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogflash(self, ctx, target_channel: discord.TextChannel, log_channel: discord.TextChannel):
        """Sets up the isolated Flash protocol. (Which channel to watch -> Where to send logs)"""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"flash_target_{ctx.guild.id}", str(target_channel.id)))
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"log_flash_{ctx.guild.id}", str(log_channel.id)))
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"flash_route_{target_channel.id}_{ctx.guild.id}", str(log_channel.id)))
            conn.commit()
        await ctx.send(f"📸 **Flash Protocol** armed. Monitoring {target_channel.mention}, routing ghosts to {log_channel.mention}")

    # --- ROLE MONITORING PROTOCOL ---

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Detects and formats role additions and removals."""
        if before.roles == after.roles:
            return

        # SERVER LOCALIZATION GUARD: Prevent empty execution loops on broken caching layers
        if not getattr(after, 'guild', None):
            return

        log_channel_id = await self.get_config(after.guild.id, "log_roles")
        if not log_channel_id:
            return
            
        log_channel = self.bot.get_channel(int(log_channel_id))
        # --- FIXED: Active API fetch protocol implemented if target channel drops from shard cache ---
        if not log_channel:
            try:
                log_channel = await self.bot.fetch_channel(int(log_channel_id))
            except:
                return

        # CROSS-SERVER SECURITY ISOLATION CHECK
        if log_channel.guild.id != after.guild.id:
            return

        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)

        for role in added_roles:
            embed = discord.Embed(color=self.color_added)
            # ADDED: Explicit names alongside mentions to prevent raw ID numbers when cache drops
            embed.description = f"**{after.mention}** ({after.display_name})\n\n**Role added**\n{role.mention} ({role.name})"
            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text=f"User ID: {after.id} • {datetime.now(timezone.utc).strftime('%d de %b de %Y %H:%M')}")
            await log_channel.send(embed=embed)

        for role in removed_roles:
            embed = discord.Embed(color=self.color_removed)
            # ADDED: Explicit names alongside mentions to prevent raw ID numbers when cache drops
            embed.description = f"**{after.mention}** ({after.display_name})\n\n**Role removed**\n{role.mention} ({role.name})"
            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text=f"User ID: {after.id} • {datetime.now(timezone.utc).strftime('%d de %b de %Y %H:%M')}")
            await log_channel.send(embed=embed)

    # --- MESSAGE MONITORING PROTOCOLS ---

    async def route_message_log(self, guild_id, origin_channel_id):
        """Determines if a message event should go to the Global Log or the isolated Flash Log."""
        
        # --- NEW: Resolves Thread/Forum IDs to their Parent Channel ID ---
        _temp_channel = self.bot.get_channel(origin_channel_id)
        if not _temp_channel:
            try:
                _temp_channel = await self.bot.fetch_channel(origin_channel_id)
            except:
                pass
        if _temp_channel and hasattr(_temp_channel, 'parent_id') and _temp_channel.parent_id:
            origin_channel_id = _temp_channel.parent_id
        # -----------------------------------------------------------------

        # FIXED: Corrected double key serialization loops by requesting the base string format directly
        specific_log_id = await self.get_config(guild_id, f"flash_route_{origin_channel_id}")
        if specific_log_id:
            # --- NEW: Forces an API fetch if the channel dropped from cache ---
            ch_obj = self.bot.get_channel(int(specific_log_id))
            if not ch_obj:
                try:
                    ch_obj = await self.bot.fetch_channel(int(specific_log_id))
                except discord.NotFound:
                    pass
            # ------------------------------------------------------------------
            if ch_obj and ch_obj.guild.id == guild_id: return ch_obj
            
        flash_target_id = await self.get_config(guild_id, "flash_target")
        
        if flash_target_id and int(flash_target_id) == origin_channel_id:
            log_id = await self.get_config(guild_id, "log_flash")
            # --- NEW: Forces an API fetch if the channel dropped from cache ---
            if log_id:
                ch_obj = self.bot.get_channel(int(log_id))
                if not ch_obj:
                    try:
                        ch_obj = await self.bot.fetch_channel(int(log_id))
                    except discord.NotFound:
                        pass
                if ch_obj and ch_obj.guild.id == guild_id: return ch_obj
            # ------------------------------------------------------------------
            return None
        
        log_id = await self.get_config(guild_id, "log_messages")
        # --- NEW: Forces an API fetch if the channel dropped from cache ---
        if log_id:
            ch_obj = self.bot.get_channel(int(log_id))
            if not ch_obj:
                try:
                    ch_obj = await self.bot.fetch_channel(int(log_id))
                except discord.NotFound:
                    pass
            if ch_obj and ch_obj.guild.id == guild_id: return ch_obj
        # ------------------------------------------------------------------
        return None

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Captures deleted messages and media."""
        if message.author.bot:
            return

        if not message.guild:
            return

        log_channel = await self.route_message_log(message.guild.id, message.channel.id)
        if not log_channel or log_channel.guild.id != message.guild.id:
            return

        embed = discord.Embed(color=self.color_deleted)
        # ADDED: Include the display_name (nickname) just in case the base username is obscure
        embed.set_author(name=f"{message.author.display_name} (@{message.author.name})", icon_url=message.author.display_avatar.url)
        
        # ADDED: Fallback channel name string in case the mention renders as a raw ID
        desc = f"Message deleted in {message.channel.mention} (**#{message.channel.name}**)\n"
        
        # --- NEW: REPLY TRACKING IMPLEMENTATION ---
        if message.reference and message.reference.message_id:
            target_user = "Unknown User"
            if message.reference.cached_message:
                target_user = f"{message.reference.cached_message.author.mention} ({message.reference.cached_message.author.display_name})"
            else:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    target_user = f"{ref_msg.author.mention} ({ref_msg.author.display_name})"
                except:
                    pass
            desc += f"↳ **Replying to:** {target_user}\n"
        desc += "\n"
        # ------------------------------------------
        
        if message.content:
            desc += f"**Content**\n{message.content[:2000]}\n"
        
        discord_files_to_send = []
        if message.attachments:
            desc += "\n**Attachments Caught:**\n"
            media_already_rendered = False
            
            async with aiohttp.ClientSession() as session:
                for att in message.attachments:
                    desc += f"📎 [{att.filename}]({att.proxy_url})\n"
                    
                    # --- NEW: ACTIVE MEDIA EMBED VISUAL GENERATOR ---
                    if not media_already_rendered:
                        if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                            embed.set_image(url=att.proxy_url)
                            media_already_rendered = True
                    
                    # --- ADDED: DOWNLOAD ARCHIVE ATTACHMENT BEFORE CDN WIPE ---
                    try:
                        async with session.get(att.proxy_url) as resp:
                            if resp.status == 200:
                                media_bytes = io.BytesIO(await resp.read())
                                d_file = discord.File(media_bytes, filename=att.filename)
                                discord_files_to_send.append(d_file)
                    except Exception as download_error:
                        print(f"Failed archive pre-fetch data streaming download: {download_error}")

        embed.description = desc
        embed.set_footer(text=f"User ID: {message.author.id} • {datetime.now(timezone.utc).strftime('%H:%M')}")
        
        if discord_files_to_send:
            await log_channel.send(embed=embed, files=discord_files_to_send)
        else:
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Captures edited messages, ignoring simple embed expansions."""
        if before.author.bot or before.content == after.content:
            return

        if not before.guild:
            return

        log_channel = await self.route_message_log(before.guild.id, before.channel.id)
        if not log_channel or log_channel.guild.id != before.guild.id:
            return

        embed = discord.Embed(color=self.color_edited)
        # ADDED: Include the display_name (nickname)
        embed.set_author(name=f"{before.author.display_name} (@{before.author.name})", icon_url=before.author.display_avatar.url)
        
        # ADDED: Fallback channel name string in case the mention renders as a raw ID
        desc = f"[Reply]({after.jump_url}) edited in {before.channel.mention} (**#{before.channel.name}**) - [Jump to message]({after.jump_url})\n\n"
        desc += f"**Old**\n{before.content[:1000]}\n\n"
        desc += f"**New**\n{after.content[:1000]}"
        
        embed.description = desc
        embed.set_footer(text=f"User ID: {before.author.id} • {datetime.now(timezone.utc).strftime('%H:%M')}")
        await log_channel.send(embed=embed)

    # --- RAW EVENT PROTOCOLS (UNCACHED MESSAGES) ---

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        """Captures deletions of uncached messages (e.g., old messages or after bot restart)."""
        if payload.cached_message:
            return
            
        if not payload.guild_id:
            return

        log_channel = await self.route_message_log(payload.guild_id, payload.channel_id)
        if not log_channel or log_channel.guild.id != payload.guild_id:
            return

        # Added explicit channel resolution fallback step to safely trace the exact name string
        resolved_channel = self.bot.get_channel(payload.channel_id)
        if not resolved_channel:
            try:
                resolved_channel = await self.bot.fetch_channel(payload.channel_id)
            except:
                pass

        channel_display = f"<#{payload.channel_id}>"
        if resolved_channel:
            channel_display = f"{resolved_channel.mention} (**#{resolved_channel.name}**)"

        embed = discord.Embed(color=self.color_deleted)
        embed.set_author(name="Ghost Message Deleted (Uncached)")
        embed.description = f"An older message was deleted in {channel_display}\n\n*Note: Because this message was sent before the bot's recent deployment/restart, Discord restricts access to the author and content.*"
        embed.set_footer(text=f"Message ID: {payload.message_id} • {datetime.now(timezone.utc).strftime('%H:%M')}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        """Captures edits of uncached messages."""
        if payload.cached_message:
            return 

        if not payload.guild_id:
            return

        log_channel = await self.route_message_log(payload.guild_id, payload.channel_id)
        if not log_channel or log_channel.guild.id != payload.guild_id:
            return

        data = payload.data
        if 'content' not in data:
            return 

        # Added dynamic structure checks to fetch incomplete or obscured target parameters out of the data block
        author_data = data.get('author', {})
        author_name = author_data.get('username', 'Unknown Author')
        author_id = author_data.get('id', 'Unknown ID')
        new_content = data.get('content', '')

        # Added step to attempt to fetch user from the server guild directly if fields match
        resolved_author = None
        if author_id != 'Unknown ID':
            try:
                guild_obj = self.bot.get_guild(payload.guild_id)
                if guild_obj:
                    resolved_author = guild_obj.get_member(int(author_id)) or await guild_obj.fetch_member(int(author_id))
            except:
                pass

        author_display_string = f"@{author_name}"
        if resolved_author:
            author_display_string = f"{resolved_author.display_name} (@{resolved_author.name})"

        # Added explicit channel name text extraction block to survive cache updates
        resolved_channel = self.bot.get_channel(payload.channel_id)
        if not resolved_channel:
            try:
                resolved_channel = await self.bot.fetch_channel(payload.channel_id)
            except:
                pass

        channel_display = f"<#{payload.channel_id}>"
        if resolved_channel:
            channel_display = f"{resolved_channel.mention} (**#{resolved_channel.name}**)"

        embed = discord.Embed(color=self.color_edited)
        embed.set_author(name=f"{author_display_string} (Uncached Edit)")
        
        desc = f"Message edited in {channel_display} - [Jump to message](https://discord.com/channels/{payload.guild_id}/{payload.channel_id}/{payload.message_id})\n\n"
        desc += f"**Old**\n*Unknown (Message was not in bot cache)*\n\n"
        desc += f"**New**\n{new_content[:1000]}"
        
        embed.description = desc
        embed.set_footer(text=f"User ID: {author_id} • {datetime.now(timezone.utc).strftime('%H:%M')}")
        await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ModerationLog(bot))
    print("✅ LOG: Next-Gen Moderation & Flash Protocols ONLINE.")
