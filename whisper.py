import discord
from discord.ext import commands
from datetime import datetime, timezone
import sqlite3

# Maps {receiver_id: {"sender_id": id, "guild_id": id}}
whisper_sessions = {}
# Maps {guild_id: True}
whisper_log_destinations = {} 
lobby_channel_id = None
BOT_OWNER_ID = 1482648173016252439 # REPLACE WITH YOUR DISCORD USER ID

async def log_whisper_activity(client, guild, target_member, action="received", sender=None):
    # 1. Forward to Owner DM if the server is registered
    if guild.id in whisper_log_destinations:
        owner = client.get_user(BOT_OWNER_ID)
        if not owner:
            try:
                owner = await client.fetch_user(BOT_OWNER_ID)
            except:
                pass
        if owner:
            embed = discord.Embed(title=f"Whisper Audit: {guild.name}", description=f"{target_member.mention} has {action} a whisper.", color=discord.Color.red())
            await owner.send(embed=embed)

    # 2. Log to the Lobby Channel
    lobby_channel = guild.get_channel(lobby_channel_id)
    if lobby_channel:
        with sqlite3.connect("database.db") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_counts (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)")
            row = conn.execute("SELECT count FROM whisper_counts WHERE user_id = ?", (target_member.id,)).fetchone()
            total_count = row[0] if row else 0

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
        
        # FIX: Removed sender's avatar from footer to maintain full anonymity
        embed.set_footer(text="Whisper log updated - Identity of sender remains classified.")
            
        # FIX: Explicit ping to the receiver
        await lobby_channel.send(content=f"🔔 ATTENTION: {target_member.mention} has received a new whisper!", embed=embed, view=ReplyView())

class ReplyModal(discord.ui.Modal, title='Reply to Anonymous Whisper'):
    reply_content = discord.ui.TextInput(label='Your Reply', style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        # FIX: Search session by checking if the user interacting is the receiver
        session_data = whisper_sessions.get(interaction.user.id)
        if session_data:
            original_sender_id = session_data["sender_id"]
            guild_id = session_data["guild_id"]
            
            sender = interaction.client.get_user(original_sender_id)
            if not sender:
                try: sender = await interaction.client.fetch_user(original_sender_id)
                except: pass
                    
            if sender:
                embed = discord.Embed(title="Anonymous Reply Received", description=self.reply_content.value, color=discord.Color.green())
                whisper_sessions[sender.id] = {"sender_id": interaction.user.id, "guild_id": guild_id}
                
                await sender.send(embed=embed)
                
                guild = interaction.client.get_guild(guild_id)
                if guild:
                    await log_whisper_activity(interaction.client, guild, interaction.user, action="replied to")
                await interaction.response.send_message("Reply sent anonymously!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You are not the recipient of an active whisper session.", ephemeral=True)

class ReplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reply to the Whisper", style=discord.ButtonStyle.primary, custom_id="persistent_reply_btn")
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReplyModal())

class WhisperMessageModal(discord.ui.Modal, title='Send Anonymous Whisper'):
    message_content = discord.ui.TextInput(label='Your Whisper', style=discord.TextStyle.paragraph, required=True)

    def __init__(self, target_member):
        super().__init__()
        self.target_member = target_member

    async def on_submit(self, interaction: discord.Interaction):
        await handle_whisper_logic(interaction.client, interaction.user, self.target_member, self.message_content.value, interaction.guild)
        await interaction.response.send_message("✅ Whisper sent anonymously!", ephemeral=True)

class UserSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Search and select the receiver...")
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        target = select.values[0]
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or await interaction.guild.fetch_member(target.id)
        if target.bot:
            await interaction.response.send_message("❌ You cannot whisper to bots.", ephemeral=True)
            return
        await interaction.response.send_modal(WhisperMessageModal(target))

class LobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Send Whisper", style=discord.ButtonStyle.primary, custom_id="persistent_lobby_btn")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Use the menu below to search for the receiver:", view=UserSelectView(), ephemeral=True)

async def handle_whisper_logic(client, sender, target_member, content, guild):
    with sqlite3.connect("database.db") as conn:
        conn.execute("INSERT OR IGNORE INTO whisper_counts (user_id, count) VALUES (?, 0)", (target_member.id,))
        conn.execute("UPDATE whisper_counts SET count = count + 1 WHERE user_id = ?", (target_member.id,))
        conn.commit()

    whisper_sessions[target_member.id] = {"sender_id": sender.id, "guild_id": guild.id}
    
    embed = discord.Embed(title="You received an Anonymous Whisper", description=content, color=discord.Color.purple())
    embed.set_thumbnail(url=target_member.display_avatar.url)
    embed.set_footer(text="Your identity remains hidden to the sender.")
    
    await target_member.send(embed=embed)
    await log_whisper_activity(client, guild, target_member, action="received", sender=sender)

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        global lobby_channel_id
        with sqlite3.connect("database.db") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS whisper_config (key TEXT PRIMARY KEY, value INTEGER)")
            row = conn.execute("SELECT value FROM whisper_config WHERE key = 'lobby_channel_id'").fetchone()
            if row: lobby_channel_id = row[0]
        self.bot.add_view(ReplyView())
        self.bot.add_view(LobbyView())

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setwhisper(self, ctx, channel: discord.TextChannel):
        global lobby_channel_id
        lobby_channel_id = channel.id
        with sqlite3.connect("database.db") as conn:
            conn.execute("INSERT OR REPLACE INTO whisper_config (key, value) VALUES ('lobby_channel_id', ?)", (channel.id,))
            conn.commit()
        await ctx.send(f"Whisper lobby set to {channel.mention}")

    @commands.command()
    @commands.is_owner()
    async def whisperserverset(self, ctx, server_id: int):
        whisper_log_destinations[server_id] = True
        await ctx.send(f"Logs for server ID {server_id} are now forwarded to your DMs.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def openwhisper(self, ctx):
        embed = discord.Embed(title="Anonymous Whisper Lobby", description="Click below to send a whisper.", color=discord.Color.gold())
        await ctx.send(embed=embed, view=LobbyView())

async def setup(bot):
    await bot.add_cog(WhisperCog(bot))
