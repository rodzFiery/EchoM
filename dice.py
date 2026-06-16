# FIX: Python 3.13 compatibility shim for audiooptry:
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
        import sys
        import sys
        sys.modules['audioop'] = audioop
    except ImportError:
        pass 

import discord
from discord.ext import commands
import sqlite3
import os
import json
import random
import asyncio
from datetime import datetime, timezone
import sys

# Persistence Logic for Database
if os.path.exists("/app/data"):
    DATABASE_PATH = "/app/data/economy.db"
else:
    DATABASE_PATH = "data/economy.db"

# AUDIT CHANNEL LOGGING
AUDIT_CHANNEL_ID = 1438810509322223677

# THE CYBER-DUNGEON DICE DARES - FOCUSING EXCLUSIVELY ON FLASH EXECUTIONS
DICE_DARES = {
    1: {"action": "LIVE FLASH", "desc": "Expose your designated assets to the live gallery immediately or suffer total failure."},
    2: {"action": "COMMAND FLASH", "desc": "Pick another participant in the current lobby. They must execute a live flash for your amusement."},
    3: {"action": "MUTUAL FLASH BINDING", "desc": "Select a partner. Both of you must perform a flash execution simultaneously in public view."},
    4: {"action": "RED COUTURIER FLASH", "desc": "Flash the gallery while holding or highlighting an object that is explicitly crimson red."},
    5: {"action": "SHADOW MINIMALIST FLASH", "desc": "Drop your coverage to absolute zero in a dimly lit setting and display the flash contrast."},
    6: {"action": "NEON CHROME REVEAL", "desc": "Apex Roll. Initiate a high-intensity flash capture utilizing neon screen tones or glowing accents."},
    7: {"action": "TARGETED TRANSMISSION", "desc": "Select one specific user from the room. Send them a direct, unedited personal flash execution."},
    8: {"action": "SILENT FLASH EXHIBITION", "desc": "Execute a full asset flash without typing a single character of context in the text feed."},
    9: {"action": "THE HOST'S TOAST", "desc": "Deploy your cleanest flash execution directly onto the hosting user's interface feed."},
    10: {"action": "DOUBLE REVEAL MATRIX", "desc": "The energy shifts. You must execute a live flash now, and then perform another one at the end of this round."},
    11: {"action": "KNEEL AND EXPOSE", "desc": "Submit a live exposure framed from a submissive, low-angled positioning perspective."},
    12: {"action": "BLACKOUT EXCLUSION", "desc": "Flash the chat using a monochrome or black-and-white visual filter context entirely."},
    13: {"action": "VELVET LINK FLASH", "desc": "Choose a partner. You are both bound to frame your flash executions with matching room textures."},
    14: {"action": "THE WHIP FLASH", "desc": "Perform a sudden, rapid-fire flash execution that reveals and vanishes instantly within seconds."},
    15: {"action": "EXHIBITIONIST GLORY", "desc": "Post a highly artistic, stylized flash showcasing your absolute peak physical aesthetic."},
    16: {"action": "CHAINED CAPTURE", "desc": "Incorporate cold metal jewelry, chains, or links into your direct flash presentation frame."},
    17: {"action": "SPOUSE SYNCHRONIZATION", "desc": "If bound to a partner, demand they witness or co-sign your upcoming live flash layout immediately."},
    18: {"action": "GLITCH MATRIX EXPOSURE", "desc": "Randomly choose any user currently online. Send them a cryptic live flash without warning."},
    19: {"action": "TITAN FOCUS TIMEOUT", "desc": "Frame a detailed close-up flash focusing completely on a single specific anatomical asset."},
    20: {"action": "SOVEREIGN INVERSION FLOW", "desc": "The player with the lowest score in the room dictates the exact theme of your immediate live flash."},
    21: {"action": "BLINDFOLD PROTOCOL REVEAL", "desc": "Cover your sightline with a dark cloth or object while executing a complete live asset flash."},
    22: {"action": "BALL GAG RESTRAINT SIGNAL", "desc": "Flash the audience while biting down on a dark item or displaying a restricted vocal posture."},
    23: {"action": "SPIKED CONTRAST LOOK", "desc": "Utilize highly creative shadows or sharp object silhouettes to outline your live flash execution."},
    24: {"action": "CROWNED OVERLORD DISPLAY", "desc": "Dedicate a magnificent, high-profile flash directly to the highest-ranking user in the chat grid."},
    25: {"action": "SHADOW SHIFT PAN", "desc": "Slowly transition an object out of the way to uncover a dynamic live flash framing over several seconds."},
    26: {"action": "SINFUL TEXTURE SCREEN", "desc": "Execute a flash that prominently highlights smooth leather, lace, or latex fabric elements directly against skin."},
    27: {"action": "ABYSSAL CONTRACT SUBMISSION", "desc": "Commit to dropping your coverings twice in a row before your 5-minute timer hits absolute zero."},
    28: {"action": "MOLTEN EMBER BACKLIGHT", "desc": "Perform a flash execution utilizing heavy warm backlighting or artificial candle lighting tones."},
    29: {"action": "VOIDS PLEASURE GLANCE", "desc": "Provide a teasing, partial live flash that hints at everything but reveals only selective quadrants."},
    30: {"action": "NEON OVERDRIVE BLAST", "desc": "Deploy an ultra-bright flash execution using the maximum lighting output your environment can provide."},
    31: {"action": "DOMINION FORFEIT REVEAL", "desc": "Completely strip away your preferred layer of attire and post the live flash confirmation."},
    32: {"action": "KRAKEN GRIP CAPTIVITY", "desc": "You are anchored. You must remain completely unclad from the waist up for the next two full rounds."},
    33: {"action": "ETERNAL FAVORITE SPOTLIGHT", "desc": "The Master demands a masterpiece. Take your time to frame a visually flawless, high-tier premium live flash."},
    34: {"action": "SAPPHIRE COLD REVEAL", "desc": "Incorporate objects or elements featuring a deep blue hue directly into your live flash frame."},
    35: {"action": "CHAOS REVERSAL SWAP", "desc": "Pick the person who rolled before you; demand they match whatever flash style you choose to deploy right now."},
    36: {"action": "ABSOLUTE NULLIFICATION RELEASE", "desc": "SUPREME ROLL. Force the entire lobby to execute a simultaneous group flash in the open gallery."}
}

