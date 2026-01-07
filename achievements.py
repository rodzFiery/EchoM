import discord
from discord.ext import commands
import sys
import os

class Achievements(commands.Cog):
    def __init__(self, bot, get_db_connection, fiery_embed):
        self.bot = bot
        self.get_db_connection = get_db_connection
        self.fiery_embed = fiery_embed
        # FIXED: Explicitly defined for the audit log integration
        self.AUDIT_CHANNEL_ID = 1438810509322223677

    def generate_fiery_scale(self):
        """ADDED: Generates the specialized Master's Scale for all achievements."""
        scale = []
        # Phase 1: 50 in 50 until 2000
        scale.extend(range(50, 2001, 50))
        # Phase 2: 100 in 100 until 3000
        scale.extend(range(2100, 3001, 100))
        # Phase 3: 250 in 250 until 5000
        scale.extend(range(3250, 5001, 250))
        # Phase 4: 500 in 500 until 10000
        scale.extend(range(5500, 10001, 500))
        return scale

    def get_tier(self, value, tiers):
        # ADDED: Safety check to treat None as 0
        val = value if value is not None else 0
        reached = [t for t in tiers if val >= t]
        return max(reached) if reached else 0

    def get_achievement_summary(self, user_id):
        """Generates a high-quality summary of highest reached tiers for the winner card."""
        # FIX: Using local connection context to prevent interference with other database tasks
        with self.get_db_connection() as conn:
            u = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        
        if not u: 
            return "First Steps..."

        # Define high-tier milestone sets
        # UPDATED: Now using the universal Fiery Scale for all primary milestones
        t_master_scale = self.generate_fiery_scale()
        t_high = t_master_scale + [15000]
        t_streaks = list(range(2, 21))

        lines = []
        
        # 1. First Blood Milestone (Killer)
        # ADDED: dict access safety (u['key'] or 0)
        fb = self.get_tier(u['first_bloods'] if 'first_bloods' in u.keys() else 0, t_master_scale)
        if fb: lines.append(f"🩸 First Blood pro: {fb}")
        
        # 2. Total Wins Milestone
        wins = self.get_tier(u['wins'] if 'wins' in u.keys() else 0, t_master_scale)
        if wins: lines.append(f"🏆 Wins: {wins}")
        
        # 3. Total Kills Milestone
        kills = self.get_tier(u['kills'] if 'kills' in u.keys() else 0, t_high)
        if kills: lines.append(f"⚔️ Kills: {kills}")
        
        # 4. Max Win Streak Milestone
        streak = self.get_tier(u['max_win_streak'] if 'max_win_streak' in u.keys() else 0, t_streaks)
        if streak: lines.append(f"🔥 Streak: {streak}x")
        
        # 5. Max Kill Streak Milestone (Killing Spree)
        ks = self.get_tier(u['max_kill_streak'] if 'max_kill_streak' in u.keys() else 0, t_streaks)
        if ks: lines.append(f"💀 Kill Spree: {ks}x")

        # 6. ADDED: First Blood (Death) Milestone
        fbd = self.get_tier(u['first_deaths'] if 'first_deaths' in u.keys() else 0, t_master_scale)
        if fbd: lines.append(f"⚰️ Victim Soul: {fbd}")

        return "\n".join(lines) if lines else "First Steps..."

    # --- NEW FEATURE: REAL-TIME AUDIT LOGGING ---
    async def check_and_log_achievements(self, user_id, category, current_value):
        """ADDED: Checks if the current value exactly matches a milestone tier and logs it to audit."""
        # Full Milestone Definitions (Mirrored from view command)
        t_master_scale = self.generate_fiery_scale()
        t_high = t_master_scale + [15000]
        # UPDATED: Killing Spree check for anything 3 or above
        t_streaks = list(range(3, 21))
        
        # Map categories to their respective tier lists
        tier_map = {
            "First Bloods": t_master_scale,
            "Total Wins": t_master_scale,
            "Total Kills": t_high,
            "Games Played": t_master_scale,
            "Win Streak": t_streaks,
            "Kill Streak": t_streaks,
            "Finalist (Top 2-5)": t_high,
            "First Deaths": t_master_scale
        }
        
        if category in tier_map and current_value in tier_map[category]:
            main_module = sys.modules['__main__']
            # ADDED: Direct ID fetch for the requested audit log
            audit_channel = self.bot.get_channel(self.AUDIT_CHANNEL_ID)
            
            if audit_channel:
                user = await self.bot.fetch_user(user_id)
                
                # Dynamic wording based on category
                if category == "Kill Streak":
                    special_note = "A killing spree has ignited. The blood is practically boiling."
                elif category == "First Deaths":
                    special_note = "An asset has been sacrificed first too many times. A true glutton for punishment."
                else:
                    special_note = "The Master has noted your growing submission to the arena."

                embed = self.fiery_embed("📜 MASTER'S LEDGER: MILESTONE REACHED", 
                    f"🫦 {user.mention} has deepened their descent. A new seal has been broken in the Achievement Room.\n\n"
                    f"🏅 **Achievement Category:** {category}\n"
                    f"📈 **Milestone Reached:** Level {current_value}\n"
                    f"⛓️ **Status:** Permanent Record Updated\n\n"
                    f"*'{special_note}'*", color=0xFFD700)
                
                if os.path.exists("LobbyTopRight.jpg"):
                    file = discord.File("LobbyTopRight.jpg", filename="milestone.jpg")
                    embed.set_thumbnail(url="attachment://milestone.jpg")
                    await audit_channel.send(content=f"👑 **Achievement Protocol Activated:** {user.mention}", file=file, embed=embed)
                else:
                    await audit_channel.send(content=f"👑 **Achievement Protocol Activated:** {user.mention}", embed=embed)

    @commands.command(name="achievements")
    async def view_achievements(self, ctx, member: discord.Member = None):
        """Displays a full breakdown of the user's achievements across all categories."""
        member = member or ctx.author
        with self.get_db_connection() as conn:
            u = conn.execute("SELECT * FROM users WHERE id = ?", (member.id,)).fetchone()
        
        if not u: 
            return await ctx.send("No records found for this tribute.")

        # Full Milestone Definitions
        t_master_scale = self.generate_fiery_scale()
        t_high = t_master_scale + [15000]
        t_streaks = list(range(2, 21))

        ach_msg = []
        
        # 1. First Blood Tracking (Killer)
        fb = self.get_tier(u['first_bloods'] if 'first_bloods' in u.keys() else 0, t_master_scale)
        if fb: ach_msg.append(f"🩸 **First Bloods (Killer):** {fb}")
        
        # 2. Participation Tracking
        gp = self.get_tier(u['games_played'] if 'games_played' in u.keys() else 0, t_master_scale)
        if gp: ach_msg.append(f"🎮 **Participations:** {gp}")
        
        # 3. Win Tracking
        wins = self.get_tier(u['wins'] if 'wins' in u.keys() else 0, t_master_scale)
        if wins: ach_msg.append(f"🏆 **Total Wins:** {wins}")
        
        # 4. Kill Tracking
        kills = self.get_tier(u['kills'] if 'kills' in u.keys() else 0, t_high)
        if kills: ach_msg.append(f"⚔️ **Total Kills:** {kills}")
        
        # 5. First Blood (Death) Tracking
        fbd = self.get_tier(u['first_deaths'] if 'first_deaths' in u.keys() else 0, t_master_scale)
        if fbd: ach_msg.append(f"⚰️ **First Blood (Victim):** {fbd}")
        
        # 6. Straight Kills Achievement (Killing Spree)
        ks = self.get_tier(u['max_kill_streak'] if 'max_kill_streak' in u.keys() else 0, t_streaks)
        if ks >= 3: ach_msg.append(f"💀 **Killing Spree (Straight Kills):** {ks}x")
        
        # Placement Tracking (Top 2-5)
        top_total = (u['top_2'] or 0) + (u['top_3'] or 0) + (u['top_4'] or 0) + (u['top_5'] or 0)
        top = self.get_tier(top_total, t_high)
        if top: ach_msg.append(f"🥈 **Finalist (Top 2-5):** {top}")

        embed = self.fiery_embed(f"{member.name}'s Achievement Room", 
                                  "\n".join(ach_msg) if ach_msg else "No milestones reached yet. The arena awaits.")
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    main_module = sys.modules['__main__']
    await bot.add_cog(Achievements(bot, main_module.get_db_connection, main_module.fiery_embed))

