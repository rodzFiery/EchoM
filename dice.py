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

# THE CYBER-DUNGEON DICE DARES - FOCUSING EXCLUSIVELY ON YOUR CUSTOM 22 DIRECTIVES
DICE_DARES = {
    1: {"action": "FLASH", "desc": "Expose your designated assets to the live gallery immediately or suffer total failure."},
    2: {"action": "FLASH WITH A FRIEND", "desc": "Coordinate with an ally in the server to drop coverage and deploy a shared flash revelation."},
    3: {"action": "PICK SOMEONE TO FLASH", "desc": "Select any asset inside this current lobby. They must execute a live flash for your amusement."},
    4: {"action": "FLASH IN BLACK AND WHITE", "desc": "Submit a complete live exposure utilizing a deep monochrome or high-contrast black and white visual filter."},
    5: {"action": "MIRROR FLASH", "desc": "Capture your reflection. Execute a full live asset flash framed completely through a mirror surface."},
    6: {"action": "SILHOUETTE FLASH", "desc": "Kill the lights. Position a bright light behind you to flash your outline as a pure, dramatic silhouette shadow."},
    7: {"action": "NAUGHTY VOICE NOTE", "desc": "Record and upload a live microphone voice note to the chat feed using your most seductive, teasing bedroom tone."},
    8: {"action": "FLASH WITH A SPECIFIC COLOR", "desc": "Perform a live flash while wearing or prominently holding an object of a vibrant color specified by the host."},
    9: {"action": "LET THE CHAT PICK WHAT YOU FLASH", "desc": "The room gains dominance. Let the public chat feed vote on exactly which asset target you must drop coverage on."},
    10: {"action": "DOUBLE TROUBLE FLASH WITH A PARTNER", "desc": "Bind fates with a partner right now. Both of you must post a simultaneous high-impact flash execution."},
    11: {"action": "SHARE A SECRET KINK", "desc": "Confess an unspoken, underground fetish or desire you keep locked deep inside your psychological matrix."},
    12: {"action": "TELL US A FANTASY", "desc": "Describe your ultimate, unfulfilled erotic scenario in vivid detail for the gallery to read."},
    13: {"action": "SHARE THE WEIRDEST PLACE YOU HAVE DONE IT", "desc": "Reveal the most unconventional, high-risk, or bizarre public location where you have engaged in a physical encounter."},
    14: {"action": "CONFESS YOUR BIGGEST TURN-ON", "desc": "Expose the single most powerful trigger, action, or element that instantly drives your desire into overdrive."},
    15: {"action": "ADMIT YOUR BIGGEST TURN-OFF", "declare": "Declare the ultimate dealbreaker—the one specific action or trait that completely kills your mood without exception."},
    16: {"action": "DESCRIBE YOUR FAVORITE POSITION", "desc": "Provide a detailed breakdown of the exact physical configuration in bed that brings you maximum satisfaction."},
    17: {"action": "REVEAL EMBARRASSING BED EVENT", "desc": "Uncover the most awkward, clumsy, or completely embarrassing incident that has ever interrupted your intimate moments."},
    18: {"action": "REVEAL WEIRDEST MASTURBATION PLACE", "desc": "Confess the most unusual, creative, or inappropriate location where you have ever pleasured yourself solo."},
    19: {"action": "FLASH WITH MUSIC", "desc": "Execute and capture a live flash while playing a dirty, rhythmic audio track or song clearly audible in your environment."},
    20: {"action": "FLASH A PIC IN THE MOMENT", "desc": "No pre-saved files allowed. Capture a raw, completely spontaneous live photo of your current coverage status right this second."},
    21: {"action": "FLASH YOUR FAVORITE BODY PART", "desc": "Isolate and flash the exact anatomical asset on your own body that you take the absolute most pride in possessing."},
    22: {"action": "TAG A MEMBER AND PASS YOUR DARE", "desc": "Escape clause. Tag an unsuspecting member in the server right now and force them to inherit this turn cycle's fate."},
    23: {"action": "FAST FLASH PROTOCOL", "desc": "Drop your coverings and execute a sudden, rapid-fire flash reveal that vanishes instantly."},
    24: {"action": "DUAL FLASH EXCLUSION", "desc": "Grab a friend from the lobby list; both of you must drop coverage and execute matching flash frames."},
    25: {"action": "DOMINANT SELECTION EYE", "desc": "Point your finger at any asset in the channel. Command them to deploy a live flash or face the community penalty."},
    26: {"action": "MONOCHROME FLASH SHIFT", "desc": "Strip away all color profiles. Flash the gallery using a pure noir black and white visual aesthetic."},
    27: {"action": "REVERSED MIRROR FLASH", "desc": "Frame a dual-perspective reflection flash using your closest mirror panel setup right now."},
    28: {"action": "SHADOW SILHOUETTE EXPOSURE", "desc": "Stand directly in front of a heavy backlight, leaving your asset lines completely outlined in a dark shadow flash."},
    29: {"action": "NAUGHTY AUDIO TRANSMISSION", "desc": "Deploy a 30-second voice note describing what you are currently wearing in your filthiest whispering voice."},
    30: {"action": "CHROMATIC FOCUS FLASH", "desc": "The host calls out a specific primary color tone. You must incorporate it into your immediate flash layout."},
    31: {"action": "PUBLIC DECISION REVEAL", "desc": "Surrender your choice to the chat network. They will dictate exactly what asset you are flashing this round."},
    32: {"action": "DOUBLE TROUBLE ALLIANCE", "desc": "Synchronize a combined flash profile with an active partner to double the heat variables in the sector."},
    33: {"action": "UNSPOKEN KINK CONFESSION", "desc": "Open up your core matrix settings and type out your absolute deepest, most taboo hidden kink."},
    34: {"action": "UNCENSORED BEDTIME FANTASY", "desc": "Paint a vivid mental picture for the audience describing your dream erotic playground setup."},
    35: {"action": "EXTREME LOCATION CHRONICLES", "desc": "Expose the single most reckless, high-exposure, or bizarre public location where you have ever hook up."},
    36: {"action": "CORE TURN-ON ANALYSIS", "desc": "Break down the ultimate sensory trigger or specific visual that drives your raw desire past its absolute limit."}
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

# ADDED: Separate validation controller view to suspend progress until confirmed completed or timed out
class DiceCompletionView(discord.ui.View):
    def __init__(self, active_player):
        super().__init__(timeout=300)
        self.active_player = active_player
        self.completed = asyncio.Event()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.active_player.id:
            await interaction.response.send_message("Only the assigned asset can assert execution completion parameters.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="TASK COMPLETED", style=discord.ButtonStyle.success, emoji="✅")
    async def complete_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        self.completed.set()
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

        players = []
        for p_id in view.participants:
            m_obj = ctx.guild.get_member(p_id)
            if not m_obj:
                try:
                    m_obj = await ctx.guild.fetch_member(p_id)
                except:
                    continue
            if m_obj:
                players.append(m_obj)

        if not players:
            if ctx.channel.id in self.active_rooms:
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

                res_emb = discord.Embed(
                    title=f"🎲 VALUE ENGAGED: [{rolled_num}] — {dare.get('action', dare.get('name', 'UNKNOWN'))}",
                    description=f"{player.mention} rolled a **{rolled_num}** on the cyber-die!\n\n**🎯 ASSIGNED DECREE (You have 5 minutes to complete this):**\n*{dare['desc']}*\n\n*Click the button below to confirm task completion and advance the system.*",
                    color=0x00FF00
                )
                res_emb.set_thumbnail(url="https://i.imgur.com/8N8K8S8.png")
                
                # FIXED: Present new confirmation panel view and pause execution progression chain
                comp_view = DiceCompletionView(player)
                comp_msg = await ctx.send(embed=res_emb, view=comp_view)

                try:
                    # System halts here until player clicks "TASK COMPLETED" or the remaining time hits 0
                    await asyncio.wait_for(comp_view.completed.wait(), timeout=300.0)
                    self.update_user_stat(player.id, "dares_completed")
                    
                    ok_emb = discord.Embed(
                        title="✅ DECREE RECORDED AND SECURED",
                        description=f"{player.mention} has confirmed execution within parameter constraints. Advancing matrix structure...",
                        color=0x00FF00
                    )
                    await ctx.send(embed=ok_emb)
                except asyncio.TimeoutError:
                    comp_view.stop()
                    self.update_user_stat(player.id, "chickens_out")
                    timeout_emb = discord.Embed(
                        title="🚨 DECREE VERIFICATION EXPIRED",
                        description=f"{player.mention} failed to click verification within the 5-minute performance allowance threshold. Progress marked as failure.",
                        color=0xFF0000
                    )
                    await ctx.send(timeout_emb)

                # Trigger VOYEUR Logging update - Synchronized directly via main core modules mapping
                try:
                    main_mod = sys.modules['__main__']
                    audit_channel = self.bot.get_channel(AUDIT_CHANNEL_ID)
                    if audit_channel:
                        log_emb = main_mod.fiery_embed("🕵️ VOYEUR FLESH ROULETTE REPORT", f"An event was triggered in the dice sector.")
                        log_emb.add_field(name="Subject", value=player.mention, inline=True)
                        log_emb.add_field(name="Roll Value", value=f"`[{rolled_num}]`", inline=True)
                        log_emb.description = f"🔞 **VOYEUR ACTION LOG:** {player.display_name} evaluated outcome {rolled_num}: {dare['desc']}"
                        log_emb.timestamp = datetime.now(timezone.utc)
                        await audit_channel.send(embed=log_emb)
                except:
                    pass

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

        if ctx.channel.id in self.active_rooms:
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
        stat_emb.set_footer(text="Every action is indexed. Every submission is recorded.")
        await ctx.send(embed=stat_emb)

async def setup(bot):
    await bot.add_cog(DiceGame(bot))
