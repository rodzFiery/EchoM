import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import sys
import os

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
            # ADDED: Table to store card system settings independently
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
            conn.execute("INSERT INTO user_cards (user_id, card_name, tier) VALUES (?, ?, ?)", 
                         (user_id, card['name'], card['tier']))
            conn.commit()

        await ctx.send(embed=main_mod.fiery_embed(
            "🔥 CARD COLLECTED!",
            f"{ctx.author.mention} has captured **{card['name']}** ({card['tier'].upper()})!\n"
            f"This asset has been archived in your Pokedex."
        ))

    @commands.command(name="pokedex")
    async def pokedex(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        main_mod = sys.modules['__main__']
        
        with main_mod.get_db_connection() as conn:
            rows = conn.execute("SELECT card_name, tier, COUNT(*) as count FROM user_cards WHERE user_id = ? GROUP BY card_name", (target.id,)).fetchall()

        if not rows:
            return await ctx.send(f"📕 {target.display_name}'s Pokedex is empty.")

        desc = ""
        for r in rows:
            desc += f"• **{r['card_name']}** ({r['tier']}) x{r['count']}\n"

        await ctx.send(embed=main_mod.fiery_embed(f"📕 {target.display_name}'S ARCHIVE", desc))

async def setup(bot):
    await bot.add_cog(CardSystem(bot))
