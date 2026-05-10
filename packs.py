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

# --- NEW COMPONENT: JOIN BUTTON VIEW ---
class RumbleJoinView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="SURRENDER YOUR BODY", style=discord.ButtonStyle.danger, emoji="🫦", custom_id="persistent_join_pit")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.process_join(interaction)

class DungeonPacks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # DATA: Item types, rarity, and Rumble stats - NSFW REFLAVOR
        self.item_pool = {
            "Common": [
                {"name": "Silk Restraints", "atk": 2, "def": 5, "spd": 8, "desc": "Soft, slippery, and dangerously agile."},
                {"name": "Lace Blindfold", "atk": 0, "def": 10, "spd": -2, "desc": "Sensory deprivation for better endurance."},
                {"name": "Worn Spreader", "atk": 5, "def": 2, "spd": -5, "desc": "Holding you open for the Pit's amusement."}
            ],
            "Rare": [
                {"name": "Titanium Cuffs", "atk": 12, "def": 15, "spd": 2, "desc": "Heavy metal for serious submission."},
                {"name": "Dragon-Tail Whip", "atk": 25, "def": 0, "spd": 10, "desc": "A sting that echoes through the room."},
                {"name": "Gimp Mask", "atk": 5, "def": 25, "spd": 5, "desc": "Breathless focus and maximum protection."}
            ],
            "Epic": [
                {"name": "Vibrating Steel Plug", "atk": 10, "def": 20, "spd": 30, "desc": "Intense internal pulses for erratic speed."},
                {"name": "High-Voltage Wand", "atk": 45, "def": 5, "spd": 15, "desc": "Electric ecstasy that breaks the mind."},
                {"name": "The Master's Cane", "atk": 60, "def": 10, "spd": -10, "desc": "A heavy lesson in absolute authority."}
            ],
            "Legendary": [
                {"name": "The Gilded Chastity", "atk": 30, "def": 80, "spd": 10, "desc": "Total containment. Locked away forever."},
                {"name": "Abyssal Dildo", "atk": 90, "def": -10, "spd": 20, "desc": "Stretching the limits. Pure devastation."},
                {"name": "Mind-Break Collar", "atk": 50, "def": 50, "spd": 50, "desc": "Total neural synchronization. Perfect balance."}
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
            
            canvas = Image.new("RGBA", (800, 450), (10, 2, 15, 255))
            draw = ImageDraw.Draw(canvas)
            
            for i in range(15, 0, -1):
                alpha = int(150 * (1 - i/15))
                draw.rectangle([i, i, 800-i, 450-i], outline=(*theme['main'], alpha), width=2)

            draw.text((40, 30), "▣ RED ROOM ASSET MATERIALIZATION", fill=theme['main'])
            draw.line([40, 60, 300, 60], fill=theme['main'], width=2)
            
            draw.rectangle([40, 80, 200, 110], fill=theme['main'])
            draw.text((50, 85), rarity.upper(), fill=(0, 0, 0))

            stats = [("LUST", item['atk'], (255, 80, 80)), ("PAIN", item['def'], (80, 140, 255)), ("HEAT", item['spd'], (80, 255, 140))]
            for idx, (label, val, col) in enumerate(stats):
                y_pos = 150 + (idx * 60)
                draw.text((40, y_pos), f"{label}: {val}", fill=col)
                draw.rectangle([140, y_pos + 5, 400, y_pos + 15], fill=(30, 30, 40))
                bar_width = int((val / 100) * 260)
                draw.rectangle([140, y_pos + 5, 140 + bar_width, y_pos + 15], fill=col)

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
            draw.text((450, 200), "V S", fill=(255, 0, 40))
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
        """Spend Flames to open a Kink Box."""
        main_mod = sys.modules['__main__']
        box_type = box_type.lower()
        prices = {"basic": 5000, "premium": 15000, "elite": 50000, "tech": 25000, "guardian": 25000, "warlord": 100000}
        if box_type not in prices: return await ctx.send("❌ Choose a valid kit, toy.")
        price = prices[box_type]
        user_data = main_mod.get_user(ctx.author.id)
        if user_data['balance'] < price: return await ctx.send("❌ Too poor for this level of pleasure.")

        rarity_weights = {"Common": 0.80, "Rare": 0.18, "Epic": 0.02, "Legendary": 0.00}
        if box_type == "premium": rarity_weights = {"Common": 0.40, "Rare": 0.45, "Epic": 0.12, "Legendary": 0.03}
        elif box_type == "elite": rarity_weights = {"Common": 0.10, "Rare": 0.30, "Epic": 0.45, "Legendary": 0.15}
        elif box_type == "tech" or box_type == "guardian": rarity_weights = {"Common": 0.30, "Rare": 0.50, "Epic": 0.20, "Legendary": 0.00}
        elif box_type == "warlord": rarity_weights = {"Common": 0.00, "Rare": 0.20, "Epic": 0.55, "Legendary": 0.25}

        rarity = random.choices(list(rarity_weights.keys()), weights=list(rarity_weights.values()))[0]
        pool = self.item_pool[rarity]
        if box_type == "tech": pool = [i for i in pool if i['spd'] >= i['atk']] or pool
        elif box_type == "guardian": pool = [i for i in pool if i['def'] >= i['atk']] or pool
        item = random.choice(pool)

        await main_mod.update_user_stats_async(ctx.author.id, amount=-price, source=f"Purchased {box_type} Toy Box")
        with self._get_db() as conn:
            conn.execute("INSERT INTO dungeon_inventory (user_id, item_name, rarity, atk, def, spd) VALUES (?, ?, ?, ?, ?, ?)",
                         (ctx.author.id, item['name'], rarity, item['atk'], item['def'], item['spd']))
            conn.commit()

        img_buf = await self.create_pack_image(ctx.author.display_avatar.url, item, rarity)
        embed = main_mod.fiery_embed(f"🔞 {box_type.upper()} TOY BOX UNLOCKED", f"Asset {ctx.author.mention}, your submission tool has arrived.")
        embed.set_image(url="attachment://pack.png")
        await ctx.send(file=discord.File(img_buf, filename="pack.png"), embed=embed)

    @commands.command(name="dungeonbag", aliases=["dbag", "gear"])
    async def dungeon_bag(self, ctx):
        """View your collected kinks."""
        main_mod = sys.modules['__main__']
        with self._get_db() as conn:
            items = conn.execute("SELECT id, item_name, rarity, atk, def, spd, is_equipped FROM dungeon_inventory WHERE user_id = ?", (ctx.author.id,)).fetchall()
        if not items: return await ctx.send("🥀 Your toy bag is empty.")
        desc = "".join([f"{'🔗 ' if i['is_equipped'] else ''}**[{i['id']}] {i['item_name']}** ({i['rarity']})\n└ ⚔️`{i['atk']}` 🛡️`{i['def']}` ⚡`{i['spd']}`\n" for i in items])
        await ctx.send(embed=main_mod.fiery_embed("🎒 TOY INVENTORY", desc))

    @commands.command(name="equip")
    async def equip_item(self, ctx, item_id: int):
        """Bind a toy to your soul for the next session."""
        with self._get_db() as conn:
            item = conn.execute("SELECT item_name FROM dungeon_inventory WHERE id = ? AND user_id = ?", (item_id, ctx.author.id)).fetchone()
            if not item: return await ctx.send("❌ I don't see that toy in your bag.")
            conn.execute("UPDATE dungeon_inventory SET is_equipped = 0 WHERE user_id = ?", (ctx.author.id,))
            conn.execute("UPDATE dungeon_inventory SET is_equipped = 1 WHERE id = ?", (item_id,))
            conn.commit()
        await ctx.send(f"⛓️ **BOUND:** `{item['item_name']}` is strapped on and ready.")

    # --- RUMBLE ENGINE START ---

    @commands.command(name="openpit")
    @commands.has_permissions(administrator=True)
    async def open_pit(self, ctx):
        """Opens the Red Room Pit for the Echo Rumble."""
        main_mod = sys.modules['__main__']
        if self.pit_open: return await ctx.send("❌ the Pit is already wet.")
        self.pit_open = True
        self.pit_lobby = []
        
        # PERSISTENT STATS RETRIEVAL
        with self._get_db() as conn:
            conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('total_echo_games', '0')")
            conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('total_echo_participants', '0')")
            g_row = conn.execute("SELECT value FROM config WHERE key = 'total_echo_games'").fetchone()
            p_row = conn.execute("SELECT value FROM config WHERE key = 'total_echo_participants'").fetchone()
            total_g = g_row[0] if g_row else "0"
            total_p = p_row[0] if p_row else "0"

        embed = main_mod.fiery_embed("🔞 ECHO RUMBLE: THE PIT IS OPEN", 
            f"The Red Room door creaks open. The Echo Rumble is calling for fresh meat.\n\n"
            f"🖤 **ENTRY FEE:** `{self.entry_fee:,} Flames`\n"
            f"🫦 **INSTRUCTIONS:** Click the button below to strip and enter.\n\n"
            f"📊 **Dungeon History:**\n"
            f"└ Sessions Completed: `{total_g}`\n"
            f"└ Assets Processed: `{total_p}`")
        
        # Visual Logo Protocol (Small top right)
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="logo.jpg")
            embed.set_thumbnail(url="attachment://logo.jpg")
            await ctx.send(file=file, embed=embed, view=RumbleJoinView(self))
        else:
            await ctx.send(embed=embed, view=RumbleJoinView(self))

    async def process_join(self, target_obj):
        is_interaction = isinstance(target_obj, discord.Interaction)
        user = target_obj.user if is_interaction else target_obj.author
        main_mod = sys.modules['__main__']
        if not self.pit_open: return await (target_obj.response.send_message("🥀 The Master isn't watching right now.", ephemeral=True) if is_interaction else target_obj.send("Pit closed."))
        if user.id in [a['user'].id for a in self.pit_lobby]: return await (target_obj.response.send_message("❌ You're already on your knees in the Pit.", ephemeral=True) if is_interaction else target_obj.send("Already in."))
        user_data = main_mod.get_user(user.id)
        if user_data['balance'] < self.entry_fee: return await (target_obj.response.send_message("❌ Not enough Flames to pay for this session.", ephemeral=True) if is_interaction else target_obj.send("Need Flames."))

        with self._get_db() as conn:
            gear = conn.execute("SELECT item_name, atk, def, spd FROM dungeon_inventory WHERE user_id = ? AND is_equipped = 1", (user.id,)).fetchone()
            # Lifetime Participant Update
            conn.execute("UPDATE config SET value = CAST(value AS INTEGER) + 1 WHERE key = 'total_echo_participants'")
            conn.commit()
        
        await main_mod.update_user_stats_async(user.id, amount=-self.entry_fee, source="Echo Rumble Entry")
        self.pit_lobby.append({"user": user, "hp": 100 + (gear['def'] if gear else 0), "atk": 10 + (gear['atk'] if gear else 0), "spd": 5 + (gear['spd'] if gear else 0), "gear_name": gear['item_name'] if gear else "Hands", "kills": 0, "revives": 0, "dead": False})
        msg = f"⛓️ **ASSET REGISTERED:** {user.mention} has surrendered to the Pit."
        if is_interaction: await target_obj.response.send_message(msg, ephemeral=True); await target_obj.channel.send(msg)
        else: await target_obj.send(msg)

    @commands.command(name="joinpit")
    async def join_pit(self, ctx): await self.process_join(ctx)

    @commands.command(name="startrumble")
    @commands.has_permissions(administrator=True)
    async def start_rumble(self, ctx):
        """Overhauled Battle Royale Engine matching the visual style requested."""
        main_mod = sys.modules['__main__']
        if not self.pit_open or len(self.pit_lobby) < 2: return await ctx.send("❌ Need more assets to start the Echo Rumble.")
        
        self.pit_open = False
        players = self.pit_lobby
        initial_count = len(players)
        prize = (initial_count * self.entry_fee) + 10000
        graveyard = []
        
        # Increment Total Games
        with self._get_db() as conn:
            conn.execute("UPDATE config SET value = CAST(value AS INTEGER) + 1 WHERE key = 'total_echo_games'")
            conn.commit()

        # Initial Embed
        start_emb = main_mod.fiery_embed("Initiated a new Echo Rumble Session", 
            f"**Assets chained:**\n{initial_count}\n**Protocol:** Erotic Classic\n**Prize:** {prize} 🪙")
        await ctx.send(embed=start_emb)
        await asyncio.sleep(2)

        round_num = 1
        while len([p for p in players if not p['dead']]) > 1:
            alive = [p for p in players if not p['dead']]
            
            # --- SPECIAL ROUND: RESURRECTION ---
            if round_num == 2 or (round_num > 5 and random.random() < 0.15):
                to_revive = random.sample(graveyard, min(len(graveyard), random.randint(1, 3))) if graveyard else []
                revive_names = ""
                for p in to_revive:
                    p['dead'] = False
                    p['revives'] += 1
                    graveyard.remove(p)
                    revive_names += f"💦 | **{p['user'].display_name}**\n"
                
                res_emb = discord.Embed(title=f"Round {round_num} - RE-AROUSED", description="The safe word wasn't used. They're coming back for more!", color=0x9B59B6)
                res_emb.add_field(name="The following assets have been re-aroused:", value=revive_names if revive_names else "None")
                res_emb.set_footer(text=f"Assets Remaining: {len([p for p in players if not p['dead']])}")
                await ctx.send(embed=res_emb)
            
            # --- NORMAL ROUND ---
            else:
                round_events = []
                num_events = random.randint(1, min(len(alive), 5))
                
                for _ in range(num_events):
                    alive = [p for p in players if not p['dead']]
                    if len(alive) <= 1: break
                    
                    event_type = random.choices(["kill", "accident", "nothing"], weights=[0.6, 0.2, 0.2])[0]
                    
                    if event_type == "kill":
                        attacker = random.choice(alive)
                        victim = random.choice([p for p in alive if p != attacker])
                        victim['dead'] = True
                        attacker['kills'] += 1
                        graveyard.append(victim)
                        
                        kill_msgs = [
                            f"🫦 | **{attacker['user'].display_name}** dominated **{victim['user'].display_name}** until they broke.",
                            f"⛓️ | **{attacker['user'].display_name}** used **{attacker['gear_name']}** to lock {victim['user'].display_name} in total submission.",
                            f"💦 | **{attacker['user'].display_name}** made **{victim['user'].display_name}** cum until they passed out. How messy!",
                            f"🎯 | **{attacker['user'].display_name}** successfully broke the mind of **{victim['user'].display_name}**."
                        ]
                        round_events.append(random.choice(kill_msgs))
                    
                    elif event_type == "accident":
                        victim = random.choice(alive)
                        victim['dead'] = True
                        graveyard.append(victim)
                        acc_msgs = [
                            f"💀 | **{victim['user'].display_name}** forgot the safe word and was extracted.",
                            f"🔞 | **{victim['user'].display_name}** got too lost in the pleasure and collapsed.",
                            f"🩸 | **{victim['user'].display_name}** couldn't handle the intensity of the room.",
                            f"🐶 | **{victim['user'].display_name}** was kept as a permanent pet by the Master."
                        ]
                        round_events.append(random.choice(acc_msgs))

                    elif event_type == "nothing":
                        p = random.choice(alive)
                        round_events.append(f"📸 | **{p['user'].display_name}** was busy performing for the voyeurs.")

                if round_events:
                    round_emb = discord.Embed(title=f"Round {round_num}", description="\n".join(round_events), color=0x8B0000)
                    round_emb.set_footer(text=f"Assets Active: {len([p for p in players if not p['dead']])}")
                    await ctx.send(embed=round_emb)

            round_num += 1
            await asyncio.sleep(3)

        winner = [p for p in players if not p['dead']][0]
        
        # --- FINAL RESULTS ---
        win_emb = discord.Embed(title="🏆 THE LEAD ECHO!", description=f"**{winner['user'].display_name}**\nReward: {prize} 🪙", color=0xF1C40F)
        win_emb.set_footer(text=f"Total Assets Processed: {initial_count}")
        await ctx.send(embed=win_emb)

        # Stats Recap
        runners_up = sorted(graveyard, key=lambda x: players.index(x), reverse=True)[:4]
        ru_text = "\n".join([f"{i+2}. {p['user'].display_name}" for i, p in enumerate(runners_up)])
        
        top_killers = sorted(players, key=lambda x: x['kills'], reverse=True)[:4]
        kill_text = "\n".join([f"{p['kills']} {p['user'].display_name}" for p in top_killers if p['kills'] > 0])
        
        revive_text = "\n".join([f"{p['revives']} {p['user'].display_name}" for p in players if p['revives'] > 0])

        recap_emb = discord.Embed(title="📊 The Master's Records", color=0x34495E)
        recap_emb.add_field(name="🫦 Exhausted Assets", value=ru_text or "None", inline=False)
        recap_emb.add_field(name="⚔️ Most Dominations", value=kill_text or "None", inline=False)
        recap_emb.add_field(name="✨ Most Re-Aroused", value=revive_text or "None", inline=False)
        await ctx.send(embed=recap_emb)

        # Update DB
        await main_mod.update_user_stats_async(winner['user'].id, amount=prize, source="Echo Rumble Victory")
        with self._get_db() as conn:
            conn.execute("INSERT OR IGNORE INTO rumble_stats (user_id) VALUES (?)", (winner['user'].id,))
            conn.execute("UPDATE rumble_stats SET wins = wins + 1 WHERE user_id = ?", (winner['user'].id,))
            for p in players:
                conn.execute("INSERT OR IGNORE INTO rumble_stats (user_id) VALUES (?)", (p['user'].id,))
                conn.execute("UPDATE rumble_stats SET kills = kills + ? WHERE user_id = ?", (p['kills'], p['user'].id))
            conn.commit()

    @commands.command(name="pitrecords", aliases=["rumblelb", "pitlb"])
    async def pit_records(self, ctx):
        main_mod = sys.modules['__main__']
        with self._get_db() as conn:
            data = conn.execute("SELECT user_id, wins, kills FROM rumble_stats ORDER BY wins DESC, kills DESC LIMIT 10").fetchall()
        if not data: return await ctx.send("🥀 No one has performed yet.")
        desc = "\n".join([f"`#{i+1}` **{self.bot.get_user(row['user_id']).display_name if self.bot.get_user(row['user_id']) else row['user_id']}** — Wins: {row['wins']} | Kills: {row['kills']}" for i, row in enumerate(data)])
        await ctx.send(embed=main_mod.fiery_embed("🕵️ TOP PERFORMING ASSETS", desc))

    @commands.command(name="dailygear", aliases=["scan"])
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily_gear(self, ctx):
        main_mod = sys.modules['__main__']
        weights = {"Common": 0.70, "Rare": 0.25, "Epic": 0.05}; rarity = random.choices(list(weights.keys()), weights=list(weights.values()))[0]
        item = random.choice(self.item_pool[rarity])
        with self._get_db() as conn:
            conn.execute("INSERT INTO dungeon_inventory (user_id, item_name, rarity, atk, def, spd) VALUES (?, ?, ?, ?, ?, ?)",
                         (ctx.author.id, item['name'], rarity, item['atk'], item['def'], item['spd']))
            conn.commit()
        img_buf = await self.create_pack_image(ctx.author.display_avatar.url, item, rarity)
        embed = main_mod.fiery_embed("📡 DAILY SENSORY SCAN COMPLETE", f"Asset {ctx.author.mention}, new tools materialized.")
        embed.set_image(url="attachment://pack.png")
        await ctx.send(file=discord.File(img_buf, filename="pack.png"), embed=embed)

    @commands.command(name="scrap")
    async def scrap_item(self, ctx, item_id: int):
        main_mod = sys.modules['__main__']
        with self._get_db() as conn:
            item = conn.execute("SELECT item_name, rarity FROM dungeon_inventory WHERE id = ? AND user_id = ?", (item_id, ctx.author.id)).fetchone()
            if not item: return await ctx.send("❌ I can't break what I can't find.")
            conn.execute("DELETE FROM dungeon_inventory WHERE id = ?", (item_id,))
            conn.commit()
        payout = {"Common": 1000, "Rare": 3000, "Epic": 10000, "Legendary": 25000}.get(item['rarity'], 500)
        await main_mod.update_user_stats_async(ctx.author.id, amount=payout, source=f"Broken {item['item_name']}")
        await ctx.send(embed=main_mod.fiery_embed("♻️ NEURAL RECYCLING", f"Toy broken. Recovered `{payout:,} Flames`."))

async def setup(bot):
    main_mod = sys.modules['__main__']
    with main_mod.get_db_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS dungeon_inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, rarity TEXT, atk INTEGER, def INTEGER, spd INTEGER, is_equipped INTEGER DEFAULT 0)")
        conn.execute("CREATE TABLE IF NOT EXISTS rumble_stats (user_id INTEGER PRIMARY KEY, wins INTEGER DEFAULT 0, kills INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, pit_master_count INTEGER DEFAULT 0)")
        # Ensure config table for global stats exists
        conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
    cog = DungeonPacks(bot)
    await bot.add_cog(cog)
    bot.add_view(RumbleJoinView(cog))
