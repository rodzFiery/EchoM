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
            # ADDED: Table to track which mastery rewards have been claimed
            conn.execute("CREATE TABLE IF NOT EXISTS card_mastery (user_id INTEGER, mastery_key TEXT, PRIMARY KEY (user_id, mastery_key))")
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
        if not tier_pool: tier_pool = [c for c in self.card_pool if c['tier'] == "basic"]
        self.current_card = random.choice(tier_pool)
        channel = self.bot.get_channel(self.spawn_channel_id)
        if channel:
            main_mod = sys.modules['__main__']
            embed = main_mod.fiery_embed("🌋 A WILD CARD HAS EMERGED!", f"**Card:** {self.current_card['name']}\n**Tier:** {self.current_card['tier'].upper()}\n**Type:** {self.current_card['type']}\n\nType `!catch {self.current_card['name']}` to collect it!")
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

    async def check_mastery(self, ctx, user_id):
        """SCANS DATABASE FOR FULL COLLECTIONS AND AWARDS PASSIVES"""
        main_mod = sys.modules['__main__']
        
        with main_mod.get_db_connection() as conn:
            user_cards = [r[0] for r in conn.execute("SELECT card_name FROM user_cards WHERE user_id = ?", (user_id,)).fetchall()]
            
            # --- 1. CATEGORY MASTERY (e.g. LAVA, GLADIATOR) ---
            categories = set(c['type'] for c in self.card_pool)
            for cat in categories:
                mastery_key = f"cat_{cat.lower()}"
                already_claimed = conn.execute("SELECT 1 FROM card_mastery WHERE user_id = ? AND mastery_key = ?", (user_id, mastery_key)).fetchone()
                
                if not already_claimed:
                    required = [c['name'] for c in self.card_pool if c['type'] == cat]
                    if all(req in user_cards for req in required):
                        # AWARD: 500k Flames + 20k XP + PASSIVE: +5% Work Yield
                        conn.execute("INSERT INTO card_mastery (user_id, mastery_key) VALUES (?, ?)", (user_id, mastery_key))
                        await main_mod.update_user_stats_async(user_id, amount=500000, xp_gain=20000, source=f"Mastery: {cat}")
                        
                        await ctx.send(embed=main_mod.fiery_embed("🏆 COLLECTION MASTERED", 
                            f"Asset {ctx.author.mention}, you have unified the **{cat}** Series.\n\n"
                            f"**Rewards:**\n💰 +500,000 Flames\n🧬 +20,000 Global XP\n"
                            f"⚡ **PASSIVE UNLOCKED:** +5% Multiplier to all extraction commands (!work, !beg, etc).", color=0xFFD700))

            # --- 2. TIER MASTERY (e.g. ALL SUPREMES) ---
            tiers = ["basic", "rare", "epic", "platine", "legendary", "supreme"]
            for tier in tiers:
                mastery_key = f"tier_{tier}"
                already_claimed = conn.execute("SELECT 1 FROM card_mastery WHERE user_id = ? AND mastery_key = ?", (user_id, mastery_key)).fetchone()
                
                if not already_claimed:
                    required = [c['name'] for c in self.card_pool if c['tier'] == tier]
                    if all(req in user_cards for req in required):
                        # AWARD: 1M Flames + 50k XP + PASSIVE: ARENA DEFENSE BOOST
                        conn.execute("INSERT INTO card_mastery (user_id, mastery_key) VALUES (?, ?)", (user_id, mastery_key))
                        await main_mod.update_user_stats_async(user_id, amount=1000000, xp_gain=50000, source=f"Tier Mastery: {tier}")
                        
                        await ctx.send(embed=main_mod.fiery_embed("👑 TIER ARCHITECT UNLOCKED", 
                            f"Asset {ctx.author.mention}, you have archived every **{tier.upper()}** asset in existence.\n\n"
                            f"**Rewards:**\n💰 +1,000,000 Flames\n🧬 +50,000 Global XP\n"
                            f"🛡️ **PASSIVE UNLOCKED:** +10% Health in Echo Hangrygames (Ignis Arena).", color=0x00FFFF))

            # --- 3. ABSOLUTE COMPLETION (THE MASTER) ---
            master_key = "absolute_master"
            already_claimed = conn.execute("SELECT 1 FROM card_mastery WHERE user_id = ? AND mastery_key = ?", (user_id, master_key)).fetchone()
            if not already_claimed:
                all_required = [c['name'] for c in self.card_pool]
                if all(req in user_cards for req in all_required):
                    conn.execute("INSERT INTO card_mastery (user_id, mastery_key) VALUES (?, ?)", (user_id, master_key))
                    await main_mod.update_user_stats_async(user_id, amount=10000000, xp_gain=250000, source="Absolute Mastery")
                    
                    await ctx.send(embed=main_mod.fiery_embed("🌌 GOD OF THE ECHO VOLCANO", 
                        f"Asset {ctx.author.mention}, the neural archive is 100% complete.\n\n"
                        f"**Rewards:**\n💰 +10,000,000 Flames\n🧬 +250,000 Global XP\n"
                        f"🔱 **PASSIVE UNLOCKED:** Permanent 1.5x Multiplier to ALL income and +20% Critical Strike in Arena.", color=0xFF0000))
            conn.commit()

    @commands.command()
    async def catch(self, ctx, *, card_name: str):
        if not self.current_card or card_name.lower() != self.current_card['name'].lower():
            return await ctx.reply("❌ That card is not here or the name is incorrect!")
        main_mod = sys.modules['__main__']
        user_id = ctx.author.id
        card = self.current_card
        self.current_card = None 
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT INTO user_cards (user_id, card_name, tier) VALUES (?, ?, ?)", (user_id, card['name'], card['tier']))
            conn.commit()
            total_count = conn.execute("SELECT COUNT(*) FROM user_cards WHERE user_id = ?", (user_id,)).fetchone()[0]
            tier_stats = [f"• **{t.upper()}:** {conn.execute('SELECT COUNT(*) FROM user_cards WHERE user_id = ? AND tier = ?', (user_id, t)).fetchone()[0]}" for t in ["supreme", "legendary", "platine", "epic", "rare", "basic"]]
            rows = conn.execute("SELECT card_name FROM user_cards WHERE user_id = ?", (user_id,)).fetchall()
            user_card_names = [r[0] for r in rows]
            collections = {}
            for p_card in self.card_pool:
                if p_card['name'] in user_card_names:
                    collections[p_card['type']] = collections.get(p_card['type'], 0) + user_card_names.count(p_card['name'])

        embed = main_mod.fiery_embed("🔥 ASSET SECURED!", f"{ctx.author.mention} caught **{card['name']}**!", color=0xFFD700)
        embed.add_field(name="🧬 Specs", value=f"**Type:** {card['type']}\n**Tier:** {card['tier'].upper()}", inline=True)
        embed.add_field(name="📊 Vault", value=f"**Total Assets:** {total_count}", inline=True)
        embed.add_field(name="💎 Rarity", value="\n".join([s for s in tier_stats if ": 0" not in s]), inline=False)
        image_path = f"card.base/{card['image']}"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="captured.png")
            embed.set_image(url="attachment://captured.png")
            await ctx.send(file=file, embed=embed)
        else: await ctx.send(embed=embed)
        
        # TRIGGER MASTERY CHECK
        await self.check_mastery(ctx, user_id)

    @commands.command(name="pokedex")
    async def pokedex(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            rows = conn.execute("SELECT card_name, tier, COUNT(*) as count FROM user_cards WHERE user_id = ? GROUP BY card_name", (target.id,)).fetchall()
        if not rows: return await ctx.send(f"📕 {target.display_name}'s Pokedex is empty.")
        categorized_data = {}
        total_found = 0
        for row in rows:
            pool_data = next((c for c in self.card_pool if c['name'] == row[0]), None)
            if pool_data:
                c_type = pool_data['type']
                if c_type not in categorized_data: categorized_data[c_type] = []
                categorized_data[c_type].append({'name': row[0], 'tier': row[1], 'count': row[2]})
                total_found += row[2]
        view = PokedexView(target, categorized_data, self.card_pool, main_mod.fiery_embed)
        for cat in categorized_data.keys():
            view.select_category.add_option(label=cat, description=f"{len(categorized_data[cat])} assets", emoji="🔥", value=cat)
        embed = main_mod.fiery_embed(f"📕 {target.display_name}'S ARCHIVE", f"### 🛡️ NEURAL ARCHIVE\n**Assets Mastered:** `{total_found}`\n**Categories:** `{len(categorized_data)}`")
        await ctx.send(embed=embed, view=view)

    @commands.command(name="collections")
    async def collections(self, ctx, member: discord.Member = None):
        """CHECKLIST TERMINAL: Consult existing assets and identify missing ones."""
        target = member or ctx.author
        main_mod = sys.modules['__main__']
        
        with main_mod.get_db_connection() as conn:
            user_cards = [r[0] for r in conn.execute("SELECT card_name FROM user_cards WHERE user_id = ?", (target.id,)).fetchall()]

        # Sort the entire pool into categories
        categories = {}
        for c in self.card_pool:
            if c['type'] not in categories:
                categories[c['type']] = []
            categories[c['type']].append(c['name'])

        embed = main_mod.fiery_embed(f"🗺️ {target.display_name}'S CHECKLIST", "Track your progress toward series mastery.")
        
        for cat_name, card_list in categories.items():
            found_in_cat = [c for c in card_list if c in user_cards]
            missing_in_cat = [c for c in card_list if c not in user_cards]
            
            percentage = int((len(found_in_cat) / len(card_list)) * 100)
            status_emoji = "✅" if percentage == 100 else "⏳"
            
            value_text = f"**Progress:** {percentage}% ({len(found_in_cat)}/{len(card_list)})\n"
            
            if missing_in_cat:
                value_text += f"❌ **Missing:** {', '.join(missing_in_cat)}"
            else:
                value_text += f"🌟 **Series Mastered!**"

            embed.add_field(name=f"{status_emoji} {cat_name} Series", value=value_text, inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CardSystem(bot))
