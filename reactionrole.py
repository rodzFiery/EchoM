import discord
from discord.ext import commands
import sqlite3
import os

# --- PERSISTENT BUTTON LOGIC ---
class ReactionRoleButton(discord.ui.Button):
    def __init__(self, emoji, role_id):
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji, custom_id=f"rr:{role_id}")
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(int(self.role_id))
        if not role:
            return await interaction.response.send_message("❌ Neural Link Error: Role not found.", ephemeral=True)

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

# --- DESIGNER MODAL ---
class ProtocolModal(discord.ui.Modal, title="🧬 DESIGN NEURAL PROTOCOL"):
    title_input = discord.ui.TextInput(label="Embed Title", placeholder="Ex: GENDER ROLES", required=True)
    desc_input = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Click the buttons to assign roles...", required=True)
    emoji_input = discord.ui.TextInput(label="Emoji", placeholder="⭐", required=True)
    role_id_input = discord.ui.TextInput(label="Role ID", placeholder="Paste Role ID here...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        role_id = self.role_id_input.value
        emoji = self.emoji_input.value
        
        embed = discord.Embed(title=self.title_input.value, description=self.desc_input.value, color=0xFF0000)
        view = ReactionRoleView({emoji: role_id})
        
        msg = await interaction.channel.send(embed=embed, view=view)
        
        # Store in DB for persistence recovery
        with sqlite3.connect("database.db") as conn:
            conn.execute("INSERT INTO reaction_roles VALUES (?, ?, ?)", (msg.id, emoji, int(role_id)))
            conn.commit()

        await interaction.response.send_message("✅ **PROTOCOL DEPLOYED:** Persistent link established.", ephemeral=True)

# --- ADMIN LOBBY VIEW ---
class DesignerLobby(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="CREATE NEW SYSTEM", style=discord.ButtonStyle.danger, emoji="➕")
    async def create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ProtocolModal())

# --- MAIN COG ---
class ReactionRoleSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._init_db()

    def _init_db(self):
        with sqlite3.connect("database.db") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS reaction_roles (message_id INTEGER, emoji TEXT, role_id INTEGER)")
            conn.commit()

    @commands.command(name="setuproles")
    @commands.has_permissions(administrator=True)
    async def setuproles(self, ctx):
        """Administrator Command to open the Design Suite."""
        embed = discord.Embed(
            title="⛓️ ECHO PROTOCOL: DESIGNER SUITE",
            description=(
                "### 🛠️ Protocol Architect\n"
                "Use the button below to launch the deployment modal. You can define "
                "custom embeds, emojis, and roles for automatic assignment.\n\n"
                "**Capabilities:**\n"
                "• **Persistence:** Automatically re-binds after restarts.\n"
                "• **Hybrid:** Supports Gateway and Multi-Role systems."
            ),
            color=0x500000
        )
        await ctx.send(embed=embed, view=DesignerLobby())

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_gateway(self, ctx, role: discord.Role):
        """Automatic Gateway Protocol for Rules Verification."""
        embed = discord.Embed(
            title="🔒 SERVER ACCESS: VERIFICATION REQUIRED",
            description=(
                "### 🧬 Acknowledgement\n"
                "To access the server sectors, you must synchronize your neural link.\n\n"
                "**By clicking below, you gain the @server-access role.**"
            ),
            color=0x00FF00
        )
        view = ReactionRoleView({"✅": role.id})
        msg = await ctx.send(embed=embed, view=view)
        
        with sqlite3.connect("database.db") as conn:
            conn.execute("INSERT INTO reaction_roles VALUES (?, ?, ?)", (msg.id, "✅", role.id))
            conn.commit()
        await ctx.message.delete()

async def setup(bot):
    await bot.add_cog(ReactionRoleSystem(bot))
