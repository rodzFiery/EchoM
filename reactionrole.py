import discord
from discord.ext import commands
import sqlite3
import asyncio
import os
import io
from datetime import datetime

# --- ADDED: DesignerLobby (The missing piece main.py was looking for) ---
class DesignerLobby(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="DESIGNER SUITE", style=discord.ButtonStyle.primary, custom_id="designer_suite_permanent")
    async def open_suite(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛠️ Designer Suite access initiated. Please use `!setroles` to configure new links.", ephemeral=True)

class ReactionRoleButton(discord.ui.Button):
    def __init__(self, emoji, role_id, count=0):
        # FIXED: Dynamic numerical counter string formatting embedded natively into the label protocol
        label_text = f"({count})" if count > 0 else None
        super().__init__(style=discord.ButtonStyle.secondary, label=label_text, emoji=emoji, custom_id=f"rr:{role_id}")
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

        # UPDATED: Recalculate dynamic tracking numbers and refresh the view structure in real-time
        updated_count = len(role.members)
        self.label = f"({updated_count})" if updated_count > 0 else None
        await interaction.message.edit(view=self.view)

class ReactionRoleView(discord.ui.View):
    def __init__(self, mappings, guild=None):
        super().__init__(timeout=None)
        for emoji, role_id in mappings.items():
            initial_count = 0
            if guild:
                role_obj = guild.get_role(int(role_id))
                if role_obj:
                    initial_count = len(role_obj.members)
            self.add_item(ReactionRoleButton(emoji, role_id, count=initial_count))

class ReactionRoleSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._init_db()

    def _init_db(self):
        with sqlite3.connect("database.db") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS reaction_roles (message_id INTEGER, emoji TEXT, role_id INTEGER)")
            # MODIFIED: admin_channel changed to admin_role_id | ADDED: ticket_count
            conn.execute("CREATE TABLE IF NOT EXISTS ticket_config (guild_id INTEGER PRIMARY KEY, lobby_channel INTEGER, admin_channel INTEGER, category_id INTEGER, admin_role_id INTEGER, ticket_count INTEGER DEFAULT 0)")
            
            # ENSURE ADMIN_ROLE_ID COLUMN PERSISTS BETWEEN DEPLOYS
            cursor = conn.execute("PRAGMA table_info(ticket_config)")
            columns = [column[1] for column in cursor.fetchall()]
            if "admin_role_id" not in columns:
                conn.execute("ALTER TABLE ticket_config ADD COLUMN admin_role_id INTEGER")
            
            # --- NEW ARCHIVE TABLE ---
            conn.execute("CREATE TABLE IF NOT EXISTS ticket_archives (ticket_id TEXT PRIMARY KEY, guild_id INTEGER, asset_name TEXT, category TEXT, content TEXT, timestamp TEXT)")
            
            # --- ADDED: AUTOROLE CONFIG TABLE ---
            conn.execute("CREATE TABLE IF NOT EXISTS autorole_config (guild_id INTEGER PRIMARY KEY, role_id INTEGER)")
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

            # --- ADDED: STEP 5 - IMAGE UPLOAD/LINK SELECTION (.JPG SUPPORT) ---
            await ctx.send("🖼️ **STEP 5:** Upload a **.jpg image** attachment or paste an image URL. (Type `none` to skip).")
            msg = await self.bot.wait_for("message", check=check, timeout=90.0)
            embed_image_url = None
            
            if msg.content.strip().lower() != "none":
                if msg.attachments:
                    embed_image_url = msg.attachments[0].url
                elif msg.content.startswith("http"):
                    embed_image_url = msg.content.strip()

            # Step 6: Final Deployment
            embed = discord.Embed(title="🧬 NEURAL LINK: PROTOCOL ESTABLISHED", description=rules_content, color=0xFF0000)
            embed.set_footer(text="Echo Protocol | Role Management")
            
            # Apply image parameter if provided by user
            if embed_image_url:
                embed.set_image(url=embed_image_url)
            
            # Use the cleaned emoji and pass guild context to calculate numbers dynamically
            view = ReactionRoleView({target_emoji: target_role.id}, guild=ctx.guild)
            
            try:
                final_msg = await target_channel.send(embed=embed, view=view)
            except discord.HTTPException as e:
                return await ctx.send(f"❌ **DEPLOYMENT FAILED:** {e}\nCheck if the bot has access to the emoji or if the role ID is valid.")

            # Store in DB
            with sqlite3.connect("database.db") as conn:
                conn.execute("INSERT INTO reaction_roles VALUES (?, ?, ?)", (final_msg.id, target_emoji, target_role.id))
                conn.commit()

            await ctx.send(f"✅ **SUCCESS:** Protocol deployed in {target_channel.mention}!")

        except asyncio.timeoutError:
            await ctx.send("⌛ **TIMEOUT:** You took too long to respond. Restart with `!setroles`.")

    # --- NEW TICKET COMMANDS ---
    @commands.command(name="ticket")
    @commands.has_permissions(administrator=True)
    async def set_ticket_lobby(self, ctx, channel: discord.TextChannel):
        """Sets the channel where the ticket embed and buttons will appear."""
        with sqlite3.connect("database.db") as conn:
            # FIX: Ensure all columns are handled for the INSERT OR REPLACE logic
            conn.execute("""
                INSERT INTO ticket_config (guild_id, lobby_channel) 
                VALUES (?, ?) 
                ON CONFLICT(guild_id) DO UPDATE SET lobby_channel=excluded.lobby_channel
            """, (ctx.guild.id, channel.id))
            conn.commit()
        
        embed = discord.Embed(
            title="📩 Contact the Staff",
            description="Select a protocol below to open a private line. Every word is recorded.\n\n"
                        "🔞 **VERIFICATION:** Prove your identity and claim your rank.\n"
                        "💬 **SUPPORT:** General inquiries and server guidance.\n"
                        "⚙️ **TECH ISSUES:** Report glitches in the neural link.\n"
                        "🚨 **DRAMAS:** Report conflicts or asset misbehavior.",
            color=0x8B0000
        )
        embed.set_footer(text="Echo Ticket System | Secure Neural Link")
        
        # --- ADDED: LARGE SCALE IMAGE PROTOCOL ---
        file = None
        if os.path.exists("ticket.png"):
            file = discord.File("ticket.png", filename="ticket.png")
            embed.set_image(url="attachment://ticket.png")

        view = TicketLobbyView()
        if file:
            await channel.send(file=file, embed=embed, view=view)
        else:
            await channel.send(embed=embed, view=view)
            
        await ctx.send(f"✅ Ticket Lobby deployed in {channel.mention}")

    @commands.command(name="ticketadmin")
    @commands.has_permissions(administrator=True)
    async def set_ticket_admin(self, ctx, role: discord.Role):
        """Sets the Admin Role and creates a private channel for notifications."""
        # Define overwrites for the new private admin channel
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Create the channel
        admin_channel = await ctx.guild.create_text_channel(
            name="war-room-logs",
            overwrites=overwrites,
            topic="Private logs for the Master and appointed Admins."
        )

        with sqlite3.connect("database.db") as conn:
            conn.execute("""
                INSERT INTO ticket_config (guild_id, admin_channel, admin_role_id) 
                VALUES (?, ?, ?) 
                ON CONFLICT(guild_id) DO UPDATE SET 
                    admin_channel=excluded.admin_channel, 
                    admin_role_id=excluded.admin_role_id
            """, (ctx.guild.id, admin_channel.id, role.id))
            conn.commit()

        await ctx.send(f"✅ Admin Role and Channel Persisted: {admin_channel.mention}\nOnly users with the role {role.mention} can see it.")

    @commands.command(name="ticketcategory")
    @commands.has_permissions(administrator=True)
    async def set_ticket_category(self, ctx, category_id: int):
        """Sets the category ID where ticket channels will be created."""
        with sqlite3.connect("database.db") as conn:
            conn.execute("""
                INSERT INTO ticket_config (guild_id, category_id) 
                VALUES (?, ?) 
                ON CONFLICT(guild_id) DO UPDATE SET category_id=excluded.category_id
            """, (ctx.guild.id, category_id))
            conn.commit()
        await ctx.send(f"✅ Ticket Category set to ID: `{category_id}`")

    @commands.command(name="setticket")
    @commands.has_permissions(administrator=True)
    async def set_ticket_count(self, ctx, count: int):
        """Manually sets the ticket counter to a specific number."""
        with sqlite3.connect("database.db") as conn:
            conn.execute("""
                INSERT INTO ticket_config (guild_id, ticket_count) 
                VALUES (?, ?) 
                ON CONFLICT(guild_id) DO UPDATE SET ticket_count=excluded.ticket_count
            """, (ctx.guild.id, count))
            conn.commit()
        await ctx.send(f"✅ Ticket counter adjusted. The next session will be **#{count + 1}**.")

    # --- NEW ARCHIVE BROWSER ---
    @commands.command(name="archives")
    @commands.has_permissions(administrator=True)
    async def list_archives(self, ctx):
        """Displays the list of sealed transcripts from the database."""
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT ticket_id, asset_name, category, timestamp FROM ticket_archives WHERE guild_id = ? ORDER BY timestamp DESC LIMIT 10", (ctx.guild.id,)).fetchall()
        
        if not rows:
            return await ctx.send("🗄️ The Black Box is empty. No sessions archived.")
        
        embed = discord.Embed(title="🗄️ NEURAL ARCHIVE: STORED SESSIONS", color=0x2F3136)
        desc = ""
        for row in rows:
            desc += f"🆔 `{row['ticket_id']}` | **{row['asset_name']}** ({row['category']}) - {row['timestamp']}\n"
        
        embed.description = desc
        embed.set_footer(text="Use !view <ID> to retrieve a specific transcript.")
        await ctx.send(embed=embed)

    @commands.command(name="view")
    @commands.has_permissions(administrator=True)
    async def view_archive(self, ctx, ticket_id: str):
        """Retrieves and re-transmits a transcript from the archives."""
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM ticket_archives WHERE ticket_id = ? AND guild_id = ?", (ticket_id, ctx.guild.id)).fetchone()
        
        if not row:
            return await ctx.send("❌ Data block not found.")
        
        buffer = io.BytesIO(row['content'].encode('utf-8'))
        await ctx.send(content=f"📑 **TRANSCRIPT RECOVERY:** `{ticket_id}`", file=discord.File(buffer, filename=f"recovered-{ticket_id}.txt"))

    # --- ADDED: AUTOROLE COMMAND SYSTEM ---
    @commands.command(name="autorole")
    @commands.has_permissions(administrator=True)
    async def set_autorole(self, ctx, role: discord.Role = None):
        """Sets or disables the role assigned automatically to joining members."""
        with sqlite3.connect("database.db") as conn:
            if role is None:
                conn.execute("DELETE FROM autorole_config WHERE guild_id = ?", (ctx.guild.id,))
                conn.commit()
                return await ctx.send("♻️ **AUTOROLE PROTOCOL DEACTIVATED:** New assets will no longer receive baseline links automatically.")
            
            conn.execute("""
                INSERT INTO autorole_config (guild_id, role_id) 
                VALUES (?, ?) 
                ON CONFLICT(guild_id) DO UPDATE SET role_id=excluded.role_id
            """, (ctx.guild.id, role.id))
            conn.commit()
        await ctx.send(f"✅ **AUTOROLE PROTOCOL ENGAGED:** Joining members will now automatically be bound to the {role.mention} role matrix.")

    # --- ADDED: MEMBER JOIN LISTENER FOR AUTOROLE ---
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Assigns the configured autorole to new assets upon arrival."""
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT role_id FROM autorole_config WHERE guild_id = ?", (member.guild.id,)).fetchone()
        
        if row and row['role_id']:
            role = member.guild.get_role(int(row['role_id']))
            if role:
                try:
                    await member.add_roles(role)
                except Exception as e:
                    print(f"Failed to assign autorole in guild {member.guild.id}: {e}")

# --- NEW TICKET UI COMPONENTS ---

class TicketLobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="VERIFICATION", style=discord.ButtonStyle.secondary, emoji="🔞", custom_id="tkt:verification")
    async def verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "verification")

    @discord.ui.button(label="SUPPORT", style=discord.ButtonStyle.secondary, emoji="💬", custom_id="tkt:support")
    async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "support")

    @discord.ui.button(label="TECH ISSUES", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="tkt:technical")
    async def technical(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "technical")

    @discord.ui.button(label="DRAMAS", style=discord.ButtonStyle.secondary, emoji="🚨", custom_id="tkt:drama")
    async def dramas(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "drama")

    async def create_ticket(self, interaction: discord.Interaction, category: str):
        # Fetch and Increment config
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            # Update counter first
            conn.execute("UPDATE ticket_config SET ticket_count = ticket_count + 1 WHERE guild_id = ?", (interaction.guild.id,))
            conn.commit()
            config = conn.execute("SELECT * FROM ticket_config WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
        
        if not config or not config['admin_role_id']:
            return await interaction.response.send_message("❌ System Error: Admin role not configured. Use `!ticketadmin @role` first.", ephemeral=True)

        admin_role = interaction.guild.get_role(config['admin_role_id'])
        current_num = config['ticket_count']

        # --- AUTO CATEGORY LOGIC ---
        cat_name = category.upper()
        target_category = discord.utils.get(interaction.guild.categories, name=cat_name)
        
        if not target_category:
            # Create the category automatically if it doesn't exist
            overwrites_cat = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True) if admin_role else None
            }
            target_category = await interaction.guild.create_category(name=cat_name, overwrites=overwrites_cat)

        # Create Private Channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add the Admin Role to the private channel permissions
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        # FORMATTED NAME: ticket[number]-[category]
        ticket_channel = await interaction.guild.create_text_channel(
            name=f"ticket{current_num}-{category}",
            overwrites=overwrites,
            category=target_category,
            topic=f"Asset ID: {interaction.user.id} | Session #{current_num}"
        )

        # --- MODIFIED: PING THE ROLE ---
        ping_content = f"{interaction.user.mention} | {admin_role.mention if admin_role else ''}"

        # Send greeting in ticket
        tkt_embed = discord.Embed(
            title=f"⛓️ SESSION #{current_num} INITIATED: {category.upper()}",
            description=f"Welcome {interaction.user.mention}. State your business clearly. "
                        "The Staff has been notified of your presence.",
            color=0x8B0000
        )
        tkt_embed.set_footer(text="The Master is watching.")
        await ticket_channel.send(content=ping_content, embed=tkt_embed, view=TicketControls())

        # Notify Admins
        admin_chan = interaction.guild.get_channel(config['admin_channel'])
        if admin_chan:
            log = discord.Embed(title=f"🚨 NEW SESSION OPENED: #{current_num}", color=0xFFD700)
            log.add_field(name="Asset", value=interaction.user.mention, inline=True)
            log.add_field(name="Category", value=category.upper(), inline=True)
            log.add_field(name="Channel", value=ticket_channel.mention, inline=False)
            await admin_chan.send(embed=log)

        await interaction.response.send_message(f"✅ Session opened: {ticket_channel.mention}", ephemeral=True)

class ArchiveViewer(discord.ui.View):
    def __init__(self, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="VIEW DATA", style=discord.ButtonStyle.secondary, emoji="👁️", custom_id="persistent_view_archive")
    async def view_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Trigger the !view command logic via interaction
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT content FROM ticket_archives WHERE ticket_id = ?", (self.ticket_id,)).fetchone()
        
        if row:
            buffer = io.BytesIO(row['content'].encode('utf-8'))
            await interaction.response.send_message(f"📑 **NEURAL RECOVERY:** Session `{self.ticket_id}`", file=discord.File(buffer, filename=f"{self.ticket_id}.txt"), ephemeral=True)
        else:
            await interaction.response.send_message("❌ Data block corrupted or missing.", ephemeral=True)

class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="CLOSE SESSION", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="tkt:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        try:
            # 1. Fetch History
            transcript = f"--- BLACK BOX TRANSCRIPT: {interaction.channel.name} ---\n"
            transcript += f"Asset: {interaction.channel.name.split('-')[-1]}\n"
            transcript += f"Sealed on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            transcript += "-"*40 + "\n\n"
            
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                time = message.created_at.strftime('%H:%M')
                content = message.clean_content if message.content else "[Attachment/Embed]"
                transcript += f"[{time}] {message.author.display_name}: {content}\n"

            # 2. Store in Database Archives
            ticket_id = interaction.channel.name
            with sqlite3.connect("database.db") as conn:
                conn.execute("INSERT OR REPLACE INTO ticket_archives VALUES (?, ?, ?, ?, ?, ?)", 
                             (ticket_id, interaction.guild.id, interaction.user.display_name, "SESSION", transcript, datetime.now().strftime('%Y-%m-%d %H:%M')))
                conn.commit()

            # 3. Transmit to Admin Channel with Button
            with sqlite3.connect("database.db") as conn:
                conn.row_factory = sqlite3.Row
                config = conn.execute("SELECT admin_channel FROM ticket_config WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
            
            if config and config['admin_channel']:
                admin_chan = interaction.guild.get_channel(config['admin_channel'])
                if admin_chan:
                    archive_emb = discord.Embed(
                        title="📸 EVIDENCE ARCHIVED",
                        description=f"Session **{ticket_id}** has been sealed. Data logged to database.",
                        color=0x2F3136
                    )
                    await admin_chan.send(embed=archive_emb, view=ArchiveViewer(ticket_id))

        except Exception as e:
            print(f"Transcript Error: {e}")

        # 4. Final Purge
        await interaction.followup.send("⛓️ *Session sealing. Data stored in Black Box. Purging in 5 seconds...*")
        await asyncio.sleep(5)
        await interaction.channel.delete()

async def setup(bot):
    await bot.add_cog(ReactionRoleSystem(bot))
    # Required for persistent buttons to work after restart
    bot.add_view(TicketLobbyView())
    bot.add_view(TicketControls())
    bot.add_view(DesignerLobby())
