import discord
from discord.ext import commands, tasks
import sqlite3
import json
import os
import random
import asyncio
import sys
from datetime import datetime, timedelta, timezone

class FieryExtensions(commands.Cog):
    def __init__(self, bot, get_db_connection, update_user_stats, fiery_embed, AUDIT_CHANNEL_ID):
        self.bot = bot
        self.get_db_connection = get_db_connection
        self.update_user_stats = update_user_stats
        self.fiery_embed = fiery_embed
        self.audit_channel_id = AUDIT_CHANNEL_ID
        self.pending_contracts = {}
        self.interaction_tracker = {} 
        
        # Legendary States
        self.is_blackout = False
        self.blackout_key_holder = None
        
        # ADDED: HEAT & MASTER PRESENCE (Fixes AttributeError in prizes.py)
        self.master_present = False
        self.heat_multiplier = 1.0

        # Exhibition Tracker
        self.last_nsfw_winner = None
        self.last_nsfw_recap = "No Hangrygames yet."
        
        # Start background loops
        self.quest_reset_loop.start()

    def cog_unload(self):
        self.quest_reset_loop.cancel()

    # ==========================================
    # 🔞 THE GRAND EXHIBITION (!nsfwtime)
    # ==========================================

    async def trigger_nsfw_start(self, ctx):
        embed = self.fiery_embed("The EchoGames", 
            "🔞 **NSFW PROTOCOL: ACTIVATED.**\n\n"
            "• **MULTIPLIER:** All Flames and XP are now **DOUBLE**.\n"
            "• **ECHOGAMES:** Winners may now `!flash` 3 victims.\n"
            "• **FIRST BLOOD:** Automatically stripped and exposed.\n\n"
            "*The Red Room is set to its most erotic frequency for the next 90 minutes.*")
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="nsfw_cover.jpg")
            embed.set_image(url="attachment://nsfw_cover.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

    @commands.command(name="flash")
    async def flash(self, ctx, victim1: discord.Member, victim2: discord.Member, victim3: discord.Member):
        """Allows the reigning champion to pick victims for a flash event during NSFW mode."""
        import sys
        main = sys.modules['__main__']
        if not main.nsfw_mode_active:
            return await ctx.send("The lights are normal. This level of exposure is forbidden right now.")
            
        embed = discord.Embed(title="🔞 THE ECHOGAMES RECAP 🔞", color=0xFF00FF)
        embed.set_author(name=f"Lead Echo Hangrygames: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        desc = (f"The Winner has opened the curtains. The following assets are currently on display for the Red Room's pleasure:\n\n"
                f"📸 **STAGE 1:** {victim1.mention}\n└ *Status:* **FLASH BABY**\n\n"
                f"📸 **STAGE 2:** {victim2.mention}\n└ *Status:* **CLOTHES OFF**\n\n"
                f"📸 **STAGE 3:** {victim3.mention}\n└ *Status:* **TEASE ME**\n\n"
                f" \"*'Look at them. Remember their name. This is the price of submission.'*\"")
        
        embed.description = desc
        self.last_nsfw_recap = f"Last Lead: {ctx.author.name} | Victims: {victim1.name}, {victim2.name}, {victim3.name}"
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="flash_thumb.jpg")
            embed.set_image(url="attachment://flash_thumb.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

        audit_chan = self.bot.get_channel(self.audit_channel_id)
        if audit_chan:
            log_emb = self.fiery_embed("📸 VOYEUR EXHIBITION AUDIT", f"A public exposure has been authorized by {ctx.author.mention}.")
            log_emb.description = f"🔞 **VOYEUR NOTE:** {ctx.author.display_name} has selected {victim1.display_name}, {victim2.display_name}, and {victim3.display_name} for total exposure. The cameras are recording their shame."
            log_emb.color = 0xFF00FF
            await audit_chan.send(embed=log_emb)

    # ==========================================
    # 🔥 HEAT SYSTEM (Used by !favor)
    # ==========================================

    async def activate_peak_heat(self, ctx):
        """Logic for Peak Heat triggered by !favor."""
        self.master_present = True
        self.heat_multiplier = 2.0
        await asyncio.sleep(3600) # Peak Heat lasts 1 hour
        self.master_present = False
        self.heat_multiplier = 1.0
        await ctx.send("🔥 **PEAK HEAT HAS COOLED.** Multipliers returning to normal.")

    def add_heat(self, amount):
        """Internal helper for heat accumulation."""
        pass

    # ==========================================
    # 💍 THE BINDING CONTRACT SYSTEM
    # ==========================================
    
    @commands.command(name="contract")
    async def contract(self, ctx, member: discord.Member, price: int):
        """Offer a 24h contract of total ownership to another soul."""
        if member.id == ctx.author.id:
            return await ctx.send("🫦 **You cannot collar yourself, little pet. Find a master or a toy.**")
        if price < 1000:
            return await ctx.send("⛓️ **The Master doesn't process soul-contracts for less than 1,000 Flames.**")

        with self.get_db_connection() as conn:
            dom = conn.execute("SELECT balance FROM users WHERE id=?", (ctx.author.id,)).fetchone()
            if not dom or dom['balance'] < price:
                return await ctx.send("❌ **Your vault is too empty to afford this level of possession.**")

        self.pending_contracts[member.id] = {"dom_id": ctx.author.id, "price": price}
        
        embed = self.fiery_embed("Binding Contract Offer", 
            f"🫦 {ctx.author.mention} is holding a cold iron collar open for {member.mention}.\n\n"
            f"🖤 **Lease Price:** {price} Flames\n"
            f"⏳ **Duration:** 24 Hours of Possession\n"
            f"📈 **Terms:** 20% of every moan and every Flame you earn flows to your Owner.\n\n"
            f"**{member.mention}, type `!accept` to feel the click of the lock.**")
        
        await ctx.send(member.mention, embed=embed)
        await self.increment_quest(ctx.author.id, "d3")

    @commands.command(name="accept")
    async def accept(self, ctx):
        """Accept the collar and the terms of the contract."""
        if ctx.author.id not in self.pending_contracts:
            return await ctx.send("⛓️ **No one is waiting to own you at the moment, toy.**")
        
        offer = self.pending_contracts.pop(ctx.author.id)
        dom_id = offer['dom_id']
        price = offer['price']
        
        with self.get_db_connection() as conn:
            dom_check = conn.execute("SELECT balance FROM users WHERE id=?", (dom_id,)).fetchone()
            if not dom_check or dom_check['balance'] < price:
                return await ctx.send("❌ **The Dominant can no longer afford the price of your submission.**")
            
            conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, dom_id))
            conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, ctx.author.id))
            
            expiry_dt = datetime.now(timezone.utc) + timedelta(hours=24)
            expiry = expiry_dt.isoformat()
            conn.execute("INSERT OR REPLACE INTO contracts (dominant_id, submissive_id, expiry) VALUES (?, ?, ?)", 
                         (dom_id, ctx.author.id, expiry))
            conn.commit()

        dom_user = await self.bot.fetch_user(dom_id)
        await ctx.send(embed=self.fiery_embed("Ownership Sealed", 
            f"🔞 **THE LOCK CLICKS.** {ctx.author.mention} is now the legal property of {dom_user.mention} for the next 24 hours.\n"
            f"The payment has been transferred to the new member.", color=0xFF0000))

        await self.increment_quest(ctx.author.id, "w4")

        audit_chan = self.bot.get_channel(self.audit_channel_id)
        if audit_chan:
            log_emb = self.fiery_embed("🕵️ VOYEUR CONTRACT AUDIT", f"A new soul has been collared.")
            log_emb.add_field(name="⛓️ Dominant", value=dom_user.mention, inline=True)
            log_emb.add_field(name="🫦 Submissive", value=ctx.author.mention, inline=True)
            log_emb.add_field(name="💰 Lease Price", value=f"{price:,} Flames", inline=True)
            log_emb.add_field(name="⏳ Expiry", value=f"<t:{int(expiry_dt.timestamp())}:R>", inline=True)
            log_emb.description = f"🔞 **VOYEUR NOTE:** {ctx.author.display_name} has accepted the terms of submission. 20% of their future earnings are now synchronized with {dom_user.display_name}'s vault."
            if os.path.exists("LobbyTopRight.jpg"):
                log_file = discord.File("LobbyTopRight.jpg", filename="audit_contract.jpg")
                log_emb.set_thumbnail(url="attachment://audit_contract.jpg")
                await audit_chan.send(file=log_file, embed=log_emb)
            else:
                await audit_chan.send(embed=log_emb)

    # ==========================================
    # 📸 THE VOYEUR'S HIDDEN GALLERY
    # ==========================================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        await self.increment_quest(message.author.id, "d16")
        if message.mentions:
            for m in message.mentions:
                await self.increment_quest(m.id, "w18")

        if not message.mentions: return
        for mentioned in message.mentions:
            if mentioned.id == message.author.id: continue
            pair = tuple(sorted((message.author.id, mentioned.id)))
            self.interaction_tracker[pair] = self.interaction_tracker.get(pair, 0) + 1

    @commands.command(name="gallery")
    async def gallery(self, ctx):
        """A peek into the most used toys and the highest tension in the pit."""
        with self.get_db_connection() as conn:
            # RESTRICTION: Only fetch users who are actually in the current server
            guild_member_ids = [m.id for m in ctx.guild.members]
            placeholders = ','.join(['?'] * len(guild_member_ids))
            recent_winners = conn.execute(f"SELECT id, wins, kills FROM users WHERE id IN ({placeholders}) AND wins > 0 ORDER BY wins DESC LIMIT 5", guild_member_ids).fetchall()
        
        # Sassy Intro
        desc = f"The voyeur cameras in **{ctx.guild.name}** are live. Some assets are performing... *exquisitely*.\n\n"
        
        embed = self.fiery_embed("💎 THE MASTER'S PRIVATE GALLERY", desc, color=0x800080)

        # Organized Leaders (Filtered by Guild)
        favorites = ""
        for i, row in enumerate(recent_winners, 1):
            m = ctx.guild.get_member(row['id'])
            name = m.display_name if m else f"Asset {row['id']}"
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "🔹")
            favorites += f"{medal} **{name}**\n└ *{row['wins']} Peaks reached | {row['kills']} Forced submissions*\n"
        
        embed.add_field(
            name="🏆 THE MASTER'S FAVORITES", 
            value=favorites if favorites else "*The podium is cold. No one is winning.*", 
            inline=False
        )
        
        # Tension Meter Visuals (Filtered by Guild)
        tension_list = ""
        # Only keep pairs where both members are in the current guild
        guild_pairs = {k: v for k, v in self.interaction_tracker.items() if k[0] in guild_member_ids and k[1] in guild_member_ids}
        sorted_pairs = sorted(guild_pairs.items(), key=lambda x: x[1], reverse=True)[:5]
        
        if not sorted_pairs:
            tension_list = "*The dungeon air is thin. No one is playing with others yet...*"
        else:
            total_interactions = sum(count for _, count in guild_pairs.items())
            for pair, count in sorted_pairs:
                u1, u2 = ctx.guild.get_member(pair[0]), ctx.guild.get_member(pair[1])
                tension_pct = int((count / total_interactions) * 100) if total_interactions > 0 else 0
                
                # Visual Tension Meter [■■■□□□]
                filled = "■" * (tension_pct // 10)
                empty = "□" * (10 - (tension_pct // 10))
                meter = f"[`{filled}{empty}`]"
                
                if u1 and u2: 
                    tension_list += f"💞 **{u1.display_name}** 🔗 **{u2.display_name}**\n└ {meter} **{tension_pct}% TENSION** ({count} pulses)\n"

        embed.add_field(
            name="🫦 VOYEUR'S LIVE FEED", 
            value=tension_list, 
            inline=False
        )

        embed.set_footer(text=f"🔞 RECORDED IN {ctx.guild.name.upper()} 🔞")

        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="gallery.jpg")
            embed.set_thumbnail(url="attachment://gallery.jpg")
            await ctx.send(file=file, embed=embed)
        else: await ctx.send(embed=embed)

    # ==========================================
    # 🌑 BLACKOUT & TRIAL SYSTEM (NO HEAT)
    # ==========================================

    @commands.command(name="search")
    async def search(self, ctx):
        """Search the dark dungeon during a Blackout."""
        if not self.is_blackout:
            return await ctx.send("The lights are on. There is no mystery to find here, toy.")
        
        roll = random.randint(1, 20)
        if roll == self.blackout_key_holder:
            self.is_blackout = False
            await self.update_user_stats(ctx.author.id, amount=100000, source="Found Master Keys")
            await ctx.send(embed=self.fiery_embed("KEY FOUND", f"🗝️ {ctx.author.mention} has found the Master's Keys in the dark! The lights flicker back on and they are rewarded with **100,000 Flames**!"))
            await self.increment_quest(ctx.author.id, "w20")

            audit_chan = self.bot.get_channel(self.audit_channel_id)
            if audit_chan:
                await audit_chan.send(f"💡 **BLACKOUT ENDED:** {ctx.author.display_name} found the Master Keys. Power restored.")
        else:
            await ctx.send(f"🌑 {ctx.author.mention} fumbles in the dark and finds nothing but cold chains.")

    @commands.command(name="trial")
    async def trial(self, ctx):
        """The Trial of the Masochist."""
        import sys
        main = sys.modules['__main__']
        user_data = main.get_user(ctx.author.id)
        if user_data['balance'] < 5000:
            return await ctx.send("You don't have enough Flames to stake your pride in this trial.")
            
        await ctx.send(f"⚖️ {ctx.author.mention}, the Trial begins. 5 waves of sensory overload. React with the emoji I show you within 2 seconds. **STAKE: 5,000 Flames.** Type `confirm` to bleed.")
        
        def check(m): return m.author == ctx.author and m.content.lower() == 'confirm'
        try:
            await self.bot.wait_for('message', check=check, timeout=15)
        except asyncio.TimeoutError:
            return await ctx.send("Cowardice is noted.")

        emojis = ["🫦", "⛓️", "🩸", "🔞", "🖤"]
        for i in range(5):
            target = random.choice(emojis)
            msg = await ctx.send(f"**WAVE {i+1}:** QUICK, SUBMIT TO THE {target}!")
            await msg.add_reaction(target)
            
            def react_check(reaction, user):
                return user == ctx.author and str(reaction.emoji) == target and reaction.message.id == msg.id
                
            try:
                await self.bot.wait_for('reaction_add', check=react_check, timeout=2.0)
            except asyncio.TimeoutError:
                await main.update_user_stats_async(ctx.author.id, amount=-5000, source="Failed Trial")
                audit_chan = self.bot.get_channel(self.audit_channel_id)
                if audit_chan:
                    log_emb = self.fiery_embed("🕵️ VOYEUR TRIAL AUDIT: BROKEN", f"An asset has failed the Trial of the Masochist.")
                    log_emb.add_field(name="🫦 Failed Asset", value=ctx.author.mention, inline=True)
                    log_emb.add_field(name="📉 Penalty", value="5,000 Flames Extracted", inline=True)
                    await audit_chan.send(embed=log_emb)
                return await ctx.send(f"❌ **BROKEN.** {ctx.author.mention} failed to react in time. 5,000 Flames lost.")

        await main.update_user_stats_async(ctx.author.id, amount=10000, xp_gain=5000, source="Passed Trial")
        await ctx.send(embed=self.fiery_embed("Trial Passed", f"🖤 {ctx.author.mention} has endured the Master's sensory Trial! They earn **10,000 Flames**.", color=0x00FF00))
        
        audit_chan = self.bot.get_channel(self.audit_channel_id)
        if audit_chan:
            log_emb = self.fiery_embed("🕵️ VOYEUR TRIAL AUDIT: ENDURED", f"An asset has passed the Trial.")
            await audit_chan.send(embed=log_emb)

    # ==========================================
    # 📜 THE MASTER'S LEDGER (QUESTS)
    # ==========================================

    @commands.command(name="quests")
    async def quests(self, ctx):
        """Check your progress on the daily and weekly demands."""
        u_id = ctx.author.id
        with self.get_db_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO quests (user_id) VALUES (?)", (u_id,))
            conn.commit()
            q = conn.execute("SELECT * FROM quests WHERE user_id = ?", (u_id,)).fetchone()

        embed = discord.Embed(title="📜 THE MASTER'S LEDGER: CLEAR DEMANDS", color=0xFFD700)
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="quest_top.jpg")
            embed.set_thumbnail(url="attachment://quest_top.jpg")

        d_tasks = [
            f"1. 🩸 **Force a Peak:** {q['d1']}/1 Kill in Arena", 
            f"2. 🎮 **Arena Hunger:** {q['d2']}/3 Games Played",
            f"3. 💍 **Offer a Collar:** {q['d3']}/1 `!contract` sent", 
            f"4. 🫦 **Groveling:** {q['d4']}/5 `!beg` uses",
            f"5. ⛓️ **Hard Service:** {q['d5']}/5 `!work` uses", 
            f"6. 🏆 **Top Authority:** {q['d6']}/1 Game Won",
            f"7. 🧪 **Lab Rat:** {q['d7']}/2 `!experiment` uses", 
            f"8. 💦 **Mopping Floors:** {q['d8']}/3 `!cumcleaner` uses",
            f"9. 👠 **Recruiting:** {q['d9']}/2 `!pimp` uses", 
            f"10. ❓ **Blind Obedience:** {q['d10']}/2 `!mystery` uses",
            f"11. 🫦 **Pure Tease:** {q['d11']}/5 `!flirt` uses", 
            f"12. 🔥 **Active Asset:** {q['d12']}/10 commands total",
            f"13. 🩸 **Fresh Meat:** {q['d13']}/1 First Blood in game", 
            f"14. 💀 **Total Yield:** {q['d14']}/2 Times defeated",
            f"15. 💰 **Wealth Gatherer:** {q['d15']}/1000 Flames earned", 
            f"16. 🫦 **Loud Toy:** {q['d16']}/10 chat messages sent",
            f"17. ⛓️ **Narcissist:** {q['d17']}/1 `!me` profile check", 
            f"18. 🔄 **Daily Dose:** {q['d18']}/1 `!daily` claimed",
            f"19. ⛓️ **Role Call:** {q['d19']}/1 Ping in a game lobby", 
            f"20. 🔞 **Full Session:** {q['d20']}/1 Game played"
        ]
        
        w_tasks = [
            f"1. 👑 **Master of Pit:** {q['w1']}/5 Wins total", 
            f"2. ⚔️ **Pride Shredder:** {q['w2']}/25 Arena Kills",
            f"3. 📈 **Arousal Streak:** {q['w3']}/3 Killstreak reached", 
            f"4. 🔒 **Soul Collector:** {q['w4']}/3 Contracts accepted",
            f"5. 🔗 **Career Slave:** {q['w5']}/30 `!work` commands", 
            f"6. 🔞 **Dungeon Fiend:** {q['w6']}/50 commands used",
            f"7. 💎 **Sultan of Flames:** {q['w7']}/10k total earnings", 
            f"8. ⛓️ **High Endurance:** {q['w8']}/10 Games joined",
            f"9. 🫦 **Golden Pet:** {q['w9']}/5 Top 5 placements", 
            f"10. 🥀 **Professional Flirt:** {q['w10']}/20 `!flirt` uses",
            f"11. 🧪 **Total Subject:** {q['w11']}/10 `!experiment` uses", 
            f"12. 💦 **Floor Manager:** {q['w12']}/15 `!cumcleaner` uses",
            f"13. 👠 **Dungeon Pimp:** {q['w13']}/10 `!pimp` uses", 
            f"14. 🕯️ **Mystery Seeker:** {q['w14']}/10 `!mystery` uses",
            f"15. 🫦 **Professional Beggar:** {q['w15']}/20 `!beg` uses", 
            f"16. 📅 **Hooked:** {q['w16']}/7 `!daily` claims",
            f"17. ⬆️ **Deepening Submission:** {q['w17']}/1 Level gained", 
            f"18. 👁️ **Public Interest:** {q['w18']}/50 Mentions in chat",
            f"19. 🌋 **Heat Chaser:** {q['w19']}/5 Heat Events triggered", 
            f"20. 🔞 **Legendary Presence:** {q['w20']}/1 Legendary Event"
        ]

        embed.add_field(name="🫦 THE DAILY DEGRADATION", value="\n".join(d_tasks[:10]), inline=True)
        embed.add_field(name="🫦 DAILY CONTINUED", value="\n".join(d_tasks[10:]), inline=True)
        embed.add_field(name="⛓️ THE WEEKLY ORDEAL", value="\n".join(w_tasks[:10]), inline=True)
        embed.add_field(name="⛓️ WEEKLY CONTINUED", value="\n".join(w_tasks[10:]), inline=True)
        embed.set_footer(text="🔞 THE MASTER IS ALWAYS WATCHING 🔞")

        if os.path.exists("LobbyTopRight.jpg"):
            await ctx.send(file=file, embed=embed)
        else: await ctx.send(embed=embed)

    @commands.command(name="questboard")
    async def quest_leaderboard(self, ctx):
        """Displays the Monthly Quest Leaderboard."""
        with self.get_db_connection() as conn:
            query = "SELECT user_id, (" + " + ".join([f"d{i}" for i in range(1, 21)]) + " + " + " + ".join([f"w{i}" for i in range(1, 21)]) + ") as total FROM quests WHERE user_id != 0 ORDER BY total DESC LIMIT 10"
            top_ten = conn.execute(query).fetchall()

        desc = "🏆 **MONTHLY SUBMISSION RANKINGS** 🏆\n\n"
        for i, row in enumerate(top_ten, 1):
            member = ctx.guild.get_member(row['user_id'])
            name = member.display_name if member else f"Asset {row['user_id']}"
            desc += f"{i}. **{name}**: {row['total']} Demands Met\n"
        
        embed = self.fiery_embed("Ledger Leaderboard", desc, color=0xFFD700)
        await ctx.send(embed=embed)

    # ==========================================
    # 🕒 BACKGROUND LOOPS (RESETS ONLY)
    # ==========================================

    @tasks.loop(minutes=30)
    async def quest_reset_loop(self):
        now = datetime.now(timezone.utc)
        with self.get_db_connection() as conn:
            last_reset_row = conn.execute("SELECT last_reset FROM quests WHERE user_id = 0").fetchone()
            if not last_reset_row:
                conn.execute("INSERT OR IGNORE INTO quests (user_id, last_reset) VALUES (0, ?)", (now.isoformat(),))
                conn.commit()
                return
            last_reset = datetime.fromisoformat(last_reset_row['last_reset'])

            if now.month != last_reset.month:
                query = "SELECT user_id FROM quests WHERE user_id != 0 ORDER BY (" + " + ".join([f"d{i}" for i in range(1, 21)]) + " + " + " + ".join([f"w{i}" for i in range(1, 21)]) + ") DESC LIMIT 10"
                winners = conn.execute(query).fetchall()
                prizes = [250000, 220000, 200000, 180000, 150000, 120000, 100000, 80000, 60000, 50000]
                recap = "🎊 **MONTHLY LEDGER PAYOUT!** 🎊\n\n"
                for idx, row in enumerate(winners):
                    prize = prizes[idx]
                    await self.update_user_stats(row['user_id'], amount=prize, source="Monthly Quest Leaderboard")
                    recap += f"Place #{idx+1}: <@{row['user_id']}> won {prize:,} Flames!\n"
                
                audit_chan = self.bot.get_channel(self.audit_channel_id)
                if audit_chan:
                    await audit_chan.send(embed=self.fiery_embed("Monthly Payout Recap", recap))
                conn.execute("UPDATE quests SET " + ", ".join([f"d{i}=0" for i in range(1, 21)]) + ", " + ", ".join([f"w{i}=0" for i in range(1, 21)]))

            if now.date() > last_reset.date():
                conn.execute("UPDATE quests SET " + ", ".join([f"d{i}=0" for i in range(1, 21)]))
                conn.execute("UPDATE quests SET last_reset = ? WHERE user_id = 0", (now.isoformat(),))
                audit_chan = self.bot.get_channel(self.audit_channel_id)
                if audit_chan:
                    await audit_chan.send("⛓️ **LEDGER WIPE:** Daily Ordeals reset.")

            if now.isoweekday() == 1 and now.isocalendar()[1] != last_reset.isocalendar()[1]:
                conn.execute("UPDATE quests SET " + ", ".join([f"w{i}=0" for i in range(1, 21)]))
                audit_chan = self.bot.get_channel(self.audit_channel_id)
                if audit_chan:
                    await audit_chan.send("🚨 **WEEKLY PURGE:** Weekly Ordeals reset.")
            conn.commit()

    @quest_reset_loop.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()

    # ==========================================
    # 🛠️ QUEST TRACKING LOGIC
    # ==========================================

    async def increment_quest(self, user_id, quest_key, amount=1):
        goals = {
            "d1": 1, "d2": 3, "d3": 1, "d4": 5, "d5": 5, "d6": 1, "d7": 2, "d8": 3, "d9": 2, "d10": 2,
            "d11": 5, "d12": 10, "d13": 1, "d14": 2, "d15": 1000, "d16": 10, "d17": 1, "d18": 1, "d19": 1, "d20": 1,
            "w1": 5, "w2": 25, "w3": 3, "w4": 3, "w5": 30, "w6": 50, "w7": 10000, "w8": 10, "w9": 5, "w10": 20,
            "w11": 10, "w12": 15, "w13": 10, "w14": 10, "w15": 20, "w16": 7, "w17": 1, "w18": 50, "w19": 5, "w20": 1
        }
        
        with self.get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("INSERT OR IGNORE INTO quests (user_id) VALUES (?)", (user_id,))
            res = conn.execute(f"SELECT {quest_key} FROM quests WHERE user_id = ?", (user_id,)).fetchone()
            current = res[0] if res else 0
            new_val = current + amount
            conn.execute(f"UPDATE quests SET {quest_key} = ? WHERE user_id = ?", (new_val, user_id))
            conn.commit()

            goal = goals.get(quest_key, 999999)
            if current < goal and new_val >= goal:
                is_weekly = quest_key.startswith('w')
                flames = 2000 if is_weekly else 250
                xp = 1000 if is_weekly else 100
                await self.update_user_stats(user_id, amount=flames, xp_gain=xp, source=f"Quest ({quest_key})")
                audit_chan = self.bot.get_channel(self.audit_channel_id)
                if audit_chan:
                    await audit_chan.send(embed=self.fiery_embed("📜 QUEST COMPLETED", f"<@{user_id}> completed a demand!"))

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        user_id = ctx.author.id
        cmd = ctx.command.name if ctx.command else None
        if not cmd: return
        
        await self.increment_quest(user_id, "d12")
        await self.increment_quest(user_id, "w6")

        mapping = {
            "beg": ["d4", "w15"], "work": ["d5", "w5"], "experiment": ["d7", "w11"],
            "cumcleaner": ["d8", "w12"], "pimp": ["d9", "w13"], "mystery": ["d10", "w14"],
            "flirt": ["d11", "w10"], "me": ["d17"], "daily": ["d18", "w16"]
        }
        
        if cmd in mapping:
            for key in mapping[cmd]:
                await self.increment_quest(user_id, key)

async def setup(bot):
    import sys
    main = sys.modules['__main__']
    await bot.add_cog(FieryExtensions(bot, main.get_db_connection, main.update_user_stats_async, main.fiery_embed, main.AUDIT_CHANNEL_ID))
