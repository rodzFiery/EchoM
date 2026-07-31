import asyncio
import random
import time
from typing import Dict, List, Optional
import discord
from discord.ext import commands

# ==========================================
# CONSTANTS & CONFIGURATION
# ==========================================
HOUSES = {
    "Gryffindor": {"emoji": "🦁", "color": 0x7F0909, "buff": "10% chance to survive fatal hits"},
    "Slytherin": {"emoji": "🐍", "color": 0x1A472A, "buff": "10% chance to deal critical damage"},
    "Ravenclaw": {"emoji": "🦅", "color": 0x0E1A40, "buff": "10% chance to dodge curses"},
    "Hufflepuff": {"emoji": "🦡", "color": 0xECB939, "buff": "10% bonus max health"}
}

ACTION_TICK_SECONDS = 15
INITIAL_HEALTH = 100
RESURRECTION_COST = 150

FLASH_PENALTIES = [
    "Flash VC or DMs within 2 minutes!",
    "Post a spicy teaser photo in the NSFW channel!",
    "Send an explicit voice note to the winning House!",
    "Perform a 10-second flash challenge on camera!",
    "Show your favorite tattoo/secret spot to the server!"
]

DUEL_SPELLS = [
    {"name": "Expelliarmus", "min_dmg": 15, "max_dmg": 25, "text": "disarmed and knocked back"},
    {"name": "Stupefy", "min_dmg": 20, "max_dmg": 30, "text": "hit with a powerful stunning spell"},
    {"name": "Sectumsempra", "min_dmg": 25, "max_dmg": 40, "text": "slashed with dark magic"},
    {"name": "Incendio", "min_dmg": 18, "max_dmg": 32, "text": "blasted with a wave of magical fire"},
    {"name": "Avada Kedavra", "min_dmg": 999, "max_dmg": 999, "text": "struck down with the Unforgivable Curse"}
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
        self.hp = INITIAL_HEALTH + (10 if house == "Hufflepuff" else 0)
        self.max_hp = self.hp
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
        return max(alive, key=lambda p: (p.hp, p.kills))


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
        self.dead_player.hp = int(self.dead_player.max_hp * 0.3)
        await interaction.followup.send(f"✨ You revived {self.dead_player.user.mention}!", ephemeral=True)
        self.stop()


# ==========================================
# MAIN EXTENSION COG
# ==========================================
class HouseCupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: Dict[int, ServerGameState] = {}
        self.server_game_counts: Dict[int, int] = {}
        self.global_game_count: int = 0
        
        # Rankings Persistence Data Structures
        self.global_house_points: Dict[str, int] = {h: 0 for h in HOUSES}
        self.server_house_points: Dict[int, Dict[str, int]] = {}
        self.wizard_stats: Dict[int, Dict[str, int]] = {}  # {user_id: {"kills": X, "points": Y, "wins": Z}}

    def cog_unload(self):
        for game in self.games.values():
            if game.game_task and not game.game_task.done():
                game.game_task.cancel()

    async def cog_load(self):
        self.bot.add_view(LobbyView(self, 0))

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
        
        # Display Bot's Avatar in the Lobby
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        embed.set_footer(text=f"Server Match #{game.server_game_num} • Global Match #{game.global_game_num} • Min 2 players required")
        return embed

    # ==========================================
    # COMMANDS (!housecup & !housecup rankings)
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

        # 1. Server House Rankings
        sorted_server_houses = sorted(server_houses.items(), key=lambda x: x[1], reverse=True)
        server_house_txt = "\n".join([f"{HOUSES[h]['emoji']} **{h}**: {pts} pts" for h, pts in sorted_server_houses])
        embed.add_field(name="🏰 Server House Standings", value=server_house_txt or "No games completed yet.", inline=False)

        # 2. Global House Rankings
        sorted_global_houses = sorted(self.global_house_points.items(), key=lambda x: x[1], reverse=True)
        global_house_txt = "\n".join([f"{HOUSES[h]['emoji']} **{h}**: {pts} pts" for h, pts in sorted_global_houses])
        embed.add_field(name="🌍 Global House Standings", value=global_house_txt, inline=False)

        # 3. Top Server Wizards
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

    # ==========================================
    # HANGRY GAMES-STYLE 1V1 DUEL BATTLE ENGINE
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

            # Pick 2 Random Wizards for a HangryGames 1v1 Clash
            attacker = random.choice(alive_players)
            potential_defenders = [p for p in alive_players if p.user.id != attacker.user.id]
            if not potential_defenders:
                continue
            defender = random.choice(potential_defenders)

            # Pick Random Spell / Encounter
            spell = random.choice(DUEL_SPELLS)
            is_unforgivable = spell["name"] == "Avada Kedavra"
            
            if is_unforgivable and random.random() > 0.15:
                # 85% chance Unforgivable Curse misses
                spell = DUEL_SPELLS[1]  # Fallback to Stupefy

            damage = random.randint(spell["min_dmg"], spell["max_dmg"])

            # Trait Checks
            if attacker.house == "Slytherin" and random.random() < 0.10:
                damage = int(damage * 1.5)

            # Resolve Combat Hit
            defender.hp -= damage
            pts_earned = 15
            game.house_points[attacker.house] += pts_earned
            attacker.points_earned += pts_earned

            is_fatal = defender.hp <= 0

            # Gryffindor Bravery Fatal Survival
            if is_fatal and defender.house == "Gryffindor" and random.random() < 0.10:
                defender.hp = 1
                is_fatal = False

            # Build HangryGames Style Dual Avatar Duel Embed
            att_icon = HOUSES[attacker.house]["emoji"]
            def_icon = HOUSES[defender.house]["emoji"]

            embed = discord.Embed(
                title=f"⚔️ DUEL CLASH — Round {game.round_number}",
                description=(
                    f"{att_icon} **{attacker.user.display_name}** ({attacker.house}) **VS** "
                    f"{def_icon} **{defender.user.display_name}** ({defender.house})\n\n"
                    f"✨ **{attacker.user.display_name}** cast **{spell['name']}**!\n"
                    f"💥 **{defender.user.display_name}** was {spell['text']} for **{damage} HP**!"
                ),
                color=HOUSES[attacker.house]["color"]
            )

            # Dual Profile Picture Display (Attacker Main Thumbnail, Defender In-Embed Image)
            embed.set_thumbnail(url=attacker.user.display_avatar.url)
            embed.set_image(url=defender.user.display_avatar.url)

            if is_fatal:
                defender.is_alive = False
                attacker.kills += 1
                kill_pts = 50
                game.house_points[attacker.house] += kill_pts
                attacker.points_earned += kill_pts

                defender.death_cause = f"Defeated in a 1v1 duel by {attacker.user.display_name} ({spell['name']})"

                game.eliminated_recap.append({
                    "player": defender,
                    "killer": attacker.user.display_name,
                    "penalty": random.choice(FLASH_PENALTIES)
                })

                embed.add_field(
                    name="💀 KNOCKOUT!",
                    value=f"**{defender.user.display_name}** was eliminated! **+{kill_pts} Pts** awarded to **{attacker.house}**!",
                    inline=False
                )

                # Trigger Spectator Rescue Window
                res_view = ResurrectionView(game, defender, self)
                asyncio.create_task(channel.send(
                    f"✨ **{defender.user.display_name}** has fallen! 15s Rescue window open:",
                    view=res_view
                ))

            leaderboard = " | ".join([f"{HOUSES[h]['emoji']} {h}: {pts}pt" for h, pts in game.house_points.items()])
            embed.set_footer(text=f"Leaderboard: {leaderboard}")

            await channel.send(embed=embed)

        # Cleanup Guild State
        if guild_id in self.games:
            del self.games[guild_id]

    async def conclude_game(self, game: ServerGameState, channel: discord.TextChannel):
        guild_id = channel.guild.id
        winning_house = max(game.house_points, key=game.house_points.get)
        survivors = [p for p in game.players.values() if p.is_alive]
        triwizard_champ = survivors[0] if survivors else None

        # Update Server & Global Persistent Rankings
        if guild_id not in self.server_house_points:
            self.server_house_points[guild_id] = {h: 0 for h in HOUSES}

        for h_name, h_pts in game.house_points.items():
            self.server_house_points[guild_id][h_name] += h_pts
            self.global_house_points[h_name] += h_pts

        for p in game.players.values():
            is_win = (triwizard_champ and p.user.id == triwizard_champ.user.id)
            self.record_wizard_stats(p.user.id, p.kills, p.points_earned, win=is_win)

        # 1. Main Winner Embed
        embed = discord.Embed(
            title="🏆 THE HOUSE CUP HAS CONCLUDED! 🏆",
            description=f"Congratulations to **{winning_house}** {HOUSES[winning_house]['emoji']} for winning the House Cup!",
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

        # 2. Final Recap & Explicit Flash Forfeit Board
        recap_embed = discord.Embed(
            title="⚡ END OF GAME RECAP & FLASH FORFEITS",
            description="All eliminated wizards must complete their assigned forfeit tasks!",
            color=0xFF0055
        )

        if game.eliminated_recap:
            for item in game.eliminated_recap:
                p = item["player"]
                recap_embed.add_field(
                    name=f"💀 {p.user.display_name} ({p.house})",
                    value=f"• **Cause:** {p.death_cause}\n• **Flash Forfeit:** {item['penalty']}",
                    inline=False
                )
        else:
            recap_embed.add_field(name="Flawless Victory", value="No wizards were eliminated during this battle!", inline=False)

        await channel.send(embed=recap_embed)


# Setup Hook for Extension Loading
async def setup(bot: commands.Bot):
    await bot.add_cog(HouseCupCog(bot))
