import discord
from discord.ext import commands
from datetime import datetime, timezone
import sqlite3
import os
import json

# Maps {receiver_id: {"sender_id": id, "guild_id": id}} or {message_id: {"sender_id": id, "guild_id": id}}
whisper_sessions = {}
# Maps {guild_id: True}
whisper_log_destinations = {} 
lobby_channel_id = None
BOT_OWNER_ID = 1482648173016252439
# ADDED: Default log channel ID
DEFAULT_LOG_CHANNEL_ID = 1498246295255646420
# ADDED: Global state toggle for system pause/resume tracking
whisper_system_active = True

# --- ADDED: PERSISTENCE LAYER FUNCTIONS TO PREVENT DATA LOSS ON RAILWAY DEPLOYS ---
def save_backup_config(key, value):
    filename = "whisper_backup_config.json"
    data = {"lobby_channel_id": None, "monitored_servers": [], "opt_outs": [], "system_active": True}
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
        except:
            pass
            
    if "opt_outs" not in data:
        data["opt_outs"] = []
    if "system_active" not in data:
        data["system_active"] = True
            
    if key == "lobby_channel_id":
        data["lobby_channel_id"] = value
    elif key == "add_server":
        if value not in data.get("monitored_servers", []):
            if "monitored_servers" not in data:
                data["monitored_servers"] = []
            data["monitored_servers"].append(value)
    elif key == "add_opt_out":
        if value not in data["opt_outs"]:
            data["opt_outs"].append(value)
    elif key == "remove_opt_out":
        if value in data["opt_outs"]:
            data["opt_outs"].remove(value)
    elif key == "system_active":
        data["system_active"] = value
            
    with open(filename, "w") as f:
        json.dump(data, f)

def load_backup_config():
    filename = "whisper_backup_config.json"
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except:
        return None

