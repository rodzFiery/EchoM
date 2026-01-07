# FIX: Python 3.13 compatibility shim for audioop
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
        import sys
        sys.modules['audioop'] = audioop
    except ImportError:
        pass 

import discord
from discord.ext import commands
import random
import asyncio
import io
import aiohttp
import os
import json
import traceback
import sqlite3 # ADDED: Necessary for database handling
import sys
from PIL import Image, ImageDraw, ImageOps
from datetime import datetime, timezone

# Accessing shared logic from main and ignis
import main
import ignis

# Configuration
AUDIT_CHANNEL_ID = 1438810509322223677

# --- NEW: CHEER/CUCK INTERACTION VIEW ---
class CheerButtons(discord.ui.View):
    def __init__(self, challenger, defender, fight_system):
        super().__init__(timeout=15.0)
        self.challenger = challenger
        self.defender = defender
        self.fight_system = fight_system
        self.cheers_p1 = 0
        self.cheers_p2 = 0

    @discord.ui.button(label="Cuck (Cheer)", style=discord.ButtonStyle.success, emoji="💚")
    async def cuck_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Prevent fighters from cheering in their own fight
        if interaction.user.id in [self.challenger.id, self.defender.id]:
            return await interaction.response.send_message("You cannot cuck your own session, pet.", ephemeral=True)
        
        # Internal View to select which member to "cuck"
        select_view = discord.ui.View(timeout=10.0)
        
        async def cheer_p1(inter):
            self.cheers_p1 += 1
            emb = main.fiery_embed("📢 Fight Interrupted", 
                f"👤 {inter.user.mention} is **cheering (cucking)** the fight!\n" 
                f"📈 **+1% Win Chance** granted to {self.challenger.mention}.", color=0x00FF00)
            await inter.response.send_message(embed=emb)

        async def cheer_p2(inter):
            self.cheers_p2 += 1
            emb = main.fiery_embed("📢 Fight Interrupted", 
                f"👤 {inter.user.mention} is **cheering (cucking)** the fight!\n" 
                f"📈 **+1% Win Chance** granted to {self.defender.mention}.", color=0x00FF00)
            await inter.response.send_message(embed=emb)

        btn_p1 = discord.ui.Button(label=f"Cheer {self.challenger.display_name}", style=discord.ButtonStyle.primary)
        btn_p2 = discord.ui.Button(label=f"Cheer {self.defender.display_name}", style=discord.ButtonStyle.primary)
        
        btn_p1.callback = cheer_p1
        btn_p2.callback = cheer_p2
        
        select_view.add_item(btn_p1)
        select_view.add_item(btn_p2)
        
        await interaction.response.send_message("Select which soul to support:", view=select_view, ephemeral=True)

class FightSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_duels = set()
        self.audit_channel_id = AUDIT_CHANNEL_ID
        
        # NEW: Pet specific interference actions
        self.pet_actions = {
            "Basic": "{pet_name} nipped at {target}'s ankles, causing a momentary lapse in focus!",
            "Normal": "{pet_name} let out a piercing cry, echoing through the Red Room and startling {target}!",
            "Rare": "{pet_name} circled {target}, its eyes glowing with abyssal hunger, distracting them!",
            "Epic": "{pet_name} channeled the void, momentarily slowing {target}'s movements with a dark aura!",
            "Legendary": "{pet_name} unleashed a wave of terror! {target} is trembling, their defense is useless!",
            "Supreme": "{pet_name} has rewritten reality for a moment. {target} is completely paralyzed by the sight of the God-Creature!"
        }

        # 50+ Additional Intensive BDSM/Power Play Combat Logs
        self.combat_logs = [
            "{winner} slams {loser} against the padded wall, the sound of leather hitting skin echoing.",
            "{winner} forces a heavy collar around {loser}'s neck, snapping the lock shut.",
            "{winner} drags {loser} by their chains, asserting total control of the floor.",
            "{winner} applies a weighted paddle to {loser}",
            "{winner} pins {loser}'s arms back, whispering dark promises of total surrender.",
            "{winner} uses a silk blindfold to plunge {loser} into a world of pure sensation.",
            "{winner} delivers a sharp sting with a riding crop, checking {loser}'s posture.",
            "{winner} locks {loser} into a spreader bar, leaving them completely exposed.",
            "{winner} whispers a command so cold it makes {loser} stop breathing for a second.",
            "{winner} asserts their status as Master, forcing {loser} to kiss the floor.",
            "{winner} tightens the corset on {loser}",
            "{winner} uses a velvet rope to bind {loser} in a complex, inescapable web.",
            "{winner} mocks {loser}'s feeble attempts to maintain their dignity.",
            "{winner} applies an ice cube to {loser}'s skin, followed immediately by the heat of a candle.",
            "{winner} claims {loser}'s senses, dictating when they can feel and when they cannot.",
            "{winner} uses a leather hood to isolate {loser}",
            "{winner} delivers a rhythmic spanking that turns {loser}'s skin a deep, fiery red.",
            "{winner} forces {loser} to kneel and maintain eye contact while they dictate the rules.",
            "{winner} uses a weighted chain to pull {loser} back into their orbit.",
            "{winner} applies a feather tickler with agonizing slowness, driving {loser} mad.",
            "{winner} demands a verbal acknowledgment of their total dominance.",
            "{winner} pins {loser} with a single hand, showing the massive gap in power.",
            "{winner} uses a latex suit to turn {loser} into a living, breathing doll.",
            "{winner} applies a vibrating egg, making {loser} struggle to stay focused.",
            "{winner} delivers a lecture on obedience while {loser} is held in a stress position.",
            "{winner} uses a sharp claw to trace lines of ownership down {loser}'s back.",
            "{winner} locks the cage door, leaving {loser} to contemplate their failure.",
            "{winner} uses a gag to silence {loser}'s protests, replaced by muffled moans.",
            "{winner} asserts that {loser} is now official property of the Red Room.",
            "{winner} applies a warm wax drip, marking {loser} as their chosen asset.",
            "{winner} uses a cane to deliver a precise lesson in dungeon etiquette.",
            "{winner} forces {loser} into a submissive pose that highlights their vulnerability.",
            "{winner} whispers that {loser}'s body no longer belongs to them tonight.",
            "{winner} uses a pair of nipple clamps to focus {loser}'s entire world into one point.",
            "{winner} claims a victory of the mind, breaking {loser} mental resistance.",
            "{winner} uses a fur-lined set of cuffs to keep {loser} close and controlled.",
            "{winner} delivers a series of stinging slaps that leave glowing marks.",
            "{winner} forces {loser} to crawl to them, emphasizing the power dynamic.",
            "{winner} uses a glass plug to increase the stakes of the current session.",
            "{winner} asserts that the winner takes all, and the loser gives everything.",
            "{winner} applies a weighted whip with a crack that startles the entire dungeon.",
            "{winner} locks {loser}'s wrists behind their back, rendering them helpless.",
            "{winner} uses a velvet leash to lead {loser} around the private chamber.",
            "{winner} delivers a final, crushing blow of absolute authority.",
            "{winner} whispers that this is only the beginning of {loser}'s training.",
            "{winner} uses a soft brush to tease {loser} before the final strike.",
            "{winner} forces {loser} to beg for the next round of discipline.",
            "{winner} asserts their dominance with a look that commands total stillness.",
            "{winner} uses a heavy belt to mark the end of {loser}'s freedom.",
            "{winner} claims {loser} as the ultimate prize of this erotic duel.",
            "{winner} winks at {loser} while tightening the cuffs. 'Did I say you could move?'",
            "{winner} whispers into {loser}'s ear: 'Your heart is beating so fast... are you scared or excited?'",
            "{winner} asks {loser} if they prefer the red paddle or the black one. 'Pick your poison.'",
            "{winner} marks their territory on {loser} with a trail of sharp bites.",
            "{winner} forces {loser} to breathe in the scent of worn leather and submission."
        ]

    # Helper: Fiery Visual HP Bar
    def get_fiery_bar(self, hp, max_hp=100):
        length = 10
        filled = int(length * hp // max_hp)
        symbol = "❤️" if hp > 70 else "🫦" if hp > 35 else "🩸"
        bar = symbol * filled + "🖤" * (length - filled)
        return f"**{bar}** `{hp}%`"

    # Helper: Fetches the best pet from shop data
    def get_user_pet(self, titles):
        import shop
        best_pet = None
        max_luck = -1
        for title in titles:
            for tier, pets in shop.MARKET_DATA["Pets"].items():
                for pet in pets:
                    if pet['name'] == title:
                        if pet['luck'] > max_luck:
                            max_luck = pet['luck']
                            best_pet = {"name": pet['name'], "tier": tier}
        return best_pet

    async def create_duel_image(self, p1_url, p2_url):
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(p1_url) as r1, session.get(p2_url) as r2:
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())
            bg_path = "1v1Background.jpg"
            bg = Image.open(bg_path).convert("RGBA").resize((1000, 500)) if os.path.exists(bg_path) else Image.new("RGBA", (1000, 500), (40, 0, 0, 255))
            av1 = Image.open(p1_data).convert("RGBA").resize((250, 250))
            av2 = Image.open(p2_data).convert("RGBA").resize((250, 250))
            av1 = ImageOps.expand(av1, border=10, fill=(255, 69, 0))
            av2 = ImageOps.expand(av2, border=10, fill=(128, 0, 128))
            bg.paste(av1, (100, 125), av1)
            bg.paste(av2, (650, 125), av2)
            overlay = Image.new("RGBA", bg.size, (139, 0, 0, 40))
            bg = Image.alpha_composite(bg, overlay)
            buf = io.BytesIO()
            bg.save(buf, format="PNG")
            buf.seek(0)
            return buf
        except: return None

    @commands.command(name="fuck", aliases=["challenge", "duel"])
    async def fight_challenge(self, ctx, member: discord.Member):
        if member.id == ctx.author.id: return await ctx.send("❌ You cannot fuck yourself. This is a dungeon, not a solo cell.")
        if member.bot: return await ctx.send("❌ Machines have no souls to break.")
        if ctx.channel.id in self.active_duels: return await ctx.send("⏳ A session is already happening here.")

        self.active_duels.add(ctx.channel.id)

        # PRE-FIGHT STAT SCAN
        ignis_engine = self.bot.get_cog("IgnisEngine")
        u1_inv = json.loads(main.get_user(ctx.author.id)['titles'])
        u2_inv = json.loads(main.get_user(member.id)['titles'])
        
        pet1 = self.get_user_pet(u1_inv)
        pet2 = self.get_user_pet(u2_inv)
        
        p1_prot, p1_luck = await ignis_engine.get_market_bonuses(u1_inv)
        p2_prot, p2_luck = await ignis_engine.get_market_bonuses(u2_inv)
        
        with main.get_db_connection() as conn:
            h1 = conn.execute("SELECT win_count FROM duel_history WHERE winner_id = ? AND loser_id = ?", (ctx.author.id, member.id)).fetchone()
            h2 = conn.execute("SELECT win_count FROM duel_history WHERE winner_id = ? AND loser_id = ?", (member.id, ctx.author.id)).fetchone()
            p1_vs_p2 = h1['win_count'] if h1 else 0
            p2_vs_p1 = h2['win_count'] if h2 else 0

        p1_win_chance = 0.5 + ((p1_prot + p1_luck) - (p2_prot + p2_luck)) / 100
        p1_win_chance = max(0.15, min(0.85, p1_win_chance))

        p1_hp, p2_hp = 100, 100

        embed = main.fiery_embed("🔞 RED ROOM PRIVATE SESSION", 
            f"🥀 **The atmosphere thickens. The doors are locked.**\n\n" 
            f"👤 **{ctx.author.display_name}** vs **{member.display_name}**\n" 
            f"📊 **Lifetime Rivalry Score:** `{p1_vs_p2}` victories to `{p2_vs_p1}`\n\n" 
            f"🛡️ **Defense:** {p1_prot} vs {p2_prot} | 🍀 **Luck:** {p1_luck} vs {p2_luck}", color=0xFF0000)
        
        file_buf = await self.create_duel_image(ctx.author.display_avatar.url, member.display_avatar.url)
        cheer_view = CheerButtons(ctx.author, member, self)
        
        main_msg = None
        if file_buf:
            file = discord.File(file_buf, filename="fight.png")
            embed.set_image(url="attachment://fight.png")
            main_msg = await ctx.send(file=file, embed=embed, view=cheer_view)
        else:
            main_msg = await ctx.send(embed=embed, view=cheer_view)

        await asyncio.sleep(8)
        
        p1_win_chance += (cheer_view.cheers_p1 * 0.01)
        p1_win_chance -= (cheer_view.cheers_p2 * 0.01)

        pet_used = False
        pet_owner_name = ""

        # --- ACTION LOOP ---
        for i in range(1, 11): 
            if p1_hp <= 0 or p2_hp <= 0: break

            is_heal = random.random() < 0.20
            round_p1_acts = random.random() < p1_win_chance
            actor = ctx.author if round_p1_acts else member
            target = member if round_p1_acts else ctx.author
            
            # Pet Logic Check inside loop for assistance tracking
            if i == 3 and (pet1 or pet2):
                active_pet_owner = ctx.author if random.random() < 0.5 and pet1 else member
                if active_pet_owner:
                    pet_used = True
                    pet_owner_name = active_pet_owner.display_name

            change_msg = ""
            if is_heal:
                h_amt = random.randint(8, 15)
                if round_p1_acts: p1_hp = min(100, p1_hp + h_amt)
                else: p2_hp = min(100, p2_hp + h_amt)
                change_msg = f"💚 **RECOVERY:** +{h_amt} HP"
                log = f"{actor.display_name} finds focus amidst the pleasure and pain."
            else:
                dmg = random.randint(15, 30)
                is_crit = random.randint(1, 100) <= (p1_luck if round_p1_acts else p2_luck)
                if is_crit: 
                    dmg = int(dmg * 1.6)
                    change_msg = f"✨ **CRITICAL:** -{dmg} HP"
                else:
                    change_msg = f"🔥 **STRIKE:** -{dmg} HP"
                
                if round_p1_acts: p2_hp = max(0, p2_hp - dmg)
                else: p1_hp = max(0, p1_hp - dmg)
                log = random.choice(self.combat_logs).format(winner=actor.display_name, loser=target.display_name)

            action_embed = main.fiery_embed(f"🔞 SESSION PROGRESS", 
                f"🔥 **RECENT ACTION:**\n> {log}\n" 
                f"{change_msg}\n\n" 
                f"👤 **{ctx.author.display_name}**\n{self.get_fiery_bar(p1_hp)}\n\n" 
                f"👤 **{member.display_name}**\n{self.get_fiery_bar(p2_hp)}", 
                color=0x8B0000 if i % 2 == 0 else 0xFF4500)
            
            if file_buf: action_embed.set_image(url="attachment://fight.png")
            await main_msg.edit(embed=action_embed, view=None if p1_hp == 0 or p2_hp == 0 else cheer_view)
            await asyncio.sleep(4)

        winner, loser = (ctx.author, member) if p1_hp > p2_hp else (member, ctx.author)
        
        # Database & Stats Sync
        await main.update_user_stats_async(winner.id, amount=2500, xp_gain=500, source="Duel Win")
        await main.update_user_stats_async(loser.id, source="Duel Loss")

        with main.get_db_connection() as conn:
            conn.execute("UPDATE users SET duel_wins = duel_wins + 1 WHERE id = ?", (winner.id,))
            conn.execute("""
                INSERT INTO duel_history (winner_id, loser_id, win_count) 
                VALUES (?, ?, 1)
                ON CONFLICT(winner_id, loser_id) DO UPDATE SET win_count = win_count + 1
            """, (winner.id, loser.id))
            conn.execute("UPDATE quests SET d1 = d1 + 1, w2 = w2 + 1 WHERE user_id = ?", (winner.id,))
            conn.commit()
            
            # Fetch fresh data for detailed win card
            u_upd = conn.execute("SELECT balance, level, duel_wins FROM users WHERE id = ?", (winner.id,)).fetchone()
            rival_data = conn.execute("SELECT win_count FROM duel_history WHERE winner_id = ? AND loser_id = ?", (winner.id, loser.id)).fetchone()

        ach_cog = self.bot.get_cog("Achievements")
        ach_text = ach_cog.get_achievement_summary(winner.id) if ach_cog else "N/A"

        # Final Detailed Victory Embed
        win_card = discord.Embed(title="👑 SUPREME DOMINION REACHED", color=0xFFD700)
        if os.path.exists("LobbyTopRight.jpg"):
            logo_file = discord.File("LobbyTopRight.jpg", filename="victory_logo.jpg")
            win_card.set_thumbnail(url="attachment://victory_logo.jpg")
        
        # Assistance Logic for Footer/Fields
        pet_assist = "Yes" if pet_used and pet_owner_name == winner.display_name else "No"
        cheers = cheer_view.cheers_p1 if winner == ctx.author else cheer_view.cheers_p2
        cuck_boost = f"+{cheers}% Chance" if cheers > 0 else "None"

        # Constructing the Detailed Dossier View
        win_card.description = (
            f"🥀 **{winner.display_name}** has asserted absolute authority over **{loser.display_name}**.\n\n"
            f"💰 **Prize Received:** 2,500 Flames\n"
            f"💦 **Experience Gained:** 500\n"
            f"🐾 **Pet Assisted:** {pet_assist}\n"
            f"💚 **Cuck Boost:** {cuck_boost}\n"
            f"📈 **Quest Progress:** Daily Kill +1\n\n"
            f"⛓️ **Lifetime Private Wins:** `{u_upd['duel_wins']}`\n"
            f"🩸 **Rivalry Dominance:** `{rival_data['win_count']}` victories over <@{loser.id}>\n\n"
            f"💳 **Wallet:** {u_upd['balance']} Flames\n"
            f"🧬 **Total Sinner Level:** {u_upd['level']}\n\n"
            f"🏅 **Achievements:**\n/\n{ach_text}"
        )
        
        win_card.set_image(url=winner.display_avatar.url)
        win_card.set_footer(text="The Red Room records your conquest. Submission is eternal.")
        
        await ctx.send(content=f"🏆 {winner.mention} stands supreme!", embed=win_card)

        # --- NEW ADDED FEATURE: VOYEUR PRIVATE SESSION AUDIT ---
        audit_channel = self.bot.get_channel(self.audit_channel_id)
        if audit_channel:
            audit_emb = main.fiery_embed("🕵️ VOYEUR PRIVATE SESSION AUDIT", 
                f"The Master's Voyeurs have recorded a private dominance ritual in {ctx.channel.mention}.")
            
            if os.path.exists("LobbyTopRight.jpg"):
                audit_emb.set_thumbnail(url="https://i.imgur.com/8N8K8S8.png")

            audit_emb.add_field(name="⛓️ Dominant", value=winner.mention, inline=True)
            audit_emb.add_field(name="🫦 Submissive", value=loser.mention, inline=True)
            audit_emb.add_field(name="📊 Resulting Rivalry", value=f"`{rival_data['win_count']}` to `{p2_vs_p1 if winner == ctx.author else p1_vs_p2}`", inline=True)
            
            audit_emb.add_field(name="🐾 Pet Assistance", value=pet_assist, inline=True)
            audit_emb.add_field(name="💚 Cuck Influence", value=cuck_boost, inline=True)
            audit_emb.add_field(name="💰 Harvest", value="+2,500 Flames", inline=True)

            audit_emb.description = (
                f" f\"🔞 **VOYEUR NOTE:** {winner.display_name} has successfully broken {loser.display_name}'s resistance. \" "
                f" f\"The session concluded with {winner.display_name} maintaining absolute control. \" "
                f" f\"New Lifetime Wins for dominant: `{u_upd['duel_wins']}`.\""
            )
            
            await audit_channel.send(embed=audit_emb)

        self.active_duels.remove(ctx.channel.id)

async def setup(bot):
    await bot.add_cog(FightSystem(bot))
