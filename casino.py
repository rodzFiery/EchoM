import discord
from discord.ext import commands
import random
import sys
import os
import asyncio
from datetime import datetime, timedelta, timezone
import inspect

# --- ENHANCED VISUAL CARD RENDERER ---
def get_visual_card(value):
    """Converts a raw card number into a high-potency, larger-looking visual string."""
    suits = {"♥️": "🔴", "♠️": "⚫", "♦️": "🔸", "♣️": "♣️"}
    suit_icon = random.choice(list(suits.keys()))
    
    if value == 11: face = "A"
    elif value == 10: face = random.choice(["10", "J", "Q", "K"])
    else: face = str(value)
    
    return f"**[ {face} {suit_icon} ]**"

# --- DICE INTERFACE (PRESERVED) ---
class DiceInterface(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.selected_guess = None
        self.selected_bet = None

    @discord.ui.select(
        placeholder="🫦 Target Climax: Choose your Sum (2-12)...",
        options=[discord.SelectOption(label=f"Sum: {i}", value=str(i), emoji="🎲") for i in range(2, 13)]
    )
    async def select_guess(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ This is not your session, pet.", ephemeral=True)
        self.selected_guess = int(select.values[0])
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="🎯 Target Sum", value=f"**{self.selected_guess}**", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.select(
        placeholder="💰 Set Tribute: Select your Bet Amount...",
        options=[
            discord.SelectOption(label="1,000 Flames", value="1000", emoji="🫦"),
            discord.SelectOption(label="5,000 Flames", value="5000", emoji="⛓️"),
            discord.SelectOption(label="15,000 Flames", value="15000", emoji="💦"),
            discord.SelectOption(label="35,000 Flames", value="35000", emoji="🔞"),
            discord.SelectOption(label="55,000 Flames", value="55000", emoji="🍑"),
            discord.SelectOption(label="75,000 Flames (MAX)", value="75000", emoji="🔥"),
        ]
    )
    async def select_bet(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ This is not your session.", ephemeral=True)
        self.selected_bet = int(select.values[0])
        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="💸 Current Bet", value=f"**{self.selected_bet:,} Flames**", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🔞 RELEASE THE BONES 🔞", style=discord.ButtonStyle.danger, row=4)
    async def roll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Your hands don't belong here.", ephemeral=True)
        if self.selected_guess is None or self.selected_bet is None:
            return await interaction.response.send_message("❌ **Incomplete Protocol.**", ephemeral=True)
        await self.cog.execute_dice_logic(interaction, self.selected_guess, self.selected_bet)
        self.stop()

# --- BLACKJACK STAKE INTERFACE (PRESERVED) ---
class BJStakeInterface(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.selected_bet = None

    @discord.ui.select(
        placeholder="🔞 Choose the weight of your surrender (Bet)...",
        options=[
            discord.SelectOption(label="5,000 Flames", value="5000", emoji="⛓️"),
            discord.SelectOption(label="15,000 Flames", value="15000", emoji="💦"),
            discord.SelectOption(label="35,000 Flames", value="35000", emoji="🔞"),
            discord.SelectOption(label="50,000 Flames", value="50000", emoji="🍑"),
            discord.SelectOption(label="75,000 Flames (MAX)", value="75000", emoji="🔥"),
        ]
    )
    async def select_bet(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ctx.author.id: return
        self.selected_bet = int(select.values[0])
        await interaction.response.edit_message(content=f"✅ **Stake locked:** `{self.selected_bet:,}` Flames. Prepare to be dealt.")

    @discord.ui.button(label="🫦 DEAL THE CARDS 🫦", style=discord.ButtonStyle.success, row=4)
    async def deal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return
        if not self.selected_bet:
            return await interaction.response.send_message("❌ You must set a stake, pet.", ephemeral=True)
        await self.cog.start_blackjack_duel(interaction, self.selected_bet)
        self.stop()

# --- BLACKJACK GAMEPLAY VIEW (PRESERVED) ---
class BJGameView(discord.ui.View):
    def __init__(self, author, cog, bet, p_hand, d_hand):
        super().__init__(timeout=120)
        self.author = author
        self.cog = cog
        self.bet = bet
        self.p_hand = p_hand
        self.d_hand = d_hand

    @discord.ui.button(label="🫦 HIT", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id: return
        self.p_hand.append(self.cog.draw_card())
        if self.cog.calculate_bj(self.p_hand) > 21:
            await self.cog.finish_blackjack(interaction, self.bet, self.p_hand, self.d_hand, "BUST")
            self.stop()
        else:
            await self.cog.update_bj_display(interaction, self.bet, self.p_hand, self.d_hand, self)

    @discord.ui.button(label="⛓️ STAND", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id: return
        while self.cog.calculate_bj(self.d_hand) < 17:
            self.d_hand.append(self.cog.draw_card())
        await self.cog.finish_blackjack(interaction, self.bet, self.p_hand, self.d_hand, "STAND")
        self.stop()

# --- ROULETTE INTERFACE (PRESERVED) ---
class RouletteInterface(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.selected_choice = None
        self.selected_bet = None

    @discord.ui.select(
        placeholder="🎡 Fate's Alignment: Pick a Color or Number...",
        options=[
            discord.SelectOption(label="Red", value="red", emoji="🔴"),
            discord.SelectOption(label="Black", value="black", emoji="⚫"),
            discord.SelectOption(label="Zero (Green)", value="0", emoji="🟢"),
        ] + [discord.SelectOption(label=f"Number {i}", value=str(i)) for i in range(1, 13)]
    )
    async def select_choice(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ctx.author.id: return
        self.selected_choice = select.values[0]
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="🎡 Targeted Outcome", value=f"**{self.selected_choice.upper()}**", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.select(
        placeholder="💰 Set Tribute: Select your Bet Amount...",
        options=[
            discord.SelectOption(label="5,000 Flames", value="5000", emoji="⛓️"),
            discord.SelectOption(label="15,000 Flames", value="15000", emoji="💦"),
            discord.SelectOption(label="35,000 Flames", value="35000", emoji="🔞"),
            discord.SelectOption(label="75,000 Flames (MAX)", value="75000", emoji="🔥"),
        ]
    )
    async def select_bet(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ctx.author.id: return
        self.selected_bet = int(select.values[0])
        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="💸 Current Bet", value=f"**{self.selected_bet:,} Flames**", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🔞 SPIN THE WHEEL 🔞", style=discord.ButtonStyle.danger, row=4)
    async def spin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return
        if not self.selected_choice or not self.selected_bet:
            return await interaction.response.send_message("❌ Complete the ritual first, pet.", ephemeral=True)
        await self.cog.execute_roulette_logic(interaction, self.selected_choice, self.selected_bet)
        self.stop()

# --- NEW: SLOTS INTERFACE ---
class SlotsInterface(discord.ui.View):
    """The interactive dashboard for the Triple Pleasure Slots."""
    def __init__(self, ctx, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.selected_bet = None

    @discord.ui.select(
        placeholder="💰 Set Tribute: Choose your Bet amount...",
        options=[
            discord.SelectOption(label="1,000 Flames", value="1000", emoji="🫦"),
            discord.SelectOption(label="5,000 Flames", value="5000", emoji="⛓️"),
            discord.SelectOption(label="10,000 Flames", value="10000", emoji="🔞"),
            discord.SelectOption(label="25,000 Flames", value="25000", emoji="🍑"),
            discord.SelectOption(label="50,000 Flames", value="50000", emoji="💦"),
            discord.SelectOption(label="75,000 Flames (MAX)", value="75000", emoji="🔥"),
        ]
    )
    async def select_bet(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ctx.author.id: return
        self.selected_bet = int(select.values[0])
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="💸 Current Bet", value=f"**{self.selected_bet:,} Flames**", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🎰 PULL THE LEVER 🎰", style=discord.ButtonStyle.danger, row=4)
    async def spin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return
        if not self.selected_bet:
            return await interaction.response.send_message("❌ Select your tribute first.", ephemeral=True)
        await self.cog.execute_slots_logic(interaction, self.selected_bet)
        self.stop()

class FieryCasino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.max_bet = 75000

    async def get_user_data(self, user_id):
        main_mod = sys.modules['__main__']
        if inspect.iscoroutinefunction(main_mod.get_user):
            return await main_mod.get_user(user_id)
        return main_mod.get_user(user_id)

    def draw_card(self):
        return random.randint(2, 11)

    def calculate_bj(self, hand):
        score = sum(hand)
        if score > 21 and 11 in hand:
            score -= 10
        return score

    # --- DICE COMMANDS ---
    @commands.command(name="dice")
    async def dice_dashboard(self, ctx):
        main_mod = sys.modules['__main__']
        user = await self.get_user_data(ctx.author.id)
        view = DiceInterface(ctx, self)
        desc = (
            "### 🎲 THE BONE TOSS INTERFACE\n"
            "The Master has waived the cooldown. You may gamble until your vault is empty.\n\n"
            f"💰 **Vault Assets:** {user['balance']:,} Flames"
        )
        embed = main_mod.fiery_embed("BONE TOSS PROTOCOL", desc, color=0x800000)
        embed.add_field(name="🎯 Target Sum", value="`Pending...`", inline=True)
        embed.add_field(name="💸 Current Bet", value="`Pending...`", inline=True)
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def execute_dice_logic(self, interaction, guess, bet):
        main_mod = sys.modules['__main__']
        user = await self.get_user_data(interaction.user.id)
        if user['balance'] < bet:
            return await interaction.response.send_message("❌ **Asset Deficiency.**", ephemeral=True)
        await interaction.response.edit_message(content="🎲 **Rattling the cup...**", view=None, embed=None)
        await asyncio.sleep(2.0)
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        mult = 1.0 + (user['fiery_level'] * 0.01)
        if total == guess:
            win = int((bet * 8) * mult)
            await main_mod.update_user_stats_async(interaction.user.id, amount=win-bet, source="Dice Win")
            title, color = "🔞 CLIMAX ACHIEVED 🔞", 0x00FF00
            res = f"The dice settle: **[{d1}]** & **[{d2}]**\nTotal: **{total}**\n\n🫦 **DOMINANCE.** You win **{win:,} Flames**."
        else:
            await main_mod.update_user_stats_async(interaction.user.id, amount=-bet, source="Dice Loss")
            title, color = "💀 CRIPPLING LOSS 💀", 0x8B0000
            res = f"The dice settle: **[{d1}]** & **[{d2}]**\nTotal: **{total}**\n\n⛓️ **SUBMISSION.** You lose **{bet:,} Flames**."
        embed = main_mod.fiery_embed(title, res, color=color)
        await interaction.edit_original_response(content=None, embed=embed)

    # --- BLACKJACK COMMANDS ---
    @commands.command(name="blackjack")
    async def blackjack_dashboard(self, ctx):
        main_mod = sys.modules['__main__']
        user = await self.get_user_data(ctx.author.id)
        view = BJStakeInterface(ctx, self)
        desc = (
            "## 🫦 THE RED TABLE: BLACKJACK\n"
            "Submit your stake to sit across from the Dealer. Reach 21 without breaking.\n\n"
            f"💰 **Current Balance:** `{user['balance']:,}` Flames"
        )
        embed = main_mod.fiery_embed("BLACKJACK PROTOCOL", desc, color=0x3b0a0a)
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def start_blackjack_duel(self, interaction, bet):
        p_hand = [self.draw_card(), self.draw_card()]
        d_hand = [self.draw_card(), self.draw_card()]
        if self.calculate_bj(p_hand) == 21:
            await self.finish_blackjack(interaction, bet, p_hand, d_hand, "BLACKJACK")
        else:
            view = BJGameView(interaction.user, self, bet, p_hand, d_hand)
            await self.update_bj_display(interaction, bet, p_hand, d_hand, view)

    async def update_bj_display(self, interaction, bet, p_hand, d_hand, view):
        main_mod = sys.modules['__main__']
        p_score = self.calculate_bj(p_hand)
        p_visual = " ".join([get_visual_card(c) for c in p_hand])
        d_visual = f"{get_visual_card(d_hand[0])} **[ ❔ ]**"
        desc = (f"### 🫦 {interaction.user.mention} against the House\n💰 **Stake:** `{bet:,}` Flames\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n\n**🎴 YOUR HAND:**\n{p_visual}\n**⚡ TOTAL:** `{p_score}`\n\n"
                f"**🃏 DEALER HAND:**\n{d_visual}\n━━━━━━━━━━━━━━━━━━━━━━━")
        embed = main_mod.fiery_embed("THE DUEL IS ON", desc, color=0x3b0a0a)
        await interaction.response.edit_message(embed=embed, view=view)

    async def finish_blackjack(self, interaction, bet, p_hand, d_hand, reason):
        main_mod = sys.modules['__main__']
        user = await self.get_user_data(interaction.user.id)
        p_score = self.calculate_bj(p_hand)
        d_score = self.calculate_bj(d_hand)
        mult = 1.0 + (user['fiery_level'] * 0.01)
        win, status = 0, ""
        if reason == "BLACKJACK":
            win = int((bet * 2.5) * mult)
            status = f"🔞 **NATURAL CLIMAX!** {interaction.user.display_name} overstimulated the dealer."
            color = 0xFFD700
        elif p_score > 21:
            win = -bet
            status = f"💀 **BUST.** {interaction.user.display_name} broke under pressure."
            color = 0x8B0000
        elif d_score > 21 or p_score > d_score:
            win = int((bet * 2) * mult)
            status = f"🫦 **DOMINANCE.** {interaction.user.display_name} outplayed the House."
            color = 0x00FF00
        elif p_score == d_score:
            win = 0
            status = f"🤝 **STALEMATE.** No one climaxes. Bet returned."
            color = 0x808080
        else:
            win = -bet
            status = f"⛓️ **DEFEAT.** {interaction.user.display_name} taken by the House."
            color = 0x8B0000

        if win > 0: await main_mod.update_user_stats_async(interaction.user.id, amount=win-bet, source="BJ Win")
        elif win < 0: await main_mod.update_user_stats_async(interaction.user.id, amount=win, source="BJ Loss")

        p_visual = " ".join([get_visual_card(c) for c in p_hand])
        d_visual = " ".join([get_visual_card(c) for c in d_hand])
        res_desc = (f"## {status}\n\n**🫦 FINAL:**\n{p_visual} (`{p_score}`)\n\n**⛓️ DEALER:**\n{d_visual} (`{d_score}`)\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n💳 **RESULT:** `{'+' if win >= 0 else ''}{win:,}` Flames")
        embed = main_mod.fiery_embed("DUEL CONCLUDED", res_desc, color=color)
        await interaction.response.edit_message(embed=embed, view=None)

    # --- ROULETTE COMMANDS ---
    @commands.command(name="roulette")
    async def roulette_dashboard(self, ctx):
        main_mod = sys.modules['__main__']
        user = await self.get_user_data(ctx.author.id)
        view = RouletteInterface(ctx, self)
        desc = (f"## 🎡 THE WHEEL OF LUST\n💰 **Balance:** `{user['balance']:,}` Flames")
        embed = main_mod.fiery_embed("ROULETTE PROTOCOL", desc, color=0x641e16)
        embed.add_field(name="🎡 Targeted Outcome", value="`Pending...`", inline=True)
        embed.add_field(name="💸 Current Bet", value="`Pending...`", inline=True)
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def execute_roulette_logic(self, interaction, choice, bet):
        main_mod = sys.modules['__main__']
        user = await self.get_user_data(interaction.user.id)
        if user['balance'] < bet: return await interaction.response.send_message("❌ **Vault Deficiency.**", ephemeral=True)
        await interaction.response.edit_message(content="🎡 **The wheel is spinning...**", view=None, embed=None)
        await asyncio.sleep(3.0)
        num = random.randint(0, 36)
        color = "red" if num % 2 == 0 and num != 0 else "black"
        if num == 0: color = "green"
        mult = 1.0 + (user['fiery_level'] * 0.01)
        win = 0
        if choice == color or (choice.isdigit() and int(choice) == num):
            payout_mult = 35 if choice.isdigit() else 2
            win = int((bet * payout_mult) * mult)
            await main_mod.update_user_stats_async(interaction.user.id, amount=win-bet, source="Roulette Win")
            title, color_hex = "🔞 THE WHEEL SUBMITS 🔞", 0x00FF00
            res = f"The ball settles on: **{num} ({color.upper()})**\n\n🫦 **ALIGNMENT.** Payout of **{win:,} Flames**!"
        else:
            await main_mod.update_user_stats_async(interaction.user.id, amount=-bet, source="Roulette Loss")
            title, color_hex = "💀 THE WHEEL REJECTS 💀", 0x8B0000
            res = f"The ball settles on: **{num} ({color.upper()})**\n\n⛓️ **SUBMISSION.** Your tribute is consumed."
        embed = main_mod.fiery_embed(title, res, color=color_hex)
        await interaction.edit_original_response(content=None, embed=embed)

    # --- SLOTS COMMANDS ---
    @commands.command(name="slots")
    async def slots_dashboard(self, ctx):
        main_mod = sys.modules['__main__']
        user = await self.get_user_data(ctx.author.id)
        view = SlotsInterface(ctx, self)
        desc = (
            "## 🎰 TRIPLE PLEASURE SLOTS\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "**⛓️ PAYTABLE:**\n"
            "• **3x Same Icon:** 10x Payout\n"
            "• **2x Same Icon:** 3x Payout\n"
            "• **3x 🔥 (JACKPOT):** 50x Payout\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 **Balance:** `{user['balance']:,}` Flames"
        )
        embed = main_mod.fiery_embed("SLOT PROTOCOL", desc, color=0xd4af37)
        embed.add_field(name="💸 Current Bet", value="`Pending...`", inline=True)
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def execute_slots_logic(self, interaction, bet):
        main_mod = sys.modules['__main__']
        user = await self.get_user_data(interaction.user.id)
        if user['balance'] < bet: return await interaction.response.send_message("❌ **Vault Deficiency.**", ephemeral=True)
        icons = ["🫦", "⛓️", "🔞", "🍑", "💦", "🔥"]
        
        # ANIMATION SEQUENCE
        await interaction.response.edit_message(content="🎰 **Spinning...**", view=None, embed=None)
        for frame in range(3):
            f1, f2, f3 = random.choice(icons), random.choice(icons), random.choice(icons)
            await interaction.edit_original_response(content=f"🎰 **REELS SPINNING:** `[ {f1} | {f2} | {f3} ]`", view=None, embed=None)
            await asyncio.sleep(0.7)
            
        r1, r2, r3 = random.choice(icons), random.choice(icons), random.choice(icons)
        mult = 1.0 + (user['fiery_level'] * 0.01)
        win = 0
        if r1 == r2 == r3:
            payout = 50 if r1 == "🔥" else 10
            win = int((bet * payout) * mult)
        elif r1 == r2 or r2 == r3 or r1 == r3:
            win = int((bet * 3) * mult)

        if win > 0:
            await main_mod.update_user_stats_async(interaction.user.id, amount=win-bet, source="Slots Win")
            title, color = "🔞 TOTAL ALIGNMENT 🔞", 0xFFD700
            res = f"### 🎰 [ {r1} | {r2} | {r3} ]\n\n🫦 **CLIMAX.** The machine shudders and releases **{win:,} Flames**!"
        else:
            await main_mod.update_user_stats_async(interaction.user.id, amount=-bet, source="Slots Loss")
            title, color = "💀 MACHINE COLD 💀", 0x8B0000
            res = f"### 🎰 [ {r1} | {r2} | {r3} ]\n\n⛓️ **SUBMISSION.** No alignment found. Your tribute is consumed."

        embed = main_mod.fiery_embed(title, res, color=color)
        await interaction.edit_original_response(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(FieryCasino(bot))
    print("✅ LOG: Triple Pleasure Slots integrated into Casino Protocols.")
