import discord
from discord.ext import commands
import sqlite3
import asyncio
import os
import io
import json
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
            
            # --- ADDED: TICKET BUTTONS TABLE FOR PERSISTENCE ACROSS RESTARTS ---
            conn.execute("CREATE TABLE IF NOT EXISTS ticket_buttons (guild_id INTEGER, btn_index INTEGER, label TEXT, emoji TEXT)")
            
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
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            target_channel = msg.channel_mentions[0] if msg.channel_mentions else None
            if not target_channel:
                return await ctx.send("❌ Invalid channel. Restart the command.")

            # --- ADDED: Ask for the number of reaction roles (Up to 25 natively supported by Discord Views) ---
            await ctx.send("🔢 **STEP 2:** How many **reaction roles** would you like to add to this panel? (Maximum of 25).")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            try:
                rr_count = int(msg.content.strip())
                if not (1 <= rr_count <= 25):
                    return await ctx.send("❌ Total reaction roles must be between 1 and 25. Protocol terminated.")
            except ValueError:
                return await ctx.send("❌ Please enter a valid number configuration.")

            mappings = {}
            db_mappings = []
            
            # --- ADDED: Loop to gather personalized Roles and Emojis dynamically ---
            for i in range(rr_count):
                # Step 3: Role Selection
                await ctx.send(f"👤 **STEP 3.{i+1}:** Mention the **role** to be granted for button #{i+1} (e.g., @Member).")
                msg = await self.bot.wait_for("message", check=check, timeout=None)
                target_role = msg.role_mentions[0] if msg.role_mentions else None
                if not target_role:
                    return await ctx.send("❌ Invalid role. Restart the command.")

                # Step 4: Emoji Selection (Multi-Server Custom Custom Emoji Support)
                await ctx.send(f"⭐ **STEP 4.{i+1}:** Send the **emoji** you want users to click for {target_role.name}. (Standard or custom server emojis are supported).")
                msg = await self.bot.wait_for("message", check=check, timeout=None)
                raw_content = msg.content.strip()
                
                # MULTI-SERVER SYNC: Convert custom client strings into valid PartialEmoji objects if custom
                if raw_content.startswith("<:") or raw_content.startswith("<a:"):
                    try:
                        target_emoji = discord.PartialEmoji.from_str(raw_content)
                    except Exception:
                        return await ctx.send("❌ Failed to process the custom emoji structure. Make sure the bot is inside the host server.")
                else:
                    target_emoji = raw_content
                    
                mappings[target_emoji] = target_role.id
                db_mappings.append((str(target_emoji), target_role.id))

            # Step 5: Content Design
            await ctx.send("📝 **STEP 5:** Type the **message/rules** that will appear in the embed.")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            rules_content = msg.content

            # API Protection: Character Limit Check
            if len(rules_content) > 4096:
                await ctx.send(f"⚠️ **TEXT TOO LARGE:** Your text is {len(rules_content)} chars. Cutting to fit 4096...")
                rules_content = rules_content[:4090] + "..."

            # --- ADDED: STEP 6 - IMAGE UPLOAD/LINK SELECTION (.JPG SUPPORT) ---
            await ctx.send("🖼️ **STEP 6:** Upload a **.jpg image** attachment or paste an image URL. (Type `none` to skip).")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            embed_image_url = None
            
            if msg.content.strip().lower() != "none":
                if msg.attachments:
                    embed_image_url = msg.attachments[0].url
                elif msg.content.startswith("http"):
                    embed_image_url = msg.content.strip()

            # Step 7: Final Deployment
            embed = discord.Embed(title="🧬 NEURAL LINK: PROTOCOL ESTABLISHED", description=rules_content, color=0xFF0000)
            embed.set_footer(text="Echo Protocol | Role Management")
            
            # Apply image parameter if provided by user
            if embed_image_url:
                embed.set_image(url=embed_image_url)
            
            # Pass custom/standard mapping data and guild context to determine current counters
            view = ReactionRoleView(mappings, guild=ctx.guild)
            
            try:
                final_msg = await target_channel.send(embed=embed, view=view)
            except discord.HTTPException as e:
                return await ctx.send(f"❌ **DEPLOYMENT FAILED:** {e}\nCheck if the bot has access to the emoji or if the role ID is valid.")

            # Store string conversion representation in database logs
            with sqlite3.connect("database.db") as conn:
                for db_emoji_str, db_role_id in db_mappings:
                    conn.execute("INSERT INTO reaction_roles VALUES (?, ?, ?)", (final_msg.id, db_emoji_str, db_role_id))
                conn.commit()

            await ctx.send(f"✅ **SUCCESS:** Protocol deployed in {target_channel.mention} with {rr_count} options!")

        except asyncio.TimeoutError:
            await ctx.send("⌛ **TIMEOUT:** You took too long to respond. Restart with `!setroles`.")

    # --- NEW TICKET COMMANDS ---
    @commands.command(name="ticket")
    @commands.has_permissions(administrator=True)
    async def set_ticket_lobby(self, ctx):
        """Guided step-by-step setup to create a custom ticket lobby with fully personalized buttons and images."""
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            # Step 1: Target Channel
            await ctx.send("🎯 **STEP 1:** Mention the **channel** where the ticket lobby panel should be sent (e.g., #support).")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            target_channel = msg.channel_mentions[0] if msg.channel_mentions else None
            if not target_channel:
                return await ctx.send("❌ Invalid channel. Cancelled protocol.")

            # Step 2: Content Copy Design
            await ctx.send("📝 **STEP 2:** Type the **description copy** that will appear in your support lobby panel embed.")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            lobby_desc = msg.content

            # Step 3: Custom Upload/Link Selection
            await ctx.send("🖼️ **STEP 3:** Upload a **custom image attachment** or paste an image link for this panel. (Type `none` to skip).")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            ticket_image_url = None
            
            if msg.content.strip().lower() != "none":
                if msg.attachments:
                    ticket_image_url = msg.attachments[0].url
                elif msg.content.startswith("http"):
                    ticket_image_url = msg.content.strip()

            # Step 4: Button Quantity Personalization
            await ctx.send("🔢 **STEP 4:** How many **custom buttons** would you like to build for this lobby? (Maximum of 5).")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            try:
                btn_count = int(msg.content.strip())
                if not (1 <= btn_count <= 5):
                    return await ctx.send("❌ Total buttons must be between 1 and 5. Protocol terminated.")
            except ValueError:
                return await ctx.send("❌ Please enter a valid number configuration.")

            # Step 5: Loop to gather personalized Button Labels and Emojis
            button_configs = []
            for i in range(btn_count):
                await ctx.send(f"🏷️ **BUTTON {i+1} NAME:** Enter the label text for Button #{i+1} (e.g., Verification).")
                msg_label = await self.bot.wait_for("message", check=check, timeout=None)
                label_text = msg_label.content.strip()

                await ctx.send(f"✨ **BUTTON {i+1} EMOJI:** Send the emoji bound to Button #{i+1} (Standard or custom).")
                msg_emoji = await self.bot.wait_for("message", check=check, timeout=None)
                raw_emoji = msg_emoji.content.strip()

                if raw_emoji.startswith("<:") or raw_emoji.startswith("<a:"):
                    try:
                        resolved_emoji = discord.PartialEmoji.from_str(raw_emoji)
                    except Exception:
                        resolved_emoji = raw_emoji
                else:
                    resolved_emoji = raw_emoji

                button_configs.append({"label": label_text, "emoji": str(resolved_emoji)})

            # Execute Config Mapping Pushes
            with sqlite3.connect("database.db") as conn:
                conn.execute("""
                    INSERT INTO ticket_config (guild_id, lobby_channel) 
                    VALUES (?, ?) 
                    ON CONFLICT(guild_id) DO UPDATE SET lobby_channel=excluded.lobby_channel
                """, (ctx.guild.id, target_channel.id))
                
                # --- ADDED: SAVE BUTTON CONFIGS FOR PERSISTENCE ---
                conn.execute("DELETE FROM ticket_buttons WHERE guild_id = ?", (ctx.guild.id,))
                for idx, cfg in enumerate(button_configs):
                    conn.execute("INSERT INTO ticket_buttons VALUES (?, ?, ?, ?)", (ctx.guild.id, idx, cfg['label'], cfg['emoji']))
                    
                conn.commit()

            # Build Custom Embed Core Layout
            embed = discord.Embed(
                title="📩 Contact the Staff",
                description=lobby_desc,
                color=0x8B0000
            )
            embed.set_footer(text="Echo Ticket System | Secure Neural Link")
            
            # Map custom picture choices dynamically if selected
            if ticket_image_url:
                embed.set_image(url=ticket_image_url)

            # Generate the personalized layout view
            view = TicketLobbyView(button_configs)
            await target_channel.send(embed=embed, view=view)
            await ctx.send(f"✅ **SUCCESS:** Personalized Ticket Lobby successfully engineered and deployed inside {target_channel.mention}")

        except asyncio.TimeoutError:
            await ctx.send("⌛ **TIMEOUT:** Configuration sequence timed out. Restart with `!ticket`.")

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

