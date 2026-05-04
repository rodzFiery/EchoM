import discord
import os
from discord.ext import commands
from datetime import datetime, timezone
import database as db_module # Ensure this is imported for independent lookup

# ===== CORE HELPERS & AUDIT =====

async def send_audit_log(bot, AUDIT_CHANNEL_ID, user_id, amount, source, xp=0):
    """UPDATED: Guild-Independent Audit Logging System"""
    
    # --- INDEPENDENT LOOKUP LOGIC ---
    target_channel_id = AUDIT_CHANNEL_ID
    
    try:
        with db_module.get_db_connection() as conn:
            pass 
    except:
        pass

    channel = bot.get_channel(target_channel_id)
    if not channel: return
    
    try:
        user = await bot.fetch_user(user_id)
        # --- NEW EROTIC AUDIT STYLE ---
        embed = discord.Embed(
            title="🕵️ THE MASTER'S LEDGER: TRANSACTION RECORDED", 
            description=f"A new reaction in the pit. Asset {user.mention} has processed a transaction.",
            color=0x8B0000, 
            timestamp=datetime.now(timezone.utc)
        )
        
        image_path = "LobbyTopRight.jpg"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="ledger_logo.jpg")
            embed.set_thumbnail(url="attachment://ledger_logo.jpg")
        else:
            embed.set_thumbnail(url=user.display_avatar.url)
            file = None
            
        embed.add_field(name="🫦 Ident: Asset", value=user.mention, inline=True)
        embed.add_field(name="⛓️ Source: Protocol", value=f"**{source}**", inline=True)
        
        val_flames = f"🔥 **+{amount}** Flames added to vault." if amount >= 0 else f"📉 **{amount}** Flames extracted."
        embed.add_field(name="💰 Currency Flow", value=val_flames, inline=False)
        
        if xp > 0:
            embed.add_field(name="💦 Neural Imprint (XP)", value=f"**+{xp}** experience units synchronized.", inline=False)
        
        embed.set_footer(text="🔞 THE RED ROOM RECORDS EVERYTHING 🔞")
        
        if file:
            await channel.send(file=file, embed=embed)
        else:
            await channel.send(embed=embed)
    except Exception as e: 
        print(f"Audit Log Error: {e}")

def fiery_embed(bot, nsfw_mode_active, title, description, color=0xFF4500):
    """ADDED: Centralized Embed Styler"""
    ext = bot.get_cog("FieryExtensions")
    if (ext and ext.master_present) or nsfw_mode_active:
        color = 0x8B0000 
    
    embed = discord.Embed(title=f" {title.upper()} ", description=description, color=color)
    
    if os.path.exists("LobbyTopRight.jpg"):
        embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
        
    embed.set_footer(text="🔞 ECHO GAMES EDITION 🔞")
    embed.timestamp = datetime.now(timezone.utc)
    return embed

# ===== ADDED: COUNTING GAME PROTOCOL =====

class DungeonCounter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.counts = {} # Simple in-memory tracker: {channel_id: current_count}
        self.designated_channel = 0 # Persistent Math Protocol Channel

    def load_channel(self):
        """Loads designated math channel from config table."""
        try:
            with db_module.get_db_connection() as conn:
                # Ensure the table exists before selecting
                conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
                row = conn.execute("SELECT value FROM config WHERE key = 'math_channel'").fetchone()
                if row: self.designated_channel = int(row['value'])
        except Exception as e:
            print(f"Math Load Error: {e}")

    @commands.command(name="math")
    @commands.has_permissions(manage_channels=True)
    async def set_math_channel(self, ctx, channel: discord.TextChannel = None):
        """DESIGNATE THE MATH PIT: Sets the active channel for counting."""
        target = channel or ctx.channel
        self.designated_channel = target.id
        
        with db_module.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('math_channel', ?)", (str(target.id),))
            conn.commit()
            
        desc = f"Protocol **MATH** initialized. The Master will only monitor numbers in {target.mention}."
        await ctx.send(embed=fiery_embed(self.bot, False, "MATH PROTOCOL SET", desc))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        # Load channel if not already cached
        if self.designated_channel == 0: 
            self.load_channel()
            
        # RESTRICTION: Only process if the channel matches the !math designation
        if message.channel.id != self.designated_channel: return
        
        if message.content.isdigit():
            val = int(message.content)
            channel_id = message.channel.id
            current = self.counts.get(channel_id, 0)

            if val == current + 1:
                self.counts[channel_id] = val
                
                if val == 25:
                    self.counts[channel_id] = 0 # Reset
                    
                    desc = (
                        f"🎯 **25 REACHED.**\n\n"
                        f"Asset {message.author.mention}, you've hit the 25. "
                        f"The rules of the Pit are absolute: **A tease picture is now required.**\n\n"
                        f"🫦 *Don't keep us waiting. Upload your tribute.*"
                    )
                    
                    embed = fiery_embed(self.bot, True, "🔞 TRIBUTE REQUIRED 🔞", desc)
                    
                    if os.path.exists("LobbyTopRight.jpg"):
                        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
                        await message.channel.send(file=file, embed=embed)
                    else:
                        await message.channel.send(embed=embed)
            
            elif val <= current and current != 0:
                try: await message.add_reaction("❌")
                except: pass

async def setup(bot):
    # Registering the Cog properly to ensure !math is found
    cog = DungeonCounter(bot)
    cog.load_channel()
    await bot.add_cog(cog)