class DiceLobbyView(discord.ui.View):
    def __init__(self, host, max_rounds):
        super().__init__(timeout=120)
        self.host = host
        self.max_rounds = max_rounds
        self.participants = [host.id]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    @discord.ui.button(label="JOIN LOBBY", style=discord.ButtonStyle.danger, emoji="🎲")
    async def join_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("Your soul is already locked into this grid.", ephemeral=True)
        
        self.participants.append(interaction.user.id)
        await interaction.response.send_message(f"➕ {interaction.user.mention} has stepped into the circle.", ephemeral=False)

    @discord.ui.button(label="START EXPERIMENT", style=discord.ButtonStyle.success, emoji="🔥")
    async def start_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host.id:
            return await interaction.response.send_message("Only the Master or officiating Moderator who sparked this ritual can start it.", ephemeral=True)
        
        if len(self.participants) < 1:
            return await interaction.response.send_message("The pit requires sacrifices. Recruit more souls before initiating.", ephemeral=True)
        
        self.stop()
        await interaction.response.defer()

class DiceTurnView(discord.ui.View):
    def __init__(self, active_player):
        super().__init__(timeout=300) # FIXED: Turn dashboard interactive window matches the 5-minute mark
        self.active_player = active_player
        self.rolled = asyncio.Event()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.active_player.id:
            await interaction.response.send_message("It is not your turn to roll the dice of fate.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="ROLL DICE (5m)", style=discord.ButtonStyle.primary, emoji="🎲")
    async def roll_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        self.rolled.set()
        await interaction.response.defer()

class DiceGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = DATABASE_PATH
        self.active_rooms = set()
        self.init_dice_db()

    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_dice_db(self):
        with self.get_db_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS dice_stats (
                user_id INTEGER PRIMARY KEY,
                games_played INTEGER DEFAULT 0,
                dares_completed INTEGER DEFAULT 0,
                chickens_out INTEGER DEFAULT 0,
                highest_roll INTEGER DEFAULT 0
            )""")
            conn.commit()
        conn.close()

    def update_user_stat(self, user_id, column):
        with self.get_db_connection() as conn:
            conn.execute(f"INSERT OR IGNORE INTO dice_stats (user_id) VALUES (?)", (user_id,))
            conn.execute(f"UPDATE dice_stats SET {column} = {column} + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
        conn.close()

    # FIXED: Command trigger converted from !dice to !echodice as specified
    @commands.command(name="echodice")
    @commands.has_permissions(manage_messages=True)
    async def initiate_dice_game(self, ctx, rounds: int = 3):
        if ctx.channel.id in self.active_rooms:
            return await ctx.send("❌ An active Flesh Roulette is already processing in this sector.")

        if rounds < 1 or rounds > 10:
            return await ctx.send("❌ Error: Total rounds must settle anywhere between 1 and 10.")

        self.active_rooms.add(ctx.channel.id)

        lobby_emb = discord.Embed(
            title="🎲 THE FLESH ROULETTE: LOBBY INITIATED",
            description=f"**Host:** {ctx.author.mention}\n**Target Threshold:** `{rounds}` Intense Rounds\n\n*Click the execution panel button below to lock your destination into the engine. Dares await.*",
            color=0x800020
        )
        lobby_emb.set_thumbnail(url="https://i.imgur.com/8N8K8S8.png")
        lobby_emb.set_footer(text="The Master watches your speed. Hesitation will draw blood.")
        lobby_emb.timestamp = datetime.now(timezone.utc)

        view = DiceLobbyView(ctx.author, rounds)
        lobby_msg = await ctx.send(embed=lobby_emb, view=view)

        # Let the lobby build for up to 120 seconds or until the host pushes start
        await view.wait()

        players = [ctx.guild.get_member(p_id) for p_id in view.participants if ctx.guild.get_member(p_id) is not None]

        if not players:
            self.active_rooms.remove(ctx.channel.id)
            return await ctx.send("❌ The experiment collapsed due to a complete lack of experimental material.")

        await ctx.send(f"🚨 **THE INJECTOR CLAMPS DOWN.** The arena is sealed with {len(players)} assets inside. Beginning the trials...")
        await asyncio.sleep(2)

        # Track active game loop
        for round_num in range(1, rounds + 1):
            round_emb = discord.Embed(
                title=f"⛓️ FLESH ROULETTE: ROUND {round_num} OF {rounds}",
                description="The layout shifting sequence initiates. The engine is picking a victim at random...",
                color=0xFF4500
            )
            await ctx.send(embed=round_emb)
            await asyncio.sleep(3)

            # FIXED: Instead of rolling systematically for everyone, pick one random participant per round
            player = random.choice(players)

            # Update total games profile
            self.update_user_stat(player.id, "games_played")

            turn_emb = discord.Embed(
                title=f"🎯 RANDOM SELECTION EYE OBSERVES: {player.display_name.upper()}",
                description=f"You have been selected by the engine, {player.mention}.\n\nYou have exactly **5 minutes** to click the dashboard below, deploy your roll, and execute the outcome.",
                color=0x9400D3
            )
            turn_emb.set_thumbnail(url=player.display_avatar.url)
            turn_emb.set_footer(text="The countdown clock is active...")

            turn_view = DiceTurnView(player)
            turn_msg = await ctx.send(embed=turn_emb, view=turn_view)

            try:
                # Strict 5-minute timeout window mapping (300.0 seconds)
                await asyncio.wait_for(turn_view.rolled.wait(), timeout=300.0)
                
                # Core random roll logic mapped seamlessly across all 36 values
                rolled_num = random.randint(1, 36)
                dare = DICE_DARES[rolled_num]

                # Save highest roll profile
                with self.get_db_connection() as conn:
                    conn.execute("INSERT OR IGNORE INTO dice_stats (user_id) VALUES (?)", (player.id,))
                    conn.execute("UPDATE dice_stats SET highest_roll = MAX(highest_roll, ?) WHERE user_id = ?", (rolled_num, player.id))
                    conn.commit()
                conn.close()

                self.update_user_stat(player.id, "dares_completed")

                res_emb = discord.Embed(
                    title=f"🎲 VALUE ENGAGED: [{rolled_num}] — {dare.get('action', dare.get('name'))}",
                    description=f"{player.mention} rolled a **{rolled_num}** on the cyber-die!\n\n**🎯 ASSIGNED DECREE (You have 5 minutes to complete this):**\n*{dare['desc']}*",
                    color=0x00FF00
                )
                res_emb.set_thumbnail(url="https://i.imgur.com/8N8K8S8.png")
                await ctx.send(embed=res_emb)

                # Trigger VOYEUR Logging update - Synchronized directly via main core modules mapping
                main_mod = sys.modules['__main__']
                audit_channel = self.bot.get_channel(AUDIT_CHANNEL_ID)
                if audit_channel:
                    log_emb = main_mod.fiery_embed("🕵️ VOYEUR FLESH ROULETTE REPORT", f"An event was triggered in the dice sector.")
                    log_emb.add_field(name="Subject", value=player.mention, inline=True)
                    log_emb.add_field(name="Roll Value", value=f"`[{rolled_num}]`", inline=True)
                    log_emb.description = f"🔞 **VOYEUR ACTION LOG:** {player.display_name} evaluated outcome {rolled_num}: {dare['desc']}"
                    log_emb.timestamp = datetime.now(timezone.utc)
                    await audit_channel.send(embed=log_emb)

            except asyncio.TimeoutError:
                turn_view.stop()
                self.update_user_stat(player.id, "chickens_out")
                
                fail_emb = discord.Embed(
                    title="🚨 TIME RUNOUT: CRITICAL COWARDICE DETECTED",
                    description=f"{player.mention} failed to execute or roll within the 5-minute limit window.\n\nThey have been logged as a **Chicken Out** and suffer extreme community shame.",
                    color=0xFF0000
                )
                await ctx.send(embed=fail_emb)

            # Wait 5 seconds before initiating the next random draw cycle
            await asyncio.sleep(5)

        self.active_rooms.remove(ctx.channel.id)
        end_emb = discord.Embed(
            title="🏁 THE ROULETTE EXPERIMENT HAS RECONVENED",
            description="The boundaries of the circle open up. The participating survivors can return to their containment fields.",
            color=0x800020
        )
        await ctx.send(embed=end_emb)

    @commands.command(name="dicestats")
    async def view_dice_analytics(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        
        with self.get_db_connection() as conn:
            row = conn.execute("SELECT games_played, dares_completed, chickens_out, highest_roll FROM dice_stats WHERE user_id = ?", (target.id,)).fetchone()
        conn.close()

        if not row:
            return await ctx.send(embed=discord.Embed(
                title=f"📊 DATA EXPANSION: EMPTY MATRIX", 
                description=f"{target.mention} has not set foot inside the Roulette matrix yet.", 
                color=0x808080
            ))

        total_games = row['games_played']
        completed = row['dares_completed']
        chickens = row['chickens_out']
        highest = row['highest_roll']

        compliance_rate = int((completed / total_games) * 100) if total_games > 0 else 0

        stat_emb = discord.Embed(title=f"📊 CORE PROFILE METRICS: {target.display_name.upper()}", color=0x00FFFF)
        stat_emb.set_toggle = True
        stat_emb.set_thumbnail(url=target.display_avatar.url)
        
        analytics_text = (
            f"🎲 **Experiments Processed:** `{total_games}`\n"
            f"✅ **Dares Welcomed:** `{completed}`\n"
            f"🐔 **Chickens / Timeouts:** `{chickens}`\n"
            f"📈 **Highest Destiny Roll:** `[{highest}/36]`\n\n"
            f"⚡ **Submission Compliance Index:** `{compliance_rate}%`"
        )
        stat_emb.description = analytics_text
        stat_emb.set_footer(text="Every action is indexed. Every submission is recorded.")
        await ctx.send(embed=stat_emb)

async def setup(bot):
    await bot.add_cog(DiceGame(bot))
