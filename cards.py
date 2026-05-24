import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import sys
import os
import json
import io # ADDED: Required for the image buffer
import aiohttp # ADDED: Required for avatar processing
from PIL import Image, ImageDraw, ImageFont, ImageFilter # ADDED: For 2030 holographic tech

# --- NEW COMPONENT: INFO BUTTON ---

class InfoView(discord.ui.View):
    def __init__(self, card_data=None):
        # Setting timeout to None helps the button stay active longer
        super().__init__(timeout=None)
        self.card_data = card_data

    @discord.ui.button(label="🔍 View Intel", style=discord.ButtonStyle.secondary, custom_id="view_intel_persistent")
    async def view_intel(self, interaction: discord.Interaction):
        # The logic is now handled by the Cog Listener for 100% reliability
        pass

# --- NEW COMPONENT: VELVETDEX SELECT ---

class VelvetdexSelect(discord.ui.Select):
    def __init__(self, cards):
        options = []
        # Create an option for each caught card
        for c in cards:
            options.append(discord.SelectOption(
                label=c['card_name'], 
                description=f"Tier: {c['tier'].upper()}", 
                value=str(c['id'])
            ))
        super().__init__(placeholder="📂 Select an asset to inspect...", options=options)

    async def callback(self, interaction: discord.Interaction):
        main_mod = sys.modules['__main__']
        card_db_id = self.values[0]
        
        with main_mod.get_db_connection() as conn:
            row = conn.execute(
                "SELECT card_name, tier, intel, powers FROM user_cards WHERE rowid = ?",
                (card_db_id,)
            ).fetchone()

        if not row:
            return await interaction.response.send_message("❌ Signature record not found.", ephemeral=True)

        card_name, tier, intel, p_raw = row[0], row[1], row[2], row[3]
        try:
            p = json.loads(p_raw)
        except:
            p = {"Tease": 0, "Flirt": 0, "Sex": 0, "Magic": 0}

        # ADDED: Tier-based color mapping for the intel embed
        tier_colors = {
            "supreme": 0xFF0000,
            "legendary": 0xFF8C00,
            "platine": 0xE5E4E2,
            "epic": 0x9B59B6,
            "rare": 0x3498DB,
            "basic": 0x95A5A6
        }
        embed_color = tier_colors.get(tier.lower(), 0xFF69B4)

        power_display = (
            f"**🔥 Tease:** {p.get('Tease', 0)}/100\n"
            f"**💘 Flirt:** {p.get('Flirt', 0)}/100\n"
            f"**🔞 Sex:** {p.get('Sex', 0)}/100\n"
            f"**✨ Magic:** {p.get('Magic', 0)}/100"
        )

        embed = discord.Embed(
            title=f"🧬 ASSET INTEL: {card_name.upper()}",
            description=f"**Tier:** `{tier.upper()}`\n\n**Classified Intel:**\n*{intel}*\n\n**Power Metrics:**\n{power_display}",
            color=embed_color
        )
        
        # ADDED: View with a "Set as Pet" button using a persistent-style custom_id
        # FIXED: card_db_id is passed as the identifying factor
        view = PetSelectionView(card_db_id, card_name)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- NEW COMPONENT: PET SELECTION ---

class PetSelectionView(discord.ui.View):
    def __init__(self, card_db_id, card_name):
        super().__init__(timeout=60)
        self.card_db_id = card_db_id
        self.card_name = card_name

    @discord.ui.button(label="🐾 Set as Active Pet", style=discord.ButtonStyle.success, custom_id="set_pet_persistent")
    async def set_pet(self, interaction: discord.Interaction):
        # Logic moved to Cog Listener to prevent "Interaction Failed"
        pass

