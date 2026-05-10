import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import sys
import os
import json

# --- NEW COMPONENT: INFO BUTTON ---

class ConfessionModal(discord.ui.Modal, title="CONFESSION SUBMISSION"):
    confession = discord.ui.TextInput(
        label="What is your frequency?",
        style=discord.TextStyle.paragraph,
        placeholder="Type your anonymous confession here...",
        required=True,
        max_length=2000,
    )

    def __init__(self, main_mod, bot, review_channel_id, target_slot=1):
        super().__init__()
        self.main_mod = main_mod
        self.bot = bot
        self.review_channel_id = review_channel_id
        self.target_slot = target_slot

    async def on_submit(self, interaction: discord.Interaction):
        review_channel = self.bot.get_channel(self.review_channel_id)
        if not review_channel:
            return await interaction.response.send_message("❌ Error: Review channel not found.", ephemeral=True)

        # --- ADDED: PING LOGIC ---
        cog = self.bot.get_cog("ConfessionSystem")
        cog.load_config(interaction.guild.id)
        ping_content = f"<@&{cog.ping_role_id}>" if cog.ping_role_id else None

        slot_label = "SFW" if self.target_slot == 1 else "NSFW"
        embed = self.main_mod.fiery_embed(f"🛰️ INCOMING CONFESSION [{slot_label}]", 
                                        f"**Submission:**\n{self.confession.value}")
        
        # --- ADDED: USER IDENTITY FOR ADMINS ---
        embed.add_field(name="👤 Submitter Identity", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
        embed.set_footer(text=f"Target Destination: {slot_label} Channel")
        
        # FIXED: Passing target_slot to the review view
        view = ConfessionReviewView(self.main_mod, self.confession.value, interaction.user.id, self.target_slot)
        await review_channel.send(content=ping_content, embed=embed, view=view)
        
        await interaction.response.send_message("✅ Your confession has been transmitted to the Master for review.", ephemeral=True)

class ConfessionReviewView(discord.ui.View):
    def __init__(self, main_mod, confession_text, submitter_id=None, target_slot=1):
        # MANDATORY PERSISTENCE FIX: Added timeout=None
        super().__init__(timeout=None)
        self.main_mod = main_mod
        self.confession_text = confession_text
        self.submitter_id = submitter_id
        self.target_slot = target_slot

    @discord.ui.button(label="APPROVE", style=discord.ButtonStyle.success, emoji="✅", custom_id="confess_approve_btn")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        main_mod = sys.modules['__main__']
        cog = interaction.client.get_cog("ConfessionSystem")
        
        # --- MODIFIED: LOADING GUILD CONFIG ON APPROVAL ---
        cog.load_config(interaction.guild.id)

        # Persistence Recovery: If text is lost due to restart, pull from embed
        if not self.confession_text:
            try:
                content_field = interaction.message.embeds[0].description
                self.confession_text = content_field.replace("**Submission:**\n", "")
                # Logic to determine slot from embed title if memory is wiped
                self.target_slot = 2 if "NSFW" in interaction.message.embeds[0].title else 1
            except:
                return await interaction.response.send_message("❌ Metadata lost. Cannot approve this legacy message.", ephemeral=True)

        # Logic to select ONLY the specific target channel based on the submission slot
        if self.target_slot == 2:
            post_channel = interaction.client.get_channel(cog.post_channel_id_2)
        else:
            post_channel = interaction.client.get_channel(cog.post_channel_id)
        
        if not post_channel:
            return await interaction.response.send_message("❌ Error: Target post channel not configured.", ephemeral=True)

        # Get total confession count for the ID
        cog.confession_count += 1
        cog.save_config(interaction.guild.id)

        embed = self.main_mod.fiery_embed(f"💌 ANONYMOUS CONFESSION #{cog.confession_count}", 
                                        f"\"{self.confession_text}\"")
        embed.set_footer(text="Frequency verified by the Red Room.")
        
        # --- ADDED: SUBMIT ANOTHER BUTTON PROTOCOL ---
        view = ConfessionSubmissionView(self.main_mod, interaction.client, cog.review_channel_id, self.target_slot)
        view.children[0].label = "SUBMIT ANOTHER"
        
        await post_channel.send(embed=embed, view=view)
        
        # --- MODIFIED: AUDIT PERSISTENCE ---
        original_embed = interaction.message.embeds[0]
        original_embed.title = "✅ CONFESSION DISPATCHED"
        original_embed.color = discord.Color.green()
        dest_name = "NSFW" if self.target_slot == 2 else "SFW"
        original_embed.add_field(name="⚖️ Decision", value=f"Approved by {interaction.user.mention}\nPublic ID: #{cog.confession_count}\nSent to: {dest_name}", inline=False)
        
        await interaction.message.edit(content=None, embed=original_embed, view=None)
        await interaction.response.send_message(f"✅ Confession Approved and Dispatched to {dest_name}.", ephemeral=True)

    @discord.ui.button(label="REJECT", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="confess_reject_btn")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        # --- AUTO-ARCHIVE PROTOCOL ---
        main_mod = sys.modules['__main__']
        audit_id = getattr(main_mod, "AUDIT_CHANNEL_ID", 1438810509322223677)
        audit_channel = interaction.client.get_channel(audit_id)
        
        # Recovery of text for rejection audit
        if not self.confession_text:
            try:
                self.confession_text = interaction.message.embeds[0].description.replace("**Submission:**\n", "")
            except: self.confession_text = "Data Purged"

        if audit_channel:
            # Attempt to find submitter ID from embed if view is cold
            if not self.submitter_id:
                try: 
                    id_val = interaction.message.embeds[0].fields[0].value
                    self.submitter_id = id_val.split("(")[-1].replace(")", "")
                except: pass

            user_info = f"<@{self.submitter_id}>" if self.submitter_id else "Unknown"
            # FIXED: f-string literal cleaned to prevent SyntaxError
            archive_emb = self.main_mod.fiery_embed("🚨 CONFESSION REJECTED & ARCHIVED", f"**Moderator:** {interaction.user.mention}\n**Submitter:** {user_info}\n**Content Purged:**\n{self.confession_text}", color=0xFF0000)
            await audit_channel.send(embed=archive_emb)

        # --- MODIFIED: HISTORY RETENTION IN REVIEW CHANNEL ---
        # Update the original review message instead of deleting it
        rejected_embed = interaction.message.embeds[0]
        rejected_embed.title = "❌ CONFESSION REJECTED"
        rejected_embed.color = discord.Color.red()
        rejected_embed.add_field(name="⚖️ Decision", value=f"Rejected by {interaction.user.mention}\nStatus: Purged from public queue.", inline=False)
        
        await interaction.message.edit(content=None, embed=rejected_embed, view=None)
        await interaction.response.send_message("🗑️ Confession Purged.", ephemeral=True)

class ConfessionSubmissionView(discord.ui.View):
    def __init__(self, main_mod, bot, review_channel_id=None, target_slot=1):
        # MANDATORY PERSISTENCE FIX: Added timeout=None
        super().__init__(timeout=None)
        self.main_mod = main_mod
        self.bot = bot
        self.review_channel_id = review_channel_id
        self.target_slot = target_slot
        
        # CRITICAL: Hardcoding custom_id logic inside the button itself is better, 
        # but here we set it in __init__ based on the target_slot.
        self.children[0].custom_id = f"confess_btn_slot_{target_slot}"

    @discord.ui.button(label="SUBMIT CONFESSION", style=discord.ButtonStyle.secondary, emoji="💌")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("ConfessionSystem")
        cog.load_config(interaction.guild.id)
        
        if cog.review_channel_id is None:
            return await interaction.response.send_message("❌ The confession system is not configured.", ephemeral=True)
        
        # Determine target slot from button ID
        slot = 1
        if button.custom_id == "confess_btn_slot_2": slot = 2

        await interaction.response.send_modal(ConfessionModal(self.main_mod, interaction.client, cog.review_channel_id, slot))

class ConfessionSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.review_channel_id = None
        self.post_channel_id = None
        self.post_channel_id_2 = None
        self.ping_role_id = None
        self.confession_count = 0

    def load_config(self, guild_id):
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                # Row-to-Dict conversion compatibility
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT value FROM config WHERE key = ?", (f'confession_config_{guild_id}',)).fetchone()
                if row:
                    data = json.loads(row['value'])
                    self.review_channel_id = data.get('review_id')
                    self.post_channel_id = data.get('post_id')
                    self.post_channel_id_2 = data.get('post_id_2')
                    self.ping_role_id = data.get('ping_role_id')
                    self.confession_count = data.get('count', 0)
                else:
                    self.review_channel_id = None
                    self.post_channel_id = None
                    self.post_channel_id_2 = None
                    self.ping_role_id = None
                    self.confession_count = 0
        except: pass

    def save_config(self, guild_id):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            data = {
                'review_id': self.review_channel_id, 
                'post_id': self.post_channel_id, 
                'post_id_2': self.post_channel_id_2, 
                'ping_role_id': self.ping_role_id,
                'count': self.confession_count
            }
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         (f'confession_config_{guild_id}', json.dumps(data)))
            conn.commit()

    @commands.command(name="setconfessreview")
    @commands.has_permissions(administrator=True)
    async def set_review(self, ctx, channel: discord.TextChannel = None):
        """Sets the admin-only channel for approving confessions."""
        self.load_config(ctx.guild.id)
        self.review_channel_id = (channel or ctx.channel).id
        self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Review channel set to {(channel or ctx.channel).mention}")

    @commands.command(name="setconfesspost")
    @commands.has_permissions(administrator=True)
    async def set_post(self, ctx, channel: discord.TextChannel = None):
        """Sets the first public channel where approved confessions are posted."""
        self.load_config(ctx.guild.id)
        self.post_channel_id = (channel or ctx.channel).id
        self.save_config(ctx.guild.id)
        await ctx.send(f"✅ SFW Post channel set to {(channel or ctx.channel).mention}")

    @commands.command(name="setconfesspost2")
    @commands.has_permissions(administrator=True)
    async def set_post_2(self, ctx, channel: discord.TextChannel = None):
        """Sets the second public channel where approved confessions are posted."""
        self.load_config(ctx.guild.id)
        self.post_channel_id_2 = (channel or ctx.channel).id
        self.save_config(ctx.guild.id)
        await ctx.send(f"✅ NSFW Post channel set to {(channel or ctx.channel).mention}")

    @commands.command(name="confessrole")
    @commands.has_permissions(administrator=True)
    async def set_confess_role(self, ctx, role: discord.Role = None):
        """Sets the role to ping when a new confession arrives in the review channel."""
        self.load_config(ctx.guild.id)
        if role:
            self.ping_role_id = role.id
            await ctx.send(f"✅ Review ping role set to {role.mention}")
        else:
            self.ping_role_id = None
            await ctx.send("✅ Review ping role has been disabled.")
        self.save_config(ctx.guild.id)

    @commands.command(name="setconfesscount")
    @commands.has_permissions(administrator=True)
    async def set_confess_count(self, ctx, count: int):
        """Manually sets the confession counter to a specific number."""
        self.load_config(ctx.guild.id)
        self.confession_count = count
        self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Confession counter adjusted. The next approved confession will be **#{count + 1}**.")

    @commands.command(name="confessstatus")
    @commands.has_permissions(administrator=True)
    async def confess_status(self, ctx):
        """Displays the current confession configuration for this sector."""
        self.load_config(ctx.guild.id)
        main_mod = sys.modules['__main__']
        
        review = f"<#{self.review_channel_id}>" if self.review_channel_id else "`Not Set`"
        post1 = f"<#{self.post_channel_id}>" if self.post_channel_id else f"`Not Set`"
        post2 = f"<#{self.post_channel_id_2}>" if self.post_channel_id_2 else f"`Not Set`"
        ping_role = f"<@&{self.ping_role_id}>" if self.ping_role_id else "`Disabled`"
        
        desc = (f"### 📡 CONFESSION PROTOCOL STATUS\n"
                f"**Review Channel:** {review}\n"
                f"**Ping Role:** {ping_role}\n"
                f"**SFW Post:** {post1}\n"
                f"**NSFW Post:** {post2}\n\n"
                f"**Total Echoed:** `{self.confession_count}`")
        await ctx.send(embed=main_mod.fiery_embed("SYSTEM CONFIGURATION AUDIT", desc, color=0x3498DB))

    @commands.command(name="confesspanel")
    @commands.has_permissions(administrator=True)
    async def send_panel(self, ctx, slot: int = 1):
        """Sends a button for members. Use !confesspanel 1 or !confesspanel 2."""
        self.load_config(ctx.guild.id)
        main_mod = sys.modules['__main__']
        slot_text = "SFW" if slot == 1 else "NSFW"
        embed = main_mod.fiery_embed(f"📩 CONFESSION HUB [{slot_text}]", 
                                    f"Click the button below to submit your frequency to the {slot_text} channel.\n"
                                    "Every submission is reviewed by the Master before being echoed.")
        # Pass slot ID to the view so it knows where to route approved messages
        view = ConfessionSubmissionView(main_mod, self.bot, self.review_channel_id, target_slot=slot)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="confess")
    async def manual_confess(self, ctx, *, message: str):
        """Manually trigger an anonymous confession (defaults to SFW)."""
        self.load_config(ctx.guild.id)
        if self.review_channel_id is None:
            return await ctx.send("❌ The confession review channel is not configured.")

        review_channel = self.bot.get_channel(self.review_channel_id)
        if not review_channel:
            return await ctx.send("❌ Error: Review channel not found.")

        main_mod = sys.modules['__main__']
        ping_content = f"<@&{self.ping_role_id}>" if self.ping_role_id else None
        embed = main_mod.fiery_embed("💗 CONFESSION [SFW]", f"**Submission:**\n{message}")
        
        # --- ADDED: USER IDENTITY FOR ADMINS ---
        embed.add_field(name="👤 Submitter Identity", value=f"{ctx.author.mention} ({ctx.author.id})", inline=False)
        embed.set_footer(text="Submitted via command protocol (SFW).")
        
        # FIXED: Passing target_slot 1 for manual commands
        view = ConfessionReviewView(main_mod, message, ctx.author.id, target_slot=1)
        await review_channel.send(content=ping_content, embed=embed, view=view)
        
        try:
            await ctx.message.delete()
        except: pass
        await ctx.send("✅ Your confession has been transmitted for review.", delete_after=5)

async def setup(bot):
    main_mod = sys.modules['__main__']
    cog = ConfessionSystem(bot)
    await bot.add_cog(cog)

    # --- PERSISTENCE PROTOCOL ---
    # We register the views here so they stay active across restarts.
    # We create one for Slot 1 and one for Slot 2.
    bot.add_view(ConfessionSubmissionView(main_mod, bot, target_slot=1))
    bot.add_view(ConfessionSubmissionView(main_mod, bot, target_slot=2))
    
    # Register the Review View (used for the approval messages themselves)
    bot.add_view(ConfessionReviewView(main_mod, confession_text=None))
