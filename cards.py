import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import sys
import os

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
        
        self.current_category = select.values[0]
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
        self.spawn_channel_id = 1438810509322223677 # Update to your target channel
        self.current_card = None
        self.activity_pool = 0
        self.required_activity = 10 # Messages needed to trigger spawn
        self._init_db()
        self.card_spawn_loop.start()
        
        # PERSISTENCE: Restore the spawn channel from the central config table
        self._load_config()

        # COMPLETE CARD POOL (Including every single uploaded file)
        self.card_pool = [
            # LAVA SERIES
            {"name": "Lava Core", "tier": "basic", "type": "Lava", "image": "lava_BASIC_1.png"},
            {"name": "Lava Surge", "tier": "rare", "type": "Lava", "image": "lava_RARE_1.png"},
            {"name": "Lava Titan", "tier": "epic", "type": "Lava", "image": "lava_EPIC_1.png"},
            {"name": "Lava Sentry", "tier": "platine", "type": "Lava", "image": "lava_PLAT_1.png"},
            {"name": "Lava King", "tier": "legendary", "type": "Lava", "image": "lava_LEGENDARY_1.png"},
            {"name": "Lava God", "tier": "supreme", "type": "Lava", "image": "lava_SUPREME_1.png"},
            
            # GLADIATOR SERIES
            {"name": "Gladiator Recruit", "tier": "basic", "type": "Gladiator", "image": "gladiator_BASIC_1.png"},
            {"name": "Gladiator Veteran", "tier": "rare", "type": "Gladiator", "image": "gladiator_RARE_1.png"},
            {"name": "Gladiator Champion", "tier": "epic", "type": "Gladiator", "image": "gladiator_EPIC_1.png"},
            {"name": "Gladiator Elite", "tier": "platine", "type": "Gladiator", "image": "gladiator_PLAT_1.png"},
            {"name": "Gladiator Legend", "tier": "legendary", "type": "Gladiator", "image": "gladiator_LEGENDARY_1.png"},
            {"name": "Gladiator Emperor", "tier": "supreme", "type": "Gladiator", "image": "gladiator_SUPREME_1.png"},

            # WATER SERIES
            {"name": "Water Spirit", "tier": "basic", "type": "Water", "image": "water_BASIC_1.png"},
            {"name": "Water Wraith", "tier": "rare", "type": "Water", "image": "water_RARE_1.png"},
            {"name": "Water Drake", "tier": "epic", "type": "Water", "image": "water_EPIC_1.png"},
            {"name": "Water Guardian", "tier": "platine", "type": "Water", "image": "water_PLAT_1.png"},
            {"name": "Water Sovereign", "tier": "legendary", "type": "Water", "image": "water_LEGENDARY_1.png"},
            {"name": "Water Deity", "tier": "supreme", "type": "Water", "image": "water_SUPREME_1.png"},

            # SPACE SERIES
            {"name": "Space Dust", "tier": "basic", "type": "Space", "image": "space_BASIC_1.png"},
            {"name": "Space Nebula", "tier": "rare", "type": "Space", "image": "space_RARE_1.png"},
            {"name": "Space Pulsar", "tier": "epic", "type": "Space", "image": "space_EPIC_1.png"},
            {"name": "Space Rift", "tier": "platine", "type": "Space", "image": "space_PLAT_1.png"},
            {"name": "Space Singularity", "tier": "legendary", "type": "Space", "image": "space_LEGENDARY_1.png"},
            {"name": "Space Overlord", "tier": "supreme", "type": "Space", "image": "space_SUPREME_1.png"},

            # GRASS SERIES
            {"name": "Grass Sprout", "tier": "basic", "type": "Grass", "image": "grass_BASIC_1.png"},
            {"name": "Grass Guardian", "tier": "rare", "type": "Grass", "image": "grass_RARE_1.png"},
            {"name": "Grass Ancient", "tier": "epic", "type": "Grass", "image": "grass_EPIC_1.png"},
            {"name": "Grass Warden", "tier": "platine", "type": "Grass", "image": "grass_PLAT_1.png"},
            {"name": "Grass Avatar", "tier": "legendary", "type": "Grass", "image": "grass_LEGENDARY_1.png"},
            {"name": "Grass Creator", "tier": "supreme", "type": "Grass", "image": "grass_SUPREME_1.png"},

            # TRICITY SERIES
            {"name": "Tricity Circuit", "tier": "basic", "type": "Tricity", "image": "tricity_basic_1.png"},
            {"name": "Tricity Pulse", "tier": "rare", "type": "Tricity", "image": "tricity_rare_1.png"},
            {"name": "Tricity Storm", "tier": "epic", "type": "Tricity", "image": "tricity_EPIC_1.png"},
            {"name": "Tricity Node", "tier": "platine", "type": "Tricity", "image": "tricity_PLAT_1.png"},
            {"name": "Tricity Core", "tier": "legendary", "type": "Tricity", "image": "tricity_LEGENDARY_1.png"},
            {"name": "Tricity Prime", "tier": "supreme", "type": "trcitiy_SUPREME_1.png"},

            # FLIRT SERIES
            {"name": "Flirt Spark", "tier": "basic", "type": "Flirt", "image": "flirt_BASIC_1.png"},
            {"name": "Flirt Glance", "tier": "rare", "type": "Flirt", "image": "flirt_RARE_1.png"},
            {"name": "Flirt Charm", "tier": "epic", "type": "Flirt", "image": "flirt_EPIC_1.png"},
            {"name": "Flirt Allure", "tier": "platine", "type": "Flirt", "image": "flirt_PLAT_1.png"},
            {"name": "Flirt Desire", "tier": "legendary", "type": "Flirt", "image": "flirt_LEGENDARY_1.png"},
            {"name": "Flirt Goddess", "tier": "supreme", "type": "flirt_SUPREME_1.png"},

            # PINK SERIES
            {"name": "Pink Mist", "tier": "basic", "type": "Pink", "image": "pink_BASIC_1.png"},
            {"name": "Pink Bloom", "tier": "rare", "type": "Pink", "image": "pink_RARE_1.png"},
            {"name": "Pink Jewel", "tier": "epic", "type": "Pink", "image": "pink_EPIC_1.png"},
            {"name": "Pink Crystal", "tier": "platine", "type": "Pink", "image": "pink_PLAT_1.png"},
            {"name": "Pink Essence", "tier": "legendary", "type": "Pink", "image": "pink_LEGENDARY_1.png"},
            {"name": "Pink Empress", "tier": "supreme", "type": "pink_SUPREME_1.png"},

            # GROUND SERIES
            {"name": "Ground Pebble", "tier": "basic", "type": "Ground", "image": "ground_BASIC_1.png"},
            {"name": "Ground Crag", "tier": "rare", "type": "Ground", "image": "ground_RARE_1.png"},
            {"name": "Ground Golem", "tier": "epic", "type": "Ground", "image": "ground_EPIC_1.png"},
            {"name": "Ground Pillar", "tier": "platine", "type": "Ground", "image": "ground_PLAT_1.png"},
            {"name": "Ground Mountain", "tier": "legendary", "type": "Ground", "image": "ground_LEGENDARY_1.png"},
            {"name": "Ground Earth-Heart", "tier": "supreme", "type": "ground_SUPREME_1.png"},

            # MYSTERY SERIES
            {"name": "Mystery Fog", "tier": "basic", "type": "Mystery", "image": "mystery_BASIC_1.png"},
            {"name": "Mystery Shadow", "tier": "rare", "type": "Mystery", "image": "mystery_RARE_1.png"},
            {"name": "Mystery Enigma", "tier": "epic", "type": "Mystery", "image": "mystery_EPIC_1.png"},
            {"name": "Mystery Void", "tier": "platine", "type": "Mystery", "image": "mystery_PLAT_1.png"}
        ]

    def _init_db(self):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS user_cards (user_id INTEGER, card_name TEXT, tier TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
            conn.execute("CREATE TABLE IF NOT EXISTS card_config (key TEXT PRIMARY KEY, value TEXT)")
            conn.commit()

    def _load_config(self):
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                row = conn.execute("SELECT value FROM card_config WHERE key = 'spawn_channel'").fetchone()
                if row:
                    self.spawn_channel_id = int(row['value'])
        except:
            pass

    @commands.command(name="setcards")
    @commands.has_permissions(administrator=True)
    async def setcards(self, ctx, channel: discord.TextChannel):
        """Admin command to bind the card spawn frequency to a channel."""
        self.spawn_channel_id = channel.id
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO card_config (key, value) VALUES ('spawn_channel', ?)", (str(channel.id),))
            conn.commit()
        
        embed = main_mod.fiery_embed("🛰️ COORDINATES SYNCHRONIZED", 
            f"The Master has locked the card emergence point to {channel.mention}.\n\n"
            f"**Status:** Emergence protocols are now active in this sector.", color=0x00FF00)
        await ctx.send(embed=embed)

    def get_random_tier(self):
        roll = random.random() * 100
        if roll < 0.5: return "supreme"
        if roll < 3.0: return "legendary"
        if roll < 10.0: return "platine"
        if roll < 25.0: return "epic"
        if roll < 50.0: return "rare"
        return "basic"

    async def spawn_card(self):
        tier = self.get_random_tier()
        tier_pool = [c for c in self.card_pool if c['tier'] == tier]
        
        if not tier_pool: # Fallback
            tier_pool = [c for c in self.card_pool if c['tier'] == "basic"]

        self.current_card = random.choice(tier_pool)
        channel = self.bot.get_channel(self.spawn_channel_id)
        
        if channel:
            main_mod = sys.modules['__main__']
            embed = main_mod.fiery_embed(
                "🌋 A WILD CARD HAS EMERGED!",
                f"**Card:** {self.current_card['name']}\n"
                f"**Tier:** {self.current_card['tier'].upper()}\n"
                f"**Type:** {self.current_card['type']}\n\n"
                f"Type `!catch {self.current_card['name']}` to collect it!"
            )
            
            image_filename = self.current_card['image']
            image_path = f"card.base/{image_filename}"
            
            if os.path.exists(image_path):
                file = discord.File(image_path, filename=image_filename)
                embed.set_image(url=f"attachment://{image_filename}")
                await channel.send(file=file, embed=embed)
            else:
                await channel.send(embed=embed)

    @tasks.loop(minutes=5)
    async def card_spawn_loop(self):
        if self.activity_pool >= self.required_activity:
            await self.spawn_card()
            self.activity_pool = 0

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.author.bot and message.guild:
            self.activity_pool += 1

    @commands.command()
    async def catch(self, ctx, *, card_name: str):
        if not self.current_card or card_name.lower() != self.current_card['name'].lower():
            return await ctx.reply("❌ That card is not here or the name is incorrect!")

        main_mod = sys.modules['__main__']
        user_id = ctx.author.id
        card = self.current_card
        self.current_card = None # Prevent double catching

        with main_mod.get_db_connection() as conn:
            # 1. Archive the new asset
            conn.execute("INSERT INTO user_cards (user_id, card_name, tier) VALUES (?, ?, ?)", 
                         (user_id, card['name'], card['tier']))
            conn.commit()

            # 2. Extract Statistics for the visual Dossier
            total_count = conn.execute("SELECT COUNT(*) FROM user_cards WHERE user_id = ?", (user_id,)).fetchone()[0]
            
            tiers = ["supreme", "legendary", "platine", "epic", "rare", "basic"]
            tier_stats = []
            for t in tiers:
                count = conn.execute("SELECT COUNT(*) FROM user_cards WHERE user_id = ? AND tier = ?", (user_id, t)).fetchone()[0]
                if count > 0:
                    tier_stats.append(f"• **{t.upper()}:** {count}")
            
            rows = conn.execute("SELECT card_name FROM user_cards WHERE user_id = ?", (user_id,)).fetchall()
            user_card_names = [r[0] for r in rows]
            
            collections = {}
            for p_card in self.card_pool:
                if p_card['name'] in user_card_names:
                    c_type = p_card['type']
                    collections[c_type] = collections.get(c_type, 0) + user_card_names.count(p_card['name'])

        # 3. Build the High-Fidelity Capture Dossier
        tier_display = "\n".join(tier_stats) if tier_stats else "New collection started."
        coll_display = "\n".join([f"🔸 **{k}:** {v}" for k, v in list(collections.items())[:5]])

        embed = main_mod.fiery_embed(
            "🔥 ASSET SECURED!",
            f"{ctx.author.mention} has successfully synchronized with **{card['name']}**!",
            color=0xFFD700 # Gold color for success
        )
        
        embed.add_field(name="🧬 Spec Details", value=f"**Type:** {card['type']}\n**Tier:** {card['tier'].upper()}", inline=True)
        embed.add_field(name="📊 Vault Summary", value=f"**Total Assets:** {total_count}\n**Rank:** Asset Hunter", inline=True)
        embed.add_field(name="💎 Rarity Distribution", value=tier_display, inline=False)
        embed.add_field(name="🏛️ Collection Mastery", value=coll_display or "Gathering data...", inline=False)
        
        image_path = f"card.base/{card['image']}"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="captured_asset.png")
            embed.set_image(url="attachment://captured_asset.png")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

    @commands.command(name="pokedex")
    async def pokedex(self, ctx, member: discord.Member = None):
        """DYNAMIC & INTERACTIVE POKEDEX: Categorized browsing with Select Menus."""
        target = member or ctx.author
        main_mod = sys.modules['__main__']
        
        with main_mod.get_db_connection() as conn:
            rows = conn.execute("SELECT card_name, tier, COUNT(*) as count FROM user_cards WHERE user_id = ? GROUP BY card_name", (target.id,)).fetchall()

        if not rows:
            return await ctx.send(f"📕 {target.display_name}'s Pokedex is empty. Go catch something, toy.")

        # Organize user cards by their collection type (Matching with card_pool)
        categorized_data = {}
        total_found = 0
        
        for row in rows:
            card_name = row[0]
            # Find the type from card_pool
            pool_data = next((c for c in self.card_pool if c['name'] == card_name), None)
            if pool_data:
                c_type = pool_data['type']
                if c_type not in categorized_data:
                    categorized_data[c_type] = []
                categorized_data[c_type].append({'name': card_name, 'tier': row[1], 'count': row[2]})
                total_found += row[2]

        # Create the Interactive View
        view = PokedexView(target, categorized_data, self.card_pool, main_mod.fiery_embed)
        
        # Setup Initial Select Options
        for category in categorized_data.keys():
            view.select_category.add_option(
                label=category, 
                description=f"View your {len(categorized_data[category])} {category} assets",
                emoji="🔞" if category == "Flirt" else "🔥",
                value=category
            )

        # Build Intro Embed
        intro_desc = (
            f"### 🛡️ NEURAL ARCHIVE OF {target.display_name}\n"
            f"**Total Mastered Assets:** `{total_found}`\n"
            f"**Unique Collections:** `{len(categorized_data)}` categories detected.\n\n"
            "*Use the terminal below to filter through your categorized captures.*"
        )
        
        embed = main_mod.fiery_embed(f"📕 {target.display_name}'S ARCHIVE", intro_desc)
        
        # Visual Decoration
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="pokedex_thumb.jpg")
            embed.set_thumbnail(url="attachment://pokedex_thumb.jpg")
            await ctx.send(file=file, embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(CardSystem(bot))
