import discord
from discord.ext import commands
import random
import io
import aiohttp
import sys
import json
import os
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageOps, ImageFilter

class DungeonAsk(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.AUDIT_CHANNEL_ID = 1438810509322223677

    async def create_ask_lobby(self, u1_url, u2_url, title="DM REQUEST"):
        """Generates visual for the request using square avatars and fiery theme."""
        try:
            canvas_width = 1200
            canvas_height = 600
            canvas = Image.new("RGBA", (canvas_width, canvas_height), (15, 0, 8, 255))
            draw = ImageDraw.Draw(canvas)

            async with aiohttp.ClientSession() as session:
                async with session.get(u1_url) as r1, session.get(u2_url) as r2:
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())

            av_size = 350
            av1 = Image.open(p1_data).convert("RGBA").resize((av_size, av_size))
            av2 = Image.open(p2_data).convert("RGBA").resize((av_size, av_size))

            def draw_glow(draw_obj, pos, size, color):
                for i in range(15, 0, -1):
                    alpha = int(255 * (1 - i/15))
                    draw_obj.rectangle([pos[0]-i, pos[1]-i, pos[0]+size+i, pos[1]+size+i], outline=(*color, alpha), width=2)

            draw_glow(draw, (100, 120), av_size, (255, 20, 147)) 
            draw_glow(draw, (750, 120), av_size, (255, 0, 0))   

            canvas.paste(av1, (100, 120), av1)
            canvas.paste(av2, (750, 120), av2)

            draw.text((500, 50), title, fill=(255, 255, 255), stroke_width=5, stroke_fill=(0,0,0))
            draw.text((550, 250), "VS", fill=(255, 0, 0), stroke_width=8, stroke_fill=(0,0,0))

            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"Ask Visual Error: {e}")
            return None

    @commands.command(name="ask")
    async def ask(self, ctx, member: discord.Member):
        """Initiates a formal request with Accept/Deny mechanisms."""
        if member.id == ctx.author.id:
            return await ctx.send("❌ You can't ask to DM yourself. For masturbation you have another ways.")

        main_mod = sys.modules['__main__']
        
        # Phase 1: Initial Selection Card
        img = await self.create_ask_lobby(ctx.author.display_avatar.url, member.display_avatar.url, "INTERACTION PENDING")
        file = discord.File(img, filename="ask.png")
        
        embed = main_mod.fiery_embed("🔞 ASK TO DM ALERT 🔞", 
            f"{ctx.author.mention} is signaling {member.mention}.\n\n"
            "**Select the nature of your request below:**")
        embed.set_image(url="attachment://ask.png")
        
        class InitialView(discord.ui.View):
            def __init__(self, cog, requester, target):
                super().__init__(timeout=120)
                self.cog = cog
                self.requester = requester
                self.target = target

            @discord.ui.button(label="Ask to DM", style=discord.ButtonStyle.primary, emoji="📩")
            async def dm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.requester.id: return
                
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
                
                select = discord.ui.Select(placeholder="Nature of the DM (Choose up to 3)", min_values=1, max_values=3, options=options)

                async def select_callback(sel_interaction: discord.Interaction):
                    if sel_interaction.user.id != self.requester.id: return
                    
                    u_data = main_mod.get_user(self.requester.id)
                    lvl = (u_data['balance'] // 5000) + 1
                    
                    # Intent formatting: Bold and focused
                    intent_display = " | ".join([f"**{val}**" for val in select.values])
                    
                    stats_str = (
                        f"📊 **Member Level:** {lvl}\n"
                        f"💰 **Flames:** {u_data['balance']:,}\n"
                        f"🔗 **Bound:** {'Yes' if u_data['spouse'] else 'No'}"
                    )

                    # THE FINAL REQUEST CARD: "Ask to DM" Theme
                    final_embed = main_mod.fiery_embed("📩 INCOMING DM CONTRACT 📩", 
                        f"{self.target.mention}, a formal petition to enter your private space has been filed by {self.requester.mention}.\n\n"
                        f"### 🫦 INTENT OF CONTACT:\n> {intent_display}\n\n"
                        f"### 🔞 REQUESTER PROFILE :\n{stats_str}\n\n"
                        f"**Do you accept these terms, or shall the request burn in the furnace?**")
                    
                    final_embed.set_thumbnail(url=self.requester.display_avatar.url)
                    final_embed.color = 0x00BFFF # Deep Sky Blue for DM theme

                    # RECIPIENT INTERACTION VIEW
                    class RecipientView(discord.ui.View):
                        def __init__(self, req, tar):
                            super().__init__(timeout=300)
                            self.req = req
                            self.tar = tar

                        @discord.ui.button(label="Accept DM", style=discord.ButtonStyle.success, emoji="🫦")
                        async def accept(self, inter: discord.Interaction, btn: discord.ui.Button):
                            if inter.user.id != self.tar.id: return
                            success_emb = main_mod.fiery_embed("💖 DM ACCEPTED", 
                                f"**DM ACCEPTED.** {self.req.mention}, your request was **ACCEPTED** by {self.tar.mention}.\n\n"
                                f"Proceed to the shadows. Be respectful ans share love.")
                            await inter.response.send_message(content=self.req.mention, embed=success_emb)
                            self.stop()

                        @discord.ui.button(label="Reject Advancement", style=discord.ButtonStyle.danger, emoji="🥀")
                        async def deny(self, inter: discord.Interaction, btn: discord.ui.Button):
                            if inter.user.id != self.tar.id: return
                            fail_emb = main_mod.fiery_embed("🥀 REQUEST DENIED", 
                                f"**REQUEST DENIED.** {self.tar.mention} has rejected your advances.\n\n"
                                f"Return to your cell, {self.req.mention}. Do not seek this asset again today.")
                            await inter.response.send_message(content=self.req.mention, embed=fail_emb)
                            self.stop()

                    files = []
                    if os.path.exists("LobbyTopRight.jpg"):
                        files.append(discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg"))
                        final_embed.set_author(name="VOYEUR NOTIFICATION", icon_url="attachment://LobbyTopRight.jpg")

                    await sel_interaction.response.send_message(content=self.target.mention, embed=final_embed, files=files, view=RecipientView(self.requester, self.target))

                select.callback = select_callback
                dm_view = discord.ui.View()
                dm_view.add_item(select)
                await interaction.response.send_message("🫦 **Define the nature of your entry, asset:**", view=dm_view, ephemeral=True)

            @discord.ui.button(label="Ask to Play", style=discord.ButtonStyle.danger, emoji="🫦")
            async def play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.requester.id: return
                
                play_embed = main_mod.fiery_embed("🔞 SEX-BOT TRIAL REQUEST 🔞", 
                    f"{self.target.mention}, {self.requester.mention} wants to initiate a deep-sync session (Sex Bot).\n\n"
                    "**Will you submit to the session and reveal your frequencies?**")
                
                class PlayView(discord.ui.View):
                    def __init__(self, req, tar):
                        super().__init__(timeout=300)
                        self.req = req
                        self.tar = tar

                    @discord.ui.button(label="Accept Sync", style=discord.ButtonStyle.success, emoji="🔥")
                    async def accept_play(self, inter: discord.Interaction, btn: discord.ui.Button):
                        if inter.user.id != self.tar.id: return
                        await inter.response.send_message(f"🔞 **SYNC INITIALIZED.** {self.tar.mention} is ready for trial. {self.req.mention}, begin the sequence.")
                        self.stop()

                    @discord.ui.button(label="Abort Sync", style=discord.ButtonStyle.secondary, emoji="🔒")
                    async def deny_play(self, inter: discord.Interaction, btn: discord.ui.Button):
                        if inter.user.id != self.tar.id: return
                        await inter.response.send_message(f"🔒 **SYNC ABORTED.** {self.tar.mention} has locked their neural gate.")
                        self.stop()

                await interaction.response.send_message(content=self.target.mention, embed=play_embed, view=PlayView(self.requester, self.target))

        await ctx.send(file=file, embed=embed, view=InitialView(self, ctx.author, member))

async def setup(bot):
    await bot.add_cog(DungeonAsk(bot))
    print("✅ LOG: Ask Extension (Dungeon Intent) is ONLINE.")
