
import discord
from discord.ext import commands
import sqlite3
import asyncio
import os
import io
import json
from datetime import datetime

DB_PATH = "database.db"
ticket_counter_lock = asyncio.Lock()


# ---------------------------------------------------------
# SHARED HELPERS
# ---------------------------------------------------------

def get_staff_role_ids(channel, fallback=None):
    """Read staff role IDs stored in the ticket channel topic."""
    role_string = fallback or ""

    if channel and channel.topic:
        for part in channel.topic.split("|"):
            part = part.strip()
            if part.startswith("Staff Roles:"):
                role_string = part.replace("Staff Roles:", "", 1).strip()
                break

    return [
        int(role_id.strip())
        for role_id in role_string.split(",")
        if role_id.strip().isdigit()
    ]


def get_topic_value(channel, key):
    """Read a value from a ticket channel topic."""
    if not channel or not channel.topic:
        return None

    for part in channel.topic.split("|"):
        part = part.strip()
        if part.startswith(key + ":"):
            return part.split(":", 1)[1].strip()

    return None


def is_ticket_staff(interaction):
    """Check whether the interacting member is an administrator or assigned staff."""
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False

    if interaction.user.guild_permissions.administrator:
        return True

    staff_ids = get_staff_role_ids(interaction.channel)

    return any(role.id in staff_ids for role in interaction.user.roles)


async def interaction_error(interaction, error):
    """Safely report an interaction error without double-responding."""
    print(f"Interaction error: {error}")

    message = "❌ Something went wrong while processing that action. Please try again."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except Exception as response_error:
        print(f"Could not send interaction error response: {response_error}")


# ---------------------------------------------------------
# DESIGNER LOBBY
# ---------------------------------------------------------

class DesignerLobby(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="DESIGNER SUITE",
        style=discord.ButtonStyle.primary,
        custom_id="designer_suite_permanent"
    )
    async def open_suite(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🛠️ Designer Suite access initiated. Please use `!setroles` to configure new links.",
            ephemeral=True
        )


# ---------------------------------------------------------
# REACTION ROLES
# ---------------------------------------------------------

class ReactionRoleButton(discord.ui.Button):
    def __init__(self, emoji, role_id, count=0):
        label_text = f"({count})" if count > 0 else None

        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=label_text,
            emoji=emoji,
            custom_id=f"rr:{role_id}"
        )

        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if not interaction.guild or not isinstance(interaction.user, discord.Member):
                return await interaction.response.send_message(
                    "❌ This button can only be used inside a server.",
                    ephemeral=True
                )

            await interaction.response.defer(ephemeral=True)

            role = interaction.guild.get_role(int(self.role_id))

            if not role:
                return await interaction.followup.send(
                    "❌ Error: Role not found.",
                    ephemeral=True
                )

            if role >= interaction.guild.me.top_role:
                return await interaction.followup.send(
                    "❌ The bot cannot manage this role because of its role hierarchy.",
                    ephemeral=True
                )

            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                response = f"🔓 **ACCESS REVOKED:** {role.name} removed."
            else:
                await interaction.user.add_roles(role)
                response = f"🔒 **ACCESS GRANTED:** {role.name} assigned."

            await interaction.followup.send(response, ephemeral=True)

            # Refresh the displayed counter.
            try:
                updated_count = len(role.members)
                self.label = f"({updated_count})" if updated_count > 0 else None
                await interaction.message.edit(view=self.view)
            except Exception as edit_error:
                print(f"Reaction role counter refresh failed: {edit_error}")

        except Exception as e:
            await interaction_error(interaction, e)


class ReactionRoleView(discord.ui.View):
    def __init__(self, mappings, guild=None):
        super().__init__(timeout=None)

        for emoji, role_id in mappings.items():
            initial_count = 0

            if guild:
                role_obj = guild.get_role(int(role_id))
                if role_obj:
                    initial_count = len(role_obj.members)

            self.add_item(
                ReactionRoleButton(emoji, role_id, count=initial_count)
            )


# ---------------------------------------------------------
# MAIN COG
# ---------------------------------------------------------

class ReactionRoleSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_setups = {}
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:

            conn.execute("""
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    message_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS ticket_config (
                    guild_id INTEGER PRIMARY KEY,
                    lobby_channel INTEGER,
                    admin_channel INTEGER,
                    category_id INTEGER,
                    admin_role_id INTEGER,
                    ticket_count INTEGER DEFAULT 0
                )
            """)

            cursor = conn.execute("PRAGMA table_info(ticket_config)")
            columns = [column[1] for column in cursor.fetchall()]

            if "admin_role_id" not in columns:
                conn.execute(
                    "ALTER TABLE ticket_config ADD COLUMN admin_role_id INTEGER"
                )

            conn.execute("""
                CREATE TABLE IF NOT EXISTS ticket_archives (
                    ticket_id TEXT PRIMARY KEY,
                    guild_id INTEGER,
                    asset_name TEXT,
                    category TEXT,
                    content TEXT,
                    timestamp TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS autorole_config (
                    guild_id INTEGER PRIMARY KEY,
                    role_id INTEGER
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS ticket_buttons (
                    guild_id INTEGER,
                    btn_index INTEGER,
                    label TEXT,
                    emoji TEXT,
                    staff_role_id TEXT
                )
            """)

            cursor_btn = conn.execute("PRAGMA table_info(ticket_buttons)")
            btn_columns = [col[1] for col in cursor_btn.fetchall()]

            if "staff_role_id" not in btn_columns:
                conn.execute(
                    "ALTER TABLE ticket_buttons ADD COLUMN staff_role_id TEXT"
                )

            # NEW: Persist the actual ticket lobby message IDs.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ticket_panels (
                    guild_id INTEGER,
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER
                )
            """)

            conn.commit()

    # -----------------------------------------------------
    # REACTION ROLE SETUP
    # -----------------------------------------------------

    @commands.command(name="setroles")
    @commands.has_permissions(administrator=True)
    async def setroles(self, ctx):
        """Guided step-by-step setup for reaction roles."""

        self.active_setups[ctx.author.id] = ctx.message.id

        def check(m):
            if self.active_setups.get(ctx.author.id) != ctx.message.id:
                raise asyncio.TimeoutError()

            if (
                m.content.lower() == "cancel"
                and m.author == ctx.author
                and m.channel == ctx.channel
            ):
                raise asyncio.TimeoutError()

            return m.author == ctx.author and m.channel == ctx.channel

        try:
            await ctx.send(
                "🎯 **STEP 1:** Mention the channel where the rules should be sent (e.g., #rules)."
            )
            await ctx.send(
                "*(Type `cancel` at any point during this process to safely abort and restart)*"
            )

            msg = await self.bot.wait_for(
                "message", check=check, timeout=None
            )

            target_channel = msg.channel_mentions[0] if msg.channel_mentions else None

            if not target_channel:
                return await ctx.send("❌ Invalid channel. Restart the command.")

            await ctx.send(
                "🔢 **STEP 2:** How many reaction roles would you like to add? (Maximum of 25)."
            )

            msg = await self.bot.wait_for(
                "message", check=check, timeout=None
            )

            try:
                rr_count = int(msg.content.strip())

                if not 1 <= rr_count <= 25:
                    return await ctx.send(
                        "❌ Total reaction roles must be between 1 and 25."
                    )

            except ValueError:
                return await ctx.send("❌ Please enter a valid number.")

            mappings = {}
            db_mappings = []

            for i in range(rr_count):
                await ctx.send(
                    f"👤 **STEP 3.{i+1}:** Mention the role to be granted for button #{i+1}."
                )

                msg = await self.bot.wait_for(
                    "message", check=check, timeout=None
                )

                target_role = msg.role_mentions[0] if msg.role_mentions else None

                if not target_role:
                    return await ctx.send("❌ Invalid role. Restart the command.")

                await ctx.send(
                    f"⭐ **STEP 4.{i+1}:** Send the emoji for {target_role.name}."
                )

                msg = await self.bot.wait_for(
                    "message", check=check, timeout=None
                )

                raw_content = msg.content.strip()

                if raw_content.startswith("<:") or raw_content.startswith("<a:"):
                    try:
                        target_emoji = discord.PartialEmoji.from_str(raw_content)
                    except Exception:
                        return await ctx.send(
                            "❌ Failed to process the custom emoji."
                        )
                else:
                    target_emoji = raw_content

                mappings[target_emoji] = target_role.id
                db_mappings.append((str(target_emoji), target_role.id))

            await ctx.send(
                "📝 **STEP 5:** Type the message/rules that will appear in the embed."
            )

            msg = await self.bot.wait_for(
                "message", check=check, timeout=None
            )

            rules_content = msg.content

            if len(rules_content) > 4096:
                await ctx.send(
                    f"⚠️ Text too large ({len(rules_content)} chars). Cutting to fit."
                )
                rules_content = rules_content[:4090] + "..."

            await ctx.send(
                "🖼️ **STEP 6:** Upload a .jpg image or paste an image URL. Type `none` to skip."
            )

            msg = await self.bot.wait_for(
                "message", check=check, timeout=None
            )

            embed_image_url = None

            if msg.content.strip().lower() != "none":
                if msg.attachments:
                    embed_image_url = msg.attachments[0].url
                elif msg.content.startswith("http"):
                    embed_image_url = msg.content.strip()

            embed = discord.Embed(
                title="🧬 NEURAL LINK: PROTOCOL ESTABLISHED",
                description=rules_content,
                color=0xFF0000
            )

            embed.set_footer(text="Echo Protocol | Role Management")

            if embed_image_url:
                embed.set_image(url=embed_image_url)

            view = ReactionRoleView(mappings, guild=ctx.guild)

            try:
                final_msg = await target_channel.send(embed=embed, view=view)
            except discord.HTTPException as e:
                return await ctx.send(
                    f"❌ **DEPLOYMENT FAILED:** {e}"
                )

            with sqlite3.connect(DB_PATH) as conn:
                for db_emoji_str, db_role_id in db_mappings:
                    conn.execute(
                        "INSERT INTO reaction_roles VALUES (?, ?, ?)",
                        (final_msg.id, db_emoji_str, db_role_id)
                    )

                conn.commit()

            await ctx.send(
                f"✅ **SUCCESS:** Protocol deployed in {target_channel.mention} with {rr_count} options!"
            )

        except asyncio.TimeoutError:
            await ctx.send(
                "⌛ **CANCELLED:** Setup timed out or was manually cancelled. Restart with `!setroles`."
            )

        finally:
            if self.active_setups.get(ctx.author.id) == ctx.message.id:
                self.active_setups.pop(ctx.author.id, None)

    # -----------------------------------------------------
    # TICKET LOBBY SETUP
    # -----------------------------------------------------

    @commands.command(name="ticket")
    @commands.has_permissions(administrator=True)
    async def set_ticket_lobby(self, ctx):
        """Guided setup for a custom ticket lobby."""

        self.active_setups[ctx.author.id] = ctx.message.id
        setup_garbage = [ctx.message]

        def check(m):
            if self.active_setups.get(ctx.author.id) != ctx.message.id:
                raise asyncio.TimeoutError()

            if (
                m.content.lower() == "cancel"
                and m.author == ctx.author
                and m.channel == ctx.channel
            ):
                raise asyncio.TimeoutError()

            return m.author == ctx.author and m.channel == ctx.channel

        async def send_tracked_step(text):
            m = await ctx.send(text)
            setup_garbage.append(m)
            return m

        async def clean_setup():
            for g_msg in setup_garbage:
                try:
                    await g_msg.delete()
                except Exception:
                    pass

        try:
            await send_tracked_step(
                "🎯 **STEP 1:** Mention the channel where the ticket lobby panel should be sent."
            )
            await send_tracked_step(
                "*(Type `cancel` at any point to abort and clean up)*"
            )

            msg = await self.bot.wait_for(
                "message", check=check, timeout=None
            )
            setup_garbage.append(msg)

            target_channel = msg.channel_mentions[0] if msg.channel_mentions else None

            if not target_channel:
                await clean_setup()
                return await ctx.send("❌ Invalid channel. Cancelled.")

            await send_tracked_step(
                "🗄️ **STEP 2:** Mention the admin logging channel."
            )

            msg_log_chan = await self.bot.wait_for(
                "message", check=check, timeout=None
            )
            setup_garbage.append(msg_log_chan)

            admin_logging_channel = (
                msg_log_chan.channel_mentions[0]
                if msg_log_chan.channel_mentions else None
            )

            if not admin_logging_channel:
                await clean_setup()
                return await ctx.send("❌ Invalid logging channel. Cancelled.")

            await send_tracked_step(
                "📝 **STEP 3:** Type the description for the support lobby."
            )

            msg = await self.bot.wait_for(
                "message", check=check, timeout=None
            )
            setup_garbage.append(msg)
            lobby_desc = msg.content

            await send_tracked_step(
                "🖼️ **STEP 4:** Upload an image or paste an image link. Type `none` to skip."
            )

            msg = await self.bot.wait_for(
                "message", check=check, timeout=None
            )
            setup_garbage.append(msg)

            ticket_image_url = None

            if msg.content.strip().lower() != "none":
                if msg.attachments:
                    ticket_image_url = msg.attachments[0].url
                elif msg.content.startswith("http"):
                    ticket_image_url = msg.content.strip()

            await send_tracked_step(
                "🔢 **STEP 5:** How many custom buttons? (Maximum of 5)."
            )

            msg = await self.bot.wait_for(
                "message", check=check, timeout=None
            )
            setup_garbage.append(msg)

            try:
                btn_count = int(msg.content.strip())

                if not 1 <= btn_count <= 5:
                    await clean_setup()
                    return await ctx.send(
                        "❌ Total buttons must be between 1 and 5."
                    )

            except ValueError:
                await clean_setup()
                return await ctx.send("❌ Please enter a valid number.")

            button_configs = []

            for i in range(btn_count):
                await send_tracked_step(
                    f"🏷️ **BUTTON {i+1} NAME:** Enter the label for Button #{i+1}."
                )

                msg_label = await self.bot.wait_for(
                    "message", check=check, timeout=None
                )
                setup_garbage.append(msg_label)
                label_text = msg_label.content.strip()

                if not label_text:
                    await clean_setup()
                    return await ctx.send("❌ Button labels cannot be empty.")

                await send_tracked_step(
                    f"✨ **BUTTON {i+1} EMOJI:** Send the emoji."
                )

                msg_emoji = await self.bot.wait_for(
                    "message", check=check, timeout=None
                )
                setup_garbage.append(msg_emoji)
                raw_emoji = msg_emoji.content.strip()

                if raw_emoji.startswith("<:") or raw_emoji.startswith("<a:"):
                    try:
                        resolved_emoji = discord.PartialEmoji.from_str(raw_emoji)
                    except Exception:
                        resolved_emoji = raw_emoji
                else:
                    resolved_emoji = raw_emoji

                await send_tracked_step(
                    f"🛡️ **BUTTON {i+1} STAFF PRIVACY:** Mention all roles allowed to access this ticket."
                )

                msg_role = await self.bot.wait_for(
                    "message", check=check, timeout=None
                )
                setup_garbage.append(msg_role)

                staff_roles_extracted = msg_role.role_mentions

                if not staff_roles_extracted:
                    await clean_setup()
                    return await ctx.send("❌ No staff roles selected. Setup cancelled.")

                staff_roles_string = ",".join(
                    str(r.id) for r in staff_roles_extracted
                )

                button_configs.append({
                    "label": label_text,
                    "emoji": str(resolved_emoji),
                    "staff_role_id": staff_roles_string
                })

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO ticket_config
                        (guild_id, lobby_channel, admin_channel, ticket_count)
                    VALUES (?, ?, ?, 0)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        lobby_channel=excluded.lobby_channel,
                        admin_channel=excluded.admin_channel,
                        ticket_count=ticket_config.ticket_count
                """, (
                    ctx.guild.id,
                    target_channel.id,
                    admin_logging_channel.id
                ))

                conn.execute(
                    "DELETE FROM ticket_buttons WHERE guild_id = ?",
                    (ctx.guild.id,)
                )

                for idx, cfg in enumerate(button_configs):
                    conn.execute(
                        "INSERT INTO ticket_buttons VALUES (?, ?, ?, ?, ?)",
                        (
                            ctx.guild.id,
                            idx,
                            cfg["label"],
                            cfg["emoji"],
                            cfg["staff_role_id"]
                        )
                    )

                conn.commit()

            embed = discord.Embed(
                title="📩 Contact the Staff",
                description=lobby_desc,
                color=0x8B0000
            )

            embed.set_footer(text="Echo Ticket System | Secure Neural Link")

            if ticket_image_url:
                embed.set_image(url=ticket_image_url)

            view = TicketLobbyView(button_configs)
            panel_message = await target_channel.send(embed=embed, view=view)

            # Save the exact lobby message ID for startup restoration.
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO ticket_panels VALUES (?, ?, ?)",
                    (ctx.guild.id, panel_message.id, target_channel.id)
                )
                conn.commit()

            await clean_setup()

            await ctx.send(
                f"✅ **SUCCESS:** Ticket Lobby deployed in {target_channel.mention}. "
                f"Transcripts assigned to {admin_logging_channel.mention}."
            )

        except asyncio.TimeoutError:
            await clean_setup()
            await ctx.send(
                "⌛ **CANCELLED:** Configuration timed out or was manually cancelled."
            )

        except Exception as e:
            await clean_setup()
            print(f"Ticket setup error: {e}")
            await ctx.send("❌ Ticket setup failed. Check the bot console for details.")

        finally:
            if self.active_setups.get(ctx.author.id) == ctx.message.id:
                self.active_setups.pop(ctx.author.id, None)

    # -----------------------------------------------------
    # TICKET CONFIGURATION COMMANDS
    # -----------------------------------------------------

    @commands.command(name="ticketadmin")
    @commands.has_permissions(administrator=True)
    async def set_ticket_admin(self, ctx, role: discord.Role):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO ticket_config (guild_id, admin_role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    admin_role_id=excluded.admin_role_id,
                    ticket_count=ticket_config.ticket_count
            """, (ctx.guild.id, role.id))
            conn.commit()

        await ctx.send(
            f"✅ Default Admin Role Persisted: {role.mention}."
        )

    @commands.command(name="ticketcategory")
    @commands.has_permissions(administrator=True)
    async def set_ticket_category(self, ctx, category_id: int):
        category = ctx.guild.get_channel(category_id)

        if not isinstance(category, discord.CategoryChannel):
            return await ctx.send("❌ That ID is not a valid category in this server.")

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO ticket_config (guild_id, category_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    category_id=excluded.category_id,
                    ticket_count=ticket_config.ticket_count
            """, (ctx.guild.id, category_id))
            conn.commit()

        await ctx.send(f"✅ Ticket Category set to ID: `{category_id}`")

    @commands.command(name="setticket")
    @commands.has_permissions(administrator=True)
    async def set_ticket_count(self, ctx, count: int):
        if count < 0:
            return await ctx.send("❌ Ticket count cannot be negative.")

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO ticket_config (guild_id, ticket_count)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    ticket_count=excluded.ticket_count
            """, (ctx.guild.id, count))
            conn.commit()

        await ctx.send(
            f"✅ Ticket counter adjusted. The next session will be **#{count + 1}**."
        )

    @commands.command(name="ticketnumber")
    @commands.has_permissions(administrator=True)
    async def ticketnumber(self, ctx, count: int):
        await self.set_ticket_count(ctx, count)

    # -----------------------------------------------------
    # ARCHIVE COMMANDS
    # -----------------------------------------------------

    @commands.command(name="archives")
    @commands.has_permissions(administrator=True)
    async def list_archives(self, ctx):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            rows = conn.execute("""
                SELECT ticket_id, asset_name, category, timestamp
                FROM ticket_archives
                WHERE guild_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            """, (ctx.guild.id,)).fetchall()

        if not rows:
            return await ctx.send(
                "🗄️ The Black Box is empty. No sessions archived."
            )

        embed = discord.Embed(
            title="🗄️ NEURAL ARCHIVE: STORED SESSIONS",
            color=0x2F3136
        )

        desc = ""

        for row in rows:
            desc += (
                f"🆔 `{row['ticket_id']}` | **{row['asset_name']}** "
                f"({row['category']}) - {row['timestamp']}\n"
            )

        embed.description = desc
        embed.set_footer(text="Use !view <ID> to retrieve a specific transcript.")

        await ctx.send(embed=embed)

    @commands.command(name="view")
    @commands.has_permissions(administrator=True)
    async def view_archive(self, ctx, ticket_id: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute("""
                SELECT *
                FROM ticket_archives
                WHERE ticket_id = ? AND guild_id = ?
            """, (ticket_id, ctx.guild.id)).fetchone()

        if not row:
            return await ctx.send("❌ Data block not found.")

        buffer = io.BytesIO(row["content"].encode("utf-8"))

        await ctx.send(
            content=f"📑 **TRANSCRIPT RECOVERY:** `{ticket_id}`",
            file=discord.File(
                buffer,
                filename=f"recovered-{ticket_id}.txt"
            )
        )

    # -----------------------------------------------------
    # AUTOROLE
    # -----------------------------------------------------

    @commands.command(name="autorole")
    @commands.has_permissions(administrator=True)
    async def set_autorole(self, ctx, role: discord.Role = None):
        with sqlite3.connect(DB_PATH) as conn:
            if role is None:
                conn.execute(
                    "DELETE FROM autorole_config WHERE guild_id = ?",
                    (ctx.guild.id,)
                )
                conn.commit()

                return await ctx.send(
                    "♻️ **AUTOROLE PROTOCOL DEACTIVATED:** "
                    "New members will no longer receive the automatic role."
                )

            conn.execute("""
                INSERT INTO autorole_config (guild_id, role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    role_id=excluded.role_id
            """, (ctx.guild.id, role.id))

            conn.commit()

        await ctx.send(
            f"✅ **AUTOROLE PROTOCOL ENGAGED:** "
            f"Joining members will receive {role.mention}."
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute("""
                SELECT role_id
                FROM autorole_config
                WHERE guild_id = ?
            """, (member.guild.id,)).fetchone()

        if row and row["role_id"]:
            role = member.guild.get_role(int(row["role_id"]))

            if role:
                try:
                    await member.add_roles(role)
                except Exception as e:
                    print(
                        f"Failed to assign autorole in guild {member.guild.id}: {e}"
                    )


# ---------------------------------------------------------
# TICKET LOBBY BUTTONS
# ---------------------------------------------------------

class TicketCustomButton(discord.ui.Button):
    def __init__(self, label, emoji, index, staff_role_id=None):
        self.category_slug = label.lower().replace(" ", "_")
        self.staff_role_id = str(staff_role_id) if staff_role_id else None
        self.raw_label = label

        # Keep the deterministic ID so the button survives restarts.
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=label,
            emoji=emoji,
            custom_id=f"tkt_customized:{self.category_slug}"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            staff_id = self.staff_role_id

            if not staff_id:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row

                    res = conn.execute("""
                        SELECT staff_role_id
                        FROM ticket_buttons
                        WHERE guild_id = ? AND label = ?
                    """, (
                        interaction.guild.id,
                        self.raw_label
                    )).fetchone()

                    if res:
                        staff_id = res["staff_role_id"]

            await self.view.create_ticket(
                interaction,
                self.category_slug,
                staff_id,
                self.raw_label
            )

        except Exception as e:
            await interaction_error(interaction, e)


class TicketLobbyView(discord.ui.View):
    def __init__(self, button_configs=None):
        super().__init__(timeout=None)

        if button_configs:
            for idx, cfg in enumerate(button_configs):
                self.add_item(
                    TicketCustomButton(
                        label=cfg["label"],
                        emoji=cfg["emoji"],
                        index=idx,
                        staff_role_id=cfg.get("staff_role_id")
                    )
                )

    async def create_ticket(
        self,
        interaction: discord.Interaction,
        category: str,
        staff_role_id: str = None,
        raw_label: str = "Support"
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            if not interaction.guild:
                return await interaction.followup.send(
                    "❌ This action must be used inside a server.",
                    ephemeral=True
                )

            guild = interaction.guild

            # -------------------------------------------------
            # Determine ticket number safely.
            # -------------------------------------------------

            async with ticket_counter_lock:
                highest_found_count = 0

                for cat_obj in guild.categories:
                    for channel in cat_obj.text_channels:
                        try:
                            chan_num = int(channel.name.split("-")[0])
                            highest_found_count = max(
                                highest_found_count,
                                chan_num
                            )
                        except (ValueError, IndexError):
                            pass

                with sqlite3.connect(DB_PATH, timeout=30) as conn:
                    conn.row_factory = sqlite3.Row
                    conn.execute("BEGIN IMMEDIATE")

                    config = conn.execute("""
                        SELECT *
                        FROM ticket_config
                        WHERE guild_id = ?
                    """, (guild.id,)).fetchone()

                    db_count = (
                        int(config["ticket_count"])
                        if config and config["ticket_count"] is not None
                        else 0
                    )

                    archive_rows = conn.execute("""
                        SELECT ticket_id
                        FROM ticket_archives
                        WHERE guild_id = ?
                    """, (guild.id,)).fetchall()

                    for row in archive_rows:
                        try:
                            archive_num = int(row["ticket_id"].split("-")[0])
                            highest_found_count = max(
                                highest_found_count,
                                archive_num
                            )
                        except (ValueError, IndexError):
                            pass

                    current_num = max(
                        highest_found_count,
                        db_count
                    ) + 1

                    conn.execute("""
                        INSERT INTO ticket_config (guild_id, ticket_count)
                        VALUES (?, ?)
                        ON CONFLICT(guild_id) DO UPDATE SET
                            ticket_count=excluded.ticket_count
                    """, (guild.id, current_num))

                    conn.commit()

                    config = conn.execute("""
                        SELECT *
                        FROM ticket_config
                        WHERE guild_id = ?
                    """, (guild.id,)).fetchone()

                # -------------------------------------------------
                # Resolve staff roles.
                # -------------------------------------------------

                chosen_staff_string = (
                    staff_role_id
                    if staff_role_id
                    else (
                        str(config["admin_role_id"])
                        if config and config["admin_role_id"]
                        else ""
                    )
                )

                parsed_role_ids = [
                    int(r.strip())
                    for r in chosen_staff_string.split(",")
                    if r.strip().isdigit()
                ]

                # -------------------------------------------------
                # Category routing.
                # -------------------------------------------------

                cat_name = raw_label[:100]

                target_category = discord.utils.get(
                    guild.categories,
                    name=cat_name
                )

                if not target_category:
                    category_overwrites = {
                        guild.default_role: discord.PermissionOverwrite(
                            read_messages=False
                        ),
                        guild.me: discord.PermissionOverwrite(
                            read_messages=True,
                            send_messages=True,
                            read_message_history=True
                        )
                    }

                    for r_id in parsed_role_ids:
                        role_obj = guild.get_role(r_id)

                        if role_obj:
                            category_overwrites[role_obj] = (
                                discord.PermissionOverwrite(
                                    read_messages=True,
                                    send_messages=True,
                                    read_message_history=True
                                )
                            )

                    target_category = await guild.create_category(
                        name=cat_name,
                        overwrites=category_overwrites
                    )

                # -------------------------------------------------
                # Ticket channel permissions.
                # -------------------------------------------------

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=False
                    ),
                    interaction.user: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        attach_files=True,
                        read_message_history=True
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_channels=True,
                        read_message_history=True
                    )
                }

                ping_mentions = []

                for r_id in parsed_role_ids:
                    role_obj = guild.get_role(r_id)

                    if role_obj:
                        overwrites[role_obj] = discord.PermissionOverwrite(
                            read_messages=True,
                            send_messages=True,
                            read_message_history=True
                        )
                        ping_mentions.append(role_obj.mention)

                ticket_channel = await guild.create_text_channel(
                    name=(
                        f"{current_num}-{interaction.user.name}-"
                        f"{category.replace('_', '-')}"
                    )[:100],
                    overwrites=overwrites,
                    category=target_category,
                    topic=(
                        f"Asset ID: {interaction.user.id} | "
                        f"Session #{current_num} | "
                        f"Staff Roles: {chosen_staff_string}"
                    )
                )

            ping_content = interaction.user.mention

            if ping_mentions:
                ping_content += " | " + " ".join(ping_mentions)

            tkt_embed = discord.Embed(
                title=(
                    f"⛓️ SESSION #{current_num} INITIATED: "
                    f"{category.upper().replace('_', ' ')}"
                ),
                description=(
                    f"Welcome {interaction.user.mention}. State your business clearly. "
                    "The appointed department has been notified."
                ),
                color=0x8B0000
            )

            tkt_embed.set_footer(text="The Master is watching.")

            await ticket_channel.send(
                content=ping_content,
                embed=tkt_embed,
                view=TicketControls()
            )

            # Admin logging.
            if config and config["admin_channel"]:
                admin_chan = guild.get_channel(config["admin_channel"])

                if admin_chan:
                    try:
                        log = discord.Embed(
                            title=f"🚨 NEW SESSION OPENED: #{current_num}",
                            color=0xFFD700
                        )

                        log.add_field(
                            name="Asset",
                            value=interaction.user.mention,
                            inline=True
                        )
                        log.add_field(
                            name="Category",
                            value=category.upper().replace("_", " "),
                            inline=True
                        )
                        log.add_field(
                            name="Assigned Department",
                            value=", ".join(ping_mentions) if ping_mentions else "Default Staff",
                            inline=True
                        )
                        log.add_field(
                            name="Channel",
                            value=ticket_channel.mention,
                            inline=False
                        )

                        await admin_chan.send(embed=log)

                    except Exception as log_error:
                        print(f"Ticket creation log failed: {log_error}")

            await interaction.followup.send(
                f"✅ Session opened: {ticket_channel.mention}",
                ephemeral=True
            )

        except Exception as e:
            await interaction_error(interaction, e)


# ---------------------------------------------------------
# ARCHIVE VIEWER
# ---------------------------------------------------------

class ArchiveViewer(discord.ui.View):
    def __init__(self, ticket_id=None):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(
        label="VIEW DATA",
        style=discord.ButtonStyle.secondary,
        emoji="👁️",
        custom_id="persistent_view_archive"
    )
    async def view_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            ticket_id = self.ticket_id

            if not ticket_id and interaction.message.embeds:
                try:
                    description = interaction.message.embeds[0].description or ""
                    ticket_id = description.split("**")[1]
                except Exception:
                    ticket_id = None

            if not ticket_id:
                return await interaction.response.send_message(
                    "❌ Ticket reference could not be resolved.",
                    ephemeral=True
                )

            await interaction.response.defer(ephemeral=True)

            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row

                row = conn.execute("""
                    SELECT content
                    FROM ticket_archives
                    WHERE ticket_id = ? AND guild_id = ?
                """, (
                    ticket_id,
                    interaction.guild.id
                )).fetchone()

            if row:
                buffer = io.BytesIO(row["content"].encode("utf-8"))

                await interaction.followup.send(
                    f"📑 **NEURAL RECOVERY:** Session `{ticket_id}`",
                    file=discord.File(
                        buffer,
                        filename=f"{ticket_id}.txt"
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Data block corrupted or missing.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction_error(interaction, e)


# ---------------------------------------------------------
# TICKET CONTROLS
# ---------------------------------------------------------

class TicketControls(discord.ui.View):
    def __init__(self, staff_role_id=None):
        super().__init__(timeout=None)
        self.staff_role_id = str(staff_role_id) if staff_role_id else None

    @discord.ui.button(
        label="CLAIM TICKET",
        style=discord.ButtonStyle.success,
        emoji="🙋‍♂️",
        custom_id="tkt:claim"
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not is_ticket_staff(interaction):
                return await interaction.response.send_message(
                    "❌ Only the assigned staff can claim this ticket.",
                    ephemeral=True
                )

            await interaction.response.defer(ephemeral=True)

            channel = interaction.channel
            opener_id = get_topic_value(channel, "Asset ID")

            # IMPORTANT:
            # Copy existing overwrites instead of rebuilding them.
            # This preserves every staff role's access.
            overwrites = dict(channel.overwrites)

            # Ensure the claimant has access.
            overwrites[interaction.user] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                read_message_history=True
            )

            # Restore opener access if their ID is stored in the topic.
            if opener_id and opener_id.isdigit():
                opener = interaction.guild.get_member(int(opener_id))

                if opener:
                    overwrites[opener] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        attach_files=True,
                        read_message_history=True
                    )

            # Keep all existing staff overwrites untouched.
            await channel.edit(overwrites=overwrites)

            old_topic = channel.topic or ""
            topic_parts = [
                part.strip()
                for part in old_topic.split("|")
                if not part.strip().startswith("Claimed by:")
            ]

            topic_parts.append(
                f"Claimed by: {interaction.user.display_name}"
            )
            topic_parts.append(
                f"Handler ID: {interaction.user.id}"
            )

            await channel.edit(topic=" | ".join(topic_parts))

            # Do not disable the button on the shared persistent view.
            # The view instance is registered globally and may serve other tickets.
            await interaction.followup.send(
                f"💼 **TICKET ASSIGNED:** {interaction.user.mention} "
                "has claimed this session.",
                ephemeral=False
            )

        except Exception as e:
            await interaction_error(interaction, e)

    @discord.ui.button(
        label="PING ADMINS",
        style=discord.ButtonStyle.primary,
        emoji="🔔",
        custom_id="tkt:ping_admins"
    )
    async def ping_admins(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not is_ticket_staff(interaction):
                return await interaction.response.send_message(
                    "❌ Only assigned staff can ping the department.",
                    ephemeral=True
                )

            target_role_ids = get_staff_role_ids(
                interaction.channel,
                self.staff_role_id
            )

            if not target_role_ids:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row

                    config = conn.execute("""
                        SELECT admin_role_id
                        FROM ticket_config
                        WHERE guild_id = ?
                    """, (interaction.guild.id,)).fetchone()

                if config and config["admin_role_id"]:
                    target_role_ids = [int(config["admin_role_id"])]

            valid_mentions = []

            for role_id in target_role_ids:
                role = interaction.guild.get_role(role_id)

                if role:
                    valid_mentions.append(role.mention)

            if valid_mentions:
                return await interaction.response.send_message(
                    f"⚠️ {' '.join(valid_mentions)} "
                    "**ATTENTION REQUIRED:** Support reinforcement requested.",
                    allowed_mentions=discord.AllowedMentions(roles=True)
                )

            await interaction.response.send_message(
                "❌ Assigned department roles could not be resolved.",
                ephemeral=True
            )

        except Exception as e:
            await interaction_error(interaction, e)

    @discord.ui.button(
        label="CLOSE SESSION",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="tkt:close"
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel = interaction.channel

            opener_id = get_topic_value(channel, "Asset ID")
            is_opener = (
                opener_id
                and opener_id.isdigit()
                and int(opener_id) == interaction.user.id
            )

            if not is_ticket_staff(interaction) and not is_opener:
                return await interaction.response.send_message(
                    "❌ Only the ticket opener or assigned staff can close this ticket.",
                    ephemeral=True
                )

            await interaction.response.defer()

            # Build transcript.
            transcript = (
                f"--- BLACK BOX TRANSCRIPT: {channel.name} ---\n"
                f"Asset ID: {opener_id or 'Unknown'}\n"
                f"Closed by: {interaction.user.display_name}\n"
                f"Sealed on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                + "-" * 40
                + "\n\n"
            )

            async for message in channel.history(
                limit=None,
                oldest_first=True
            ):
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M")

                content = (
                    message.clean_content
                    if message.content
                    else "[Attachment/Embed]"
                )

                if message.attachments:
                    content += " | Attachments: " + ", ".join(
                        attachment.url for attachment in message.attachments
                    )

                transcript += (
                    f"[{timestamp}] {message.author.display_name}: "
                    f"{content}\n"
                )

            ticket_id = channel.name

            # Save archive before deleting anything.
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ticket_archives
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    ticket_id,
                    interaction.guild.id,
                    interaction.user.display_name,
                    "SESSION",
                    transcript,
                    datetime.now().strftime("%Y-%m-%d %H:%M")
                ))

                conn.commit()

            # Retrieve logging channel.
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row

                config = conn.execute("""
                    SELECT admin_channel
                    FROM ticket_config
                    WHERE guild_id = ?
                """, (interaction.guild.id,)).fetchone()

            # Logging failure must not destroy the saved transcript.
            if config and config["admin_channel"]:
                admin_chan = interaction.guild.get_channel(
                    config["admin_channel"]
                )

                if admin_chan:
                    try:
                        archive_embed = discord.Embed(
                            title="📸 EVIDENCE ARCHIVED",
                            description=(
                                f"Session **{ticket_id}** has been sealed. "
                                "Data logged to database."
                            ),
                            color=0x2F3136
                        )

                        await admin_chan.send(
                            embed=archive_embed,
                            view=ArchiveViewer(ticket_id)
                        )

                    except Exception as log_error:
                        print(
                            f"Archive log delivery failed: {log_error}"
                        )

            await interaction.followup.send(
                "⛓️ *Session sealed. Data stored in Black Box. "
                "Purging in 5 seconds...*"
            )

            await asyncio.sleep(5)

            await channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )

        except Exception as e:
            # If transcript storage failed, the channel is deliberately retained.
            await interaction_error(interaction, e)


# ---------------------------------------------------------
# PERSISTENT VIEW REGISTRATION
# ---------------------------------------------------------

async def setup(bot):
    await bot.add_cog(ReactionRoleSystem(bot))

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            # Restore reaction role views using their stored message IDs.
            rr_rows = conn.execute("""
                SELECT message_id, emoji, role_id
                FROM reaction_roles
            """).fetchall()

            rr_dict = {}

            for row in rr_rows:
                message_id = row["message_id"]

                if message_id not in rr_dict:
                    rr_dict[message_id] = {}

                rr_dict[message_id][row["emoji"]] = row["role_id"]

            for message_id, mappings in rr_dict.items():
                bot.add_view(
                    ReactionRoleView(mappings),
                    message_id=message_id
                )

            # Restore ticket lobby views using the exact panel message IDs.
            panel_rows = conn.execute("""
                SELECT guild_id, message_id, channel_id
                FROM ticket_panels
            """).fetchall()

            for panel in panel_rows:
                guild_id = panel["guild_id"]

                btns = conn.execute("""
                    SELECT label, emoji, btn_index, staff_role_id
                    FROM ticket_buttons
                    WHERE guild_id = ?
                    ORDER BY btn_index
                """, (guild_id,)).fetchall()

                configs = [
                    {
                        "label": row["label"],
                        "emoji": row["emoji"],
                        "staff_role_id": str(row["staff_role_id"] or "")
                    }
                    for row in btns
                ]

                if configs:
                    bot.add_view(
                        TicketLobbyView(configs),
                        message_id=panel["message_id"]
                    )

    except Exception as e:
        print(f"Failed to restore persistent views: {e}")

    # These views use fixed custom IDs and can serve persistent messages.
    bot.add_view(TicketControls())
    bot.add_view(DesignerLobby())
    bot.add_view(ArchiveViewer())