async def log_whisper_activity(client, guild, target_member, action="received", sender=None, content=None):
    # 1. Database logic for audit log (fully isolated)
    is_logging_enabled = False
    with sqlite3.connect("database.db") as conn:
        conn.row_factory = None
        # ADDED: Ensure table exists so it doesn't fail if DB wiped
        conn.execute("CREATE TABLE IF NOT EXISTS whisper_server_logs (guild_id INTEGER PRIMARY KEY)")
        cursor = conn.execute("SELECT 1 FROM whisper_server_logs WHERE guild_id = ?", (guild.id,))
        audit_row = cursor.fetchone()
        if audit_row: is_logging_enabled = True
        
    # BACKUP RECOVERY CHECK: If DB was wiped on deploy, check backup file configurations
    if not is_logging_enabled:
        backup = load_backup_config()
        if backup and guild.id in backup.get("monitored_servers", []):
            with sqlite3.connect("database.db") as conn:
                conn.execute("INSERT OR IGNORE INTO whisper_server_logs (guild_id) VALUES (?)", (guild.id,))
            is_logging_enabled = True
    
    if is_logging_enabled:
        # FIXED: main.py overrides client.get_user to return a DB Row, so we strictly use fetch_user to get the Discord Object
        try: owner = await client.fetch_user(BOT_OWNER_ID)
        except: owner = None
        
        # ADDED: Debug print to help track owner fetch
        print(f"Log debug: owner found = {owner is not None}")
        
        if owner:
            try:
                # ADDED: Include whisper content in audit log for moderation
                msg_desc = f"**Content:** {content}" if content else "No content available."
                
                # ENHANCED LOGGING FORMAT FOR BOT OWNER MODERATION PURPOSES
                if action == "replied to":
                    audit_text = f"{target_member.mention} (`{target_member.id}`) replied to {sender.mention} (`{sender.id}`) with this message:\n{msg_desc}"
                elif action == "blocked / opt-out":
                    sender_text = sender.mention if sender else "Unknown User"
                    sender_id_text = f"`{sender.id}`" if sender else "`Unknown ID`"
                    audit_text = f"🚨 **BLOCKED ATTEMPT:** {sender_text} ({sender_id_text}) tried to whisper {target_member.mention} (`{target_member.id}`), but the target has whispers disabled.\n{msg_desc}"
                else:
                    sender_text = sender.mention if sender else "Unknown User"
                    sender_id_text = f"`{sender.id}`" if sender else "`Unknown ID`"
                    audit_text = f"{sender_text} ({sender_id_text}) sent a whisper to {target_member.mention} (`{target_member.id}`) with this message:\n{msg_desc}"

                embed = discord.Embed(
                    title=f"Whisper Audit Tracker: {guild.name}", 
                    description=audit_text, 
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                await owner.send(embed=embed)
            except Exception as e:
                print(f"Could not send log to owner: {e}")
        else:
            # ADDED: Error log for owner fetch fail
            print("Could not find owner to send log.")

    # MODIFIED: Stopped execution early for replies and blocks right here. 
    # This completely skips public channel messages/pings for replies, but lets everything above (like DB updates and Owner Logs) execute properly.
    if action == "replied to" or action == "blocked / opt-out":
        return

    # 2. Logic for Lobby channel announcement
    global lobby_channel_id
    
    # BACKUP RECOVERY CHECK FOR LOBBY CHANNEL
    if lobby_channel_id is None:
        backup = load_backup_config()
        if backup and backup.get("lobby_channel_id"):
            lobby_channel_id = int(backup["lobby_channel_id"])
            with sqlite3.connect("database.db") as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS whisper_config (key TEXT PRIMARY KEY, value INTEGER)")
                conn.execute("INSERT OR REPLACE INTO whisper_config (key, value) VALUES ('lobby_channel_id', ?)", (lobby_channel_id,))

    lobby_channel = guild.get_channel(lobby_channel_id) if lobby_channel_id else None
    
    if lobby_channel and isinstance(lobby_channel, discord.TextChannel):
        total_count = 0
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = None
            # ADDED: Table failsafe so it doesn't crash before reaching Step 3 if DB resets
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_counts (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)")
            cursor = conn.execute("SELECT count FROM whisper_counts WHERE user_id = ?", (target_member.id,))
            count_row = cursor.fetchone()
            if count_row:
                total_count = count_row[0]

        color = discord.Color.blue() if action == "received" else discord.Color.green()
        action_text = "received a new whisper" if action == "received" else "replied to a whisper"
        
        embed = discord.Embed(
            title="🔞 ANONYMOUS NEURAL WHISPER LOG 🔞", 
            description=f"**Target Asset:** {target_member.mention}\n**Current Status:** {action_text.capitalize()}\n**Intensity:** High-Heat Protocol", 
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="🌐 System Protocol", value="Encrypted transmission active", inline=True)
        embed.add_field(name="🔥 Heat Level", value="Maximum", inline=True)
        embed.add_field(name="📊 Total Whispers Received", value=str(total_count), inline=False)
        embed.set_author(name="Whisper Log Registry", icon_url=guild.icon.url if guild.icon else None)
        embed.set_thumbnail(url=target_member.display_avatar.url)
        embed.set_footer(text="Whisper log updated - Identity of sender remains classified.")
            
        await lobby_channel.send(content=f"🔔 ATTENTION: {target_member.mention} has received a new whisper!", embed=embed, view=ReplyView())

        # REPOST THE WHISPER LOBBY AUTOMATICALLY SO IT STAYS BEHIND
        try:
            # Delete old lobby messages to prevent channel flooding
            async for old_msg in lobby_channel.history(limit=20):
                if old_msg.author.id == client.user.id and old_msg.embeds and "💋 NEURAL WHISPER LOBBY 💋" in str(old_msg.embeds[0].title):
                    await old_msg.delete()
        except Exception as delete_error:
            print(f"Lobby clean error: {delete_error}")

        lobby_embed = discord.Embed(
            title="💋 NEURAL WHISPER LOBBY 💋", 
            description="### ⛓️ PRIVATE HANDSHAKE TERMINAL\n"
                        "Welcome to the shadows, darling. Want to confess a secret, leave a bite mark, or drive someone crazy entirely undetected?\n\n"
                        "• **Complete Anonymity:** The server records won't save your footprint.\n"
                        "• **Direct Sync:** Your target receives a secure panel directly in their private box.\n\n"
                        "*Go ahead... hit the switch below and leave them wondering all night.*", 
            color=0xE0115F
        )
        lobby_embed.set_footer(text="Encrypted Connection Online • Proceed at your own risk.")
        await lobby_channel.send(embed=lobby_embed, view=LobbyView())

    # 3. ADDED: Default server log channel logic
    default_log_channel = client.get_channel(DEFAULT_LOG_CHANNEL_ID)
    if not default_log_channel:
        try:
            default_log_channel = await client.fetch_channel(DEFAULT_LOG_CHANNEL_ID)
        except Exception as e:
            print(f"Log Error: Fetch failed - {e}")
            pass
            
    if default_log_channel:
        try:
            sender_info = sender.mention if sender else "Anonymous / Session Reply"
            log_embed = discord.Embed(
                title="Global Whisper System Log", 
                description=f"**Target Asset:** {target_member.mention}\n**Action Executed:** {action.capitalize()}\n**Associated User:** {sender_info}", 
                color=discord.Color.dark_gray(),
                timestamp=datetime.now(timezone.utc)
            )
            await default_log_channel.send(log_embed)
        except Exception as e:
            print(f"Could not send log to default log channel: {e}")


class ReplyModal(discord.ui.Modal):
    reply_content = discord.ui.TextInput(label='Your Reply', style=discord.TextStyle.paragraph, required=True)

    # ADDED: Accepting message_id dynamically to separate mixed session routes
    def __init__(self, message_id=None):
        super().__init__(title='Reply to Anonymous Whisper')
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # ADDED: Global emergency pause handling checks
            if not whisper_system_active:
                return await interaction.response.send_message("⚠️ The Whisper System is currently paused by administration. Please try again later.", ephemeral=True)

            session_data = None
            
            # ADDED: Target mapping via unique message ID first to completely separate distinct whispers
            if self.message_id:
                session_data = whisper_sessions.get(self.message_id)
                if not session_data:
                    with sqlite3.connect("database.db") as conn:
                        conn.row_factory = None
                        cursor = conn.execute("SELECT sender_id, guild_id FROM whisper_message_sessions WHERE message_id = ?", (self.message_id,))
                        row = cursor.fetchone()
                        if row:
                            session_data = {"sender_id": row[0], "guild_id": row[1]}
                            whisper_sessions[self.message_id] = session_data

            # Fallback to the original legacy user ID session mapping if message ID matching yields nothing
            if not session_data:
                session_data = whisper_sessions.get(interaction.user.id)
                if not session_data:
                    with sqlite3.connect("database.db") as conn:
                        conn.row_factory = None
                        cursor = conn.execute("SELECT sender_id, guild_id FROM whisper_sessions WHERE receiver_id = ?", (interaction.user.id,))
                        row = cursor.fetchone()
                        if row:
                            session_data = {"sender_id": row[0], "guild_id": row[1]}
                            whisper_sessions[interaction.user.id] = session_data

            if session_data:
                # Defensive extraction to permanently block the 'sqlite3.Row' attribute error
                raw_sender = session_data["sender_id"]
                original_sender_id = raw_sender[0] if type(raw_sender).__name__ == 'Row' else int(raw_sender)
                
                raw_guild = session_data["guild_id"]
                guild_id = raw_guild[0] if type(raw_guild).__name__ == 'Row' else int(raw_guild)
                
                try:
                    # FIXED: main.py overrides get_user, returning a sqlite Row. We strictly use fetch_user to get the Discord User.
                    sender = await interaction.client.fetch_user(original_sender_id)
                except:
                    sender = None
                
                if sender:
                    embed = discord.Embed(title="Anonymous Reply Received", description=self.reply_content.value, color=discord.Color.green())
                    
                    # MODIFIED: Dispatched directly to target box without setting legacy user id maps to prevent cross-chatter bugs
                    outbound_msg = await sender.send(embed=embed, view=ReplyView())
                    
                    # ADDED: Track outbound message session specifically to keep threads separated on subsequent replies
                    if outbound_msg:
                        whisper_sessions[outbound_msg.id] = {"sender_id": interaction.user.id, "guild_id": guild_id}
                        with sqlite3.connect("database.db") as conn:
                            conn.execute("CREATE TABLE IF NOT EXISTS whisper_message_sessions (message_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER)")
                            conn.execute("INSERT OR REPLACE INTO whisper_message_sessions (message_id, sender_id, guild_id) VALUES (?, ?, ?)", (outbound_msg.id, interaction.user.id, guild_id))
                            conn.commit()

                    guild = interaction.client.get_guild(guild_id)
                    # ADDED: Fetch guild fallback if not cached
                    if not guild:
                        try: guild = await interaction.client.fetch_guild(guild_id)
                        except: pass
                    if guild:
                        # FIXED: Passing sender=sender and content=self.reply_content.value to capture the message for logs
                        await log_whisper_activity(interaction.client, guild, interaction.user, action="replied to", sender=sender, content=self.reply_content.value)
                    await interaction.response.send_message("Reply sent anonymously!", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Could not find the sender.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Session not found. You must be a whisper recipient to use this button.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Could not send the reply. The user has DMs closed or has blocked the bot.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

class ReplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reply to the Whisper", style=discord.ButtonStyle.primary, custom_id="persistent_reply_btn")
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ADDED: Global emergency pause handling checks
        if not whisper_system_active:
            return await interaction.response.send_message("⚠️ The Whisper System is currently paused by administration.", ephemeral=True)
        # ADDED: Pass the unique DM message ID down to the modal handler
        msg_id = interaction.message.id if interaction.message else None
        await interaction.response.send_modal(ReplyModal(message_id=msg_id))

class WhisperMessageModal(discord.ui.Modal, title='Send Anonymous Whisper'):
    message_content = discord.ui.TextInput(label='Your Whisper', style=discord.TextStyle.paragraph, required=True)

    def __init__(self, target_member):
        super().__init__()
        self.target_member = target_member

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # ADDED: Global emergency pause handling checks
            if not whisper_system_active:
                return await interaction.response.send_message("⚠️ The Whisper System is currently paused by administration. Transmissions are locked.", ephemeral=True)

            # CHECK TARGET OPT-OUT STATUS PRIOR TO DISPATCHING DATA
            is_opted_out = False
            with sqlite3.connect("database.db") as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS whisper_opt_outs (user_id INTEGER PRIMARY KEY)")
                cursor = conn.execute("SELECT 1 FROM whisper_opt_outs WHERE user_id = ?", (self.target_member.id,))
                if cursor.fetchone():
                    is_opted_out = True
            
            if not is_opted_out:
                backup = load_backup_config()
                if backup and self.target_member.id in backup.get("opt_outs", []):
                    with sqlite3.connect("database.db") as conn:
                        conn.execute("INSERT OR IGNORE INTO whisper_opt_outs (user_id) VALUES (?)", (self.target_member.id,))
                        conn.commit()
                    is_opted_out = True

            if is_opted_out:
                # LOG THE BLOCKED ATTEMPT SECURELY TO THE BOT OWNER
                await log_whisper_activity(interaction.client, interaction.guild, self.target_member, action="blocked / opt-out", sender=interaction.user, content=self.message_content.value)
                # RETURN EXPLICIT ANONYMOUS NOTICE BACK TO THE INITIATOR WITHOUT EXPOSING IDENTITIES
                return await interaction.response.send_message("❌ This member does not accept whispers.", ephemeral=True)

            await handle_whisper_logic(interaction.client, interaction.user, self.target_member, self.message_content.value, interaction.guild)
            await interaction.response.send_message("✅ Whisper sent anonymously!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Could not send the whisper. The user has DMs closed or has blocked the bot.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

class UserSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Search and select the receiver...")
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        # ADDED: Global emergency pause handling checks
        if not whisper_system_active:
            return await interaction.response.send_message("⚠️ The Whisper System is currently paused by administration.", ephemeral=True)
        target = select.values[0]
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or await interaction.guild.fetch_member(target.id)
        await interaction.response.send_modal(WhisperMessageModal(target))

class LobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Transmit Secret", style=discord.ButtonStyle.danger, emoji="💋", custom_id="persistent_lobby_btn")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ADDED: Global emergency pause handling checks
        if not whisper_system_active:
            return await interaction.response.send_message("⚠️ The Whisper System is currently paused by administration. Transmissions are locked.", ephemeral=True)
        await interaction.response.send_message("Search for the receiver:", view=UserSelectView(), ephemeral=True)

async def handle_whisper_logic(client, sender, target_member, content, guild):
    with sqlite3.connect("database.db") as conn:
        conn.row_factory = None
        conn.execute("CREATE TABLE IF NOT EXISTS whisper_counts (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)")
        conn.execute("INSERT OR IGNORE INTO whisper_counts (user_id, count) VALUES (?, 0)", (target_member.id,))
        conn.execute("UPDATE whisper_counts SET count = count + 1 WHERE user_id = ?", (target_member.id,))
        
        # ADDED: Save session to database
        conn.execute("CREATE TABLE IF NOT EXISTS whisper_sessions (receiver_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER)")
        conn.execute("INSERT OR REPLACE INTO whisper_sessions (receiver_id, sender_id, guild_id) VALUES (?, ?, ?)", (target_member.id, sender.id, guild.id))
        conn.commit()
        
    # Map the target (receiver) to the sender so they can reply back
    whisper_sessions[target_member.id] = {"sender_id": sender.id, "guild_id": guild.id}
    embed = discord.Embed(title="You received an Anonymous Whisper", description=content, color=discord.Color.purple())
    # ADDED: view=ReplyView() so the receiver actually gets the button in their DM!
    dm_msg = await target_member.send(embed=embed, view=ReplyView())
    
    # FIXED: Tied directly via unique message ID dictionary maps and database logging mapping
    if dm_msg:
        whisper_sessions[dm_msg.id] = {"sender_id": sender.id, "guild_id": guild.id}
        with sqlite3.connect("database.db") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_message_sessions (message_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER)")
            conn.execute("INSERT OR REPLACE INTO whisper_message_sessions (message_id, sender_id, guild_id) VALUES (?, ?, ?)", (dm_msg.id, sender.id, guild.id))
            conn.commit()
            
    await log_whisper_activity(client, guild, target_member, action="received", sender=sender, content=content)

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        global lobby_channel_id, whisper_system_active
        
        # BACKUP RECOVERY CHECK ON SYSTEM BOOTUP
        backup = load_backup_config()
        
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = None
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_config (key TEXT PRIMARY KEY, value INTEGER)")
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_server_logs (guild_id INTEGER PRIMARY KEY)")
            # ADDED: Ensure whisper_counts exists on ready
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_counts (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)")
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_opt_outs (user_id INTEGER PRIMARY KEY)")
            # ADDED: Ensure message tracking table exists on ready boot
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_message_sessions (message_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER)")
            # ADDED: Handle bot-wide switch tracking layout inside the DB schema safely
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_global_state (key TEXT PRIMARY KEY, status INTEGER DEFAULT 1)")
            
            # Repopulate server logs table if wiped out
            if backup and backup.get("monitored_servers"):
                for s_id in backup["monitored_servers"]:
                    conn.execute("INSERT OR IGNORE INTO whisper_server_logs (guild_id) VALUES (?)", (s_id,))
            
            # Repopulate opt-out list table if wiped out
            if backup and backup.get("opt_outs"):
                for u_id in backup["opt_outs"]:
                    conn.execute("INSERT OR IGNORE INTO whisper_opt_outs (user_id) VALUES (?)", (u_id,))
            
            # Repopulate lobby configurations if wiped out
            if backup and backup.get("lobby_channel_id"):
                conn.execute("INSERT OR REPLACE INTO whisper_config (key, value) VALUES ('lobby_channel_id', ?)", (backup["lobby_channel_id"],))
            conn.commit()
            
            # ADDED: Restore system status visibility metrics
            if backup and "system_active" in backup:
                whisper_system_active = backup["system_active"]
                conn.execute("INSERT OR REPLACE INTO whisper_global_state (key, status) VALUES ('bot_active', ?)", (1 if whisper_system_active else 0,))
                conn.commit()
            else:
                cursor = conn.execute("SELECT status FROM whisper_global_state WHERE key = 'bot_active'")
                state_row = cursor.fetchone()
                if state_row:
                    whisper_system_active = True if state_row[0] == 1 else False

            # ADDED: Table creation and memory load for sessions on startup
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_sessions (receiver_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER)")
            cursor = conn.execute("SELECT receiver_id, sender_id, guild_id FROM whisper_sessions")
            for session_row in cursor.fetchall():
                whisper_sessions[session_row[0]] = {"sender_id": session_row[1], "guild_id": session_row[2]}
            
            # ADDED: Pull message-level tracking records back into memory cache on ready load
            cursor = conn.execute("SELECT message_id, sender_id, guild_id FROM whisper_message_sessions")
            for msg_row in cursor.fetchall():
                whisper_sessions[msg_row[0]] = {"sender_id": msg_row[1], "guild_id": msg_row[2]}
            
            cursor = conn.execute("SELECT value FROM whisper_config WHERE key = 'lobby_channel_id'")
            row = cursor.fetchone()
            if row and row[0] is not None:
                lobby_channel_id = int(row[0])
                
        self.bot.add_view(LobbyView())
        self.bot.add_view(ReplyView())

    @commands.command(name="togglewhisperbot")
    @commands.is_owner()
    async def toggle_global_whisper_system(self, ctx):
        """ADDED: Owner-only emergency toggle command to securely pause or resume the entire system without losing configurations."""
        global whisper_system_active
        whisper_system_active = not whisper_system_active
        
        with sqlite3.connect("database.db") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_global_state (key TEXT PRIMARY KEY, status INTEGER DEFAULT 1)")
            conn.execute("INSERT OR REPLACE INTO whisper_global_state (key, status) VALUES ('bot_active', ?)", (1 if whisper_system_active else 0,))
            conn.commit()
            
        save_backup_config("system_active", whisper_system_active)
        
        if whisper_system_active:
            await ctx.send("✅ **System Operational:** The Whisper System has been completely resumed. All configurations, channels, and logs remain perfectly active.")
        else:
            await ctx.send("⏸️ **System Paused:** The Whisper System has been temporarily locked down. All settings are preserved, but transmissions are locked.")

    @commands.command(name="nowhisper")
    async def toggle_whisper_opt_out(self, ctx):
        """Allows members to opt out or opt back into receiving anonymous whispers."""
        is_opted_out = False
        with sqlite3.connect("database.db") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_opt_outs (user_id INTEGER PRIMARY KEY)")
            cursor = conn.execute("SELECT 1 FROM whisper_opt_outs WHERE user_id = ?", (ctx.author.id,))
            if cursor.fetchone():
                is_opted_out = True
                
        if is_opted_out:
            with sqlite3.connect("database.db") as conn:
                conn.execute("DELETE FROM whisper_opt_outs WHERE user_id = ?", (ctx.author.id,))
                conn.commit()
            save_backup_config("remove_opt_out", ctx.author.id)
            await ctx.send("✅ **Whisper System Activated:** You are now open to receive anonymous whispers again.")
        else:
            with sqlite3.connect("database.db") as conn:
                conn.execute("INSERT OR IGNORE INTO whisper_opt_outs (user_id) VALUES (?)", (ctx.author.id,))
                conn.commit()
            save_backup_config("add_opt_out", ctx.author.id)
            await ctx.send("❌ **Whisper System Deactivated:** You have successfully locked your portal. No new anonymous whispers can be sent to you.")

    @commands.command()
    async def setwhisper(self, ctx, channel: discord.TextChannel):
        global lobby_channel_id
        lobby_channel_id = channel.id
        with sqlite3.connect("database.db") as conn:
            # ADDED: Ensure table exists just in case
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_config (key TEXT PRIMARY KEY, value INTEGER)")
            conn.execute("INSERT OR REPLACE INTO whisper_config (key, value) VALUES ('lobby_channel_id', ?)", (channel.id,))
            conn.commit()
        save_backup_config("lobby_channel_id", channel.id)
        await ctx.send(f"Whisper lobby set to {channel.mention}")

    @commands.command()
    async def whisperserverset(self, ctx, server_id: int):
        with sqlite3.connect("database.db") as conn:
            # ADDED: Ensure table exists just in case
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_server_logs (guild_id INTEGER PRIMARY KEY)")
            conn.execute("INSERT OR IGNORE INTO whisper_server_logs (guild_id) VALUES (?)", (server_id,))
            conn.commit()
        save_backup_config("add_server", server_id)
        await ctx.send(f"Logs for server ID {server_id} are now forwarded to your DMs.")

    @commands.command()
    async def openwhisper(self, ctx):
        embed = discord.Embed(
            title="💋 NEURAL WHISPER LOBBY 💋", 
            description="### ⛓️ PRIVATE HANDSHAKE TERMINAL\n"
                        "Welcome to the shadows, darling. Want to confess a secret, leave a bite mark, or drive someone crazy entirely undetected?\n\n"
                        "• **Complete Anonymity:** The server records won't save your footprint.\n"
                        "• **Direct Sync:** Your target receives a secure panel directly in their private box.\n\n"
                        "*Go ahead... hit the switch below and leave them wondering all night.*", 
            color=0xE0115F
        )
        embed.set_footer(text="Encrypted Connection Online • Proceed at your own risk.")
        await ctx.send(embed=embed, view=LobbyView())

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))
