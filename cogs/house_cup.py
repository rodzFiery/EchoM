import asyncio
import json
import os
import random
import time
from typing import Dict, List, Optional
import discord
from discord.ext import commands

# ==========================================
# CONSTANTS & CONFIGURATION
# ==========================================
DATA_FILE_PATH = "house_cup_data.json"

HOUSES = {
    "Gryffindor": {"emoji": "🦁", "color": 0x7F0909, "buff": "10% chance to survive fatal hits"},
    "Slytherin": {"emoji": "🐍", "color": 0x1A472A, "buff": "10% chance to deal critical damage"},
    "Ravenclaw": {"emoji": "🦅", "color": 0x0E1A40, "buff": "10% chance to dodge curses"},
    "Hufflepuff": {"emoji": "🦡", "color": 0xECB939, "buff": "10% bonus max health"}
}

ACTION_TICK_SECONDS = 15
RESURRECTION_COST = 150

FLASH_PENALTIES = [
    "Flash VC or DMs within 2 minutes!",
    "Post a spicy teaser photo in the NSFW channel!",
    "Send an explicit voice note to the winning House!",
    "Perform a 10-second flash challenge on camera!",
    "Show your favorite tattoo/secret spot to the server!"
]

LEXICON_CLASHES = [
    "{attacker} overpowered {defender} with a sudden Expelliarmus, forcing them off the duel podium!",
    "{attacker} caught {defender} off-guard with a swift Stupefy spell!",
    "{attacker} cast an icy Petrificus Totalus, locking {defender} in place!",
    "{attacker} disarmed {defender} in a brilliant flash of magical dueling!",
    "{attacker} unleashed a scorching Incendio wave that sent {defender} tumbling back!",
    "{attacker} read {defender}'s spell trajectory perfectly and countered with a crushing blow!"
]

# Database/Economy Hook Integration
def modify_user_balance(bot: commands.Bot, user_id: int, amount: int) -> bool:
    try:
        if hasattr(bot, 'update_user_stats_async'):
            asyncio.create_task(bot.update_user_stats_async(user_id, amount=amount, source="HouseCup Spectator"))
            return True
    except Exception:
        pass
    return True


# ==========================================
# GAME ENGINE DATA MODELS
# ==========================================
class WizardPlayer:
    def __init__(self, user: discord.User | discord.Member, house: str):
        self.user = user
        self.house = house
        self.is_alive = True
        self.kills = 0
        self.points_earned = 0
        self.death_cause = ""

class ServerGameState:
    def __init__(self, guild_id: int, channel_id: int, server_game_num: int, global_game_num: int):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.server_game_num = server_game_num
        self.global_game_num = global_game_num
        self.is_lobby_open = True
        self.is_running = False
        self.players: Dict[int, WizardPlayer] = {}
        self.house_points: Dict[str, int] = {h: 0 for h in HOUSES}
        self.round_number = 0
        self.eliminated_recap: List[dict] = []  # Stores data for final recap board
        self.winning_house: Optional[str] = None
        self.triwizard_champ: Optional[WizardPlayer] = None
        self.game_task: Optional[asyncio.Task] = None
        self.lobby_message: Optional[discord.Message] = None

    def get_balanced_house(self) -> str:
        house_counts = {h: 0 for h in HOUSES}
        for player in self.players.values():
            house_counts[player.house] += 1
        min_count = min(house_counts.values())
        available_houses = [h for h, count in house_counts.items() if count == min_count]
        return random.choice(available_houses)

    def get_leader_player(self) -> Optional[WizardPlayer]:
        alive = [p for p in self.players.values() if p.is_alive]
        if not alive:
            return None
        return max(alive, key=lambda p: (p.kills, p.points_earned))


