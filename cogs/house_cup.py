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
PEPPERUP_COST = 50
PROTEGO_COST = 100
HEX_COST = 75
DRAGON_COST = 250
RESURRECTION_COST = 150

FLASH_PENALTIES = [
    "Flash VC or DMs within 2 minutes!",
    "Post a spicy teaser photo in the NSFW channel!",
    "Send an explicit voice note to the winning House!",
    "Perform a 10-second flash challenge on camera!",
    "Show your favorite tattoo/secret spot to the server!"
]

# Database/Economy Hook Integration
def get_user_balance(bot: commands.Bot, user_id: int) -> int:
    try:
        user_data = bot.get_user(user_id)
        if isinstance(user_data, dict) and 'balance' in user_data:
            return user_data['balance']
    except Exception:
        pass
    return 1000

def modify_user_balance(bot: commands.Bot, user_id: int, amount: int) -> bool:
    try:
        if hasattr(bot, 'update_user_stats_async'):
            # Trigger economy update via main bot handler
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
        self.has_shield = False
        self.is_frozen = False
        self.kills = 0
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
        self.spectator_queue: List[dict] = []
        self.eliminated_recap: List[dict] = []  # Stores data for the final recap board
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

        # Delete old lobby message if cached
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


class SpectatorSelectView(discord.ui.View):
    def __init__(self, game: ServerGameState, action_type: str, cost: int, cog: "HouseCupCog"):
        super().__init__(timeout=None)  # Infinite lifetime
        self.game = game
        self.action_type = action_type
        self.cost = cost
        self.cog = cog

        options = [
            discord.SelectOption(
                label=p.user.display_name[:100],
                description=f"House: {p.house} | HP: {p.hp}",
                value=str(p.user.id)
            ) for p in game.players.values() if p.is_alive
        ]

        if not options:
            options.append(discord.SelectOption(label="No valid targets", value="none"))

        select = discord.ui.Select(
            placeholder="Select a Wizard target...",
            options=options[:25],
            custom_id=f"housecup:select:{action_type}"
        )
        select.callback = self.target_selected
        self.add_item(select)

    async def target_selected(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_id = int(interaction.data['values'][0])
        
        if target_id not in self.game.players:
            await interaction.followup.send("❌ Target no longer available.", ephemeral=True)
            return

        if not modify_user_balance(self.cog.bot, interaction.user.id, -self.cost):
            await interaction.followup.send("❌ Insufficient server currency balance!", ephemeral=True)
            return

        self.game.spectator_queue.append({
            "action": self.action_type,
            "caster": interaction.user,
            "target_id": target_id
        })

        target_player = self.game.players[target_id]
        await interaction.followup.send(
            f"✅ Sent **{self.action_type}** targeting **{target_player.user.display_name}** for {self.cost} coins!",
            ephemeral=True
        )
        self.stop()


class ArenaControlView(discord.ui.View):
    def __init__(self, cog: "HouseCupCog", guild_id: int):
        super().__init__(timeout=None)  # Infinite lifetime
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="Pepperup Potion (50c)", style=discord.ButtonStyle.success, emoji="🧪", custom_id="housecup:arena:pepperup")
    async def pepperup(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game(interaction.guild_id)
        if not game or not game.is_running:
            await interaction.response.send_message("❌ No active battle running.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Select target to heal (+30 HP):",
            view=SpectatorSelectView(game, "pepperup", PEPPERUP_COST, self.cog),
            ephemeral=True
        )

    @discord.ui.button(label="Protego Shield (100c)", style=discord.ButtonStyle.primary, emoji="🛡️", custom_id="housecup:arena:protego")
    async def protego(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game(interaction.guild_id)
        if not game or not game.is_running:
            await interaction.response.send_message("❌ No active battle running.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Select target to shield against next hit:",
            view=SpectatorSelectView(game, "protego", PROTEGO_COST, self.cog),
            ephemeral=True
        )

    @discord.ui.button(label="Cast Hex (75c)", style=discord.ButtonStyle.secondary, emoji="⚡", custom_id="housecup:arena:hex")
    async def cast_hex(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.get_game(interaction.guild_id)
        if not game or not game.is_running:
            await interaction.response.send_message("❌ No active battle running.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Select rival target to freeze for 1 round:",
            view=SpectatorSelectView(game, "hex", HEX_COST, self.cog),
            ephemeral=True
        )

    @discord.ui.button(label="Release Dragon (250c)", style=discord.ButtonStyle.danger, emoji="🐉", custom_id="housecup:arena:dragon")
    async def unleash_dragon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        game = self.cog.get_game(interaction.guild_id)
        if not game or not game.is_running:
            await interaction.followup.send("❌ No active battle running.", ephemeral=True)
            return

        if not modify_user_balance(self.cog.bot, interaction.user.id, -DRAGON_COST):
            await interaction.followup.send("❌ Insufficient funds (250 Coins required)!", ephemeral=True)
            return

        game.spectator_queue.append({
            "action": "dragon",
            "caster": interaction.user,
            "target_id": None
        })
        await interaction.followup.send("🐉 **Hungarian Horntail** released into the arena queue!", ephemeral=True)


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
        self.server_game_counts: Dict[int, int] = {}  # Tracks total games per guild
        self.global_game_count: int = 0               # Tracks total games across all guilds

    def cog_unload(self):
        for game in self.games.values():
            if game.game_task and not game.game_task.done():
                game.game_task.cancel()

    async def cog_load(self):
        self.bot.add_view(LobbyView(self, 0))
        self.bot.add_view(ArenaControlView(self, 0))

    def get_game(self, guild_id: int) -> Optional[ServerGameState]:
        return self.games.get(guild_id)

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
        
        # Profile Picture Integration
        leader = game.get_leader_player()
        if leader:
            embed.set_thumbnail(url=leader.user.display_avatar.url)

        embed.set_footer(text=f"Server Match #{game.server_game_num} • Global Match #{game.global_game_num} • Min 2 players required")
        return embed

    # ==========================================
    # DIRECT PREFIX COMMAND (!housecup)
    # ==========================================
    @commands.command(name="housecup")
    @commands.guild_only()
    async def housecup(self, ctx: commands.Context):
        """Creates or manages the active House Cup game lobby."""
        guild_id = ctx.guild.id
        if guild_id in self.games and (self.games[guild_id].is_lobby_open or self.games[guild_id].is_running):
            await ctx.send("⚠️ A House Cup lobby or active game is already running in this server!")
            return

        # Increment game tracking counters
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

    # ==========================================
    # AUTOMATED BATTLE ENGINE LOOP
    # ==========================================
    async def run_battle_loop(self, guild_id: int, channel: discord.TextChannel):
        game = self.games.get(guild_id)
        if not game:
            return

        control_view = ArenaControlView(self, guild_id)

        while game.is_running:
            game.round_number += 1
            await asyncio.sleep(ACTION_TICK_SECONDS)

            alive_players = [p for p in game.players.values() if p.is_alive]
            
            # Check End Conditions
            surviving_houses = {p.house for p in alive_players}
            if len(alive_players) <= 1 or len(surviving_houses) <= 1:
                game.is_running = False
                await self.conclude_game(game, channel)
                break

            round_logs: List[str] = []

            # 1. Resolve Spectator Actions Queue
            while game.spectator_queue:
                action = game.spectator_queue.pop(0)
                act_type = action["action"]
                caster = action["caster"]
                target = game.players.get(action["target_id"]) if action["target_id"] else None

                if act_type == "pepperup" and target and target.is_alive:
                    target.hp = min(target.max_hp, target.hp + 30)
                    round_logs.append(f"🧪 **{caster.display_name}** fed a Pepperup Potion to **{target.user.display_name}** (+30 HP)!")

                elif act_type == "protego" and target and target.is_alive:
                    target.has_shield = True
                    round_logs.append(f"🛡️ **{caster.display_name}** cast Protego over **{target.user.display_name}**!")

                elif act_type == "hex" and target and target.is_alive:
                    if target.house == "Ravenclaw" and random.random() < 0.10:
                        round_logs.append(f"🦅 **{target.user.display_name}** dodged **{caster.display_name}**'s Hex with Ravenclaw Wit!")
                    else:
                        target.is_frozen = True
                        round_logs.append(f"⚡ **{caster.display_name}** hit **{target.user.display_name}** with *Petrificus Totalus*!")

                elif act_type == "dragon":
                    target_dragon = max(alive_players, key=lambda p: p.hp)
                    damage = random.randint(35, 50)
                    if target_dragon.has_shield:
                        target_dragon.has_shield = False
                        round_logs.append(f"🐉 Hungarian Horntail scorched **{target_dragon.user.display_name}**, but Protego absorbed it!")
                    else:
                        target_dragon.hp -= damage
                        if target_dragon.hp <= 0:
                            target_dragon.death_cause = "Burned to ashes by a spectator's Hungarian Horntail"
                        round_logs.append(f"🐉 Hungarian Horntail blasted **{target_dragon.user.display_name}** for **{damage} HP**!")

            # 2. Fully Automated Combat & Trap Encounters
            for player in alive_players:
                if not player.is_alive:
                    continue

                if player.is_frozen:
                    player.is_frozen = False
                    round_logs.append(f"❄️ **{player.user.display_name}** was frozen and skipped their turn!")
                    continue

                # Pick random rival target
                potential_rivals = [p for p in alive_players if p.house != player.house and p.is_alive]
                if not potential_rivals:
                    continue
                
                target = random.choice(potential_rivals)
                damage = random.randint(15, 30)

                # Slytherin Trait
                if player.house == "Slytherin" and random.random() < 0.10:
                    damage = int(damage * 1.5)
                    round_logs.append(f"🐍 Slytherin Ambition triggered critical hit for **{player.user.display_name}**!")

                if target.has_shield:
                    target.has_shield = False
                    round_logs.append(f"🛡️ **{player.user.display_name}** attacked **{target.user.display_name}**, but Protego shielded them!")
                else:
                    target.hp -= damage
                    game.house_points[player.house] += 10
                    round_logs.append(f"🪄 **{player.user.display_name}** cast *Stupefy* on **{target.user.display_name}** (-{damage} HP)!")

                # Handle Knockouts & Fatal Traits
                if target.hp <= 0:
                    if target.house == "Gryffindor" and random.random() < 0.10:
                        target.hp = 1
                        round_logs.append(f"🦁 Gryffindor Bravery saved **{target.user.display_name}** from fatal collapse!")
                    else:
                        target.is_alive = False
                        player.kills += 1
                        game.house_points[player.house] += 50
                        if not target.death_cause:
                            target.death_cause = f"Knocked off broomstick by {player.user.display_name}"
                        
                        # Store for final recap board
                        game.eliminated_recap.append({
                            "player": target,
                            "killer": player.user.display_name,
                            "penalty": random.choice(FLASH_PENALTIES)
                        })

                        round_logs.append(f"💀 **{target.user.display_name}** was eliminated from the battle!")

                        # Trigger Spectator Rescue Window
                        res_view = ResurrectionView(game, target, self)
                        asyncio.create_task(channel.send(
                            f"✨ **{target.user.display_name}** has fallen! 15s Spectator Rescue window open:",
                            view=res_view
                        ))

            # 3. Publish Round Outcome Embed
            leader = game.get_leader_player()
            embed = discord.Embed(
                title=f"⚔️ House Cup Battle - Round {game.round_number}",
                color=HOUSES[leader.house]["color"] if leader else 0x7F0909
            )
            embed.add_field(name="Round Events", value="\n".join(round_logs) if round_logs else "Quiet turn in the arena.", inline=False)

            status_text = ""
            for p in game.players.values():
                icon = HOUSES[p.house]["emoji"]
                st = f"HP: {p.hp}/{p.max_hp}" if p.is_alive else "☠️ ELIMINATED"
                status_text += f"{icon} **{p.user.display_name}** | {st}\n"
            
            embed.add_field(name="Wizard Status", value=status_text, inline=False)
            
            # Set top wizard profile picture as thumbnail
            if leader:
                embed.set_thumbnail(url=leader.user.display_avatar.url)

            leaderboard = " | ".join([f"{HOUSES[h]['emoji']} {h}: {pts}pt" for h, pts in game.house_points.items()])
            embed.set_footer(text=f"Leaderboard: {leaderboard}")

            await channel.send(embed=embed, view=control_view)

        # Cleanup Guild State
        if guild_id in self.games:
            del self.games[guild_id]

    async def conclude_game(self, game: ServerGameState, channel: discord.TextChannel):
        winning_house = max(game.house_points, key=game.house_points.get)
        survivors = [p for p in game.players.values() if p.is_alive]
        triwizard_champ = survivors[0] if survivors else None

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
