import discord
from discord.ext import commands
import random
import sys
import json
import io
import asyncio
import os
from PIL import Image, ImageDraw, ImageOps, ImageFilter, ImageFont
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
        # ADDED: Rumble Lobby State
        self.pit_lobby = []
        self.pit_open = False
        self.entry_fee = 5000

    def _get_db(self):
        return sys.modules['__main__'].get_db_connection()

    async def create_pack_image(self, user_avatar_url, item, rarity):
        """Generates a visual 'Neural Dossier' for the item pull."""
        def draw_task():
            # Rarity Colors
            colors = {
                "Common": (204, 204, 204),
                "Rare": (52, 152, 219),
                "Epic": (155, 89, 182),
                "Legendary": (241, 196, 15)
            }
            theme_color = colors.get(rarity, (255, 255, 255))
            
            # Create Canvas
            canvas = Image.new("RGBA", (600, 400), (15, 5, 20, 255))
            draw = ImageDraw.Draw(canvas)
            
            # Border
            draw.rectangle([0, 0, 600, 400], outline=theme_color, width=10)
            
            # Header
            draw.text((20, 20), "NEURAL ASSET ACQUIRED", fill=theme_color)
            draw.text((20, 50), f"CLASSIFICATION: {rarity.upper()}", fill=(200, 200, 200))
            
            # Item Details
            draw.text((250, 120), f"NAME: {item['name']}", fill=theme_color)
            draw.text((250, 160), f"ATK: {item['atk']}", fill=(255, 100, 100))
            draw.text((250, 190), f"DEF: {item['def']}", fill=(100, 150, 255))
            draw.text((250, 220), f"SPD: {item['spd']}", fill=(100, 255, 100))
            
            # Desc
            draw.text((20, 320), f"\"{item['desc']}\"", fill=(150, 150, 150))
            
            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            buf.seek(0)
            return buf

        return await asyncio.to_thread(draw_task)

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
                cursor = conn.execute("INSERT INTO dungeon_inventory (user_id, item_name, rarity, atk, def, spd) VALUES (?, ?, ?, ?, ?, ?)",
                             (ctx.author.id, item['name'], rarity, item['atk'], item['def'], item['spd']))
                conn.commit()
                return cursor.lastrowid
        
        new_id = await asyncio.to_thread(add_item)

        # GENERATE IMAGE
        img_buf = await self.create_pack_image(ctx.author.display_avatar.url, item, rarity)
        
        # Visual Feedback
        color = 0xCCCCCC if rarity == "Common" else 0x3498DB if rarity == "Rare" else 0x9B59B6 if rarity == "Epic" else 0xF1C40F
        embed = main_mod.fiery_embed(f"📦 {box_type.upper()} BOX DEPLOYED", f"Asset {ctx.author.mention}, your gear has arrived.")
        embed.color = color
        embed.set_image(url="attachment://pack.png")
        
        await ctx.send(file=discord.File(img_buf, filename="pack.png"), embed=embed)

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

    # --- RUMBLE ENGINE START ---

    @commands.command(name="openpit")
    @commands.has_permissions(administrator=True)
    async def open_pit(self, ctx):
        """Opens the Red Room lobby for assets to join."""
        main_mod = sys.modules['__main__']
        if self.pit_open: return await ctx.send("❌ The Pit is already open.")
        
        self.pit_open = True
        self.pit_lobby = []
        
        embed = main_mod.fiery_embed("⛓️ THE PIT IS OPEN", 
            f"The Red Room Rumble lobby is active.\n\n**Entry Fee:** `{self.entry_fee:,} Flames`\n**Protocol:** Type `!joinpit` to enter.")
        await ctx.send(embed=embed)

    @commands.command(name="joinpit")
    async def join_pit(self, ctx):
        """Enter the current Rumble lobby."""
        main_mod = sys.modules['__main__']
        if not self.pit_open: return await ctx.send("🥀 The Pit is currently cold.")
        if ctx.author.id in [a['user'].id for a in self.pit_lobby]:
            return await ctx.send("❌ You are already registered for this sequence.")
            
        user_data = await asyncio.to_thread(main_mod.get_user, ctx.author.id)
        if user_data['balance'] < self.entry_fee:
            return await ctx.send(f"❌ Entry requires `{self.entry_fee:,}` Flames.")

        # Fetch Equipped Gear
        def get_gear():
            with self._get_db() as conn:
                return conn.execute("SELECT item_name, atk, def, spd FROM dungeon_inventory WHERE user_id = ? AND is_equipped = 1", (ctx.author.id,)).fetchone()
        
        gear = await asyncio.to_thread(get_gear)
        
        await main_mod.update_user_stats_async(ctx.author.id, amount=-self.entry_fee, source="Rumble Pit Entry")
        
        self.pit_lobby.append({
            "user": ctx.author,
            "hp": 100 + (gear['def'] if gear else 0),
            "atk": 10 + (gear['atk'] if gear else 0),
            "spd": 5 + (gear['spd'] if gear else 0),
            "gear_name": gear['item_name'] if gear else "Fists",
            "kills": 0
        })
        
        await ctx.send(f"⛓️ **ASSET REGISTERED:** {ctx.author.mention} entered with **{gear['item_name'] if gear else 'No Gear'}**.")

    @commands.command(name="startrumble")
    @commands.has_permissions(administrator=True)
    async def start_rumble(self, ctx):
        """Initiates the Pit simulation and determines the winner."""
        main_mod = sys.modules['__main__']
        if not self.pit_open: return await ctx.send("❌ Open the Pit first.")
        if len(self.pit_lobby) < 2: return await ctx.send("❌ Need at least 2 assets for a Rumble.")
        
        self.pit_open = False
        combatants = self.pit_lobby
        total_pot = len(combatants) * self.entry_fee
        bonus = 10000
        prize = total_pot + bonus
        
        embed = main_mod.fiery_embed("🔞 RUMBLE INITIATED", "The gates lock. The voyeurs lean in. **BLOOD WILL FLOW.**")
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(2)

        history = []
        while len(combatants) > 1:
            # Sort by speed + random factor
            combatants.sort(key=lambda x: x['spd'] + random.randint(1, 10), reverse=True)
            
            attacker = combatants[0]
            targets = [c for c in combatants if c['user'].id != attacker['user'].id]
            target = random.choice(targets)
            
            damage = random.randint(attacker['atk'] // 2, attacker['atk'])
            target['hp'] -= damage
            
            history_line = f"⛓️ **{attacker['user'].display_name}** uses **{attacker['gear_name']}** on **{target['user'].display_name}** for `{damage}` DMG!"
            
            if target['hp'] <= 0:
                history_line += f"\n💀 **{target['user'].display_name} has been BROKEN!**"
                attacker['kills'] += 1
                combatants.remove(target)
            
            history.append(history_line)
            
            # Keep history display manageable
            if len(history) > 5: history.pop(0)
            
            embed.description = "\n".join(history)
            embed.set_footer(text=f"Remaining Assets: {len(combatants)}")
            await msg.edit(embed=embed)
            await asyncio.sleep(1.5)

        winner = combatants[0]
        
        # Update database stats
        def update_winner():
            with self._get_db() as conn:
                conn.execute("INSERT OR IGNORE INTO rumble_stats (user_id) VALUES (?)", (winner['user'].id,))
                conn.execute("UPDATE rumble_stats SET wins = wins + 1, pit_master_count = pit_master_count + 1 WHERE user_id = ?", (winner['user'].id,))
                for asset in self.pit_lobby:
                    if asset['user'].id != winner['user'].id:
                        conn.execute("INSERT OR IGNORE INTO rumble_stats (user_id) VALUES (?)", (asset['user'].id,))
                        conn.execute("UPDATE rumble_stats SET losses = losses + 1 WHERE user_id = ?", (asset['user'].id,))
                    conn.execute("UPDATE rumble_stats SET kills = kills + ? WHERE user_id = ?", (asset['kills'], asset['user'].id))
                conn.commit()

        await asyncio.to_thread(update_winner)
        await main_mod.update_user_stats_async(winner['user'].id, amount=prize, source="Rumble Pit Winner")

        win_embed = main_mod.fiery_embed("🏆 PIT MASTER DECLARED", 
            f"### **{winner['user'].mention}**\n\n"
            f"The asset has emerged victorious with `{winner['kills']}` eliminations.\n\n"
            f"**💰 REWARD:** `{prize:,} Flames` added to balance.\n"
            f"**📊 STATUS:** The Red Room is satisfied.")
        win_embed.color = 0xF1C40F
        await ctx.send(embed=win_embed)

    @commands.command(name="pitrecords", aliases=["rumblelb", "pitlb"])
    async def pit_records(self, ctx):
        """Displays the top fighters in the dungeon archives."""
        main_mod = sys.modules['__main__']
        
        def fetch_records():
            with self._get_db() as conn:
                return conn.execute("SELECT user_id, wins, kills, pit_master_count FROM rumble_stats ORDER BY wins DESC, kills DESC LIMIT 10").fetchall()
        
        data = await asyncio.to_thread(fetch_records)
        if not data: return await ctx.send("🥀 The archives are empty. No blood has been spilled.")

        desc = "### 🏛️ DUNGEON PIT ARCHIVES\n"
        for i, row in enumerate(data, 1):
            user = self.bot.get_user(row['user_id'])
            name = user.display_name if user else f"Unknown Asset ({row['user_id']})"
            desc += f"`#{i}` **{name}** — `Wins: {row['wins']}` | `Kills: {row['kills']}`\n"

        embed = main_mod.fiery_embed("🕵️ TOP RUMBLE ASSETS", desc)
        embed.color = 0xFF4500
        await ctx.send(embed=embed)

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
