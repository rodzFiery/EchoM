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

    @discord.ui.button(label="Examine Crime File", style=discord.ButtonStyle.primary, emoji="🔞", custom_id="crime_winner_details")
    async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=self.details_embed, ephemeral=True)


class CrimeLobbyView(discord.ui.View):
    def __init__(self, owner=None, edition=0, guild_id=None):
        super().__init__(timeout=None)
        self.owner = owner
        self.edition = edition
        self.guild_id = guild_id
        self.active = True
        
        # Unique IDs are generated dynamically to bind this view to this guild's active state
        join_id = f"crime_join_{self.guild_id}" if self.guild_id else "crime_join_btn_default"
        start_id = f"crime_start_{self.guild_id}" if self.guild_id else "crime_start_btn_default"

        join_btn = discord.ui.Button(label="Sign the Blood Pact", style=discord.ButtonStyle.success, emoji="🫦", custom_id=join_id)
        join_btn.callback = self.join_button_callback
        self.add_item(join_btn)

        start_btn = discord.ui.Button(label="Initiate Heist Operation", style=discord.ButtonStyle.danger, emoji="⛓️", custom_id=start_id)
        start_btn.callback = self.start_button_callback
        self.add_item(start_btn)

    def fetch_teams_from_db(self, engine, guild_id):
        """Helper to build a clean 15-team squad map directly from the database state."""
        teams = {i: [None, None] for i in range(1, 16)}
        try:
            with engine.get_db_connection() as conn:
                # Safe migration recovery inside DB call
                try:
                    conn.execute("SELECT team_num FROM crime_lobby_participants LIMIT 1")
                except sqlite3.OperationalError:
                    conn.execute("DROP TABLE IF EXISTS crime_lobby_participants")
                
                conn.execute("CREATE TABLE IF NOT EXISTS crime_lobby_participants (guild_id INTEGER, user_id INTEGER, team_num INTEGER, slot_num INTEGER)")
                rows = conn.execute("SELECT user_id, team_num, slot_num FROM crime_lobby_participants WHERE guild_id = ?", (guild_id,)).fetchall()
                for r in rows:
                    uid, t_num, s_num = r[0], r[1], r[2]
                    if t_num in teams and s_num in [0, 1]:
                        teams[t_num][s_num] = uid
        except Exception as e:
            print(f"Error fetching teams from DB: {e}")
        return teams

    def render_lobby_embeds(self, teams, server_edition, edition_num):
        # Count current participants
        all_players = []
        for t_idx, slots in teams.items():
            for player in slots:
                if player:
                    all_players.append(player)

        # Embed 1: Lobby Status Details
        info_embed = discord.Embed(
            title=f"💦 Partners In Crime Spree # {edition_num} 💦", 
            description=f"**Syndicate Grid Server Edition: #{server_edition}**\n\nFind your partner in bondage, lock and load your weapons, and seal your signatures in blood to claim your stake of the vault.", 
            color=0xFF00FF
        )
        info_embed.add_field(
            name="⛓️ Active Syndicate Underworld Roster", 
            value=f"**{len(all_players)}** outlaws chained in cells... preparing tools.", 
            inline=False
        )

        # Embed 2: The Grid of Squad Teams
        teams_embed = discord.Embed(
            title="🫦 Underworld Cell Block Divisions",
            color=0xFF00FF
        )
        
        for t_idx, slots in teams.items():
            p1_mention = f"<@{slots[0]}>" if slots[0] else "*Unassigned*"
            p2_mention = f"<@{slots[1]}>" if slots[1] else "*Unassigned*"
            
            status_symbol = "👅" if (slots[0] and slots[1]) else "👣" if (slots[0] or slots[1]) else "🔒"
            
            # Show up to 15 squads, hiding empty squads past squad 6 to avoid hitting Discord embed character limits
            if slots[0] or slots[1] or t_idx <= 6:
                teams_embed.add_field(
                    name=f"{status_symbol} Cell Squad Unit {t_idx}", 
                    value=f"• **Dominant Partner:** {p1_mention}\n• **Submissive Partner:** {p2_mention}", 
                    inline=True
                )
            
        teams_embed.set_footer(text=f"Underworld Registration Board: {len(all_players)}/30 locked in.")
        return [info_embed, teams_embed]

    async def join_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not self.active:
            return await interaction.followup.send("❌ **The cell blocks are locked down.** The operation is already active.", ephemeral=True)

        engine = interaction.client.get_cog("PartnersInCrimeEngine")
        if not engine: 
            return await interaction.followup.send("❌ Internal Error: Engine not found.", ephemeral=True)

        # 1. Fetch synced team list directly from the database
        lobby_teams = self.fetch_teams_from_db(engine, interaction.guild.id)

        # 2. Check if the user is already signed up in any team
        user_already_registered = False
        for t_idx, slots in lobby_teams.items():
            if interaction.user.id in slots:
                user_already_registered = True
                break
                
        if user_already_registered:
            return await interaction.followup.send("🔗 **You are already chained to your cell block.** The keys are gone.", ephemeral=True)

        # 3. Find empty slots
        available_slots = []
        for t_idx, slots in lobby_teams.items():
            if slots[0] is None:
                available_slots.append((t_idx, 0))
            if slots[1] is None:
                available_slots.append((t_idx, 1))

        if not available_slots:
            return await interaction.followup.send("❌ **The cell blocks are packed!** No empty spots left.", ephemeral=True)

        # 4. Assign user randomly to one of the empty slots
        selected_team, selected_slot = random.choice(available_slots)
        lobby_teams[selected_team][selected_slot] = interaction.user.id

        # 5. Write assignment immediately to database
        with engine.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS crime_lobby_participants (guild_id INTEGER, user_id INTEGER, team_num INTEGER, slot_num INTEGER)")
            conn.execute("INSERT INTO crime_lobby_participants (guild_id, user_id, team_num, slot_num) VALUES (?, ?, ?, ?)", 
                         (interaction.guild.id, interaction.user.id, selected_team, selected_slot))
            conn.commit()
        
        try:
            # Query server stats
            server_edition = 1
            with engine.get_db_connection() as conn:
                row = conn.execute("SELECT server_edition FROM crime_server_stats WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
                if row:
                    server_edition = row[0]
            
            # Re-render both embeds with the freshly updated database configuration
            updated_embeds = self.render_lobby_embeds(lobby_teams, server_edition, self.edition)
            await interaction.message.edit(embeds=updated_embeds, view=self)
            await interaction.followup.send(f"🫦 **Pact Sealed!** You have been assigned to **Cell Squad Unit {selected_team}**.", ephemeral=True)
        except Exception as e:
            print(f"Crime Lobby Join Error: {e}")
            traceback.print_exc()
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
            conn.execute("CREATE TABLE IF NOT EXISTS ignis_settings (guild_id PRIMARY KEY, role_id INTEGER)")
            row = conn.execute("SELECT role_id FROM ignis_settings WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
            if row: 
                ignis_admin_role_id = row[0]

        user_perms = getattr(interaction.channel.permissions_for(interaction.user), 'manage_messages', False)
        is_admin = getattr(interaction.channel.permissions_for(interaction.user), 'administrator', False)
        is_staff = any(role.name in ["Staff", "Admin", "Moderator"] or role.id == ignis_admin_role_id for role in getattr(interaction.user, 'roles', []))
        is_staff = is_staff or user_perms or is_admin
        
        owner_id = getattr(self.owner, 'id', None)
        if owner_id and interaction.user.id != owner_id and not is_staff:
            return await interaction.followup.send("🔒 **Clearance Denied: Only the Ring Leader or Staff can launch this operation.**", ephemeral=True)
        
        # Load latest synced teams directly from database
        lobby_teams = self.fetch_teams_from_db(engine, interaction.guild.id)

        # Collect and filter active players (ignore empty slots completely)
        final_teams_list = []
        for t_idx, slots in lobby_teams.items():
            team_members = [player for player in slots if player is not None]
            if len(team_members) > 0:
                final_teams_list.append(team_members)

        # Flatten list to verify player headcount
        flat_players = [p for squad in final_teams_list for p in squad]

        if len(flat_players) < 4:
            return await interaction.followup.send("We need at least 4 devious outlaws inside the registration room to begin!", ephemeral=True)
        
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
        
        await interaction.channel.send("🚨 **THE SIRENS SCREAM... PARTNERS IN CRIME SPREE IS NOW LIVE!**")
        
        import sys as _sys_m
        main_mod = _sys_m.modules['__main__']
        final_edition = self.edition if self.edition != 0 else getattr(main_mod, "crime_game_edition", 1)
        
        # Launch battle using the dynamic pre-made squad arrangement
        asyncio.create_task(engine.start_battle_with_premade_teams(interaction.channel, final_teams_list, final_edition))
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
            "No honor among thieves. Strip down completely and pay your hot tax.",
            "You got caught red-handed. Shed those clothes and show your dirty crimes.",
            "The sirens are coming, and you're caught totally bare. Start striping.",
            "Partners in chains, partners in shame. Expose your hot surrender right now.",
            "Your heist failed. Pay the ultimate tax of complete exposure!"
        ]
        self._init_persistence()

    def _init_persistence(self):
        with self.get_db_connection() as conn:
            try:
                conn.execute("SELECT team_num FROM crime_lobby_participants LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("DROP TABLE IF EXISTS crime_lobby_participants")

            conn.execute("CREATE TABLE IF NOT EXISTS crime_lobby_participants (guild_id INTEGER, user_id INTEGER, team_num INTEGER, slot_num INTEGER)")
            conn.execute("CREATE TABLE IF NOT EXISTS crime_server_stats (guild_id PRIMARY KEY, server_edition INTEGER DEFAULT 1)")
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
            
            # Use partners.jpg as the core backdrop template
            bg_path = "partners.jpg"
            if os.path.exists(bg_path):
                bg = Image.open(bg_path).convert("RGBA")
            else:
                bg = Image.new("RGBA", (1366, 768), (10, 10, 30, 255))
            
            # The template golden squares are approximately 194x194 pixels
            av_size = 194
            
            # Load and size avatars
            a1 = Image.open(buffers[0]).convert("RGBA").resize((av_size, av_size))
            a2 = Image.open(buffers[1]).convert("RGBA").resize((av_size, av_size))
            a3 = Image.open(buffers[2]).convert("RGBA").resize((av_size, av_size))
            a4 = Image.open(buffers[3]).convert("RGBA").resize((av_size, av_size))
            
            # High-intensity red wash filter over the losers (Team B)
            a3_gray = ImageOps.grayscale(a3).convert("RGBA")
            a4_gray = ImageOps.grayscale(a4).convert("RGBA")
            red_overlay = Image.new("RGBA", (av_size, av_size), (255, 0, 0, 130))
            a3 = Image.alpha_composite(a3_gray, red_overlay)
            a4 = Image.alpha_composite(a4_gray, red_overlay)

            # --- PRECISE COORDINATES TO NEST WITHIN THE GOLDEN SQUARES ---
            # Team A (Left Side): 
            # - Left square bounds: x=115, y=318 (approx)
            # - Right square bounds: x=334, y=318 (approx)
            bg.paste(a1, (115, 318), a1)
            bg.paste(a2, (334, 318), a2)

            # Team B (Right Side):
            # - Left square bounds: x=937, y=318 (approx)
            # - Right square bounds: x=1157, y=318 (approx)
            bg.paste(a3, (937, 318), a3)
            bg.paste(a4, (1157, 318), a4)
            
            buf = io.BytesIO()
            bg.save(buf, format="PNG")
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"Crime Image Synthesizer Error: {e}")
            fallback = Image.new("RGBA", (1366, 768), (10, 10, 20, 255))
            buf = io.BytesIO()
            fallback.save(buf, format="PNG")
            buf.seek(0)
            return buf

    async def create_recap_image(self, winners, victims_list):
        """Synthesizes a visual layout depicting winners (massive sizes) and available targets (smaller profiles)."""
        try:
            async with aiohttp.ClientSession() as session:
                winner_buffers = []
                for w in winners:
                    async with session.get(w.display_avatar.url, timeout=10) as resp:
                        if resp.status == 200:
                            winner_buffers.append(io.BytesIO(await resp.read()))
                
                victim_buffers = []
                for v in victims_list:
                    async with session.get(v.display_avatar.url, timeout=10) as resp:
                        if resp.status == 200:
                            victim_buffers.append(io.BytesIO(await resp.read()))

            canvas_w = 1600
            canvas_h = 900
            bg_path = "1v1Background.jpg"
            bg = Image.open(bg_path).convert("RGBA").resize((canvas_w, canvas_h)) if os.path.exists(bg_path) else Image.new("RGBA", (canvas_w, canvas_h), (15, 5, 25, 255))
            
            # 1. DRAW WINNERS (Left Side - Prominent & Massive)
            w_size = 450
            for idx, buf in enumerate(winner_buffers[:2]):
                av = Image.open(buf).convert("RGBA").resize((w_size, w_size))
                av = ImageOps.expand(av, border=20, fill="#FF00FF") # Hot pink glowing border
                bg.paste(av, (80, 100 + (idx * 400)), av)

            # Draw central boundary line
            draw = ImageDraw.Draw(bg)
            draw.line((650, 50, 650, 850), fill=(255, 0, 255), width=15)

            # 2. DRAW TARGET DUOS (Right Side - Grid Structure of smaller profiles)
            v_size = 180
            x_start = 720
            y_start = 80
            spacing_x = 220
            spacing_y = 210

            for idx, buf in enumerate(victim_buffers[:12]): # Showcase top 12 available targets in the pool
                col = idx % 4
                row = idx // 4
                av = Image.open(buf).convert("RGBA").resize((v_size, v_size))
                av = ImageOps.expand(av, border=8, fill="#550011") # Dark red frame
                px = x_start + (col * spacing_x)
                py = y_start + (row * spacing_y)
                bg.paste(av, (px, py), av)

            buf = io.BytesIO()
            bg.save(buf, format="PNG")
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"Recap Canvas Generation Failure: {e}")
            fallback = Image.new("RGBA", (1600, 900), (15, 5, 25, 255))
            buf = io.BytesIO()
            fallback.save(buf, format="PNG")
            buf.seek(0)
            return buf

    async def start_battle_with_premade_teams(self, channel, pre_made_teams, edition):
        if channel.id in self.active_battles: 
            return
        self.active_battles.add(channel.id)

        try:
            await self.bot.wait_until_ready()
            
            # Convert user IDs to real member objects
            resolved_teams = []
            for team_players in pre_made_teams:
                resolved_members = []
                for p_id in team_players:
                    m = channel.guild.get_member(p_id) or await channel.guild.fetch_member(p_id)
                    if m:
                        resolved_members.append(m)
                
                # Setup proper Duo targets based on registered headcount
                if len(resolved_members) == 2:
                    resolved_teams.append({
                        "p1": resolved_members[0],
                        "p2": resolved_members[1],
                        "name": f"😈 {resolved_members[0].display_name} & {resolved_members[1].display_name}"
                    })
                elif len(resolved_members) == 1:
                    resolved_teams.append({
                        "p1": resolved_members[0],
                        "p2": resolved_members[0], # Clone for visualization protection
                        "name": f"🐺 Rogue Renegade: {resolved_members[0].display_name}"
                    })

            # Shuffle battle matchup sequence to keep it dynamic
            random.shuffle(resolved_teams)
            self.current_survivors[channel.id] = resolved_teams.copy()

            # Display Teams
            roster_desc = ""
            for idx, duo in enumerate(resolved_teams, 1):
                roster_desc += f"**Squad {idx}:** {duo['name']}\n"
                
            roster_emb = self.fiery_embed(
                f"⛓️ Operational Syndicate Roster - Heist Spree #{edition} ⛓️", 
                f"The gangs have locked targets and marked territories:\n\n" + roster_desc, 
                color=0xFF00FF
            )
            await channel.send(embed=roster_emb)
            await asyncio.sleep(5)

            # Track initial losers to present them as the pool of targets inside the recap image
            defeated_victims = []

            # Fight loop
            while len(resolved_teams) > 1:
                t1 = resolved_teams.pop(random.randrange(len(resolved_teams)))
                t2 = resolved_teams.pop(random.randrange(len(resolved_teams)))

                await channel.send(f"💥 **TERRITORY INVASION!** {t1['name']} corners {t2['name']} in a dark alleyway...")
                await asyncio.sleep(3)

                # Execute Fight
                winner, loser = (t1, t2) if random.random() < 0.5 else (t2, t1)
                resolved_teams.append(winner)
                
                # Record loser members for our Target Pool display
                if loser['p1'] not in defeated_victims:
                    defeated_victims.append(loser['p1'])
                if loser['p2'] not in defeated_victims and loser['p2'] != loser['p1']:
                    defeated_victims.append(loser['p2'])

                # Update survivors cache
                if channel.id in self.current_survivors:
                    self.current_survivors[channel.id] = resolved_teams.copy()

                # Synthesize 2v2 Canvas using template background coordinates
                arena_image = await self.create_duo_arena_image(
                    winner['p1'].display_avatar.url, winner['p2'].display_avatar.url,
                    loser['p1'].display_avatar.url, loser['p2'].display_avatar.url
                )
                file = discord.File(fp=arena_image, filename="arena_duo.png")

                emb = discord.Embed(
                    title=f"🫦 {winner['name']} DOMINATES AND WIPES OUT {loser['name']}!", 
                    description=f"Stripped of armor and dignity, {loser['name']} has been cast out of the heist zone.", 
                    color=0xFF00FF
                )
                emb.set_image(url="attachment://arena_duo.png")
                await channel.send(file=file, embed=emb)
                await asyncio.sleep(5)

            # We have an absolute Winning Duo
            champion_duo = resolved_teams[0]
            # Track list of winner IDs. Each winner must use their own decree individually!
            self.reign_of_terror[channel.id] = [champion_duo['p1'].id, champion_duo['p2'].id]

            # Rewards Implementation
            for winner_member in [champion_duo['p1'], champion_duo['p2']]:
                await self.update_user_stats(winner_member.id, amount=30000, xp_gain=3000, wins=1, source="Syndicate Win")

            win_emb = discord.Embed(
                title=f"👑 REIGNING SYNDICATE OVERLORDS 👑",
                description=(
                    f"All hail our absolute Masters of the Vault: **{champion_duo['p1'].mention}** & **{champion_duo['p2'].mention}**!\n\n"
                    f"They have cleaned out the cache! Both partners claim **30,000 Flames** and **3,000 XP**.\n\n"
                    f"🔞 **Supreme Victor Decrees:** You hold absolute dominance over the defeated. "
                    f"**EACH** partner has their own private pick! Run `!strip @victim1 @victim2` to force your targets into submission!"
                ),
                color=0xFFD700
            )
            
            # Setup Winner detail layout cards
            details_card = discord.Embed(title="📜 Dossier: The Syndicate Vault Breakers", color=0xFFD700)
            details_card.add_field(name="Heist Outcome", value="All defense layers neutralized. Treasures divided 50/50 under covenant rules.")
            view = CrimeWinnerDetailsView(details_card)
            self.bot.add_view(view)

            await channel.send(embed=win_emb, view=view)
            await asyncio.sleep(2)

            # Execute RECAP PROTOCOL
            recap_banner = await self.create_recap_image([champion_duo['p1'], champion_duo['p2']], defeated_victims)
            recap_file = discord.File(fp=recap_banner, filename="crime_recap.png")
            recap_emb = discord.Embed(
                title="🎯 SYNDICATE RECAP: THE HIT LIST IS LIVE 🎯",
                description="The heist is won, but the contract is incomplete. Below is the visual board containing your Overlords (left) and the remaining vulnerable targets available to be forced into submission (right). Execute your decree now!",
                color=0xFF00FF
            )
            recap_emb.set_image(url="attachment://crime_recap.png")
            await channel.send(file=recap_file, embed=recap_emb)

        except Exception as e:
            print(f"# CRITICAL CRIME ENGINE FAILURE: {e}")
            traceback.print_exc()
            await channel.send("❌ A critical syndicate error occurred. Call Dev.rodz.")
        finally:
            if channel.id in self.current_survivors:
                del self.current_survivors[channel.id]
            if channel.id in self.active_battles:
                self.active_battles.remove(channel.id)


