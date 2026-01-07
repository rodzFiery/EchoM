import discord
from discord.ext import commands
import sqlite3
import os
import json
from datetime import datetime, timezone
import sys

# Persistence Logic for Railway
if os.path.exists("/app/data"):
    DATABASE_PATH = "/app/data/economy.db"
else:
    DATABASE_PATH = "data/economy.db"

# EMOJI SET BY RARITY - REBORN WITH EROTIC THEMES
TIER_EMOJIS = {
    "Basic": "⚪", "Normal": "🟢", "Rare": "🔵", 
    "Epic": "🟣", "Legendary": "🟠", "Supreme": "🔴"
}

# SECTION ICONS FOR PAGINATION
CAT_ICONS = {
    "Houses": "🏰", "Pets": "🫦", "Rings": "💍", "Stones": "💎", "Toys": "⛓️"
}

# AUDIT CHANNEL ID
AUDIT_CHANNEL_ID = 1438810509322223677

# ==========================================
# THE BLACK MARKET VAULT (RE-BALANCED PRICES)
# ==========================================
MARKET_DATA = {
    "Houses": {
        "Basic": [
            {"name": "Damp Cell", "price": 10000, "prot": 1, "desc": "A cold iron cage. Humiliating, but shields the first strike."},
            {"name": "Rusty Locker", "price": 15000, "prot": 1, "desc": "Barely enough space to breathe. No one looks here."},
            {"name": "Shadowed Shack", "price": 25000, "prot": 1, "desc": "A crude wooden box in the dungeon's alleyway."},
            {"name": "Stone Alcove", "price": 40000, "prot": 1, "desc": "A hole in the wall. Hard to hit, hard to stay in."},
            {"name": "Maimed Tent", "price": 50000, "prot": 1, "desc": "Tattered cloth that smells of sulfur and old blood."}
        ],
        "Normal": [
            {"name": "Sinner's Flat", "price": 100000, "prot": 2, "desc": "A basic apartment in the Red District. Secure and private."},
            {"name": "Guard's Bunk", "price": 150000, "prot": 2, "desc": "Stolen from a watchman. Comes with a sturdy lock."},
            {"name": "Brick Bunker", "price": 250000, "prot": 2, "desc": "Thick walls. No windows. Pure survival mindset."},
            {"name": "Tribute Lodge", "price": 400000, "prot": 2, "desc": "A community house for survivors. Strength in numbers."},
            {"name": "Basement Vault", "price": 600000, "prot": 2, "desc": "Hidden beneath a bar. Soundproof and reinforced."}
        ],
        "Rare": [
            {"name": "Gothic Manor", "price": 1500000, "prot": 4, "desc": "Ivy-covered stone and iron gates. For the rising elite."},
            {"name": "Obsidian Villa", "price": 2500000, "prot": 4, "desc": "Forged in the deep pits. Immune to common breaches."},
            {"name": "Neon Penthouse", "price": 5000000, "prot": 4, "desc": "Modern luxury meets dungeon grit. High-tech sensors."},
            {"name": "Hidden Sanctuary", "price": 8000000, "prot": 4, "desc": "Located behind a blood-red waterfall. Perfect solitude."},
            {"name": "Merchant's Estate", "price": 12000000, "prot": 4, "desc": "Gold-trimmed walls. You are a target, but a safe one."}
        ],
        "Epic": [
            {"name": "Velvet Dungeon", "price": 25000000, "prot": 8, "desc": "The ultimate playground. Padded walls and silk shackles."},
            {"name": "Crystal Cathedral", "price": 45000000, "prot": 8, "desc": "A holy site of survival. The glass is harder than diamond."},
            {"name": "Shadow Fortress", "price": 75000000, "prot": 8, "desc": "Built from solid darkness. Exists in two dimensions."},
            {"name": "Iron Monastery", "price": 120000000, "prot": 8, "desc": "A place of cold discipline and total protection."},
            {"name": "Sky-Bound Spire", "price": 250000000, "prot": 8, "desc": "A tower floating above the toxins. Only drones can reach you."}
        ],
        "Legendary": [
            {"name": "The Ivory Tower", "price": 500000000, "prot": 10, "desc": "Untouchable. Unreachable. Unforgiving prestige."},
            {"name": "Abyssal Throne", "price": 850000000, "prot": 10, "desc": "A seat of power in the void. FB is almost impossible."},
            {"name": "Grand Exhibition Hall", "price": 1200000000, "prot": 10, "desc": "You are the centerpiece. The Master guards your sleep."},
            {"name": "Molten Citadel", "price": 2000000000, "prot": 10, "desc": "A castle on a lava lake. Only the heat can find you."},
            {"name": "Kraken's Maw", "price": 3500000000, "prot": 10, "desc": "Underwater and sealed. Absolute isolation."}
        ],
        "Supreme": [
            {"name": "The Forbidden Palace", "price": 6000000000, "prot": 12, "desc": "The Master's quarters. You are property of the highest tier."},
            {"name": "Dominion Prime", "price": 8000000000, "prot": 12, "desc": "Total control over the landscape. You dictate the rules."},
            {"name": "Eternity's Bastion", "price": 10000000000, "prot": 12, "desc": "Built outside of time. You cannot fall if time stops."},
            {"name": "The Red Sun", "price": 15000000000, "prot": 12, "desc": "A celestial body mansion. You are a God of the Pit."},
            {"name": "Absolute Null", "price": 25000000000, "prot": 15, "desc": "SUPREME: You exist in negative space. FB is a myth."}
        ]
    },
    "Pets": {
        "Basic": [
            {"name": "Scrawny Rat", "price": 5000, "luck": 1, "desc": "It bites. Occasionally the right people."},
            {"name": "One-EyED Cat", "price": 10000, "luck": 1, "desc": "Grumpy, but brings luck in the final stretch."},
            {"name": "Sewer Toad", "price": 20000, "luck": 1, "desc": "Its slime is lucky. Don't ask why."},
            {"name": "Maimed Pigeon", "price": 35000, "luck": 1, "desc": "Flies low, but its heart is in the win."},
            {"name": "Starving Cur", "price": 50000, "luck": 1, "desc": "Loyal to anyone with a Flame and a whip."}
        ],
        "Normal": [
            {"name": "Pit Viper", "price": 150000, "luck": 2, "desc": "Deadly and sleek. Precision for the final blow."},
            {"name": "Trained Raven", "price": 250000, "luck": 2, "desc": "Whispers the enemy's fear to you."},
            {"name": "Black Rabbit", "price": 400000, "luck": 2, "desc": "Symbol of the dark moon and quick victories."},
            {"name": "Ferret Thief", "price": 600000, "luck": 2, "desc": "Steals the momentum from your 1v1 opponent."},
            {"name": "Dungeon Bat", "price": 800000, "luck": 2, "desc": "Sonic waves guide your final strike in the dark."}
        ],
        "Rare": [
            {"name": "Shadow Panther", "price": 3000000, "luck": 4, "desc": "Hunter of the abyss. Favors the silent striker."},
            {"name": "Silver Wolf", "price": 6000000, "luck": 4, "desc": "The alpha of the pack. Dominance is in its blood."},
            {"name": "Mech Spider", "price": 12000000, "luck": 4, "desc": "Calculates the winning move for you in real-time."},
            {"name": "Blood Hound", "price": 25000000, "luck": 4, "desc": "Tracks the scent of victory through the arena."},
            {"name": "Harpy Chick", "price": 45000000, "luck": 4, "desc": "Vicious and seductive. A very rare companion."}
        ],
        "Epic": [
            {"name": "Obsidian Gargoyle", "price": 100000000, "luck": 8, "desc": "Stays frozen until the final 1v1 begins."},
            {"name": "Succubus Spirit", "price": 250000000, "luck": 8, "desc": "She charms the RNG in your favor."},
            {"name": "Void Serpent", "price": 500000000, "luck": 8, "desc": "A creature from between-spaces. Reality is its toy."},
            {"name": "Iron Golem Minion", "price": 850000000, "luck": 8, "desc": "An unstoppable force protecting your victory."},
            {"name": "Spectral Stag", "price": 1200000000, "luck": 8, "desc": "A ghostly king. Regal, deadly, and lucky."}
        ],
        "Legendary": [
            {"name": "Inferno Drake", "price": 3000000000, "luck": 12, "desc": "Breathes fire upon your enemy's chances."},
            {"name": "Master's Shadow", "price": 6000000000, "luck": 12, "desc": "A piece of the Master. Your win is decreed."},
            {"name": "Lich Owl", "price": 9000000000, "luck": 12, "desc": "Sees all futures. Chooses the one where you win."},
            {"name": "Behemoth Cub", "price": 15000000000, "luck": 12, "desc": "Tiny, but carries the strength of a thousand games."},
            {"name": "Siren of Pits", "price": 25000000000, "luck": 12, "desc": "Her song makes the final opponent surrender."}
        ],
        "Supreme": [
            {"name": "World-Eater Worm", "price": 40000000000, "luck": 12, "desc": "A god-tier parasite. It eats the bad luck of its owner."},
            {"name": "Phoenix Reborn", "price": 60000000000, "luck": 12, "desc": "You cannot lose. You only rise again to conquer."},
            {"name": "Avatar of Lust", "price": 85000000000, "luck": 12, "desc": "The ultimate temptation. The arena falls in love with you."},
            {"name": "Chronos Cat", "price": 120000000000, "luck": 12, "desc": "Rewinds time until you land the killing blow."},
            {"name": "Tiamat's Seed", "price": 200000000000, "luck": 12, "desc": "SUPREME: The multi-headed God of Luck. It is over."}
        ]
    },
    "Rings": {
        "Basic": [
            {"name": "Copper Loop", "price": 5000, "desc": "A simple band. +1% Shared Luck with partners."},
            {"name": "Twisted Wire", "price": 10000, "desc": "Crude, but binds two souls together tightly."},
            {"name": "Rust Ring", "price": 18000, "desc": "Left behind by a fallen lover in the pit."},
            {"name": "Glass Band", "price": 25000, "desc": "Fragile, like most dungeon romances."},
            {"name": "Bone Signet", "price": 40000, "desc": "Carved from a finger bone. Creepy but bonding."}
        ],
        "Normal": [
            {"name": "Iron Girdle", "price": 100000, "desc": "Strong enough to withstand betrayal. +2% shared luck."},
            {"name": "Steel Promise", "price": 180000, "desc": "A pact of iron and fire for best friends."},
            {"name": "Leather Thong", "price": 300000, "desc": "Suggestive and binding. BDSM flavor."},
            {"name": "Lead Shackle", "price": 500000, "desc": "A heavy burden shared is a burden halved."},
            {"name": "Brass Seal", "price": 750000, "desc": "Official recognition of your partnership."}
        ],
        "Rare": [
            {"name": "Silver Vow", "price": 2000000, "desc": "Lustrous and enduring. Shared protection 4%."},
            {"name": "Amethyst Loop", "price": 4500000, "desc": "Protects the mind from arena-induced madness."},
            {"name": "Sapphire Bond", "price": 8000000, "desc": "A deep connection, as vast as the dark sea."},
            {"name": "Garnet Kiss", "price": 15000000, "desc": "A ring that tastes of salt and desire."},
            {"name": "Emerald Trust", "price": 30000000, "desc": "The rarest commodity in the dungeon: Trust."}
        ],
        "Epic": [
            {"name": "Gold Covenant", "price": 80000000, "desc": "Wealth and power shared between two dominant souls."},
            {"name": "Ruby Passion", "price": 150000000, "desc": "Burns with the heat of the Red Room."},
            {"name": "Diamond Decree", "price": 300000000, "desc": "A marriage that cannot be broken by death events."},
            {"name": "Platinum Oath", "price": 600000000, "desc": "The highest tier of friendship. Shared income +10%."},
            {"name": "Shadow Ring", "price": 1000000000, "desc": "Two people, one shadow. Total synchronization."}
        ],
        "Legendary": [
            {"name": "Obsidian Brand", "price": 4000000000, "desc": "Permanent. Painful. Powerful. 12% Shared Luck."},
            {"name": "Master's Blessing", "price": 8000000000, "desc": "The Master himself officiates this bond."},
            {"name": "Eldritch Eye", "price": 15000000000, "desc": "A ring that blinks. You see what your partner sees."},
            {"name": "Dragon's Heart", "price": 30000000000, "desc": "Brave and fiery. Shared protection is 15%."},
            {"name": "Void Marriage", "price": 60000000000, "desc": "Bound beyond the grave. Respawn together."}
        ],
        "Supreme": [
            {"name": "The One Ring", "price": 100000000000, "desc": "SUPREME: One to rule the pit. Absolute shared dominance."},
            {"name": "Soul Braid", "price": 250000000000, "desc": "SUPREME: Your souls are literally woven together."},
            {"name": "Infinity Band", "price": 400000000000, "desc": "SUPREME: Shared balance and no cooldowns for partners."},
            {"name": "Heart of Chaos", "price": 650000000000, "desc": "SUPREME: You can sacrifice your partner to win instantly."},
            {"name": "The Master's Rib", "price": 800000000000, "desc": "SUPREME: Created from the Master. You are the creators."}
        ]
    },
    "Stones": {
        "Basic": [
            {"name": "Pebble of Greed", "price": 2500, "desc": "+5% Work Flames for 1h."},
            {"name": "Dull Shard", "price": 5000, "desc": "Slightly increases beg success rate."},
            {"name": "Cold Flint", "price": 12000, "desc": "Sparks a small fire in the soul. +10 XP."},
            {"name": "Salt Crystal", "price": 20000, "desc": "Rub it in the wound. Intimidates others."},
            {"name": "Soot Stone", "price": 35000, "desc": "Hides your presence for 10 minutes."}
        ],
        "Normal": [
            {"name": "Polished Malachite", "price": 75000, "desc": "+10% Flames for 2h."},
            {"name": "Tiger's Eye", "price": 150000, "desc": "Luck in small gambles increased."},
            {"name": "Bloodstone", "price": 300000, "desc": "Consumable: Heal 50% HP in trial events."},
            {"name": "Moonstone", "price": 500000, "desc": "Increases flirt rewards for 1h."},
            {"name": "Jade Essence", "price": 800000, "desc": "Permanent +100 Max Balance limit."}
        ],
        "Rare": [
            {"name": "Sun Gem", "price": 2500000, "desc": "Forces 'Peak Heat' for you only for 30m."},
            {"name": "Tear of Siren", "price": 6000000, "desc": "Allows one escape from a dungeon trap."},
            {"name": "Wraith Shard", "price": 12000000, "desc": "Turns you invisible in the lobby for 5m."},
            {"name": "Lust Crystal", "price": 25000000, "desc": "Doubles all flirt/pimp rewards for 1h."},
            {"name": "Void Fragment", "price": 50000000, "desc": "Teleports you out of a losing 1v1 (No XP gain)."}
        ],
        "Epic": [
            {"name": "Demon Heart", "price": 150000000, "desc": "Permanent +5% Flame bonus from all sources."},
            {"name": "Angel Wing", "price": 350000000, "desc": "Protects you from one 'Blackout' event."},
            {"name": "Dragon Scale", "price": 750000000, "desc": "Socketable: Permanent +2% First Blood Prot."},
            {"name": "Titan Core", "price": 1200000000, "desc": "Doubles all XP for 24 hours."},
            {"name": "Witch's Brew", "price": 2500000000, "desc": "Resets all daily/weekly cooldowns instantly."}
        ],
        "Legendary": [
            {"name": "Star Soul", "price": 10000000000, "desc": "Permanent +15% XP/FXP gain."},
            {"name": "Master's Key", "price": 25000000000, "desc": "Allows you to bypass a 'Blackout' for everyone."},
            {"name": "God's Tear", "price": 45000000000, "desc": "Heals all injuries and grants 1M Flames."},
            {"name": "Hellfire Core", "price": 75000000000, "desc": "Socketable: 1v1 Final match luck +5%."},
            {"name": "Abyssal Pearl", "price": 120000000000, "desc": "Permanent: You no longer lose flames on death."}
        ],
        "Supreme": [
            {"name": "Infinity Stone", "price": 200000000000, "desc": "SUPREME: Control over time. Reset any cooldown."},
            {"name": "The Origin Gem", "price": 350000000000, "desc": "SUPREME: Grants one free win per week."},
            {"name": "The Master's Eye", "price": 500000000000, "desc": "SUPREME: See everyone's secret items and balance."},
            {"name": "Chaos Emerald", "price": 750000000000, "desc": "SUPREME: Change the winner of a game (Once/Week)."},
            {"name": "Reality Shard", "price": 950000000000, "desc": "SUPREME: Force Peak Heat for the whole server for 24h."}
        ]
    },
    "Toys": {
        "Basic": [
            {"name": "Leather Crop", "price": 5000, "desc": "Suggestive. +5% Work XP for 1h."},
            {"name": "Ball Gag", "price": 10000, "desc": "Silences the weak. Increases intimidation."},
            {"name": "Blindfold", "price": 22000, "desc": "Focuses the mind. +2% Luck in trials."},
            {"name": "Feather Tickler", "price": 35000, "desc": "Distracts the enemy. Minor luck boost."},
            {"name": "Silk Ribbon", "price": 50000, "desc": "Binds gently. Shared XP bonus 1%."}
        ],
        "Normal": [
            {"name": "Weighted Paddle", "price": 150000, "desc": "Delivers a lesson. +5% Pimp/Work rewards."},
            {"name": "Latex Hood", "price": 250000, "desc": "Anonymity in the pit. Reduces death penalty."},
            {"name": "Steel Handcuffs", "price": 450000, "desc": "Standard issue control. +5% Intimidation."},
            {"name": "Velvet Rope", "price": 600000, "desc": "BDSM flavor. Increases flirt success 10%."},
            {"name": "Glass Plug", "price": 850000, "desc": "Beautiful and daring. Boosts status in gallery."}
        ],
        "Rare": [
            {"name": "Electric Wand", "price": 4000000, "desc": "Shocking results. +10% Work Flames for 1h."},
            {"name": "Spiked Collar", "price": 9000000, "desc": "Shows who is owned. +5% FXP gain."},
            {"name": "Nipple Clamps", "price": 18000000, "desc": "Focus through pain. Reduces trial cooldown."},
            {"name": "Fur-Lined Cuffs", "price": 35000000, "desc": "Comfort in bondage. Shared luck +5%."},
            {"name": "Rosewood Cane", "price": 60000000, "desc": "Elegant discipline. Permanent +1% Luck."}
        ],
        "Epic": [
            {"name": "Gilded Cage", "price": 200000000, "desc": "The most expensive home. FB Prot +5%."},
            {"name": "Crystal Dildo", "price": 450000000, "desc": "Pure luxury. Increases XP gain by 10% for 12h."},
            {"name": "Iron Maiden", "price": 900000000, "desc": "The ultimate test. Survivors get 1M Flames."},
            {"name": "Vibrating Egg", "price": 1800000000, "desc": "Constant buzz. Keeps you alert for Blackouts."},
            {"name": "Master's Paddle", "price": 3500000000, "desc": "Signed by the Master. Intimidates everyone."}
        ],
        "Legendary": [
            {"name": "Dragon's Tail", "price": 15000000000, "luck": 12, "desc": "A whip made of dragon hide. Luck +8%."},
            {"name": "The Gilded Leash", "price": 30000000000, "desc": "Total ownership. Dominants get 5% of Sub's work."},
            {"name": "Obsidian Mask", "price": 60000000000, "desc": "Hides your soul. No one can steal your flames."},
            {"name": "The Velvet Throne", "price": 90000000000, "desc": "A seat for a King. Permanent +5% all income."},
            {"name": "Crowned Shackle", "price": 150000000000, "desc": "The mark of a legend. Your name glows red."}
        ],
        "Supreme": [
            {"name": "The God's Crop", "price": 300000000000, "desc": "SUPREME: One hit grants instant Level Up."},
            {"name": "Absolute Restraint", "price": 500000000000, "desc": "SUPREME: Lock any user out of commands for 10m."},
            {"name": "Sovereign's Scepter", "price": 700000000000, "desc": "SUPREME: Control the arena events."},
            {"name": "The Eternal Collar", "price": 850000000000, "desc": "SUPREME: You are now the Master's Favorite."},
            {"name": "Void Pleasure", "price": 950000000000, "desc": "SUPREME: Ascend beyond the dungeon. Infinite XP."}
        ]
    }
}

