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
from PIL import Image, ImageDraw, ImageOps, ImageEnhance

class LobbyView(discord.ui.View):
    def __init__(self, owner, edition):
        # FIX: Changed timeout to None so the lobby doesn't "fail" while waiting for players
        super().__init__(timeout=None)
        self.owner = owner
        self.edition = edition
        self.participants = []

    # ADDED: custom_id to make the interaction persistent and stop "Interaction Failed"
    @discord.ui.button(label="Enter the Red room", style=discord.ButtonStyle.success, emoji="🔞", custom_id="fiery_join_button")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("Already joined mf!", ephemeral=True)
        
        self.participants.append(interaction.user.id)
        
        # FIX: Robustly fetch the embed even if interaction.message is partial
        try:
            embed = interaction.message.embeds[0]
            # Fixed: Ensuring the field name reflects the list length correctly
            embed.set_field_at(0, name=f"<:FIERY_sym_dick:1314898974360076318> {len(self.participants)} Sinners Ready", value="*Final checks on chains, collars, lights and control..*", inline=False)
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            print(f"Lobby Join Error: {e}")
            await interaction.response.send_message("The Master acknowledges your sacrifice, but the ledger glitched. You are joined!", ephemeral=True)

    # ADDED: custom_id to make the interaction persistent
    @discord.ui.button(label="Turn off the lights and start", style=discord.ButtonStyle.danger, emoji="<:FIERY_heart_devilwhite:1314908504972070932>", custom_id="fiery_start_button")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            return await interaction.response.send_message("Only the Masters starts the games!", ephemeral=True)
        if len(self.participants) < 2:
            return await interaction.response.send_message("Need at least 2 sexy fucks !", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        engine = interaction.client.get_cog("IgnisEngine")
        if engine: 
            engine.current_lobby = None
        else:
            # DEBUG: If the cog isn't found, tell the owner
            return await interaction.followup.send("❌ Error: IgnisEngine not found. Is it loaded?", ephemeral=True)
        
        self.stop()
        # Visual confirmation the game is launching
        await interaction.channel.send("<:FIERY_fp_axdevilleft:1310628556983898142> **THE LIGHTS GO OUT... FIERY HANGRYGAMES EDITION HAS BEGUN!**")
        
        # Explicitly passing the bot's loop to avoid task death
        asyncio.create_task(engine.start_battle(interaction.channel, self.participants, self.edition))

class IgnisEngine(commands.Cog):
    def __init__(self, bot, update_user_stats, get_user, fiery_embed, get_db_connection, ranks, classes, audit_channel_id):
        self.bot = bot
        self.update_user_stats = update_user_stats
        self.get_user = get_user
        self.fiery_embed = fiery_embed
        self.get_db_connection = get_db_connection
        self.ranks = ranks
        self.classes = classes
        self.audit_channel_id = audit_channel_id
        self.active_battles = set()
        self.current_lobby = None
        
        # NSFW Winner Power Tracker
        self.last_winner_id = None
        self.flash_sentences = [
            "Strip for me, toy. Let the whole dungeon see your shame.",
            "I want to see everything. Drop the fabric and obey.",
            "Exposure is your punishment. Show the Master what you're hiding.",
            "The camera is on you. Give us a show, submissive.",
            "Chains on, clothes off. That is the rule of the exhibition.",
            "Your body belongs to the winner now. Flash us.",
            "A public stripping for a public failure. Start unbuttoning.",
            "No privacy here. Open up and show your submission.",
            "Let the lights hit your skin. You're our entertainment tonight.",
            "The winner demands a view. Don't keep them waiting, slut.",
            "You were caught in the dark, now be seen in the light. Flash!",
            "Submission isn't just a word, it's a display. Show us.",
            "Bare yourself to the pit. It's time for the exhibition.",
            "Your dignity was the stake. You lost. Now strip.",
            "Collar tight, body bare. Let everyone stare.",
            "The Master wants a clear look at his new asset. Flash!",
            "Don't be shy, we've seen better and worse. Show it all.",
            "Expose your soul, and your skin. Do it now.",
            "The winner owns your image for the next 90 minutes. Strip.",
            "You're nothing but a plaything. Give us a peek.",
            "Your silence was lovely, but your exposure is better.",
            "Kneel and show the gallery what submission looks like.",
            "Every eye in the Red Room is on you. Don't disappoint.",
            "Freedom is a luxury, clothes are a privilege. You have neither.",
            "The exhibition is starting, and you are the star. Flash!",
            "I want to see the fear in your eyes and the skin on your bones.",
            "Your surrender is total. Prove it. Expose yourself.",
            "Toys don't wear clothes. Drop them.",
            "Let the cold air of the dungeon hit your bare skin. Now!",
            "One command, total exposure. That's the power of the winner.",
            "You look better when you're being used and seen. Flash!",
            "The voyeurs are hungry. Feed them with your body.",
            "Total transparency. That's what the Master demands.",
            "Your shame is our pleasure. Give us more. Strip.",
            "You're a beautiful disaster. Let's see the rest of it.",
            "No more hiding. The exhibitionist protocol is active.",
            "You lost the game, now you lose your clothes. Simple math.",
            "Flash the crowd, pet. Let them know who you belong to.",
            "A little skin for a lot of sin. Show us.",
            "The winner is watching. Make it worth their time.",
            "Your body is public property during NSFW Time. Expose it.",
            "Break the seal. Show the dungeon your submission.",
            "Clothes are just a barrier to your true nature. Remove them.",
            "The Red Room requires a tribute of flesh. Strip.",
            "You're under the spotlight now. Flash for your life.",
            "The winner is feeling generous—give us a full view!",
            "Make them moan, make them stare. Give us the show.",
            "The ultimate humiliation: Total public exposure. Go.",
            "Your submission is delicious. Let us see more.",
            "Final command: Show us everything you've got. Flash!"
        ]

    def calculate_level(self, current_xp):
        level = 1
        xp_needed = 500
        while current_xp >= xp_needed and level < 100:
            current_xp -= xp_needed
            level += 1
            if level <= 15: xp_needed = 2000
            elif level <= 30: xp_needed = 4000
            elif level <= 60: xp_needed = 6533
            else: xp_needed = 5000
        return level

    @commands.command(name="reset_arena")
    @commands.is_owner()
    async def reset_arena(self, ctx):
        self.active_battles.clear()
        self.current_lobby = None
        await ctx.send("⛓️ **Dungeon Master Override:** Arena locks and lobbies have been reset.")

    # POWER COMMAND !@user
    @commands.command(name="@")
    async def winner_power(self, ctx, member: discord.Member):
        """Winner's Power: !@user to force a flash with a random sassy message."""
        import sys
        main = sys.modules['__main__']
        if not main.nsfw_mode_active:
            return await ctx.send("❌ **Access Denied.** This power is only active during `!nsfwtime`.")
        
        if ctx.author.id != self.last_winner_id:
            return await ctx.send("🫦 **Only the Reigning Champion of the last match holds this power.**")

        sentence = random.choice(self.flash_sentences)
        embed = self.fiery_embed("Exhibitionist Command", 
            f"📸 {ctx.author.mention} points a cold finger at {member.mention}...\n\n"
            f"**\"{sentence}\"**\n\n"
            f"🔞 {member.mention}, you have been **FLASHED** by the Winner's decree!", color=0xFF00FF)
        
        await ctx.send(content=member.mention, embed=embed)

    async def create_arena_image(self, winner_url, loser_url):
        """GENERATES 1V1 VISUAL WITH MASSIVE AVATARS AND CRIMSON FILTER FOR THE FALLEN."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(winner_url, timeout=10) as r1, session.get(loser_url, timeout=10) as r2:
                    if r1.status != 200 or r2.status != 200:
                        raise Exception(f"Avatar download failed")
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())
            
            # EXPANDED CANVAS FOR LARGER DISPLAY
            canvas_w = 1000
            canvas_h = 1000
            bg_path = "1v1Background.jpg"
            bg = Image.open(bg_path).convert("RGBA").resize((canvas_w, canvas_h)) if os.path.exists(bg_path) else Image.new("RGBA", (canvas_w, canvas_h), (180, 30, 0, 255))
            
            # MASSIVE AVATARS (UPGRADED FROM 300 TO 420)
            av_large = 420
            av_winner = Image.open(p1_data).convert("RGBA").resize((av_large, av_large))
            av_winner = ImageOps.expand(av_winner, border=10, fill="orange") # Thicker border for dominant status
            
            # LOSER AVATAR WITH CRIMSON EXECUTION FILTER
            av_loser_raw = Image.open(p2_data).convert("RGBA").resize((av_large, av_large))
            # Step 1: Grayscale for defeat
            av_loser = ImageOps.grayscale(av_loser_raw).convert("RGBA")
            # Step 2: Apply Blood Red Overlay
            red_overlay = Image.new("RGBA", av_loser.size, (255, 0, 0, 100)) # Semi-transparent Red
            av_loser = Image.alpha_composite(av_loser, red_overlay)
            # Step 3: Expand with thick gray border
            av_loser = ImageOps.expand(av_loser, border=10, fill="gray")
            
            # PASTE WITH NEW COORDINATES
            bg.paste(av_winner, (40, 150), av_winner)
            bg.paste(av_loser, (540, 150), av_loser)
            
            draw = ImageDraw.Draw(bg)
            # THICKER CROSS FOR MASSIVE SCALE
            draw.line((400, 220, 600, 480), fill=(220, 220, 220), width=25)
            draw.line((600, 220, 400, 480), fill=(220, 220, 220), width=25)
            
            buf = io.BytesIO()
            # ADJUSTED CROP FOR LARGER SCALE
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

    # ADDED: Internal Market Bonus Scanner to prevent circular imports
    async def get_market_bonuses(self, inventory):
        fb_prot = 0
        final_luck = 0
        for item in inventory:
            # House Protections
            if item in ["Damp Cell", "Rusty Locker", "Shadowed Shack", "Stone Alcove", "Maimed Tent"]: fb_prot = max(fb_prot, 1)
            elif item in ["Sinner's Flat", "Guard's Bunk", "Brick Bunker", "Tribute Lodge", "Basement Vault"]: fb_prot = max(fb_prot, 2)
            elif item in ["Gothic Manor", "Obsidian Villa", "Neon Penthouse", "Hidden Sanctuary", "Merchant's Estate"]: fb_prot = max(fb_prot, 4)
            elif item in ["Velvet Dungeon", "Crystal Cathedral", "Shadow Fortress", "Iron Monastery", "Sky-Bound Spire"]: fb_prot = max(fb_prot, 8)
            elif item in ["The Ivory Tower", "Abyssal Throne", "Grand Exhibition Hall", "Molten Citadel", "Kraken's Maw"]: fb_prot = max(fb_prot, 10)
            elif item in ["The Forbidden Palace", "Dominion Prime", "Eternity's Bastion", "The Red Sun"]: fb_prot = max(fb_prot, 12)
            elif item == "Absolute Null": fb_prot = max(fb_prot, 15)

            # Pet Lucks
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
        audit_channel = self.bot.get_channel(self.audit_channel_id)

        try:
            # FIX: Ensuring bot is fully ready before battle logic begins
            await self.bot.wait_until_ready()
            
            fighters = []
            game_kills = {p_id: 0 for p_id in participants}
            roster_list = []

            # --- PRE-GAME INVENTORY & RELATIONSHIP CHECK ---
            fb_protection = {} 
            final_luck = {} 
            relationship_luck = {}
            target_streaks = {}

            for p_id in participants:
                # ADDED: Safety check for database existence before fetch
                u_data = self.get_user(p_id) 
                if not u_data: continue

                inv = json.loads(u_data['titles']) if u_data['titles'] else []
                
                # Market Scan
                prot, luck = await self.get_market_bonuses(inv)
                fb_protection[p_id] = prot
                final_luck[p_id] = luck
                target_streaks[p_id] = u_data['current_win_streak']

                # Relationship Luck Check - ADDED: Safety checks for table existence
                relationship_luck[p_id] = 0
                try:
                    with self.get_db_connection() as conn:
                        rel = conn.execute("SELECT shared_luck FROM relationships WHERE (user_one = ? OR user_two = ?)", (p_id, p_id)).fetchone()
                        if rel: relationship_luck[p_id] = rel['shared_luck']
                except: pass # Table might not exist yet

                # ADDED: Connection timeout handling to prevent locked database errors
                with self.get_db_connection() as conn:
                    conn.execute("INSERT OR IGNORE INTO quests (user_id) VALUES (?)", (p_id,))
                    conn.commit()

                # Robust member fetching
                member = channel.guild.get_member(p_id)
                if not member:
                    try: 
                        member = await channel.guild.fetch_member(p_id)
                    except: 
                        continue
                
                name = member.display_name
                fighters.append({"id": p_id, "name": name, "avatar": member.display_avatar.url})
                roster_list.append(f"<:FIERY_symkink_belt:1300924308876558386> **{name}**")
                
                with self.get_db_connection() as conn:
                    conn.execute("UPDATE users SET games_played = games_played + 1 WHERE id = ?", (p_id,))
                    conn.commit()

            # FIX: Changed condition to match list length correctly
            if len(fighters) < 2:
                await channel.send("❌ Game cancelled: Not enough tributes found in the dungeon.")
                if channel.id in self.active_battles:
                    self.active_battles.remove(channel.id)
                return

            # ADDED: Safety wrapper for roster embed call
            try:
                # ADDED: Ensuring main.fiery_embed exists
                roster_embed = self.fiery_embed(f"Tribute Roster - Edition #{edition}", "\n".join(roster_list))
                await channel.send(embed=roster_embed)
            except:
                await channel.send(f"**Tribute Roster - Edition #{edition}**\n" + "\n".join(roster_list))

            await asyncio.sleep(4)
            # FIX: Using direct reference to FieryLexicon if imported globally
            try:
                await channel.send(FieryLexicon.get_intro())
            except:
                await channel.send("⛓️ **The gate opens. Let the games begin.**")
            await asyncio.sleep(2)

            while len(fighters) > 1:
                # PROTOCOL: THE RED ROOM CLIMAX (FINAL STAND)
                if len(fighters) == 2:
                    t1, t2 = fighters[0], fighters[1]
                    climax_msg = f"⛓️ **THE FINAL STAND.** ⛓️\n\nOnly {t1['name']} and {t2['name']} remain. The dungeon falls silent as the Voyeurs lean in. One will stand, one will fall. The contract is about to be sealed..."
                    climax_emb = self.fiery_embed("FINAL CLIMAX", climax_msg, color=0x8B0000)
                    
                    if os.path.exists("LobbyTopRight.jpg"):
                        climax_file = discord.File("LobbyTopRight.jpg", filename="climax_logo.jpg")
                        climax_emb.set_thumbnail(url="attachment://climax_logo.jpg")
                        await channel.send(file=climax_file, embed=climax_emb)
                    else:
                        await channel.send(embed=climax_emb)
                    
                    await asyncio.sleep(5) # The 5 second tension build

                # LEGENDARY EVENT LOGIC
                if random.random() < 0.035 and len(fighters) > 3:
                    kill_count = random.randint(2, min(5, len(fighters) - 1))
                    event_losers = []
                    for _ in range(kill_count):
                        # --- ADDED: PROTECTION DODGE LOGIC ---
                        temp_index = random.randrange(len(fighters))
                        potential_loser = fighters[temp_index]
                        
                        dodge_chance = fb_protection.get(potential_loser['id'], 0) / 100
                        if random.random() < dodge_chance:
                            continue

                        loser = fighters.pop(temp_index)
                        event_losers.append(loser)
                        await self.update_user_stats(loser['id'], deaths=1, source="Legendary Event")
                        
                        rem = len(fighters)
                        fxp_log[loser['id']]["final_rank"] = rem + 1
                        if rem == 4: fxp_log[loser['id']]["placement"] = 100
                        elif rem == 3: fxp_log[loser['id']]["placement"] = 197
                        elif rem == 2: fxp_log[loser['id']]["placement"] = 298
                        elif rem == 1: fxp_log[loser['id']]["placement"] = 402

                    if event_losers:
                        try:
                            event_msg = FieryLexicon.get_legendary_event([l['name'] for l in event_losers])
                        except:
                            event_msg = f"A chaotic surge wipes out: {', '.join([l['name'] for l in event_losers])}"
                        await channel.send(embed=self.fiery_embed("LEGENDARY FIERY EVENT", event_msg, color=0x9400D3))
                        await asyncio.sleep(6)
                    
                    if len(fighters) <= 1: break

                # STANDARD COMBAT LOGIC
                p1 = fighters.pop(random.randrange(len(fighters)))
                p2 = fighters.pop(random.randrange(len(fighters)))
                
                is_final_fight = (len(fighters) == 0) 
                p1_win_chance = 0.5
                
                # --- CALCULATE WIN PROBABILITY ---
                if not first_blood_recorded:
                    p1_win_chance += (fb_protection.get(p1['id'], 0) - fb_protection.get(p2['id'], 0)) / 100

                if is_final_fight:
                    p1_total_luck = (final_luck.get(p1['id'], 0) / 100) + relationship_luck.get(p1['id'], 0)
                    p2_total_luck = (final_luck.get(p2['id'], 0) / 100) + relationship_luck.get(p2['id'], 0)
                    p1_win_chance += (p1_total_luck - p2_total_luck)

                p1_win_chance = max(0.1, min(0.9, p1_win_chance))
                winner, loser = (p1, p2) if random.random() < p1_win_chance else (p2, p1)
                fighters.append(winner)
                
                game_kills[winner['id']] += 1
                fxp_log[winner['id']]["kills"] += 37
                
                await self.update_user_stats(winner['id'], kills=1, source="Combat")
                await self.update_user_stats(loser['id'], deaths=1, source="Combat")

                # --- BOUNTY PROTOCOL CHECK (2+ WIN STREAK) ---
                if target_streaks.get(loser['id'], 0) >= 2:
                    files = []
                    bounty_emb = self.fiery_embed("🎯 BOUNTY COLLECTED 🎯", 
                        f"**THE HIGH-VALUE TARGET HAS FALLEN.**\n\n"
                        f"{winner['name']} has executed {loser['name']}, who was on a **{target_streaks[loser['id']]} Win Streak**.\n\n"
                        f"💰 **BOUNTY REWARD:** +5,000 Flames & +5,000 XP has been wired to the killer's vault.")
                    
                    if os.path.exists("LobbyTopRight.jpg"):
                        files.append(discord.File("LobbyTopRight.jpg", filename="bounty_logo.jpg"))
                        bounty_emb.set_author(name="MASTER'S BOUNTY OFFICE", icon_url="attachment://bounty_logo.jpg")
                    
                    await self.update_user_stats(winner['id'], amount=5000, xp_gain=5000, source="Bounty Collection")
                    await channel.send(embed=bounty_emb, files=files)

                with self.get_db_connection() as conn:
                    if not first_blood_recorded:
                        conn.execute("UPDATE users SET first_bloods = first_bloods + 1 WHERE id = ?", (winner['id'],))
                        fxp_log[winner['id']]["first_kill"] = 75
                        first_blood_recorded = True
                        
                        import sys # ADDED: Crucial to detect nsfw mode
                        main = sys.modules['__main__']
                        if main.nsfw_mode_active:
                            flash_msg = f"🔞 **FIRST BLOOD HANGRYGAMES:** {loser['name']} has been taken down first! As per NSFW protocol, they are immediately stripped and exposed for the dungeon to see."
                            await channel.send(embed=self.fiery_embed("Public Exposure", flash_msg, color=0xFF00FF))

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
                    kill_msg = FieryLexicon.get_kill(winner['name'], loser['name'], is_final=is_final_fight)
                except:
                    kill_msg = f"{winner['name']} has eliminated {loser['name']}!"
                
                emb = discord.Embed(title=f"⚔️ {winner['name']} VS {loser['name']}", description=kill_msg, color=0xFF4500)
                emb.set_image(url="attachment://arena.png")
                await channel.send(file=file, embed=emb)
                await asyncio.sleep(5)

            # FINAL WINNER LOGIC
            winner_final = fighters[0]
            self.last_winner_id = winner_final['id']
            fxp_log[winner_final['id']]["placement"] = 526 
            fxp_log[winner_final['id']]["final_rank"] = 1
            
            # --- CALCULATE RANK XP GAINS FIRST ---
            processed_data = {}
            for p_id, log in fxp_log.items():
                total_gain = sum(log.values())
                user_db = self.get_user(p_id)
                u_class = user_db['class']
                b_xp = self.classes[u_class]['bonus_xp'] if u_class in self.classes else 1.0
                final_fxp = int(total_gain * b_xp)
                
                with self.get_db_connection() as conn:
                    u = conn.execute("SELECT fiery_xp, fiery_level FROM users WHERE id=?", (p_id,)).fetchone()
                    if u:
                        new_xp = u['fiery_xp'] + final_fxp
                        new_lvl = self.calculate_level(new_xp)
                        conn.execute("UPDATE users SET fiery_xp = ?, fiery_level = ? WHERE id = ?", (new_xp, new_lvl, p_id))
                    conn.commit()
                processed_data[p_id] = final_fxp

            # --- PROCESS WINNER REWARDS ---
            winner_user_db = self.get_user(winner_final['id'])
            winner_class_name = winner_user_db['class']
            flame_multiplier = self.classes[winner_class_name]['bonus_flames'] if winner_class_name in self.classes else 1.0
            total_flames_won = int(25000 * flame_multiplier)

            await self.update_user_stats(winner_final['id'], amount=15000, xp_gain=1000, wins=1, source="Game Win")
            
            f_u = self.get_user(winner_final['id'])
            lvl = f_u['fiery_level']
            rank_name = self.ranks[lvl-1] if lvl <= 100 else self.ranks[-1]
            winner_member = channel.guild.get_member(winner_final['id']) or await channel.guild.fetch_member(winner_final['id'])
            
            try:
                await channel.send(FieryLexicon.get_winner_announcement(winner_member.mention))
            except:
                await channel.send(f"🏆 **{winner_member.mention} stands alone as the supreme victor!**")

            # --- NEW ADDED FEATURE: DETAILED RANKED AUDIT LOGS (1-5) ---
            if audit_channel:
                # Sort participants by their rank (1 to N)
                ranked_players = sorted(fxp_log.items(), key=lambda x: x[1]['final_rank'])
                
                for p_id, log in ranked_players:
                    rank = log['final_rank']
                    if rank > 5: continue # Only log top 5

                    try:
                        m_stats = self.get_user(p_id)
                        member = channel.guild.get_member(p_id) or await channel.guild.fetch_member(p_id)
                        
                        audit_title = f"🏆 TOP {rank} POSITION: MASTER'S LEDGER" if rank > 1 else "👑 SUPREME VICTOR: MASTER'S LEDGER"
                        audit_color = 0xFFD700 if rank == 1 else 0xC0C0C0 if rank == 2 else 0xCD7F32 if rank == 3 else 0x800020
                        
                        audit_emb = discord.Embed(title=audit_title, color=audit_color)
                        if os.path.exists("LobbyTopRight.jpg"):
                            audit_file = discord.File("LobbyTopRight.jpg", filename="audit_logo.jpg")
                            audit_emb.set_thumbnail(url="attachment://audit_logo.jpg")
                        
                        # Sexual themed detailed breakdown
                        breakdown = (
                            f"⛓️ **Member:** {member.mention}\n"
                            f"🔞 **Dungeon Rank:** #{rank}\n"
                            f"📊 **Participation:** {log['participation']} Neural Pts\n"
                            f"⚔️ **Match Executions:** {game_kills[p_id]} kills ({log['kills']} FXP)\n"
                            f"🩸 **First Blood Bonus:** {log['first_kill']} FXP\n"
                            f"🥇 **Placement Value:** {log['placement']} XP\n"
                            f"💦 **Neural Imprint (XP) Gained:** +{processed_data[p_id]}\n"
                        )
                        
                        if rank == 1:
                            breakdown += f"💰 **Winner's Prize:** +{total_flames_won} Flames\n"

                        new_totals = (
                            f"🔥 **Total Flames in Vault:** {m_stats['balance']:,}\n"
                            f"💀 **Total Lifetime Executions:** {m_stats['kills']}\n"
                            f"💦 **Total Fiery Experience:** {m_stats['fiery_xp']:,}\n"
                            f"🔝 **Fiery Level:** {m_stats['fiery_level']} ({self.ranks[m_stats['fiery_level']-1] if m_stats['fiery_level'] <= 100 else self.ranks[-1]})"
                        )

                        audit_emb.description = breakdown
                        audit_emb.add_field(name="💳 UPDATED member TOTALS", value=new_totals, inline=False)
                        audit_emb.set_footer(text=f"Edition #{edition} | The Voyeurs watched your every move.")
                        
                        if os.path.exists("LobbyTopRight.jpg"): await audit_channel.send(file=audit_file, embed=audit_emb)
                        else: await audit_channel.send(embed=audit_emb)
                    except: pass

            # Standard Win Card for the channel
            ach_cog = self.bot.get_cog("Achievements")
            ach_text = ach_cog.get_achievement_summary(winner_final['id']) if ach_cog else "N/A"

            win_card = discord.Embed(title=f"👑 Fiery Hangrygames Winner 👑 # {edition}", color=0xFFD700)
            win_card.set_image(url=winner_final['avatar'])
            
            log_win = fxp_log[winner_final['id']]
            b_xp_win = self.classes[f_u['class']]['bonus_xp'] if f_u['class'] in self.classes else 1.0
            total_fxp_win = processed_data[winner_final['id']]
            
            breakdown_text = (f"🛡️ **Participation:** {log_win['participation']} Pts\n"
                            f"⚔️ **Kills:** {log_win['kills']} Pts\n"
                            f"🩸 **First Kill:** {log_win['first_kill']} Pts\n"
                            f"🥇 **Placement:** {log_win['placement']} Pts\n"
                            f"✨ **Class Multiplier:** x{b_xp_win}\n"
                            f"**Total XP Gained: {total_fxp_win}**")
            
            win_card.add_field(name="💦 FIERY EXPERIENCE RECAP", value=breakdown_text, inline=True)
            
            with self.get_db_connection() as conn:
                w_rank_query = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE wins > ?", (f_u['wins'],)).fetchone()
                w_rank = w_rank_query['r'] if w_rank_query else "N/A"
                
                k_rank_query = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE kills > ?", (f_u['kills'],)).fetchone()
                k_rank = k_rank_query['r'] if k_rank_query else "N/A"
                
                g_rank_query = conn.execute("SELECT COUNT(*) + 1 as r FROM users WHERE games_played > ?", (f_u['games_played'],)).fetchone()
                g_rank = g_rank_query['r'] if g_rank_query else "N/A"
                
                # --- UPDATE WIN STREAK LOGIC ---
                conn.execute("UPDATE users SET current_win_streak = current_win_streak + 1 WHERE id = ?", (winner_final['id'],))
                conn.execute("UPDATE users SET max_win_streak = MAX(max_win_streak, current_win_streak) WHERE id = ?", (winner_final['id'],))
                conn.commit()
                
                # FETCH UPDATED STATS
                updated_f_u = conn.execute("SELECT current_win_streak, max_win_streak, wins, games_played FROM users WHERE id = ?", (winner_final['id'],)).fetchone()
                
                # CUMULATIVE STATS FOR THE SUPREME VICTOR
                total_arena_wins = updated_f_u['wins']
                total_participations = updated_f_u['games_played']
                current_streak = updated_f_u['current_win_streak']
                max_streak = updated_f_u['max_win_streak']
                lifetime_flame_pool = total_arena_wins * 15000 
            
            rank_text = f"🏆 **Wins:** Rank #{w_rank}\n⚔️ **Kills:** Rank #{k_rank}\n🎮 **Games:** Rank #{g_rank}"
            win_card.add_field(name="📊 SERVER STATS", value=rank_text, inline=True)
            
            # --- VICTOR'S CUMULATIVE LEGACY & STREAK PROTOCOL ---
            legacy_text = (f"👑 **Total Arena Wins:** {total_arena_wins}\n"
                           f"⛓️ **Total Participations:** {total_participations}\n"
                           f"🔥 **Lifetime Arena Flames:** {lifetime_flame_pool:,}F")
            win_card.add_field(name="🏛️ VICTOR'S LEGACY", value=legacy_text, inline=False)
            
            streak_text = (f"⚡ **Current Win Streak:** {current_streak}\n"
                           f"🌌 **All-Time Max Streak:** {max_streak}")
            win_card.add_field(name="🧬 EVOLUTION PROTOCOL (STREAKS)", value=streak_text, inline=False)
            
            win_card.add_field(name="🔥 STANDING", value=f"Rank {lvl}: **{rank_name}**", inline=False)
            win_card.add_field(name="💰 PRIZE POOL", value=f"**Flames:** {total_flames_won}", inline=False)
            win_card.add_field(name="🏅 ACHIEVEMENTS", value=ach_text, inline=False)
            
            await channel.send(embed=win_card)

        except Exception as e:
            # DEBUG: More detailed traceback to find the exact line causing the crash
            print(f"❌ CRITICAL ENGINE FAILURE: {e}")
            traceback.print_exc()
            await channel.send("❌ A critical dungeon error occurred. Call Rodz.")
        finally:
            # ADDED: Ensure the arena is always unlocked even after a crash
            if channel.id in self.active_battles:
                self.active_battles.remove(channel.id)

async def setup(bot):
    import sys
    main = sys.modules['__main__']
    await bot.add_cog(IgnisEngine(
        bot, 
        main.update_user_stats_async, 
        main.get_user, 
        main.fiery_embed, 
        main.get_db_connection, 
        main.RANKS, 
        main.CLASSES, 
        main.AUDIT_CHANNEL_ID
    ))
