import discord
from discord.ext import commands
import sqlite3
import os

# --- THE STABLE BUTTON ---
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

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_gateway(self, ctx, role: discord.Role):
        """Standard verification gateway."""
        embed = discord.Embed(
            title="🔒 SERVER ACCESS: VERIFICATION REQUIRED",
            description="### 🧬 Acknowledgement\nTo access the server, acknowledge the rules by clicking below.",
            color=0x00FF00
        )
        view = ReactionRoleView({"✅": role.id})
        msg = await ctx.send(embed=embed, view=view)
        
        with sqlite3.connect("database.db") as conn:
            conn.execute("INSERT INTO reaction_roles VALUES (?, ?, ?)", (msg.id, "✅", role.id))
            conn.commit()
        await ctx.message.delete()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setuprole_custom(self, ctx, role: discord.Role, emoji: str, title: str, *, description: str):
        """Manually create any reaction role message via command."""
        embed = discord.Embed(title=title, description=description, color=0xFF0000)
        embed.set_footer(text="Echo Protocol | Role Synchronization")
        
        view = ReactionRoleView({emoji: role.id})
        msg = await ctx.send(embed=embed, view=view)

        with sqlite3.connect("database.db") as conn:
            conn.execute("INSERT INTO reaction_roles VALUES (?, ?, ?)", (msg.id, emoji, role.id))
            conn.commit()
        await ctx.message.delete()

async def setup(bot):
    await bot.add_cog(ReactionRoleSystem(bot))
