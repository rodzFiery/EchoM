import discord
import os
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import database as db_module # Ensure this is imported for independent lookup
import json
import random # Ensure random is available for the new logic

# ===== CORE HELPERS & AUDIT =====

async def send_audit_log(bot, AUDIT_CHANNEL_ID, user_id, amount, source, xp=0, guild_id=None):
    """UPDATED: Guild-Independent Audit Logging System"""
    
    # --- INDEPENDENT LOOKUP LOGIC ---
    target_channel_id = AUDIT_CHANNEL_ID
    
    if guild_id:
        try:
            with db_module.get_db_connection() as conn:
                res = conn.execute("SELECT value FROM guild_config WHERE guild_id = ? AND key = 'audit_channel'", (guild_id,)).fetchone()
                if res:
                    target_channel_id = int(res[0])
        except:
            pass

    channel = bot.get_channel(target_channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(target_channel_id)
        except:
            return
    
    try:
        user = await bot.fetch_user(user_id)
        # --- NEW EROTIC AUDIT STYLE ---
        embed = discord.Embed(
            title="🕵️ THE MASTER'S LEDGER: TRANSACTION RECORDED", 
            description=f"A new reaction in the pit. Asset {user.mention} has processed a transaction.",
            color=0x8B0000, 
            timestamp=datetime.now(timezone.utc)
        )
        
        image_path = "LobbyTopRight.jpg"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="ledger_logo.jpg")
            embed.set_thumbnail(url="attachment://ledger_logo.jpg")
        else:
            embed.set_thumbnail(url=user.display_avatar.url)
            file = None
            
        embed.add_field(name="🫦 Ident: Asset", value=user.mention, inline=True)
        embed.add_field(name="⛓️ Source: Protocol", value=f"**{source}**", inline=True)
        
        val_flames = f"🔥 **+{amount}** Flames added to vault." if amount >= 0 else f"📉 **{amount}** Flames extracted."
        embed.add_field(name="💰 Currency Flow", value=val_flames, inline=False)
        
        if xp > 0:
            embed.add_field(name="💦 Neural Imprint (XP)", value=f"**+{xp}** experience units synchronized.", inline=False)
        
        embed.set_footer(text="🔞 THE RED ROOM RECORDS EVERYTHING 🔞")
        
        if file:
            await channel.send(file=file, embed=embed)
        else:
            await channel.send(embed=embed)
    except Exception as e: 
        print(f"Audit Log Error: {e}")

def fiery_embed(bot, nsfw_mode_active, title, description, color=0xFF4500):
    """ADDED: Centralized Embed Styler"""
    ext = bot.get_cog("FieryExtensions")
    if (ext and hasattr(ext, 'master_present') and ext.master_present) or nsfw_mode_active:
        color = 0x8B0000 
    
    embed = discord.Embed(title=f" {title.upper()} ", description=description, color=color)
    
    if os.path.exists("LobbyTopRight.jpg"):
        embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
        
    embed.set_footer(text="🔞 ECHO GAMES EDITION 🔞")
    embed.timestamp = datetime.now(timezone.utc)
    return embed

# ===== ADDED: COUNTING GAME PROTOCOL =====

