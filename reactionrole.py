import discord
from discord.ext import commands
import sqlite3
import asyncio
import os
import io
import json
import shutil
import traceback
from datetime import datetime

# ---------------------------------------------------------
# DATABASE CONFIGURATION - RAILWAY PERSISTENT VOLUME
# ---------------------------------------------------------

DATA_DIR = "/data"
DB_PATH = os.path.join(DATA_DIR, "economy.db")

os.makedirs(DATA_DIR, exist_ok=True)

# Migrate an existing database from the application folder.
OLD_DB_PATH = "database.db"

if not os.path.exists(DB_PATH) and os.path.exists(OLD_DB_PATH):
    try:
        shutil.copy2(OLD_DB_PATH, DB_PATH)
        print("Echo database migrated to Railway Volume.")
    except Exception as e:
        print(f"Database migration failed: {e}")

ticket_counter_lock = asyncio.Lock()


def get_db():
    """Create a configured SQLite connection."""
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------
# SHARED HELPERS
# ---------------------------------------------------------

def get_staff_role_ids(channel, fallback=None):
    role_string = fallback or ""

    if channel and channel.topic:
        for part in channel.topic.split("|"):
            part = part.strip()

            if part.startswith("Staff Roles:"):
                role_string = part.replace(
                    "Staff Roles:", "", 1
                ).strip()
                break

    return [
        int(role_id.strip())
        for role_id in role_string.split(",")
        if role_id.strip().isdigit()
    ]


def get_topic_value(channel, key):
    if not channel or not channel.topic:
        return None

    for part in channel.topic.split("|"):
        part = part.strip()

        if part.startswith(key + ":"):
            return part.split(":", 1)[1].strip()

    return None


def is_ticket_staff(interaction):
    if not interaction.guild:
        return False

    if not isinstance(interaction.user, discord.Member):
        return False

    if interaction.user.guild_permissions.administrator:
        return True

    staff_ids = get_staff_role_ids(interaction.channel)

    return any(
        role.id in staff_ids
        for role in interaction.user.roles
    )


async def interaction_error(interaction, error):
    print("Echo interaction error:")
    traceback.print_exception(
        type(error),
        error,
        error.__traceback__
    )

    message = (
        "❌ Something went wrong while processing that action. "
        "Please try again or contact staff."
    )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=True
            )
    except Exception as response_error:
        print(
            f"Could not send interaction error response: "
            f"{response_error}"
        )


async def acknowledge_interaction(interaction, ephemeral=True):
    """Acknowledge an interaction only if it has not already been answered."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=ephemeral)


def get_bot_member(guild, bot):
    """Resolve the bot's member object safely."""
    if guild.me:
        return guild.me

    if bot.user:
        return guild.get_member(bot.user.id)

    return None


# ---------------------------------------------------------
# DATABASE INITIALISATION
# ---------------------------------------------------------

