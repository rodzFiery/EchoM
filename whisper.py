import discord

# Maps {receiver_id: sender_id}
whisper_sessions = {}
# Maps {guild_id: True}
whisper_log_destinations = {} 
lobby_channel_id = None
BOT_OWNER_ID = 0 # REPLACE WITH YOUR DISCORD USER ID

async def log_whisper_activity(guild, target_member, action="received"):
    # 1. Forward to Owner DM if the server is registered
    if guild.id in whisper_log_destinations:
        owner = guild.get_member(BOT_OWNER_ID) or await guild.fetch_member(BOT_OWNER_ID)
        if owner:
            embed = discord.Embed(title=f"Whisper Audit: {guild.name}", description=f"{target_member.mention} has {action} a whisper.", color=discord.Color.red())
            await owner.send(embed=embed)

    # 2. Log to the Lobby Channel
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

async def handle_whisper(message, target_member: discord.Member):
    whisper_sessions[target_member.id] = message.author.id
    embed = discord.Embed(title="You received an Anonymous Whisper", description=message.content, color=discord.Color.purple())
    embed.set_thumbnail(url=target_member.display_avatar.url)
    embed.set_footer(text="Your identity remains hidden to the sender.")
    await target_member.send(embed=embed, view=ReplyView())
    await log_whisper_activity(message.guild, target_member, action="received")
