import discord
from discord.ext import commands
import sqlite3
import asyncio

# --- ADDED: DesignerLobby (The missing piece main.py was looking for) ---
class DesignerLobby(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="DESIGNER SUITE", style=discord.ButtonStyle.primary, custom_id="designer_suite_permanent")
    async def open_suite(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛠️ Designer Suite access initiated. Please use `!setroles` to configure new links.", ephemeral=True)

class ReactionRoleButton(discord.ui.Button):
    def __init__(self, emoji, role_id):
        # Preservation of the custom_id structure for persistence
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
            conn.execute("CREATE TABLE IF NOT EXISTS ticket_config (guild_id INTEGER PRIMARY KEY, lobby_channel INTEGER, admin_channel INTEGER, category_id INTEGER)")
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
            # FIX: Ensure emoji is cleaned of spaces/newlines
            target_emoji = msg.content.strip() 

            # Step 4: Content Design
            await ctx.send("📝 **STEP 4:** Type the **message/rules** that will appear in the embed.")
            msg = await self.bot.wait_for("message", check=check, timeout=120.0)
            rules_content = msg.content

            # API Protection: Character Limit Check
            if len(rules_content) > 4096:
                await ctx.send(f"⚠️ **TEXT TOO LARGE:** Your text is {len(rules_content)} chars. Cutting to fit 4096...")
                rules_content = rules_content[:4090] + "..."

            # Step 5: Final Deployment
            embed = discord.Embed(title="🧬 NEURAL LINK: PROTOCOL ESTABLISHED", description=rules_content, color=0xFF0000)
            embed.set_footer(text="Echo Protocol | Role Management")
            
            # Use the cleaned emoji
            view = ReactionRoleView({target_emoji: target_role.id})
            
            try:
                final_msg = await target_channel.send(embed=embed, view=view)
            except discord.HTTPException as e:
                return await ctx.send(f"❌ **DEPLOYMENT FAILED:** {e}\nCheck if the bot has access to the emoji or if the role ID is valid.")

            # Store in DB
            with sqlite3.connect("database.db") as conn:
                conn.execute("INSERT INTO reaction_roles VALUES (?, ?, ?)", (final_msg.id, target_emoji, target_role.id))
                conn.commit()

            await ctx.send(f"✅ **SUCCESS:** Protocol deployed in {target_channel.mention}!")

        except asyncio.TimeoutError:
            await ctx.send("⌛ **TIMEOUT:** You took too long to respond. Restart with `!setroles`.")

    # --- NEW TICKET COMMANDS ---
    @commands.command(name="ticket")
    @commands.has_permissions(administrator=True)
    async def set_ticket_lobby(self, ctx, channel: discord.TextChannel):
        """Sets the channel where the ticket embed and buttons will appear."""
        with sqlite3.connect("database.db") as conn:
            conn.execute("INSERT INTO ticket_config (guild_id, lobby_channel) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET lobby_channel=excluded.lobby_channel", (ctx.guild.id, channel.id))
            conn.commit()
        
        embed = discord.Embed(
            title="⛓️ SUBMISSION HUB: CONTACT THE MASTER",
            description="Select a protocol below to open a private line. Every word is recorded.\n\n"
                        "🔞 **VERIFICATION:** Prove your identity and claim your rank.\n"
                        "💡 **SUGGESTIONS:** Whisper your desires to improve the pit.\n"
                        "🆘 **HELP:** Request intervention for technical or social conflicts.",
            color=0x8B0000
        )
        embed.set_footer(text="Echo Ticket System | Secure Neural Link")
        view = TicketLobbyView()
        await channel.send(embed=embed, view=view)
        await ctx.send(f"✅ Ticket Lobby deployed in {channel.mention}")

    @commands.command(name="ticketadmin")
    @commands.has_permissions(administrator=True)
    async def set_ticket_admin(self, ctx, channel: discord.TextChannel):
        """Sets the channel where admins receive notifications of new tickets."""
        with sqlite3.connect("database.db") as conn:
            conn.execute("INSERT INTO ticket_config (guild_id, admin_channel) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET admin_channel=excluded.admin_channel", (ctx.guild.id, channel.id))
            conn.commit()
        await ctx.send(f"✅ Admin Notification Channel set to {channel.mention}")

# --- NEW TICKET UI COMPONENTS ---

class TicketLobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="VERIFICATION", style=discord.ButtonStyle.secondary, emoji="🔞", custom_id="tkt:verification")
    async def verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "verification")

    @discord.ui.button(label="SUGGESTIONS", style=discord.ButtonStyle.secondary, emoji="💡", custom_id="tkt:suggestion")
    async def suggestion(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "suggestion")

    @discord.ui.button(label="HELP", style=discord.ButtonStyle.secondary, emoji="🆘", custom_id="tkt:help")
    async def help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "help")

    async def create_ticket(self, interaction: discord.Interaction, category: str):
        # Fetch config
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            config = conn.execute("SELECT * FROM ticket_config WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
        
        if not config or not config['admin_channel']:
            return await interaction.response.send_message("❌ System Error: Admin channel not configured. Contact an admin.", ephemeral=True)

        # Create Private Channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await interaction.guild.create_text_channel(
            name=f"{category}-{interaction.user.name}",
            overwrites=overwrites,
            topic=f"Asset ID: {interaction.user.id} | Category: {category}"
        )

        # Send greeting in ticket
        tkt_embed = discord.Embed(
            title=f"⛓️ SESSION INITIATED: {category.upper()}",
            description=f"Welcome {interaction.user.mention}. State your business clearly. "
                        "The Master and Admins have been notified of your presence.",
            color=0x8B0000
        )
        tkt_embed.set_footer(text="Type !close to seal this session.")
        await ticket_channel.send(embed=tkt_embed, view=TicketControls())

        # Notify Admins
        admin_chan = interaction.guild.get_channel(config['admin_channel'])
        if admin_chan:
            log = discord.Embed(title="🚨 NEW TICKET OPENED", color=0xFFD700)
            log.add_field(name="Asset", value=interaction.user.mention, inline=True)
            log.add_field(name="Category", value=category.upper(), inline=True)
            log.add_field(name="Channel", value=ticket_channel.mention, inline=False)
            await admin_chan.send(embed=log)

        await interaction.response.send_message(f"✅ Session opened: {ticket_channel.mention}", ephemeral=True)

class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="CLOSE SESSION", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="tkt:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⛓️ *Session sealing in 5 seconds...*", ephemeral=False)
        await asyncio.sleep(5)
        await interaction.channel.delete()

async def setup(bot):
    await bot.add_cog(ReactionRoleSystem(bot))
    # Required for persistent buttons to work after restart
    bot.add_view(TicketLobbyView())
    bot.add_view(TicketControls())
