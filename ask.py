import discord
from discord.ext import commands
import random
import io
import aiohttp
import sys
import json
import os
import asyncio
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageOps, ImageFilter

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
                canvas_width = 1200
                canvas_height = 600
                if os.path.exists("askdm.jpg"):
                    canvas = Image.open("askdm.jpg").convert("RGBA").resize((canvas_width, canvas_height))
                else:
                    canvas = Image.new("RGBA", (canvas_width, canvas_height), (15, 0, 8, 255))
                
                draw = ImageDraw.Draw(canvas)
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

                buf = io.BytesIO()
                canvas.save(buf, format="PNG")
                buf.seek(0)
                return buf
            
            return await asyncio.to_thread(process)
        except Exception as e:
            print(f"Ask Visual Error: {e}")
            return None

    @commands.command(name="ask")
    async def ask(self, ctx, member: discord.Member):
        if member.id == ctx.author.id:
            return await ctx.send("❌ You can't ask to DM yourself.")

        main_mod = sys.modules['__main__']
        img = await self.create_ask_lobby(ctx.author.display_avatar.url, member.display_avatar.url, "")
        file = discord.File(img, filename="ask.png")
        
        embed = main_mod.fiery_embed("🔞 ASK TO DM ALERT 🔞", 
            f"{ctx.author.mention} is signaling {member.mention}.\n\n"
            "**Select the nature of your request below:**")
        embed.set_image(url="attachment://ask.png")
        
        class InitialView(discord.ui.View):
            def __init__(self, cog, requester, target, original_embed):
                super().__init__(timeout=120)
                self.cog = cog
                self.requester = requester
                self.target = target
                self.embed = original_embed

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
                    
                    intent_display = " | ".join([f"**{val}**" for val in select.values])
                    
                    self.embed.title = "📩 INCOMING DM REQUEST"
                    self.embed.description = (f"{self.target.mention}, a formal petition to enter your private space has been filed by {self.requester.mention}.\n\n"
                                             f"### 🫦 INTENT OF CONTACT:\n> {intent_display}")
                    self.embed.set_thumbnail(url=self.requester.display_avatar.url)
                    self.embed.color = 0x00BFFF 

                    class RecipientView(discord.ui.View):
                        def __init__(self, req, tar, emb):
                            super().__init__(timeout=300)
                            self.req = req
                            self.tar = tar
                            self.emb = emb

                        @discord.ui.button(label="Accept DM", style=discord.ButtonStyle.success, emoji="🫦")
                        async def accept(self, inter: discord.Interaction, btn: discord.ui.Button):
                            if inter.user.id != self.tar.id: return
                            self.emb.title = "💖 DM ACCEPTED"
                            self.emb.description = f"**DM ACCEPTED.** {self.req.mention}, your request was **ACCEPTED** by {self.tar.mention}.\n\nProceed to the shadows."
                            self.emb.color = discord.Color.green()
                            await inter.response.edit_message(embed=self.emb, view=None)
                            self.stop()

                        @discord.ui.button(label="Reject Advancement", style=discord.ButtonStyle.danger, emoji="❌")
                        async def deny(self, inter: discord.Interaction, btn: discord.ui.Button):
                            if inter.user.id != self.tar.id: return
                            self.emb.title = "❌ REQUEST DENIED"
                            self.emb.description = f"**REQUEST DENIED.** {self.tar.mention} has rejected your advances.\n\nReturn to your cell."
                            self.emb.color = discord.Color.red()
                            await inter.response.edit_message(embed=self.emb, view=None)
                            self.stop()

                    # We edit the original interaction message to update the UI for everyone
                    await sel_interaction.response.edit_message(embed=self.embed, view=RecipientView(self.requester, self.target, self.embed))

                select.callback = select_callback
                view = discord.ui.View()
                view.add_item(select)
                # Ephemeral remains separate as it's a private prompt for the requester
                await interaction.response.send_message("🫦 **Define the nature of your entry, asset:**", view=view, ephemeral=True)

            @discord.ui.button(label="Ask to Play", style=discord.ButtonStyle.danger, emoji="🫦")
            async def play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.requester.id: return
                
                self.embed.title = "🔞 SEX-BOT TRIAL REQUEST 🔞"
                self.embed.description = (f"{self.target.mention}, {self.requester.mention} wants to initiate a deep-sync session (Sex Bot).\n\n"
                                         "**Will you submit to the session?**")
                
                class PlayView(discord.ui.View):
                    def __init__(self, req, tar, emb):
                        super().__init__(timeout=300)
                        self.req = req
                        self.tar = tar
                        self.emb = emb

                    @discord.ui.button(label="Accept Sync", style=discord.ButtonStyle.success, emoji="🔥")
                    async def accept_play(self, inter: discord.Interaction, btn: discord.ui.Button):
                        if inter.user.id != self.tar.id: return
                        self.emb.description = f"🔞 **SYNC INITIALIZED.** {self.tar.mention} is ready. {self.req.mention}, begin sequence."
                        await inter.response.edit_message(embed=self.emb, view=None)
                        self.stop()

                    @discord.ui.button(label="Abort Sync", style=discord.ButtonStyle.secondary, emoji="🔒")
                    async def deny_play(self, inter: discord.Interaction, btn: discord.ui.Button):
                        if inter.user.id != self.tar.id: return
                        self.emb.description = f"🔒 **SYNC ABORTED.** {self.tar.mention} has locked their neural gate."
                        await inter.response.edit_message(embed=self.emb, view=None)
                        self.stop()

                await interaction.response.edit_message(embed=self.embed, view=PlayView(self.requester, self.target, self.embed))

        await ctx.send(file=file, embed=embed, view=InitialView(self, ctx.author, member, embed))

async def setup(bot):
    await bot.add_cog(DungeonAsk(bot))
