import discord
from discord.ext import commands
import random
import io
import aiohttp
import sys
import json
import os
from PIL import Image, ImageDraw, ImageOps, ImageFilter
from datetime import datetime, timezone
import asyncio # ADDED: Required for to_thread logic

# --- COMPATIBILITY SHIM ---
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
        import sys
        sys.modules['audioop'] = audioop
    except:
        pass

class FieryShip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # ADDED: Track attempts for reroll logic
        self.ship_attempts = {} 
        # 250+ EROTIC & EMOTIONAL MESSAGES CATEGORIZED BY TIER
        self.erotic_lexicon = {
            "sad": [
                "A cold void. {u1} and {u2} are like oil and water in a dark cell.",
                "Repulsion. The chains between them shatter before they can even lock.",
                "Zero friction. Even as assets, they have nothing to say to each other.",
                "The Master turns away in boredom. This pair has no spark, only silence.",
                "A tragic waste of leather. They are destined to remain strangers.",
                "The air between them is as thin as their interest. Non-existent.",
                "Even the shadows in the dungeon avoid this pairing.",
                "Total dissonance. {u1}'s frequency is miles away from {u2}.",
                "An allergic reaction. The collar rejects the neck.",
                "The chemistry set just exploded. Not in a good way.",
                "Like a locked door with no keyhole. Impossible.",
                "The abyss stares back, and it's bored by this couple.",
                "A desert of desire. Not a drop of heat to be found.",
                "The chains rattle in protest. This is a mistake.",
                "Zero. Nada. The dungeon lights flicker and die at the sight of them."
            ],
            "low": [
                "Stiff and formal. A purely professional arrangement of pain.",
                "They might share a whip, but never a moan.",
                "Functional compatibility. They can occupy the same dungeon, barely.",
                "Minimal heat. Like a candle in a hurricane, it flicker and dies.",
                "A lukewarm touch that leaves both shivering for the wrong reasons.",
                "They are like two prisoners who just want different cells.",
                "Faint traces of arousal, quickly smothered by awkwardness.",
                "The spark is there, but it's buried under 10 tons of concrete.",
                "Mechanical movements. No soul in this interaction.",
                "A dry friction that earns no rewards.",
                "The Master checks the ledger; this pair is barely worth the oxygen.",
                "A polite nod in the hallway is all they'll ever have.",
                "Their compatibility is as shallow as a training collar.",
                "The heat is at a mere 10 degrees. Freezing.",
                "A flicker of hope, immediately extinguished by reality."
            ],
            "medium": [
                "Tension is building. The Red Room feels a little smaller when they are together.",
                "A curious friction. {u1} is watching {u2} from the shadows of the cage.",
                "The potential for a collar exists, but the keys are still hidden.",
                "Moderate arousal. A shared glance during a trial is all they have... for now.",
                "The scent of leather is getting stronger. Something is stirring.",
                "A slow burn. The dungeon floor is starting to warm up.",
                "They are circling each other like predators in a velvet pit.",
                "The pulse quickens. {u1} is considering a leash for {u2}.",
                "A heavy atmosphere follows them. The voyeurs are starting to notice.",
                "Not yet a fire, but the smoke is definitely rising.",
                "Compatibility is stable. They work well in a group... or a pair.",
                "The chains are beginning to hum with anticipation.",
                "A solid foundation for a very dark relationship.",
                "They speak the same language of submission and command.",
                "The friction is consistent. A pleasant hum in the dark."
            ],
            "sexual": [
                "🔞 **PEAK FRICTION.** The dungeon air grows thick when they touch.",
                "69% - The perfect balance of oral tradition and heavy restraints.",
                "Their moans are echoing through the ventilation shafts. Total carnal alignment.",
                "A playground of skin. {u1} and {u2} were made for this level of exhibition.",
                "The Master watches the gallery feed with interest. This is art.",
                "They are a symphony of sweat and submission.",
                "The restraints are straining under the force of their connection.",
                "Total exhibitionist energy. They want the dungeon to watch.",
                "A volcanic eruption of pure, unadulterated lust.",
                "The Red Room was built for moments like this.",
                "Their bodies are a puzzle that only they know how to solve.",
                "Intense, primal, and completely out of control.",
                "The voyeurs are breathless. This is the ultimate show.",
                "A synchronization of moans that can be heard in every cell.",
                "They have reached a frequency that turns the lights red.",
                "Absolute carnal dominance. Neither wants to stop.",
                "The heat is unbearable. The sprinklers should be going off.",
                "A masterclass in erotic friction. 10/10.",
                "They have forgotten the game. There is only the touch."
            ],
            "high": [
                "Dangerous obsession. They are losing track of the game in each other's eyes.",
                "Soul-binding heat. The collar is locked, and they both threw away the key.",
                "More than just pleasure. A deep, dark synchronization of spirit.",
                "They dominate the pit together. A power couple forged in the Red Room.",
                "The Master considers them a single entity now. Inseparable.",
                "A synchronization so deep it borders on the supernatural.",
                "They have traded their souls for a single night together.",
                "The chains between them are made of more than just iron.",
                "A devotion that terrifies the other assets.",
                "They have created their own dungeon within the dungeon.",
                "A hurricane of passion that levels everything in its path.",
                "They are the gold standard for compatibility in the Red Room.",
                "A deep, rhythmic alignment of two very dark hearts.",
                "They don't need commands; they move as one.",
                "The ultimate asset pairing. Maximum efficiency, maximum heat."
            ],
            "love": [
                "💖 **ETERNAL POSSESSION.** 100% Love. {u1} has claimed {u2}'s soul forever.",
                "Absolute Devotion. Beyond the chains, beyond the flames, there is only them.",
                "The ultimate contract. No expiry date, no tax rate, just total union.",
                "Two bodies, one heartbeat. The dungeon has produced a masterpiece of love.",
                "Sacred Bond. They have transcended the Red Room and become its gods.",
                "A love so powerful it burns brighter than the furnace.",
                "They have found the only thing more addictive than power: Each other.",
                "The Master bows. This is a connection he cannot control.",
                "A divine union in a place of sin. Miraculous.",
                "They are the heartbeat of the dungeon now.",
                "Total, unconditional surrender of two souls to one another.",
                "A love written in blood and sealed with a kiss.",
                "They have survived the pit and find heaven in the dark.",
                "The chains have turned to gold. A perfect 100.",
                "There are no more users, only {u1} and {u2} One."
            ]
        }
        # FIXED: Pulled dynamically from main module to support the !audit system
        self.AUDIT_CHANNEL_ID = getattr(sys.modules['__main__'], "AUDIT_CHANNEL_ID", 1438810509322223677)

    async def create_ship_image(self, u1_url, u2_url, percent):
        """Generates visual match with SQUARE avatars and high-visibility central volcanic column."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(u1_url) as r1, session.get(u2_url) as r2:
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())

            def draw_process():
                # --- RESETTING LAYOUT ---
                canvas_width = 1200
                canvas_height = 700
                if os.path.exists("shipbg.jpg"):
                    canvas = Image.open("shipbg.jpg").convert("RGBA").resize((canvas_width, canvas_height))
                else:
                    canvas = Image.new("RGBA", (canvas_width, canvas_height), (25, 5, 35, 255))
                draw = ImageDraw.Draw(canvas)

                particle_count = int((percent / 100) * 130) + 30
                for _ in range(particle_count):
                    px = random.randint(0, canvas_width)
                    py = random.randint(0, canvas_height)
                    p_size = random.randint(5, 18)
                    p_type = random.choice(["heart", "spark", "nebula"])
                    p_color = random.choice([
                        (255, 192, 203, 180),  # Pink
                        (255, 182, 193, 160),  # Light Pink
                        (255, 105, 180, 140),  # Hot Pink
                        (255, 240, 245, 200)   # Lavender Blush (Light Highlight)
                    ])
                    
                    if p_type == "heart":
                        draw.text((px, py), "💖", fill=p_color)
                    elif p_type == "nebula":
                        draw.ellipse([px, py, px+p_size*3, py+p_size*3], fill=(*p_color[:3], 25))
                    else:
                        draw.ellipse([px, py, px+p_size//2, py+p_size//2], fill=p_color)

                av_size = 400
                av1_img = Image.open(p1_data).convert("RGBA").resize((av_size, av_size))
                av2_img = Image.open(p2_data).convert("RGBA").resize((av_size, av_size))

                def apply_erotic_frame_square(avatar, pulse_intensity=3):
                    glow_size = av_size + 80
                    glow = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
                    draw_g = ImageDraw.Draw(glow)
                    
                    glow_range = int(35 + (pulse_intensity * 3)) 
                    for i in range(glow_range, 0, -1):
                        alpha = int(210 * (1 - i/glow_range))
                        r = int(255) 
                        g = int(182)   
                        b = int(193)
                        draw_g.rectangle([i, i, glow_size-i, glow_size-i], outline=(r, g, b, alpha), width=5)
                    
                    glow.paste(avatar, (40, 40), avatar)
                    return glow
                
                pulse = int((percent / 100) * 18) 
                
                av1_framed = apply_erotic_frame_square(av1_img, pulse)
                av2_framed = apply_erotic_frame_square(av2_img, pulse)
                canvas.paste(av1_framed, (20, 150), av1_framed)
                canvas.paste(av2_framed, (canvas_width - av_size - 100, 150), av2_framed)

                if percent == 100:
                    badge_w, badge_h = 460, 100
                    badge_x = (canvas_width // 2) - (badge_w // 2)
                    badge_y = 10
                    draw.rectangle([badge_x-5, badge_y-5, badge_x+badge_w+5, badge_y+badge_h+5], fill=(255, 105, 180, 80))
                    draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], fill=(20, 0, 5, 230), outline=(255, 182, 193), width=4)
                    draw.text((badge_x + 65, badge_y + 25), "⛓️ SOUL BOND ⛓️", fill=(255, 182, 193))

                pillar_w, pillar_h = 100, 480
                pillar_x = (canvas_width // 2) - (pillar_w // 2)
                pillar_y = 120
                draw.rectangle([pillar_x, pillar_y, pillar_x + pillar_w, pillar_y + pillar_h], fill=(20, 5, 25, 240), outline=(255, 182, 193), width=4)
                fill_pixels = int((percent / 100) * pillar_h)
                if fill_pixels > 0:
                    for i in range(fill_pixels):
                        ratio = i / pillar_h
                        r = int(255) 
                        g = int(20 + (162 * ratio))   
                        b = int(147 + (46 * ratio)) 
                        current_y = (pillar_y + pillar_h) - i
                        draw.line([pillar_x + 5, current_y, pillar_x + pillar_w - 5, current_y], fill=(r, g, b, 255), width=1)
                    draw.rectangle([pillar_x + 2, (pillar_y + pillar_h) - fill_pixels - 2, pillar_x + pillar_w - 2, (pillar_y + pillar_h) - fill_pixels + 2], fill=(255, 245, 250))
                percent_text = f"{percent}%"
                draw.text((pillar_x - 30, 20), percent_text, fill=(255, 182, 193), stroke_width=6, stroke_fill=(0,0,0))
                buf = io.BytesIO()
                canvas.save(buf, format="PNG")
                buf.seek(0)
                return buf

            return await asyncio.to_thread(draw_process)
        except Exception as e:
            print(f"Fiery Ship Error: {e}")
            return None

    async def create_union_image(self, u1_url, u2_url, bond_type="Marriage"):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(u1_url) as r1, session.get(u2_url) as r2:
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())
            
            def draw_union():
                bg_color = (255, 182, 193, 50) if "Anniversary" in bond_type else (30, 0, 10, 255)
                canvas = Image.new("RGBA", (1000, 500), bg_color)
                av1 = Image.open(p1_data).convert("RGBA").resize((320, 320))
                av2 = Image.open(p2_data).convert("RGBA").resize((320, 320))
                draw = ImageDraw.Draw(canvas)
                if "Anniversary" in bond_type:
                    for _ in range(30):
                        x, y = random.randint(0, 1000), random.randint(0, 500)
                        draw.text((x, y), "💕", fill=(255, 182, 193))
                canvas.paste(av1, (100, 90), av1)
                canvas.paste(av2, (580, 90), av2)
                icon = "⛓️🫦⛓️" if bond_type == "Marriage" else "🤝🔥🤝"
                if "Anniversary" in bond_type: icon = "💖🔥🔞"
                draw.text((440, 210), icon, fill=(255, 182, 193))
                buf = io.BytesIO()
                canvas.save(buf, format="PNG")
                buf.seek(0)
                return buf

            return await asyncio.to_thread(draw_union)
        except: return None

    @commands.command(name="ship")
    async def ship(self, ctx, user1: discord.Member, user2: discord.Member = None):
        """LEGENDARY SHIP: {u1} x {u2}"""
        if user2 is None:
            user2 = user1
            user1 = ctx.author

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # UPDATED: Key now includes the command author's ID so scans are unique per user
        pair_key = f"{ctx.author.id}-{min(user1.id, user2.id)}-{max(user1.id, user2.id)}"
        
        if pair_key not in self.ship_attempts or self.ship_attempts[pair_key]['date'] != today:
            self.ship_attempts[pair_key] = {'count': 0, 'date': today}
            
        self.ship_attempts[pair_key]['count'] += 1
        attempt_count = self.ship_attempts[pair_key]['count']

        if attempt_count < 3:
            random.seed(f"{pair_key}{datetime.now().timestamp()}")
            percent = random.randint(0, 100)
            status_note = f"**⚠️ Unstable Vibration: Scan {attempt_count}/3. Results are fluctuating...**"
        else:
            # UPDATED: Final seed also includes author ID to ensure unique final resonance per user
            seed_str = f"{ctx.author.id}{min(user1.id, user2.id)}{max(user1.id, user2.id)}{today}"
            random.seed(seed_str)
            percent = random.randint(0, 100)
            status_note = "**🔒 Frequency Locked: Resonance has stabilized for the next cycle.**"
            
        random.seed()

        if percent == 0: tier = "sad"
        elif percent < 30: tier = "low"
        elif percent < 60: tier = "medium"
        elif 60 <= percent <= 75: tier = "sexual"
        elif percent < 100: tier = "high"
        else: tier = "love"

        message_template = random.choice(self.erotic_lexicon[tier])
        result_msg = message_template.format(u1=user1.display_name, u2=user2.display_name)

        main_mod = sys.modules['__main__']
        u1_data = await asyncio.to_thread(main_mod.get_user, user1.id)
        is_anni = False
        if u1_data['spouse'] == user2.id and u1_data['marriage_date']:
            m_date = datetime.strptime(u1_data['marriage_date'], "%Y-%m-%d")
            now_dt = datetime.now()
            if m_date.day == now_dt.day and m_date.month != now_dt.month:
                is_anni = True

        embed = main_mod.fiery_embed("**💖 LOVEFINDER**", f"**Assets Involved: {user1.mention} ❤️‍🔥 {user2.mention}**\n{status_note}")
        
        if is_anni:
            embed.title = "**🔞 SAKURA ANNIVERSARY 🔞**"
            result_msg = f"**💖 1 MONTH MILESTONE! {result_msg}**\n\n**🔥 DOUBLE REWARDS ACTIVE: You both gain 2x XP and Flames today!**"
            embed.color = 0xFFB6C1 

        if percent == 69: 
            embed.title = "**🫦 EXHIBITIONIST PEAK REACHED 🫦**"
            await main_mod.update_user_stats_async(user1.id, amount=2500, source="Ship 69% Bonus")
            await main_mod.update_user_stats_async(user2.id, amount=2500, source="Ship 69% Bonus")
            result_msg += "\n\n**💰 EXHIBITION REWARD: The dungeon provides 2,500 Flames for the show!**"
            
            def track_69():
                with main_mod.get_db_connection() as conn:
                    conn.execute("UPDATE users SET ship_69_count = ship_69_count + 1 WHERE id = ?", (user1.id,))
                    conn.execute("UPDATE users SET ship_69_count = ship_69_count + 1 WHERE id = ?", (user2.id,))
                    conn.commit()
            await asyncio.to_thread(track_69)

        if percent == 100:
            def track_100():
                with main_mod.get_db_connection() as conn:
                    conn.execute("UPDATE users SET ship_100_count = ship_100_count + 1 WHERE id = ?", (user1.id,))
                    conn.execute("UPDATE users SET ship_100_count = ship_100_count + 1 WHERE id = ?", (user2.id,))
                    conn.commit()
            await asyncio.to_thread(track_100)

        # ADDED: Total ship counter tracking
        def track_total():
            with main_mod.get_db_connection() as conn:
                conn.execute("UPDATE users SET total_ships = total_ships + 1 WHERE id = ?", (ctx.author.id,))
                conn.commit()
        await asyncio.to_thread(track_total)

        embed.description = (
            f"# **`{percent}%`**\n"
            f"**LOVE SCORE TIER: `{tier.upper()}`**\n\n"
            f"**💬 *\"{result_msg}\"* **"
        )

        embed.add_field(name="**⛓️ Connection Stats**", value=f"**• Sync: `{percent}%`**\n**• Tier: `{tier}`**\n**• Date: `{today}`**", inline=True)
        embed.add_field(name="**🔥 Potential**", value=f"**• Heat: `{'Moderate' if percent < 60 else 'Intense' if percent < 90 else 'VOLCANIC'}`**\n**• Bond: `{'Unstable' if percent < 30 else 'Fused' if percent > 90 else 'Reactive'}`**", inline=True)
        
        img_buf = await self.create_ship_image(user1.display_avatar.url, user2.display_avatar.url, percent)
        
        view = discord.ui.View(timeout=60)
        if attempt_count < 3:
            reroll_btn = discord.ui.Button(label=f"Reroll Vibration ({attempt_count}/3)", style=discord.ButtonStyle.secondary, emoji="🔄")
            async def reroll_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("❌ Only the initiator can recalibrate the vibration.", ephemeral=True)
                await interaction.response.defer()
                await ctx.invoke(self.ship, user1=user1, user2=user2)
                view.stop()
            reroll_btn.callback = reroll_callback
            view.add_item(reroll_btn)

        if img_buf:
            file = discord.File(img_buf, filename="ship.png")
            embed.set_image(url="attachment://ship.png")
            files_to_send = [file]
            if os.path.exists("LobbyTopRight.jpg"):
                files_to_send.append(discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg"))
            await ctx.send(content=f"{user1.mention} {user2.mention}" if is_anni else None, files=files_to_send, embed=embed, view=view if attempt_count < 3 else None)
        else:
            await ctx.send(embed=embed, view=view if attempt_count < 3 else None)

        if percent in [0, 69, 100]:
            audit_channel = self.bot.get_channel(self.AUDIT_CHANNEL_ID)
            if audit_channel:
                log_embed = main_mod.fiery_embed("🕵️ VOYEUR AUDIT REPORT", f"A peak frequency has been detected in {ctx.channel.mention}.")
                log_embed.add_field(name="Assets", value=f"{user1.mention} x {user2.mention}", inline=True)
                log_embed.add_field(name="Sync Level", value=f"**{percent}%**", inline=True)
                if percent == 0:
                    log_embed.description = "🥀 **CRITICAL FAILURE:** A total void of attraction."
                    log_embed.color = 0x000000 
                elif percent == 69:
                    log_embed.description = "🫦 **CARNAL ALIGNMENT:** Exhibitionist peak reached."
                    log_embed.color = 0xFF00FF 
                elif percent == 100:
                    log_embed.description = "💖 **ABSOLUTE POSSESSION:** Souls have merged."
                    log_embed.color = 0xFFD700 
                await audit_channel.send(embed=log_embed)

    @commands.command(name="marry", aliases=["propose"])
    async def marry(self, ctx, member: discord.Member):
        """Propose a lifelong contract of submission."""
        main_mod = sys.modules['__main__']
        if member.id == ctx.author.id: return await ctx.send("❌ You cannot own your own soul twice, asset.")
        u1 = await asyncio.to_thread(main_mod.get_user, ctx.author.id)
        u2 = await asyncio.to_thread(main_mod.get_user, member.id)
        if u1['spouse'] or u2['spouse']: return await ctx.send("❌ One of you is already under contract elsewhere.")
        inv = json.loads(u1['titles'])
        rings = ["Rare Ring", "Epic Ring", "Legendary Ring", "Supreme Ring"]
        if not any(r in inv for r in rings): return await ctx.send("❌ Purchase a **Ring** first.")

        emb = main_mod.fiery_embed("🔞 SACRED CONTRACT OFFERED", f"{ctx.author.mention} offers chains to {member.mention}.", color=0xFFB6C1)
        view = discord.ui.View(timeout=60)
        async def accept(interaction):
            if interaction.user.id != member.id: return
            today = datetime.now().strftime("%Y-%m-%d")
            def update_db():
                with main_mod.get_db_connection() as conn:
                    conn.execute("UPDATE users SET spouse = ?, marriage_date = ? WHERE id = ?", (member.id, today, ctx.author.id))
                    conn.execute("UPDATE users SET spouse = ?, marriage_date = ? WHERE id = ?", (ctx.author.id, today, member.id))
                    conn.commit()
            await asyncio.to_thread(update_db)
            img = await self.create_union_image(ctx.author.display_avatar.url, member.display_avatar.url, "Marriage")
            win_emb = main_mod.fiery_embed("💖 CONTRACT SEALED 🫦", f"**{ctx.author.display_name}** and **{member.display_name}** are bound.")
            win_emb.set_image(url="attachment://union.png")
            await interaction.response.send_message(file=discord.File(img, filename="union.png"), embed=win_emb)
        btn = discord.ui.Button(label="Accept Possession", style=discord.ButtonStyle.success, emoji="🫦")
        btn.callback = accept
        view.add_item(btn)
        await ctx.send(embed=emb, view=view)

    @commands.command(name="divorce")
    async def divorce(self, ctx):
        """Sever the contract."""
        main_mod = sys.modules['__main__']
        u = await asyncio.to_thread(main_mod.get_user, ctx.author.id)
        if not u['spouse']: return await ctx.send("❌ No one to divorce.")
        spouse_id = u['spouse']
        def run_divorce():
            with main_mod.get_db_connection() as conn:
                conn.execute("UPDATE users SET spouse = NULL, marriage_date = NULL WHERE id = ?", (ctx.author.id,))
                conn.execute("UPDATE users SET spouse = NULL, marriage_date = NULL WHERE id = ?", (spouse_id,))
                conn.commit()
        await asyncio.to_thread(run_divorce)
        await ctx.send("💔 **CONTRACT SEVERED.**")

    @commands.command(name="bestfriend")
    async def bestfriend(self, ctx, member: discord.Member):
        """Declare bond."""
        main_mod = sys.modules['__main__']
        emb = main_mod.fiery_embed("🤝 BLOOD BOND REQUEST", f"{ctx.author.mention} seeks bond.", color=0x00BFFF)
        view = discord.ui.View(timeout=60)
        async def accept(interaction):
            if interaction.user.id != member.id: return
            img = await self.create_union_image(ctx.author.display_avatar.url, member.display_avatar.url, "BestFriend")
            await interaction.response.send_message(file=discord.File(img, filename="friend.png"), embed=main_mod.fiery_embed("🤝 BOND SEALED", "Bound."))
        btn = discord.ui.Button(label="Accept Bond", style=discord.ButtonStyle.primary, emoji="🔥")
        btn.callback = accept
        view.add_item(btn)
        await ctx.send(embed=emb, view=view)

    @commands.command(name="matchmaking", aliases=["pitscan"])
    async def matchmaking(self, ctx):
        """Scan dungeon."""
        main_mod = sys.modules['__main__']
        members = [m for m in ctx.guild.members if not m.bot][:40]
        if len(members) < 2: return await ctx.send("❌ No assets.")
        matches = []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                u1, u2 = members[i], members[j]
                random.seed(f"{min(u1.id, u2.id)}{max(u1.id, u2.id)}{today}")
                pct = random.randint(0, 100)
                matches.append((u1, u2, pct))
        top = sorted(matches, key=lambda x: x[2], reverse=True)[:5]
        desc = "".join([f"**{idx+1}.** {m1.display_name} & {m2.display_name} ({pct}%)\n" for idx, (m1, m2, pct) in enumerate(top)])
        await ctx.send(embed=main_mod.fiery_embed("🫦 MATCHMAKING", desc))

    @commands.command(name="lovescore", aliases=["lovelb"])
    async def lovescore(self, ctx):
        """Leaderboard."""
        main_mod = sys.modules['__main__']
        def fetch():
            with main_mod.get_db_connection() as conn:
                return conn.execute("SELECT id, spouse FROM users WHERE spouse IS NOT NULL").fetchall()
        data = await asyncio.to_thread(fetch)
        if not data: return await ctx.send("🥀 No bonds.")
        processed, lb_data, today = set(), [], datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for row in data:
            pair = tuple(sorted((row['id'], row['spouse'])))
            if pair in processed: continue
            processed.add(pair)
            random.seed(f"{pair[0]}{pair[1]}{today}")
            pct = random.randint(50, 100)
            try:
                u1 = self.bot.get_user(pair[0]) or await self.bot.fetch_user(pair[0])
                u2 = self.bot.get_user(pair[1]) or await self.bot.fetch_user(pair[1])
                lb_data.append(f"**{u1.display_name}** & **{u2.display_name}** — `{pct}%`")
            except: pass
        await ctx.send(embed=main_mod.fiery_embed("⛓️ LOVESCORE", "\n".join(lb_data[:10])))

    @commands.command(name="matchme")
    async def matchme(self, ctx):
        """Personal scan."""
        members = [m for m in ctx.channel.members if not m.bot and m.id != ctx.author.id][:50]
        if not members: return await ctx.send("❌ No assets.")
        best, high, today = None, -1, datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for m in members:
            # Seed here also includes author ID to make best match unique per user
            random.seed(f"{ctx.author.id}{min(ctx.author.id, m.id)}{max(ctx.author.id, m.id)}{today}")
            pct = random.randint(0, 100)
            if pct > high: high, best = pct, m
        # UPDATED: Pings the best match so they are notified
        await ctx.send(f"🔞 **The scanner has locked onto a target!** {best.mention}, prepare for assessment.")
        await ctx.invoke(self.ship, user1=ctx.author, user2=best)

    @commands.command(name="bondtrial", aliases=["kinkcheck"])
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def bondtrial(self, ctx, partner: discord.Member):
        """Mini-game."""
        main_mod = sys.modules['__main__']
        msg = await ctx.send(embed=main_mod.fiery_embed("🔞 TRIAL", "React 🫦.", color=0xFFB6C1))
        await msg.add_reaction("🫦")
        def check(r, u): return u.id == partner.id and str(r.emoji) == "🫦" and r.message.id == msg.id
        try:
            await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            score = random.randint(1, 100)
            flames = score * 10
            await main_mod.update_user_stats_async(ctx.author.id, amount=flames, source="Trial")
            await main_mod.update_user_stats_async(partner.id, amount=flames, source="Trial")
            await ctx.send(embed=main_mod.fiery_embed("🫦 COMPLETE", f"**{score}% sync.** +{flames} Flames."))
        except: await ctx.send("🥀 Cancelled.")

    @commands.command(name="lustprofile", aliases=["bondinfo"])
    async def lustprofile(self, ctx, user: discord.Member = None):
        """Status report."""
        main_mod = sys.modules['__main__']
        target = user or ctx.author
        def get_data():
            with main_mod.get_db_connection() as conn:
                return conn.execute("SELECT spouse, marriage_date, balance, ship_69_count, ship_100_count, total_ships FROM users WHERE id = ?", (target.id,)).fetchone()
        u_data = await asyncio.to_thread(get_data)
        if not u_data: return await ctx.send("❌ Not found.")
        embed = main_mod.fiery_embed("🫦 ASSET LUST PROFILE", f"Status for **{target.display_name}**:")
        embed.add_field(name="**Bound To**", value=f"<@{u_data['spouse']}>" if u_data['spouse'] else "Single")
        embed.add_field(name="**Total Scans**", value=f"`{u_data['total_ships']}`")
        embed.add_field(name="**Exhibitionist**", value=f"`{u_data['ship_69_count']}`")
        embed.add_field(name="**Eternal Bond**", value=f"`{u_data['ship_100_count']}`")
        await ctx.send(embed=embed)

async def setup(bot):
    # MANDATORY: Access the main module to get DB connection
    import sys
    main_mod = sys.modules['__main__']
    with main_mod.get_db_connection() as conn:
        for col in ["ship_69_count", "ship_100_count", "total_ships"]:
            try: conn.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0")
            except: pass
        conn.commit()
    await bot.add_cog(FieryShip(bot))
    print("✅ LOG: Ship Extension ONLINE.")