class CrimeEngineControl(commands.Cog):
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
                return await ctx.send("❌ **An active heist is already running.** Clear current operations first.")
            if ctx.guild.id in engine.current_lobbies:
                return await ctx.send("❌ **Lobby gates are already open in this city.**")

        with self.get_db_connection() as conn:
            # Re-migration safety check before setting up the game lobby
            try:
                conn.execute("SELECT team_num FROM crime_lobby_participants LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("DROP TABLE IF EXISTS crime_lobby_participants")

            conn.execute("CREATE TABLE IF NOT EXISTS crime_lobby_participants (guild_id INTEGER, user_id INTEGER, team_num INTEGER, slot_num INTEGER)")
            conn.execute("DELETE FROM crime_lobby_participants WHERE guild_id = ?", (ctx.guild.id,))
            conn.execute("CREATE TABLE IF NOT EXISTS crime_server_stats (guild_id INTEGER PRIMARY KEY, server_edition INTEGER DEFAULT 1)")
            row = conn.execute("SELECT server_edition FROM crime_server_stats WHERE guild_id = ?", (ctx.guild.id,)).fetchone()
            server_edition = row[0] if row else 1
            conn.commit()

        # Set game edition variables globally inside main
        if not hasattr(main, "crime_game_edition"):
            main.crime_game_edition = 1

        # Instantiate lobby and generate dynamic layout cards
        view = CrimeLobbyView(ctx.author, main.crime_game_edition, ctx.guild.id)
        self.bot.add_view(view)

        if engine: 
            engine.current_lobbies[ctx.guild.id] = view

        # Populate starting empty dictionary layout directly
        teams = {i: [None, None] for i in range(1, 16)}
        embeds = view.render_lobby_embeds(teams, server_edition, main.crime_game_edition)
        await ctx.send(embeds=embeds, view=view)
        
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
            return await ctx.send("❌ **No syndicate rulers are active in this territory.**")

        if ctx.author.id not in active_winners:
            return await ctx.send("🫦 **Only the reigning partners of this heist hold the power of submission, or you already executed your pick!**")

        sentence = random.choice(engine.flash_sentences)
        
        embed = self.fiery_embed(
            "Underworld Submission Mandate", 
            f"📸 {ctx.author.mention} signs the warrant of absolute exposure over the defeated targets...\n\n"
            f"**\"{sentence}\"**\n\n"
            f"🔞 {m1.mention} & {m2.mention}, by blood-oath syndicate law, **YOU MUST FLASH!**",
            color=0xFF00FF
        )
        await ctx.send(content=f"{m1.mention} {m2.mention}", embed=embed)
        
        # Safe removal of only the command sender's ID from the registry
        engine.reign_of_terror[ctx.channel.id].remove(ctx.author.id)
        
        # Clean the active channel entry from cache only when both winners have depleted their charges
        if not engine.reign_of_terror[ctx.channel.id]:
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
    
    crime_engine_control = CrimeEngineControl(
        bot,
        main.fiery_embed,
        main.save_game_config,
        main.get_db_connection
    )
    await bot.add_cog(crime_engine_control)
