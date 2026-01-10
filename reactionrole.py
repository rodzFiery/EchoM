import discord
from discord.ext import commands
import sqlite3
import asyncio

class ReactionRoleButton(discord.ui.Button):
    def __init__(self, emoji, role_id):
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji, custom_id=f"rr:{role_id}")
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(int(self.role_id))
        if not role:
            return await interaction.response.send_message("❌ Error: Role not found.", ephemeral=True)

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"🔓 **ACCESS REVOKED:** {role.name} removed.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"🔒 **ACCESS GRANTED:** {role.name} assigned.", ephemeral=True)

class ReactionRoleView(discord.ui.View):
    def __init__(self, mappings):
        super().__init__(timeout=None)
        for emoji, role_id in mappings.items():
            self.add_item(ReactionRoleButton(emoji, role_id))

class ReactionRoleSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._init_db()

    def _init_db(self):
        with sqlite3.connect("database.db") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS reaction_roles (message_id INTEGER, emoji TEXT, role_id INTEGER)")
            conn.commit()

    @commands.command(name="setroles")
    @commands.has_permissions(administrator=True)
    async def setroles(self, ctx):
        """Guided step-by-step setup for reaction roles."""
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            # Step 1: Target Channel
            guide_msg = await ctx.send("🎯 **STEP 1:** Mention the **channel** where the rules should be sent (e.g., #rules).")
            msg = await self.bot.wait_for("message", check=check, timeout=60.0)
            target_channel = msg.channel_mentions[0] if msg.channel_mentions else None
            if not target_channel:
                return await ctx.send("❌ Invalid channel. Restart the command.")

            # Step 2: Role Selection
            await ctx.send(f"👤 **STEP 2:** Mention the **role** to be granted (e.g., @Member).")
            msg = await self.bot.wait_for("message", check=check, timeout=60.0)
            target_role = msg.role_mentions[0] if msg.role_mentions else None
            if not target_role:
                return await ctx.send("❌ Invalid role. Restart the command.")

            # Step 3: Emoji Selection
            await ctx.send("⭐ **STEP 3:** Send the **emoji** you want users to click.")
            msg = await self.bot.wait_for("message", check=check, timeout=60.0)
            target_emoji = msg.content # Simplistic check, assumes admin sends just the emoji

            # Step 4: Content Design
            await ctx.send("📝 **STEP 4:** Type the **message/rules** that will appear in the embed.")
            msg = await self.bot.wait_for("message", check=check, timeout=120.0)
            rules_content = msg.content

            # Step 5: Final Deployment
            embed = discord.Embed(title="🧬 NEURAL LINK: PROTOCOL ESTABLISHED", description=rules_content, color=0xFF0000)
            embed.set_footer(text="Echo Protocol | Role Management")
            
            view = ReactionRoleView({target_emoji: target_role.id})
            final_msg = await target_channel.send(embed=embed, view=view)

            # Store in DB
            with sqlite3.connect("database.db") as conn:
                conn.execute("INSERT INTO reaction_roles VALUES (?, ?, ?)", (final_msg.id, target_emoji, target_role.id))
                conn.commit()

            await ctx.send(f"✅ **SUCCESS:** Protocol deployed in {target_channel.mention}!")

        except asyncio.TimeoutError:
            await ctx.send("⌛ **TIMEOUT:** You took too long to respond. Restart with `!setroles`.")

async def setup(bot):
    await bot.add_cog(ReactionRoleSystem(bot))
