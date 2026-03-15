import discord
from discord.ext import commands
import random
import sys
import json
import io
import asyncio
from datetime import datetime

class DungeonPacks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # DATA: Item types, rarity, and Rumble stats
        self.item_pool = {
            "Common": [
                {"name": "Nylon Rope", "atk": 2, "def": 5, "spd": 8, "desc": "Light and flexible. Good for agility."},
                {"name": "Leather Blindfold", "atk": 0, "def": 10, "spd": -2, "desc": "Heightens other senses. Solid defense."},
                {"name": "Basic Spreader", "atk": 5, "def": 2, "spd": -5, "desc": "Keeps targets in place. Clunky."}
            ],
            "Rare": [
                {"name": "Steel Handcuffs", "atk": 12, "def": 15, "spd": 2, "desc": "Cold, hard restraints. High impact."},
                {"name": "Woven Bullwhip", "atk": 25, "def": 0, "spd": 10, "desc": "A sharp crack that commands respect."},
                {"name": "Latex Hood", "atk": 5, "def": 25, "spd": 5, "desc": "Total sensory focus. Elite protection."}
            ],
            "Epic": [
                {"name": "Weighted Anal Plug", "atk": 10, "def": 20, "spd": 30, "desc": "Intense focus. Massive speed/stamina boost."},
                {"name": "Electric Wand", "atk": 45, "def": 5, "spd": 15, "desc": "Shocking power. Hard to dodge."},
                {"name": "The Master's Paddle", "atk": 60, "def": 10, "spd": -10, "desc": "A heavy, wooden lesson in authority."}
            ],
            "Legendary": [
                {"name": "The Gilded Cage", "atk": 30, "def": 80, "spd": 10, "desc": "Complete containment. Near-impenetrable."},
                {"name": "Abyssal Thorns", "atk": 90, "def": -10, "spd": 20, "desc": "Pure agony. Massive damage, low defense."},
                {"name": "Neural Override Collar", "atk": 50, "def": 50, "spd": 50, "desc": "Total control. Perfectly balanced stats."}
            ]
        }

    def _get_db(self):
        return sys.modules['__main__'].get_db_connection()

    @commands.command(name="buybox")
    async def buy_box(self, ctx, box_type: str = "basic"):
        """Spend Flames to open a Gear Box (basic, premium, elite)."""
        main_mod = sys.modules['__main__']
        box_type = box_type.lower()
        
        prices = {"basic": 5000, "premium": 15000, "elite": 50000}
        if box_type not in prices:
            return await ctx.send("❌ Valid boxes: `basic` (5k), `premium` (15k), `elite` (50k).")

        price = prices[box_type]
        user_data = await asyncio.to_thread(main_mod.get_user, ctx.author.id)
        
        if user_data['balance'] < price:
            return await ctx.send(f"❌ You lack the Flames. Opening a {box_type} box requires `{price:,}`.")

        # Determine Rarity
        rand = random.random()
        if box_type == "basic":
            weights = {"Common": 0.80, "Rare": 0.18, "Epic": 0.02, "Legendary": 0.00}
        elif box_type == "premium":
            weights = {"Common": 0.40, "Rare": 0.45, "Epic": 0.12, "Legendary": 0.03}
        else: # Elite
            weights = {"Common": 0.10, "Rare": 0.30, "Epic": 0.45, "Legendary": 0.15}

        rarity = random.choices(list(weights.keys()), weights=list(weights.values()))[0]
        item = random.choice(self.item_pool[rarity])
        
        # Deduct money and add to inventory
        await main_mod.update_user_stats_async(ctx.author.id, amount=-price, source=f"Purchased {box_type} Gear Box")
        
        def add_item():
            with self._get_db() as conn:
                conn.execute("INSERT INTO dungeon_inventory (user_id, item_name, rarity, atk, def, spd) VALUES (?, ?, ?, ?, ?, ?)",
                             (ctx.author.id, item['name'], rarity, item['atk'], item['def'], item['spd']))
                conn.commit()
        
        await asyncio.to_thread(add_item)

        # Visual Feedback
        color = 0xCCCCCC if rarity == "Common" else 0x3498DB if rarity == "Rare" else 0x9B59B6 if rarity == "Epic" else 0xF1C40F
        embed = main_mod.fiery_embed(f"📦 {box_type.upper()} BOX DEPLOYED", f"Asset {ctx.author.mention}, your gear has arrived.")
        embed.color = color
        embed.add_field(name=f"**{item['name']}**", value=f"**Rarity:** `{rarity}`\n**Stats:** ⚔️`{item['atk']}` 🛡️`{item['def']}` ⚡`{item['spd']}`\n\n*\"{item['desc']}\"*")
        
        await ctx.send(embed=embed)

    @commands.command(name="dungeonbag", aliases=["inventory", "gear"])
    async def dungeon_bag(self, ctx):
        """View your collected Rumble gear."""
        main_mod = sys.modules['__main__']
        
        def fetch_inv():
            with self._get_db() as conn:
                return conn.execute("SELECT id, item_name, rarity, atk, def, spd, is_equipped FROM dungeon_inventory WHERE user_id = ?", (ctx.author.id,)).fetchall()
        
        items = await asyncio.to_thread(fetch_inv)
        if not items:
            return await ctx.send("🥀 Your bag is empty. Buy a box to start your collection.")

        desc = ""
        for i in items:
            eq = "✅ " if i['is_equipped'] else ""
            desc += f"{eq}**[{i['id']}] {i['item_name']}** ({i['rarity']})\n└ ⚔️`{i['atk']}` 🛡️`{i['def']}` ⚡`{i['spd']}`\n"

        embed = main_mod.fiery_embed("🎒 DUNGEON INVENTORY", f"Gear stored by {ctx.author.mention}:\n\n{desc}")
        embed.set_footer(text="Use !equip <id> to prepare for the Pit.")
        await ctx.send(embed=embed)

    @commands.command(name="equip")
    async def equip_item(self, ctx, item_id: int):
        """Select gear to use in the next Rumble."""
        def do_equip():
            with self._get_db() as conn:
                # Check ownership
                item = conn.execute("SELECT item_name FROM dungeon_inventory WHERE id = ? AND user_id = ?", (item_id, ctx.author.id)).fetchone()
                if not item: return None
                # Unequip all, then equip target
                conn.execute("UPDATE dungeon_inventory SET is_equipped = 0 WHERE user_id = ?", (ctx.author.id,))
                conn.execute("UPDATE dungeon_inventory SET is_equipped = 1 WHERE id = ?", (item_id,))
                conn.commit()
                return item['item_name']

        name = await asyncio.to_thread(do_equip)
        if not name:
            return await ctx.send("❌ Item not found in your inventory.")
        
        await ctx.send(f"⛓️ **EQUIPPED:** `{name}` is now ready for the Pit.")

async def setup(bot):
    main_mod = sys.modules['__main__']
    with main_mod.get_db_connection() as conn:
        # Create Inventory table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dungeon_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_name TEXT,
                rarity TEXT,
                atk INTEGER,
                def INTEGER,
                spd INTEGER,
                is_equipped INTEGER DEFAULT 0
            )
        """)
        # Create Rumble Stats table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rumble_stats (
                user_id INTEGER PRIMARY KEY,
                wins INTEGER DEFAULT 0,
                kills INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                pit_master_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()
    await bot.add_cog(DungeonPacks(bot))
    print("✅ LOG: Dungeon Packs & Gear ONLINE.")
