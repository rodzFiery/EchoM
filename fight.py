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
from PIL import Image, ImageDraw, ImageOps, ImageFilter
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

# --- NEW: GAUNTLET (FIGHTECHO) VIEW ---
class GauntletView(discord.ui.View):
    def __init__(self, p1, p2, fight_system):
        super().__init__(timeout=None) # Keep active for the whole game
        self.p1 = p1
        self.p2 = p2
        self.fight_system = fight_system
        self.siphon_used = {p1.id: False, p2.id: False}
        self.tributes = {p1.id: 0, p2.id: 0}
        self.current_actions = {p1.id: "Endure", p2.id: "Endure"}
        self.mercy_offered = False
        self.mercy_accepted = False

    def update_buttons(self, p1_will, p2_will, p1_status, p2_status, scramble=False):
        self.clear_items()
        
        # Scramble Logic for Echo Events
        labels = [("ENDURE", "🛡️", discord.ButtonStyle.primary, "Endure"), 
                  ("FOCUS", "🧘", discord.ButtonStyle.success, "Focus"), 
                  ("SIPHON", "💉", discord.ButtonStyle.danger, "Siphon")]
        
        if scramble:
            random.shuffle(labels)

        for label, emoji, style, action_val in labels:
            btn = discord.ui.Button(label=label if not scramble else "???", style=style, emoji=emoji)
            
            async def callback(inter, val=action_val):
                if inter.user.id not in [self.p1.id, self.p2.id]: return
                # Status Effect Logic: Bound
                status = p1_status if inter.user.id == self.p1.id else p2_status
                if val == "Siphon" and "Bound" in status:
                    return await inter.response.send_message("⛓️ You are BOUND and cannot siphon!", ephemeral=True)
                
                self.current_actions[inter.user.id] = val
                await inter.response.send_message(f"Action locked: {val if not scramble else '???'}", ephemeral=True)
            
            btn.callback = callback
            self.add_item(btn)

        # Mercy Button (Visible if willpower is low)
        if (p1_will < 10 or p2_will < 10) and not self.mercy_offered:
            mercy_btn = discord.ui.Button(label="OFFER MERCY", style=discord.ButtonStyle.secondary, emoji="🏳️")
            async def mercy_callback(inter):
                if inter.user.id not in [self.p1.id, self.p2.id]: return
                # Only the one winning can offer mercy
                winner_id = self.p1.id if p1_will > p2_will else self.p2.id
                if inter.user.id != winner_id: return await inter.response.send_message("Only the dominant soul can offer mercy.", ephemeral=True)
                self.mercy_offered = True
                self.mercy_accepted = True # Flag to loop
                await inter.response.send_message("🏳️ You have offered a pity gift to your broken opponent.")
            mercy_btn.callback = mercy_callback
            self.add_item(mercy_btn)

        # Tribute remains for crowd
        tribute_btn = discord.ui.Button(label="TRIBUTE (100)", style=discord.ButtonStyle.secondary, emoji="💎")
        async def trib_callback(inter):
            if inter.user.id in [self.p1.id, self.p2.id]: return await inter.response.send_message("No self-mercy.", ephemeral=True)
            # Check Balance
            with main.get_db_connection() as conn:
                user = conn.execute("SELECT balance FROM users WHERE id=?", (inter.user.id,)).fetchone()
                if not user or user['balance'] < 100: return await inter.response.send_message("Too poor.", ephemeral=True)
                conn.execute("UPDATE users SET balance = balance - 100 WHERE id=?", (inter.user.id,))
                conn.commit()
            self.tributes[self.p1.id if random.random() > 0.5 else self.p2.id] += 10
            await inter.response.send_message("💎 Tribute cast into the pit!", ephemeral=True)
        tribute_btn.callback = trib_callback
        self.add_item(tribute_btn)

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

        # GAUNTLET HAZARDS
        self.gauntlet_hazards = [
            "The room fills with thick, sweet incense. {player} loses focus, their Willpower slipping.",
            "Heavy chains descend from the ceiling. {player} manages to dodge, but the effort is exhausting.",
            "The Master increases the frequency of the vibration. {player}'s resolve is crumbling!",
            "Freezing water sprays the floor. {player} is trembling under the sensory shock.",
            "The Sensory Silence begins. {player} is trapped with only their thoughts and the sound of their heart.",
            "A velvet bind tightens automatically. {player} struggles to remain upright.",
            "The scent of iron and ozone fills the air. The dungeon demands a price in will."
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
                            best_pet = {"name": pet['name'], "tier": tier, "luck": pet['luck']}
        return best_pet

    async def create_duel_image(self, p1_url, p2_url, relic1=None, relic2=None):
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(p1_url) as r1, session.get(p2_url) as r2:
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())
            
            bg_path = "1v1Background.jpg"
            bg = Image.open(bg_path).convert("RGBA").resize((1000, 500)) if os.path.exists(bg_path) else Image.new("RGBA", (1000, 500), (40, 0, 0, 255))
            
            # --- CUSTOM BACKGROUNDS PER RELIC ---
            if relic1 == "Void Blade" or relic2 == "Void Blade":
                overlay_color = Image.new("RGBA", bg.size, (128, 0, 128, 60)) # Purple tint
                bg = Image.alpha_composite(bg, overlay_color)
            if relic1 == "Iron Will Cage" or relic2 == "Iron Will Cage":
                # Simulated Chain Overlay (simplified)
                draw_bg = ImageDraw.Draw(bg)
                for x in range(0, 1000, 50): draw_bg.line((x, 0, x, 500), fill=(50,50,50,100), width=5)
            if relic1 == "Abyssal Eye" or relic2 == "Abyssal Eye":
                bg = bg.point(lambda p: p * 0.3) # Darken
                draw_bg = ImageDraw.Draw(bg)
                draw_bg.ellipse((450, 200, 550, 300), outline=(255,0,0,200), width=5) # Red eye

            av1 = Image.open(p1_data).convert("RGBA").resize((310, 310))
            av2 = Image.open(p2_data).convert("RGBA").resize((310, 310))
            
            mask = Image.new("L", (310, 310), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, 310, 310), fill=255)
            av1 = ImageOps.fit(av1, mask.size, centering=(0.5, 0.5))
            av1.putalpha(mask)
            av2 = ImageOps.fit(av2, mask.size, centering=(0.5, 0.5))
            av2.putalpha(mask)

            av1 = ImageOps.expand(av1, border=10, fill=(255, 69, 0)) 
            av2 = ImageOps.expand(av2, border=10, fill=(139, 0, 0))

            bg.paste(av1, (70, 95), av1)
            bg.paste(av2, (620, 95), av2)
            
            if os.path.exists("DragonFrame.png"):
                dragon = Image.open("DragonFrame.png").convert("RGBA").resize((1000, 500))
                bg = Image.alpha_composite(bg, dragon)

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
        round_counter = 0

        # --- ACTION LOOP ---
        while p1_hp > 0 and p2_hp > 0:
            round_counter += 1
            
            is_heal = random.random() < 0.20
            round_p1_acts = random.random() < p1_win_chance
            actor = ctx.author if round_p1_acts else member
            target = member if round_p1_acts else ctx.author
            
            if round_counter == 3 and (pet1 or pet2):
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
                color=0x8B0000 if round_counter % 2 == 0 else 0xFF4500)
            
            if file_buf: action_embed.set_image(url="attachment://fight.png")
            await main_msg.edit(embed=action_embed, view=None if p1_hp == 0 or p2_hp == 0 else cheer_view)
            await asyncio.sleep(4)

        winner, loser = (ctx.author, member) if p1_hp > p2_hp else (member, ctx.author)
        
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
            
            u_upd = conn.execute("SELECT balance, level, duel_wins FROM users WHERE id = ?", (winner.id,)).fetchone()
            rival_data = conn.execute("SELECT win_count FROM duel_history WHERE winner_id = ? AND loser_id = ?", (winner.id, loser.id)).fetchone()

        ach_cog = self.bot.get_cog("Achievements")
        ach_text = ach_cog.get_achievement_summary(winner.id) if ach_cog else "N/A"

        win_card = discord.Embed(title="👑 SUPREME DOMINION REACHED", color=0xFFD700)
        if os.path.exists("LobbyTopRight.jpg"):
            logo_file = discord.File("LobbyTopRight.jpg", filename="victory_logo.jpg")
            win_card.set_thumbnail(url="attachment://victory_logo.jpg")
        
        pet_assist = "Yes" if pet_used and pet_owner_name == winner.display_name else "No"
        cheers = cheer_view.cheers_p1 if winner == ctx.author else cheer_view.cheers_p2
        cuck_boost = f"+{cheers}% Chance" if cheers > 0 else "None"

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

        self.active_duels.remove(ctx.channel.id)

    # ==========================================
    # 🌑 GAUNTLET OF SHADOWS (!fightecho)
    # ==========================================

    @commands.command(name="fightecho", aliases=["gauntlet", "survive"])
    async def gauntlet_shadows(self, ctx, member: discord.Member):
        if member.id == ctx.author.id: return await ctx.send("You cannot walk the shadows alone.")
        if member.bot: return await ctx.send("The dungeon doesn't recognize cold metal.")
        if ctx.channel.id in self.active_duels: return await ctx.send("The shadows are currently occupied.")

        self.active_duels.add(ctx.channel.id)

        # TOLL GATHERING
        with main.get_db_connection() as conn:
            for uid in [ctx.author.id, member.id]:
                bal = conn.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()['balance']
                if bal < 10000:
                    self.active_duels.remove(ctx.channel.id)
                    return await ctx.send(f"❌ <@{uid}> cannot afford the toll.")
                conn.execute("UPDATE users SET balance = balance - 10000 WHERE id=?", (uid,))
            conn.commit()

        # ECHOPACK INITIATION PHASE
        ready_players = {ctx.author.id: False, member.id: False}
        player_relics = {ctx.author.id: None, member.id: None}
        
        init_emb = main.fiery_embed("🌑 VOID PACK INITIATION", "Type `!echopack` to draw your catalyst.")
        init_msg = await ctx.send(embed=init_emb)

        def pack_check(m): return m.channel == ctx.channel and m.content.lower() == "!echopack" and m.author.id in ready_players

        try:
            while not all(ready_players.values()):
                m = await self.bot.wait_for("message", check=pack_check, timeout=45.0)
                if not ready_players[m.author.id]:
                    relic_pool = [
                        {"name": "Void Blade", "atk_bonus": 15, "def_bonus": 0, "luck_bonus": 5, "desc": "Siphons Willpower more efficiently."},
                        {"name": "Iron Will Cage", "atk_bonus": 0, "def_bonus": 20, "luck_bonus": 0, "desc": "Provides massive defense."},
                        {"name": "Abyssal Eye", "atk_bonus": 5, "def_bonus": 0, "luck_bonus": 20, "desc": "Increases Luck."},
                        {"name": "Mirror of Narcissus", "atk_bonus": 0, "def_bonus": 5, "luck_bonus": 5, "desc": "Reflects 50% Siphon damage."},
                        {"name": "Leech's Collar", "atk_bonus": 0, "def_bonus": 0, "luck_bonus": 10, "desc": "Focus steals 5 Willpower."},
                        {"name": "The Masochist's Rose", "atk_bonus": 0, "def_bonus": 10, "luck_bonus": 0, "desc": "Hazard damage -50%, but no healing."},
                        {"name": "The Gambler's Coin", "atk_bonus": 0, "def_bonus": 0, "luck_bonus": 40, "desc": "Massive Luck, but double damage on fail."}
                    ]
                    relic = random.choice(relic_pool)
                    player_relics[m.author.id] = relic
                    ready_players[m.author.id] = True
                    await ctx.send(embed=main.fiery_embed("📦 ECHOPACK OPENED", f"{m.author.mention} drawn **{relic['name']}**!"))
        except asyncio.TimeoutError:
            self.active_duels.remove(ctx.channel.id)
            return await ctx.send("⌛ Abandoned.")

        # PRE-FIGHT SCAN
        ignis_engine = self.bot.get_cog("IgnisEngine")
        u1_inv = json.loads(main.get_user(ctx.author.id)['titles'])
        u2_inv = json.loads(main.get_user(member.id)['titles'])
        pet1, pet2 = self.get_user_pet(u1_inv), self.get_user_pet(u2_inv)
        p1_prot, p1_luck = await ignis_engine.get_market_bonuses(u1_inv)
        p2_prot, p2_luck = await ignis_engine.get_market_bonuses(u2_inv)

        # APPLY RELIC STATS
        p1_prot += player_relics[ctx.author.id]['def_bonus']
        p1_luck += player_relics[ctx.author.id]['luck_bonus']
        p2_prot += player_relics[member.id]['def_bonus']
        p2_luck += player_relics[member.id]['luck_bonus']

        p1_will, p2_will = 100, 100
        p1_status, p2_status = [], []
        view = GauntletView(ctx.author, member, self)
        
        # Initial Background
        img_buf = await self.create_duel_image(ctx.author.display_avatar.url, member.display_avatar.url, player_relics[ctx.author.id]['name'], player_relics[member.id]['name'])
        
        msg = await ctx.send(file=discord.File(img_buf, "trial.png") if img_buf else None, 
                             embed=main.fiery_embed("🌑 THE TRIAL BEGINS", "Select your actions."), view=view)

        round_num = 0
        stash_item = None
        hazard_modifier = 1.0

        while p1_will > 0 and p2_will > 0:
            round_num += 1
            
            # --- CHOICE BASED HAZARD ---
            if round_num % 3 == 0:
                h_choice = random.choice(["Whip", "Cold"])
                if h_choice == "Whip": 
                    hazard_text = "The Master cracks the Whip! High damage incoming, but siphons will be stronger."
                    hazard_modifier = 1.5
                else: 
                    hazard_text = "The Cold settles in. Low damage, but your next action is frozen to ENDURE."
                    hazard_modifier = 0.5
            else:
                hazard_text = random.choice(self.gauntlet_hazards)
                hazard_modifier = 1.0

            # --- ECHO EVENTS ---
            scramble = False
            if (p1_will + p2_will) < 100:
                echo_event = random.choice(["Blackout", "Voyeur", "FinalStand"])
                if echo_event == "Blackout":
                    hazard_text = "🌑 SUDDEN BLACKOUT! Actions are scrambled!"
                    scramble = True
                elif echo_event == "Voyeur":
                    hazard_text = "👁️ THE VOYEUR'S GAZE! Damage doubled, crowd influence tripled!"
                    hazard_modifier *= 2.0
                elif echo_event == "FinalStand":
                    hazard_text = "🩸 FINAL STAND! Protection is useless!"
                    p1_prot = p2_prot = 0

            # Update View Buttons
            view.update_buttons(p1_will, p2_will, p1_status, p2_status, scramble)
            await msg.edit(embed=main.fiery_embed(f"ROUND {round_num}", f"*{hazard_text}*"), view=view)

            # --- MID-GAME STASH (!grab) ---
            if round_num == 5:
                stash_announcement = await ctx.send("🎁 **THE MASTER DROPPED A STASH! Type `!grab` first!**")
                def grab_check(m): return m.channel == ctx.channel and m.content.lower() == "!grab" and m.author.id in [ctx.author.id, member.id]
                try:
                    grab_msg = await self.bot.wait_for("message", check=grab_check, timeout=5.0)
                    items = ["Silk Gag", "Blindfold", "Restraint Keys"]
                    stash_item = (grab_msg.author.id, random.choice(items))
                    await ctx.send(f"✅ {grab_msg.author.display_name} grabbed **{stash_item[1]}**!")
                except asyncio.TimeoutError:
                    await ctx.send("💨 The stash vanished into the void.")

            await asyncio.sleep(8) 

            # --- RESOLUTION ---
            round_results = []
            
            # Status: Bleeding Will
            if "Bleeding" in p1_status: p1_will -= 3; round_results.append("🩸 P1 Will bleeds.")
            if "Bleeding" in p2_status: p2_will -= 3; round_results.append("🩸 P2 Will bleeds.")

            for i, p_data in enumerate([{"u": ctx.author, "w": p1_will, "p": p1_prot, "l": p1_luck, "r": player_relics[ctx.author.id], "s": p1_status, "pet": pet1},
                                        {"u": member, "w": p2_will, "p": p2_prot, "l": p2_luck, "r": player_relics[member.id], "s": p2_status, "pet": pet2}]):
                
                u, w, p, l, r, s, pet = p_data["u"], p_data["w"], p_data["p"], p_data["l"], p_data["r"], p_data["s"], p_data["pet"]
                other_will = p2_will if u.id == ctx.author.id else p1_will
                choice = view.current_actions[u.id]

                # RELIC: Masochist Rose (Passive)
                current_hazard_mod = 0.5 if r["name"] == "The Masochist's Rose" else hazard_modifier

                if choice == "Siphon":
                    dmg = (30 + r["atk_bonus"]) * (1.5 if "Whip" in hazard_text else 1.0)
                    # RELIC: Mirror of Narcissus (Opponent Passive)
                    other_relic = player_relics[member.id] if u.id == ctx.author.id else player_relics[ctx.author.id]
                    if other_relic["name"] == "Mirror of Narcissus":
                        w -= (dmg * 0.5)
                        round_results.append(f"🪞 {u.name}'s siphon reflected!")
                    
                    w -= 15 # Cost
                    if u.id == ctx.author.id: p2_will -= dmg
                    else: p1_will -= dmg
                    round_results.append(f"💉 {u.name} siphoned {dmg} will!")

                elif choice == "Focus":
                    if r["name"] == "The Masochist's Rose":
                        round_results.append(f"🌹 {u.name} cannot focus (Relic penalty).")
                    else:
                        f_luck = l * (0.5 if "Deprived" in s else 1.0)
                        if random.randint(1, 100) <= (f_luck + 25):
                            w = min(100, w + 15)
                            if "Bleeding" in s: s.remove("Bleeding")
                            # RELIC: Leech Collar
                            if r["name"] == "Leech's Collar":
                                if u.id == ctx.author.id: p2_will -= 5
                                else: p1_will -= 5
                                round_results.append(f"🧛 {u.name} leeched 5 will!")
                            round_results.append(f"🧘 {u.name} Focused.")
                        else:
                            penalty = 20 * (2.0 if r["name"] == "The Gambler's Coin" else 1.0)
                            w -= penalty
                            round_results.append(f"❌ {u.name} Focus failed.")
                
                else: # Endure
                    h_dmg = max(5, (random.randint(15, 25) * current_hazard_mod) - (p // 4))
                    w -= h_dmg
                    # Status chance: Exposed
                    if random.random() < 0.2: s.append("Exposed"); round_results.append(f"👁️ {u.name} is EXPOSED!")
                    round_results.append(f"🛡️ {u.name} Endured {h_dmg}.")

                # Tributes
                w = min(100, w + view.tributes[u.id])
                view.tributes[u.id] = 0

                # Final update
                if u.id == ctx.author.id: p1_will = max(0, w)
                else: p2_will = max(0, w)

            # Check Mercy Acceptance
            if view.mercy_accepted: break

            # Reset status countdowns (simplified)
            view.current_actions = {ctx.author.id: "Endure", member.id: "Endure"}
            await msg.edit(embed=main.fiery_embed(f"ROUND {round_num}", f"Recap:\n" + "\n".join(round_results)))
            await asyncio.sleep(4)

        winner, loser = (ctx.author, member) if p1_will > p2_will else (member, ctx.author)
        payout = 19000
        if view.mercy_accepted:
            payout = 7000
            await ctx.send(f"🏳️ {winner.name} showed MERCY. {loser.name} keeps 2,000 Flames as a pity gift.")
            await main.update_user_stats_async(loser.id, amount=2000)

        await main.update_user_stats_async(winner.id, amount=payout, xp_gain=1000, source="Gauntlet")
        await ctx.send(embed=main.fiery_embed("🏆 TRIAL OVER", f"{winner.mention} survived."))
        self.active_duels.remove(ctx.channel.id)

async def setup(bot):
    await bot.add_cog(FightSystem(bot))
