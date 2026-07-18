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
        # --- ADDED: TRACK ACTIVE SETUPS TO PREVENT GHOST LOCKOUTS ---
        self.active_setups = {}
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
            
            # --- UPDATED: TICKET BUTTONS TABLE FOR PERSISTENCE ACROSS RESTARTS TO TRACK DEPARTMENT ROLES ---
            # NOTE: staff_role_id changed to TEXT to natively accept comma-separated multiple role entries safely
            conn.execute("CREATE TABLE IF NOT EXISTS ticket_buttons (guild_id INTEGER, btn_index INTEGER, label TEXT, emoji TEXT, staff_role_id TEXT)")
            
            # DATABASE RESET CHECK FOR NEW COLUMN UPDATES
            cursor_btn = conn.execute("PRAGMA table_info(ticket_buttons)")
            btn_columns = [col[1] for col in cursor_btn.fetchall()]
            if "staff_role_id" not in btn_columns:
                conn.execute("ALTER TABLE ticket_buttons ADD COLUMN staff_role_id TEXT")
            
            conn.commit()

    @commands.command(name="setroles")
    @commands.has_permissions(administrator=True)
    async def setroles(self, ctx):
        """Guided step-by-step setup for reaction roles."""
        
        # --- ADDED: REGISTER NEW SESSION TO AUTO-KILL OLD GHOST ONES ---
        self.active_setups[ctx.author.id] = ctx.message.id
        
        def check(m):
            # --- ADDED: GHOST KILLER AND MANUAL CANCEL ---
            if self.active_setups.get(ctx.author.id) != ctx.message.id:
                raise asyncio.TimeoutError()
            if m.content.lower() == 'cancel' and m.author == ctx.author and m.channel == ctx.channel:
                raise asyncio.TimeoutError()
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            # Step 1: Target Channel
            await ctx.send("🎯 **STEP 1:** Mention the **channel** where the rules should be sent (e.g., #rules).")
            # --- ADDED: EXPLICIT CANCELLATION INSTRUCTION ---
            await ctx.send("*(Type `cancel` at any point during this process to safely abort and restart)*")
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
        
        # --- ADDED: REGISTER NEW SESSION TO AUTO-KILL OLD GHOST ONES ---
        self.active_setups[ctx.author.id] = ctx.message.id
        
        # --- ADDED: GARBAGE CONTAINER MATRIX FOR AUTO-PURGING ---
        setup_garbage = [ctx.message]

        def check(m):
            if self.active_setups.get(ctx.author.id) != ctx.message.id:
                raise asyncio.TimeoutError()
            if m.content.lower() == 'cancel' and m.author == ctx.author and m.channel == ctx.channel:
                raise asyncio.TimeoutError()
            return m.author == ctx.author and m.channel == ctx.channel

        async def send_tracked_step(text):
            m = await ctx.send(text)
            setup_garbage.append(m)
            return m

        try:
            # Step 1: Target Lobby Channel
            await send_tracked_step("🎯 **STEP 1:** Mention the **channel** where the ticket lobby panel should be sent (e.g., #support).")
            await send_tracked_step("*(Type `cancel` at any point during this process to safely abort and clean up)*")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            setup_garbage.append(msg)
            target_channel = msg.channel_mentions[0] if msg.channel_mentions else None
            if not target_channel:
                for g_msg in setup_garbage:
                    try: await g_msg.delete()
                    except Exception: pass
                return await ctx.send("❌ Invalid channel. Cancelled protocol.")

            # --- ADDED STEP: Define Admin Logging Archive Target ---
            await send_tracked_step("🗄️ **STEP 2:** Mention the **admin logging channel** where sealed ticket logs and transcripts should be sent (e.g., #ticket-logs).")
            msg_log_chan = await self.bot.wait_for("message", check=check, timeout=None)
            setup_garbage.append(msg_log_chan)
            admin_logging_channel = msg_log_chan.channel_mentions[0] if msg_log_chan.channel_mentions else None
            if not admin_logging_channel:
                for g_msg in setup_garbage:
                    try: await g_msg.delete()
                    except Exception: pass
                return await ctx.send("❌ Invalid logging channel. Cancelled protocol.")

            # Step 3: Content Copy Design
            await send_tracked_step("📝 **STEP 3:** Type the **description copy** that will appear in your support lobby panel embed.")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            setup_garbage.append(msg)
            lobby_desc = msg.content

            # Step 4: Custom Upload/Link Selection
            await send_tracked_step("🖼️ **STEP 4:** Upload a **custom image attachment** or paste an image link for this panel. (Type `none` to skip).")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            setup_garbage.append(msg)
            ticket_image_url = None
            
            if msg.content.strip().lower() != "none":
                if msg.attachments:
                    ticket_image_url = msg.attachments[0].url
                elif msg.content.startswith("http"):
                    ticket_image_url = msg.content.strip()

            # Step 5: Button Quantity Personalization
            await send_tracked_step("🔢 **STEP 5:** How many **custom buttons** would you like to build for this lobby? (Maximum of 5).")
            msg = await self.bot.wait_for("message", check=check, timeout=None)
            setup_garbage.append(msg)
            try:
                btn_count = int(msg.content.strip())
                if not (1 <= btn_count <= 5):
                    for g_msg in setup_garbage:
                        try: await g_msg.delete()
                        except Exception: pass
                    return await ctx.send("❌ Total buttons must be between 1 and 5. Protocol terminated.")
            except ValueError:
                for g_msg in setup_garbage:
                    try: await g_msg.delete()
                    except Exception: pass
                return await ctx.send("❌ Please enter a valid number configuration.")

            # Step 6: Loop to gather personalized Button Labels, Emojis, and Multi-Role Privacies
            button_configs = []
            for i in range(btn_count):
                await send_tracked_step(f"🏷️ **BUTTON {i+1} NAME:** Enter the label text for Button #{i+1} (e.g., Verification).")
                msg_label = await self.bot.wait_for("message", check=check, timeout=None)
                setup_garbage.append(msg_label)
                label_text = msg_label.content.strip()

                await send_tracked_step(f"✨ **BUTTON {i+1} EMOJI:** Send the emoji bound to Button #{i+1} (Standard or custom).")
                msg_emoji = await self.bot.wait_for("message", check=check, timeout=None)
                setup_garbage.append(msg_emoji)
                raw_emoji = msg_emoji.content.strip()

                if raw_emoji.startswith("<:") or raw_emoji.startswith("<a:"):
                    try: resolved_emoji = discord.PartialEmoji.from_str(raw_emoji)
                    except Exception: resolved_emoji = raw_emoji
                else:
                    resolved_emoji = raw_emoji

                await send_tracked_step(f"🛡️ **BUTTON {i+1} STAFF PRIVACY:** Mention **all specific roles** allowed to see and ping tickets via this button (e.g., @Moderators @SupportTeam).")
                msg_role = await self.bot.wait_for("message", check=check, timeout=None)
                setup_garbage.append(msg_role)
                
                staff_roles_extracted = msg_role.role_mentions
                if not staff_roles_extracted:
                    for g_msg in setup_garbage:
                        try: await g_msg.delete()
                        except Exception: pass
                    return await ctx.send("❌ Invalid roles selected. Setup process canceled.")

                staff_roles_string = ",".join([str(r.id) for r in staff_roles_extracted])
                button_configs.append({"label": label_text, "emoji": str(resolved_emoji), "staff_role_id": staff_roles_string})

            # Execute Config Mapping Pushes
            with sqlite3.connect("database.db") as conn:
                # FIXED PERSISTENCE MATRIX: Use ticket_count=ticket_config.ticket_count on conflict to ensure the counter is NEVER overridden or reset by lobby alterations
                conn.execute("""
                    INSERT INTO ticket_config (guild_id, lobby_channel, admin_channel, ticket_count) 
                    VALUES (?, ?, ?, 0) 
                    ON CONFLICT(guild_id) DO UPDATE SET 
                        lobby_channel=excluded.lobby_channel,
                        admin_channel=excluded.admin_channel,
                        ticket_count=ticket_config.ticket_count
                """, (ctx.guild.id, target_channel.id, admin_logging_channel.id))
                
                conn.execute("DELETE FROM ticket_buttons WHERE guild_id = ?", (ctx.guild.id,))
                for idx, cfg in enumerate(button_configs):
                    conn.execute("INSERT INTO ticket_buttons VALUES (?, ?, ?, ?, ?)", (ctx.guild.id, idx, cfg['label'], cfg['emoji'], cfg['staff_role_id']))
                    
                conn.commit()

            # Build Custom Embed Core Layout
            embed = discord.Embed(
                title="📩 Contact the Staff",
                description=lobby_desc,
                color=0x8B0000
            )
            embed.set_footer(text="Echo Ticket System | Secure Neural Link")
            
            if ticket_image_url:
                embed.set_image(url=ticket_image_url)

            view = TicketLobbyView(button_configs)
            await target_channel.send(embed=embed, view=view)
            
            for g_msg in setup_garbage:
                try: await g_msg.delete()
                except Exception: pass

            await ctx.send(f"✅ **SUCCESS:** Personalized Ticket Lobby designed and deployed inside {target_channel.mention}. Transcripts assigned to {admin_logging_channel.mention}.")

        except asyncio.TimeoutError:
            for g_msg in setup_garbage:
                try: await g_msg.delete()
                except Exception: pass
            await ctx.send("⌛ **TIMEOUT:** Configuration sequence timed out or manually canceled. Cleaned setup logs.")

    @commands.command(name="ticketadmin")
    @commands.has_permissions(administrator=True)
    async def set_ticket_admin(self, ctx, role: discord.Role):
        """Sets the Default Admin Role and configures the tracking database."""
        with sqlite3.connect("database.db") as conn:
            conn.execute("""
                INSERT INTO ticket_config (guild_id, admin_role_id) 
                VALUES (?, ?) 
                ON CONFLICT(guild_id) DO UPDATE SET 
                    admin_role_id=excluded.admin_role_id,
                    ticket_count=ticket_config.ticket_count
            """, (ctx.guild.id, role.id))
            conn.commit()

        await ctx.send(f"✅ Default Admin Role Persisted: {role.mention}. Base matrix updated.")

    @commands.command(name="ticketcategory")
    @commands.has_permissions(administrator=True)
    async def set_ticket_category(self, ctx, category_id: int):
        """Sets the category ID where ticket channels will be created."""
        with sqlite3.connect("database.db") as conn:
            conn.execute("""
                INSERT INTO ticket_config (guild_id, category_id) 
                VALUES (?, ?) 
                ON CONFLICT(guild_id) DO UPDATE SET category_id=excluded.category_id, ticket_count=ticket_config.ticket_count
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

    @commands.command(name="ticketnumber")
    @commands.has_permissions(administrator=True)
    async def ticketnumber(self, ctx, count: int):
        """Manually sets the ticket counter configuration to a specific value."""
        with sqlite3.connect("database.db") as conn:
            conn.execute("""
                INSERT INTO ticket_config (guild_id, ticket_count) 
                VALUES (?, ?) 
                ON CONFLICT(guild_id) DO UPDATE SET ticket_count=excluded.ticket_count
            """, (ctx.guild.id, count))
            conn.commit()
        await ctx.send(f"✅ Ticket number matrix calibrated. Next execution will register as session **#{count + 1}**.")

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
    def __init__(self, label, emoji, index, staff_role_id=None):
        self.category_slug = label.lower().replace(" ", "_")
        self.staff_role_id = str(staff_role_id) if staff_role_id else None
        # Store raw label for dynamic temporary category generation titles
        self.raw_label = label
        super().__init__(style=discord.ButtonStyle.secondary, label=label, emoji=emoji, custom_id=f"tkt_customized:{index}:{self.category_slug}")

    async def callback(self, interaction: discord.Interaction):
        await self.view.create_ticket(interaction, self.category_slug, self.staff_role_id, self.raw_label)

class TicketLobbyView(discord.ui.View):
    def __init__(self, button_configs=None):
        super().__init__(timeout=None)
        if button_configs:
            for idx, cfg in enumerate(button_configs):
                self.add_item(TicketCustomButton(label=cfg['label'], emoji=cfg['emoji'], index=idx, staff_role_id=cfg.get('staff_role_id')))

    async def create_ticket(self, interaction: discord.Interaction, category: str, staff_role_id: str = None, raw_label: str = "Support"):
        # --- FIX: ACKNOWLEDGE INTERACTION IMMEDIATELY TO PREVENT "INTERACTION FAILED" LOGGING ---
        await interaction.response.defer(ephemeral=True)

        # --- SAFE ADVANCED AUTO-HEALING MATRIX PROTOCOL START ---
        highest_found_count = 0
        
        # 1. Inspect local configuration registry state if existing
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            config = conn.execute("SELECT * FROM ticket_config WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
            if config and config['ticket_count']:
                if config['ticket_count'] > highest_found_count:
                    highest_found_count = config['ticket_count']
                    
            # 2. Complete deep inspection parse across all past historical sealed logs in archive tables
            try:
                archive_rows = conn.execute("SELECT ticket_id FROM ticket_archives WHERE guild_id = ?", (interaction.guild.id,)).fetchall()
                for r in archive_rows:
                    try:
                        arch_num = int(r['ticket_id'].split('-')[0])
                        if arch_num > highest_found_count:
                            highest_found_count = arch_num
                    except Exception:
                        pass
            except Exception:
                pass

        # 3. Dynamic real-time execution scanning of live server channel networks (Ensures absolute persistence)
        for cat_obj in interaction.guild.categories:
            for channel in cat_obj.text_channels:
                try:
                    chan_num = int(channel.name.split('-')[0])
                    if chan_num > highest_found_count:
                        highest_found_count = chan_num
                except Exception:
                    pass

        # Establish absolute un-wipeable true sequential counter position
        current_num = highest_found_count + 1

        # Save absolute validated sequential coordinate permanently back down to DB
        with sqlite3.connect("database.db") as conn:
            conn.execute("""
                INSERT INTO ticket_config (guild_id, ticket_count) 
                VALUES (?, ?) 
                ON CONFLICT(guild_id) DO UPDATE SET ticket_count = ?
            """, (interaction.guild.id, current_num, current_num))
            conn.commit()
            config = conn.execute("SELECT * FROM ticket_config WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
        # --- SAFE ADVANCED AUTO-HEALING MATRIX PROTOCOL END ---

        chosen_staff_string = staff_role_id if staff_role_id else str(config['admin_role_id']) if config['admin_role_id'] else ""
        parsed_role_ids = [int(r.strip()) for r in chosen_staff_string.split(",") if r.strip().isdigit()]

        # --- DYNAMIC CATEGORY ROUTING MATCHING THE TEXT LABEL OF CLICKED BUTTON ---
        cat_name = raw_label
        target_category = discord.utils.get(interaction.guild.categories, name=cat_name)
        
        if not target_category:
            overwrites_cat = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            for r_id in parsed_role_ids:
                r_obj = interaction.guild.get_role(r_id)
                if r_obj:
                    overwrites_cat[r_obj] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                
            target_category = await interaction.guild.create_category(name=cat_name, overwrites=overwrites_cat)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ping_mentions = []
        for r_id in parsed_role_ids:
            r_obj = interaction.guild.get_role(r_id)
            if r_obj:
                overwrites[r_obj] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                ping_mentions.append(r_obj.mention)
        
        ticket_channel = await interaction.guild.create_text_channel(
            name=f"{current_num}-{interaction.user.name}-{category.replace('_', '-')}",
            overwrites=overwrites,
            category=target_category,
            topic=f"Asset ID: {interaction.user.id} | Session #{current_num}"
        )

        ping_content = f"{interaction.user.mention}"
        if ping_mentions:
            ping_content += f" | {' '.join(ping_mentions)}"

        tkt_embed = discord.Embed(
            title=f"⛓️ SESSION #{current_num} INITIATED: {category.upper().replace('_', ' ')}",
            description=f"Welcome {interaction.user.mention}. State your business clearly. "
                        "The Appointed Department has been notified of your presence.",
            color=0x8B0000
        )
        tkt_embed.set_footer(text="The Master is watching.")
        
        await ticket_channel.send(content=ping_content, embed=tkt_embed, view=TicketControls(staff_role_id=chosen_staff_string))

        admin_chan = interaction.guild.get_channel(config['admin_channel'])
        if admin_chan:
            log = discord.Embed(title=f"🚨 NEW SESSION OPENED: #{current_num}", color=0xFFD700)
            log.add_field(name="Asset", value=interaction.user.mention, inline=True)
            log.add_field(name="Category", value=category.upper().replace('_', ' '), inline=True)
            log.add_field(name="Assigned Department", value=", ".join(ping_mentions) if ping_mentions else "Default Staff", inline=True)
            log.add_field(name="Channel", value=ticket_channel.mention, inline=False)
            await admin_chan.send(embed=log)

        # --- UPDATED: DELIVER RESPONSE VIA FOLLOWUP DUETO THE INITIAL DEFERRAL SYSTEM ---
        await interaction.followup.send(f"✅ Session opened: {ticket_channel.mention}", ephemeral=True)

class ArchiveViewer(discord.ui.View):
    def __init__(self, ticket_id=None):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="VIEW DATA", style=discord.ButtonStyle.secondary, emoji="👁️", custom_id="persistent_view_archive")
    async def view_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not getattr(self, 'ticket_id', None) and interaction.message.embeds:
            try:
                self.ticket_id = interaction.message.embeds[0].description.split("**")[1]
            except Exception:
                pass
                
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT content FROM ticket_archives WHERE ticket_id = ?", (self.ticket_id,)).fetchone()
        
        if row:
            buffer = io.BytesIO(row['content'].encode('utf-8'))
            await interaction.response.send_message(f"📑 **NEURAL RECOVERY:** Session `{self.ticket_id}`", file=discord.File(buffer, filename=f"{self.ticket_id}.txt"), ephemeral=True)
        else:
            await interaction.response.send_message("❌ Data block corrupted or missing.", ephemeral=True)

class TicketControls(discord.ui.View):
    def __init__(self, staff_role_id=None):
        super().__init__(timeout=None)
        self.staff_role_id = str(staff_role_id) if staff_role_id else None

    @discord.ui.button(label="CLAIM TICKET", style=discord.ButtonStyle.success, emoji="🙋‍♂️", custom_id="tkt:claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            opener_name = interaction.channel.name.split("-")[1]
            opener = discord.utils.get(interaction.guild.members, name=opener_name)
        except Exception:
            opener = None

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        if opener:
            overwrites[opener] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)

        await interaction.channel.edit(
            overwrites=overwrites,
            topic=f"Claimed by: {interaction.user.display_name} | Handler ID: {interaction.user.id}"
        )

        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"💼 **TICKET ASSIGNED:** {interaction.user.mention} has claimed this session and will take care of it.")

    @discord.ui.button(label="PING ADMINS", style=discord.ButtonStyle.primary, emoji="🔔", custom_id="tkt:ping_admins")
    async def ping_admins(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_role_string = self.staff_role_id
        
        if not target_role_string:
            try:
                category_slug = interaction.channel.name.split("-")[-1].replace("-", "_")
                with sqlite3.connect("database.db") as conn:
                    conn.row_factory = sqlite3.Row
                    res = conn.execute("SELECT staff_role_id FROM ticket_buttons WHERE label LIKE ? LIMIT 1", (category_slug.replace("_", " "),)).fetchone()
                    if res:
                        target_role_string = res["staff_role_id"]
            except Exception:
                pass

        if not target_role_string:
            with sqlite3.connect("database.db") as conn:
                conn.row_factory = sqlite3.Row
                config = conn.execute("SELECT admin_role_id FROM ticket_config WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
                if config and config["admin_role_id"]:
                    target_role_string = str(config["admin_role_id"])

        if target_role_string:
            role_ids = [int(r.strip()) for r in target_role_string.split(",") if r.strip().isdigit()]
            valid_mentions = []
            
            for r_id in role_ids:
                staff_role_obj = interaction.guild.get_role(r_id)
                if staff_role_obj:
                    valid_mentions.append(staff_role_obj.mention)

            if valid_mentions:
                return await interaction.response.send_message(
                    f"⚠️ {' '.join(valid_mentions)} **ATTENTION REQUIRED:** Appointed support reinforcement has been signaled immediately!", 
                    allowed_mentions=discord.AllowedMentions(roles=True)
                )

        await interaction.response.send_message("❌ Error: Assigned department role matrix could not be resolved.", ephemeral=True)

    @discord.ui.button(label="CLOSE SESSION", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="tkt:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        try:
            transcript = f"--- BLACK BOX TRANSCRIPT: {interaction.channel.name} ---\n"
            transcript += f"Asset: {interaction.channel.name.split('-')[-1]}\n"
            transcript += f"Sealed on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            transcript += "-"*40 + "\n\n"
            
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                time = message.created_at.strftime('%H:%M')
                content = message.clean_content if message.content else "[Attachment/Embed]"
                transcript += f"[{time}] {message.author.display_name}: {content}\n"

            ticket_id = interaction.channel.name
            with sqlite3.connect("database.db") as conn:
                conn.execute("INSERT OR REPLACE INTO ticket_archives VALUES (?, ?, ?, ?, ?, ?)", 
                             (ticket_id, interaction.guild.id, interaction.user.display_name, "SESSION", transcript, datetime.now().strftime('%Y-%m-%d %H:%M')))
                conn.commit()

            with sqlite3.connect("database.db") as conn:
                conn.row_factory = sqlite3.Row
                config = conn.execute("SELECT admin_channel FROM ticket_config WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
            
            # --- TRANSCRIPT SHIPPED DIRECTLY TO YOUR PREDETERMINED ADMIN LOGGING CHANNEL MATRIX ---
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

        await interaction.followup.send("⛓️ *Session sealing. Data stored in Black Box. Purging in 5 seconds...*")
        await asyncio.sleep(5)
        await interaction.channel.delete()

async def setup(bot):
    await bot.add_cog(ReactionRoleSystem(bot))
    
    try:
        with sqlite3.connect("database.db") as conn:
            conn.row_factory = sqlite3.Row
            
            rr_rows = conn.execute("SELECT message_id, emoji, role_id FROM reaction_roles").fetchall()
            rr_dict = {}
            for row in rr_rows:
                msg_id = row["message_id"]
                if msg_id not in rr_dict:
                    rr_dict[msg_id] = {}
                rr_dict[msg_id][row["emoji"]] = row["role_id"]
            
            for msg_id, mappings in rr_dict.items():
                bot.add_view(ReactionRoleView(mappings), message_id=msg_id)
                
            try:
                guilds = conn.execute("SELECT DISTINCT guild_id FROM ticket_buttons").fetchall()
                for g in guilds:
                    guild_id = g["guild_id"]
                    btns = conn.execute("SELECT label, emoji, btn_index, staff_role_id FROM ticket_buttons WHERE guild_id = ? ORDER BY btn_index", (guild_id,)).fetchall()
                    configs = [{"label": b["label"], "emoji": b["emoji"], "staff_role_id": str(b["staff_role_id"])} for b in btns]
                    if configs:
                        bot.add_view(TicketLobbyView(configs))
            except sqlite3.OperationalError:
                pass
                
    except Exception as e:
        print(f"Failed to restore persistent views: {e}")

    bot.add_view(TicketLobbyView())
    bot.add_view(TicketControls())
    bot.add_view(DesignerLobby())
    bot.add_view(ArchiveViewer())
