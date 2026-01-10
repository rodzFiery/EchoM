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

        # INITIAL 20 CARD DATA (Echo Volcano Theme)
        # Types: Magma, Ash, Obsidian, Inferno
        self.card_pool = [
            {"name": "Magma Core", "tier": "basic", "type": "Magma", "image": "Magma_Core.jpg"},
            {"name": "Ash Cloud", "tier": "basic", "type": "Ash", "image": "Ash_Cloud.jpg"},
            {"name": "Obsidion Shard", "tier": "basic", "type": "Obsidian", "image": "Obsidion_Shard.jpg"},
            {"name": "Small Spark", "tier": "basic", "type": "Inferno", "image": "Small_Spark.jpg"},
            {"name": "Lava Snake", "tier": "rare", "type": "Magma", "image": "Lava_Snake.jpg"},
            {"name": "Cinder Spirit", "tier": "rare", "type": "Ash", "image": "Cinder_Spirit.jpg"},
            {"name": "Stone Golem", "tier": "rare", "type": "Obsidian", "image": "Stone_Golem.jpg"},
            {"name": "Fire Wisp", "tier": "rare", "type": "Inferno", "image": "Fire_Wisp.jpg"},
            {"name": "Volcanic Dragon", "tier": "epic", "type": "Magma", "image": "Volcanic_Dragon.jpg"},
            {"name": "Phoenix Feather", "tier": "epic", "type": "Inferno", "image": "Phoenix_Feather.jpg"},
            {"name": "Obsidian Armor", "tier": "epic", "type": "Obsidian", "image": "Obsidian_Armor.jpg"},
            {"name": "Platinum Embers", "tier": "platine", "type": "Inferno", "image": "Platinum_Embers.jpg"},
            {"name": "Crystal Magma", "tier": "platine", "type": "Magma", "image": "Crystal_Magma.jpg"},
            {"name": "Eternal Flame", "tier": "legendary", "type": "Inferno", "image": "Eternal_Flame.jpg"},
            {"name": "Echo Volcano Heart", "tier": "legendary", "type": "Ash", "image": "Echo_Volcano_Heart.jpg"},
            {"name": "Supreme Inferno King", "tier": "supreme", "type": "Inferno", "image": "Supreme_Inferno_King.jpg"},
            {"name": "Magma Leviathan", "tier": "epic", "type": "Magma", "image": "Magma_Leviathan.jpg"},
            {"name": "Shadow Ash", "tier": "rare", "type": "Ash", "image": "Shadow_Ash.jpg"},
            {"name": "Burning Rune", "tier": "basic", "type": "Inferno", "image": "Burning_Rune.jpg"},
            {"name": "Void Obsidian", "tier": "platine", "type": "Obsidian", "image": "Void_Obsidian.jpg"}
        ]

    def _init_db(self):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS user_cards (user_id INTEGER, card_name TEXT, tier TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
            conn.commit()

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
            
            # Updated image path logic using the 'image' key from pool
            image_filename = self.current_card['image']
            image_path = f"cards/{image_filename}"
            
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