def initialise_database():
    os.makedirs(DATA_DIR, exist_ok=True)

    with get_db() as conn:

        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")

        # UPDATED: Reaction roles now store a button label.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                message_id INTEGER,
                emoji TEXT,
                role_id INTEGER,
                label TEXT DEFAULT ''
            )
        """)

        # DATABASE MIGRATION:
        # Adds the label column to existing databases.
        reaction_columns = [
            column[1]
            for column in conn.execute(
                "PRAGMA table_info(reaction_roles)"
            ).fetchall()
        ]

        if "label" not in reaction_columns:
            conn.execute("""
                ALTER TABLE reaction_roles
                ADD COLUMN label TEXT DEFAULT ''
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

        columns = [
            column[1]
            for column in conn.execute(
                "PRAGMA table_info(ticket_config)"
            ).fetchall()
        ]

        if "admin_role_id" not in columns:
            conn.execute("""
                ALTER TABLE ticket_config
                ADD COLUMN admin_role_id INTEGER
            """)

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

        button_columns = [
            column[1]
            for column in conn.execute(
                "PRAGMA table_info(ticket_buttons)"
            ).fetchall()
        ]

        if "staff_role_id" not in button_columns:
            conn.execute("""
                ALTER TABLE ticket_buttons
                ADD COLUMN staff_role_id TEXT
            """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_panels (
                guild_id INTEGER,
                message_id INTEGER PRIMARY KEY,
                channel_id INTEGER
            )
        """)

        conn.commit()

    print(f"Echo database ready: {DB_PATH}")


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
    async def open_suite(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "🛠️ Designer Suite access initiated. "
            "Please use `!setroles` to configure new links.",
            ephemeral=True
        )


# ---------------------------------------------------------
# REACTION ROLES
# ---------------------------------------------------------

class ReactionRoleButton(discord.ui.Button):

    def __init__(self, emoji, role_id, label, count=0):

        self.role_id = int(role_id)
        self.base_label = label or "Select Role"

        # Display the button name and member count.
        if count > 0:
            display_label = f"{self.base_label} ({count})"
        else:
            display_label = self.base_label

        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=display_label[:80],
            emoji=emoji,
            custom_id=f"rr:{role_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            if (
                not interaction.guild
                or not isinstance(interaction.user, discord.Member)
            ):
                return await interaction.response.send_message(
                    "❌ This button can only be used inside a server.",
                    ephemeral=True
                )

            await acknowledge_interaction(interaction)

            role = interaction.guild.get_role(self.role_id)

            if not role:
                return await interaction.followup.send(
                    "❌ Error: Role not found.",
                    ephemeral=True
                )

            bot_member = get_bot_member(
                interaction.guild,
                interaction.client
            )

            if not bot_member:
                return await interaction.followup.send(
                    "❌ Bot member could not be resolved.",
                    ephemeral=True
                )

            if role >= bot_member.top_role:
                return await interaction.followup.send(
                    "❌ The bot cannot manage this role because "
                    "of its role hierarchy.",
                    ephemeral=True
                )

            if role in interaction.user.roles:
                await interaction.user.remove_roles(
                    role,
                    reason="Reaction role button"
                )
                response = (
                    f"🔓 **ACCESS REVOKED:** "
                    f"{role.name} removed."
                )
            else:
                await interaction.user.add_roles(
                    role,
                    reason="Reaction role button"
                )
                response = (
                    f"🔒 **ACCESS GRANTED:** "
                    f"{role.name} assigned."
                )

            await interaction.followup.send(
                response,
                ephemeral=True
            )

            # Refresh the member count while preserving the button name.
            try:
                updated_count = len(role.members)

                if updated_count > 0:
                    self.label = (
                        f"{self.base_label} ({updated_count})"
                    )[:80]
                else:
                    self.label = self.base_label[:80]

                await interaction.message.edit(
                    view=self.view
                )

            except Exception as edit_error:
                print(
                    f"Reaction role counter refresh failed: "
                    f"{edit_error}"
                )

        except Exception as e:
            await interaction_error(interaction, e)


class ReactionRoleView(discord.ui.View):

    def __init__(self, mappings, guild=None):
        super().__init__(timeout=None)

        for emoji, config in mappings.items():

            # Support both the new mapping format and older mappings.
            if isinstance(config, dict):
                role_id = config["role_id"]
                button_label = config.get("label", "Select Role")
            else:
                role_id = config[0]
                button_label = config[1] if len(config) > 1 else "Select Role"

            initial_count = 0

            if guild:
                role_obj = guild.get_role(int(role_id))

                if role_obj:
                    initial_count = len(role_obj.members)

            self.add_item(
                ReactionRoleButton(
                    emoji,
                    role_id,
                    button_label,
                    count=initial_count
                )
            )


# ---------------------------------------------------------
# MAIN COG
# ---------------------------------------------------------

class ReactionRoleSystem(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.active_setups = {}
        initialise_database()

    # -----------------------------------------------------
    # REACTION ROLE SETUP
    # -----------------------------------------------------

    @commands.command(name="setroles")
    @commands.has_permissions(administrator=True)
    async def setroles(self, ctx):

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

            return (
                m.author == ctx.author
                and m.channel == ctx.channel
            )

        try:
            await ctx.send(
                "🎯 **STEP 1:** Mention the channel where "
                "the rules should be sent."
            )

            await ctx.send(
                "*(Type `cancel` at any point to abort.)*"
            )

            msg = await self.bot.wait_for(
                "message",
                check=check,
                timeout=None
            )

            target_channel = (
                msg.channel_mentions[0]
                if msg.channel_mentions
                else None
            )

            if not target_channel:
                return await ctx.send(
                    "❌ Invalid channel. Restart the command."
                )

            await ctx.send(
                "🔢 **STEP 2:** How many reaction roles? "
                "(Maximum 25)."
            )

            msg = await self.bot.wait_for(
                "message",
                check=check,
                timeout=None
            )

            try:
                rr_count = int(msg.content.strip())

                if not 1 <= rr_count <= 25:
                    return await ctx.send(
                        "❌ Total reaction roles must be "
                        "between 1 and 25."
                    )

            except ValueError:
                return await ctx.send(
                    "❌ Please enter a valid number."
                )

            mappings = {}
            db_mappings = []

            for i in range(rr_count):

                # STEP 3: Select role.
                await ctx.send(
                    f"👤 **STEP 3.{i+1}:** Mention the role "
                    f"for button #{i+1}."
                )

                msg = await self.bot.wait_for(
                    "message",
                    check=check,
                    timeout=None
                )

                target_role = (
                    msg.role_mentions[0]
                    if msg.role_mentions
                    else None
                )

                if not target_role:
                    return await ctx.send(
                        "❌ Invalid role. Restart the command."
                    )

                # NEW STEP 4: Set button name.
                await ctx.send(
                    f"🏷️ **STEP 4.{i+1}:** What name should "
                    f"appear on the button for {target_role.name}?\n"
                    "Example: `Europe`, `Gaming`, `Announcements`.\n"
                    "Maximum 80 characters."
                )

                msg = await self.bot.wait_for(
                    "message",
                    check=check,
                    timeout=None
                )

                button_label = msg.content.strip()

                if not button_label:
                    return await ctx.send(
                        "❌ Button name cannot be empty."
                    )

                if len(button_label) > 80:
                    return await ctx.send(
                        "❌ Button name cannot exceed 80 characters."
                    )

                # STEP 5: Select emoji.
                await ctx.send(
                    f"⭐ **STEP 5.{i+1}:** Send the emoji "
                    f"for the **{button_label}** button."
                )

                msg = await self.bot.wait_for(
                    "message",
                    check=check,
                    timeout=None
                )

                raw_content = msg.content.strip()

                if (
                    raw_content.startswith("<:")
                    or raw_content.startswith("<a:")
                ):
                    try:
                        target_emoji = discord.PartialEmoji.from_str(
                            raw_content
                        )
                    except Exception:
                        return await ctx.send(
                            "❌ Failed to process custom emoji."
                        )
                else:
                    target_emoji = raw_content

                mappings[str(target_emoji)] = {
                    "role_id": target_role.id,
                    "label": button_label
                }

                db_mappings.append(
                    (
                        str(target_emoji),
                        target_role.id,
                        button_label
                    )
                )

            # STEP 6: Rules message.
            await ctx.send(
                "📝 **STEP 6:** Type the rules message."
            )

            msg = await self.bot.wait_for(
                "message",
                check=check,
                timeout=None
            )

            rules_content = msg.content

            if len(rules_content) > 4096:
                rules_content = rules_content[:4090] + "..."

            # STEP 7: Image.
            await ctx.send(
                "🖼️ **STEP 7:** Upload an image or paste "
                "an image URL. Type `none` to skip."
            )

            msg = await self.bot.wait_for(
                "message",
                check=check,
                timeout=None
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

            embed.set_footer(
                text="Echo Protocol | Role Management"
            )

            if embed_image_url:
                embed.set_image(url=embed_image_url)

            view = ReactionRoleView(
                mappings,
                guild=ctx.guild
            )

            try:
                final_msg = await target_channel.send(
                    embed=embed,
                    view=view
                )

            except discord.HTTPException as e:
                return await ctx.send(
                    f"❌ **DEPLOYMENT FAILED:** {e}"
                )

            # Save reaction roles, including their button names.
            with get_db() as conn:

                conn.execute(
                    "DELETE FROM reaction_roles WHERE message_id = ?",
                    (final_msg.id,)
                )

                for emoji_string, role_id, button_label in db_mappings:
                    conn.execute("""
                        INSERT INTO reaction_roles
                            (message_id, emoji, role_id, label)
                        VALUES (?, ?, ?, ?)
                    """, (
                        final_msg.id,
                        emoji_string,
                        role_id,
                        button_label
                    ))

                conn.commit()

            await ctx.send(
                f"✅ **SUCCESS:** Protocol deployed in "
                f"{target_channel.mention} with {rr_count} options!"
            )

        except asyncio.TimeoutError:
            await ctx.send(
                "⌛ **CANCELLED:** Setup manually cancelled."
            )

        except Exception as e:
            print(f"Reaction role setup error: {e}")
            traceback.print_exc()

            await ctx.send(
                "❌ Reaction role setup failed. "
                "Check the Railway logs."
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

            return (
                m.author == ctx.author
                and m.channel == ctx.channel
            )

        async def send_tracked_step(message):
            sent = await ctx.send(message)
            setup_garbage.append(sent)
            return sent

        async def clean_setup():
            for message in setup_garbage:
                try:
                    await message.delete()
                except Exception:
                    pass

        try:

            await send_tracked_step(
                "🎯 **STEP 1:** Mention the ticket lobby channel."
            )

            await send_tracked_step(
                "*(Type `cancel` at any point to abort.)*"
            )

            msg = await self.bot.wait_for(
                "message",
                check=check,
                timeout=None
            )

            setup_garbage.append(msg)

            target_channel = (
                msg.channel_mentions[0]
                if msg.channel_mentions
                else None
            )

            if not target_channel:
                await clean_setup()
                return await ctx.send(
                    "❌ Invalid channel. Cancelled."
                )

            await send_tracked_step(
                "🗄️ **STEP 2:** Mention the admin logging channel."
            )

            msg = await self.bot.wait_for(
                "message",
                check=check,
                timeout=None
            )

            setup_garbage.append(msg)

            admin_logging_channel = (
                msg.channel_mentions[0]
                if msg.channel_mentions
                else None
            )

            if not admin_logging_channel:
                await clean_setup()
                return await ctx.send(
                    "❌ Invalid logging channel. Cancelled."
                )

            await send_tracked_step(
                "📝 **STEP 3:** Type the ticket lobby description."
            )

            msg = await self.bot.wait_for(
                "message",
                check=check,
                timeout=None
            )

            setup_garbage.append(msg)
            lobby_desc = msg.content

            await send_tracked_step(
                "🖼️ **STEP 4:** Upload an image or paste "
                "an image link. Type `none` to skip."
            )

            msg = await self.bot.wait_for(
                "message",
                check=check,
                timeout=None
            )

            setup_garbage.append(msg)

            ticket_image_url = None

            if msg.content.strip().lower() != "none":

                if msg.attachments:
                    ticket_image_url = msg.attachments[0].url

                elif msg.content.startswith("http"):
                    ticket_image_url = msg.content.strip()

            await send_tracked_step(
                "🔢 **STEP 5:** How many custom buttons? "
                "(Maximum 5)."
            )

            msg = await self.bot.wait_for(
                "message",
                check=check,
                timeout=None
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
                return await ctx.send(
                    "❌ Please enter a valid number."
                )

            button_configs = []

            for i in range(btn_count):

                await send_tracked_step(
                    f"🏷️ **BUTTON {i+1} NAME:** "
                    f"Enter the label for Button #{i+1}."
                )

                msg_label = await self.bot.wait_for(
                    "message",
                    check=check,
                    timeout=None
                )

                setup_garbage.append(msg_label)
                label_text = msg_label.content.strip()

                if not label_text:
                    await clean_setup()
                    return await ctx.send(
                        "❌ Button labels cannot be empty."
                    )

                await send_tracked_step(
                    f"✨ **BUTTON {i+1} EMOJI:** Send the emoji."
                )

                msg_emoji = await self.bot.wait_for(
                    "message",
                    check=check,
                    timeout=None
                )

                setup_garbage.append(msg_emoji)
                raw_emoji = msg_emoji.content.strip()

                if (
                    raw_emoji.startswith("<:")
                    or raw_emoji.startswith("<a:")
                ):
                    try:
                        resolved_emoji = discord.PartialEmoji.from_str(
                            raw_emoji
                        )
                    except Exception:
                        resolved_emoji = raw_emoji
                else:
                    resolved_emoji = raw_emoji

                await send_tracked_step(
                    f"🛡️ **BUTTON {i+1} STAFF PRIVACY:** "
                    "Mention all roles allowed to access this ticket."
                )

                msg_role = await self.bot.wait_for(
                    "message",
                    check=check,
                    timeout=None
                )

                setup_garbage.append(msg_role)

                staff_roles = msg_role.role_mentions

                if not staff_roles:
                    await clean_setup()
                    return await ctx.send(
                        "❌ No staff roles selected. Setup cancelled."
                    )

                staff_roles_string = ",".join(
                    str(role.id)
                    for role in staff_roles
                )

                button_configs.append({
                    "label": label_text,
                    "emoji": str(resolved_emoji),
                    "staff_role_id": staff_roles_string
                })

            # Save configuration.
            with get_db() as conn:

                conn.execute("""
                    INSERT INTO ticket_config
                        (guild_id, lobby_channel, admin_channel, ticket_count)
                    VALUES (?, ?, ?, 0)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        lobby_channel=excluded.lobby_channel,
                        admin_channel=excluded.admin_channel
                """, (
                    ctx.guild.id,
                    target_channel.id,
                    admin_logging_channel.id
                ))

                conn.execute("""
                    DELETE FROM ticket_buttons
                    WHERE guild_id = ?
                """, (ctx.guild.id,))

                for idx, cfg in enumerate(button_configs):

                    conn.execute("""
                        INSERT INTO ticket_buttons
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        ctx.guild.id,
                        idx,
                        cfg["label"],
                        cfg["emoji"],
                        cfg["staff_role_id"]
                    ))

                conn.commit()

            embed = discord.Embed(
                title="📩 Contact the Staff",
                description=lobby_desc,
                color=0x8B0000
            )

            embed.set_footer(
                text="Echo Ticket System | Secure Neural Link"
            )

            if ticket_image_url:
                embed.set_image(url=ticket_image_url)

            view = TicketLobbyView(button_configs)

            panel_message = await target_channel.send(
                embed=embed,
                view=view
            )

            # Save exact panel message ID.
            with get_db() as conn:

                conn.execute("""
                    INSERT OR REPLACE INTO ticket_panels
                    VALUES (?, ?, ?)
                """, (
                    ctx.guild.id,
                    panel_message.id,
                    target_channel.id
                ))

                conn.commit()

            await clean_setup()

            await ctx.send(
                f"✅ **SUCCESS:** Ticket Lobby deployed in "
                f"{target_channel.mention}. Transcripts assigned to "
                f"{admin_logging_channel.mention}."
            )

        except asyncio.TimeoutError:
            await clean_setup()

            await ctx.send(
                "⌛ **CANCELLED:** Configuration manually cancelled."
            )

        except Exception as e:
            await clean_setup()

            print(f"Ticket setup error: {e}")
            traceback.print_exc()

            await ctx.send(
                "❌ Ticket setup failed. Check Railway logs."
            )

        finally:
            if self.active_setups.get(ctx.author.id) == ctx.message.id:
                self.active_setups.pop(ctx.author.id, None)

    # -----------------------------------------------------
    # TICKET CONFIGURATION COMMANDS
    # -----------------------------------------------------

    @commands.command(name="ticketadmin")
    @commands.has_permissions(administrator=True)
    async def set_ticket_admin(self, ctx, role: discord.Role):

        with get_db() as conn:

            conn.execute("""
                INSERT INTO ticket_config
                    (guild_id, admin_role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    admin_role_id=excluded.admin_role_id
            """, (
                ctx.guild.id,
                role.id
            ))

            conn.commit()

        await ctx.send(
            f"✅ Default Admin Role Persisted: {role.mention}."
        )

    @commands.command(name="ticketcategory")
    @commands.has_permissions(administrator=True)
    async def set_ticket_category(self, ctx, category_id: int):

        category = ctx.guild.get_channel(category_id)

        if not isinstance(category, discord.CategoryChannel):
            return await ctx.send(
                "❌ That ID is not a valid category in this server."
            )

        with get_db() as conn:

            conn.execute("""
                INSERT INTO ticket_config
                    (guild_id, category_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    category_id=excluded.category_id
            """, (
                ctx.guild.id,
                category_id
            ))

            conn.commit()

        await ctx.send(
            f"✅ Ticket Category set to ID: `{category_id}`"
        )

    @commands.command(name="setticket")
    @commands.has_permissions(administrator=True)
    async def set_ticket_count(self, ctx, count: int):

        if count < 0:
            return await ctx.send(
                "❌ Ticket count cannot be negative."
            )

        with get_db() as conn:

            conn.execute("""
                INSERT INTO ticket_config
                    (guild_id, ticket_count)
                VALUES (?, ?,)
                ON CONFLICT(guild_id) DO UPDATE SET
                    ticket_count=excluded.ticket_count
            """.replace("(?, ?,)", "(?, ?)"), (
                ctx.guild.id,
                count
            ))

            conn.commit()

        await ctx.send(
            f"✅ Ticket counter adjusted. "
            f"The next session will be **#{count + 1}**."
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

        with get_db() as conn:

            rows = conn.execute("""
                SELECT ticket_id, asset_name, category, timestamp
                FROM ticket_archives
                WHERE guild_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            """, (
                ctx.guild.id,
            )).fetchall()

        if not rows:
            return await ctx.send(
                "🗄️ The Black Box is empty. No sessions archived."
            )

        embed = discord.Embed(
            title="🗄️ NEURAL ARCHIVE: STORED SESSIONS",
            color=0x2F3136
        )

        description = ""

        for row in rows:
            description += (
                f"🆔 `{row['ticket_id']}` | "
                f"**{row['asset_name']}** "
                f"({row['category']}) - {row['timestamp']}\n"
            )

        embed.description = description

        embed.set_footer(
            text="Use !view <ID> to retrieve a transcript."
        )

        await ctx.send(embed=embed)

    @commands.command(name="view")
    @commands.has_permissions(administrator=True)
    async def view_archive(self, ctx, ticket_id: str):

        with get_db() as conn:

            row = conn.execute("""
                SELECT *
                FROM ticket_archives
                WHERE ticket_id = ? AND guild_id = ?
            """, (
                ticket_id,
                ctx.guild.id
            )).fetchone()

        if not row:
            return await ctx.send(
                "❌ Data block not found."
            )

        buffer = io.BytesIO(
            row["content"].encode("utf-8")
        )

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
    async def set_autorole(
        self,
        ctx,
        role: discord.Role = None
    ):

        with get_db() as conn:

            if role is None:

                conn.execute("""
                    DELETE FROM autorole_config
                    WHERE guild_id = ?
                """, (
                    ctx.guild.id,
                ))

                conn.commit()

                return await ctx.send(
                    "♻️ **AUTOROLE PROTOCOL DEACTIVATED:** "
                    "New members will no longer receive the automatic role."
                )

            conn.execute("""
                INSERT INTO autorole_config
                    (guild_id, role_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    role_id=excluded.role_id
            """, (
                ctx.guild.id,
                role.id
            ))

            conn.commit()

        await ctx.send(
            f"✅ **AUTOROLE PROTOCOL ENGAGED:** "
            f"Joining members will receive {role.mention}."
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        with get_db() as conn:

            row = conn.execute("""
                SELECT role_id
                FROM autorole_config
                WHERE guild_id = ?
            """, (
                member.guild.id,
            )).fetchone()

        if row and row["role_id"]:

            role = member.guild.get_role(
                int(row["role_id"])
            )

            if role:
                try:
                    await member.add_roles(
                        role,
                        reason="Echo automatic member role"
                    )

                except Exception as e:
                    print(
                        f"Failed to assign autorole "
                        f"in guild {member.guild.id}: {e}"
                    )


# ---------------------------------------------------------
# TICKET LOBBY BUTTONS
# ---------------------------------------------------------

class TicketCustomButton(discord.ui.Button):

    def __init__(
        self,
        label,
        emoji,
        index,
        staff_role_id=None
    ):

        self.category_slug = (
            label.lower().replace(" ", "_")
        )

        self.staff_role_id = (
            str(staff_role_id)
            if staff_role_id
            else None
        )

        self.raw_label = label

        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=label,
            emoji=emoji,
            custom_id=f"tkt_customized:{self.category_slug}"
        )

    async def callback(self, interaction: discord.Interaction):

        try:
            await acknowledge_interaction(
                interaction,
                ephemeral=True
            )

            if not interaction.guild:
                return await interaction.followup.send(
                    "❌ This action must be used inside a server.",
                    ephemeral=True
                )

            staff_id = self.staff_role_id

            if not staff_id:

                with get_db() as conn:

                    result = conn.execute("""
                        SELECT staff_role_id
                        FROM ticket_buttons
                        WHERE guild_id = ? AND label = ?
                    """, (
                        interaction.guild.id,
                        self.raw_label
                    )).fetchone()

                    if result:
                        staff_id = result["staff_role_id"]

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

            for idx, config in enumerate(button_configs):

                self.add_item(
                    TicketCustomButton(
                        label=config["label"],
                        emoji=config["emoji"],
                        index=idx,
                        staff_role_id=config.get("staff_role_id")
                    )
                )

    async def create_ticket(
        self,
        interaction: discord.Interaction,
        category: str,
        staff_role_id: str = None,
        raw_label: str = "Support"
    ):

        try:
            await acknowledge_interaction(
                interaction,
                ephemeral=True
            )

            if not interaction.guild:
                return await interaction.followup.send(
                    "❌ This action must be used inside a server.",
                    ephemeral=True
                )

            guild = interaction.guild

            # -------------------------------------------------
            # DETERMINE TICKET NUMBER
            # -------------------------------------------------

            async with ticket_counter_lock:

                highest_found_count = 0

                for category_obj in guild.categories:

                    for channel in category_obj.text_channels:

                        try:
                            channel_number = int(
                                channel.name.split("-")[0]
                            )

                            highest_found_count = max(
                                highest_found_count,
                                channel_number
                            )

                        except (ValueError, IndexError):
                            pass

                with get_db() as conn:

                    conn.execute("BEGIN IMMEDIATE")

                    config = conn.execute("""
                        SELECT *
                        FROM ticket_config
                        WHERE guild_id = ?
                    """, (
                        guild.id,
                    )).fetchone()

                    db_count = (
                        int(config["ticket_count"])
                        if config
                        and config["ticket_count"] is not None
                        else 0
                    )

                    archive_rows = conn.execute("""
                        SELECT ticket_id
                        FROM ticket_archives
                        WHERE guild_id = ?
                    """, (
                        guild.id,
                    )).fetchall()

                    for row in archive_rows:

                        try:
                            archive_number = int(
                                row["ticket_id"].split("-")[0]
                            )

                            highest_found_count = max(
                                highest_found_count,
                                archive_number
                            )

                        except (ValueError, IndexError):
                            pass

                    current_num = max(
                        highest_found_count,
                        db_count
                    ) + 1

                    conn.execute("""
                        INSERT INTO ticket_config
                            (guild_id, ticket_count)
                        VALUES (?, ?)
                        ON CONFLICT(guild_id) DO UPDATE SET
                            ticket_count=excluded.ticket_count
                    """, (
                        guild.id,
                        current_num
                    ))

                    conn.commit()

                    config = conn.execute("""
                        SELECT *
                        FROM ticket_config
                        WHERE guild_id = ?
                    """, (
                        guild.id,
                    )).fetchone()

                # -------------------------------------------------
                # RESOLVE STAFF ROLES
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
                    int(role_id.strip())
                    for role_id in chosen_staff_string.split(",")
                    if role_id.strip().isdigit()
                ]

                # -------------------------------------------------
                # CATEGORY ROUTING
                # -------------------------------------------------

                category_name = raw_label[:100]

                target_category = discord.utils.get(
                    guild.categories,
                    name=category_name
                )

                bot_member = get_bot_member(
                    guild,
                    interaction.client
                )

                if not bot_member:
                    raise RuntimeError(
                        "Could not resolve Echo's server member."
                    )

                if not target_category:

                    category_overwrites = {
                        guild.default_role:
                            discord.PermissionOverwrite(
                                read_messages=False
                            ),

                        bot_member:
                            discord.PermissionOverwrite(
                                read_messages=True,
                                send_messages=True,
                                read_message_history=True
                            )
                    }

                    for role_id in parsed_role_ids:

                        role_obj = guild.get_role(role_id)

                        if role_obj:
                            category_overwrites[role_obj] = (
                                discord.PermissionOverwrite(
                                    read_messages=True,
                                    send_messages=True,
                                    read_message_history=True
                                )
                            )

                    target_category = await guild.create_category(
                        name=category_name,
                        overwrites=category_overwrites
                    )

                # -------------------------------------------------
                # TICKET CHANNEL PERMISSIONS
                # -------------------------------------------------

                overwrites = {
                    guild.default_role:
                        discord.PermissionOverwrite(
                            read_messages=False
                        ),

                    interaction.user:
                        discord.PermissionOverwrite(
                            read_messages=True,
                            send_messages=True,
                            attach_files=True,
                            read_message_history=True
                        ),

                    bot_member:
                        discord.PermissionOverwrite(
                            read_messages=True,
                            send_messages=True,
                            manage_channels=True,
                            read_message_history=True
                        )
                }

                ping_mentions = []

                for role_id in parsed_role_ids:

                    role_obj = guild.get_role(role_id)

                    if role_obj:

                        overwrites[role_obj] = (
                            discord.PermissionOverwrite(
                                read_messages=True,
                                send_messages=True,
                                read_message_history=True
                            )
                        )

                        ping_mentions.append(
                            role_obj.mention
                        )

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

            # -------------------------------------------------
            # SEND TICKET MESSAGE
            # -------------------------------------------------

            ping_content = interaction.user.mention

            if ping_mentions:
                ping_content += " | " + " ".join(
                    ping_mentions
                )

            ticket_embed = discord.Embed(
                title=(
                    f"⛓️ SESSION #{current_num} INITIATED: "
                    f"{category.upper().replace('_', ' ')}"
                ),

                description=(
                    f"Welcome {interaction.user.mention}. "
                    "Please describe your request clearly. "
                    "The appointed department has been notified."
                ),

                color=0x8B0000
            )

            ticket_embed.set_footer(
                text="Echo Support System."
            )

            await ticket_channel.send(
                content=ping_content,
                embed=ticket_embed,
                view=TicketControls()
            )

            # -------------------------------------------------
            # ADMIN LOGGING
            # -------------------------------------------------

            if config and config["admin_channel"]:

                admin_channel = guild.get_channel(
                    config["admin_channel"]
                )

                if admin_channel:

                    try:
                        log = discord.Embed(
                            title=(
                                f"🚨 NEW SESSION OPENED: "
                                f"#{current_num}"
                            ),
                            color=0xFFD700
                        )

                        log.add_field(
                            name="Member",
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
                            value=(
                                ", ".join(ping_mentions)
                                if ping_mentions
                                else "Default Staff"
                            ),
                            inline=True
                        )

                        log.add_field(
                            name="Channel",
                            value=ticket_channel.mention,
                            inline=False
                        )

                        await admin_channel.send(
                            embed=log
                        )

                    except Exception as log_error:
                        print(
                            f"Ticket creation log failed: {log_error}"
                        )

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
    async def view_data(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        try:
            await acknowledge_interaction(
                interaction,
                ephemeral=True
            )

            ticket_id = self.ticket_id

            if (
                not ticket_id
                and interaction.message.embeds
            ):

                try:
                    description = (
                        interaction.message.embeds[0].description
                        or ""
                    )

                    ticket_id = description.split("**")[1]

                except Exception:
                    ticket_id = None

            if not ticket_id:
                return await interaction.followup.send(
                    "❌ Ticket reference could not be resolved.",
                    ephemeral=True
                )

            if not interaction.guild:
                return await interaction.followup.send(
                    "❌ This action requires a server.",
                    ephemeral=True
                )

            with get_db() as conn:

                row = conn.execute("""
                    SELECT content
                    FROM ticket_archives
                    WHERE ticket_id = ? AND guild_id = ?
                """, (
                    ticket_id,
                    interaction.guild.id
                )).fetchone()

            if row:

                buffer = io.BytesIO(
                    row["content"].encode("utf-8")
                )

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

        self.staff_role_id = (
            str(staff_role_id)
            if staff_role_id
            else None
        )

    # -----------------------------------------------------
    # CLAIM TICKET
    # -----------------------------------------------------

    @discord.ui.button(
        label="CLAIM TICKET",
        style=discord.ButtonStyle.success,
        emoji="🙋‍♂️",
        custom_id="tkt:claim"
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        try:
            if not is_ticket_staff(interaction):
                return await interaction.response.send_message(
                    "❌ Only the assigned staff can claim this ticket.",
                    ephemeral=True
                )

            await acknowledge_interaction(
                interaction,
                ephemeral=True
            )

            channel = interaction.channel

            opener_id = get_topic_value(
                channel,
                "Asset ID"
            )

            # Preserve all existing channel permissions.
            overwrites = dict(channel.overwrites)

            overwrites[interaction.user] = (
                discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    read_message_history=True
                )
            )

            if opener_id and opener_id.isdigit():

                opener = interaction.guild.get_member(
                    int(opener_id)
                )

                if opener:
                    overwrites[opener] = (
                        discord.PermissionOverwrite(
                            read_messages=True,
                            send_messages=True,
                            attach_files=True,
                            read_message_history=True
                        )
                    )

            old_topic = channel.topic or ""

            topic_parts = [
                part.strip()
                for part in old_topic.split("|")
                if (
                    not part.strip().startswith("Claimed by:")
                    and not part.strip().startswith("Handler ID:")
                )
            ]

            topic_parts.append(
                f"Claimed by: {interaction.user.display_name}"
            )

            topic_parts.append(
                f"Handler ID: {interaction.user.id}"
            )

            await channel.edit(
                overwrites=overwrites,
                topic=" | ".join(topic_parts)
            )

            await interaction.followup.send(
                f"💼 **TICKET ASSIGNED:** "
                f"{interaction.user.mention} has claimed this session.",
                ephemeral=False
            )

        except Exception as e:
            await interaction_error(interaction, e)

    # -----------------------------------------------------
    # PING ADMINS
    # -----------------------------------------------------

    @discord.ui.button(
        label="PING ADMINS",
        style=discord.ButtonStyle.primary,
        emoji="🔔",
        custom_id="tkt:ping_admins"
    )
    async def ping_admins(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        try:
            if not is_ticket_staff(interaction):
                return await interaction.response.send_message(
                    "❌ Only assigned staff can ping the department.",
                    ephemeral=True
                )

            await acknowledge_interaction(
                interaction,
                ephemeral=True
            )

            target_role_ids = get_staff_role_ids(
                interaction.channel,
                self.staff_role_id
            )

            if not target_role_ids:

                with get_db() as conn:

                    config = conn.execute("""
                        SELECT admin_role_id
                        FROM ticket_config
                        WHERE guild_id = ?
                    """, (
                        interaction.guild.id,
                    )).fetchone()

                if config and config["admin_role_id"]:
                    target_role_ids = [
                        int(config["admin_role_id"])
                    ]

            valid_mentions = []

            for role_id in target_role_ids:

                role = interaction.guild.get_role(role_id)

                if role:
                    valid_mentions.append(role.mention)

            if valid_mentions:

                await interaction.followup.send(
                    f"⚠️ {' '.join(valid_mentions)} "
                    "**ATTENTION REQUIRED:** "
                    "Support reinforcement requested.",

                    allowed_mentions=discord.AllowedMentions(
                        roles=True
                    )
                )

            else:
                await interaction.followup.send(
                    "❌ Assigned department roles could not be resolved.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction_error(interaction, e)

    # -----------------------------------------------------
    # CLOSE TICKET
    # -----------------------------------------------------

    @discord.ui.button(
        label="CLOSE SESSION",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="tkt:close"
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        try:
            channel = interaction.channel

            opener_id = get_topic_value(
                channel,
                "Asset ID"
            )

            is_opener = (
                opener_id
                and opener_id.isdigit()
                and int(opener_id) == interaction.user.id
            )

            if not is_ticket_staff(interaction) and not is_opener:
                return await interaction.response.send_message(
                    "❌ Only the ticket opener or assigned staff "
                    "can close this ticket.",
                    ephemeral=True
                )

            await acknowledge_interaction(
                interaction,
                ephemeral=False
            )

            transcript = (
                f"--- BLACK BOX TRANSCRIPT: {channel.name} ---\n"
                f"Asset ID: {opener_id or 'Unknown'}\n"
                f"Closed by: {interaction.user.display_name}\n"
                f"Sealed on: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                + "-" * 40
                + "\n\n"
            )

            async for message in channel.history(
                limit=None,
                oldest_first=True
            ):

                timestamp = message.created_at.strftime(
                    "%Y-%m-%d %H:%M"
                )

                content = (
                    message.clean_content
                    if message.content
                    else "[Attachment/Embed]"
                )

                if message.attachments:
                    content += (
                        " | Attachments: "
                        + ", ".join(
                            attachment.url
                            for attachment in message.attachments
                        )
                    )

                transcript += (
                    f"[{timestamp}] "
                    f"{message.author.display_name}: "
                    f"{content}\n"
                )

            ticket_id = channel.name

            # Save transcript BEFORE deleting the channel.
            with get_db() as conn:

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

            with get_db() as conn:

                config = conn.execute("""
                    SELECT admin_channel
                    FROM ticket_config
                    WHERE guild_id = ?
                """, (
                    interaction.guild.id,
                )).fetchone()

            # Logging failure does not delete the saved transcript.
            if config and config["admin_channel"]:

                admin_channel = interaction.guild.get_channel(
                    config["admin_channel"]
                )

                if admin_channel:

                    try:
                        archive_embed = discord.Embed(
                            title="📸 EVIDENCE ARCHIVED",
                            description=(
                                f"Session **{ticket_id}** has been sealed. "
                                "Data logged to database."
                            ),
                            color=0x2F3136
                        )

                        await admin_channel.send(
                            embed=archive_embed,
                            view=ArchiveViewer(ticket_id)
                        )

                    except Exception as log_error:
                        print(
                            f"Archive log delivery failed: {log_error}"
                        )

            await interaction.followup.send(
                "⛓️ Session sealed. Data stored in Black Box. "
                "Purging in 5 seconds..."
            )

            await asyncio.sleep(5)

            await channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )

        except Exception as e:
            await interaction_error(interaction, e)


# ---------------------------------------------------------
# PERSISTENT VIEW REGISTRATION
# ---------------------------------------------------------

async def setup(bot):

    # Initialise database before restoring views.
    initialise_database()

    await bot.add_cog(
        ReactionRoleSystem(bot)
    )

    # -----------------------------------------------------
    # RESTORE SAVED VIEWS
    # -----------------------------------------------------

    try:

        with get_db() as conn:

            # ---------------------------------------------
            # REACTION ROLE PANELS
            # ---------------------------------------------

            rr_rows = conn.execute("""
                SELECT message_id, emoji, role_id, label
                FROM reaction_roles
            """).fetchall()

            rr_dict = {}

            for row in rr_rows:

                message_id = row["message_id"]

                if message_id not in rr_dict:
                    rr_dict[message_id] = {}

                rr_dict[message_id][row["emoji"]] = {
                    "role_id": row["role_id"],
                    "label": row["label"] or "Select Role"
                }

            for message_id, mappings in rr_dict.items():

                try:
                    bot.add_view(
                        ReactionRoleView(mappings),
                        message_id=message_id
                    )

                except Exception as e:
                    print(
                        f"Could not restore reaction role panel "
                        f"{message_id}: {e}"
                    )

            # ---------------------------------------------
            # TICKET LOBBY PANELS
            # ---------------------------------------------

            panel_rows = conn.execute("""
                SELECT guild_id, message_id, channel_id
                FROM ticket_panels
            """).fetchall()

            for panel in panel_rows:

                guild_id = panel["guild_id"]

                try:

                    btns = conn.execute("""
                        SELECT label, emoji, btn_index, staff_role_id
                        FROM ticket_buttons
                        WHERE guild_id = ?
                        ORDER BY btn_index
                    """, (
                        guild_id,
                    )).fetchall()

                    configs = [
                        {
                            "label": row["label"],
                            "emoji": row["emoji"],
                            "staff_role_id": (
                                str(row["staff_role_id"] or "")
                            )
                        }
                        for row in btns
                    ]

                    if configs:

                        bot.add_view(
                            TicketLobbyView(configs),
                            message_id=panel["message_id"]
                        )

                except Exception as e:
                    print(
                        f"Could not restore ticket panel "
                        f"{panel['message_id']}: {e}"
                    )

    except Exception as e:
        print("Persistent view restoration failed:")
        traceback.print_exc()

    # -----------------------------------------------------
    # GLOBAL PERSISTENT VIEWS
    # -----------------------------------------------------

    bot.add_view(TicketControls())
    bot.add_view(DesignerLobby())
    bot.add_view(ArchiveViewer())

    print("Echo persistent views registered successfully.")
    print("Echo ticket system loaded.")
