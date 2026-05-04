import discord
from discord.ext import commands
import random
import io
import aiohttp
import sys
import json
import os
import asyncio # ADDED: Required for thread-safe processing
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageOps, ImageFilter

# --- PERSISTENT VIEW CLASSES (MOVED OUTSIDE FOR STABILITY) ---

class InitialView(discord.ui.View):
    def __init__(self, requester_id=None, target_id=None):
        super().__init__(timeout=None)
        self.requester_id = requester_id
        self.target_id = target_id

    @discord.ui.button(label="Ask to DM", style=discord.ButtonStyle.primary, emoji="📩", custom_id="ask_dm_init_v2")
    async def dm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # If IDs aren't in memory (after restart), we extract from mentions in the embed
        req_id = self.requester_id or int(interaction.message.embeds[0].description.split('<@')[1].split('>')[0])
        tar_id = self.target_id or int(interaction.message.embeds[0].description.split('signaling <@')[1].split('>')[0])

        if interaction.user.id != req_id: 
            return await interaction.response.send_message("❌ This is not your request to configure, asset.", ephemeral=True)
        
        options = [
            discord.SelectOption(label="SFW", emoji="🛡️"),
            discord.SelectOption(label="NSFW", emoji="🔞"),
            discord.SelectOption(label="Flirting", emoji="🫦"),
            discord.SelectOption(label="Problem Solving", emoji="🧠"),
            discord.SelectOption(label="Casual Chat only", emoji="💬"),
            discord.SelectOption(label="Friends only", emoji="🤝"),
            discord.SelectOption(label="Dating vibes", emoji="💘"),
            discord.SelectOption(label="Open to Anything", emoji="🔞")
        ]
        
        select = discord.ui.Select(placeholder="Nature of the DM (Choose up to 3)", min_values=1, max_values=3, options=options, custom_id="ask_dm_select_v2")

        async def select_callback(sel_interaction: discord.Interaction):
            if sel_interaction.user.id != req_id: 
                return await sel_interaction.response.send_message("❌ Hands off.", ephemeral=True)
            
            main_mod = sys.modules['__main__']
            intent_display = " | ".join([f"**{val}**" for val in select.values])
            target_user = interaction.guild.get_member(tar_id)
            requester_user = interaction.guild.get_member(req_id)

            final_embed = main_mod.fiery_embed(" 📩 INCOMING DM REQUEST", 
                f"{target_user.mention}, a formal petition to enter your private space has been filed by {requester_user.mention}.\n\n"
                f"### 🫦 INTENT OF CONTACT:\n> {intent_display}\n\n"
                f"** **")
            
            final_embed.set_thumbnail(url=requester_user.display_avatar.url)
            final_embed.color = 0x00BFFF 

            view = RecipientView(req_id, tar_id)
            await sel_interaction.response.send_message(content=target_user.mention, embed=final_embed, view=view)

        select.callback = select_callback
        dm_view = discord.ui.View(timeout=None)
        dm_view.add_item(select)
        await interaction.response.send_message("🫦 **Define the nature of your entry:**", view=dm_view, ephemeral=True)

    @discord.ui.button(label="Ask to Play", style=discord.ButtonStyle.danger, emoji="🫦", custom_id="ask_play_init_v2")
    async def play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        req_id = self.requester_id or int(interaction.message.embeds[0].description.split('<@')[1].split('>')[0])
        tar_id = self.target_id or int(interaction.message.embeds[0].description.split('signaling <@')[1].split('>')[0])

        if interaction.user.id != req_id: 
            return await interaction.response.send_message("❌ Access denied.", ephemeral=True)
        
        main_mod = sys.modules['__main__']
        target_user = interaction.guild.get_member(tar_id)
        requester_user = interaction.guild.get_member(req_id)

        play_embed = main_mod.fiery_embed("🔞 SEX-BOT TRIAL REQUEST 🔞", 
            f"{target_user.mention}, {requester_user.mention} wants to initiate a deep-sync session.\n\n"
            f"**Will you submit?**")
        
        view = PlayView(req_id, tar_id)
        await interaction.response.send_message(content=target_user.mention, embed=play_embed, view=view)

