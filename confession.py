import discord
from discord.ext import commands
import sys
import os
import json

class ConfessionModal(discord.ui.Modal, title="NEURAL CONFESSION SUBMISSION"):
    confession = discord.ui.TextInput(
        label="What is your frequency?",
        style=discord.TextStyle.paragraph,
        placeholder="Type your anonymous confession here...",
        required=True,
        max_length=2000,
    )

    def __init__(self, main_mod, bot, review_channel_id):
        super().__init__()
        self.main_mod = main_mod
        self.bot = bot
        self.review_channel_id = review_channel_id

    async def on_submit(self, interaction: discord.Interaction):
        review_channel = self.bot.get_channel(self.review_channel_id)
        if not review_channel:
            return await interaction.response.send_message("❌ Error: Review channel not found.", ephemeral=True)

        embed = self.main_mod.fiery_embed("🛰️ INCOMING CONFESSION FOR REVIEW", 
                                        f"**Submission:**\n{self.confession.value}")
        embed.set_footer(text="The Master must decide the fate of this frequency.")
        
        view = ConfessionReviewView(self.main_mod, self.confession.value)
        await review_channel.send(embed=embed, view=view)
        
        await interaction.response.send_message("✅ Your confession has been transmitted to the Master for review.", ephemeral=True)

class ConfessionReviewView(discord.ui.View):
    def __init__(self, main_mod, confession_text):
        super().__init__(timeout=None)
        self.main_mod = main_mod
        self.confession_text = confession_text

    @discord.ui.button(label="APPROVE", style=discord.ButtonStyle.success, emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        main_mod = sys.modules['__main__']
        cog = interaction.client.get_cog("ConfessionSystem")
        
        post_channel = interaction.client.get_channel(cog.post_channel_id)
        if not post_channel:
            return await interaction.response.send_message("❌ Error: Post channel not found.", ephemeral=True)

        # Get total confession count for the ID
        cog.confession_count += 1
        cog.save_config()

        embed = self.main_mod.fiery_embed(f"🌑 ANONYMOUS CONFESSION #{cog.confession_count}", 
                                        f"\"{self.confession_text}\"")
        embed.set_footer(text="Frequency verified by the Red Room.")
        
        await post_channel.send(embed=embed)
        await interaction.message.delete()
        await interaction.response.send_message("✅ Confession Approved and Dispatched.", ephemeral=True)

    @discord.ui.button(label="REJECT", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        # --- AUTO-ARCHIVE PROTOCOL ---
        main_mod = sys.modules['__main__']
        audit_id = getattr(main_mod, "AUDIT_CHANNEL_ID", 1438810509322223677)
        audit_channel = interaction.client.get_channel(audit_id)
        
        if audit_channel:
            archive_emb = self.main_mod.fiery_embed("🚨 CONFESSION REJECTED & ARCHIVED", 
                f"**Moderator:** {interaction.user.mention}\n"
                f"**Content Purged:**\n```\n{self.confession_text}\n```", color=0xFF0000)
            await audit_channel.send(embed=archive_emb)

        await interaction.message.delete()
        await interaction.response.send_message("🗑️ Confession Purged.", ephemeral=True)

class ConfessionSubmissionView(discord.ui.View):
    def __init__(self, main_mod, bot, review_channel_id):
        super().__init__(timeout=None)
        self.main_mod = main_mod
        self.bot = bot
        self.review_channel_id = review_channel_id

    @discord.ui.button(label="SUBMIT CONFESSION", style=discord.ButtonStyle.secondary, emoji="🌑")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.review_channel_id is None:
            return await interaction.response.send_message("❌ The confession system is not configured.", ephemeral=True)
        await interaction.response.send_modal(ConfessionModal(self.main_mod, self.bot, self.review_channel_id))

class ConfessionSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.review_channel_id = None
        self.post_channel_id = None
        self.confession_count = 0
        self.load_config()

    def load_config(self):
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                row = conn.execute("SELECT value FROM config WHERE key = 'confession_config'").fetchone()
                if row:
                    data = json.loads(row['value'])
                    self.review_channel_id = data.get('review_id')
                    self.post_channel_id = data.get('post_id')
                    self.confession_count = data.get('count', 0)
        except: pass

    def save_config(self):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            data = {'review_id': self.review_channel_id, 'post_id': self.post_channel_id, 'count': self.confession_count}
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         ('confession_config', json.dumps(data)))
            conn.commit()

    @commands.command(name="setconfessreview")
    @commands.has_permissions(administrator=True)
    async def set_review(self, ctx, channel: discord.TextChannel = None):
        """Sets the admin-only channel for approving confessions."""
        self.review_channel_id = (channel or ctx.channel).id
        self.save_config()
        await ctx.send(f"✅ Review channel set to {(channel or ctx.channel).mention}")

    @commands.command(name="setconfesspost")
    @commands.has_permissions(administrator=True)
    async def set_post(self, ctx, channel: discord.TextChannel = None):
        """Sets the public channel where approved confessions are posted."""
        self.post_channel_id = (channel or ctx.channel).id
        self.save_config()
        await ctx.send(f"✅ Post channel set to {(channel or ctx.channel).mention}")

    @commands.command(name="confesspanel")
    @commands.has_permissions(administrator=True)
    async def send_panel(self, ctx):
        """Sends the permanent button for members to submit confessions."""
        main_mod = sys.modules['__main__']
        embed = main_mod.fiery_embed("🌑 NEURAL CONFESSION HUB", 
                                    "Click the button below to submit your frequency anonymously.\n"
                                    "Every submission is reviewed by the Master before being echoed.")
        view = ConfessionSubmissionView(main_mod, self.bot, self.review_channel_id)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ConfessionSystem(bot))
