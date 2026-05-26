import discord
from discord.ext import commands

# Maps {receiver_id: sender_id}
whisper_sessions = {}
# Maps {guild_id: True}
whisper_log_destinations = {} 
lobby_channel_id = None
BOT_OWNER_ID = 0 # REPLACE WITH YOUR DISCORD USER ID

async def log_whisper_activity(guild, target_member, action="received"):
    if guild.id in whisper_log_destinations:
        owner = guild.get_member(BOT_OWNER_ID) or await guild.fetch_member(BOT_OWNER_ID)
        if owner:
            embed = discord.Embed(title=f"Whisper Audit: {guild.name}", description=f"{target_member.mention} has {action} a whisper.", color=discord.Color.red())
            await owner.send(embed=embed)

    lobby_channel = guild.get_channel(lobby_channel_id)
    if lobby_channel:
        color = discord.Color.blue() if action == "received" else discord.Color.green()
        action_text = "received a new whisper" if action == "received" else "replied to a whisper"
        embed = discord.Embed(title="Anonymous Whisper Activity", description=f"{target_member.mention} {action_text}.", color=color)
        embed.set_thumbnail(url=target_member.display_avatar.url)
        await lobby_channel.send(embed=embed)

class ReplyModal(discord.ui.Modal, title='Reply to Anonymous Whisper'):
    reply_content = discord.ui.TextInput(label='Your Reply', style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        original_sender_id = whisper_sessions.get(interaction.user.id)
        if original_sender_id:
            sender = interaction.guild.get_member(original_sender_id)
            if sender:
                embed = discord.Embed(title="Anonymous Reply Received", description=self.reply_content.value, color=discord.Color.green())
                await sender.send(embed=embed)
                await log_whisper_activity(interaction.guild, interaction.user, action="replied to")
                await interaction.response.send_message("Reply sent anonymously!", ephemeral=True)

class ReplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reply", style=discord.ButtonStyle.primary, custom_id="persistent_reply_btn")
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReplyModal())

class WhisperSelectModal(discord.ui.Modal, title='Send Anonymous Whisper'):
    target_select = discord.ui.Select(placeholder='Select a receiver', min_values=1, max_values=1)
    message_content = discord.ui.TextInput(label='Your Whisper', style=discord.TextStyle.paragraph, required=True)

    def __init__(self, members):
        super().__init__()
        for m in members[:25]:
            self.target_select.add_option(label=m.display_name, value=str(m.id))
        self.add_item(self.target_select)

    async def on_submit(self, interaction: discord.Interaction):
        target = interaction.guild.get_member(int(self.target_select.values[0]))
        if target:
            await handle_whisper_logic(interaction.user, target, self.message_content.value, interaction.guild)
            await interaction.response.send_message("✅ Whisper sent anonymously!", ephemeral=True)

class LobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Send Whisper", style=discord.ButtonStyle.primary, custom_id="persistent_lobby_btn")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        members = [m for m in interaction.guild.members if not m.bot]
        await interaction.response.send_modal(WhisperSelectModal(members))

async def handle_whisper_logic(sender, target_member, content, guild):
    whisper_sessions[target_member.id] = sender.id
    embed = discord.Embed(title="You received an Anonymous Whisper", description=content, color=discord.Color.purple())
    embed.set_thumbnail(url=target_member.display_avatar.url)
    embed.set_footer(text="Your identity remains hidden to the sender.")
    await target_member.send(embed=embed, view=ReplyView())
    await log_whisper_activity(guild, target_member, action="received")

class WhisperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(ReplyView())
        self.bot.add_view(LobbyView())

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setwhisper(self, ctx, channel: discord.TextChannel):
        global lobby_channel_id
        lobby_channel_id = channel.id
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