class RecipientView(discord.ui.View):
    def __init__(self, req_id, tar_id):
        super().__init__(timeout=None)
        self.req_id = req_id
        self.tar_id = tar_id

    @discord.ui.button(label="Accept DM", style=discord.ButtonStyle.success, emoji="🫦", custom_id="ask_dm_accept_v2")
    async def accept(self, inter: discord.Interaction, btn: discord.ui.Button):
        if inter.user.id != self.tar_id: 
            return await inter.response.send_message("❌ Access denied.", ephemeral=True)
        main_mod = sys.modules['__main__']
        success_emb = main_mod.fiery_embed("💖 DM ACCEPTED", f"**ACCEPTED.** <@{self.req_id}>, request accepted by <@{self.tar_id}>.")
        await inter.response.send_message(content=f"<@{self.req_id}>", embed=success_emb)

    @discord.ui.button(label="Reject Advancement", style=discord.ButtonStyle.danger, emoji="❌", custom_id="ask_dm_reject_v2")
    async def deny(self, inter: discord.Interaction, btn: discord.ui.Button):
        if inter.user.id != self.tar_id: 
            return await inter.response.send_message("❌ Access denied.", ephemeral=True)
        main_mod = sys.modules['__main__']
        fail_emb = main_mod.fiery_embed("❌ REQUEST DENIED", f"**DENIED.** <@{self.tar_id}> has rejected your advances.")
        await inter.response.send_message(content=f"<@{self.req_id}>", embed=fail_emb)

class PlayView(discord.ui.View):
    def __init__(self, req_id, tar_id):
        super().__init__(timeout=None)
        self.req_id = req_id
        self.tar_id = tar_id

    @discord.ui.button(label="Accept Sync", style=discord.ButtonStyle.success, emoji="🔥", custom_id="ask_play_accept_v2")
    async def accept_play(self, inter: discord.Interaction, btn: discord.ui.Button):
        if inter.user.id != self.tar_id: 
            return await inter.response.send_message("❌ Access denied.", ephemeral=True)
        await inter.response.send_message(f"🔞 **SYNC INITIALIZED.** <@{self.tar_id}> is ready. <@{self.req_id}>, begin.")

    @discord.ui.button(label="Abort Sync", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="ask_play_deny_v2")
    async def deny_play(self, inter: discord.Interaction, btn: discord.ui.Button):
        if inter.user.id != self.tar_id: 
            return await inter.response.send_message("❌ Access denied.", ephemeral=True)
        await inter.response.send_message(f"🔒 **SYNC ABORTED.** <@{self.tar_id}> has locked their gate.")

# --- COG CLASS ---

class DungeonAsk(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.AUDIT_CHANNEL_ID = getattr(sys.modules['__main__'], "AUDIT_CHANNEL_ID", 1482071248631758865)

    async def create_ask_lobby(self, u1_url, u2_url, title="DM REQUEST"):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(u1_url) as r1, session.get(u2_url) as r2:
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())

            def process():
                canvas_width, canvas_height = 1200, 600
                canvas = Image.open("askdm.jpg").convert("RGBA").resize((canvas_width, canvas_height)) if os.path.exists("askdm.jpg") else Image.new("RGBA", (canvas_width, canvas_height), (15, 0, 8, 255))
                draw = ImageDraw.Draw(canvas)
                av_size = 350
                av1 = Image.open(p1_data).convert("RGBA").resize((av_size, av_size))
                av2 = Image.open(p2_data).convert("RGBA").resize((av_size, av_size))
                canvas.paste(av1, (100, 120), av1)
                canvas.paste(av2, (750, 120), av2)
                buf = io.BytesIO()
                canvas.save(buf, format="PNG")
                buf.seek(0)
                return buf
            
            return await asyncio.to_thread(process)
        except Exception as e:
            print(f"Visual Error: {e}")
            return None

    @commands.command(name="ask")
    async def ask(self, ctx, member: discord.Member):
        """Initiates a formal request."""
        if member.id == ctx.author.id:
            return await ctx.send("❌ You can't ask to DM yourself.")

        main_mod = sys.modules['__main__']
        img = await self.create_ask_lobby(ctx.author.display_avatar.url, member.display_avatar.url, "")
        file = discord.File(img, filename="ask.png")
        
        embed = main_mod.fiery_embed("🔞 ASK TO DM ALERT 🔞", 
            f"{ctx.author.mention} is signaling {member.mention}.\n\n"
            f"**Select the nature of your request below:**")
        embed.set_image(url="attachment://ask.png")
        
        view = InitialView(ctx.author.id, member.id)
        await ctx.send(file=file, embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(DungeonAsk(bot))
    # Register views for persistence after setup
    bot.add_view(InitialView())
    bot.add_view(RecipientView(0, 0))
    bot.add_view(PlayView(0, 0))
    print("✅ LOG: Ask Extension is ONLINE.")
