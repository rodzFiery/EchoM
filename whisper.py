import discord
from discord.ext import commands
from datetime import datetime, timezone
import sqlite3
import os
import json
import asyncio
import hashlib
import random

# --- PERSISTENCE STORAGE PATH FOR RAILWAY VOLUMES ---
PERSISTENT_ENV = os.getenv("PERSISTENT_STORAGE_DIR", "/data")

if os.path.exists("/data"):
    STORAGE_DIR = "/data"
elif os.path.exists(PERSISTENT_ENV):
    try:
        os.makedirs(PERSISTENT_ENV, exist_ok=True)
        STORAGE_DIR = PERSISTENT_ENV
    except Exception:
        STORAGE_DIR = os.path.dirname(os.path.abspath(__file__))
else:
    STORAGE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(STORAGE_DIR, "database.db")
BACKUP_PATH = os.path.join(STORAGE_DIR, "whisper_backup_config.json")

# In-Memory Cache maps
whisper_sessions = {}
guild_lobby_channels = {}
monitored_server_logs = set()
lobby_channel_id = None

BOT_OWNER_ID = 1482648173016252439
DEFAULT_LOG_CHANNEL_ID = 1498246295255646420
whisper_system_active = True

# --- DEDUPLICATION & CONCURRENCY LOCK ENGINE ---
active_whisper_locks = set()
processed_payload_hashes = set()

# --- PERSONA MASK DEFINITIONS ---
PERSONA_MASKS = {
    "standard": {
        "name": "Standard Neural Whisper",
        "title": "💋 You received an Anonymous Whisper",
        "color": 0x9B59B6,
        "icon": "https://cdn.discordapp.com/embed/avatars/0.png"
    },
    "admirer": {
        "name": "The Secret Admirer",
        "title": "💌 A Secret Admirer left a message for you...",
        "color": 0xFF69B4,
        "icon": "https://cdn.discordapp.com/embed/avatars/1.png"
    },
    "shadow": {
        "name": "The Shadow Observer",
        "title": "👁️ Watching from the Shadows...",
        "color": 0x34495E,
        "icon": "https://cdn.discordapp.com/embed/avatars/2.png"
    },
    "rival": {
        "name": "The Arch-Rival",
        "title": "⚡ A challenge from your Arch-Rival!",
        "color": 0xE74C3C,
        "icon": "https://cdn.discordapp.com/embed/avatars/3.png"
    },
    "phantom": {
        "name": "The Phantom",
        "title": "👻 A ghost in the machine whispered to you...",
        "color": 0x1ABC9C,
        "icon": "https://cdn.discordapp.com/embed/avatars/4.png"
    }
}

# --- TRUTH OR DARE POOLS ---
TRUTH_PROMPTS = [
    "What is something you've never confessed to anyone in this server?",
    "Who was your very first impression/crush in this server?",
    "What is the biggest secret you are holding right now?",
    "If you had to delete one channel in this server forever, which one would it be?"
]

DARE_PROMPTS = [
    "Change your server nickname to whatever the person who sent this demands for 24h.",
    "Post your most used emoji in general chat right now with zero context.",
    "Send a voice message in general singing 5 seconds of any song.",
    "Send a completely random meme to the last person who messaged you."
]

WYR_PROMPTS = [
    "Would you rather know who sent every whisper OR have everyone know when you send one?",
    "Would you rather lose access to all text channels OR all voice channels in this server?",
    "Would you rather reveal your browser history to the server OR your camera roll?"
]

def acquire_whisper_lock(key: str) -> bool:
    if key in active_whisper_locks:
        return False
    active_whisper_locks.add(key)
    return True

def release_whisper_lock(key: str):
    active_whisper_locks.discard(key)

def is_duplicate_payload(sender_id: int, target_id: int, content: str) -> bool:
    raw_key = f"{sender_id}:{target_id}:{content}"
    payload_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    if payload_hash in processed_payload_hashes:
        return True
    processed_payload_hashes.add(payload_hash)
    asyncio.get_event_loop().call_later(10, processed_payload_hashes.discard, payload_hash)
    return False

def get_pair_key(user1_id: int, user2_id: int) -> str:
    """Generates a deterministic hash identifier for a pair of two interacting users."""
    sorted_ids = sorted([int(user1_id), int(user2_id)])
    raw_key = f"{sorted_ids[0]}:{sorted_ids[1]}"
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

def is_pair_blocked(sender_id: int, receiver_id: int) -> bool:
    """Checks whether the recipient has blocked whispers specifically from this anonymous pair key."""
    pair_key = get_pair_key(sender_id, receiver_id)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS whisper_blocked_pairs (pair_key TEXT PRIMARY KEY, blocked_by INTEGER)")
        cursor = conn.execute("SELECT 1 FROM whisper_blocked_pairs WHERE pair_key = ?", (pair_key,))
        return cursor.fetchone() is not None

