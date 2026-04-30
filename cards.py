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
        self.spawn_channel_id = 1438810509322223677 
        self.current_card = None
        
        # ACTIVITY LOGIC: restored and tied to member-spawns
        self.activity_pool = 0
        self.required_activity = 15 # Messages needed to trigger a spawn
        
        self._init_db()
        
        # PERSISTENCE: Restore the spawn channel from the central config table
        self._load_config()

        # SERIES DEFINITIONS (Used to flavor the member-cards)
        self.series_types = ["Lava", "Gladiator", "Water", "Space", "Grass", "Tricity", "Flirt", "Pink", "Ground", "Mystery"]

    def _init_db(self):
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS user_cards (user_id INTEGER, card_name TEXT, tier TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
            conn.execute("CREATE TABLE IF NOT EXISTS card_config (key TEXT PRIMARY KEY, value TEXT)")
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
        if roll < 0.8: return "supreme", 0xFFD700
        if roll < 4.0: return "legendary", 0xF1C40F
        if roll < 12.0: return "platine", 0xE5E4E2
        if roll < 28.0: return "epic", 0x9B59B6
        if roll < 55.0: return "rare", 0x3498DB
        return "basic", 0x95A5A6

    async def spawn_card(self, guild):
        """LOCALIZATION SEQUENCE: Selects a member based on activity pulse."""
        channel = self.bot.get_channel(self.spawn_channel_id)
        if not channel: return

        # Target a random member who isn't a bot
        members = [m for m in guild.members if not m.bot]
        if not members: return
        target_member = random.choice(members)

        tier_name, color = self.get_random_tier()
        series = random.choice(self.series_types)
        
        self.current_card = {
            "name": target_member.display_name,
            "tier": tier_name,
            "type": series,
            "id": target_member.id
        }

        main_mod = sys.modules['__main__']
        
        desc = (
            f"⚡ **ACTIVITY SPIKE DETECTED:** A soul has manifested in the thermal vents!\n\n"
            f"👤 **Asset:** {target_member.mention}\n"
            f"🧬 **Series:** {series}\n"
            f"💎 **Tier:** `{tier_name.upper()}`\n\n"
            f"Type `!catch {target_member.display_name}` to claim this asset!"
        )
        
        embed = main_mod.fiery_embed("🛰️ NEURAL ASSET LOCALIZED", desc, color=color)
        embed.set_image(url=target_member.display_avatar.url)
        embed.set_footer(text=f"Triggered by server activity | {series} series")
        
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        """The Listener: Increments activity pool and checks for spawn readiness."""
        if message.author.bot or not message.guild: return
        
        # Track global server activity
        self.activity_pool += 1
        
        if self.activity_pool >= self.required_activity:
            # Chance check so it's not exactly every 15 messages (more addictive)
            if random.random() < 0.40: 
                self.activity_pool = 0
                await self.spawn_card(message.guild)

    async def check_mastery(self, ctx, user_id):
        pass

    @commands.command()
    async def catch(self, ctx, *, card_name: str):
        if not self.current_card or card_name.lower() != self.current_card['name'].lower():
            return await ctx.reply("❌ Asset signal lost or incorrect ID signature!")
        
        main_mod = sys.modules['__main__']
        user_id = ctx.author.id
        card = self.current_card
        self.current_card = None 

        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT INTO user_cards (user_id, card_name, tier) VALUES (?, ?, ?)", (user_id, card['name'], card['tier']))
            conn.commit()
            total_count = conn.execute("SELECT COUNT(*) FROM user_cards WHERE user_id = ?", (user_id,)).fetchone()[0]

        embed = main_mod.fiery_embed("🔥 ASSET SECURED!", f"{ctx.author.mention} has archived **{card['name']}**!", color=0xFFD700)
        # FIX APPLIED BELOW: String and Brackets corrected
        embed.add_field(name="🧬 Metadata", value=f"Series:\nTier:.upper()}", inline=True)
        embed.add_field(name="📊 Archive", value=f"**Total Assets:** {total_count}", inline=True)
        
        target_member = ctx.guild.get_member(card['id'])
        if target_member:
            embed.set_thumbnail(url=target_member.display_avatar.url)

        await ctx.send(embed=embed)

    @commands.command(name="pokedex")
    async def pokedex(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            rows = conn.execute("SELECT card_name, tier, COUNT(*) as count FROM user_cards WHERE user_id = ? GROUP BY card_name", (target.id,)).fetchall()
        if not rows: return await ctx.send(f"📕 {target.display_name}'s Archive is empty.")
        
        desc = "### 🛡️ NEURAL ARCHIVE\n"
        for row in rows:
            desc += f"• **{row[0]}** (`{row[1].upper()}`) — x{row[2]}\n"
        
        embed = main_mod.fiery_embed(f"📕 {target.display_name}'S ARCHIVE", desc)
        await ctx.send(embed=embed)

    @commands.command(name="collections")
    async def collections(self, ctx, member: discord.Member = None):
        await ctx.send("The Checklist Protocol is analyzing the human metadata...")

async def setup(bot):
    await bot.add_cog(CardSystem(bot))