class VelvetdexView(discord.ui.View):
    def __init__(self, cards, target, current_page=0):
        super().__init__(timeout=180)
        self.cards = cards
        self.target = target
        self.current_page = current_page
        self.per_page = 25
        
        # Calculate slices for pagination
        start = self.current_page * self.per_page
        end = start + self.per_page
        current_slice = self.cards[start:end]
        
        # Add Select menu
        self.add_item(VelvetdexSelect(current_slice))
        
        # Disable buttons based on page count
        if len(self.cards) > self.per_page:
            prev_btn = discord.ui.Button(label="⬅️ Previous", style=discord.ButtonStyle.gray, disabled=(self.current_page == 0))
            prev_btn.callback = self.prev_page
            
            next_btn = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.gray, disabled=(end >= len(self.cards)))
            next_btn.callback = self.next_page
            
            self.add_item(prev_btn)
            self.add_item(next_btn)

    async def update_view(self, interaction: discord.Interaction):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            pet_row = conn.execute("SELECT card_name FROM user_pets WHERE user_id = ?", (self.target.id,)).fetchone()
            pet_display = f"\n🐾 **Active Pet:** {pet_row[0]}" if pet_row else "\n🐾 **Active Pet:** None"
        
        embed = main_mod.fiery_embed(f"📂 {self.target.display_name.upper()}'S VELVETDEX", 
                                     f"Select an asset signature from the dropdown (Page {self.current_page + 1}).{pet_display}")
        
        # Re-create view to update buttons/select
        new_view = VelvetdexView(self.cards, self.target, self.current_page)
        await interaction.response.edit_message(embed=embed, view=new_view)

    async def next_page(self, interaction: discord.Interaction):
        self.current_page += 1
        await self.update_view(interaction)

    async def prev_page(self, interaction: discord.Interaction):
        self.current_page -= 1
        await self.update_view(interaction)

# --- INTERACTIVE POKEDEX COMPONENTS ---

class PokedexView(discord.ui.View):
    def __init__(self, target, data, card_pool, fiery_embed_func):
        super().__init__(timeout=60)
        self.target = target
        self.data = data # Dict: {collection_type: [cards]}
        self.card_pool = card_pool
        self.fiery_embed = fiery_embed_func
        self.current_category = list(data.keys())[0] if data else None

    @discord.ui.select(placeholder="📂 Filter by Collection Type...", custom_id="poke_filter")
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("This is not your archive, toy.", ephemeral=True)
        
        self.self.current_category = select.values[0]
        await self.update_display(interaction)

    async def update_display(self, interaction):
        cards = self.data.get(self.current_category, [])
        desc = f"### 🗂️ {self.current_category.upper()} COLLECTION\n"
        
        for c in cards:
            desc += f"• **{c['name']}** (`{c['tier'].upper()}`) — x{c['count']}\n"
        
        embed = self.fiery_embed(f"📕 {self.target.display_name}'S ARCHIVE", desc)
        embed.set_footer(text=f"Viewing {self.current_category} | Protocol V8.0")
        await interaction.response.edit_message(embed=embed, view=self)

class CardSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spawn_channel_id = None 
        self.current_card = None
        
        # ACTIVITY LOGIC: restored and tied to member-spawns
        self.activity_pool = 0
        self.required_activity = 25 
        
        self._init_db()
        
        # PERSISTENCE: Restore the spawn channel from the central config table
        self._load_config()

        # SERIES DEFINITIONS (Used to flavor the member-cards)
        self.series_types = ["Slut", "Dominator", "Submissive", "Switcher", "Threesomer", "Dirty", "Cummer", "Bossy", "Pimp", "Cum Cleaner"]

        # 50 RANDOM SILLY NAUGHTY SENTENCES
        self.intel_pool = [
            "Secretly enjoys being watched through the webcam.", "Always forgets their safe word during intense 'archiving'.",
            "Has a collection of toys hidden in the server basement.", "Thinks 'SQL injection' is a type of bedroom play.",
            "Wears lace under that digital avatar skin.", "Is 100% likely to send a risky text at 3 AM.",
            "Can't resist the sound of handcuffs clicking.", "Actually prefers the 'Cum Cleaner' series over everything.",
            "Has been a very naughty asset this week.", "Wants to be dominated by the bot's master code.",
            "Known for leaving wet patches in the neural vents.", "Frequently visits the 'special' channels in incognito.",
            "Their favorite exercise is 'horizontal cardio'.", "Spends too much time looking at 'asset' photos.",
            "Has a hidden tattoo only the Dominator tier can see.", "Obsessed with the feeling of cold latex.",
            "Always ready for a quick neural upload in the bathroom.", "Has a folder named 'Tax Returns' that is definitely not taxes.",
            "Dreams of being shared by a full Threesomer squad.", "Likes it rough, especially when the server lags.",
            "Their moans can be heard across three different nodes.", "Prefers to be 'archived' face down.",
            "The loudest asset in the entire neural network.", "Known for breaking the 'no touching' protocol.",
            "Has a dirty mind that would crash a lesser AI.", "Secretly wants to be the server's favorite toy.",
            "Can make a grown admin blush with a single DM.", "Always 'up' for a challenge, regardless of the tier.",
            "Leaves lip marks on the monitor screen.", "Has a list of kinks longer than the bot's code.",
            "Actually enjoys being caught and archived.", "Always asks for 'just one more' round of testing.",
            "The primary reason the server needs a 'Cum Cleaner'.", "Wants to explore every corner of your database.",
            "A total switcher when the lights go out.", "Thinks the Pokedex is a menu for a wild night.",
            "Always carries a spare pair of digital cuffs.", "Their favorite sound is the notification of a new catch.",
            "Likes to play 'Master and Asset' during maintenance.", "Has a 'submissive' mode triggered by certain keywords.",
            "Can handle more 'data' than you can provide.", "Known for making the thermal vents overheat.",
            "Always looking for a Threesomer partner in the chat.", "Has a very high 'Magic' rating for bedroom tricks.",
            "Thinks a 'hard drive' is a suggestion, not hardware.", "Secretly records their sessions for the Pimp series.",
            "Would sell their soul for a Supreme tier night.", "The dirtiest asset ever recorded in this sector.",
            "Always wet and ready for a neural sync.", "Never says no to a 'Dirty' series encounter."
        ]

    # --- ADDED: 2030 HOLOGRAPHIC TECH ---
    async def create_holographic_card(self, avatar_url, tier):
        tier_colors = {
            "supreme": (255, 0, 0), "legendary": (255, 140, 0), "platine": (229, 228, 226),
            "epic": (155, 89, 182), "rare": (52, 152, 219), "basic": (149, 165, 166)
        }
        color = tier_colors.get(tier.lower(), (255, 105, 180))
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as r:
                av = Image.open(io.BytesIO(await r.read())).convert("RGBA").resize((600, 600))
        canvas = Image.new("RGBA", (700, 1000), (10, 10, 15, 255))
        draw = ImageDraw.Draw(canvas)
        
        # --- ADDED: DYNAMIC HOLOGRAPHIC AURA ---
        if tier.lower() == "supreme":
            for w in range(25, 0, -2):
                draw.rectangle([10-w, 10-w, 690+w, 990+w], outline=(255, 0, 0, int(255 - (w * 10))), width=2)
        elif tier.lower() == "legendary":
            for w in range(15, 0, -2):
                draw.rectangle([10-w, 10-w, 690+w, 990+w], outline=(255, 140, 0, int(255 - (w * 15))), width=2)

        draw.rectangle([10, 10, 690, 990], outline=color, width=15)
        canvas.paste(av, (50, 100), av)
        
        # --- ADDED: SCANLINE EFFECTS ---
        if tier.lower() == "supreme":
            for i in range(0, 1000, 8): 
                draw.line([(0, i), (700, i)], fill=(255, 50, 50, 40), width=3)
            for i in range(0, 1000, 25):
                glitch_y = i + random.randint(-8, 8)
                draw.line([(0, glitch_y), (700, glitch_y)], fill=(255, 255, 255, 80), width=1)
        else:
            for i in range(0, 1000, 4): draw.line([(0, i), (700, i)], fill=(255, 255, 255, 15))
            
        draw.text((30, 950), f"SYS_SYNC: 0x{random.randint(1000,9999)}-{tier.upper()}", fill=(0, 255, 255, 100))
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def _init_db(self):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            # Updated table to include intel and powers
            conn.execute("CREATE TABLE IF NOT EXISTS user_cards (user_id INTEGER, card_name TEXT, tier TEXT, intel TEXT, powers TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
            conn.execute("CREATE TABLE IF NOT EXISTS card_config (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS card_mastery (user_id INTEGER, mastery_key TEXT, PRIMARY KEY (user_id, mastery_key))")
            # NEW TABLE: To store the pet/companion (added avatar_url column)
            conn.execute("CREATE TABLE IF NOT EXISTS user_pets (user_id INTEGER PRIMARY KEY, card_rowid INTEGER, card_name TEXT, avatar_url TEXT)")
            # ADDED: PING TABLE
            conn.execute("CREATE TABLE IF NOT EXISTS supreme_pings (user_id INTEGER PRIMARY KEY)")
            
            # Migration check: add columns if they don't exist in an old DB
            cursor = conn.execute("PRAGMA table_info(user_cards)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'intel' not in columns:
                conn.execute("ALTER TABLE user_cards ADD COLUMN intel TEXT")
            if 'powers' not in columns:
                conn.execute("ALTER TABLE user_cards ADD COLUMN powers TEXT")
            
            # Migration check for user_pets
            cursor = conn.execute("PRAGMA table_info(user_pets)")
            pet_cols = [column[1] for column in cursor.fetchall()]
            if 'avatar_url' not in pet_cols:
                conn.execute("ALTER TABLE user_pets ADD COLUMN avatar_url TEXT")
            
            conn.commit()

    def _load_config(self):
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                print("[SYS] Attempting to load spawn_channel_id from database...") # ADDED
                row = conn.execute("SELECT value FROM card_config WHERE key = 'spawn_channel'").fetchone()
                if row:
                    self.spawn_channel_id = int(row['value'])
                    print(f"[SYS] Successfully loaded spawn_channel_id: {self.spawn_channel_id}") # ADDED
                else:
                    print("[SYS] No spawn_channel_id found in database. Await !setcards command.") # ADDED
        except Exception as e:
            print(f"[SYS] Error loading config: {e}") # ADDED
            pass

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """THE GLOBAL FIX: Listens for the persistent button IDs."""
        if interaction.type != discord.InteractionType.component: return
        custom_id = interaction.data.get('custom_id')
        
        main_mod = sys.modules['__main__']
        user_id = interaction.user.id

        # --- LOGIC FOR VIEW INTEL ---
        if custom_id == "view_intel_persistent":
            with main_mod.get_db_connection() as conn:
                row = conn.execute(
                    "SELECT card_name, tier, intel, powers FROM user_cards WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
                    (user_id,)
                ).fetchone()

            if not row:
                return await interaction.response.send_message("❌ Signature data corrupted or archive empty.", ephemeral=True)

            card_name, tier, intel_text, p_raw = row[0], row[1], row[2], row[3]
            try:
                p = json.loads(p_raw)
            except:
                p = {"Tease": 0, "Flirt": 0, "Sex": 0, "Magic": 0}

            # ADDED: Tier-based color mapping for the intel embed
            tier_colors = {
                "supreme": 0xFF0000,
                "legendary": 0xFF8C00,
                "platine": 0xE5E4E2,
                "epic": 0x9B59B6,
                "rare": 0x3498DB,
                "basic": 0x95A5A6
            }
            embed_color = tier_colors.get(tier.lower(), 0xFF69B4)

            power_display = (
                f"**🔥 Tease:** {p.get('Tease', 0)}/100\n"
                f"**💘 Flirt:** {p.get('Flirt', 0)}/100\n"
                f"**🔞 Sex:** {p.get('Sex', 0)}/100\n"
                f"**✨ Magic:** {p.get('Magic', 0)}/100"
            )
            
            intel_embed = discord.Embed(
                title=f"📜 CLASSIFIED: {card_name}",
                description=f"*{intel_text}*\n\n{power_display}",
                color=embed_color
            )
            await interaction.response.send_message(embed=intel_embed, ephemeral=True)

        # --- LOGIC FOR SET PET ---
        elif custom_id == "set_pet_persistent":
            # FIXED: Robust parsing of card name from Intel embed title
            if not interaction.message.embeds: return
            title = interaction.message.embeds[0].title
            # Handles "🧬 ASSET INTEL: NAME" format by stripping prefix
            card_name = title.split(":")[-1].strip()

            with main_mod.get_db_connection() as conn:
                # Find the rowid and original name for this specific card using name check
                row = conn.execute("SELECT rowid, card_name FROM user_cards WHERE user_id = ? AND UPPER(card_name) = ? ORDER BY timestamp DESC LIMIT 1", (user_id, card_name.upper())).fetchone()
                if row:
                    db_rowid = row[0]
                    db_name = row[1]
                    avatar_url = None
                    
                    # Robust search for member avatar URL
                    target_member = discord.utils.get(interaction.guild.members, display_name=db_name)
                    if not target_member:
                        target_member = discord.utils.get(interaction.guild.members, name=db_name)
                    
                    if target_member:
                        avatar_url = target_member.display_avatar.url
                    
                    conn.execute("INSERT OR REPLACE INTO user_pets (user_id, card_rowid, card_name, avatar_url) VALUES (?, ?, ?, ?)", 
                                 (user_id, db_rowid, db_name, avatar_url))
                    conn.commit()
                    await interaction.response.send_message(f"✅ **{db_name}** is now your active pet following you!", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Failed to find **{card_name}** in your archive. Re-open !velvetdex.", ephemeral=True)

    @commands.command(name="setcards")
    @commands.has_permissions(administrator=True)
    async def setcards(self, ctx, channel: discord.TextChannel):
        """Admin command to bind the card spawn frequency to a channel."""
        self.spawn_channel_id = channel.id
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO card_config (key, value) VALUES ('spawn_channel', ?)", (str(channel.id),))
            conn.commit()
        
        embed = main_mod.fiery_embed("Coordinates Synchronized", 
            f"The Master has locked the card emergence point to {channel.mention}.\n\n"
            f"**Status:** Emergence protocols are now active in this sector.", color=0x00FF00)
        await ctx.send(embed=embed)

    @commands.command()
    async def supremeping(self, ctx):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO supreme_pings VALUES (?)", (ctx.author.id,))
            conn.commit()
        await ctx.send("✅ You will be pinged when a SUPREME card manifests.")

    @commands.command()
    async def nosupremeping(self, ctx):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("DELETE FROM supreme_pings WHERE user_id = ?", (ctx.author.id,))
            conn.commit()
        await ctx.send("✅ You have been removed from the Supreme Alert protocol.")

    def get_random_tier(self):
        roll = random.random() * 100
        if roll < 0.8: return "supreme", 0xFF0000
        if roll < 4.0: return "legendary", 0xFF8C00
        if roll < 12.0: return "platine", 0xE5E4E2
        if roll < 28.0: return "epic", 0x9B59B6
        if roll < 55.0: return "rare", 0x3498DB
        return "basic", 0x95A5A6

    async def spawn_card(self, guild):
        """LOCALIZATION SEQUENCE: Selects a member and ROLLS A NEW RARITY every time."""
        print(f"[SYS] Initiating spawn sequence for {guild.name}...") # ADDED
        if not self.spawn_channel_id: 
            print("[SYS] Aborting spawn: spawn_channel_id is currently None.") # ADDED
            return
        channel = self.bot.get_channel(self.spawn_channel_id)
        if not channel: 
            print(f"[SYS] Aborting spawn: Channel ID {self.spawn_channel_id} not found in guild.") # ADDED
            return
        print(f"[SYS] Manifestation point locked on: {channel.name}. Proceeding...") # ADDED

        # FIXED: Enforced server localization by forcing an API chunk fetch to clean internal cross-server member leaks completely
        try:
            await guild.chunk()
        except:
            pass

        members = [m for m in guild.members if not m.bot]
        if not members: return
        target_member = random.choice(members)

        # TRIGGER NEW RARITY ROLL: Independent of the user identity
        tier_name, color = self.get_random_tier()
        series = random.choice(self.series_types)
        
        # RARITY POWER SCALING LOGIC
        # Basic: 1-40 | Rare: 30-60 | Epic: 50-80 | Platine: 70-90 | Legendary: 85-98 | Supreme: 95-100
        if tier_name == "supreme": low, high = 95, 100
        elif tier_name == "legendary": low, high = 85, 98
        elif tier_name == "platine": low, high = 70, 90
        elif tier_name == "epic": low, high = 50, 80
        elif tier_name == "rare": low, high = 30, 60
        else: low, high = 1, 40 # Basic

        # GENERATE RANDOM INTEL AND POWERS
        intel_text = random.choice(self.intel_pool)
        powers = {
            "Tease": random.randint(low, high), 
            "Flirt": random.randint(low, high), 
            "Sex": random.randint(low, high), 
            "Magic": random.randint(low, high)
        }

        self.current_card = {
            "name": target_member.display_name,
            "tier": tier_name,
            "type": series,
            "id": target_member.id,
            "intel": intel_text,
            "powers": powers
        }

        main_mod = sys.modules['__main__']
        
        # --- CALL THE HOLOGRAPHIC GENERATOR ---
        img_buf = await self.create_holographic_card(target_member.display_avatar.url, tier_name)
        file = discord.File(img_buf, filename="card.png")
        
        desc = (
            f"⚡ **ACTIVITY SPIKE DETECTED:** A soul has manifested in the thermal vents!\n\n"
            f"👤 **Asset:** {target_member.mention}\n"
            f"🧬 **Series:** {series}\n"
            f"💎 **Tier:** `{tier_name.upper()}`"
        )
        
        # SUPREME PING LOGIC
        ping_str = ""
        if tier_name == "supreme":
            with main_mod.get_db_connection() as conn:
                pings = conn.execute("SELECT user_id FROM supreme_pings").fetchall()
                ping_str = " ".join([f"<@{p[0]}>" for p in pings])
        
        embed = main_mod.fiery_embed("🛰️ NEURAL ASSET LOCALIZED", desc, color=color)
        embed.set_image(url="attachment://card.png")
        embed.set_footer(text=f"Triggered by server activity | {series} series")
        
        # Send main big informational embed
        await channel.send(content=ping_str, embed=embed, file=file)
        
        # Send ONLY the command block for clean copy-paste
        await channel.send(f"!catch {target_member.display_name}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """The Listener: Increments activity pool and checks for spawn readiness."""
        if message.author.bot or not message.guild: return
        
        # Track global server activity
        self.activity_pool += 1
        
        if self.activity_pool >= self.required_activity:
            # Chance check lowered to 0.25 (25%) to slow down the high-frequency drops
            if random.random() < 0.25: 
                self.activity_pool = 0
                await self.spawn_card(message.guild)

    async def check_mastery(self, ctx, user_id):
        pass

    @commands.command()
    async def catch(self, ctx, *, card_name: str):
        # FIX: strip whitespace and use case-insensitive matching to solve "invalid name" errors
        if not self.current_card or card_name.strip().lower() != self.current_card['name'].strip().lower():
            return await ctx.reply("❌ Asset signal lost or incorrect ID signature!")
        
        main_mod = sys.modules['__main__']
        user_id = ctx.author.id
        card = self.current_card
        
        # Prepare View - Passing card here though the listener handles it
        view = InfoView(card)
        self.current_card = None 

        with main_mod.get_db_connection() as conn:
            # Save card with Intel and Powers (serialized to JSON)
            conn.execute(
                "INSERT INTO user_cards (user_id, card_name, tier, intel, powers) VALUES (?, ?, ?, ?, ?)", 
                (user_id, card['name'], card['tier'], card['intel'], json.dumps(card['powers']))
            )
            conn.commit()
            total_count = conn.execute("SELECT COUNT(*) FROM user_cards WHERE user_id = ?", (user_id,)).fetchone()[0]

        # Get color based on tier
        _, color = self.get_random_tier()
        
        embed = main_mod.fiery_embed("🔥 ASSET SECURED!", f"{ctx.author.mention} has archived **{card['name']}**!", color=color)
        
        # --- FOOLPROOF WORKAROUND FOR PREVIOUS SYNTAX ERROR ---
        metadata_value = "**Series:** " + str(card['type']) + "\n**Tier:** " + str(card['tier']).upper()
        embed.add_field(name="🧬 Metadata", value=metadata_value, inline=True)
        
        embed.add_field(name="📊 Archive", value=f"**Total Assets:** {total_count}", inline=True)
        
        target_member = ctx.guild.get_member(card['id'])
        if target_member:
            embed.set_thumbnail(url=target_member.display_avatar.url)

        await ctx.send(embed=embed, view=view)

    @commands.command(name="pokedex")
    async def pokedex(self, ctx, member: discord.Member = None):
        """Displays the neural archive sorted by rarity and user identity."""
        target = member or ctx.author
        main_mod = sys.modules['__main__']
        
        with main_mod.get_db_connection() as conn:
            # Retrieve intel and powers along with count
            rows = conn.execute(
                "SELECT card_name, tier, intel, powers, COUNT(*) as count FROM user_cards WHERE user_id = ? "
                "GROUP BY card_name, tier ORDER BY "
                "CASE tier WHEN 'supreme' THEN 1 WHEN 'legendary' THEN 2 WHEN 'platine' THEN 3 "
                "WHEN 'epic' THEN 4 WHEN 'rare' THEN 5 ELSE 6 END", 
                (target.id,)
            ).fetchall()
            
            # Logic to count unique members caught
            unique_members_caught = conn.execute(
                "SELECT COUNT(DISTINCT card_name) FROM user_cards WHERE user_id = ?", 
                (target.id,)
            ).fetchone()[0]

            # FETCH PET DATA
            pet_row = conn.execute("SELECT card_name, avatar_url FROM user_pets WHERE user_id = ?", (target.id,)).fetchone()
            pet_name = pet_row[0] if pet_row else "None"
            pet_avatar = pet_row[1] if pet_row else None

        if not rows:
            return await ctx.send(f"📕 {target.display_name}'s Archive is empty. No neural patterns recorded.")

        # Logic to count server members (excluding bots)
        server_member_count = len([m for m in ctx.guild.members if not m.bot])

        # Organize by rarity for the embed fields
        tiers_data = {}
        last_card_caught = None 
        for row in rows:
            name, tier, intel, powers, count = row[0], row[1], row[2], row[3], row[4]
            if tier not in tiers_data: tiers_data[tier] = []
            tiers_data[tier].append(f"• **{name}** x{count}")
            # Prep data for the button
            last_card_caught = {"name": name, "intel": intel, "powers": powers}

        embed = main_mod.fiery_embed(f"📕 {target.display_name.upper()}'S NEURAL ARCHIVE", 
                                     f"The archive holds the following digitized signatures:\n\n🐾 **Active Pet:** {pet_name}")
        
        # If pet exists, show their thumbnail; otherwise show target's
        if pet_avatar:
            embed.set_thumbnail(url=pet_avatar)
        else:
            embed.set_thumbnail(url=target.display_avatar.url)

        # Add the progress field
        progress_val = f"**{unique_members_caught}** / **{server_member_count}** Members archived."
        embed.add_field(name="📡 COLLECTION PROGRESS", value=progress_val, inline=False)

        for tier, cards_list in tiers_data.items():
            content = "\n".join(cards_list)
            if len(content) > 1024: content = content[:1020] + "..."
            embed.add_field(name=f"💎 {tier.upper()} TIER", value=content, inline=False)

        embed.set_footer(text=f"Total Unique Signatures: {len(rows)} | Data Persists Forever")
        
        # Create a view if there is intel to show
        view = InfoView(last_card_caught) if last_card_caught else None
        await ctx.send(embed=embed, view=view)

    @commands.command(name="velvetdex")
    async def velvetdex(self, ctx, member: discord.Member = None):
        """Consult the specific stats and intel of assets caught by a user."""
        target = member or ctx.author
        main_mod = sys.modules['__main__']

        with main_mod.get_db_connection() as conn:
            # Get individual rows to display in the select menu
            # NEW: Sorted by top rarity first for better organization
            rows = conn.execute(
                "SELECT rowid, card_name, tier FROM user_cards WHERE user_id = ? ORDER BY "
                "CASE tier WHEN 'supreme' THEN 1 WHEN 'legendary' THEN 2 WHEN 'platine' THEN 3 "
                "WHEN 'epic' THEN 4 WHEN 'rare' THEN 5 ELSE 6 END, timestamp DESC",
                (target.id,)
            ).fetchall()

            # FETCH PET DATA
            pet_row = conn.execute("SELECT card_name, avatar_url FROM user_pets WHERE user_id = ?", (target.id,)).fetchone()
            pet_display = f"\n🐾 **Active Pet:** {pet_row[0]}" if pet_row else "\n🐾 **Active Pet:** None"
            pet_avatar = pet_row[1] if pet_row else None

        if not rows:
            return await ctx.send(f"📕 {target.display_name}'s Velvetdex is currently offline. No assets recorded.")

        # Structure data for the view
        card_list = []
        for r in rows:
            card_list.append({'id': r[0], 'card_name': r[1], 'tier': r[2]})

        embed = main_mod.fiery_embed(f"📂 {target.display_name.upper()}'S VELVETDEX", 
                                     f"Select an asset signature from the dropdown to access encrypted metadata.{pet_display}")
        
        # If pet exists, show their thumbnail; otherwise show target's
        if pet_avatar:
            embed.set_thumbnail(url=pet_avatar)
        else:
            embed.set_thumbnail(url=target.display_avatar.url)
        
        # FIXED: Using Paginated VelvetdexView
        view = VelvetdexView(card_list, target)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="collections")
    async def collections(self, ctx, member: discord.Member = None):
        await ctx.send("The Checklist Protocol is analyzing the human metadata...")

async def setup(bot):
    await bot.add_cog(CardSystem(bot))