# --- INTERACTIVE COMPONENTS ---

class ShopView(discord.ui.View):
    def __init__(self, cog, category, page, user, items):
        super().__init__(timeout=60)
        self.cog = cog
        self.category = category
        self.page = page
        self.user = user
        self.items = items

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Only the boutique customer can use these buttons.", ephemeral=True)
            return False
        return True

    async def handle_buy(self, interaction, index):
        if index >= len(self.items): return
        item_name = self.items[index]['name']
        await interaction.response.defer()
        await self.cog.buy_item(interaction, item_name=item_name)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.grey, row=1)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        await self.cog.update_shop_message(interaction, self.category, self.page, self.user)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.grey, row=1)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self.cog.update_shop_message(interaction, self.category, self.page, self.user)

    @discord.ui.button(label="💰1", style=discord.ButtonStyle.success, row=0)
    async def buy1(self, i, b): await self.handle_buy(i, 0)
    @discord.ui.button(label="💰2", style=discord.ButtonStyle.success, row=0)
    async def buy2(self, i, b): await self.handle_buy(i, 1)
    @discord.ui.button(label="💰3", style=discord.ButtonStyle.success, row=0)
    async def buy3(self, i, b): await self.handle_buy(i, 2)
    @discord.ui.button(label="💰4", style=discord.ButtonStyle.success, row=0)
    async def buy4(self, i, b): await self.handle_buy(i, 3)
    @discord.ui.button(label="💰5", style=discord.ButtonStyle.success, row=0)
    async def buy5(self, i, b): await self.handle_buy(i, 4)

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = DATABASE_PATH
        self.init_relation_db()

    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_relation_db(self):
        with self.get_db_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS relationships (
                user_one INTEGER,
                user_two INTEGER,
                type TEXT,
                shared_luck REAL DEFAULT 0.0,
                passive_income REAL DEFAULT 0.0,
                PRIMARY KEY (user_one, user_two)
            )""")
            conn.commit()

    def get_item_details(self, name):
        for category, tiers in MARKET_DATA.items():
            for tier, items in tiers.items():
                for item in items:
                    if item['name'].lower() == name.lower():
                        return item, category, tier
        return None, None, None

    # Helper for Button UI updates
    async def update_shop_message(self, interaction, category, page, user):
        tiers = list(MARKET_DATA[category].keys())
        page = max(1, min(page, len(tiers)))
        embed, view = await self.create_shop_ui(category, page, user)
        await interaction.response.edit_message(embed=embed, view=view)

    async def create_shop_ui(self, category, page, user):
        tiers = list(MARKET_DATA[category].keys())
        current_tier = tiers[page-1]
        items = MARKET_DATA[category][current_tier]
        t_emoji = TIER_EMOJIS[current_tier]
        cat_icon = CAT_ICONS.get(category, "🔞")

        embed = discord.Embed(title=f"{cat_icon} RED ROOM BOUTIQUE: {category.upper()}", color=0x800020)
        embed.set_thumbnail(url="https://i.imgur.com/8N8K8S8.png") 
        embed.description = f"🫦 **Sector:** {current_tier} {t_emoji}\n*Browse the vault, asset.*"

        item_list = ""
        for i, item in enumerate(items):
            item_list += f"💰{i+1} {t_emoji} **{item['name']}** — `{item['price']:,}` 🔥\n*{item['desc']}*\n\n"
        
        embed.add_field(name=f"━━━ {current_tier.upper()} SELECTION ━━━", value=item_list, inline=False)
        embed.set_footer(text=f"Tier {page}/{len(tiers)} | Use Buttons or !buy <Name>")
        embed.timestamp = datetime.now(timezone.utc)
        
        view = ShopView(self, category, page, user, items)
        view.prev.disabled = (page == 1)
        view.next.disabled = (page == len(tiers))
        for idx, btn in enumerate([view.buy1, view.buy2, view.buy3, view.buy4, view.buy5]):
            btn.disabled = (idx >= len(items))
            
        return embed, view

    @commands.command(name="shop")
    async def shop_display(self, ctx, category: str = "Houses", page: int = 1):
        category = category.capitalize()
        if category not in MARKET_DATA:
            err_emb = discord.Embed(title="❌ Market Error", description="Valid Categories: Houses, Pets, Rings, Stones, Toys", color=0xFF0000)
            return await ctx.send(embed=err_emb)

        embed, view = await self.create_shop_ui(category, page, ctx.author)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="buy")
    async def buy_item(self, ctx, *, item_name: str):
        # Support for both standard command and Button interaction
        author = ctx.author if hasattr(ctx, 'author') else ctx.user
        send_method = ctx.send if hasattr(ctx, 'send') else ctx.followup.send
        guild = ctx.guild if hasattr(ctx, 'guild') else ctx.guild

        found_item, found_cat, found_tier = self.get_item_details(item_name)
        
        if not found_item: 
            err_emb = discord.Embed(title="❌ Item Not Found", description=f"The item '{item_name}' does not exist.", color=0xFF0000)
            return await send_method(embed=err_emb)

        if found_cat == "Rings":
            return await self.handle_ring_purchase(ctx, found_item, found_tier)

        with self.get_db_connection() as conn:
            user = conn.execute("SELECT balance, titles FROM users WHERE id = ?", (author.id,)).fetchone()
            if not user or user['balance'] < found_item['price']:
                lack_emb = discord.Embed(title="❌ Insufficient Flames", description=f"You need **{found_item['price']:,}** 🔥.", color=0xFF0000)
                return await send_method(embed=lack_emb)

            inv = json.loads(user['titles']) if user['titles'] else []
            if found_item['name'] in inv: 
                own_emb = discord.Embed(title="❌ Already Possessed", description=f"You already own the **{found_item['name']}**.", color=0xFFFF00)
                return await send_method(embed=own_emb)

            inv.append(found_item['name'])
            conn.execute("UPDATE users SET balance = balance - ?, titles = ? WHERE id = ?", 
                         (found_item['price'], json.dumps(inv), author.id))
            conn.commit()

        success_emb = discord.Embed(title="🫦 Acquisition Successful", description=f"You have taken possession of: **{found_item['name']}**", color=0x00FF00)
        
        if found_tier == "Supreme":
            success_emb.title = "🚨 SUPREME ASSET CLAIMED!"
            success_emb.color = 0xFF0000
            await send_method(content=f"@everyone 🔞 **A SOUL HAS REACHED APEX POWER!**", embed=success_emb)
        else:
            await send_method(embed=success_emb)

        # --- AUDIT LOG FOR PURCHASES ---
        main_mod = sys.modules['__main__']
        audit_channel = self.bot.get_channel(AUDIT_CHANNEL_ID)
        if audit_channel:
            log_emb = main_mod.fiery_embed("🕵️ VOYEUR TRANSACTION REPORT", f"The Master's Ledger has recorded a purchase in {found_cat}.")
            log_emb.set_thumbnail(url="https://i.imgur.com/8N8K8S8.png") # The Fiery JPG
            log_emb.add_field(name="Asset Involved", value=author.mention, inline=True)
            log_emb.add_field(name="Item Claimed", value=f"{TIER_EMOJIS[found_tier]} **{found_item['name']}**", inline=True)
            log_emb.add_field(name="Price Paid", value=f"`{found_item['price']:,}` 🔥", inline=True)
            log_emb.description = f"🔞 **VOYEUR NOTE:** {author.display_name} is increasing their power. Their inventory has been updated with the {found_tier} asset: *{found_item['desc']}*"
            log_emb.set_footer(text="The Ledger never lies. Your wealth is monitored.")
            await audit_channel.send(embed=log_emb)

    @commands.command(name="inv", aliases=["inventory", "assets"])
    async def inventory(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        
        with self.get_db_connection() as conn:
            user = conn.execute("SELECT titles, spouse FROM users WHERE id = ?", (target.id,)).fetchone()
        
        if not user or not user['titles'] or user['titles'] == "[]":
            desc = "This soul owns nothing but their chains." if target == ctx.author else f"{target.display_name} is currently naked of assets."
            return await ctx.send(embed=discord.Embed(title=f"🎒 {target.display_name.upper()}'S VAULT", description=desc, color=0x808080))

        owned_names = json.loads(user['titles'])
        categories = {"Houses": [], "Pets": [], "Stones": [], "Toys": [], "Other": []}
        
        for name in owned_names:
            item, cat, tier = self.get_item_details(name)
            if item:
                emoji = TIER_EMOJIS.get(tier, "⚪")
                stat_text = ""
                if cat == "Houses": stat_text = f" [🛡️ Prot: {item.get('prot', 0)}]"
                elif cat == "Pets": stat_text = f" [🍀 Luck: {item.get('luck', 0)}]"
                categories[cat].append(f"{emoji} **{name}**{stat_text}")
            else:
                categories["Other"].append(f"⚪ **{name}**")

        embed = discord.Embed(title=f"🎒 {target.display_name.upper()}'S PRIVATE VAULT", color=0xFF69B4)
        embed.set_thumbnail(url=target.display_avatar.url)
        
        if user['spouse']:
            embed.description = f"💍 **Bound to:** <@{user['spouse']}>"

        for cat_name, items in categories.items():
            if items:
                content = "\n".join(items)
                if len(content) > 1000: content = content[:997] + "..."
                embed.add_field(name=f"{CAT_ICONS.get(cat_name, '📦')} {cat_name.upper()}", value=content, inline=False)

        embed.set_footer(text=f"Total Assets: {len(owned_names)} | The Master is watching.")
        embed.timestamp = datetime.now(timezone.utc)
        await ctx.send(embed=embed)

    async def handle_ring_purchase(self, ctx, item, tier):
        author = ctx.author if hasattr(ctx, 'author') else ctx.user
        send_method = ctx.send if hasattr(ctx, 'send') else ctx.followup.send
        channel = ctx.channel if hasattr(ctx, 'channel') else ctx.message.channel
        guild = ctx.guild if hasattr(ctx, 'guild') else ctx.guild

        def check(m):
            return m.author == author and m.channel == channel

        prompt_emb = discord.Embed(title="💍 Soul Binding Ceremony", description=f"You are sacrificing flames for the **{item['name']}**.\nTag the soul you wish to bind to your destiny.", color=0xFF69B4)
        await send_method(embed=prompt_emb)
        
        try:
            msg = await self.bot.wait_for('message', timeout=30.0, check=check)
            if not msg.mentions:
                return await channel.send(embed=discord.Embed(title="❌ Binding Failed", description="You cannot bind a ghost. Tag a user.", color=0xFF0000))
            
            target = msg.mentions[0]
            if target.id == author.id:
                return await channel.send(embed=discord.Embed(title="❌ Forbidden Narcissism", description="A bond requires two souls.", color=0xFF0000))

            luck_bonus = 0.01 
            income_bonus = 0.0 

            if tier == "Normal": luck_bonus = 0.02
            elif tier == "Rare": luck_bonus = 0.04
            elif tier == "Epic": luck_bonus = 0.08; income_bonus = 0.10
            elif tier == "Legendary": luck_bonus = 0.12; income_bonus = 0.15
            elif tier == "Supreme": luck_bonus = 0.20; income_bonus = 0.25

            with self.get_db_connection() as conn:
                user = conn.execute("SELECT balance FROM users WHERE id = ?", (author.id,)).fetchone()
                if not user or user['balance'] < item['price']:
                    return await channel.send(discord.Embed(title="❌ Transaction Denied", description="Your wallet cannot afford this devotion.", color=0xFF0000))

                u1, u2 = sorted([author.id, target.id])
                conn.execute("INSERT OR REPLACE INTO relationships (user_one, user_two, type, shared_luck, passive_income) VALUES (?, ?, ?, ?, ?)",
                             (u1, u2, "Bound", luck_bonus, income_bonus))
                
                conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (item['price'], author.id))
                conn.commit()

            bond_emb = discord.Embed(title="💞 THE CHAINS OF DESIRE", color=0xFF1493)
            bond_emb.description = f"{author.mention} and {target.mention} have sealed their fates with the **{item['name']}**.\n\n" \
                                   f"🍀 **Shared Arousal (Luck):** +{int(luck_bonus*100)}%\n" \
                                   f"💰 **Shared Ecstasy (Income):** +{int(income_bonus*100)}%"
            await channel.send(embed=bond_emb)

            # --- AUDIT LOG FOR RING PURCHASE ---
            main_mod = sys.modules['__main__']
            audit_channel = self.bot.get_channel(AUDIT_CHANNEL_ID)
            if audit_channel:
                log_emb = main_mod.fiery_embed("🕵️ VOYEUR BONDING AUDIT", f"The Master's Voyeurs have recorded a soul-binding ritual.")
                log_emb.set_thumbnail(url="https://i.imgur.com/8N8K8S8.png")
                log_emb.add_field(name="Soul One (Buyer)", value=author.mention, inline=True)
                log_emb.add_field(name="Soul Two (Target)", value=target.mention, inline=True)
                log_emb.add_field(name="The Bond", value=f"{TIER_EMOJIS[tier]} **{item['name']}**", inline=True)
                log_emb.description = f"💍 **VOYEUR NOTE:** Two assets are now synchronized. {author.display_name} has sacrificed `{item['price']:,}` 🔥 to weave their fate with {target.display_name}."
                await audit_channel.send(embed=log_emb)

        except Exception as e:
            await channel.send(embed=discord.Embed(title="❌ Ritual Interrupted", description="The Master is bored by your hesitation. Request expired.", color=0xFF0000))

    # ADDED: Sell Command to Liquidate Assets for 50% Value
    @commands.command(name="sell")
    async def sell_item(self, ctx, *, item_name: str):
        """Liquidate an asset for 50% of its original Flame value."""
        found_item, found_cat, found_tier = self.get_item_details(item_name)
        if not found_item:
            return await ctx.send(embed=discord.Embed(title="❌ Item Not Found", description="This asset does not exist in our records.", color=0xFF0000))

        with self.get_db_connection() as conn:
            user = conn.execute("SELECT titles FROM users WHERE id = ?", (ctx.author.id,)).fetchone()
            inv = json.loads(user['titles']) if user['titles'] else []
            
            if found_item['name'] not in inv:
                return await ctx.send(embed=discord.Embed(title="❌ Theft Attempt", description="You cannot sell what you do not possess.", color=0xFF0000))
            
            sell_value = int(found_item['price'] * 0.5)
            inv.remove(found_item['name'])
            
            conn.execute("UPDATE users SET balance = balance + ?, titles = ? WHERE id = ?", (sell_value, json.dumps(inv), ctx.author.id))
            conn.commit()

        sell_emb = discord.Embed(title="💰 ASSET LIQUIDATED", description=f"The Master has reclaimed the **{found_item['name']}**.\n\nReturned: **{sell_value:,}** 🔥", color=0xFFFF00)
        await ctx.send(embed=sell_emb)

async def setup(bot):
    await bot.add_cog(Shop(bot))