# ==========================================
# DISCORD UI COMPONENTS (PERSISTENT VIEWS)
# ==========================================
class LobbyView(discord.ui.View):
    def __init__(self, cog: "HouseCupCog", guild_id: int):
        super().__init__(timeout=None)  # Infinite lifetime - never expires
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(
        label="Enter the Great Hall", 
        style=discord.ButtonStyle.primary, 
        emoji="🧹", 
        custom_id="housecup:lobby:join"
    )
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        game = self.cog.get_game(interaction.guild_id)
        
        if not game or not game.is_lobby_open:
            await interaction.followup.send("❌ No active lobby in this server or game already started!", ephemeral=True)
            return

        if interaction.user.id in game.players:
            player = game.players[interaction.user.id]
            house_data = HOUSES[player.house]
            await interaction.followup.send(
                f"You are already sorted into **{player.house}** {house_data['emoji']}!", 
                ephemeral=True
            )
            return

        house = game.get_balanced_house()
        game.players[interaction.user.id] = WizardPlayer(interaction.user, house)
        house_data = HOUSES[house]

        await interaction.followup.send(
            f"✨ The Sorting Hat placed you in **{house}** {house_data['emoji']}!\n*Trait:* {house_data['buff']}",
            ephemeral=True
        )

        if interaction.message:
            embed = self.cog.build_lobby_embed(game)
            await interaction.message.edit(embed=embed)

    @discord.ui.button(
        label="Start Game", 
        style=discord.ButtonStyle.success, 
        emoji="⚔️", 
        custom_id="housecup:lobby:start"
    )
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        game = self.cog.get_game(interaction.guild_id)

        if not game or not game.is_lobby_open:
            await interaction.followup.send("❌ No active lobby found to start.", ephemeral=True)
            return

        if len(game.players) < 2:
            await interaction.followup.send("❌ Need at least 2 players sorted to start!", ephemeral=True)
            return

        game.is_lobby_open = False
        game.is_running = True
        game.game_task = asyncio.create_task(self.cog.run_battle_loop(interaction.guild_id, interaction.channel))
        await interaction.channel.send(f"⚔️ **The Great Hall doors are locked! Match #{game.server_game_num} Has Begun!**")

    @discord.ui.button(
        label="Repost Lobby", 
        style=discord.ButtonStyle.secondary, 
        emoji="🔄", 
        custom_id="housecup:lobby:repost"
    )
    async def repost_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        game = self.cog.get_game(interaction.guild_id)

        if not game or not game.is_lobby_open:
            await interaction.followup.send("❌ No open lobby found in this server!", ephemeral=True)
            return

        if game.lobby_message:
            try:
                await game.lobby_message.delete()
            except Exception:
                pass

        embed = self.cog.build_lobby_embed(game)
        view = LobbyView(self.cog, interaction.guild_id)
        new_msg = await interaction.channel.send(embed=embed, view=view)
        game.lobby_message = new_msg
        await interaction.followup.send("✅ Lobby reposted at the bottom of the channel!", ephemeral=True)


