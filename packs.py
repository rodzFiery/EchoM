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
        """Generates a visual 'Neural Dossier' with enhanced glow and rarity effects."""
        def draw_task():
            # Enhanced Rarity Palette
            colors = {
                "Common": {"main": (150, 150, 150), "glow": (50, 50, 50)},
                "Rare": {"main": (52, 152, 219), "glow": (20, 70, 120)},
                "Epic": {"main": (155, 89, 182), "glow": (80, 40, 100)},
                "Legendary": {"main": (241, 196, 15), "glow": (120, 100, 10)}
            }
            theme = colors.get(rarity, {"main": (255, 255, 255), "glow": (100, 100, 100)})
            
            # Create Background with slight gradient effect
            canvas = Image.new("RGBA", (800, 450), (10, 2, 15, 255))
            draw = ImageDraw.Draw(canvas)
            
            # Draw Outer Glow/Border
            for i in range(15, 0, -1):
                alpha = int(150 * (1 - i/15))
                draw.rectangle([i, i, 800-i, 450-i], outline=(*theme['main'], alpha), width=2)

            # Header Styling
            draw.text((40, 30), "▣ NEURAL ASSET RECOVERY", fill=theme['main'])
            draw.line([40, 60, 300, 60], fill=theme['main'], width=2)
            
            # Rarity Badge
            draw.rectangle([40, 80, 200, 110], fill=theme['main'])
            draw.text((50, 85), rarity.upper(), fill=(0, 0, 0))

            # Stats Visualization (Bar Style)
            stats = [("ATK", item['atk'], (255, 80, 80)), ("DEF", item['def'], (80, 140, 255)), ("SPD", item['spd'], (80, 255, 140))]
            for idx, (label, val, col) in enumerate(stats):
                y_pos = 150 + (idx * 60)
                draw.text((40, y_pos), f"{label}: {val}", fill=col)
                # Draw Bar Background
                draw.rectangle([140, y_pos + 5, 400, y_pos + 15], fill=(30, 30, 40))
                # Draw Bar Fill
                bar_width = int((val / 100) * 260)
                draw.rectangle([140, y_pos + 5, 140 + bar_width, y_pos + 15], fill=col)

            # Item Display Box (Right Side)
            draw.rectangle([450, 80, 750, 350], outline=theme['main'], width=3)
            draw.text((465, 365), f"ASSET: {item['name']}", fill=theme['main'])
            draw.text((40, 400), f"DESCRIPTION: \"{item['desc']}\"", fill=(180, 180, 180))
            
            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            buf.seek(0)
            return buf

        return await asyncio.to_thread(draw_task)

    async def create_rumble_card(self, players):
        """Generates a high-tension 'VERSUS' screen for the Rumble lobby."""
        def draw_task():
            canvas = Image.new("RGBA", (1000, 500), (20, 0, 5, 255))
            draw = ImageDraw.Draw(canvas)
            
            # Central 'VS' text with glitch effect
            draw.text((450, 200), "V S", fill=(255, 0, 40))
            
            # List first 3 players on each side
            for idx, player in enumerate(players[:6]):
                x = 50 if idx < 3 else 700
                y = 100 + (idx % 3 * 100)
                draw.text((x, y), f"► {player['user'].display_name[:15]}", fill=(255, 255, 255))
                draw.text((x + 20, y + 30), f"EQUIP: {player['gear_name']}", fill=(180, 0, 0))

            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            buf.seek(0)
            return buf
        return await asyncio.to_thread(draw_task)

    @commands.command(name="buybox")
    async def buy_box(self, ctx, box_type: str = "basic"):
        """Spend Flames to open a Gear Box (basic, premium, elite, tech, guardian, warlord)."""
        main_mod = sys.modules['__main__']
        box_type = box_type.lower()
        
        prices = {
            "basic": 5000, 
            "premium": 15000, 
            "elite": 50000,
            "tech": 25000,
            "guardian": 25000,
            "warlord": 100000
        }
        if box_type not in prices:
            return await ctx.send("❌ Valid boxes: `basic`, `premium`, `elite`, `tech`, `guardian`, `warlord`.")

        price = prices[box_type]
        user_data = await asyncio.to_thread(main_mod.get_user, ctx.author.id)
        
        if user_data['balance'] < price:
            return await ctx.send(f"❌ You lack the Flames. Opening a {box_type} box requires `{price:,}`.")

        # Determine Rarity and Filtering
        rarity_weights = {"Common": 0.80, "Rare": 0.18, "Epic": 0.02, "Legendary": 0.00}
        
        if box_type == "premium":
            rarity_weights = {"Common": 0.40, "Rare": 0.45, "Epic": 0.12, "Legendary": 0.03}
        elif box_type == "elite":
            rarity_weights = {"Common": 0.10, "Rare": 0.30, "Epic": 0.45, "Legendary": 0.15}
        elif box_type == "tech" or box_type == "guardian":
            rarity_weights = {"Common": 0.30, "Rare": 0.50, "Epic": 0.20, "Legendary": 0.00}
        elif box_type == "warlord":
            rarity_weights = {"Common": 0.00, "Rare": 0.20, "Epic": 0.55, "Legendary": 0.25}

        rarity = random.choices(list(rarity_weights.keys()), weights=list(rarity_weights.values()))[0]
        
        # Filter pool based on specialty boxes
        pool = self.item_pool[rarity]
        if box_type == "tech":
            pool = [i for i in pool if i['spd'] >= i['atk']] or pool
        elif box_type == "guardian":
            pool = [i for i in pool if i['def'] >= i['atk']] or pool
            
        item = random.choice(pool)
        
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
        
        # NEW: Visual Intro Card
        card_buf = await self.create_rumble_card(combatants)
        embed = main_mod.fiery_embed("🔞 RUMBLE INITIATED", "The gates lock. The voyeurs lean in. **BLOOD WILL FLOW.**")
        embed.set_image(url="attachment://vs.png")
        msg = await ctx.send(file=discord.File(card_buf, filename="vs.png"), embed=embed)
        await asyncio.sleep(4)

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

    @commands.command(name="dailygear", aliases=["scan"])
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily_gear(self, ctx):
        """Perform a free daily Neural Scan for gear (Common, Rare, or Epic)."""
        main_mod = sys.modules['__main__']
        
        # Rarity weights for free scan: No legendary, but chance for Epic.
        weights = {"Common": 0.70, "Rare": 0.25, "Epic": 0.05}
        rarity = random.choices(list(weights.keys()), weights=list(weights.values()))[0]
        item = random.choice(self.item_pool[rarity])
        
        def add_item():
            with self._get_db() as conn:
                conn.execute("INSERT INTO dungeon_inventory (user_id, item_name, rarity, atk, def, spd) VALUES (?, ?, ?, ?, ?, ?)",
                             (ctx.author.id, item['name'], rarity, item['atk'], item['def'], item['spd']))
                conn.commit()
        
        await asyncio.to_thread(add_item)
        img_buf = await self.create_pack_image(ctx.author.display_avatar.url, item, rarity)
        
        color = 0xCCCCCC if rarity == "Common" else 0x3498DB if rarity == "Rare" else 0x9B59B6
        embed = main_mod.fiery_embed("📡 DAILY NEURAL SCAN COMPLETE", f"Asset {ctx.author.mention}, free gear has been materialized.")
        embed.color = color
        embed.set_image(url="attachment://pack.png")
        
        await ctx.send(file=discord.File(img_buf, filename="pack.png"), embed=embed)

    @daily_gear.error
    async def daily_gear_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            hours = int(error.retry_after // 3600)
            minutes = int((error.retry_after % 3600) // 60)
            await ctx.send(f"🥀 **SIGNAL INTERFERENCE:** Neural scanner is recharging. Try again in `{hours}h {minutes}m`.")

    @commands.command(name="scrap")
    async def scrap_item(self, ctx, item_id: int):
        """Deconstruct unwanted gear for Flames."""
        main_mod = sys.modules['__main__']
        
        def do_scrap():
            with self._get_db() as conn:
                item = conn.execute("SELECT item_name, rarity FROM dungeon_inventory WHERE id = ? AND user_id = ?", (item_id, ctx.author.id)).fetchone()
                if not item: return None
                conn.execute("DELETE FROM dungeon_inventory WHERE id = ?", (item_id,))
                conn.commit()
                return item['item_name'], item['rarity']

        result = await asyncio.to_thread(do_scrap)
        if not result:
            return await ctx.send("❌ Item not found in your inventory.")

        name, rarity = result
        scraps = {"Common": 1000, "Rare": 3000, "Epic": 10000, "Legendary": 25000}
        payout = scraps.get(rarity, 500)

        await main_mod.update_user_stats_async(ctx.author.id, amount=payout, source=f"Scrapped {name} ({rarity})")
        
        embed = main_mod.fiery_embed("♻️ NEURAL RECYCLING COMPLETE", 
            f"Asset {ctx.author.mention}, **{name}** has been deconstructed.\n\n"
            f"**Neural Scraps Recovered:** `{payout:,} Flames`.")
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