def record_transcript_entry(sender_id: int, receiver_id: int, content: str):
    """Appends a timestamped transmission message into the paired encrypted database ledger."""
    pair_key = get_pair_key(sender_id, receiver_id)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS whisper_pair_transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair_key TEXT,
                sender_id INTEGER,
                receiver_id INTEGER,
                content TEXT,
                timestamp TEXT
            )
        """)
        conn.execute(
            "INSERT INTO whisper_pair_transcripts (pair_key, sender_id, receiver_id, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (pair_key, sender_id, receiver_id, content, now_str)
        )
        conn.commit()

# --- INTELLIGENT DM INDUCTION SENSOR + OWNER ALERT ENGINE ---
async def alert_and_check_dm_induction(client, user: discord.User, text: str, context_type: str) -> bool:
    if not text:
        return False
    
    normalized_text = text.lower()
    
    forbidden_phrases = [
        "talking in private",
        "slide",
        "can i",
        "send you a message",
        "send u a message",
        "private"
    ]
    
    detected = False
    triggered_phrase = None
    
    for phrase in forbidden_phrases:
        if phrase in normalized_text:
            detected = True
            triggered_phrase = phrase
            break
            
    if not detected:
        cleaned_for_words = normalized_text.replace(".", "").replace("-", "").replace("'", "")
        words_list = cleaned_for_words.split()
        
        if "dm" in words_list or "dms" in words_list:
            detected = True
            triggered_phrase = "dm / dms (standalone word identifier)"

    if detected:
        try:
            owner = await client.fetch_user(BOT_OWNER_ID)
            if owner:
                alert_embed = discord.Embed(
                    title="⚠️ DM INDUCTION SENSOR ALERT ⚠️",
                    description=f"The intelligent filter has intercepted a blocked phrase variation.",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(timezone.utc)
                )
                alert_embed.add_field(name="👤 Triggered By", value=f"{user.mention} (`{user.id}`)", inline=True)
                alert_embed.add_field(name="📁 Transmission Type", value=context_type, inline=True)
                alert_embed.add_field(name="🚫 Detected Trigger", value=f"`{triggered_phrase}`", inline=False)
                alert_embed.add_field(name="📝 Flagged Content", value=text, inline=False)
                await owner.send(embed=alert_embed)
        except Exception as alert_error:
            print(f"Failed to transmit filter alert to bot owner: {alert_error}")
        return True
        
    return False

# --- PERSISTENCE SWAP CONFIG LOADERS AND SAVERS ---
def load_backup_config():
    filename = BACKUP_PATH
    default_structure = {
        "lobby_channel_id": None, 
        "guild_lobbies": {}, 
        "monitored_servers": [], 
        "opt_outs": [], 
        "system_active": True
    }
    if not os.path.exists(filename):
        return default_structure
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return default_structure
            for key, val in default_structure.items():
                if key not in data:
                    data[key] = val
            return data
    except Exception as e:
        print(f"Error loading backup config: {e}")
        return default_structure

def save_backup_config(key, value, guild_id=None):
    filename = BACKUP_PATH
    data = load_backup_config()
            
    if key == "lobby_channel_id":
        data["lobby_channel_id"] = value
    elif key == "set_guild_lobby" and guild_id:
        if "guild_lobbies" not in data or not isinstance(data["guild_lobbies"], dict):
            data["guild_lobbies"] = {}
        data["guild_lobbies"][str(guild_id)] = value
    elif key == "add_server":
        if "monitored_servers" not in data or not isinstance(data["monitored_servers"], list):
            data["monitored_servers"] = []
        if value not in data["monitored_servers"]:
            data["monitored_servers"].append(value)
    elif key == "add_opt_out":
        if "opt_outs" not in data or not isinstance(data["opt_outs"], list):
            data["opt_outs"] = []
        if value not in data["opt_outs"]:
            data["opt_outs"].append(value)
    elif key == "remove_opt_out":
        if "opt_outs" in data and value in data["opt_outs"]:
            data["opt_outs"].remove(value)
    elif key == "system_active":
        data["system_active"] = value
    elif key == "full_sync":
        if isinstance(value, dict):
            data.update(value)

    temp_filename = f"{filename}.tmp"
    try:
        with open(temp_filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_filename, filename)
    except Exception as e:
        print(f"Failed to write backup configuration safely: {e}")
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except Exception:
                pass

async def async_save_backup_config(key, value, guild_id=None):
    await asyncio.to_thread(save_backup_config, key, value, guild_id)

async def log_whisper_activity(client, guild, target_member, action="received", sender=None, content=None):
    is_logging_enabled = False
    if guild and guild.id in monitored_server_logs:
        is_logging_enabled = True

    if not is_logging_enabled and guild:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = None
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_server_logs (guild_id INTEGER PRIMARY KEY)")
            cursor = conn.execute("SELECT 1 FROM whisper_server_logs WHERE guild_id = ?", (guild.id,))
            if cursor.fetchone():
                is_logging_enabled = True
                monitored_server_logs.add(guild.id)

    if not is_logging_enabled and guild:
        backup = load_backup_config()
        if backup and guild.id in backup.get("monitored_servers", []):
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("INSERT OR IGNORE INTO whisper_server_logs (guild_id) VALUES (?)", (guild.id,))
                conn.commit()
            is_logging_enabled = True
            monitored_server_logs.add(guild.id)
    
    if is_logging_enabled:
        try:
            owner = await client.fetch_user(BOT_OWNER_ID)
        except Exception:
            owner = None
        
        if owner:
            try:
                msg_desc = f"**Content:** {content}" if content else "No content available."
                guild_name = guild.name if guild else "Unknown Server"
                
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
                    title=f"Whisper Audit Tracker: {guild_name}", 
                    description=audit_text, 
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                await owner.send(embed=embed)
            except Exception as e:
                print(f"Could not send log to owner: {e}")

    if action == "replied to" or action == "blocked / opt-out":
        return

    global lobby_channel_id, guild_lobby_channels
    
    target_lobby_id = guild_lobby_channels.get(guild.id) if guild else None
    
    if target_lobby_id is None and guild:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = None
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_guild_lobbies (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)")
            cursor = conn.execute("SELECT channel_id FROM whisper_guild_lobbies WHERE guild_id = ?", (guild.id,))
            row = cursor.fetchone()
            if row:
                target_lobby_id = row[0]
                guild_lobby_channels[guild.id] = target_lobby_id

    if target_lobby_id is None and guild:
        backup = load_backup_config()
        if backup and backup.get("guild_lobbies") and str(guild.id) in backup["guild_lobbies"]:
            target_lobby_id = int(backup["guild_lobbies"][str(guild.id)])
            guild_lobby_channels[guild.id] = target_lobby_id
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS whisper_guild_lobbies (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)")
                conn.execute("INSERT OR REPLACE INTO whisper_guild_lobbies (guild_id, channel_id) VALUES (?, ?)", (guild.id, target_lobby_id))
                conn.commit()

    if target_lobby_id is None:
        target_lobby_id = lobby_channel_id

    lobby_channel = guild.get_channel(target_lobby_id) if (guild and target_lobby_id) else None
    if not lobby_channel and target_lobby_id:
        try:
            lobby_channel = await client.fetch_channel(target_lobby_id)
        except Exception:
            lobby_channel = None
    
    if lobby_channel and isinstance(lobby_channel, discord.TextChannel):
        total_count = 0
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = None
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
        
        guild_icon_url = guild.icon.url if guild and guild.icon else None
        target_avatar_url = target_member.display_avatar.url if target_member and hasattr(target_member, "display_avatar") else None
        
        embed.set_author(name="Whisper Log Registry", icon_url=guild_icon_url)
        if target_avatar_url:
            embed.set_thumbnail(url=target_avatar_url)
        embed.set_footer(text="Whisper log updated - Identity of sender remains classified.")
            
        await lobby_channel.send(content=f"🔔 ATTENTION: {target_member.mention} has received a new whisper!", embed=embed, view=ReplyView())

        try:
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
                        "• **Direct Sync:** Your target receives a secure panel directly in their private box.\n"
                        "• **Masks & Games:** Custom Persona Masks, Anonymous Games, and Quick Polls available!\n\n"
                        "🔒 **Opt-Out Control:** Don't want whispers? Type `!nomorewhispers` to lock your portal. Use `!backtowhisper` anytime to reactivate.\n\n"
                        "*Go ahead... hit the switch below and leave them wondering all night.*", 
            color=0xE0115F
        )
        lobby_embed.set_footer(text="Encrypted Connection Online • Proceed at your own risk.")
        await lobby_channel.send(embed=lobby_embed, view=LobbyView())

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

# --- FEATURE 4: ANONYMOUS POLLS UI COMPONENTS ---
class PollVoteView(discord.ui.View):
    def __init__(self, poll_id, option_a_label, option_b_label):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.option_a_btn.label = option_a_label[:80]
        self.option_b_btn.label = option_b_label[:80]
        self.option_a_btn.custom_id = f"poll_vote_a:{poll_id}"
        self.option_b_btn.custom_id = f"poll_vote_b:{poll_id}"

    @discord.ui.button(style=discord.ButtonStyle.success, custom_id="poll_vote_a_default")
    async def option_a_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_vote(interaction, "A")

    @discord.ui.button(style=discord.ButtonStyle.secondary, custom_id="poll_vote_b_default")
    async def option_b_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_vote(interaction, "B")

    async def process_vote(self, interaction: discord.Interaction, choice: str):
        await interaction.response.defer(ephemeral=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS whisper_polls (
                    poll_id TEXT PRIMARY KEY,
                    option_a TEXT,
                    option_b TEXT,
                    votes_a INTEGER DEFAULT 0,
                    votes_b INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS whisper_poll_voters (
                    poll_id TEXT,
                    voter_id INTEGER,
                    PRIMARY KEY (poll_id, voter_id)
                )
            """)
            
            cursor = conn.execute("SELECT 1 FROM whisper_poll_voters WHERE poll_id = ? AND voter_id = ?", (self.poll_id, interaction.user.id))
            if cursor.fetchone():
                return await interaction.followup.send("⚠️ You have already voted on this anonymous poll card.", ephemeral=True)

            if choice == "A":
                conn.execute("UPDATE whisper_polls SET votes_a = votes_a + 1 WHERE poll_id = ?", (self.poll_id,))
            else:
                conn.execute("UPDATE whisper_polls SET votes_b = votes_b + 1 WHERE poll_id = ?", (self.poll_id,))
                
            conn.execute("INSERT INTO whisper_poll_voters (poll_id, voter_id) VALUES (?, ?)", (self.poll_id, interaction.user.id))
            conn.commit()

            cursor = conn.execute("SELECT option_a, option_b, votes_a, votes_b FROM whisper_polls WHERE poll_id = ?", (self.poll_id,))
            row = cursor.fetchone()

        if row:
            opt_a, opt_b, v_a, v_b = row
            total = v_a + v_b
            p_a = round((v_a / total) * 100) if total > 0 else 0
            p_b = round((v_b / total) * 100) if total > 0 else 0
            
            results_embed = discord.Embed(
                title="📊 Poll Results Recorded!",
                description=f"**{opt_a}:** `{v_a}` votes ({p_a}%)\n**{opt_b}:** `{v_b}` votes ({p_b}%)\n\n*Total Votes Cast: {total}*",
                color=discord.Color.gold()
            )
            await interaction.followup.send(embed=results_embed, ephemeral=True)