class ResurrectionView(discord.ui.View):
    def __init__(self, game: ServerGameState, dead_player: WizardPlayer, cog: "HouseCupCog"):
        super().__init__(timeout=15)
        self.game = game
        self.dead_player = dead_player
        self.cog = cog

    @discord.ui.button(label=f"Resurrect {RESURRECTION_COST}c", style=discord.ButtonStyle.danger, emoji="✨", custom_id="housecup:arena:resurrect")
    async def revive(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not modify_user_balance(self.cog.bot, interaction.user.id, -RESURRECTION_COST):
            await interaction.followup.send("❌ Insufficient coins!", ephemeral=True)
            return

        self.dead_player.is_alive = True
        await interaction.followup.send(f"✨ You revived {self.dead_player.user.mention}!", ephemeral=True)
        self.stop()


# ==========================================
# MAIN EXTENSION COG
# ==========================================
class HouseCupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: Dict[int, ServerGameState] = {}
        self.recent_finished_games: Dict[int, ServerGameState] = {}  # Retained for !leviosa targeting
        self.server_game_counts: Dict[int, int] = {}
        self.global_game_count: int = 0
        
        # Rankings Persistence Data Structures
        self.global_house_points: Dict[str, int] = {h: 0 for h in HOUSES}
        self.server_house_points: Dict[int, Dict[str, int]] = {}
        self.wizard_stats: Dict[int, Dict[str, int]] = {}  # {user_id: {"kills": X, "points": Y, "wins": Z}}

    def cog_unload(self):
        self.save_persistent_data()
        for game in self.games.values():
            if game.game_task and not game.game_task.done():
                game.game_task.cancel()

    async def cog_load(self):
        self.load_persistent_data()
        self.bot.add_view(LobbyView(self, 0))

    # ==========================================
    # JSON PERSISTENCE ENGINE (LOAD & SAVE)
    # ==========================================
    def save_persistent_data(self):
        """Saves game counters, house points, and player stats to JSON."""
        data = {
            "global_game_count": self.global_game_count,
            "server_game_counts": {str(k): v for k, v in self.server_game_counts.items()},
            "global_house_points": self.global_house_points,
            "server_house_points": {str(k): v for k, v in self.server_house_points.items()},
            "wizard_stats": {str(k): v for k, v in self.wizard_stats.items()}
        }
        try:
            with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[HouseCup Engine] Error saving data: {e}")

    def load_persistent_data(self):
        """Loads game counters, house points, and player stats from JSON on startup."""
        if not os.path.exists(DATA_FILE_PATH):
            return

        try:
            with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.global_game_count = data.get("global_game_count", 0)
            
            srv_counts = data.get("server_game_counts", {})
            self.server_game_counts = {int(k): v for k, v in srv_counts.items()}

            self.global_house_points = data.get("global_house_points", {h: 0 for h in HOUSES})

            srv_houses = data.get("server_house_points", {})
            self.server_house_points = {int(k): v for k, v in srv_houses.items()}

            w_stats = data.get("wizard_stats", {})
            self.wizard_stats = {int(k): v for k, v in w_stats.items()}
        except Exception as e:
            print(f"[HouseCup Engine] Error loading data: {e}")

    def get_game(self, guild_id: int) -> Optional[ServerGameState]:
        return self.games.get(guild_id)

    def record_wizard_stats(self, user_id: int, kills: int, points: int, win: bool = False):
        if user_id not in self.wizard_stats:
            self.wizard_stats[user_id] = {"kills": 0, "points": 0, "wins": 0}
        self.wizard_stats[user_id]["kills"] += kills
        self.wizard_stats[user_id]["points"] += points
        if win:
            self.wizard_stats[user_id]["wins"] += 1

    def build_lobby_embed(self, game: ServerGameState) -> discord.Embed:
        embed = discord.Embed(
            title="🏆 Battle for the House Cup - Sorting Lobby",
            description=(
                f"**Server Game #{game.server_game_num}** | **Global Game #{game.global_game_num}**\n\n"
                "Click **Enter the Great Hall** below to receive your House assignment!"
            ),
            color=0xECB939
        )
        house_summary = ""
        for house_name, data in HOUSES.items():
            members = [p.user.display_name for p in game.players.values() if p.house == house_name]
            house_summary += f"{data['emoji']} **{house_name}** ({len(members)}): {', '.join(members) if members else 'None'}\n"
        
        embed.add_field(name="Current House Roster", value=house_summary, inline=False)
        
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        embed.set_footer(text=f"Server Match #{game.server_game_num} • Global Match #{game.global_game_num} • Min 2 players required")
        return embed

    # ==========================================
    # COMMANDS (!housecup, !housecup rankings, !leviosa)
    # ==========================================
    @commands.group(name="housecup", invoke_without_command=True)
    @commands.guild_only()
    async def housecup(self, ctx: commands.Context):
        """Creates or manages the active House Cup game lobby."""
        guild_id = ctx.guild.id
        if guild_id in self.games and (self.games[guild_id].is_lobby_open or self.games[guild_id].is_running):
            await ctx.send("⚠️ A House Cup lobby or active game is already running in this server!")
            return

        self.server_game_counts[guild_id] = self.server_game_counts.get(guild_id, 0) + 1
        self.global_game_count += 1
        self.save_persistent_data()

        server_num = self.server_game_counts[guild_id]
        global_num = self.global_game_count

        game = ServerGameState(guild_id, ctx.channel.id, server_num, global_num)
        self.games[guild_id] = game

        embed = self.build_lobby_embed(game)
        view = LobbyView(self, guild_id)
        msg = await ctx.send(embed=embed, view=view)
        game.lobby_message = msg

    @housecup.command(name="rankings")
    @commands.guild_only()
    async def show_rankings(self, ctx: commands.Context):
        """Displays Server and Global House Cup Rankings."""
        guild_id = ctx.guild.id
        server_houses = self.server_house_points.get(guild_id, {h: 0 for h in HOUSES})

        embed = discord.Embed(
            title="🏆 HOUSE CUP LEADERBOARDS & RANKINGS",
            color=0xECB939
        )

        sorted_server_houses = sorted(server_houses.items(), key=lambda x: x[1], reverse=True)
        server_house_txt = "\n".join([f"{HOUSES[h]['emoji']} **{h}**: {pts} pts" for h, pts in sorted_server_houses])
        embed.add_field(name="🏰 Server House Standings", value=server_house_txt or "No games completed yet.", inline=False)

        sorted_global_houses = sorted(self.global_house_points.items(), key=lambda x: x[1], reverse=True)
        global_house_txt = "\n".join([f"{HOUSES[h]['emoji']} **{h}**: {pts} pts" for h, pts in sorted_global_houses])
        embed.add_field(name="🌍 Global House Standings", value=global_house_txt, inline=False)

        guild_members = [m.id for m in ctx.guild.members]
        server_wizards = {uid: stats for uid, stats in self.wizard_stats.items() if uid in guild_members}
        sorted_wizards = sorted(server_wizards.items(), key=lambda x: (x[1]["points"], x[1]["kills"]), reverse=True)[:5]
        
        wizard_txt = ""
        for rank, (uid, stats) in enumerate(sorted_wizards, start=1):
            user = self.bot.get_user(uid)
            name = user.display_name if user else f"Wizard {uid}"
            wizard_txt += f"`#{rank}` **{name}** — {stats['points']} pts | {stats['kills']} kills | {stats['wins']} wins\n"

        embed.add_field(name="🧙 Top Server Wizards", value=wizard_txt or "No wizard data available yet.", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="leviosa")
    @commands.guild_only()
    async def leviosa(self, ctx: commands.Context, target: discord.Member):
        """Allows winning wizards to cast Wingardium Leviosa and force a target to flash."""
        guild_id = ctx.guild.id
        finished_game = self.recent_finished_games.get(guild_id)

        if not finished_game:
            await ctx.send("❌ No recent match finished where you can assign flash forfeits!")
            return

        winner_player = finished_game.players.get(ctx.author.id)
        if not winner_player:
            await ctx.send("❌ You did not participate in the most recent match!")
            return

        is_champ = finished_game.triwizard_champ and finished_game.triwizard_champ.user.id == ctx.author.id
        is_winning_house = winner_player.house == finished_game.winning_house

        if not (is_champ or is_winning_house):
            await ctx.send("❌ Only members of the winning House or the Triwizard Champion can cast !leviosa!")
            return

        if target.id == ctx.author.id:
            await ctx.send("❌ You cannot target yourself!")
            return

        target_player = finished_game.players.get(target.id)
        if target_player and target_player.house == finished_game.winning_house:
            await ctx.send("❌ You cannot force your own winning House teammate to flash!")
            return

        penalty = random.choice(FLASH_PENALTIES)
        embed = discord.Embed(
            title="✨ WINGARDIUM LEVIOSA FORFEIT CAST!",
            description=(
                f"🪄 **{ctx.author.display_name}** levitated **{target.mention}**!\n\n"
                f"⚡ **ASSIGNED FORFEIT:** {penalty}"
            ),
            color=0xFF0055
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    # ==========================================
    # HANGRY GAMES-STYLE DIRECT 1V1 DUEL ENGINE
    # ==========================================
    async def run_battle_loop(self, guild_id: int, channel: discord.TextChannel):
        game = self.games.get(guild_id)
        if not game:
            return

        while game.is_running:
            game.round_number += 1
            await asyncio.sleep(ACTION_TICK_SECONDS)

            alive_players = [p for p in game.players.values() if p.is_alive]
            surviving_houses = {p.house for p in alive_players}

            # Check End Conditions
            if len(alive_players) <= 1 or len(surviving_houses) <= 1:
                game.is_running = False
                await self.conclude_game(game, channel)
                break

            attacker = random.choice(alive_players)
            potential_defenders = [p for p in alive_players if p.house != attacker.house]
            
            if not potential_defenders:
                potential_defenders = [p for p in alive_players if p.user.id != attacker.user.id]
            
            if not potential_defenders:
                continue
                
            defender = random.choice(potential_defenders)

            is_eliminated = True
            if defender.house == "Gryffindor" and random.random() < 0.10:
                is_eliminated = False

            sentence_template = random.choice(LEXICON_CLASHES)
            narrative = sentence_template.format(
                attacker=f"**{attacker.user.display_name}**",
                defender=f"**{defender.user.display_name}**"
            )

            att_icon = HOUSES[attacker.house]["emoji"]
            def_icon = HOUSES[defender.house]["emoji"]

            embed = discord.Embed(
                title=f"⚔️ 1V1 DUEL — Round {game.round_number}",
                description=(
                    f"{att_icon} **{attacker.user.display_name}** ({attacker.house}) **VS** "
                    f"{def_icon} **{defender.user.display_name}** ({defender.house})\n\n"
                    f"{narrative}"
                ),
                color=HOUSES[attacker.house]["color"]
            )

            embed.set_thumbnail(url=attacker.user.display_avatar.url)
            embed.set_image(url=defender.user.display_avatar.url)

            if is_eliminated:
                defender.is_alive = False
                attacker.kills += 1
                kill_pts = 50
                game.house_points[attacker.house] += kill_pts
                attacker.points_earned += kill_pts

                defender.death_cause = f"Defeated in a 1v1 duel by {attacker.user.display_name}"

                embed.add_field(
                    name="💀 KNOCKOUT!",
                    value=f"**{defender.user.display_name}** was eliminated! **+{kill_pts} Pts** awarded to **{attacker.house}**!",
                    inline=False
                )

                res_view = ResurrectionView(game, defender, self)
                asyncio.create_task(channel.send(
                    f"✨ **{defender.user.display_name}** has fallen! 15s Rescue window open:",
                    view=res_view
                ))
            else:
                pts = 15
                game.house_points[attacker.house] += pts
                attacker.points_earned += pts
                embed.add_field(
                    name="🦁 SURVIVED!",
                    value=f"**{defender.user.display_name}** narrowly survived the clash! **+{pts} Pts** awarded to **{attacker.house}**!",
                    inline=False
                )

            leaderboard = " | ".join([f"{HOUSES[h]['emoji']} {h}: {pts}pt" for h, pts in game.house_points.items()])
            embed.set_footer(text=f"Leaderboard: {leaderboard}")

            await channel.send(embed=embed)

        if guild_id in self.games:
            self.recent_finished_games[guild_id] = game
            del self.games[guild_id]

    async def conclude_game(self, game: ServerGameState, channel: discord.TextChannel):
        guild_id = channel.guild.id
        winning_house = max(game.house_points, key=game.house_points.get)
        survivors = [p for p in game.players.values() if p.is_alive]
        triwizard_champ = survivors[0] if survivors else None

        game.winning_house = winning_house
        game.triwizard_champ = triwizard_champ

        # Update Server & Global Persistent Rankings
        if guild_id not in self.server_house_points:
            self.server_house_points[guild_id] = {h: 0 for h in HOUSES}

        for h_name, h_pts in game.house_points.items():
            self.server_house_points[guild_id][h_name] += h_pts
            self.global_house_points[h_name] += h_pts

        for p in game.players.values():
            is_win = (triwizard_champ and p.user.id == triwizard_champ.user.id)
            self.record_wizard_stats(p.user.id, p.kills, p.points_earned, win=is_win)

        # Write all accumulated scores to permanent local storage
        self.save_persistent_data()

        # 1. Main Winner Embed
        embed = discord.Embed(
            title="🏆 THE HOUSE CUP HAS CONCLUDED! 🏆",
            description=(
                f"Congratulations to **{winning_house}** {HOUSES[winning_house]['emoji']} for winning the House Cup!\n\n"
                f"🪄 **Winners command:** Type `!leviosa @user` to pick someone to perform a Flash Forfeit!"
            ),
            color=HOUSES[winning_house]["color"]
        )
        embed.add_field(
            name="🥇 Triwizard Champion (Last Standing)", 
            value=triwizard_champ.user.display_name if triwizard_champ else "None", 
            inline=True
        )
        embed.add_field(name="📊 Winning House Score", value=f"{game.house_points[winning_house]} Points", inline=True)
        
        if triwizard_champ:
            embed.set_thumbnail(url=triwizard_champ.user.display_avatar.url)

        await channel.send(embed=embed)

        # 2. Random House Flash Forfeit Selection
        non_winning_houses = [h for h in HOUSES if h != winning_house]
        punished_house = random.choice(non_winning_houses)
        punished_members = [p for p in game.players.values() if p.house == punished_house]

        recap_embed = discord.Embed(
            title="⚡ END OF GAME RECAP & RANDOM HOUSE FLASH FORFEIT",
            description=f"The Sorting Hat selected **{punished_house}** {HOUSES[punished_house]['emoji']} for a group Flash Penalty!",
            color=0xFF0055
        )

        if punished_members:
            for p in punished_members:
                penalty = random.choice(FLASH_PENALTIES)
                recap_embed.add_field(
                    name=f"⚡ {p.user.display_name} ({p.house})",
                    value=f"• **Assigned Forfeit:** {penalty}",
                    inline=False
                )
        else:
            recap_embed.add_field(
                name=f"{HOUSES[punished_house]['emoji']} {punished_house}",
                value="No wizards were sorted into this house during the match!",
                inline=False
            )

        await channel.send(embed=recap_embed)


# Setup Hook for Extension Loading
async def setup(bot: commands.Bot):
    await bot.add_cog(HouseCupCog(bot))
