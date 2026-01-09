import discord
from discord.ext import commands
import random
import io
import aiohttp
import sys
import json
import os
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageOps, ImageFilter

class FieryShip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
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
                "They have survived the pit and found heaven in the dark.",
                "The chains have turned to gold. A perfect 100.",
                "There are no more users, only {u1} and {u2} One."
            ]
        }
        self.AUDIT_CHANNEL_ID = 1438810509322223677

    async def create_ship_image(self, u1_url, u2_url, percent):
        """Generates visual match with SQUARE avatars and high-visibility central green ruler."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(u1_url) as r1, session.get(u2_url) as r2:
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())

            # --- RESETTING LAYOUT ---
            canvas_width = 1200
            canvas_height = 700
            
            # Use shipbg.jpg as background
            if os.path.exists("shipbg.jpg"):
                canvas = Image.open("shipbg.jpg").convert("RGBA").resize((canvas_width, canvas_height))
            else:
                canvas = Image.new("RGBA", (canvas_width, canvas_height), (10, 0, 5, 255))
                
            draw = ImageDraw.Draw(canvas)

            # BIGGER SQUARE AVATARS: Set to 400px
            av_size = 400
            av1_img = Image.open(p1_data).convert("RGBA").resize((av_size, av_size))
            av2_img = Image.open(p2_data).convert("RGBA").resize((av_size, av_size))

            def apply_erotic_frame_square(avatar, color, pulse_intensity=3):
                glow_size = av_size + 80
                glow = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
                draw_g = ImageDraw.Draw(glow)
                glow_range = 20 + pulse_intensity 
                for i in range(glow_range, 0, -1):
                    alpha = int(220 * (1 - i/glow_range))
                    draw_g.rectangle([i, i, glow_size-i, glow_size-i], outline=(*color, alpha), width=5)
                glow.paste(avatar, (40, 40), avatar)
                return glow

            frame_color = (255, 20, 147) # Hot Pink
            pulse = int((percent / 100) * 10) 
            
            if percent == 69: frame_color = (255, 0, 255) 
            elif percent >= 90: frame_color = (255, 0, 80) 

            av1_framed = apply_erotic_frame_square(av1_img, frame_color, pulse)
            av2_framed = apply_erotic_frame_square(av2_img, frame_color, pulse)

            # Paste SQUARE Avatars on the sides
            canvas.paste(av1_framed, (20, 150), av1_framed)
            canvas.paste(av2_framed, (canvas_width - av_size - 100, 150), av2_framed)

            # --- THE CENTRAL RULER (DOMINANT FEATURE) ---
            col_x, col_y, col_w, col_h = (canvas_width // 2) - 60, 120, 120, 480
            light_green = (50, 255, 50) # High-Visibility Vibrant Green
            
            draw.rectangle([col_x, col_y, col_x + col_w, col_y + col_h], fill=(20, 20, 20, 200), outline=(255, 255, 255), width=5)
            
            fill_height = (percent / 100) * col_h
            if percent > 0:
                draw.rectangle([col_x + 8, (col_y + col_h) - fill_height, col_x + col_w - 8, col_y + col_h - 8], fill=light_green)

            # MASSIVE PERCENTAGE TEXT
            score_text = f"{percent}%"
            draw.text(((canvas_width // 2) - 80, 20), score_text, fill=(255, 255, 255), stroke_width=10, stroke_fill=(0,0,0))

            # --- REMOVED: Bottom Progress Bar Section ---
            
            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"Fiery Ship Error: {e}")
            return None

    async def create_union_image(self, u1_url, u2_url, bond_type="Marriage"):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(u1_url) as r1, session.get(u2_url) as r2:
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())
            
            bg_color = (255, 20, 147, 40) if "Anniversary" in bond_type else (25, 0, 0, 255)
            canvas = Image.new("RGBA", (1000, 500), bg_color)
            av1 = Image.open(p1_data).convert("RGBA").resize((320, 320))
            av2 = Image.open(p2_data).convert("RGBA").resize((320, 320))
            
            draw = ImageDraw.Draw(canvas)
            if "Anniversary" in bond_type:
                for _ in range(30):
                    x, y = random.randint(0, 1000), random.randint(0, 500)
                    draw.text((x, y), "💕", fill=(255, 105, 180))

            canvas.paste(av1, (100, 90), av1)
            canvas.paste(av2, (580, 90), av2)
            
            icon = "⛓️🫦⛓️" if bond_type == "Marriage" else "🤝🔥🤝"
            if "Anniversary" in bond_type: icon = "💖🔥🔞"
            draw.text((440, 210), icon, fill=(255, 255, 255))
            
            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            buf.seek(0)
            return buf
        except: return None

    @commands.command(name="ship")
    async def ship(self, ctx, user1: discord.Member, user2: discord.Member = None):
        """LEGENDARY SHIP: {u1} x {u2}"""
        if user2 is None:
            user2 = user1
            user1 = ctx.author

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        seed_str = f"{min(user1.id, user2.id)}{max(user1.id, user2.id)}{today}"
        random.seed(seed_str)
        percent = random.randint(0, 100)
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
        
        u1_data = main_mod.get_user(user1.id)
        is_anni = False
        if u1_data['spouse'] == user2.id and u1_data['marriage_date']:
            m_date = datetime.strptime(u1_data['marriage_date'], "%Y-%m-%d")
            now_dt = datetime.now()
            if m_date.day == now_dt.day and m_date.month != now_dt.month:
                is_anni = True

        embed = main_mod.fiery_embed("🔞 SOUL SYNCHRONIZATION 🔞", f"**Assets Involved:** {user1.mention} & {user2.mention}")
        
        if is_anni:
            embed.title = "🔞 HOT PINK ANNIVERSARY 🔞"
            result_msg = f"💖 **1 MONTH MILESTONE!** {result_msg}\n\n🔥 **DOUBLE REWARDS ACTIVE:** You both gain 2x XP and Flames today!"
            embed.color = 0xFF1493 

        if percent == 69: 
            embed.title = "🫦 EXHIBITIONIST PEAK REACHED 🫦"
            await main_mod.update_user_stats_async(user1.id, amount=2500, source="Ship 69% Bonus")
            await main_mod.update_user_stats_async(user2.id, amount=2500, source="Ship 69% Bonus")
            result_msg += "\n\n💰 **EXHIBITION REWARD:** The dungeon provides **2,500 Flames** for the show!"

        embed.add_field(name=f"📊 Compatibility: {percent}%", value=f"*{result_msg}*", inline=False)
        
        img_buf = await self.create_ship_image(user1.display_avatar.url, user2.display_avatar.url, percent)
        if img_buf:
            file = discord.File(img_buf, filename="ship.png")
            embed.set_image(url="attachment://ship.png")
            
            files_to_send = [file]
            if os.path.exists("LobbyTopRight.jpg"):
                files_to_send.append(discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg"))
            
            await ctx.send(content=f"{user1.mention} {user2.mention}" if is_anni else None, files=files_to_send, embed=embed)
        else:
            await ctx.send(embed=embed)

        if percent in [0, 69, 100]:
            audit_channel = self.bot.get_channel(self.AUDIT_CHANNEL_ID)
            if audit_channel:
                log_embed = main_mod.fiery_embed("🕵️ VOYEUR AUDIT REPORT", f"A peak frequency has been detected in {ctx.channel.mention}.")
                log_embed.add_field(name="Assets", value=f"{user1.mention} x {user2.mention}", inline=True)
                log_embed.add_field(name="Sync Level", value=f"**{percent}%**", inline=True)
                
                if percent == 0:
                    log_embed.description = "🥀 **CRITICAL FAILURE:** A total void of attraction. The assets are completely incompatible."
                    log_embed.color = 0x000000 
                elif percent == 69:
                    log_embed.description = "🫦 **CARNAL ALIGNMENT:** Exhibitionist peak reached. 2,500 Flames distributed to each asset."
                    log_embed.color = 0xFF00FF 
                elif percent == 100:
                    log_embed.description = "💖 **ABSOLUTE POSSESSION:** Souls have merged. The contract is permanent."
                    log_embed.color = 0xFFD700 
                
                await audit_channel.send(embed=log_embed)

    @commands.command(name="marry", aliases=["propose"])
    async def marry(self, ctx, member: discord.Member):
        """Propose a lifelong contract of submission."""
        main_mod = sys.modules['__main__']
        if member.id == ctx.author.id: return await ctx.send("❌ You cannot own your own soul twice, asset.")
        
        u1 = main_mod.get_user(ctx.author.id)
        u2 = main_mod.get_user(member.id)
        
        if u1['spouse'] or u2['spouse']:
            return await ctx.send("❌ One of you is already under contract elsewhere.")
            
        inv = json.loads(u1['titles'])
        rings = ["Rare Ring", "Epic Ring", "Legendary Ring", "Supreme Ring"]
        has_ring = any(r in inv for r in rings)
        
        if not has_ring:
            return await ctx.send("❌ You cannot propose empty-handed. Purchase a **Ring** from the Market first.")

        emb = main_mod.fiery_embed("🔞 SACRED CONTRACT OFFERED", f"{ctx.author.mention} is offering their soul and a ring to {member.mention}.\n\nDo you accept these chains?", color=0xFF1493)
        view = discord.ui.View(timeout=60)
        
        async def accept(interaction):
            if interaction.user.id != member.id: return
            today = datetime.now().strftime("%Y-%m-%d")
            with main_mod.get_db_connection() as conn:
                conn.execute("UPDATE users SET spouse = ?, marriage_date = ? WHERE id = ?", (member.id, today, ctx.author.id))
                conn.execute("UPDATE users SET spouse = ?, marriage_date = ? WHERE id = ?", (ctx.author.id, today, member.id))
                conn.commit()
            
            img = await self.create_union_image(ctx.author.display_avatar.url, member.display_avatar.url, "Marriage")
            file = discord.File(img, filename="union.png")
            win_emb = main_mod.fiery_embed("💖 CONTRACT SEALED 🫦", f"The Master has signed the decree. **{ctx.author.display_name}** and **{member.display_name}** are officially bound.\n\nThey now share a single heartbeat in the dark.", color=0xFFD700)
            win_emb.set_image(url="attachment://union.png")
            
            files_to_send = [file]
            if os.path.exists("LobbyTopRight.jpg"):
                files_to_send.append(discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg"))
            
            await interaction.response.send_message(files=files_to_send, embed=win_emb)
            
            audit_channel = self.bot.get_channel(self.AUDIT_CHANNEL_ID)
            if audit_channel:
                log_emb = main_mod.fiery_embed("💍 VOYEUR UNION AUDIT", f"A permanent synchronization has been achieved.")
                log_emb.add_field(name="Dominant/Partner", value=ctx.author.mention, inline=True)
                log_emb.add_field(name="Submissive/Partner", value=member.mention, inline=True)
                log_emb.description = f"🔞 **VOYEUR NOTE:** {ctx.author.display_name} and {member.display_name} have sealed their fates. The Red Room records their eternal bond."
                await audit_channel.send(embed=log_emb)
            view.stop()

        btn = discord.ui.Button(label="Accept Possession", style=discord.ButtonStyle.success, emoji="🫦")
        btn.callback = accept
        view.add_item(btn)
        await ctx.send(embed=emb, view=view)

    @commands.command(name="divorce")
    async def divorce(self, ctx):
        """Sever the contract and return to the pit alone."""
        main_mod = sys.modules['__main__']
        u = main_mod.get_user(ctx.author.id)
        if not u['spouse']: return await ctx.send("❌ You have no one to divorce, pet.")
        
        spouse_id = u['spouse']
        with main_mod.get_db_connection() as conn:
            conn.execute("UPDATE users SET spouse = NULL, marriage_date = NULL WHERE id = ?", (ctx.author.id,))
            conn.execute("UPDATE users SET spouse = NULL, marriage_date = NULL WHERE id = ?", (spouse_id,))
            conn.commit()
            
        embed = main_mod.fiery_embed("💔 CONTRACT SEVERED", f"You and <@{spouse_id}> are now strangers in the shadows.\n\nThe Red Room consumes another failed union.")
        if os.path.exists("LobbyTopRight.jpg"):
             file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
             embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
             await ctx.send(file=file, embed=embed)
        else:
             await ctx.send(embed=embed)
        
        audit_channel = self.bot.get_channel(self.AUDIT_CHANNEL_ID)
        if audit_channel:
            log_emb = main_mod.fiery_embed("💔 VOYEUR SEVERANCE AUDIT", f"A synchronization has been shattered.")
            log_emb.add_field(name="Asset One", value=ctx.author.mention, inline=True)
            log_emb.add_field(name="Asset Two", value=f"<@{spouse_id}>", inline=True)
            log_emb.description = f"🥀 **VOYEUR NOTE:** The contract between these assets has been nullified. They return to the dungeon floor as solitary figures."
            await audit_channel.send(embed=log_emb)

    @commands.command(name="bestfriend")
    async def bestfriend(self, ctx, member: discord.Member):
        """Declare a platonic blood-bond."""
        main_mod = sys.modules['__main__']
        if member.id == ctx.author.id: return await ctx.send("❌ Self-bestfriends are not authorized.")
        
        emb = main_mod.fiery_embed("🤝 BLOOD BOND REQUEST", f"{ctx.author.mention} wants to seal a blood-bond with you. Accept?", color=0x00BFFF)
        view = discord.ui.View(timeout=60)
        
        async def accept(interaction):
            if interaction.user.id != member.id: return
            img = await self.create_union_image(ctx.author.display_avatar.url, member.display_avatar.url, "BestFriend")
            file = discord.File(img, filename="friend.png")
            win_emb = main_mod.fiery_embed("🤝 BLOOD BOND SEALED", f"**{ctx.author.display_name}** and **{member.display_name}** are now Blood-Bound Best Friends!")
            win_emb.set_image(url="attachment://friend.png")
            if os.path.exists("LobbyTopRight.jpg"):
                 thumb_file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
                 await interaction.response.send_message(files=[file, thumb_file], embed=win_emb)
            else:
                 await interaction.response.send_message(file=file, embed=win_emb)
            
            audit_channel = self.bot.get_channel(self.AUDIT_CHANNEL_ID)
            if audit_channel:
                log_emb = main_mod.fiery_embed("🤝 VOYEUR ALLIANCE AUDIT", f"A new blood-bond has been formed.")
                log_emb.add_field(name="Ally One", value=ctx.author.mention, inline=True)
                log_emb.add_field(name="Ally Two", value=member.mention, inline=True)
                log_emb.description = f"🔥 **VOYEUR NOTE:** {ctx.author.display_name} and {member.display_name} have shared blood. A platonic alliance is recorded."
                await audit_channel.send(embed=log_emb)
            view.stop()

        btn = discord.ui.Button(label="Accept Bond", style=discord.ButtonStyle.primary, emoji="🔥")
        btn.callback = accept
        view.add_item(btn)
        await ctx.send(embed=emb, view=view)

    @commands.command(name="matchmaking", aliases=["pitscan"])
    async def matchmaking(self, ctx):
        """Scans the dungeon for the highest compatibility pairs of the day."""
        main_mod = sys.modules['__main__']
        await ctx.send("👁️ **The Master's Voyeurs are scanning the pit for erotic frequencies...**")
        members = [m for m in ctx.channel.members if not m.bot][:40]
        if len(members) < 2:
            return await ctx.send("❌ Not enough assets in this sector to scan.")

        matches = []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                u1, u2 = members[i], members[j]
                seed_str = f"{min(u1.id, u2.id)}{max(u1.id, u2.id)}{today}"
                random.seed(seed_str)
                percent = random.randint(0, 100)
                random.seed()
                matches.append((u1, u2, percent))

        top_matches = sorted(matches, key=lambda x: x[2], reverse=True)[:5]
        embed = main_mod.fiery_embed("🫦 THE MASTER'S MATCHMAKING 🫦", "Scanning current vibrations for peak exhibition:")
        description = ""
        for idx, (m1, m2, pct) in enumerate(top_matches, 1):
            icon = "⛓️"
            if pct >= 69: icon = "🔞"
            if pct == 100: icon = "💖"
            description += f"**{idx}.** {icon} {m1.mention} + {m2.mention} — **{pct}% Sync**\n"
        embed.description = description
        embed.set_footer(text="The dungeon floor is heating up. Watch and learn.")
        if os.path.exists("LobbyTopRight.jpg"):
             file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
             embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
             await ctx.send(file=file, embed=embed)
        else:
             await ctx.send(embed=embed)

    @commands.command(name="lovescore", aliases=["lovelb"])
    async def lovescore(self, ctx):
        """Displays the most powerful and synchronized bonds in the dungeon."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            data = conn.execute("SELECT id, spouse FROM users WHERE spouse IS NOT NULL").fetchall()
        
        if not data:
            return await ctx.send("🥀 **The Master finds no sacred bonds in the current sector. Propose a contract!**")

        processed = set()
        leaderboard_data = []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for row in data:
            u_id = row['id']
            s_id = row['spouse']
            pair = tuple(sorted((u_id, s_id)))
            if pair in processed: continue
            processed.add(pair)
            random.seed(f"{pair[0]}{pair[1]}{today}")
            pct = random.randint(50, 100)
            random.seed()
            
            try:
                u_user = await self.bot.fetch_user(pair[0])
                s_user = await self.bot.fetch_user(pair[1])
                u_name = u_user.name
                s_user_name = s_user.name
                leaderboard_data.append((u_name, s_user_name, pct))
            except: pass

        leaderboard_data.sort(key=lambda x: x[2], reverse=True)
        embed = main_mod.fiery_embed("⛓️ THE MASTER'S LOVESCORE 💍", "The most synchronized and submissive bonds today:")
        description = ""
        for idx, (n1, n2, pct) in enumerate(leaderboard_data[:10], 1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else "🔥"
            description += f"{medal} **{n1}** & **{n2}** — `{pct}% Resonance`\n"
        embed.description = description
        if os.path.exists("LobbyTopRight.jpg"):
             file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
             embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
             await ctx.send(file=file, embed=embed)
        else:
             await ctx.send(embed=embed)

    @commands.command(name="matchme")
    async def matchme(self, ctx):
        """Finds your personal highest-rated partner in this channel."""
        members = [m for m in ctx.channel.members if not m.bot and m.id != ctx.author.id][:50]
        if not members:
            return await ctx.send("❌ No compatible assets detected in range.")
        best_partner = None
        highest_pct = -1
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for m in members:
            seed_str = f"{min(ctx.author.id, m.id)}{max(ctx.author.id, m.id)}{today}"
            random.seed(seed_str)
            pct = random.randint(0, 100)
            random.seed()
            if pct > highest_pct:
                highest_pct = pct
                best_partner = m
        await ctx.invoke(self.ship, user1=ctx.author, user2=best_partner)

    @commands.command(name="bondtrial", aliases=["kinkcheck"])
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def bondtrial(self, ctx, partner: discord.Member):
        """Put your bond to the test in an erotic mini-game."""
        main_mod = sys.modules['__main__']
        if partner.id == ctx.author.id:
            return await ctx.send("❌ Solitary play is for the cells. Find a partner for the trials.")
            
        embed = main_mod.fiery_embed("🔞 THE EXHIBITIONIST TRIAL 🔞", 
            f"{ctx.author.mention} and {partner.mention} have been selected for the stage.\n\n"
            "**The Task:** Sync your moans to the Master's rhythm.\n"
            "**React with 🫦 to begin the show!**", color=0xFF0000)
        
        if os.path.exists("LobbyTopRight.jpg"):
             file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
             embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
             msg = await ctx.send(file=file, embed=embed)
        else:
             msg = await ctx.send(embed=embed)
             
        await msg.add_reaction("🫦")

        def check(reaction, user):
            return user.id == partner.id and str(reaction.emoji) == "🫦" and reaction.message.id == msg.id

        try:
            await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            score = random.randint(1, 100)
            flames = score * 10
            
            res_emb = main_mod.fiery_embed("🫦 TRIAL COMPLETE 🫦", 
                f"The audience is breathless. {ctx.author.mention} & {partner.mention} performed with **{score}% synchronization**.\n\n"
                f"💰 **FLAME HARVEST:** +{flames} Flames added to both accounts.\n\n"
                f"The exhibition has yielded a rich harvest of neural XP.")
            
            await main_mod.update_user_stats_async(ctx.author.id, amount=flames, source="Trial Completion")
            await main_mod.update_user_stats_async(partner.id, amount=flames, source="Trial Completion")
            if os.path.exists("LobbyTopRight.jpg"):
                file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
                res_emb.set_thumbnail(url="attachment://LobbyTopRight.jpg")
                await ctx.send(file=file, embed=res_emb)
            else:
                await ctx.send(embed=res_emb)
            
        except:
            await ctx.send(f"🥀 {partner.mention} was too shy for the stage. The trial is cancelled.")

    @commands.command(name="lustprofile", aliases=["bondinfo"])
    async def lustprofile(self, ctx, user: discord.Member = None):
        """Check the status of your chains and bond level."""
        main_mod = sys.modules['__main__']
        target = user or ctx.author
        u_data = main_mod.get_user(target.id)
        
        spouse_ment = f"<@{u_data['spouse']}>" if u_data['spouse'] else "None (Single Asset)"
        m_date = u_data['marriage_date'] or "N/A"
        bond_lv = (u_data['balance'] // 10000) + 1
        
        embed = main_mod.fiery_embed("🫦 ASSET LUST PROFILE 🫦", f"Status report for {target.mention}:")
        embed.add_field(name="⛓️ Bound To", value=spouse_ment, inline=True)
        embed.add_field(name="📅 Contract Signed", value=m_date, inline=True)
        embed.add_field(name="🔥 Lust Potency (Level)", value=f"Level {bond_lv}", inline=False)
        
        if u_data['spouse']:
            embed.set_footer(text="Your chains are heavy, but your resonance is eternal.")
        else:
            embed.set_footer(text="A wandering soul. Use !matchme to find a Master or a Pet.")
            
        if os.path.exists("LobbyTopRight.jpg"):
             file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
             embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
             await ctx.send(file=file, embed=embed)
        else:
             await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(FieryShip(bot))
    print("✅ LOG: Ship Extension (Soul Synchronization) is ONLINE.")