class TicketCustomButton(discord.ui.Button):
    def __init__(self, label, emoji, index):
        # Dynamically map the button features to a persistent generic custom_id structure
        super().__init__(style=discord.ButtonStyle.secondary, label=label, emoji=emoji, custom_id=f"tkt_customized:{index}")
        self.category_slug = label.lower().replace(" ", "_")
        # --- ADDED: ENSURE GLOBALLY UNIQUE CUSTOM ID FOR PERSISTENCE ACROSS REFRESHES ---
        self.custom_id = f"tkt_customized:{index}:{self.category_slug}"

    async def callback(self, interaction: discord.Interaction):
        await self.view.create_ticket(interaction, self.category_slug)

class TicketLobbyView(discord.ui.View):
    def __init__(self, button_configs=None):
        super().__init__(timeout=None)
        # If initialized by setup loop or persistent register reload
        if button_configs:
            for idx, cfg in enumerate(button_configs):
                self.add_item(TicketCustomButton(label=cfg['label'], emoji=cfg['emoji'], index=idx))

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
            name=f"ticket{current_num}-{category.replace('_', '-')}",
            overwrites=overwrites,
            category=target_category,
            topic=f"Asset ID: {interaction.user.id} | Session #{current_num}"
        )

        # --- MODIFIED: PING THE ROLE ---
        ping_content = f"{interaction.user.mention} | {admin_role.mention if admin_role else ''}"

        # Send greeting in ticket
        tkt_embed = discord.Embed(
            title=f"⛓️ SESSION #{current_num} INITIATED: {category.upper().replace('_', ' ')}",
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
            log.add_field(name="Category", value=category.upper().replace('_', ' '), inline=True)
            log.add_field(name="Channel", value=ticket_channel.mention, inline=False)
            await admin_chan.send(embed=log)

        await interaction.response.send_message(f"✅ Session opened: {ticket_channel.mention}", ephemeral=True)

class ArchiveViewer(discord.ui.View):
    # MODIFIED: Default ticket_id to None to allow setup initialization
    def __init__(self, ticket_id=None):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="VIEW DATA", style=discord.ButtonStyle.secondary, emoji="👁️", custom_id="persistent_view_archive")
    async def view_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        # --- ADDED: RECOVER ID IF VIEW WAS RESTARTED ---
        if not getattr(self, 'ticket_id', None) and interaction.message.embeds:
            try:
                self.ticket_id = interaction.message.embeds[0].description.split("**")[1]
            except Exception:
                pass
                
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
    
    # --- ADDED: DYNAMIC PERSISTENCE LOADER ---
    try:
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            
            # 1. Restore Reaction Roles mappings directly onto bot
            rr_rows = conn.execute("SELECT message_id, emoji, role_id FROM reaction_roles").fetchall()
            rr_dict = {}
            for row in rr_rows:
                msg_id = row["message_id"]
                if msg_id not in rr_dict:
                    rr_dict[msg_id] = {}
                rr_dict[msg_id][row["emoji"]] = row["role_id"]
            
            for msg_id, mappings in rr_dict.items():
                bot.add_view(ReactionRoleView(mappings), message_id=msg_id)
                
            # 2. Restore dynamically configured Ticket Lobbies
            try:
                guilds = conn.execute("SELECT DISTINCT guild_id FROM ticket_buttons").fetchall()
                for g in guilds:
                    guild_id = g["guild_id"]
                    btns = conn.execute("SELECT label, emoji, btn_index FROM ticket_buttons WHERE guild_id = ? ORDER BY btn_index", (guild_id,)).fetchall()
                    configs = [{"label": b["label"], "emoji": b["emoji"]} for b in btns]
                    if configs:
                        bot.add_view(TicketLobbyView(configs))
            except sqlite3.OperationalError:
                pass # Ignores missing table if booting entirely for the very first time
                
    except Exception as e:
        print(f"Failed to restore persistent views: {e}")

    # Required for persistent buttons to work after restart
    # MODIFIED: Passing placeholder lists to allow registration validation on system start without static buttons crashing
    bot.add_view(TicketLobbyView())
    bot.add_view(TicketControls())
    bot.add_view(DesignerLobby())
    bot.add_view(ArchiveViewer()) # ADDED: Ensure archives remain viewable permanently
