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
from PIL import Image, ImageDraw, ImageOps, ImageEnhance, ImageFont
import io
import aiohttp

# Importação do Lexicon para as frases de efeito
from lexicon import FieryLexicon

# ==============================================================================
# VIEW SYSTEM (PERSISTENT COUPLING)
# ==============================================================================

class CrimeWinnerDetailsView(discord.ui.View):
    def __init__(self, details_embed=None):
        # Setting timeout to None makes the view persistent and never expire
        super().__init__(timeout=None)
        self.details_embed = details_embed

    @discord.ui.button(label="Examine Crime File", style=discord.ButtonStyle.primary, emoji="🔞", custom_id="crime_winner_details")
    async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Safe fallback if view was restored from cache without embed memory
        if not self.details_embed:
            self.details_embed = discord.Embed(
                title="📜 Dossier: The Syndicate Vault Breakers", 
                description="All defense layers neutralized. Treasures divided 50/50 under covenant rules.",
                color=0xFFD700
            )
        await interaction.response.send_message(embed=self.details_embed, ephemeral=True)


class CrimeLobbyView(discord.ui.View):
    def __init__(self, owner=None, edition=0, guild_id=None):
        # Setting timeout to None makes the view persistent and never expire
        super().__init__(timeout=None)
        self.owner = owner
        self.edition = edition
        self.guild_id = guild_id
        self.active = True
        
        # Hardcoded static custom_ids are mandatory for persistent views to prevent interaction failures after bot restarts
        join_btn = discord.ui.Button(label="Sign the Blood Pact", style=discord.ButtonStyle.success, emoji="🫦", custom_id="crime_lobby_join")
        join_btn.callback = self.join_button_callback
        self.add_item(join_btn)

        start_btn = discord.ui.Button(label="Initiate Heist Operation", style=discord.ButtonStyle.danger, emoji="⛓️", custom_id="crime_lobby_start")
        start_btn.callback = self.start_button_callback
        self.add_item(start_btn)

        repost_btn = discord.ui.Button(label="Repost Lobby Board", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="crime_lobby_repost")
        repost_btn.callback = self.repost_button_callback
        self.add_item(repost_btn)

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

            # Check if all 15 duos (30 spots total) are full to alert the lobby host
            current_participants_count = 0
            for t_idx, slots in lobby_teams.items():
                for p in slots:
                    if p is not None:
                        current_participants_count += 1

            if current_participants_count == 30:
                host_mention = f"<@{self.owner.id}>" if self.owner else "Ring Leader"
                await interaction.channel.send(
                    f"🚨 **ALL 15 DUOS REGISTERED!** {host_mention}, the Underworld Cell Block Divisions are completely full! You can now launch the heist operation!"
                )

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
                final_teams_list.append((t_idx, team_members))

        # Flatten list to verify player headcount
        flat_players = []
        for idx, squad in final_teams_list:
            for p in squad:
                flat_players.append(p)

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

    async def repost_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not self.active:
            return await interaction.followup.send("❌ **The cell blocks are locked down.** The operation is already active.", ephemeral=True)

        engine = interaction.client.get_cog("PartnersInCrimeEngine")
        if not engine: 
            return await interaction.followup.send("❌ Internal Error: Engine not found.", ephemeral=True)

        try:
            # 1. Disable the old message view to avoid duplicate inputs or clutter
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
        except Exception:
            pass

        # 2. Spawn a completely new cloned View instance with the same metadata settings
        new_view = CrimeLobbyView(self.owner, self.edition, self.guild_id)
        interaction.client.add_view(new_view)

        if interaction.guild.id in engine.current_lobbies:
            engine.current_lobbies[interaction.guild.id] = new_view

        # 3. Pull teams configuration fresh from DB 
        lobby_teams = self.fetch_teams_from_db(engine, interaction.guild.id)

        # Query stats
        server_edition = 1
        with engine.get_db_connection() as conn:
            row = conn.execute("SELECT server_edition FROM crime_server_stats WHERE guild_id = ?", (interaction.guild.id,)).fetchone()
            if row:
                server_edition = row[0]

        # 4. Build and send the lobby message down at the very bottom of the channel text history
        updated_embeds = new_view.render_lobby_embeds(lobby_teams, server_edition, self.edition)
        await interaction.channel.send(embeds=updated_embeds, view=new_view)
        await interaction.followup.send("🔄 **Lobby Board Reposted!** Board has been pushed to the bottom of the channel.", ephemeral=True)
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
        self.historical_match_squads = {} # Tracks exact member profiles per squad index to allow squad targeting commands

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
            
            # Use partners.jpg as the core backdrop template
            bg_path = "partners.jpg"
            if os.path.exists(bg_path):
                # Ensure the loaded canvas matches your custom template coordinates completely
                bg = Image.open(bg_path).convert("RGBA").resize((1423, 735))
            else:
                bg = Image.new("RGBA", (1423, 735), (10, 10, 30, 255))
            
            # The template spaces are exactly 204x220 pixels
            target_w = 204
            target_h = 220
            
            def crop_to_fit(image, tw, th):
                """Helper method executing central cropping (cover crop) to prevent distortion."""
                iw, ih = image.size
                iasp = iw / ih
                tasp = tw / th
                if iasp > tasp:
                    nw = int(th * iasp)
                    image = image.resize((nw, th), Image.Resampling.LANCZOS)
                    left = (nw - tw) // 2
                    image = image.crop((left, 0, left + tw, th))
                else:
                    nh = int(tw / iasp)
                    image = image.resize((tw, nh), Image.Resampling.LANCZOS)
                    top = (nh - th) // 2
                    image = image.crop((0, top, tw, top + th))
                return image

            # Load, cover-crop, and size avatars
            a1 = crop_to_fit(Image.open(buffers[0]).convert("RGBA"), target_w, target_h)
            a2 = crop_to_fit(Image.open(buffers[1]).convert("RGBA"), target_w, target_h)
            a3 = crop_to_fit(Image.open(buffers[2]).convert("RGBA"), target_w, target_h)
            a4 = crop_to_fit(Image.open(buffers[3]).convert("RGBA"), target_w, target_h)
            
            # High-intensity red wash filter over the losers (Team B)
            a3_gray = ImageOps.grayscale(a3).convert("RGBA")
            a4_gray = ImageOps.grayscale(a4).convert("RGBA")
            red_overlay = Image.new("RGBA", (target_w, target_h), (255, 0, 0, 130))
            a3 = Image.alpha_composite(a3_gray, red_overlay)
            a4 = Image.alpha_composite(a4_gray, red_overlay)

            # --- PRECISE COORDINATES TO NEST WITHIN THE SPACES ---
            # Team A (Left Side): 
            # - Slot 1 bounds: x=69, y=208
            # - Slot 2 bounds: x=317, y=208
            bg.paste(a1, (69, 208), a1)
            bg.paste(a2, (317, 208), a2)

            # Team B (Right Side):
            # - Slot 1 bounds: x=902, y=208
            # - Slot 2 bounds: x=1150, y=208
            bg.paste(a3, (902, 208), a3)
            bg.paste(a4, (1150, 208), a4)
            
            buf = io.BytesIO()
            bg.save(buf, format="PNG")
            buf.seek(0)
            return buf
        except Exception as e:
            print(f"Crime Image Synthesizer Error: {e}")
            fallback = Image.new("RGBA", (1423, 735), (10, 10, 20, 255))
            buf = io.BytesIO()
            fallback.save(buf, format="PNG")
            buf.seek(0)
            return buf

    async def create_recap_image(self, winners, victims_list):
        """Synthesizes a highly advanced visual layout matching recap.jpg template structure.
        Showcases the Overlord Winners on the Left and the remaining target cell blocks on the Right."""
        try:
            async with aiohttp.ClientSession() as session:
                winner_buffers = []
                for w in winners:
                    async with session.get(w.display_avatar.url, timeout=10) as resp:
                        if resp.status == 200:
                            winner_buffers.append(io.BytesIO(await resp.read()))
                
                # Group victims by squad index mapping: squad_id -> [list of members]
                grouped_victims = {}
                for v_team_num, v_member in victims_list:
                    if v_team_num not in grouped_victims:
                        grouped_victims[v_team_num] = []
                    # Keep unique entries only
                    if v_member not in grouped_victims[v_team_num]:
                        grouped_victims[v_team_num].append(v_member)

                # Pre-download victim avatars
                victim_avatars = {}
                for s_id, members in list(grouped_victims.items())[:6]: # Display top 6 squads neatly
                    for m in members:
                        async with session.get(m.display_avatar.url, timeout=10) as resp:
                            if resp.status == 200:
                                victim_avatars[m.id] = io.BytesIO(await resp.read())

            canvas_w = 1600
            canvas_h = 900
            
            # Load and map specifically to your custom recap.jpg template background
            bg_path = "recap.jpg"
            if os.path.exists(bg_path):
                bg = Image.open(bg_path).convert("RGBA").resize((canvas_w, canvas_h))
            else:
                bg = Image.open("1v1Background.jpg").convert("RGBA").resize((canvas_w, canvas_h)) if os.path.exists("1v1Background.jpg") else Image.new("RGBA", (canvas_w, canvas_h), (15, 5, 25, 255))
            
            draw = ImageDraw.Draw(bg)

            # 1. DRAW OVERLORD WINNERS (Left Side Column - Large Profiles)
            # Fits precisely on the left half of the template layout
            w_size = 360
            for idx, buf in enumerate(winner_buffers[:2]):
                av = Image.open(buf).convert("RGBA").resize((w_size, w_size))
                av = ImageOps.expand(av, border=15, fill="#FF00FF") # Glowing pink border
                bg.paste(av, (80, 80 + (idx * 410)), av)
                
                # Winner Title Labels
                draw.rectangle([80, 80 + (idx * 410) + w_size - 40, 80 + w_size + 30, 80 + (idx * 410) + w_size + 15], fill=(0, 0, 0, 220))
                draw.text((100, 80 + (idx * 410) + w_size - 30), f"HEIST OVERLORD", fill=(255, 215, 0))

            # Draw central dividing separation line
            draw.line((580, 40, 580, 860), fill=(255, 0, 255), width=8)

            # 2. DRAW TARGET DUOS GROUPED BY CELL SQUAD (Right Side Column Rows)
            # Accommodates up to 6 distinct cell squads stacked sequentially
            y_offset = 60
            for squad_idx, (squad_id, members) in enumerate(list(grouped_victims.items())[:6]):
                # Draw Squad Division Frame
                draw.rectangle([620, y_offset, 1540, y_offset + 35], fill=(85, 0, 17, 180))
                draw.text((635, y_offset + 8), f"CELL SQUAD UNIT #{squad_id}", fill=(255, 0, 255))
                
                # Draw both squad members inside this division row
                for m_idx, member in enumerate(members[:2]):
                    m_x = 640 + (m_idx * 450)
                    m_y = y_offset + 50
                    
                    if member.id in victim_avatars:
                        v_av = Image.open(victim_avatars[member.id]).convert("RGBA").resize((70, 70))
                        v_av = ImageOps.expand(v_av, border=3, fill="#550011") # Heavy red frame
                        bg.paste(v_av, (m_x, m_y), v_av)
                    
                    # Trim layout overflows
                    display_name = member.display_name if len(member.display_name) <= 18 else member.display_name[:15] + "..."
                    draw.text((m_x + 95, m_y + 22), display_name, fill=(255, 255, 255))
                    
                y_offset += 135

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
            
            # Reset and map channel match tracking history
            self.historical_match_squads[channel.id] = {}
            
            # Convert user IDs to real member objects
            resolved_teams = []
            for t_idx, team_players in pre_made_teams:
                resolved_members = []
                for p_id in team_players:
                    m = channel.guild.get_member(p_id) or await channel.guild.fetch_member(p_id)
                    if m:
                        resolved_members.append(m)
                
                # Setup proper Duo targets based on registered headcount
                if len(resolved_members) == 2:
                    team_payload = {
                        "id": t_idx,
                        "p1": resolved_members[0],
                        "p2": resolved_members[1],
                        "name": f"😈 {resolved_members[0].display_name} & {resolved_members[1].display_name}"
                    }
                    resolved_teams.append(team_payload)
                    self.historical_match_squads[channel.id][t_idx] = [resolved_members[0], resolved_members[1]]
                elif len(resolved_members) == 1:
                    team_payload = {
                        "id": t_idx,
                        "p1": resolved_members[0],
                        "p2": resolved_members[0], # Clone for visualization protection
                        "name": f"🐺 Rogue Renegade: {resolved_members[0].display_name}"
                    }
                    resolved_teams.append(team_payload)
                    self.historical_match_squads[channel.id][t_idx] = [resolved_members[0]]

            # Shuffle battle matchup sequence to keep it dynamic
            random.shuffle(resolved_teams)
            self.current_survivors[channel.id] = resolved_teams.copy()

            # Display Teams
            roster_desc = ""
            for duo in resolved_teams:
                roster_desc += f"**Squad {duo['id']}:** {duo['name']}\n"
                
            roster_emb = self.fiery_embed(
                f"⛓️ Operational Syndicate Roster - Heist Spree #{edition} ⛓️", 
                f"The gangs have locked targets and marked territories:\n\n" + roster_desc, 
                color=0xFF00FF
            )
            await channel.send(embed=roster_emb)
            await asyncio.sleep(5)

            # Track initial losers mapped with team index numbers to present them inside the recap image template
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
                
                # Record loser members coupled with squad identification
                defeated_victims.append((loser['id'], loser['p1']))
                if loser['p2'] != loser['p1']:
                    defeated_victims.append((loser['id'], loser['p2']))

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
                    title=f"🫦 Squad {winner['id']} DOMINATES AND WIPES OUT Squad {loser['id']}!", 
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
                title=f"👑 REIGNING SYNDICATE OVERLORDS: SQUAD {champion_duo['id']} 👑",
                description=(
                    f"All hail our absolute Masters of the Vault: **{champion_duo['p1'].mention}** & **{champion_duo['p2'].mention}**!\n\n"
                    f"They have cleaned out the cache! Both partners claim **30,000 Flames** and **3,000 XP**.\n\n"
                    f"🔞 **Supreme Victor Decrees:** You hold absolute dominance over the defeated. "
                    f"**EACH** partner has their own private pick! Run `!strip <squad_number>` (e.g. `!strip 12`) to force an entire squad into submission!"
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
            
            # Generate the detailed members available list for the Discord text embed description
            targets_text_list = ""
            # Group by squad units for text-based emphasis too
            txt_groups = {}
            for squad_id, member in defeated_victims:
                if squad_id not in txt_groups:
                    txt_groups[squad_id] = []
                if member not in txt_groups[squad_id]:
                    txt_groups[squad_id].append(member)
                    
            for squad_id, members in txt_groups.items():
                targets_text_list += f"\n**Cell Squad {squad_id}**\n"
                for member in members:
                    targets_text_list += f"• {member.mention} ({member.display_name})\n"

            recap_emb = discord.Embed(
                title="🎯 SYNDICATE RECAP: THE HIT LIST IS LIVE 🎯",
                description=(
                    "The heist is won, but the contract is incomplete. Below is the visual board containing your Overlords (left) and the remaining vulnerable targets available to be forced into submission (right).\n"
                    "Look up their **SQUAD #** printed on the cards and run `!strip <squad_number>` now!\n\n"
                    "**📋 ACTIVE REMAINING TARGETS:**" + targets_text_list
                ),
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
            
            # --- THE FIX: SAFETY UPSERT ON STATS ---
            # Using standard SQLite conflict resolution to initialize with 1 OR increment by 1 cleanly
            conn.execute("CREATE TABLE IF NOT EXISTS crime_server_stats (guild_id INTEGER PRIMARY KEY, server_edition INTEGER DEFAULT 1)")
            conn.execute(
                "INSERT INTO crime_server_stats (guild_id, server_edition) VALUES (?, 1) "
                "ON CONFLICT(guild_id) DO UPDATE SET server_edition = server_edition + 1",
                (ctx.guild.id,)
            )
            
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

    @commands.command(name="strip")
    async def crime_strip_command(self, ctx, squad_num: int):
        """Allows winning duo to target an entire team layout using its Squad ID index."""
        engine = self.bot.get_cog("PartnersInCrimeEngine")
        if not engine: 
            return

        active_winners = engine.reign_of_terror.get(ctx.channel.id)
        if not active_winners:
            return await ctx.send("❌ **No syndicate rulers are active in this territory.**")

        if ctx.author.id not in active_winners:
            return await ctx.send("🫦 **Only the reigning partners of this heist hold the power of submission, or you already executed your pick!**")

        # Pull match structural layouts from match tracking logs
        match_history = engine.historical_match_squads.get(ctx.channel.id)
        if not match_history or squad_num not in match_history:
            return await ctx.send(f"❌ **Squad #{squad_num} was not found inside the registration file of this operation cycle.**")

        target_members = match_history[squad_num]
        if not target_members:
            return await ctx.send("❌ Internal Error: Target squad is unassigned or empty.")

        sentence = random.choice(engine.flash_sentences)
        
        # Compile target mentions for proper announcements
        target_mentions_str = " & ".join([m.mention for m in target_members])
        
        embed = self.fiery_embed(
            "Underworld Submission Mandate", 
            f"📸 {ctx.author.mention} signs the warrant of absolute exposure over **Squad #{squad_num}**...\n\n"
            f"**\"{sentence}\"**\n\n"
            f"🔞 {target_mentions_str}, by blood-oath syndicate law, **YOU MUST FLASH!**",
            color=0xFF00FF
        )
        
        # Build ping headers to send out proper notifications
        ping_content = " ".join([m.mention for m in target_members])
        await ctx.send(content=ping_content, embed=embed)
        
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
    
    # Register the views globally with the bot so they survive reboots and never fail / fail to interact
    bot.add_view(CrimeWinnerDetailsView())
    bot.add_view(CrimeLobbyView())
    
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
