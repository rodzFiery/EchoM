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

# Importação do Lexicon para as frases de efeito
from lexicon import FieryLexicon

# ==============================================================================
# VIEW SYSTEM
# ==============================================================================

class CrimeWinnerDetailsView(discord.ui.View):
    def __init__(self, details_embed):
        super().__init__(timeout=None)
        self.details_embed = details_embed

    @discord.ui.button(label="View Case File", style=discord.ButtonStyle.primary, emoji="📁", custom_id="crime_winner_details")
    async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=self.details_embed, ephemeral=True)


class CrimeLobbyView(discord.ui.View):
    def __init__(self, owner=None, edition=0, guild_id=None):
        super().__init__(timeout=None)
        self.owner = owner
        self.edition = edition
        self.guild_id = guild_id
        self.participants = []
        self.active = True
        
        # --- DYNAMIC CUSTOM ID FIX ---
        join_id = f"crime_join_{self.guild_id}" if self.guild_id else "crime_join_button"
        start_id = f"crime_start_{self.guild_id}" if self.guild_id else "crime_start_button"

        join_btn = discord.ui.Button(label="Sign the Pact", style=discord.ButtonStyle.success, emoji="🖋️", custom_id=join_id)
        join_btn.callback = self.join_button_callback
        self.add_item(join_btn)

        start_btn = discord.ui.Button(label="Lock Cells and Begin", style=discord.ButtonStyle.danger, emoji="⛓️", custom_id=start_id)
        start_btn.callback = self.start_button_callback
        self.add_item(start_btn)

        # --- Persistence Rehydration ---
        if self.guild_id:
            try:
                import sys as _sys
                main = _sys.modules['__main__']
                with main.get_db_connection() as conn:
                    conn.execute("CREATE TABLE IF NOT EXISTS crime_lobby_participants (guild_id INTEGER, user_id INTEGER)")
                    rows = conn.execute("SELECT user_id FROM crime_lobby_participants WHERE guild_id = ?", (self.guild_id,)).fetchall()
                    self.participants = [r[0] for r in rows]
            except Exception as e:
                print(f"Crime Rehydration Error: {e}")

    async def join_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not self.active:
            return await interaction.followup.send("❌ **The gates are locked.** The syndicate has already left.", ephemeral=True)

        engine = interaction.client.get_cog("PartnersInCrimeEngine")
        if not engine: 
            return

        with engine.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS crime_lobby_participants (guild_id INTEGER, user_id INTEGER)")
            check = conn.execute("SELECT 1 FROM crime_lobby_participants WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, interaction.user.id)).fetchone()
            if check:
                return await interaction.followup.send("🔗 **You are already chained to a cell partner.** There is no backing out.", ephemeral=True)
            
            conn.execute("INSERT INTO crime_lobby_participants (guild_id, user_id) VALUES (?, ?)", (interaction.guild.id, interaction.user.id))
            conn.commit()

        with engine.get_db_connection() as conn:
            rows = engine.get_db_connection().execute("SELECT user_id FROM crime_lobby_participants WHERE guild_id = ?", (interaction.guild.id,)).fetchall()
            self.participants = [r[0] for r in rows]
        
        try:
            embed = interaction.message.embeds[0]
            embed.set_field_at(1 if len(embed.fields) > 1 else 0, name=f"👥 {len(self.participants)} Partners Recruited", value="*Whispering in the shadows, dividing the cut...*", inline=False)
            await interaction.message.edit(embed=embed, view=self)
            await interaction.followup.send("🤝 **The blood pact is sealed.** You are officially in the syndicate.", ephemeral=True)
        except Exception as e:
            print(f"Crime Lobby Join Error: {e}")
            await interaction.followup.send("The Syndicate ledger glitched but your signature was captured!", ephemeral=True)

    async def start_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        engine = interaction.client.get_cog("PartnersInCrimeEngine")
        if not engine:
            for name, cog in interaction.client.cogs.items():
                if "partnersincrimeengine" in name.lower():
                    engine = cog
                    break

        if not engine: 
            print("DEBUG: PartnersInCrimeEngine Cog NOT FOUND during start click.")
            return

        ignis_admin_role_id = None
        with engine.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS ignis_settings (guild_id INTEGER PRIMARY KEY, role_id INTEGER)")
            row = conn.execute("SELECT role_id FROM ignis_settings WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
            if row: 
                ignis_admin_role_id = row[0]

        user_perms = getattr(interaction.channel.permissions_for(interaction.user), 'manage_messages', False)
        is_admin = getattr(interaction.channel.permissions_for(interaction.user), 'administrator', False)
        is_staff = any(role.name in ["Staff", "Admin", "Moderator"] or role.id == ignis_admin_role_id for role in getattr(interaction.user, 'roles', []))
        is_staff = is_staff or user_perms or is_admin
        
        owner_id = getattr(self.owner, 'id', None)
        if owner_id and interaction.user.id != owner_id and not is_staff:
            return await interaction.followup.send("🔒 **Clearance Denied: Only the Mob Boss or Staff can launch this heist.**", ephemeral=True)
        
        with engine.get_db_connection() as conn:
            rows = conn.execute("SELECT user_id FROM crime_lobby_participants WHERE guild_id = ?", (interaction.guild.id,)).fetchall()
            self.participants = [r[0] for r in rows]

        if len(self.participants) < 4:
            return await interaction.followup.send("We need at least 4 outlaws to form opposing teams!", ephemeral=True)
        
        guild_games = 0
        for channel_id in engine.active_battles:
            ch = interaction.client.get_channel(channel_id)
            if ch and ch.guild and ch.guild.id == interaction.guild.id:
                guild_games += 1
        
        if guild_games >= 2:
            return await interaction.followup.send("❌ **The streets are already full of conflict.** Wait for other operations to clean up.", ephemeral=True)

        self.active = False

        if interaction.guild.id in engine.current_lobbies:
            del engine.current_lobbies[interaction.guild.id]

        with engine.get_db_connection() as conn:
            conn.execute("DELETE FROM crime_lobby_participants WHERE guild_id = ?", (interaction.guild.id,))
            conn.commit()
        
        await interaction.channel.send("🚨 **THE ALARMS SCREAM... PARTNERS IN CRIME SPREE HAS BEGUN!**")
        
        import sys as _sys_m
        main_mod = _sys_m.modules['__main__']
        final_edition = self.edition if self.edition != 0 else getattr(main_mod, "crime_game_edition", 1)
        
        asyncio.create_task(engine.start_battle(interaction.channel, list(self.participants), final_edition))
        self.stop()

# ==============================================================================
# CORE COG ENGINE
# ==============================================================================

class PartnersInCrimeEngine(commands.Cog):
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
        self.reign_of_terror = {}  # Tracks last winner duos per channel

        self.flash_sentences = [
            "No honor among thieves. Strip down and pay your dues.",
            "You got caught red-handed. Shed the clothes and show your crimes.",
            "The sirens are coming, and you're caught bare. Start striping.",
            "Partners in chains, partners in shame. Expose your surrender.",
            "Your heist failed. Pay the ultimate tax of exposure right now!"
        ]
        self._init_persistence()

    def _init_persistence(self):
        with self.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS crime_lobby_participants (guild_id INTEGER, user_id INTEGER)")
            conn.execute("CREATE TABLE IF NOT EXISTS crime_server_stats (guild_id INTEGER PRIMARY KEY, server_edition INTEGER DEFAULT 1)")
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

    async def create_duo_arena_image(self, d1_p1_url, d1_p2_url, d2_p1_url, d2_p2_url):
        try:
            async with aiohttp.ClientSession() as session:
                urls = [d1_p1_url, d1_p2_url, d2_p1_url, d2_p2_url]
                buffers = []
                for url in urls:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status != 200:
                            raise Exception("Avatar download error")
                        buffers.append(io.BytesIO(await resp.read()))
            
            canvas_w = 1000
            canvas_h = 1000
            bg_path = "1v1Background.jpg"
            bg = Image.open(bg_path).convert("RGBA").resize((canvas_w, canvas_h)) if os.path.exists(bg_path) else Image.new("RGBA", (canvas_w, canvas_h), (10, 10, 30, 255))
            
            av_size = 200
            
            # Load and size avatars
            a1 = Image.open(buffers[0]).convert("RGBA").resize((av_size, av_size))
            a2 = Image.open(buffers[1]).convert("RGBA").resize((av_size, av_size))
            a3 = Image.open(buffers[2]).convert("RGBA").resize((av_size, av_size))
            a4 = Image.open(buffers[3]).convert("RGBA").resize((av_size, av_size))
            
            # Add borders
            a1 = ImageOps.expand(a1, border=8, fill="orange")
            a2 = ImageOps.expand(a2, border=8, fill="orange")
            
            # Losers get grayscale and red wash
            a3_gray = ImageOps.grayscale(a3).convert("RGBA")
            a4_gray = ImageOps.grayscale(a4).convert("RGBA")
            red_overlay = Image.new("RGBA", (av_size, av_size), (255, 0, 0, 100))
            a3 = Image.alpha_composite(a3_gray, red_overlay)
            a4 = Image.alpha_composite(a4_gray, red_overlay)
            a3 = ImageOps.expand(a3, border=8, fill="gray")
            a4 = ImageOps.expand(a4, border=8, fill="gray")

            # Paste Team 1 (Winners) left side
            bg.paste(a1, (50, 200), a1)
            bg.paste(a2, (270, 200), a2)

            # Paste Team 2 (Losers) right side
            bg.paste(a3, (510, 200), a3)
            bg.paste(a4, (730, 200), a4)
            
            draw = ImageDraw.Draw(bg)
            draw.line((480, 150, 500, 450), fill=(220, 0, 0), width=15)
            
            buf = io.BytesIO()
            bg.crop((0, 100, 1000, 550)).save(buf, format="PNG")
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"Crime Image Synthesizer Error: {e}")
            fallback = Image.new("RGBA", (1000, 450), (10, 10, 20, 255))
            buf = io.BytesIO()
            fallback.save(buf, format="PNG")
            buf.seek(0)
            return buf

    async def start_battle(self, channel, participants, edition):
        if channel.id in self.active_battles: 
            return
        self.active_battles.add(channel.id)

        import sys as _sys
        main = _sys.modules['__main__']
        audit_channel = self.bot.get_channel(self.audit_channel_id)

        try:
            await self.bot.wait_until_ready()
            
            members = []
            for p_id in participants:
                m = channel.guild.get_member(p_id) or await channel.guild.fetch_member(p_id)
                if m:
                    members.append(m)

            # Randomize and Pair Up
            random.shuffle(members)
            duos = []
            
            for i in range(0, len(members), 2):
                if i + 1 < len(members):
                    duos.append({
                        "p1": members[i],
                        "p2": members[i+1],
                        "name": f"🎭 {members[i].display_name} & {members[i+1].display_name}"
                    })
                else:
                    # Single player remaining gets paired with the ghost of a boss or a random member
                    duos.append({
                        "p1": members[i],
                        "p2": members[0],  # Duplicate for protection and visual synergy
                        "name": f"🐺 Solo Outlaw: {members[i].display_name}"
                    })

            self.current_survivors[channel.id] = duos.copy()

            # Display Teams
            roster_desc = ""
            for idx, duo in enumerate(duos, 1):
                roster_desc += f"**Team {idx}:** {duo['name']}\n"
                
            roster_emb = self.fiery_embed(
                f"Syndicate Roster - Spree #{edition}", 
                f"The gangs have carved out their territories:\n\n" + roster_desc, 
                color=0x00FFFF
            )
            await channel.send(embed=roster_emb)
            await asyncio.sleep(5)

            # Fight loop
            while len(duos) > 1:
                t1 = duos.pop(random.randrange(len(duos)))
                t2 = duos.pop(random.randrange(len(duos)))

                await channel.send(f"💥 **CLASH IN THE BACK ALLEY!** {t1['name']} encounters {t2['name']}...")
                await asyncio.sleep(3)

                # Execute Fight
                winner, loser = (t1, t2) if random.random() < 0.5 else (t2, t1)
                duos.append(winner)
                
                # Update survivors cache
                if channel.id in self.current_survivors:
                    self.current_survivors[channel.id] = duos.copy()

                # Synthesize 2v2 Canvas
                arena_image = await self.create_duo_arena_image(
                    winner['p1'].display_avatar.url, winner['p2'].display_avatar.url,
                    loser['p1'].display_avatar.url, loser['p2'].display_avatar.url
                )
                file = discord.File(fp=arena_image, filename="arena_duo.png")

                emb = discord.Embed(
                    title=f"⚔️ {winner['name']} WIPES OUT {loser['name']}!", 
                    description=f"In a shower of sparks and gunfire, {loser['name']} has been run off the turf.", 
                    color=0x00FF00
                )
                emb.set_image(url="attachment://arena_duo.png")
                await channel.send(file=file, embed=emb)
                await asyncio.sleep(5)

            # We have an absolute Winning Duo
            champion_duo = duos[0]
            self.reign_of_terror[channel.id] = [champion_duo['p1'].id, champion_duo['p2'].id]

            # Rewards Implementation
            for winner_member in [champion_duo['p1'], champion_duo['p2']]:
                await self.update_user_stats(winner_member.id, amount=30000, xp_gain=3000, wins=1, source="Syndicate Win")

            win_emb = discord.Embed(
                title=f"👑 CO-CHAMPIONS OF THE UNDERWORLD 👑",
                description=(
                    f"Congratulations to **{champion_duo['p1'].mention}** & **{champion_duo['p2'].mention}**!\n\n"
                    f"They have cleaned out the vault! Both earn **30,000 Flames** and **3,000 XP**.\n\n"
                    f"🔞 **Winner's Decree Ready:** You hold absolute command over the citizens. "
                    f"Run `!strip @victim1 @victim2` to execute your punishment!"
                ),
                color=0xFFD700
            )
            
            # Setup Winner detail layout cards
            details_card = discord.Embed(title="📜 Case File: The Grand Sieve", color=0xFFD700)
            details_card.add_field(name="Heist Details", value="All trace operations cleanly neutralized. Loot divided 50/50.")
            view = CrimeWinnerDetailsView(details_card)
            self.bot.add_view(view)

            await channel.send(embed=win_emb, view=view)

        except Exception as e:
            print(f"# CRITICAL CRIME ENGINE FAILURE: {e}")
            traceback.print_exc()
            await channel.send("❌ A critical syndicate error occurred. Call Dev.rodz.")
        finally:
            if channel.id in self.current_survivors:
                del self.current_survivors[channel.id]
            if channel.id in self.active_battles:
                self.active_battles.remove(channel.id)


class EngineControl(commands.Cog):
    def __init__(self, bot, fiery_embed, save_game_config, get_db_connection):
        self.bot = bot
        self.fiery_embed = fiery_embed
        self.save_game_config = save_game_config
        self.get_db_connection = get_db_connection

    @commands.command(name="crimepartners")
    async def crime_partners_start(self, ctx):
        """Launches a new Partners in Crime Lobby."""
        import sys
        main = sys.modules['__main__']
        
        engine = self.bot.get_cog("PartnersInCrimeEngine")
        if engine:
            if ctx.channel.id in engine.active_battles:
                return await ctx.send("❌ **A heist is already in progress.** Wait for the police pursuit to finish.")
            if ctx.guild.id in engine.current_lobbies:
                return await ctx.send("❌ **Registration is already open for this server.**")

        with self.get_db_connection() as conn:
            conn.execute("DELETE FROM crime_lobby_participants WHERE guild_id = ?", (ctx.guild.id,))
            conn.execute("CREATE TABLE IF NOT EXISTS crime_server_stats (guild_id INTEGER PRIMARY KEY, server_edition INTEGER DEFAULT 1)")
            row = conn.execute("SELECT server_edition FROM crime_server_stats WHERE guild_id = ?", (ctx.guild.id,)).fetchone()
            server_edition = row[0] if row else 1
            conn.commit()

        # Set game edition variables globally inside main
        if not hasattr(main, "crime_game_edition"):
            main.crime_game_edition = 1

        embed = discord.Embed(
            title=f"Partners In Crime Spree # {main.crime_game_edition}", 
            description=f"**Server Edition: #{server_edition}**\n\nFind a partner, load your mags, and sign the registry to secure your cut of the vault.", 
            color=0x00FFFF
        )
        embed.add_field(name="🧙‍♂️ 0 Partners Ready", value="Silent loading of rounds...", inline=False)
        
        view = CrimeLobbyView(ctx.author, main.crime_game_edition, ctx.guild.id)
        self.bot.add_view(view)

        if engine: 
            engine.current_lobbies[ctx.guild.id] = view

        await ctx.send(embed=embed, view=view)
        
        main.crime_game_edition += 1
        self.save_game_config()
        
        with self.get_db_connection() as conn:
            conn.execute("UPDATE crime_server_stats SET server_edition = server_edition + 1 WHERE guild_id = ?", (ctx.guild.id,))
            conn.commit()

    @commands.command(name="strip")
    async def crime_strip_command(self, ctx, m1: discord.Member, m2: discord.Member):
        """Allows winning duo to select exactly two victims to flash."""
        engine = self.bot.get_cog("PartnersInCrimeEngine")
        if not engine: 
            return

        active_winners = engine.reign_of_terror.get(ctx.channel.id)
        if not active_winners:
            return await ctx.send("❌ **No active heist winners are registered in this district.**")

        if ctx.author.id not in active_winners:
            return await ctx.send("🫦 **Only the reigning partners in crime hold the keys to this vault.**")

        sentence = random.choice(engine.flash_sentences)
        
        embed = self.fiery_embed(
            "Exhibitionist Decree", 
            f"📸 {ctx.author.mention} waves the syndicate contract over the targets...\n\n"
            f"**\"{sentence}\"**\n\n"
            f"🔞 {m1.mention} & {m2.mention}, by law of the underground, **YOU MUST FLASH!**",
            color=0xFF00FF
        )
        await ctx.send(content=f"{m1.mention} {m2.mention}", embed=embed)
        
        # Clear reign values after execution to prevent repeat abuse
        del engine.reign_of_terror[ctx.channel.id]


# ==============================================================================
# SETUP AND REGISTRATION
# ==============================================================================

async def setup(bot):
    import sys as _sys_setup
    main = _sys_setup.modules['__main__']
    
    crime_engine = PartnersInCrimeEngine(
        bot, 
        main.update_user_stats_async, 
        main.get_user, 
        main.fiery_embed, 
        main.get_db_connection, 
        main.RANKS, 
        main.CLASSES, 
        main.AUDIT_CHANNEL_ID
    )
    await bot.add_cog(crime_engine)
    
    engine_control = EngineControl(
        bot,
        main.fiery_embed,
        main.save_game_config,
        main.get_db_connection
    )
    await bot.add_cog(engine_control)