class ReplyModal(discord.ui.Modal):
    reply_content = discord.ui.TextInput(label='Your Reply', style=discord.TextStyle.paragraph, required=True)

    def __init__(self, message_id=None):
        super().__init__(title='Reply to Anonymous Whisper')
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        lock_key = f"reply:{interaction.user.id}:{self.message_id or 'fallback'}"
        if not acquire_whisper_lock(lock_key):
            return await interaction.followup.send("⚠️ A reply submission is already processing. Please wait.", ephemeral=True)

        try:
            if not whisper_system_active:
                return await interaction.followup.send("⚠️ The Whisper System is currently paused by administration. Please try again later.", ephemeral=True)

            if await alert_and_check_dm_induction(interaction.client, interaction.user, self.reply_content.value, "Session Reply Box"):
                return await interaction.followup.send("❌ **Transmission Blocked:** Requesting or offering to move conversations to private DMs is forbidden in whispers. Please use the public channels to ask for a DM connection.", ephemeral=True)

            session_data = None
            
            if self.message_id:
                session_data = whisper_sessions.get(self.message_id)
                if not session_data:
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.row_factory = None
                        cursor = conn.execute("SELECT sender_id, guild_id, last_content FROM whisper_message_sessions WHERE message_id = ?", (self.message_id,))
                        row = cursor.fetchone()
                        if row:
                            session_data = {"sender_id": row[0], "guild_id": row[1], "last_content": row[2]}
                            whisper_sessions[self.message_id] = session_data

            if not session_data:
                session_data = whisper_sessions.get(interaction.user.id)
                if not session_data:
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.row_factory = None
                        cursor = conn.execute("SELECT sender_id, guild_id, last_content FROM whisper_sessions WHERE receiver_id = ?", (interaction.user.id,))
                        row = cursor.fetchone()
                        if row:
                            session_data = {"sender_id": row[0], "guild_id": row[1], "last_content": row[2]}
                            whisper_sessions[interaction.user.id] = session_data

            if session_data:
                raw_sender = session_data["sender_id"]
                original_sender_id = raw_sender[0] if type(raw_sender).__name__ == 'Row' else int(raw_sender)
                
                raw_guild = session_data["guild_id"]
                guild_id = raw_guild[0] if type(raw_guild).__name__ == 'Row' else int(raw_guild)
                
                last_content = session_data.get("last_content", None)
                
                # Check if pair is blocked
                if is_pair_blocked(interaction.user.id, original_sender_id):
                    return await interaction.followup.send("❌ Transmission blocked: This portal connection has been terminated.", ephemeral=True)

                if is_duplicate_payload(interaction.user.id, original_sender_id, self.reply_content.value):
                    return await interaction.followup.send("⚠️ Duplicate transmission detected and discarded.", ephemeral=True)

                try:
                    sender = await interaction.client.fetch_user(original_sender_id)
                except Exception:
                    sender = None
                
                if sender:
                    record_transcript_entry(interaction.user.id, original_sender_id, self.reply_content.value)

                    embed = discord.Embed(title="Anonymous Reply Received", color=discord.Color.green())
                    
                    if last_content:
                        embed.add_field(name="📜 Last Whisper Transmitted", value=f"> {last_content}", inline=False)
                    
                    embed.add_field(name="✉️ Reply Content", value=self.reply_content.value, inline=False)
                    
                    outbound_msg = await sender.send(embed=embed, view=ReplyView())
                    
                    if outbound_msg:
                        whisper_sessions[outbound_msg.id] = {"sender_id": interaction.user.id, "guild_id": guild_id, "last_content": self.reply_content.value}
                        whisper_sessions[sender.id] = {"sender_id": interaction.user.id, "guild_id": guild_id, "last_content": self.reply_content.value}
                        
                        with sqlite3.connect(DB_PATH) as conn:
                            conn.execute("CREATE TABLE IF NOT EXISTS whisper_message_sessions (message_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER, last_content TEXT)")
                            conn.execute("INSERT OR REPLACE INTO whisper_message_sessions (message_id, sender_id, guild_id, last_content) VALUES (?, ?, ?, ?)", (outbound_msg.id, interaction.user.id, guild_id, self.reply_content.value))
                            
                            conn.execute("CREATE TABLE IF NOT EXISTS whisper_sessions (receiver_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER, last_content TEXT)")
                            conn.execute("INSERT OR REPLACE INTO whisper_sessions (receiver_id, sender_id, guild_id, last_content) VALUES (?, ?, ?, ?)", (sender.id, interaction.user.id, guild_id, self.reply_content.value))
                            conn.commit()

                    guild = interaction.client.get_guild(guild_id)
                    if not guild:
                        try:
                            guild = await interaction.client.fetch_guild(guild_id)
                        except Exception:
                            guild = None
                    if guild:
                        await log_whisper_activity(interaction.client, guild, interaction.user, action="replied to", sender=sender, content=self.reply_content.value)
                    await interaction.followup.send("Reply sent anonymously!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Could not find the sender.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Session not found. You must be a whisper recipient to use this button.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Could not send the reply. The user has DMs closed or has blocked the bot.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
        finally:
            release_whisper_lock(lock_key)

class ReplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reply to the Whisper", style=discord.ButtonStyle.primary, custom_id="persistent_reply_btn")
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not whisper_system_active:
            return await interaction.response.send_message("⚠️ The Whisper System is currently paused by administration.", ephemeral=True)
        msg_id = interaction.message.id if interaction.message else None
        await interaction.response.send_modal(ReplyModal(message_id=msg_id))

    @discord.ui.button(label="📜 View Transcript History", style=discord.ButtonStyle.secondary, custom_id="persistent_transcript_btn")
    async def transcript_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        msg_id = interaction.message.id if interaction.message else None
        session_data = whisper_sessions.get(msg_id) if msg_id else None

        if not session_data:
            session_data = whisper_sessions.get(interaction.user.id)

        if not session_data:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = None
                if msg_id:
                    cursor = conn.execute("SELECT sender_id, guild_id, last_content FROM whisper_message_sessions WHERE message_id = ?", (msg_id,))
                    row = cursor.fetchone()
                    if row:
                        session_data = {"sender_id": row[0], "guild_id": row[1], "last_content": row[2]}

                if not session_data:
                    cursor = conn.execute("SELECT sender_id, guild_id, last_content FROM whisper_sessions WHERE receiver_id = ?", (interaction.user.id,))
                    row = cursor.fetchone()
                    if row:
                        session_data = {"sender_id": row[0], "guild_id": row[1], "last_content": row[2]}

        if not session_data:
            return await interaction.followup.send("❌ No active transcript history found for this session portal.", ephemeral=True)

        other_user_id = session_data["sender_id"]
        if isinstance(other_user_id, tuple) or type(other_user_id).__name__ == 'Row':
            other_user_id = other_user_id[0]
        other_user_id = int(other_user_id)

        pair_key = get_pair_key(interaction.user.id, other_user_id)

        rows = []
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = None
            cursor = conn.execute("""
                SELECT sender_id, content, timestamp 
                FROM whisper_pair_transcripts 
                WHERE pair_key = ? 
                ORDER BY id ASC
            """, (pair_key,))
            rows = cursor.fetchall()

        if not rows:
            return await interaction.followup.send("📜 No past logs found in the encrypted archive for this thread yet.", ephemeral=True)

        formatted_lines = []
        for index, (s_id, content, ts) in enumerate(rows, start=1):
            if s_id == interaction.user.id:
                speaker_tag = "👤 **You**"
            else:
                speaker_tag = "🎭 **Anonymous Party**"
            
            formatted_lines.append(f"`#{index:02d}` `[{ts}]` {speaker_tag}:\n> {content}\n")

        full_transcript_text = "\n".join(formatted_lines)

        if len(full_transcript_text) > 3800:
            full_transcript_text = full_transcript_text[-3800:]
            full_transcript_text = "*(Older transcript entries truncated for length)*\n\n" + full_transcript_text

        transcript_embed = discord.Embed(
            title="📜 ENCRYPTED TRANSCRIPT HISTORY",
            description=f"### 🔐 **Session Portal Audit Trail**\nAll messages exchanged in this anonymous thread:\n\n{full_transcript_text}",
            color=0x2B2D31,
            timestamp=datetime.now(timezone.utc)
        )
        transcript_embed.set_footer(text="Neural Network Encryption • Identities Secured")

        await interaction.followup.send(embed=transcript_embed, ephemeral=True)

    # --- FEATURE 2: SAFE-WORD EMERGENCY KILL-SWITCH & BLOCK ---
    @discord.ui.button(label="🛑 Block Sender", style=discord.ButtonStyle.danger, custom_id="persistent_block_sender_btn")
    async def block_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        msg_id = interaction.message.id if interaction.message else None
        session_data = whisper_sessions.get(msg_id) if msg_id else None

        if not session_data:
            session_data = whisper_sessions.get(interaction.user.id)

        if not session_data:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = None
                if msg_id:
                    cursor = conn.execute("SELECT sender_id FROM whisper_message_sessions WHERE message_id = ?", (msg_id,))
                    row = cursor.fetchone()
                    if row:
                        session_data = {"sender_id": row[0]}
                if not session_data:
                    cursor = conn.execute("SELECT sender_id FROM whisper_sessions WHERE receiver_id = ?", (interaction.user.id,))
                    row = cursor.fetchone()
                    if row:
                        session_data = {"sender_id": row[0]}

        if not session_data:
            return await interaction.followup.send("❌ Unable to trace connection to execute block protocol.", ephemeral=True)

        other_user_id = session_data["sender_id"]
        if isinstance(other_user_id, tuple) or type(other_user_id).__name__ == 'Row':
            other_user_id = other_user_id[0]
        other_user_id = int(other_user_id)

        pair_key = get_pair_key(interaction.user.id, other_user_id)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_blocked_pairs (pair_key TEXT PRIMARY KEY, blocked_by INTEGER)")
            conn.execute("INSERT OR REPLACE INTO whisper_blocked_pairs (pair_key, blocked_by) VALUES (?, ?)", (pair_key, interaction.user.id))
            conn.commit()

        await interaction.followup.send("🛑 **Portal Locked:** Future anonymous whispers from this specific sender are permanently blocked. Their identity remains hidden.", ephemeral=True)

# --- OUTBOUND MODALS WITH MASK & POLL FEATURES ---
class WhisperMessageModal(discord.ui.Modal, title='Send Anonymous Whisper'):
    message_content = discord.ui.TextInput(label='Your Whisper', style=discord.TextStyle.paragraph, required=True)
    poll_option_a = discord.ui.TextInput(label='Optional Poll Choice A', style=discord.TextStyle.short, required=False, placeholder="e.g. Yes / Guess who?")
    poll_option_b = discord.ui.TextInput(label='Optional Poll Choice B', style=discord.TextStyle.short, required=False, placeholder="e.g. No / Someone else")

    def __init__(self, target_member, persona_key="standard"):
        super().__init__()
        self.target_member = target_member
        self.persona_key = persona_key

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        lock_key = f"outbound:{interaction.user.id}:{self.target_member.id}"
        if not acquire_whisper_lock(lock_key):
            return await interaction.followup.send("⚠️ A whisper to this user is currently processing. Please wait.", ephemeral=True)

        try:
            if not whisper_system_active:
                return await interaction.followup.send("⚠️ The Whisper System is currently paused by administration. Transmissions are locked.", ephemeral=True)

            if is_pair_blocked(interaction.user.id, self.target_member.id):
                return await interaction.followup.send("❌ **Transmission Failed:** The recipient has blocked portal transmissions from this connection.", ephemeral=True)

            if await alert_and_check_dm_induction(interaction.client, interaction.user, self.message_content.value, "Initial Outbound Whisper"):
                return await interaction.followup.send("❌ **Transmission Blocked:** Requesting or offering to move conversations to private DMs is forbidden in whispers. Please use the public channels to ask for a DM connection.", ephemeral=True)

            if is_duplicate_payload(interaction.user.id, self.target_member.id, self.message_content.value):
                return await interaction.followup.send("⚠️ Duplicate transmission detected and discarded.", ephemeral=True)

            is_opted_out = False
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS whisper_opt_outs (user_id INTEGER PRIMARY KEY)")
                cursor = conn.execute("SELECT 1 FROM whisper_opt_outs WHERE user_id = ?", (self.target_member.id,))
                if cursor.fetchone():
                    is_opted_out = True
            
            if not is_opted_out:
                backup = load_backup_config()
                if backup and self.target_member.id in backup.get("opt_outs", []):
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute("INSERT OR IGNORE INTO whisper_opt_outs (user_id) VALUES (?)", (self.target_member.id,))
                        conn.commit()
                    is_opted_out = True

            if is_opted_out:
                await log_whisper_activity(interaction.client, interaction.guild, self.target_member, action="blocked / opt-out", sender=interaction.user, content=self.message_content.value)
                return await interaction.followup.send("❌ This member does not accept whispers.", ephemeral=True)

            record_transcript_entry(interaction.user.id, self.target_member.id, self.message_content.value)

            # Build poll payload if present
            poll_id = None
            opt_a = self.poll_option_a.value.strip()
            opt_b = self.poll_option_b.value.strip()
            if opt_a and opt_b:
                poll_id = hashlib.sha256(f"{interaction.user.id}:{datetime.now()}".encode()).hexdigest()[:12]
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS whisper_polls (
                            poll_id TEXT PRIMARY KEY,
                            option_a TEXT,
                            option_b TEXT,
                            votes_a INTEGER DEFAULT 0,
                            votes_b INTEGER DEFAULT 0
                        )
                    """)
                    conn.execute("INSERT INTO whisper_polls (poll_id, option_a, option_b) VALUES (?, ?, ?)", (poll_id, opt_a, opt_b))
                    conn.commit()

            await handle_whisper_logic(
                interaction.client, 
                interaction.user, 
                self.target_member, 
                self.message_content.value, 
                interaction.guild,
                persona_key=self.persona_key,
                poll_id=poll_id,
                opt_a=opt_a,
                opt_b=opt_b
            )
            await interaction.followup.send("✅ Whisper sent anonymously!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Could not send the whisper. The user has DMs closed or has blocked the bot.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
        finally:
            release_whisper_lock(lock_key)

# --- FEATURE 1: CUSTOM PERSONA SELECT VIEW ---
class PersonaSelectView(discord.ui.View):
    def __init__(self, target_member):
        super().__init__(timeout=300)
        self.target_member = target_member

    @discord.ui.select(
        placeholder="🎭 Select your Anonymous Mask/Persona...",
        options=[
            discord.SelectOption(label="Standard Neural", value="standard", description="Default anonymous whisper styling", emoji="💋"),
            discord.SelectOption(label="The Secret Admirer", value="admirer", description="Pink theme, romantic header", emoji="💌"),
            discord.SelectOption(label="The Shadow Observer", value="shadow", description="Dark theme, mysterious header", emoji="👁️"),
            discord.SelectOption(label="The Arch-Rival", value="rival", description="Red theme, competitive header", emoji="⚡"),
            discord.SelectOption(label="The Phantom", value="phantom", description="Cyan theme, spectral header", emoji="👻")
        ]
    )
    async def select_persona(self, interaction: discord.Interaction, select: discord.ui.Select):
        persona_key = select.values[0]
        await interaction.response.send_modal(WhisperMessageModal(self.target_member, persona_key=persona_key))

class UserSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Search and select the receiver...")
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if not whisper_system_active:
            return await interaction.response.send_message("⚠️ The Whisper System is currently paused by administration.", ephemeral=True)
        target = select.values[0]
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or await interaction.guild.fetch_member(target.id)
        
        await interaction.response.send_message("🎭 **Pick an Identity Mask for your transmission:**", view=PersonaSelectView(target), ephemeral=True)

# --- FEATURE 3: GAME PROMPT TRUTH/DARE COMPONENTS ---
class GamePromptModal(discord.ui.Modal):
    custom_prompt = discord.ui.TextInput(label='Custom Game Prompt (Optional)', style=discord.TextStyle.paragraph, required=False, placeholder="Leave blank to use a randomized prompt!")

    def __init__(self, target_member, mode):
        super().__init__(title=f'Send Anonymous {mode}')
        self.target_member = target_member
        self.mode = mode

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        prompt_text = self.custom_prompt.value.strip()
        
        if not prompt_text:
            if self.mode == "Truth":
                prompt_text = random.choice(TRUTH_PROMPTS)
            elif self.mode == "Dare":
                prompt_text = random.choice(DARE_PROMPTS)
            else:
                prompt_text = random.choice(WYR_PROMPTS)

        full_content = f"🎲 **ANONYMOUS {self.mode.upper()} CHALLENGE:**\n> {prompt_text}"

        record_transcript_entry(interaction.user.id, self.target_member.id, full_content)
        await handle_whisper_logic(interaction.client, interaction.user, self.target_member, full_content, interaction.guild, persona_key="rival")
        await interaction.followup.send(f"✅ Anonymous **{self.mode}** challenge delivered successfully!", ephemeral=True)

class GameModeSelectView(discord.ui.View):
    def __init__(self, target_member):
        super().__init__(timeout=300)
        self.target_member = target_member

    @discord.ui.button(label="Truth", style=discord.ButtonStyle.primary, emoji="🔍")
    async def truth_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GamePromptModal(self.target_member, "Truth"))

    @discord.ui.button(label="Dare", style=discord.ButtonStyle.danger, emoji="🔥")
    async def dare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GamePromptModal(self.target_member, "Dare"))

    @discord.ui.button(label="Would You Rather", style=discord.ButtonStyle.secondary, emoji="⚖️")
    async def wyr_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GamePromptModal(self.target_member, "Would You Rather"))

class GameUserSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Select a target player for the Game Prompt...")
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        target = select.values[0]
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or await interaction.guild.fetch_member(target.id)
        await interaction.response.send_message("🎲 **Choose a game prompt mode:**", view=GameModeSelectView(target), ephemeral=True)

class LobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Transmit Secret", style=discord.ButtonStyle.danger, emoji="💋", custom_id="persistent_lobby_btn")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not whisper_system_active:
            return await interaction.response.send_message("⚠️ The Whisper System is currently paused by administration. Transmissions are locked.", ephemeral=True)
        await interaction.response.send_message("Search for the receiver:", view=UserSelectView(), ephemeral=True)

    @discord.ui.button(label="Truth or Dare", style=discord.ButtonStyle.primary, emoji="🎲", custom_id="persistent_lobby_game_btn")
    async def game_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not whisper_system_active:
            return await interaction.response.send_message("⚠️ The Whisper System is currently paused by administration.", ephemeral=True)
        await interaction.response.send_message("Select a member to challenge:", view=GameUserSelectView(), ephemeral=True)

async def handle_whisper_logic(client, sender, target_member, content, guild, persona_key="standard", poll_id=None, opt_a=None, opt_b=None):
    previous_whisper_content = None

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = None
        conn.execute("CREATE TABLE IF NOT EXISTS whisper_sessions (receiver_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER, last_content TEXT)")
        cursor = conn.execute("SELECT last_content, sender_id FROM whisper_sessions WHERE receiver_id = ?", (target_member.id,))
        existing_session = cursor.fetchone()
        
        if existing_session and existing_session[1] == sender.id:
            previous_whisper_content = existing_session[0]

    if not previous_whisper_content and target_member.id in whisper_sessions:
        cached_data = whisper_sessions.get(target_member.id)
        if cached_data and cached_data.get("sender_id") == sender.id:
            previous_whisper_content = cached_data.get("last_content")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = None
        conn.execute("CREATE TABLE IF NOT EXISTS whisper_counts (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)")
        conn.execute("INSERT OR IGNORE INTO whisper_counts (user_id, count) VALUES (?, 0)", (target_member.id,))
        conn.execute("UPDATE whisper_counts SET count = count + 1 WHERE user_id = ?", (target_member.id,))
        
        conn.execute("CREATE TABLE IF NOT EXISTS whisper_sessions (receiver_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER, last_content TEXT)")
        conn.execute("INSERT OR REPLACE INTO whisper_sessions (receiver_id, sender_id, guild_id, last_content) VALUES (?, ?, ?, ?)", (target_member.id, sender.id, guild.id, content))
        conn.commit()
        
    whisper_sessions[target_member.id] = {"sender_id": sender.id, "guild_id": guild.id, "last_content": content}
    
    persona = PERSONA_MASKS.get(persona_key, PERSONA_MASKS["standard"])
    embed = discord.Embed(title=persona["title"], color=persona["color"])
    embed.set_thumbnail(url=persona["icon"])
    
    if previous_whisper_content:
        embed.add_field(name="📜 Last Whisper Transmitted", value=f"> {previous_whisper_content}", inline=False)
        
    embed.add_field(name="✉️ Whisper Content", value=content, inline=False)

    if poll_id and opt_a and opt_b:
        embed.add_field(name="📊 Attached Anonymous Poll", value=f"**A:** {opt_a}\n**B:** {opt_b}\n*(Cast vote via buttons below)*", inline=False)

    view = ReplyView()
    dm_msg = await target_member.send(embed=embed, view=view)

    if poll_id and opt_a and opt_b:
        poll_view = PollVoteView(poll_id, opt_a, opt_b)
        await target_member.send("📊 **Cast your vote on the attached poll:**", view=poll_view)
    
    if dm_msg:
        whisper_sessions[dm_msg.id] = {"sender_id": sender.id, "guild_id": guild.id, "last_content": content}
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_message_sessions (message_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER, last_content TEXT)")
            conn.execute("INSERT OR REPLACE INTO whisper_message_sessions (message_id, sender_id, guild_id, last_content) VALUES (?, ?, ?, ?)", (dm_msg.id, sender.id, guild.id, content))
            conn.commit()
            
    await log_whisper_activity(client, guild, target_member, action="received", sender=sender, content=content)

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Executes during cog loading before on_ready to guarantee database restoration across redeploys."""
        await self.sync_persistence_state()

    async def sync_persistence_state(self):
        global lobby_channel_id, whisper_system_active, guild_lobby_channels, monitored_server_logs
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = None
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_config (key TEXT PRIMARY KEY, value INTEGER)")
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_guild_lobbies (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)")
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_server_logs (guild_id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_counts (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)")
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_opt_outs (user_id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_message_sessions (message_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER, last_content TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_global_state (key TEXT PRIMARY KEY, status INTEGER DEFAULT 1)")
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_sessions (receiver_id INTEGER PRIMARY KEY, sender_id INTEGER, guild_id INTEGER, last_content TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_blocked_pairs (pair_key TEXT PRIMARY KEY, blocked_by INTEGER)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS whisper_polls (
                    poll_id TEXT PRIMARY KEY,
                    option_a TEXT,
                    option_b TEXT,
                    votes_a INTEGER DEFAULT 0,
                    votes_b INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS whisper_poll_voters (
                    poll_id TEXT,
                    voter_id INTEGER,
                    PRIMARY KEY (poll_id, voter_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS whisper_pair_transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_key TEXT,
                    sender_id INTEGER,
                    receiver_id INTEGER,
                    content TEXT,
                    timestamp TEXT
                )
            """)

            try:
                conn.execute("ALTER TABLE whisper_sessions ADD COLUMN last_content TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE whisper_message_sessions ADD COLUMN last_content TEXT")
            except Exception:
                pass

            conn.commit()

        backup = load_backup_config()

        env_lobby = os.getenv("WHISPER_DEFAULT_LOBBY_ID")
        if env_lobby and env_lobby.isdigit():
            lobby_channel_id = int(env_lobby)
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("INSERT OR REPLACE INTO whisper_config (key, value) VALUES ('lobby_channel_id', ?)", (lobby_channel_id,))
                conn.commit()

        env_servers = os.getenv("WHISPER_MONITORED_GUILDS")
        if env_servers:
            for s_id in env_servers.split(","):
                s_id = s_id.strip()
                if s_id.isdigit():
                    monitored_server_logs.add(int(s_id))
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute("INSERT OR IGNORE INTO whisper_server_logs (guild_id) VALUES (?)", (int(s_id),))
                        conn.commit()

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = None

            if backup and backup.get("monitored_servers"):
                for s_id in backup["monitored_servers"]:
                    conn.execute("INSERT OR IGNORE INTO whisper_server_logs (guild_id) VALUES (?)", (s_id,))
            
            if backup and backup.get("opt_outs"):
                for u_id in backup["opt_outs"]:
                    conn.execute("INSERT OR IGNORE INTO whisper_opt_outs (user_id) VALUES (?)", (u_id,))
            
            if backup and backup.get("lobby_channel_id") and not lobby_channel_id:
                conn.execute("INSERT OR REPLACE INTO whisper_config (key, value) VALUES ('lobby_channel_id', ?)", (backup["lobby_channel_id"],))
            
            if backup and backup.get("guild_lobbies"):
                for g_id_str, ch_id in backup["guild_lobbies"].items():
                    conn.execute("INSERT OR REPLACE INTO whisper_guild_lobbies (guild_id, channel_id) VALUES (?, ?)", (int(g_id_str), ch_id))

            conn.commit()
            
            cursor = conn.execute("SELECT guild_id, channel_id FROM whisper_guild_lobbies")
            db_guild_lobbies = {}
            for g_row in cursor.fetchall():
                guild_lobby_channels[g_row[0]] = g_row[1]
                db_guild_lobbies[str(g_row[0])] = g_row[1]

            cursor = conn.execute("SELECT user_id FROM whisper_opt_outs")
            db_opt_outs = [row[0] for row in cursor.fetchall()]

            cursor = conn.execute("SELECT guild_id FROM whisper_server_logs")
            monitored_server_logs = {row[0] for row in cursor.fetchall()}
            db_monitored_servers = list(monitored_server_logs)

            cursor = conn.execute("SELECT value FROM whisper_config WHERE key = 'lobby_channel_id'")
            row = cursor.fetchone()
            if row and row[0] is not None:
                lobby_channel_id = int(row[0])

            cursor = conn.execute("SELECT status FROM whisper_global_state WHERE key = 'bot_active'")
            state_row = cursor.fetchone()
            if state_row:
                whisper_system_active = True if state_row[0] == 1 else False
            elif backup and "system_active" in backup:
                whisper_system_active = backup["system_active"]
                conn.execute("INSERT OR REPLACE INTO whisper_global_state (key, status) VALUES ('bot_active', ?)", (1 if whisper_system_active else 0,))
                conn.commit()

            cursor = conn.execute("SELECT receiver_id, sender_id, guild_id, last_content FROM whisper_sessions")
            for session_row in cursor.fetchall():
                whisper_sessions[session_row[0]] = {"sender_id": session_row[1], "guild_id": session_row[2], "last_content": session_row[3]}
            
            cursor = conn.execute("SELECT message_id, sender_id, guild_id, last_content FROM whisper_message_sessions")
            for msg_row in cursor.fetchall():
                whisper_sessions[msg_row[0]] = {"sender_id": msg_row[1], "guild_id": msg_row[2], "last_content": msg_row[3]}

            full_sync_data = {
                "lobby_channel_id": lobby_channel_id,
                "guild_lobbies": db_guild_lobbies,
                "monitored_servers": db_monitored_servers,
                "opt_outs": db_opt_outs,
                "system_active": whisper_system_active
            }
            await async_save_backup_config("full_sync", full_sync_data)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.sync_persistence_state()
        self.bot.add_view(LobbyView())
        self.bot.add_view(ReplyView())

    @commands.command(name="togglewhisperbot")
    @commands.is_owner()
    async def toggle_global_whisper_system(self, ctx):
        global whisper_system_active
        whisper_system_active = not whisper_system_active
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_global_state (key TEXT PRIMARY KEY, status INTEGER DEFAULT 1)")
            conn.execute("INSERT OR REPLACE INTO whisper_global_state (key, status) VALUES ('bot_active', ?)", (1 if whisper_system_active else 0,))
            conn.commit()
            
        await async_save_backup_config("system_active", whisper_system_active)
        
        if whisper_system_active:
            await ctx.send("✅ **System Operational:** The Whisper System has been completely resumed.")
        else:
            await ctx.send("⏸️ **System Paused:** The Whisper System has been temporarily locked down.")

    @commands.command(name="nowhisper")
    async def toggle_whisper_opt_out(self, ctx):
        is_opted_out = False
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_opt_outs (user_id INTEGER PRIMARY KEY)")
            cursor = conn.execute("SELECT 1 FROM whisper_opt_outs WHERE user_id = ?", (ctx.author.id,))
            if cursor.fetchone():
                is_opted_out = True
                
        if is_opted_out:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("DELETE FROM whisper_opt_outs WHERE user_id = ?", (ctx.author.id,))
                conn.commit()
            await async_save_backup_config("remove_opt_out", ctx.author.id)
            await ctx.send("✅ **Whisper System Activated:** You are now open to receive anonymous whispers again.")
        else:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("INSERT OR IGNORE INTO whisper_opt_outs (user_id) VALUES (?)", (ctx.author.id,))
                conn.commit()
            await async_save_backup_config("add_opt_out", ctx.author.id)
            await ctx.send("❌ **Whisper System Deactivated:** You have successfully locked your portal.")

    @commands.command(name="nomorewhispers")
    async def opt_out_whispers_explicit(self, ctx):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_opt_outs (user_id INTEGER PRIMARY KEY)")
            conn.execute("INSERT OR IGNORE INTO whisper_opt_outs (user_id) VALUES (?)", (ctx.author.id,))
            conn.commit()
        await async_save_backup_config("add_opt_out", ctx.author.id)
        await ctx.send("❌ **Whisper System Deactivated:** You have successfully locked your portal.")

    @commands.command(name="backtowhisper")
    async def opt_in_whispers_explicit(self, ctx):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_opt_outs (user_id INTEGER PRIMARY KEY)")
            conn.execute("DELETE FROM whisper_opt_outs WHERE user_id = ?", (ctx.author.id,))
            conn.commit()
        await async_save_backup_config("remove_opt_out", ctx.author.id)
        await ctx.send("✅ **Whisper System Activated:** You are now open to receive anonymous whispers again.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setwhisper(self, ctx, channel: discord.TextChannel = None):
        global lobby_channel_id, guild_lobby_channels
        target_channel = channel or ctx.channel
        
        if ctx.guild:
            guild_lobby_channels[ctx.guild.id] = target_channel.id
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS whisper_guild_lobbies (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)")
                conn.execute("INSERT OR REPLACE INTO whisper_guild_lobbies (guild_id, channel_id) VALUES (?, ?)", (ctx.guild.id, target_channel.id))
                conn.commit()
            await async_save_backup_config("set_guild_lobby", target_channel.id, ctx.guild.id)
        
        lobby_channel_id = target_channel.id
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_config (key TEXT PRIMARY KEY, value INTEGER)")
            conn.execute("INSERT OR REPLACE INTO whisper_config (key, value) VALUES ('lobby_channel_id', ?)", (target_channel.id,))
            conn.commit()
        await async_save_backup_config("lobby_channel_id", target_channel.id)
        await ctx.send(f"✅ Whisper lobby for **{ctx.guild.name if ctx.guild else 'this server'}** set to {target_channel.mention}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def whisperserverset(self, ctx, server_id: int = None):
        global monitored_server_logs
        target_server_id = server_id or (ctx.guild.id if ctx.guild else None)
        
        if not target_server_id:
            return await ctx.send("❌ Please provide a valid Server/Guild ID.")
            
        monitored_server_logs.add(target_server_id)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_server_logs (guild_id INTEGER PRIMARY KEY)")
            conn.execute("INSERT OR REPLACE INTO whisper_server_logs (guild_id) VALUES (?)", (target_server_id,))
            conn.commit()
            
        await async_save_backup_config("add_server", target_server_id)
        await ctx.send(f"✅ Whisper audit logs for server ID `{target_server_id}` are now forwarded to owner DMs.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def openwhisper(self, ctx):
        embed = discord.Embed(
            title="💋 NEURAL WHISPER LOBBY 💋", 
            description="### ⛓️ PRIVATE HANDSHAKE TERMINAL\n"
                        "Welcome to the shadows, darling. Want to confess a secret, leave a bite mark, or drive someone crazy entirely undetected?\n\n"
                        "• **Complete Anonymity:** The server records won't save your footprint.\n"
                        "• **Direct Sync:** Your target receives a secure panel directly in their private box.\n"
                        "• **Masks & Games:** Custom Persona Masks, Anonymous Games, and Quick Polls available!\n\n"
                        "🔒 **Opt-Out Control:** Don't want whispers? Type `!nomorewhispers` to lock your portal. Use `!backtowhisper` anytime to reactivate.\n\n"
                        "*Go ahead... hit the switch below and leave them wondering all night.*", 
            color=0xE0115F
        )
        embed.set_footer(text="Encrypted Connection Online • Proceed at your own risk.")
        await ctx.send(embed=embed, view=LobbyView())

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))
