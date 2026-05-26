# FIX: Python 3.13 compatibility shim for audioop
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
from discord.ext import commands, tasks
import random
import sqlite3
import os
import asyncio
import json
import traceback
import sys
from PIL import Image, ImageDraw, ImageOps, ImageEnhance
import io
import aiohttp

# Importação do Lexicon SFW para as frases de efeito
from lexiconsfw import FieryLexiconSFW

class WinnerDetailsViewSFW(discord.ui.View):
    def __init__(self, details_embed):
        super().__init__(timeout=None)
        self.details_embed = details_embed

    @discord.ui.button(label="View Full Breakdown", style=discord.ButtonStyle.primary, emoji="📜", custom_id="sfw_winner_details")
    async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=self.details_embed, ephemeral=True)

class LobbyViewSFW(discord.ui.View):
    def __init__(self, owner=None, edition=0, guild_id=None):
        super().__init__(timeout=None)
        self.owner = owner
        self.edition = edition
        self.guild_id = guild_id
        self.participants = []
        self.active = True 
        
        # --- ADDED: Persistence Rehydration ---
        if self.guild_id:
            try:
                import sys as _sys
                main = _sys.modules['__main__']
                with main.get_db_connection() as conn:
                    # Use SFW table
                    conn.execute("CREATE TABLE IF NOT EXISTS sfw_lobby_participants (guild_id INTEGER, user_id INTEGER)")
                    rows = conn.execute("SELECT user_id FROM sfw_lobby_participants WHERE guild_id = ?", (self.guild_id,)).fetchall()
                    self.participants = [r[0] for r in rows]
            except Exception as e:
                print(f"Rehydration Error: {e}")

    @discord.ui.button(label="Enter the Arena", style=discord.ButtonStyle.success, emoji="⚔️", custom_id="sfw_join_button")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            return await interaction.response.send_message("❌ **The gates are locked.** The session has already begun.", ephemeral=True)

        engine = interaction.client.get_cog("IgnisEngineSFW")
        if not engine: return

        # PERSISTENCE LOGIC: Add to DB and Local List
        with engine.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sfw_lobby_participants (guild_id INTEGER, user_id INTEGER)")
            check = conn.execute("SELECT 1 FROM sfw_lobby_participants WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, interaction.user.id)).fetchone()
            if check:
                return await interaction.response.send_message("🛡️ **You are already registered in the Arena.** There is no escape now.", ephemeral=True)
            
            conn.execute("INSERT INTO sfw_lobby_participants (guild_id, user_id) VALUES (?, ?)", (interaction.guild.id, interaction.user.id))
            conn.commit()

        # Update local list from DB to ensure sync after restart
        with engine.get_db_connection() as conn:
            rows = engine.get_db_connection().execute("SELECT user_id FROM sfw_lobby_participants WHERE guild_id = ?", (interaction.guild.id,)).fetchall()
            self.participants = [r[0] for r in rows]
        
        try:
            embed = interaction.message.embeds[0]
            embed.set_field_at(0, name=f"🧙‍♂️ {len(self.participants)} Fighters Ready", value="*Final checks on armor, weapons, and provisions..*", inline=False)
            
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.followup.send("⚔️ **The gates lock in place.** You have successfully entered the Arena.", ephemeral=True)
        except Exception as e:
            print(f"Lobby Join Error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("The Guild acknowledges your signin but the ledger glitched. You are joined!", ephemeral=True)
            else:
                await interaction.followup.send("The Guild acknowledges your signin but the ledger glitched. You are joined!", ephemeral=True)

    @discord.ui.button(label="Start the Games", style=discord.ButtonStyle.danger, emoji="🏁", custom_id="sfw_start_button")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        engine = interaction.client.get_cog("IgnisEngineSFW")
        if not engine:
            for name, cog in interaction.client.cogs.items():
                if "ignisenginesfw" in name.lower():
                    engine = cog
                    break

        if not engine: print("DEBUG: IgnisEngineSFW Cog NOT FOUND during button click.")
        
        ignis_admin_role_id = None
        if engine:
            with engine.get_db_connection() as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS sfw_ignis_settings (guild_id INTEGER PRIMARY KEY, role_id INTEGER)")
                row = conn.execute("SELECT role_id FROM sfw_ignis_settings WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
                if row: ignis_admin_role_id = row[0]

        is_staff = any(role.name in ["Staff", "Admin", "Moderator"] or role.id == ignis_admin_role_id for role in getattr(interaction.user, 'roles', []))
        
        owner_id = getattr(self.owner, 'id', None)
        
        if owner_id and interaction.user.id != owner_id and not is_staff:
            return await interaction.followup.send("Only the Hosts or Staff start the games!", ephemeral=True)
        
        with engine.get_db_connection() as conn:
            rows = conn.execute("SELECT user_id FROM sfw_lobby_participants WHERE guild_id = ?", (interaction.guild.id,)).fetchall()
            self.participants = [r[0] for r in rows]

        if len(self.participants) < 2:
            return await interaction.followup.send("Need at least 2 brave souls!", ephemeral=True)
        
        if not engine:
            engine = interaction.client.get_cog("IgnisEngineSFW")
        
        if engine: 
            guild_games = 0
            for channel_id in engine.active_battles:
                ch = interaction.client.get_channel(channel_id)
                if ch and ch.guild and ch.guild.id == interaction.guild.id:
                    guild_games += 1
            
            if guild_games >= 2:
                return await interaction.followup.send("❌ **The Arena is at capacity in this server.** Only 2 games can run at once here.", ephemeral=True)

            self.active = False

            if interaction.guild.id in engine.current_lobbies:
                del engine.current_lobbies[interaction.guild.id]

            with engine.get_db_connection() as conn:
                conn.execute("DELETE FROM sfw_lobby_participants WHERE guild_id = ?", (interaction.guild.id,))
                conn.commit()
            
            await interaction.channel.send("⚔️ **THE GATES OPEN... ECHO HANGRYGAMES SFW EDITION HAS BEGUN!**")
            
            import sys as _sys_m
            main_mod = _sys_m.modules['__main__']
            final_edition = self.edition if self.edition != 0 else getattr(main_mod, "game_edition", 1)
            asyncio.create_task(engine.start_battle(interaction.channel, list(self.participants), final_edition))
            self.stop()
        else:
            return await interaction.followup.send("❌ Error: IgnisEngineSFW not found. Is it loaded? Check bot logs.", ephemeral=True)

class FieryExtensionsSFW(commands.Cog):
    def __init__(self, bot, get_db_connection, update_user_stats, fiery_embed, AUDIT_CHANNEL_ID):
        self.bot = bot
        self.get_db_connection = get_db_connection
        self.update_user_stats = update_user_stats
        self.fiery_embed = fiery_embed
        self.audit_channel_id = AUDIT_CHANNEL_ID
        self.pending_contracts = {}
        self.interaction_tracker = {} 
        
        self.is_blackout = False
        self.blackout_key_holder = None
        
        self.master_present = False
        self.heat_multiplier = 1.0

        self.last_nsfw_winner = None
        self.last_nsfw_recap = "No Hangrygames yet."
        
        self.sfw_quest_reset_loop.start()
        
        self._prepare_tension_db()

    def _prepare_tension_db(self):
        with self.get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sfw_tension (
                    pair_key TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    last_interaction TIMESTAMP
                )
            """)
            conn.commit()

    def cog_unload(self):
        self.sfw_quest_reset_loop.cancel()

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
    # 💍 THE BINDING CONTRACT SYSTEM (SFW)
    # ==========================================
    
    @commands.command(name="sfwcontract")
    async def contract(self, ctx, member: discord.Member, price: int):
        """Offer a 24h contract of loyalty to another soul."""
        if member.id == ctx.author.id:
            return await ctx.send("🛡️ **You cannot pledge to yourself. Find a mentor or an apprentice.**")
        if price < 1000:
            return await ctx.send("⚔️ **The Guild doesn't process pledges for less than 1,000 Flames.**")

        with self.get_db_connection() as conn:
            dom = conn.execute("SELECT balance FROM users WHERE id=?", (ctx.author.id,)).fetchone()
            if not dom or dom['balance'] < price:
                return await ctx.send("❌ **Your vault is too empty to afford this level of sponsorship.**")

        self.pending_contracts[member.id] = {"dom_id": ctx.author.id, "price": price}
        
        embed = self.fiery_embed("Binding Oath Offer", 
            f"🛡️ {ctx.author.mention} is holding an oath of loyalty open for {member.mention}.\n\n"
            f"🖤 **Sponsorship Price:** {price} Flames\n"
            f"⏳ **Duration:** 24 Hours of Loyalty\n"
            f"📈 **Terms:** 20% of every Flame you earn flows to your Mentor.\n\n"
            f"**{member.mention}, type `!sfwaccept` to seal the oath.**")
        
        await ctx.send(member.mention, embed=embed)
        await self.increment_quest(ctx.author.id, "d3")

    @commands.command(name="sfwaccept")
    async def accept(self, ctx):
        """Accept the oath and the terms of the contract."""
        if ctx.author.id not in self.pending_contracts:
            return await ctx.send("⚔️ **No one is waiting for your pledge at the moment.**")
        
        offer = self.pending_contracts.pop(ctx.author.id)
        dom_id = offer['dom_id']
        price = offer['price']
        
        with self.get_db_connection() as conn:
            dom_check = conn.execute("SELECT balance FROM users WHERE id=?", (dom_id,)).fetchone()
            if not dom_check or dom_check['balance'] < price:
                return await ctx.send("❌ **The Mentor can no longer afford the price of your apprenticeship.**")
            
            conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, dom_id))
            conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (price, ctx.author.id))
            
            expiry_dt = datetime.now(timezone.utc) + timedelta(hours=24)
            expiry = expiry_dt.isoformat()
            conn.execute("INSERT OR REPLACE INTO contracts (dominant_id, submissive_id, expiry) VALUES (?, ?, ?)", 
                         (dom_id, ctx.author.id, expiry))
            conn.commit()

        dom_user = await self.bot.fetch_user(dom_id)
        await ctx.send(embed=self.fiery_embed("Oath Sealed", 
            f"⚔️ **THE OATH IS SEALED.** {ctx.author.mention} is now the loyal apprentice of {dom_user.mention} for the next 24 hours.\n"
            f"The payment has been transferred to the new member.", color=0xFF0000))

        await self.increment_quest(ctx.author.id, "w4")

        audit_chan = self.bot.get_channel(self.audit_channel_id)
        if audit_chan:
            log_emb = self.fiery_embed("🕵️ GUILD CONTRACT AUDIT", f"A new soul has taken the oath.")
            log_emb.add_field(name="⚔️ Mentor", value=dom_user.mention, inline=True)
            log_emb.add_field(name="🛡️ Apprentice", value=ctx.author.mention, inline=True)
            log_emb.add_field(name="💰 Sponsorship Price", value=f"{price:,} Flames", inline=True)
            log_emb.add_field(name="⏳ Expiry", value=f"<t:{int(expiry_dt.timestamp())}:R>", inline=True)
            log_emb.description = f"🛡️ **GUILD NOTE:** {ctx.author.display_name} has accepted the terms. 20% of their future earnings are now synchronized with {dom_user.display_name}'s vault."
            if os.path.exists("LobbyTopRight.jpg"):
                log_file = discord.File("LobbyTopRight.jpg", filename="audit_contract.jpg")
                log_emb.set_thumbnail(url="attachment://audit_contract.jpg")
                await audit_chan.send(file=log_file, embed=log_emb)
            else:
                await audit_chan.send(embed=log_emb)

    # ==========================================
    # 📸 THE OBSERVER'S HIDDEN GALLERY
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
            
            pair_ids = sorted([message.author.id, mentioned.id])
            pair_key = f"{pair_ids[0]}_{pair_ids[1]}"
            
            with self.get_db_connection() as conn:
                conn.execute("""
                    INSERT INTO sfw_tension (pair_key, count, last_interaction) 
                    VALUES (?, 1, ?)
                    ON CONFLICT(pair_key) DO UPDATE SET 
                        count = count + 1,
                        last_interaction = ?
                """, (pair_key, datetime.now().isoformat(), datetime.now().isoformat()))
                conn.commit()

    @commands.command(name="sfwgallery")
    async def gallery(self, ctx):
        """A peek into the highest tension in the arena."""
        with self.get_db_connection() as conn:
            guild_member_ids = [m.id for m in ctx.guild.members]
            placeholders = ','.join(['?'] * len(guild_member_ids))
            recent_winners = conn.execute(f"SELECT id, wins, kills FROM users WHERE id IN ({placeholders}) AND wins > 0 ORDER BY wins DESC LIMIT 5", guild_member_ids).fetchall()
            
            tension_data = conn.execute("SELECT pair_key, count FROM sfw_tension ORDER BY count DESC LIMIT 5").fetchall()
            total_sum_row = conn.execute("SELECT SUM(count) as total FROM sfw_tension").fetchone()
            total_global_pulses = total_sum_row['total'] if total_sum_row and total_sum_row['total'] else 1
        
        desc = f"The observer cameras in **{ctx.guild.name}** are live. Some fighters are performing... *exquisitely*.\n\n"
        embed = self.fiery_embed("💎 THE GUILD'S PRIVATE GALLERY", desc, color=0x800080)

        favorites = ""
        for i, row in enumerate(recent_winners, 1):
            m = ctx.guild.get_member(row['id'])
            name = m.display_name if m else f"Fighter {row['id']}"
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "🔹")
            favorites += f"{medal} **{name}**\n└ *{row['wins']} Echo Wins | {row['kills']} Echo Kills*\n"
        
        embed.add_field(name="🏆 THE GUILD'S FAVORITES", value=favorites if favorites else "*The podium is cold.*", inline=False)
        
        tension_list = ""
        if not tension_data:
            tension_list = "*The arena air is thin. No one is clashing yet...*"
        else:
            for row in tension_data:
                u1_id, u2_id = map(int, row['pair_key'].split('_'))
                u1, u2 = ctx.guild.get_member(u1_id), ctx.guild.get_member(u2_id)
                
                if u1 and u2:
                    count = row['count']
                    tension_pct = int((count / total_global_pulses) * 100)
                    
                    if count > 100: state = "⚡ **DANGEROUS**"
                    elif count > 50: state = "🔥 **ELECTRIC**"
                    elif count > 20: state = "🛡️ **SIMMERING**"
                    else: state = "☁️ **MISTY**"

                    filled = "■" * (min(tension_pct, 100) // 10)
                    empty = "□" * (10 - len(filled))
                    tension_list += f"{state} **{u1.display_name}** 🔗 **{u2.display_name}**\n└ [`{filled}{empty}`] **{count} Clashes**\n"

        embed.add_field(name="👁️ OBSERVER'S LIVE FEED (SERVER TENSION)", value=tension_list if tension_list else "*Static on the screen...*", inline=False)
        embed.set_footer(text=f"⚔️ RECORDED IN {ctx.guild.name.upper()} ⚔️")

        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="gallery.jpg")
            embed.set_thumbnail(url="attachment://gallery.jpg")
            await ctx.send(file=file, embed=embed)
        else: await ctx.send(embed=embed)

    # ==========================================
    # 🌑 BLACKOUT & TRIAL SYSTEM
    # ==========================================

    @commands.command(name="sfwsearch")
    async def search(self, ctx):
        """Search the dark arena during a Blackout."""
        if not self.is_blackout:
            return await ctx.send("The lights are on. There is no mystery to find here, fighter.")
        
        roll = random.randint(1, 20)
        if roll == self.blackout_key_holder:
            self.is_blackout = False
            await self.update_user_stats(ctx.author.id, amount=100000, source="Found Guild Keys")
            await ctx.send(embed=self.fiery_embed("KEY FOUND", f"🗝️ {ctx.author.mention} has found the Guild's Keys in the dark! The lights flicker back on and they are rewarded with **100,000 Flames**!"))
            await self.increment_quest(ctx.author.id, "w20")

            audit_chan = self.bot.get_channel(self.audit_channel_id)
            if audit_chan:
                await audit_chan.send(f"💡 **BLACKOUT ENDED:** {ctx.author.display_name} found the Guild Keys. Power restored.")
        else:
            await ctx.send(f"🌑 {ctx.author.mention} fumbles in the dark and finds nothing but cold steel.")

    @commands.command(name="sfwtrial")
    async def trial(self, ctx):
        """The Trial of the Gladiator."""
        import sys
        main = sys.modules['__main__']
        user_data = main.get_user(ctx.author.id)
        if user_data['balance'] < 5000:
            return await ctx.send("You don't have enough Flames to stake your pride in this trial.")
            
        await ctx.send(f"⚖️ {ctx.author.mention}, the Trial begins. 5 waves of combat tests. React with the emoji I show you within 2 seconds. **STAKE: 5,000 Flames.** Type `confirm` to fight.")
        
        def check(m): return m.author == ctx.author and m.content.lower() == 'confirm'
        try:
            await self.bot.wait_for('message', check=check, timeout=15)
        except asyncio.TimeoutError:
            return await ctx.send("Cowardice is noted.")

        emojis = ["🛡️", "⚔️", "🩸", "🎯", "🖤"]
        for i in range(5):
            target = random.choice(emojis)
            msg = await ctx.send(f"**WAVE {i+1}:** QUICK, DEFEND WITH {target}!")
            await msg.add_reaction(target)
            
            def react_check(reaction, user):
                return user == ctx.author and str(reaction.emoji) == target and reaction.message.id == msg.id
                
            try:
                await self.bot.wait_for('reaction_add', check=react_check, timeout=2.0)
            except asyncio.TimeoutError:
                await main.update_user_stats_async(ctx.author.id, amount=-5000, source="Failed Trial")
                audit_chan = self.bot.get_channel(self.audit_channel_id)
                if audit_chan:
                    log_emb = self.fiery_embed("🕵️ GUILD TRIAL AUDIT: BROKEN", f"A fighter has failed the Trial of the Gladiator.")
                    log_emb.add_field(name="🛡️ Failed Fighter", value=ctx.author.mention, inline=True)
                    log_emb.add_field(name="📉 Penalty", value="5,000 Flames Extracted", inline=True)
                    await audit_chan.send(embed=log_emb)
                return await ctx.send(f"❌ **DEFEATED.** {ctx.author.mention} failed to react in time. 5,000 Flames lost.")

        await main.update_user_stats_async(ctx.author.id, amount=10000, xp_gain=5000, source="Passed Trial")
        await ctx.send(embed=self.fiery_embed("Trial Passed", f"🖤 {ctx.author.mention} has endured the Guild's combat Trial! They earn **10,000 Flames**.", color=0x00FF00))
        
        audit_chan = self.bot.get_channel(self.audit_channel_id)
        if audit_chan:
            log_emb = self.fiery_embed("🕵️ GUILD TRIAL AUDIT: ENDURED", f"A fighter has passed the Trial.")
            await audit_chan.send(embed=log_emb)

    # ==========================================
    # 📜 THE GUILD'S LEDGER (QUESTS)
    # ==========================================

    @commands.command(name="sfwquests")
    async def quests(self, ctx):
        """Check your progress on the daily and weekly demands."""
        u_id = ctx.author.id
        with self.get_db_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO quests (user_id) VALUES (?)", (u_id,))
            conn.commit()
            q = conn.execute("SELECT * FROM quests WHERE user_id = ?", (u_id,)).fetchone()

        embed = discord.Embed(title="📜 THE GUILD'S LEDGER: CLEAR DEMANDS", color=0xFFD700)
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="quest_top.jpg")
            embed.set_thumbnail(url="attachment://quest_top.jpg")

        d_tasks = [
            f"1. 🩸 **Force a Defeat:** {q['d1']}/1 Kill in Arena", 
            f"2. 🎮 **Arena Hunger:** {q['d2']}/3 Games Played",
            f"3. 💍 **Offer an Oath:** {q['d3']}/1 `!sfwcontract` sent", 
            f"4. 🛡️ **Pleading:** {q['d4']}/5 `!beg` uses",
            f"5. ⚔️ **Hard Labor:** {q['d5']}/5 `!work` uses", 
            f"6. 🏆 **Top Authority:** {q['d6']}/1 Game Won",
            f"7. 🧪 **Lab Rat:** {q['d7']}/2 `!experiment` uses", 
            f"8. 💧 **Cleaning Duty:** {q['d8']}/3 `!cumcleaner` uses",
            f"9. 👠 **Recruiting:** {q['d9']}/2 `!pimp` uses", 
            f"10. ❓ **Blind Obedience:** {q['d10']}/2 `!mystery` uses",
            f"11. 🛡️ **Charm:** {q['d11']}/5 `!flirt` uses", 
            f"12. 🔥 **Active Fighter:** {q['d12']}/10 commands total",
            f"13. 🩸 **First Strike:** {q['d13']}/1 First Blood in game", 
            f"14. 💀 **Total Yield:** {q['d14']}/2 Times defeated",
            f"15. 💰 **Wealth Gatherer:** {q['d15']}/1000 Flames earned", 
            f"16. 🛡️ **Loud Challenger:** {q['d16']}/10 chat messages sent",
            f"17. ⚔️ **Narcissist:** {q['d17']}/1 `!me` profile check", 
            f"18. 🔄 **Daily Dose:** {q['d18']}/1 `!daily` claimed",
            f"19. ⚔️ **Role Call:** {q['d19']}/1 Ping in a game lobby", 
            f"20. 🏆 **Full Session:** {q['d20']}/1 Game played"
        ]
        
        w_tasks = [
            f"1. 👑 **Champion of Arena:** {q['w1']}/5 Wins total", 
            f"2. ⚔️ **Pride Shredder:** {q['w2']}/25 Arena Kills",
            f"3. 📈 **Victory Streak:** {q['w3']}/3 Killstreak reached", 
            f"4. 🔒 **Loyalty Collector:** {q['w4']}/3 Contracts accepted",
            f"5. 🔗 **Career Worker:** {q['w5']}/30 `!work` commands", 
            f"6. 🏆 **Arena Fiend:** {q['w6']}/50 commands used",
            f"7. 💎 **Sultan of Flames:** {q['w7']}/10k total earnings", 
            f"8. ⚔️ **High Endurance:** {q['w8']}/10 Games joined",
            f"9. 🛡️ **Golden Fighter:** {q['w9']}/5 Top 5 placements", 
            f"10. 🥀 **Professional Charmer:** {q['w10']}/20 `!flirt` uses",
            f"11. 🧪 **Total Subject:** {q['w11']}/10 `!experiment` uses", 
            f"12. 💧 **Floor Manager:** {q['w12']}/15 `!cumcleaner` uses",
            f"13. 👠 **Guild Recruiter:** {q['w13']}/10 `!pimp` uses", 
            f"14. 🕯️ **Mystery Seeker:** {q['w14']}/10 `!mystery` uses",
            f"15. 🛡️ **Professional Pleader:** {q['w15']}/20 `!beg` uses", 
            f"16. 📅 **Hooked:** {q['w16']}/7 `!daily` claims",
            f"17. ⬆️ **Deepening Skill:** {q['w17']}/1 Level gained", 
            f"18. 👁️ **Public Interest:** {q['w18']}/50 Mentions in chat",
            f"19. 🌋 **Heat Chaser:** {q['w19']}/5 Heat Events triggered", 
            f"20. 🏆 **Legendary Presence:** {q['w20']}/1 Legendary Event"
        ]

        embed.add_field(name="🛡️ THE DAILY TASKS", value="\n".join(d_tasks[:10]), inline=True)
        embed.add_field(name="🛡️ DAILY CONTINUED", value="\n".join(d_tasks[10:]), inline=True)
        embed.add_field(name="⚔️ THE WEEKLY ORDEAL", value="\n".join(w_tasks[:10]), inline=True)
        embed.add_field(name="⚔️ WEEKLY CONTINUED", value="\n".join(w_tasks[10:]), inline=True)
        embed.set_footer(text="⚔️ THE GUILD IS ALWAYS WATCHING ⚔️")

        if os.path.exists("LobbyTopRight.jpg"):
            await ctx.send(file=file, embed=embed)
        else: await ctx.send(embed=embed)

    @commands.command(name="sfwquestboard")
    async def quest_leaderboard(self, ctx):
        """Displays the Monthly Quest Leaderboard."""
        with self.get_db_connection() as conn:
            query = "SELECT user_id, (" + " + ".join([f"d{i}" for i in range(1, 21)]) + " + " + " + ".join([f"w{i}" for i in range(1, 21)]) + ") as total FROM quests WHERE user_id != 0 ORDER BY total DESC LIMIT 10"
            top_ten = conn.execute(query).fetchall()

        desc = "🏆 **MONTHLY GUILD RANKINGS** 🏆\n\n"
        for i, row in enumerate(top_ten, 1):
            member = ctx.guild.get_member(row['user_id'])
            name = member.display_name if member else f"Fighter {row['user_id']}"
            desc += f"{i}. **{name}**: {row['total']} Demands Met\n"
        
        embed = self.fiery_embed("Ledger Leaderboard", desc, color=0xFFD700)
        await ctx.send(embed=embed)

    # ==========================================
    # 🕒 BACKGROUND LOOPS (RESETS ONLY)
    # ==========================================

    @tasks.loop(minutes=30)
    async def sfw_quest_reset_loop(self):
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
                    await audit_chan.send("⚔️ **LEDGER WIPE:** Daily Ordeals reset.")

            if now.isoweekday() == 1 and now.isocalendar()[1] != last_reset.isocalendar()[1]:
                conn.execute("UPDATE quests SET " + ", ".join([f"w{i}=0" for i in range(1, 21)]))
                audit_chan = self.bot.get_channel(self.audit_channel_id)
                if audit_chan:
                    await audit_chan.send("🚨 **WEEKLY PURGE:** Weekly Ordeals reset.")
            conn.commit()

    @sfw_quest_reset_loop.before_loop
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

class EngineControlSFW(commands.Cog):
    def __init__(self, bot, fiery_embed, save_game_config, get_db_connection):
        self.bot = bot
        self.fiery_embed = fiery_embed
        self.save_game_config = save_game_config
        self.get_db_connection = get_db_connection
        
        with self.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sfw_ignis_server_stats (guild_id INTEGER PRIMARY KEY, server_edition INTEGER DEFAULT 1)")
            conn.commit()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setsfwadmin(self, ctx, role: discord.Role):
        """Sets the specific role allowed to manage Ignis SFW games."""
        with self.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sfw_ignis_settings (guild_id INTEGER PRIMARY KEY, role_id INTEGER)")
            conn.execute("INSERT OR REPLACE INTO sfw_ignis_settings (guild_id, role_id) VALUES (?, ?)", (ctx.guild.id, role.id))
            conn.commit()
        await ctx.send(embed=self.fiery_embed("Settings Updated", f"The role {role.mention} is now recognized as an **Ignis SFW Admin**."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setsfw(self, ctx, number: int):
        """Manually sets the next SFW game edition number."""
        import sys
        main = sys.modules['__main__']
        main.game_edition = number
        self.save_game_config()
        await ctx.send(f"✅ Next SFW game edition set to **#{number}**.")
        
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def sfwserverfix(self, ctx, number: int):
        """Manually sets the next server-specific SFW game edition number."""
        with self.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sfw_ignis_server_stats (guild_id INTEGER PRIMARY KEY, server_edition INTEGER DEFAULT 1)")
            conn.execute("INSERT OR REPLACE INTO sfw_ignis_server_stats (guild_id, server_edition) VALUES (?, ?)", (ctx.guild.id, number))
            conn.commit()
        await ctx.send(f"✅ Next server-specific SFW game edition set to **#{number}**.")

    @commands.command()
    async def sfwecho(self, ctx):
        import sys
        main = sys.modules['__main__']
        
        engine = self.bot.get_cog("IgnisEngineSFW")
        if engine:
            if ctx.channel.id in engine.active_battles:
                return await ctx.send("❌ **A session is already active in this room.** Wait for it to conclude.")
            if ctx.guild.id in engine.current_lobbies:
                 existing_view = engine.current_lobbies[ctx.guild.id]
                 return await ctx.send("❌ **Registration is already open for this server.** Use `!sfwlobby` to check status.")

        with self.get_db_connection() as conn:
            conn.execute("DELETE FROM sfw_lobby_participants WHERE guild_id = ?", (ctx.guild.id,))
            
            conn.execute("CREATE TABLE IF NOT EXISTS sfw_ignis_server_stats (guild_id INTEGER PRIMARY KEY, server_edition INTEGER DEFAULT 1)")
            row = conn.execute("SELECT server_edition FROM sfw_ignis_server_stats WHERE guild_id = ?", (ctx.guild.id,)).fetchone()
            if row:
                server_edition = row[0]
            else:
                server_edition = 1
                conn.execute("INSERT INTO sfw_ignis_server_stats (guild_id, server_edition) VALUES (?, ?)", (ctx.guild.id, server_edition))
            
            conn.commit()

        embed = discord.Embed(
            title=f"Echo's Hangrygames (SFW) Edition # {main.game_edition}", 
            description=f"**Server Edition: #{server_edition}**\n\nThe arena gates are about to open, brave souls. Submit to the registration.", 
            color=0x0000FF
        )
        
        view = LobbyViewSFW(ctx.author, main.game_edition, ctx.guild.id)
        
        self.bot.add_view(view)

        if engine: 
            engine.current_lobbies[ctx.guild.id] = view

        embed.add_field(name="🧙‍♂️ 0 Fighters Ready", value="The air is thick with anticipation.", inline=False)
        await ctx.send(embed=embed, view=view)
        
        main.game_edition += 1
        self.save_game_config()
        
        with self.get_db_connection() as conn:
            conn.execute("UPDATE sfw_ignis_server_stats SET server_edition = server_edition + 1 WHERE guild_id = ?", (ctx.guild.id,))
            conn.commit()

    @commands.command()
    async def sfwlobby(self, ctx):
        engine = self.bot.get_cog("IgnisEngineSFW")
        guild_lobby = engine.current_lobbies.get(ctx.guild.id) if engine else None
        
        participants = []
        with self.get_db_connection() as conn:
            rows = conn.execute("SELECT user_id FROM sfw_lobby_participants WHERE guild_id = ?", (ctx.guild.id,)).fetchall()
            participants = [r[0] for r in rows]
        
        if not participants:
            embed = self.fiery_embed("Lobby Status", "No active registration in progress. The arena is closed.")
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            return await ctx.send(file=file, embed=embed)
        
        mentions = [f"<@{p_id}>" for p_id in participants]
        edition_val = guild_lobby.edition if guild_lobby else "?"
        embed = self.fiery_embed("Active Tributes", f"The following souls are bound for SFW Edition #{edition_val}:\n\n" + "\n".join(mentions), color=0x00FF00)
        file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
        await ctx.send(file=file, embed=embed)

class IgnisEngineSFW(commands.Cog):
    def __init__(self, bot, update_user_stats, get_user, fiery_embed, get_db_connection, ranks, classes, audit_channel_id):
        self.bot = bot
        self.update_user_stats = update_user_stats
        self.get_user = get_user
        self.fiery_embed = fiery_embed
        self.get_db_connection = get_db_connection
        self.ranks = ranks
        self.classes = classes
        self.audit_channel_id = getattr(sys.modules['__main__'], "AUDIT_CHANNEL_ID", audit_channel_id)
        
        self.active_battles = set() 
        self.current_lobbies = {} 
        self.current_survivors = {} 

        self._init_persistence()

    def _init_persistence(self):
        with self.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sfw_lobby_participants (guild_id INTEGER, user_id INTEGER)")
            conn.commit()

    def calculate_level(self, current_xp):
        level = 1
        xp_needed = 500
        while current_xp >= xp_needed and level < 100:
            current_xp -= xp_needed
            level += 1
            if level <= 15: xp_needed = 2500
            elif level <= 30: xp_needed = 5000
            elif level <= 60: xp_needed = 7500
            else: xp_needed = 5000
        return level

    @commands.command(name="sfw_reset_arena")
    @commands.is_owner()
    async def reset_arena(self, ctx):
        self.active_battles.clear()
        self.current_lobbies.clear()
        self.current_survivors.clear()
        with self.get_db_connection() as conn:
            conn.execute("DELETE FROM sfw_lobby_participants WHERE guild_id = ?", (ctx.guild.id,))
            conn.commit()
        await ctx.send("⚔️ **Guild Master Override:** Global SFW Arena locks and lobbies have been reset.")

    async def create_arena_image(self, winner_url, loser_url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(winner_url, timeout=10) as r1, session.get(loser_url, timeout=10) as r2:
                    if r1.status != 200 or r2.status != 200:
                        raise Exception(f"Avatar download failed")
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())
            
            canvas_w = 1000
            canvas_h = 1000
            bg_path = "1v1Background.jpg"
            bg = Image.open(bg_path).convert("RGBA").resize((canvas_w, canvas_h)) if os.path.exists(bg_path) else Image.new("RGBA", (canvas_w, canvas_h), (180, 30, 0, 255))
            
            av_large = 420
            av_winner = Image.open(p1_data).convert("RGBA").resize((av_large, av_large))
            av_winner = ImageOps.expand(av_winner, border=10, fill="orange") 
            
            av_loser_raw = Image.open(p2_data).convert("RGBA").resize((av_large, av_large))
            av_loser = ImageOps.grayscale(av_loser_raw).convert("RGBA")
            red_overlay = Image.new("RGBA", av_loser.size, (255, 0, 0, 100)) 
            av_loser = Image.alpha_composite(av_loser, red_overlay)
            av_loser = ImageOps.expand(av_loser, border=10, fill="gray")
            
            bg.paste(av_winner, (40, 150), av_winner)
            bg.paste(av_loser, (540, 150), av_loser)
            
            draw = ImageDraw.Draw(bg)
            draw.line((400, 220, 600, 480), fill=(220, 220, 220), width=25)
            draw.line((600, 220, 400, 480), fill=(220, 220, 220), width=25)
            
            buf = io.BytesIO()
            bg.crop((0, 50, 1000, 750)).save(buf, format="PNG")
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"Arena Image Error: {e}")
            fallback = Image.new("RGBA", (1000, 700), (120, 20, 0, 255))
            buf = io.BytesIO()
            fallback.save(buf, format="PNG")
            buf.seek(0)
            return buf

    async def create_suicide_image(self, user_url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(user_url, timeout=10) as r:
                    if r.status != 200: raise Exception("Avatar download failed")
                    data = io.BytesIO(await r.read())
            
            canvas_w, canvas_h = 1000, 1000
            bg_path = "1v1Background.jpg"
            bg = Image.open(bg_path).convert("RGBA").resize((canvas_w, canvas_h)) if os.path.exists(bg_path) else Image.new("RGBA", (canvas_w, canvas_h), (50, 50, 50, 255))
            
            av_size = 500
            av_raw = Image.open(data).convert("RGBA").resize((av_size, av_size))
            av = ImageOps.grayscale(av_raw).convert("RGBA")
            enhancer = ImageEnhance.Contrast(av)
            av = enhancer.enhance(1.5)
            av = ImageOps.expand(av, border=15, fill=(40, 40, 40))
            
            bg.paste(av, (250, 150), av)
            
            draw = ImageDraw.Draw(bg)
            draw.line((250, 150, 750, 650), fill=(200, 0, 0), width=30)
            draw.line((750, 150, 250, 650), fill=(200, 0, 0), width=30)
            
            buf = io.BytesIO()
            bg.crop((0, 50, 1000, 750)).save(buf, format="PNG")
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"Suicide Image Error: {e}")
            fallback = Image.new("RGBA", (1000, 700), (0, 0, 0, 255))
            buf = io.BytesIO()
            fallback.save(buf, format="PNG")
            buf.seek(0)
            return buf

    async def get_market_bonuses(self, inventory):
        fb_prot = 0
        final_luck = 0
        for item in inventory:
            if item in ["Damp Cell", "Rusty Locker", "Shadowed Shack", "Stone Alcove", "Maimed Tent"]: fb_prot = max(fb_prot, 1)
            elif item in ["Sinner's Flat", "Guard's Bunk", "Brick Bunker", "Tribute Lodge", "Basement Vault"]: fb_prot = max(fb_prot, 2)
            elif item in ["Gothic Manor", "Obsidian Villa", "Neon Penthouse", "Hidden Sanctuary", "Merchant's Estate"]: fb_prot = max(fb_prot, 4)
            elif item in ["Velvet Dungeon", "Crystal Cathedral", "Shadow Fortress", "Iron Monastery", "Sky-Bound Spire"]: fb_prot = max(fb_prot, 8)
            elif item in ["The Ivory Tower", "Abyssal Throne", "Grand Exhibition Hall", "Molten Citadel", "Kraken's Maw"]: fb_prot = max(fb_prot, 10)
            elif item in ["The Forbidden Palace", "Dominion Prime", "Eternity's Bastion", "The Red Sun"]: fb_prot = max(fb_prot, 12)
            elif item == "Absolute Null": fb_prot = max(fb_prot, 15)

            if item in ["Scrawny Rat", "One-EyED Cat", "Sewer Toad", "Maimed Pigeon", "Starving Cur"]: final_luck = max(final_luck, 1)
            elif item in ["Pit Viper", "Trained Raven", "Black Rabbit", "Ferret Thief", "Dungeon Bat"]: final_luck = max(final_luck, 2)
            elif item in ["Shadow Panther", "Silver Wolf", "Mech Spider", "Blood Hound", "Harpy Chick"]: final_luck = max(final_luck, 4)
            elif item in ["Obsidian Gargoyle", "Succubus Spirit", "Void Serpent", "Iron Golem Minion", "Spectral Stag"]: final_luck = max(final_luck, 8)
            elif item in ["Inferno Drake", "Master's Shadow", "Lich Owl", "Behemoth Cub", "Siren of Pits"]: final_luck = max(final_luck, 12)
        return fb_prot, final_luck

    async def start_battle(self, channel, participants, edition):
        if channel.id in self.active_battles: 
            return
        self.active_battles.add(channel.id)
        
        fxp_log = {p_id: {"participation": 100, "kills": 0, "first_kill": 0, "placement": 0, "final_rank": 0} for p_id in participants}
        first_blood_recorded = False

        import sys as _sys
        self.audit_channel_id = getattr(_sys.modules['__main__'], "AUDIT_CHANNEL_ID", self.audit_channel_id)
        audit_channel = self.bot.get_channel(self.audit_channel_id)

        try:
            await self.bot.wait_until_ready()
            
            fighters = []
            game_kills = {p_id: 0 for p_id in participants}
            roster_list = []

            fb_protection = {} 
            final_luck = {} 
            relationship_luck = {}
            target_streaks = {}
            
            arena_shielding = {}
            omni_protocol = {}

            for p_id in participants:
                u_raw = self.get_user(p_id) 
                if not u_raw: continue
                u_data = dict(u_raw) 

                inv = json.loads(u_data['titles']) if u_data['titles'] else []
                prot, luck = await self.get_market_bonuses(inv)
                fb_protection[p_id] = prot
                final_luck[p_id] = luck
                target_streaks[p_id] = u_data.get('current_win_streak', 0)

                arena_shielding[p_id] = 0
                omni_protocol[p_id] = 0
                with self.get_db_connection() as conn:
                    shield_count = conn.execute("SELECT COUNT(*) FROM card_mastery WHERE user_id = ? AND mastery_key LIKE 'tier_%'", (p_id,)).fetchone()[0]
                    arena_shielding[p_id] = shield_count * 0.10
                    if conn.execute("SELECT 1 FROM card_mastery WHERE user_id = ? AND mastery_key = 'absolute_master'", (p_id,)).fetchone():
                        omni_protocol[p_id] = 0.20

                relationship_luck[p_id] = 0
                try:
                    with self.get_db_connection() as conn:
                        rel = conn.execute("SELECT shared_luck FROM relationships WHERE (user_one = ? OR user_two = ?)", (p_id, p_id)).fetchone()
                        if rel: relationship_luck[p_id] = rel['shared_luck']
                except: pass

                with self.get_db_connection() as conn:
                    conn.execute("INSERT OR IGNORE INTO quests (user_id) VALUES (?)", (p_id,))
                    conn.commit()

                member = channel.guild.get_member(p_id)
                if not member:
                    try: 
                        member = await channel.guild.fetch_member(p_id)
                    except: 
                        continue
                
                name = member.display_name
                fighters.append({"id": p_id, "name": name, "avatar": member.display_avatar.url})
                roster_list.append(f"· **{name}**")
                
                with self.get_db_connection() as conn:
                    conn.execute("UPDATE users SET games_played = games_played + 1 WHERE id = ?", (p_id,))
                    conn.commit()

            self.current_survivors[channel.id] = [f['id'] for f in fighters]

            if len(fighters) < 2:
                await channel.send("❌ Game cancelled: Not enough tributes found in the arena.")
                if channel.id in self.active_battles:
                    self.active_battles.remove(channel.id)
                return

            try:
                total_count = len(fighters)
                roster_embed = self.fiery_embed(f"Tribute Roster - Edition #{edition}", f"**Total Fighters Bound:** `{total_count}`\n\n" + "\n".join(roster_list))
                await channel.send(embed=roster_embed)
            except:
                await channel.send(f"**Tribute Roster - Edition #{edition} (Total: {len(fighters)})**\n" + "\n".join(roster_list))

            await asyncio.sleep(4)
            try:
                await channel.send(FieryLexiconSFW.get_intro())
            except:
                await channel.send("⚔️ **The gate opens. Let the games begin.**")
            await asyncio.sleep(2)

            while len(fighters) > 1:
                if random.random() < 0.10 and len(fighters) > 2:
                    victim_idx = random.randrange(len(fighters))
                    victim = fighters.pop(victim_idx)
                    
                    if not first_blood_recorded:
                        first_blood_recorded = True

                    if channel.id in self.current_survivors:
                        if victim['id'] in self.current_survivors[channel.id]:
                            self.current_survivors[channel.id].remove(victim['id'])
                    
                    await self.update_user_stats(victim['id'], deaths=1, source="Suicide")
                    with self.get_db_connection() as conn:
                        conn.execute("UPDATE users SET current_kill_streak = 0, current_win_streak = 0 WHERE id = ?", (victim['id'],))
                        conn.commit()
                    
                    rem = len(fighters)
                    fxp_log[victim['id']]["final_rank"] = rem + 1
                    
                    s_img = await self.create_suicide_image(victim['avatar'])
                    s_file = discord.File(fp=s_img, filename="suicide.png")
                    
                    s_msg = f"🥀 **THE ARENA WAS TOO MUCH.** {victim['name']} couldn't take the pressure and has ended their own existence."
                    s_emb = discord.Embed(title="💀 SELF-TERMINATION DETECTED 💀", description=s_msg, color=0x333333)
                    s_emb.set_image(url="attachment://suicide.png")
                    
                    await channel.send(file=s_file, embed=s_emb)
                    
                    await asyncio.sleep(5)
                    if len(fighters) <= 1: break
                    continue 

                if len(fighters) == 2:
                    t1, t2 = fighters[0], fighters[1]
                    climax_msg = f"⚔️ **THE FINAL STAND.** ⚔️\n\nOnly {t1['name']} and {t2['name']} remain. The arena falls silent. One will stand, one will fall..."
                    climax_emb = self.fiery_embed("FINAL CLIMAX", climax_msg, color=0x8B0000)
                    
                    if os.path.exists("LobbyTopRight.jpg"):
                        climax_file = discord.File("LobbyTopRight.jpg", filename="climax_logo.jpg")
                        climax_emb.set_thumbnail(url="attachment://climax_logo.jpg")
                        await channel.send(file=climax_file, embed=climax_emb)
                    else:
                        await channel.send(embed=climax_emb)
                    
                    await asyncio.sleep(5)

                if random.random() < 0.035 and len(fighters) > 3:
                    kill_count = random.randint(2, min(2, len(fighters) - 1))
                    event_losers = []
                    for _ in range(kill_count):
                        if len(fighters) <= 1: break
                        temp_index = random.randrange(len(fighters))
                        potential_loser = fighters[temp_index]
                        
                        dodge_chance = (fb_protection.get(potential_loser['id'], 0) / 100) + arena_shielding.get(potential_loser['id'], 0)
                        if random.random() < dodge_chance:
                            continue

                        loser = fighters.pop(temp_index)
                        event_losers.append(loser)

                        if not first_blood_recorded:
                             first_blood_recorded = True

                        if channel.id in self.current_survivors:
                            if loser['id'] in self.current_survivors[channel.id]:
                                self.current_survivors[channel.id].remove(loser['id'])

                        await self.update_user_stats(loser['id'], deaths=1, source="Legendary Event")
                        
                        rem = len(fighters)
                        fxp_log[loser['id']]["final_rank"] = rem + 1

                    if event_losers:
                        try:
                            event_msg = FieryLexiconSFW.get_legendary_event([l['name'] for l in event_losers])
                        except:
                            event_msg = f"A chaotic surge wipes out: {', '.join([l['name'] for l in event_losers])}"
                        await channel.send(embed=self.fiery_embed("LEGENDARY ECHO EVENT", event_msg, color=0x9400D3))
                        await asyncio.sleep(6)
                    
                    if len(fighters) <= 1: break
                    continue

                p1_idx = random.randrange(len(fighters))
                p1 = fighters.pop(p1_idx)
                p2_idx = random.randrange(len(fighters))
                p2 = fighters.pop(p2_idx)
                
                is_final_fight = (len(fighters) == 0) 
                p1_win_chance = 0.5
                
                if not first_blood_recorded:
                    p1_win_chance += (fb_protection.get(p1['id'], 0) + (arena_shielding.get(p1['id'], 0)*100) - fb_protection.get(p2['id'], 0) - (arena_shielding.get(p2['id'], 0)*100)) / 100

                if is_final_fight:
                    p1_total_luck = (final_luck.get(p1['id'], 0) / 100) + relationship_luck.get(p1['id'], 0) + omni_protocol.get(p1['id'], 0)
                    p2_total_luck = (final_luck.get(p2['id'], 0) / 100) + relationship_luck.get(p2['id'], 0) + omni_protocol.get(p2['id'], 0)
                    p1_win_chance += (p1_total_luck - p2_total_luck)

                p1_win_chance = max(0.1, min(0.9, p1_win_chance))
                winner, loser = (p1, p2) if random.random() < p1_win_chance else (p2, p1)
                fighters.append(winner)

                if not first_blood_recorded:
                    first_blood_recorded = True

                if channel.id in self.current_survivors:
                    if loser['id'] in self.current_survivors[channel.id]:
                        self.current_survivors[channel.id].remove(loser['id'])
                
                game_kills[winner['id']] += 1
                fxp_log[winner['id']]["kills"] += 750
                
                await self.update_user_stats(winner['id'], kills=1, source="Combat")
                await self.update_user_stats(loser['id'], deaths=1, source="Combat")

                if target_streaks.get(loser['id'], 0) >= 2:
                    files = []
                    bounty_emb = self.fiery_embed("🎯 BOUNTY COLLECTED 🎯", 
                        f"**THE HIGH-VALUE TARGET HAS FALLEN.**\n\n"
                        f"{winner['name']} has executed {loser['name']}, who was on a **{target_streaks[loser['id']]} Win Streak**.\n\n"
                        f"💰 **BOUNTY REWARD:** +5,000 Flames & +5,000 XP has been wired to the killer's vault.")
                    
                    if os.path.exists("LobbyTopRight.jpg"):
                        files.append(discord.File("LobbyTopRight.jpg", filename="bounty_logo.jpg"))
                        bounty_emb.set_author(name="GUILD's BOUNTY OFFICE", icon_url="attachment://bounty_logo.jpg")
                    
                    await self.update_user_stats(winner['id'], amount=5000, xp_gain=5000, source="Bounty Collection")
                    await channel.send(embed=bounty_emb, files=files)

                with self.get_db_connection() as conn:
                    conn.execute("UPDATE users SET current_kill_streak = current_kill_streak + 1 WHERE id = ?", (winner['id'],))
                    conn.execute("UPDATE users SET max_kill_streak = MAX(max_kill_streak, current_kill_streak) WHERE id = ?", (winner['id'],))
                    conn.execute("UPDATE users SET current_kill_streak = 0, current_win_streak = 0 WHERE id = ?", (loser['id'],))
                    
                    rem = len(fighters)
                    fxp_log[loser['id']]["final_rank"] = rem + 1
                    if rem == 4: 
                        fxp_log[loser['id']]["placement"] = 100
                        conn.execute("UPDATE users SET top_5 = top_5 + 1 WHERE id = ?", (loser['id'],))
                    elif rem == 3: 
                        fxp_log[loser['id']]["placement"] = 197
                        conn.execute("UPDATE users SET top_4 = top_4 + 1 WHERE id = ?", (loser['id'],))
                    elif rem == 2: 
                        fxp_log[loser['id']]["placement"] = 298
                        conn.execute("UPDATE users SET top_3 = top_3 + 1 WHERE id = ?", (loser['id'],))
                    elif rem == 1: 
                        fxp_log[loser['id']]["placement"] = 402
                        conn.execute("UPDATE users SET top_2 = top_2 + 1 WHERE id = ?", (loser['id'],))
                    conn.commit()

                arena_image = await self.create_arena_image(winner['avatar'], loser['avatar'])
                file = discord.File(fp=arena_image, filename="arena.png")
                try:
                    kill_msg = FieryLexiconSFW.get_kill(winner['name'], loser['name'], is_final=is_final_fight)
                except:
                    kill_msg = f"{winner['name']} has eliminated {loser['name']}!"
                
                emb = discord.Embed(title=f"⚔️ {winner['name']} VS {loser['name']}", description=kill_msg, color=0xFF4500)
                emb.set_image(url="attachment://arena.png")
                await channel.send(file=file, embed=emb)
                await asyncio.sleep(5)

            winner_final = fighters[0]
            self.last_winner_id = winner_final['id']
            fxp_log[winner_final['id']]["placement"] = 5000 
            fxp_log[winner_final['id']]["final_rank"] = 1
            
            processed_data = {}
            for p_id, log in fxp_log.items():
                total_gain = sum(log.values())
                user_raw = self.get_user(p_id)
                user_db = dict(user_raw) if user_raw else {}
                u_class = user_db.get('class', 'None')
                
                b_xp = 1.0
                if u_class == "Submissive": b_xp = 1.25
                elif u_class in ["Switch", "Exhibitionist"]: b_xp = 1.14 if u_class == "Switch" else 0.80

                final_fxp = int(total_gain * b_xp)
                
                with self.get_db_connection() as conn:
                    u = conn.execute("SELECT fiery_xp, fiery_level FROM users WHERE id=?", (p_id,)).fetchone()
                    if u:
                        new_xp = u['fiery_xp'] + final_fxp
                        new_lvl = self.calculate_level(new_xp)
                        conn.execute("UPDATE users SET fiery_xp = ?, fiery_level = ? WHERE id = ?", (new_xp, new_lvl, p_id))
                    conn.commit()
                processed_data[p_id] = final_fxp

            winner_raw = self.get_user(winner_final['id'])
            winner_user_db = dict(winner_raw) if winner_raw else {}
            winner_class_name = winner_user_db.get('class', 'None')
            
            flame_multiplier = 1.0
            if winner_class_name == "Dominant": flame_multiplier = 1.20
            elif winner_class_name == "Exhibitionist": flame_multiplier = 1.40
            elif winner_class_name == "Switch": flame_multiplier = 1.14

            total_flames_won = int(25000 * flame_multiplier)

            await self.update_user_stats(winner_final['id'], amount=75000, xp_gain=5000, wins=1, source="Game Win")
            
            f_raw = self.get_user(winner_final['id'])
            f_u = dict(f_raw) if f_raw else {}

            lvl = f_u.get('fiery_level', 1)
            rank_name = self.ranks[min(lvl-1, len(self.ranks)-1)] if lvl > 0 else self.ranks[0]
            winner_member = channel.guild.get_member(winner_final['id']) or await channel.guild.fetch_member(winner_final['id'])
            
            try:
                await channel.send(FieryLexiconSFW.get_winner_announcement(winner_member.mention))
            except:
                await channel.send(f"🏆 **{winner_member.mention} stands alone as the supreme victor!**")

            import sys as _sys_audit
            self.audit_channel_id = getattr(_sys_audit.modules['__main__'], "AUDIT_CHANNEL_ID", self.audit_channel_id)
            audit_channel = self.bot.get_channel(self.audit_channel_id)

            if audit_channel:
                ranked_players = sorted(fxp_log.items(), key=lambda x: x[1]['final_rank'])
                
                for p_id, log in ranked_players:
                    rank = log['final_rank']
                    if rank > 5: continue 

                    try:
                        m_raw = self.get_user(p_id)
                        m_stats = dict(m_raw) if m_raw else {}

                        member = channel.guild.get_member(p_id) or await channel.guild.fetch_member(p_id)
                        
                        audit_title = f"🏆 TOP {rank} POSITION: GUILD'S LEDGER" if rank > 1 else "👑 SUPREME VICTOR: GUILD'S LEDGER"
                        audit_color = 0xFFD700 if rank == 1 else 0xC0C0C0 if rank == 2 else 0xCD7F32 if rank == 3 else 0x800020
                        
                        audit_emb = discord.Embed(title=audit_title, color=audit_color)
                        if os.path.exists("LobbyTopRight.jpg"):
                            audit_file = discord.File("LobbyTopRight.jpg", filename="audit_logo.jpg")
                            audit_emb.set_thumbnail(url="attachment://audit_logo.jpg")
                        
                        breakdown = (
                            f"⚔️ **Member:** {member.mention}\n"
                            f"🛡️ **Arena Rank:** #{rank}\n"
                            f"📊 **Participation:** {log['participation']} Neural Pts\n"
                            f"⚔️ **Match Executions:** {game_kills[p_id]} kills ({log['kills']} XP)\n"
                            f"🩸 **First Blood Bonus:** {log['first_kill']} XP\n"
                            f"🥇 **Placement Value:** {log['placement']} XP\n"
                            f"💧 **Neural Imprint (XP) Gained:** +{processed_data.get(p_id, 0)}\n"
                        )
                        
                        if rank == 1:
                            breakdown += f"💰 **Winner's Prize:** +{total_flames_won} Flames\n"

                        lvl_m = m_stats.get('fiery_level', 1)
                        rank_m_name = self.ranks[min(lvl_m-1, len(self.ranks)-1)]

                        new_totals = (
                            f"🔥 **Total Flames in Vault:** {m_stats.get('balance', 0):,}\n"
                            f"💀 **Total Lifetime Executions:** {m_stats.get('kills', 0)}\n"
                            f"💧 **Total Echo Experience:** {m_stats.get('fiery_xp', 0):,}\n"
                            f"🔝 **Echo Level:** {lvl_m} ({rank_m_name})"
                        )

                        audit_emb.description = breakdown
                        audit_emb.add_field(name="💳 UPDATED member TOTALS", value=new_totals, inline=False)
                        audit_emb.set_footer(text=f"Edition #{edition} | The Guild watched your every move.")
                        
                        if os.path.exists("LobbyTopRight.jpg"): await audit_channel.send(file=audit_file, embed=audit_emb)
                        else: await audit_channel.send(embed=audit_emb)
                    except: pass

            ach_cog = self.bot.get_cog("Achievements")
            ach_text = ach_cog.get_achievement_summary(winner_final['id']) if ach_cog else "N/A"

            win_card = discord.Embed(title=f"👑 Echogames Winner 👑 # {edition}", color=0xFFD700)
            win_card.set_image(url=winner_final['avatar'])
            
            log_win = fxp_log[winner_final['id']]
            winner_raw_fin = self.get_user(winner_final['id'])
            winner_user_db_fin = dict(winner_raw_fin) if winner_raw_fin else {}
            u_class_win = winner_user_db_fin.get('class', 'None')
            b_xp_win = 1.0
            if u_class_win == "Submissive": b_xp_win = 1.25
            elif u_class_win in ["Switch", "Exhibitionist"]: b_xp_win = 1.14 if u_class == "Switch" else 0.80
            total_fxp_win = processed_data.get(winner_final['id'], 0)
            
            details_card = discord.Embed(title="📜 Detailed Performance", color=0xFFD700)
            breakdown_text = (f"🛡️ **Participation:** {log_win['participation']} XP\n"
                            f"⚔️ **Kills:** {log_win['kills']} XP\n"
                            f"🩸 **First Kill:** {log_win['first_kill']} XP\n"
                            f"🥇 **Placement:** {log_win['placement']} XP\n"
                            f"✨ **Class Multiplier:** x{b_xp_win}\n"
                            f"**Total XP Gained: {total_fxp_win}**")
            details_card.add_field(name="💧 ECHO EXPERIENCE RECAP", value=breakdown_text, inline=False)
            
            with self.get_db_connection() as conn:
                w_rank_query = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE wins > ?", (f_u.get('wins', 0),)).fetchone()
                w_rank = w_rank_query['r'] if w_rank_query else "N/A"
                k_rank_query = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE kills > ?", (f_u.get('kills', 0),)).fetchone()
                k_rank = k_rank_query['r'] if k_rank_query else "N/A"
                g_rank_query = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE games_played > ?", (f_u.get('games_played', 0),)).fetchone()
                g_rank = g_rank_query['r'] if g_rank_query else "N/A"
                
                conn.execute("UPDATE users SET current_win_streak = current_win_streak + 1 WHERE id = ?", (winner_final['id'],))
                conn.execute("UPDATE users SET max_win_streak = MAX(max_win_streak, current_win_streak) WHERE id = ?", (winner_final['id'],))
                conn.commit()
                
                updated_f_u = conn.execute("SELECT current_win_streak, max_win_streak, wins, games_played FROM users WHERE id = ?", (winner_final['id'],)).fetchone()
                
                total_arena_wins = updated_f_u['wins']
                total_participations = updated_f_u['games_played']
                current_streak = updated_f_u['current_win_streak']
                max_streak = updated_f_u['max_win_streak']
                lifetime_flame_pool = total_arena_wins * 15000 
            
            rank_text = f"🏆 **Wins:** Rank #{w_rank}\n⚔️ **Kills:** Rank #{k_rank}\n🎮 **Games:** Rank #{g_rank}"
            win_card.add_field(name="📊 SERVER STATS", value=rank_text, inline=True)
            
            legacy_text = (f"👑 **Total Arena Wins:** {total_arena_wins}\n"
                           f"📝 **Total Participations:** {total_participations}\n"
                           f"🔥 **Lifetime Arena Flames:** {lifetime_flame_pool:,}F")
            win_card.add_field(name="🏛️ VICTOR'S LEGACY", value=legacy_text, inline=False)
            
            streak_text = (f"⚡ **Current Win Streak:** {current_streak}\n"
                           f"🌌 **All-Time Max Streak:** {max_streak}")
            details_card.add_field(name="🧬 EVOLUTION PROTOCOL (STREAKS)", value=streak_text, inline=False)
            details_card.add_field(name="🔥 STANDING", value=f"Rank {lvl}: **{rank_name}**", inline=False)
            details_card.add_field(name="💰 PRIZE POOL", value=f"**Flames:** {total_flames_won}", inline=False)
            details_card.add_field(name="🏅 ACHIEVEMENTS", value=ach_text, inline=False)
            
            view = WinnerDetailsViewSFW(details_card)
            self.bot.add_view(view)
            await channel.send(embed=win_card, view=view)

        except Exception as e:
            print(f"# CRITICAL ENGINE FAILURE: {e}")
            traceback.print_exc()
            await channel.send("❌ A critical dungeon error occurred. Call Dev.rodz.")
        finally:
            if channel.id in self.current_survivors:
                del self.current_survivors[channel.id]
            if channel.id in self.active_battles:
                self.active_battles.remove(channel.id)

class StatusCheckSFW(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.alive_sentences = [
            "Still breathing and fighting for more, aren't you? {mention} is alive.",
            "The blows haven't broken you yet. {mention} is still in the game.",
            "A stubborn fighter. {mention} is still standing in the pit.",
            "You look good in the arena. {mention} is very much alive.",
            "Your heart is still racing for the victory. {mention} survives."
        ]
        self.dead_sentences = [
            "Cold, quiet, and completely defeated. {mention} is dead.",
            "Another soul for the furnace. {mention} has been eliminated.",
            "The arena is empty for you. {mention} has fallen.",
            "Combat reached its limit. {mention} is out of the game.",
            "Silence suits you, loser. {mention} is dead."
        ]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        content = message.content.lower().strip()
        engine = self.bot.get_cog("IgnisEngineSFW")
        if not engine: return

        if content in ["i am alive", "i am dead"]:
            if message.channel.id not in engine.active_battles:
                return 
            
            survivors = engine.current_survivors.get(message.channel.id, [])
            is_survivor = message.author.id in survivors

            if content == "i am alive":
                if is_survivor:
                    msg = random.choice(self.alive_sentences).format(mention=message.author.mention)
                    await message.channel.send(f"⚔️ **{msg}**")
                else:
                    await message.channel.send(f"🥀 **Don't lie to the Guild, ghost. You are already broken and gone.**")
            
            elif content == "i am dead":
                if not is_survivor:
                    msg = random.choice(self.dead_sentences).format(mention=message.author.mention)
                    await message.channel.send(f"💀 **{msg}**")
                else:
                    await message.channel.send(f"🛡️ **Not yet, brave soul. You're still here to entertain us.**")

class PersistentLobbyLauncherSFW(commands.Cog):
    """This Cog ensures that if the bot restarts, it 'remembers' to listen for lobby button clicks per server."""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        import sys as _sys
        main = _sys.modules['__main__']
        
        self.bot.add_view(WinnerDetailsViewSFW(None))
        
        try:
            with main.get_db_connection() as conn:
                cursor = conn.execute("SELECT DISTINCT guild_id FROM sfw_lobby_participants")
                guilds = cursor.fetchall()
                
                engine = self.bot.get_cog("IgnisEngineSFW")
                
                for row in guilds:
                    g_id = row[0]
                    view = LobbyViewSFW(owner=None, edition=0, guild_id=g_id)
                    
                    self.bot.add_view(view)
                    
                    if engine:
                        engine.current_lobbies[g_id] = view
                        
                print(f"⚔️ Ignis SFW Persistence Protocol: Registered {len(guilds)} independent server lobbies.")
        except Exception as e:
            print(f"Persistence Rehydration Error (SFW): {e}")

async def setup(bot):
    import sys as _sys_setup
    main = _sys_setup.modules['__main__']
    
    ignis_engine_sfw = IgnisEngineSFW(
        bot, 
        main.update_user_stats_async, 
        main.get_user, 
        main.fiery_embed, 
        main.get_db_connection, 
        main.RANKS, 
        main.CLASSES, 
        main.AUDIT_CHANNEL_ID
    )
    await bot.add_cog(ignis_engine_sfw)
    
    engine_control_sfw = EngineControlSFW(
        bot,
        main.fiery_embed,
        main.save_game_config,
        main.get_db_connection
    )
    await bot.add_cog(engine_control_sfw)

    fiery_extensions_sfw = FieryExtensionsSFW(
        bot, 
        main.get_db_connection, 
        main.update_user_stats_async, 
        main.fiery_embed, 
        main.AUDIT_CHANNEL_ID
    )
    await bot.add_cog(fiery_extensions_sfw)

    await bot.add_cog(StatusCheckSFW(bot))
    
    await bot.add_cog(PersistentLobbyLauncherSFW(bot))