class DungeonCounter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.counts = {} # Simple in-memory tracker: {channel_id: current_count}
        self.designated_channel = 0 # Persistent Math Protocol Channel (Legacy fallback)
        self.next_tribute_number = 0 # Tracks when the next random tribute occurs (Legacy fallback)
        
        # --- ADDED: Multi-Server Mappings ---
        self.active_channels = {} # {guild_id: channel_id}
        self.tribute_trackers = {} # {guild_id: next_tribute_number}

    def load_channel(self):
        """Loads designated math channel and current count from config table."""
        try:
            with db_module.get_db_connection() as conn:
                # Ensure the table exists before selecting
                conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
                
                # --- ADDED: Load all math channels across all servers ---
                conn.row_factory = db_module.sqlite3.Row
                channel_rows = conn.execute("SELECT key, value FROM config WHERE key LIKE 'math_channel_%'").fetchall()
                for row in channel_rows:
                    key_parts = row['key'].split('_')
                    if len(key_parts) >= 3:
                        guild_id = int(key_parts[-1])
                        self.active_channels[guild_id] = int(row['value'])
                
                # Load current counts for all active servers
                count_rows = conn.execute("SELECT key, value FROM config WHERE key LIKE 'math_current_count_%'").fetchall()
                for row in count_rows:
                    key_parts = row['key'].split('_')
                    if len(key_parts) >= 4:
                        guild_id = int(key_parts[-1])
                        channel_id = self.active_channels.get(guild_id)
                        if channel_id:
                            self.counts[channel_id] = int(row['value'])

                # Ensure columns exist in users table globally during load
                cursor = conn.execute("PRAGMA table_info(users)")
                cols = [c[1] for c in cursor.fetchall()]
                if "math_total_numbers" not in cols:
                    conn.execute("ALTER TABLE users ADD COLUMN math_total_numbers INTEGER DEFAULT 0")
                if "math_total_tributes" not in cols:
                    conn.execute("ALTER TABLE users ADD COLUMN math_total_tributes INTEGER DEFAULT 0")
                conn.commit()
        except Exception as e:
            print(f"Math Load Error: {e}")

    def save_count(self, count, guild_id=None):
        """Saves current count to the database for persistence."""
        try:
            with db_module.get_db_connection() as conn:
                # --- ADDED: Save based on guild ID ---
                if guild_id:
                    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f'math_current_count_{guild_id}', str(count)))
                else:
                    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('math_current_count', ?)", (str(count),))
                conn.commit()
        except Exception as e:
            print(f"Math Save Error: {e}")

    @commands.command(name="math")
    @commands.has_permissions(manage_channels=True)
    async def set_math_channel(self, ctx, channel: discord.TextChannel = None):
        """DESIGNATE THE MATH PIT: Sets the active channel for counting."""
        target = channel or ctx.channel
        guild_id = ctx.guild.id
        
        self.designated_channel = target.id
        # --- ADDED: Register channel to specific server ---
        self.active_channels[guild_id] = target.id
        
        # Reset count when re-setting channel
        self.counts[target.id] = 0
        self.next_tribute_number = 0
        self.tribute_trackers[guild_id] = 0
        
        with db_module.get_db_connection() as conn:
            # --- ADDED: Insert specific to the server's guild_id ---
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f'math_channel_{guild_id}', str(target.id)))
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, '0')", (f'math_current_count_{guild_id}',))
            conn.commit()
            
        desc = f"Protocol **MATH** initialized. The Master will only monitor numbers in {target.mention}."
        await ctx.send(embed=fiery_embed(self.bot, False, "MATH PROTOCOL SET", desc))

    @commands.command(name="mathfix")
    @commands.has_permissions(manage_channels=True)
    async def math_fix_count(self, ctx, new_number: int):
        """FORCE SEQUENCE: Sets the current count to a specific number."""
        guild_id = ctx.guild.id
        current_math_channel = self.active_channels.get(guild_id, 0)
        
        if current_math_channel == 0:
            return await ctx.send("❌ **Error:** No math channel designated yet. Use `!math` first.")

        self.counts[current_math_channel] = new_number
        self.save_count(new_number, guild_id)
        
        desc = f"The Master has recalibrated the sequence. The current count is now **{new_number}**.\n\n" \
               f"The next required number is **{new_number + 1}**."
        await ctx.send(embed=fiery_embed(self.bot, False, "MATH PROTOCOL ADJUSTED", desc))

    # --- THE MEDIA PURGE PROTOCOL ---
    @commands.command(name="deletemymedia")
    async def delete_my_media(self, ctx, days: int):
        """PURGE PROTOCOL: Scans server history and targets user files older than specified days."""
        if days < 0:
            return await ctx.send("❌ **Sequence Failure:** Time criteria metrics cannot fall into negative boundaries.")
        
        status_msg = await ctx.send("⚙️ **SCANNING SERVERS...** Querying server history frames for archive links. Please remain patient...")
        
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=days)
        
        deleted_count = 0
        channels_scanned = 0
        earliest_timestamp = None
        latest_timestamp = None
        
        # FIXED: Restricted history scanning parameters exclusively to channels matching the current contextual guild layout
        for channel in ctx.guild.text_channels:
            # Verify permissions before checking history frames
            perms = channel.permissions_for(ctx.guild.me)
            if not perms.read_message_history or not perms.read_messages:
                continue
                
            channels_scanned += 1
            try:
                async for msg in channel.history(limit=500, before=cutoff_date):
                    # STRICT OWNER RULE: Ensure we ONLY target and match the ID of the person executing the command
                    if msg.author.id == ctx.author.id:
                        if msg.attachments or any(embed.type in ['image', 'video', 'gifv'] for embed in msg.embeds):
                            msg_time = msg.created_at.replace(tzinfo=timezone.utc)
                            
                            # Keep track of dates found
                            if earliest_timestamp is None or msg_time < earliest_timestamp:
                                earliest_timestamp = msg_time
                            if latest_timestamp is None or msg_time > latest_timestamp:
                                latest_timestamp = msg_time
                                
                            try:
                                await msg.delete()
                                deleted_count += 1
                            except:
                                pass
            except Exception as channel_error:
                print(f"Skipping channel scanning track loop: {channel_error}")
                
        await status_msg.delete()
        
        # Build layout details for response block
        earliest_str = earliest_timestamp.strftime('%d de %b de %Y %H:%M') if earliest_timestamp else "N/A"
        latest_str = latest_timestamp.strftime('%d de %b de %Y %H:%M') if latest_timestamp else "N/A"
        
        report_desc = (
            f"Asset {ctx.author.mention}, your historical footprints file wipe has concluded successfully.\n\n"
            f"### 🧪 DELETION BREAKDOWN:\n"
            f"* **Purged Items:** `{deleted_count}` active media/attachments\n"
            f"* **Channels Processed:** `{channels_scanned}` targets checked\n"
            f"* **Target Timeline Limit:** Older than `{days}` days\n\n"
            f"### 🗓️ CHRONOLOGICAL RANGE OF DELETED ITEMS:\n"
            f"* **Oldest File Found:** `{earliest_str}`\n"
            f"* **Newest File Found:** `{latest_str}`"
        )
        
        embed = fiery_embed(self.bot, True, "🗑️ FILES WIPED FROM LEDGER", report_desc)
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        if not message.guild: return
        
        guild_id = message.guild.id
        
        # Load channel and count from DB if memory is empty (happens on deploy)
        if not self.active_channels or not self.counts: 
            self.load_channel()
            
        active_channel_for_guild = self.active_channels.get(guild_id, 0)
            
        # RESTRICTION: Only process if the channel matches the !math designation for this specific server
        if message.channel.id != active_channel_for_guild: return
        
        if message.content.isdigit():
            val = int(message.content)
            channel_id = message.channel.id
            current = self.counts.get(channel_id, 0)

            # Sequence Check
            if val == current + 1:
                self.counts[channel_id] = val
                self.save_count(val, guild_id) # PERSISTENCE: Save each increment to DB immediately
                
                # --- UPDATE USER HISTORY STATS ---
                try:
                    with db_module.get_db_connection() as conn:
                        # Register user if they don't exist to avoid integrity errors
                        conn.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.author.id,))
                        # Direct increment
                        conn.execute("UPDATE users SET math_total_numbers = COALESCE(math_total_numbers, 0) + 1 WHERE id = ?", (message.author.id,))
                        conn.commit()
                except Exception as e: 
                    print(f"Stats Error: {e}")

                # Logic for Randomized Tributes (Infinite Counting)
                current_tribute = self.tribute_trackers.get(guild_id, 0)
                if current_tribute == 0:
                    if random.random() < 0.05:
                        self.tribute_trackers[guild_id] = val
                        current_tribute = val

                # If the Tribute number is hit
                if current_tribute != 0 and val == current_tribute:
                    self.tribute_trackers[guild_id] = 0 # Reset tribute tracker
                    
                    # --- UPDATE TRIBUTE COUNT & FETCH STATS ---
                    u_numbers = 0
                    u_tributes = 0
                    try:
                        with db_module.get_db_connection() as conn:
                            conn.execute("UPDATE users SET math_total_tributes = COALESCE(math_total_tributes, 0) + 1 WHERE id = ?", (message.author.id,))
                            conn.commit()
                            
                            # Use row_factory style for dict-like access
                            conn.row_factory = db_module.sqlite3.Row
                            row = conn.execute("SELECT math_total_numbers, math_total_tributes FROM users WHERE id = ?", (message.author.id,)).fetchone()
                            if row:
                                u_numbers = row["math_total_numbers"] if row["math_total_numbers"] else 0
                                u_tributes = row["math_total_tributes"] if row["math_total_tributes"] else 0
                    except Exception as e: 
                        print(f"Fetch Error: {e}")

                    desc = (
                        f"🎯 **TRIBUTE ACTIVATED: {val}**\n\n"
                        f"Asset {message.author.mention}, you have hit a hidden target.\n"
                        f"🫦 A tease picture must be posted immediately. The count continues."
                    )
                    embed = fiery_embed(self.bot, True, "🔞 TRIBUTE REQUIRED 🔞", desc)
                    
                    # Add historical stats to the embed
                    embed.add_field(name="📊 Member Statistics", value=f"Total Numbers Contributed: **{u_numbers}**\nTributes Demanded: **{u_tributes}**", inline=False)
                    
                    if os.path.exists("LobbyTopRight.jpg"):
                        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
                        await message.channel.send(file=file, embed=embed)
                    else:
                        await message.channel.send(embed=embed)
                
                # Standard confirmation for non-tribute numbers
                else:
                    try: await message.add_reaction("✅")
                    except: pass
            
            # Error handling if they break the count
            elif val != current + 1:
                try: await message.add_reaction("❌")
                except: pass

async def setup(bot):
    # Registering the Cog properly to ensure !math is found
    cog = DungeonCounter(bot)
    cog.load_channel()
    await bot.add_cog(cog)
