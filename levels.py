import discord
from discord.ext import commands
import sys
import os
import json
import random
import asyncio

class RankTopView(discord.ui.View):
    def __init__(self, ctx, data, main_mod):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.data = data
        self.main_mod = main_mod
        self.page = 0
        self.per_page = 20

    def create_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        current_page_data = self.data[start:end]
        
        desc = "### 🏆 NEURAL TEXTING LEADERBOARD\n"
        desc += "*The most active frequencies in the Red Room.*\n\n"
        
        for i, row in enumerate(current_page_data, start=start+1):
            user_id, lvl, xp = row
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"`#{i}`"
            desc += f"{medal} <@{user_id}> — **Level {lvl}** (*{xp:,} XP*)\n"
            
        total_pages = (len(self.data) - 1) // self.per_page + 1
        embed = self.main_mod.fiery_embed("GLOBAL RANKINGS", desc)
        embed.set_footer(text=f"Page {self.page + 1} of {total_pages} | Total Assets: {len(self.data)}")
        return embed

    @discord.ui.button(label="PREVIOUS", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Only the initiator can navigate.", ephemeral=True)
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="NEXT", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Only the initiator can navigate.", ephemeral=True)
        if (self.page + 1) * self.per_page < len(self.data):
            self.page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

class TextLevelSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Local cache for the Level-Up announcement channel
        self.level_channel_id = None
        # Local cache for level-to-role mappings
        self.level_roles = {}
        self.load_config()
        # Cooldown to prevent spamming (1 message per 10 seconds counts for XP)
        self._cooldown = commands.CooldownMapping.from_cooldown(1, 10, commands.BucketType.user)

    def load_config(self):
        """Load level-up channel ID and roles from the database config."""
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                # Load Level Channel
                row = conn.execute("SELECT value FROM config WHERE key = 'level_up_channel'").fetchone()
                if row: self.level_channel_id = int(row['value'])
                
                # Load Level Roles
                role_row = conn.execute("SELECT value FROM config WHERE key = 'level_roles'").fetchone()
                if role_row: self.level_roles = json.loads(role_row['value'])
        except: pass

    def save_config(self):
        """Save level-up channel ID and roles."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         ('level_up_channel', str(self.level_channel_id)))
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", 
                         ('level_roles', json.dumps(self.level_roles)))
            conn.commit()

    def get_xp_needed(self, level):
        """Formula: Level 1 needs 100 XP, increasing by 50 per level."""
        return 100 + (level * 50)

    async def check_achievement(self, user, current_count, previous_count, category):
        """Logic for 500-step milestones up to 500,000 with Profile Data."""
        if current_count > previous_count and current_count % 500 == 0 and current_count <= 500000:
            main_mod = sys.modules['__main__']
            channel = self.bot.get_channel(self.level_channel_id) if self.level_channel_id else None
            
            # PULLING DATA FROM main.py get_user
            u_data = await asyncio.to_thread(main_mod.get_user, user.id)
            
            title = "📜 NEURAL CERTIFICATE OF RECOGNITION"
            desc = (f"### 🎖️ MILESTONE ACHIEVED: {category.upper()}\n"
                    f"Asset {user.mention}, your consistency has been noted by the Echo.\n\n"
                    f"**Total {category}:** `{current_count:,}`\n"
                    f"**Status:** `Verified & Archived`\n\n")
            
            desc += "⚙️ **SUBSYSTEM SNAPSHOT:**\n"
            desc += f"└─ `Neural Level:` **{u_data['fiery_level']}**\n"
            desc += f"└─ `Total XP:` **{u_data['xp']:,}**\n"
            desc += f"└─ `Capital:` **{u_data['balance']:,} Flames**\n"
            desc += f"└─ `Current Class:` **{u_data['class']}**\n"
            desc += f"└─ `Premium Tier:` **{u_data['premium_type'] or 'Standard'}**\n\n"
            desc += f"*The Red Room appreciates your high-frequency interaction.*"
            
            embed = main_mod.fiery_embed(title, desc, color=0xFFD700)
            if os.path.exists("LobbyTopRight.jpg"):
                file = discord.File("LobbyTopRight.jpg", filename="cert.jpg")
                embed.set_thumbnail(url="attachment://cert.jpg")
                if channel: await channel.send(content=user.mention, file=file, embed=embed)
            else:
                if channel: await channel.send(content=user.mention, embed=embed)

    @commands.command(name="setlevelchannel")
    @commands.has_permissions(administrator=True)
    async def set_level_channel(self, ctx, channel: discord.TextChannel = None):
        """Sets the channel where Level Up messages are recorded."""
        target = channel or ctx.channel
        self.level_channel_id = target.id
        self.save_config()
        
        main_mod = sys.modules['__main__']
        embed = main_mod.fiery_embed("📈 LEVEL PROTOCOL UPDATED", 
                                    f"The Master will now record all textual ascensions in {target.mention}.")
        await ctx.send(embed=embed)

    @commands.command(name="setlevelrole")
    @commands.has_permissions(administrator=True)
    async def set_level_role(self, ctx, level: int, role: discord.Role):
        """Maps a specific level to a Discord role."""
        self.level_roles[str(level)] = role.id
        self.save_config()
        
        main_mod = sys.modules['__main__']
        embed = main_mod.fiery_embed("🛡️ ROLE PROTOCOL SEALED", 
                                    f"Neural Level **{level}** is now bound to the role: {role.mention}.")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Track reactions for achievements."""
        if payload.member and payload.member.bot: return
        main_mod = sys.modules['__main__']
        
        def update_reaction_data():
            with main_mod.get_db_connection() as conn:
                try: conn.execute("ALTER TABLE users ADD COLUMN total_reactions INTEGER DEFAULT 0")
                except: pass
                
                user = conn.execute("SELECT total_reactions FROM users WHERE id = ?", (payload.user_id,)).fetchone()
                prev = user['total_reactions'] if user else 0
                curr = prev + 1
                conn.execute("UPDATE users SET total_reactions = ? WHERE id = ?", (curr, payload.user_id))
                conn.commit()
                return curr, prev

        curr, prev = await asyncio.to_thread(update_reaction_data)
        
        # Determine the user object for the achievement ping
        guild = self.bot.get_guild(payload.guild_id)
        if guild:
            member = payload.member or guild.get_member(payload.user_id)
            if member:
                await self.check_achievement(member, curr, prev, "Reactions Given")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        main_mod = sys.modules['__main__']
        user_id = message.author.id

        # --- ACHIEVEMENT TRACKING (Messages) ---
        def update_msg_count():
            with main_mod.get_db_connection() as conn:
                try: conn.execute("ALTER TABLE users ADD COLUMN total_messages INTEGER DEFAULT 0")
                except: pass
                user = conn.execute("SELECT total_messages FROM users WHERE id = ?", (user_id,)).fetchone()
                prev = user['total_messages'] if user else 0
                curr = prev + 1
                conn.execute("UPDATE users SET total_messages = ? WHERE id = ?", (curr, user_id))
                conn.commit()
                return curr, prev
        
        curr_msg, prev_msg = await asyncio.to_thread(update_msg_count)
        await self.check_achievement(message.author, curr_msg, prev_msg, "Messages Sent")

        # Cooldown check for XP (Independent from Achievement counter)
        bucket = self._cooldown.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return

        xp_gain = random.randint(15, 25) # Random XP per message

        def update_level_data():
            with main_mod.get_db_connection() as conn:
                # Ensure columns exist
                try: conn.execute("ALTER TABLE users ADD COLUMN text_xp INTEGER DEFAULT 0")
                except: pass
                try: conn.execute("ALTER TABLE users ADD COLUMN text_level INTEGER DEFAULT 0")
                except: pass

                user = conn.execute("SELECT text_xp, text_level FROM users WHERE id = ?", (user_id,)).fetchone()
                if not user: return None, None, False

                current_xp = user['text_xp'] + xp_gain
                current_lvl = user['text_level']
                xp_needed = self.get_xp_needed(current_lvl)

                leveled_up = False
                if current_xp >= xp_needed:
                    current_xp -= xp_needed
                    current_lvl += 1
                    leveled_up = True

                conn.execute("UPDATE users SET text_xp = ?, text_level = ? WHERE id = ?", 
                             (current_xp, current_lvl, user_id))
                conn.commit()
                return current_lvl, current_xp, leveled_up

        new_lvl, new_xp, did_level_up = await asyncio.to_thread(update_level_data)

        if did_level_up:
            # Handle Auto-Role logic
            if str(new_lvl) in self.level_roles:
                role_id = self.level_roles[str(new_lvl)]
                role = message.guild.get_role(role_id)
                if role:
                    try: await message.author.add_roles(role, reason=f"Neural Level {new_lvl} reached.")
                    except: pass

            if self.level_channel_id:
                lvl_channel = self.bot.get_channel(self.level_channel_id)
                if lvl_channel:
                    embed = main_mod.fiery_embed("✨ NEURAL ASCENSION", 
                        f"Congratulations {message.author.mention}.\n\n"
                        f"Your constant frequency has pushed you to **Level {new_lvl}**.\n"
                        f"The Red Room acknowledges your growth.", color=0x00FFFF)
                    
                    if os.path.exists("LobbyTopRight.jpg"):
                        file = discord.File("LobbyTopRight.jpg", filename="level.jpg")
                        embed.set_thumbnail(url="attachment://level.jpg")
                        await lvl_channel.send(file=file, embed=embed)
                    else:
                        await lvl_channel.send(embed=embed)

    @commands.command(name="rank")
    async def text_rank(self, ctx, member: discord.Member = None):
        """Check your texting level and progress."""
        target = member or ctx.author
        main_mod = sys.modules['__main__']
        user = main_mod.get_user(target.id)
        
        lvl = user.get('text_level', 0)
        xp = user.get('text_xp', 0)
        needed = self.get_xp_needed(lvl)
        
        # Progress bar
        bar_len = 10
        filled = int((xp / max(1, needed)) * bar_len)
        bar = "🟦" * filled + "⬛" * (bar_len - filled)

        embed = main_mod.fiery_embed(f"📊 {target.display_name}'S RANK", 
                                    f"**Text Level:** {lvl}\n"
                                    f"**XP:** {xp:,} / {needed:,}\n"
                                    f"**Progress:** [{bar}]")
        
        await ctx.send(embed=embed)

    @commands.command(name="ranktop")
    async def ranktop(self, ctx):
        """Displays the top texting levels with pagination."""
        main_mod = sys.modules['__main__']
        
        def fetch_top():
            with main_mod.get_db_connection() as conn:
                return conn.execute("SELECT id, text_level, text_xp FROM users WHERE text_level > 0 OR text_xp > 0 ORDER BY text_level DESC, text_xp DESC").fetchall()

        data = await asyncio.to_thread(fetch_top)
        if not data:
            return await ctx.send("The ledger is empty. No frequencies detected yet.")

        view = RankTopView(ctx, data, main_mod)
        await ctx.send(embed=view.create_embed(), view=view)

async def setup(bot):
    await bot.add_cog(TextLevelSystem(bot))
