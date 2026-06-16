# FIX: Python 3.13 compatibility shim for audioop
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

# THE CYBER-DUNGEON DICE DARES - EXPANDED TO 36 CYBER-DECREES
DICE_DARES = {
    1: {"action": "FLASH", "desc": "Expose your assets to the gallery immediately or pay the price."},
    2: {"action": "COMMAND FLASH", "desc": "Pick another participant. They must flash for your amusement."},
    3: {"action": "MUTUAL BINDING", "desc": "Select a partner. Both of you must perform a flash execution simultaneously."},
    4: {"name": "The Whipping Post", "desc": "Receive a stinging penalty. You are locked out from earning bonuses on your next work command."},
    5: {"name": "Voyeur's Tithe", "desc": "Deduct 10% of your current Flames balance and disperse it evenly to the other players in the lobby."},
    6: {"name": "The Master's Pass", "desc": "APEX ROLL. You dodge all penalties this round and siphon 5,000 Flames from the player with the highest balance."},
    7: {"action": "SURRENDER CHAINS", "desc": "Change your nickname to 'The Master's Pet' for the next 24 hours."},
    8: {"action": "SILENT SUBMISSION", "desc": "You are forbidden from typing in public chat channels for the next 10 minutes."},
    9: {"action": "PIMP ASSIGNMENT", "desc": "Select a player. You must pay them a contract fee of 2,500 Flames from your savings account."},
    10: {"action": "ROULETTE RE-ROLL", "desc": "The energy shifts. You must immediately roll the hyper-dice a second time and accept both penalties."},
    11: {"action": "KNEEL AND BEG", "desc": "Use the !beg command right now and dedicate the output completely to the active host."},
    12: {"action": "RED DISTRICT DEBT", "desc": "Your body belongs to the house. The next item you sell only yields 25% value instead of 50%."},
    13: {"action": "VELVET SHACKLES", "desc": "Choose another participant. Both of your profiles are locked as allies for the remainder of this game."},
    14: {"action": "LEATHER STRIKE", "desc": "The whip cracks. Lose 1,500 Flames immediately into the arena void."},
    15: {"action": "EXHIBITIONIST GLORY", "desc": "Post your most creative digital card asset or favorite emoji structure in the boutique chat."},
    16: {"action": "AVATAR RESTRAINT", "desc": "Change your Discord avatar design context or display status to feature chains for 1 hour."},
    17: {"action": "SPOUSE CHASTITY", "desc": "If you have a bound partner, transfer 10% of your wallet directly to their grid as a token of ownership."},
    18: {"action": "GLITCH MATRIX", "desc": "Randomly select any online user. You must tag them and confess your deepest submission state."},
    19: {"action": "TITAN CHICKEN", "desc": "Your timer for all standard commands is doubled for the next 30 minutes due to exhaustion."},
    20: {"action": "SOVEREIGN INVERSION", "desc": "The lowest-scoring player in the lobby siphons 3,000 Flames directly from your account balances."},
    21: {"action": "BLINDFOLD PROTOCOL", "desc": "Turn off your custom embedded fonts or interface reactions for the next round of play."},
    22: {"action": "BALL GAG COOLDOWN", "desc": "Your next daily reward is cut completely in half by the off-world routers."},
    23: {"action": "SPIKED INJECTION", "desc": "The arena toxins burn. Lose 50 XP from your level progression matrix immediately."},
    24: {"action": "CROWNED EXECUTION", "desc": "Declare the player to your left as your superior dominant entity for the remainder of this match."},
    25: {"action": "SHADOW SHIFT", "desc": "Swap your active position in the upcoming round turn matrix with the host of the game loop."},
    26: {"action": "SINFUL DRAIN", "desc": "All assets currently tracked inside your private vault lose 1% combat weighting for the hour."},
    27: {"action": "ABYSSAL CONTRACT", "desc": "You must commit to playing the next two matches of Flesh Roulette without dropping out."},
    28: {"action": "MOLTEN BRAND", "desc": "The brand is applied. Your profile receives a temporary restriction on luxury item acquisition."},
    29: {"action": "VOIDS PLEASURE", "desc": "Receive a wave of sensory overflow. Gain 1,000 baseline Flames directly from the engine reserves."},
    30: {"action": "NEON OVERDRIVE", "desc": "Force Peak Heat variables for the next turn loop, making everyone else's rolls more dangerous."},
    31: {"action": "DOMINION FORFEIT", "desc": "Relinquish your highest-ranking inventory tier item visibility for the duration of the cycle."},
    32: {"action": "KRAKEN GRIP", "desc": "You are anchored. You cannot exit this lobby under any circumstance until all rounds terminate."},
    33: {"action": "ETERNAL FAVORITE", "desc": "The Master targets you with a blessing. Gain a permanent +1% compliance rating adjustment."},
    34: {"action": "SAPPHIRE KISS", "desc": "Choose a player to pimp out. Both of you instantly receive 500 safety Flames from the pool."},
    35: {"action": "CHAOS REVERSAL", "desc": "Swap the execution parameters of Roll 1 with Roll 6 for your current position profile."},
    36: {"action": "ABSOLUTE NULLIFICATION", "desc": "SUPREME ROLL. Wipe away all previous penalties incurred during this match and claim apex immunity."}
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
        super().__init__(timeout=40)
        self.active_player = active_player
        self.rolled = asyncio.Event()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.active_player.id:
            await interaction.response.send_message("It is not your turn to roll the dice of fate.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="ROLL DICE (40s)", style=discord.ButtonStyle.primary, emoji="🎲")
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

    @commands.command(name="dice")
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
                description="The layout shifting sequence initiates. All players must roll or suffer automatic failure.",
                color=0xFF4500
            )
            await ctx.send(embed=round_emb)
            await asyncio.sleep(2)

            for player in players:
                # Update total games profile
                self.update_user_stat(player.id, "games_played")

                turn_emb = discord.Embed(
                    title=f"👁️ CURRENT ASSET SPOTLIGHT: {player.display_name.upper()}",
                    description=f"Your execution window has unlocked, {player.mention}.\n\nYou have exactly **40 seconds** to click the dashboard below and deploy your variable roll.",
                    color=0x9400D3
                )
                turn_emb.set_thumbnail(url=player.display_avatar.url)
                turn_emb.set_footer(text="Tick... Tock...")

                turn_view = DiceTurnView(player)
                turn_msg = await ctx.send(embed=turn_emb, view=turn_view)

                try:
                    # Strict countdown check
                    await asyncio.wait_for(turn_view.rolled.wait(), timeout=40.0)
                    
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
                        description=f"{player.mention} rolled a **{rolled_num}** on the cyber-die!\n\n**🎯 ASSIGNED DECREE:**\n*{dare['desc']}*",
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
                        description=f"{player.mention} froze under the weight of the pressure and let their countdown hit absolute zero.\n\nThey have been logged as a **Chicken Out** and suffer extreme community shame.",
                        color=0xFF0000
                    )
                    await ctx.send(embed=fail_emb)

                await asyncio.sleep(4)

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
        stat_emb.set_thumbnail(url=target.display_avatar.url)
        
        analytics_text = (
            f"🎲 **Experiments Processed:** `{total_games}`\n"
            f"✅ **Dares Welcomed:** `{completed}`\n"
            f"🐔 **Chickens / Timeouts:** `{chickens}`\n"
            f"📈 **Highest Destiny Roll:** `[{highest}/36]`\n\n"
            f"⚡ **Submission Compliance Index:** `{compliance_rate}%`"
        )
        stat_emb.description = analytics_text
        stat_emb.set_toggle = True # Added functional anchor link for future expansion hooks
        stat_emb.set_footer(text="Every action is indexed. Every submission is recorded.")
        await ctx.send(embed=stat_emb)

async def setup(bot):
    await bot.add_cog(DiceGame(bot))
