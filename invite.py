import discord
from discord.ext import commands
from datetime import datetime, timezone
import sys

class InviteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # This will cache all invites for all servers: {guild_id: {invite_code: uses}}
        self.invites = {}
        # --- 2030 UPGRADE: Cross-session memory to track who invited a user when they leave ---
        self.invited_by = {}

    async def get_log_channel(self, guild_id):
        """Fetches the designated invite log channel from your existing database."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            # Ensure the config table exists just in case
            conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
            row = conn.execute("SELECT value FROM config WHERE key = ?", (f"invite_log_{guild_id}",)).fetchone()
            if row:
                return self.bot.get_channel(int(row['value']))
        return None

    @commands.command(name="setinvite")
    @commands.has_permissions(administrator=True)
    async def setinvite(self, ctx, channel: discord.TextChannel):
        """Admin command to set where the invite logs should be sent."""
        main_mod = sys.modules['__main__']
        with main_mod.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (f"invite_log_{ctx.guild.id}", str(channel.id)))
            conn.commit()
        
        try:
            embed = main_mod.fiery_embed("Log Channel Updated", f"✅ Invite logs will now be sent to {channel.mention}", color=0x00FF00)
            # --- 2030 UPGRADE: Dynamic Footers for Admin Logs ---
            embed.set_footer(text=f"Configuration locked by {ctx.author.name} • Master Protocol Active")
            await ctx.send(embed=embed)
        except Exception:
            await ctx.send(f"✅ Invite logs will now be sent to {channel.mention}")

    @commands.Cog.listener()
    async def on_ready(self):
        """When the bot wakes up, cache all current invites for all servers."""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                invs = await guild.invites()
                self.invites[guild.id] = {invite.code: invite.uses for invite in invs}
            except discord.Forbidden:
                # Bot doesn't have "Manage Server" permissions in this guild to view invites
                pass

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """Update cache when a new invite is created."""
        if invite.guild.id not in self.invites:
            self.invites[invite.guild.id] = {}
        self.invites[invite.guild.id][invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        """Update cache when an invite is deleted."""
        if invite.guild.id in self.invites and invite.code in self.invites[invite.guild.id]:
            del self.invites[invite.guild.id][invite.code]

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Triggered when a member joins. Calculates age and finds the inviter."""
        guild = member.guild
        log_channel = await self.get_log_channel(guild.id)
        
        if not log_channel:
            return # Logging channel hasn't been set up yet for this server

        inviter = None
        total_invites = 0
        
        try:
            current_invites = await guild.invites()
            cached_invites = self.invites.get(guild.id, {})

            # Compare cached invites vs current invites to find which one was just used
            for invite in current_invites:
                old_uses = cached_invites.get(invite.code, 0)
                if invite.uses > old_uses:
                    inviter = invite.inviter
                    break

            # Rebuild the cache with the new values and calculate total invites for the inviter
            self.invites[guild.id] = {}
            for invite in current_invites:
                self.invites[guild.id][invite.code] = invite.uses
                # Tally up all uses across all active links owned by this inviter
                if inviter and invite.inviter and invite.inviter.id == inviter.id:
                    total_invites += invite.uses

        except discord.Forbidden:
            pass

        # Calculate Account Age
        now = datetime.now(timezone.utc)
        created = member.created_at
        diff = now - created
        days = diff.days
        months = days // 30
        rem_days = days % 30
        
        if months > 0:
            age_str = f"{months} months, {rem_days} days"
        else:
            age_str = f"{days} days"

        # --- 2030 UPGRADE: Enhanced Security & Timestamp Calculations ---
        created_ts = int(created.timestamp())
        member_count = len(guild.members)
        is_bot = "🤖 Bot Account" if member.bot else "👤 Human User"
        
        security_flag = ""
        if days < 3:
            security_flag = "\n🚨 **SECURITY ALERT:** Ultra-new account detected. Monitor closely."

        # Build the Embed
        embed = discord.Embed(color=0x2b2d31)
        embed.set_author(name="Member Joined", icon_url=member.display_avatar.url)
        embed.description = f"{member.mention} {member.name}\n\n**Account Age**\n{age_str}\n\n**ID:** {member.id}"
        embed.set_thumbnail(url=member.display_avatar.url)

        # --- 2030 UPGRADE: Appending Next-Gen Data payload ---
        embed.description += f"\n\n**Creation Date:** <t:{created_ts}:F> (<t:{created_ts}:R>)"
        embed.description += f"\n**Join Sequence:** Member #{member_count:,}"
        embed.description += f"\n**Classification:** {is_bot}"
        embed.description += security_flag
        embed.timestamp = now

        if inviter:
            footer_text = f"{member.name} just joined. They were invited by {inviter.name} who now has {total_invites} invites!"
            # --- 2030 UPGRADE: Save to memory for departure tracking ---
            if guild.id not in self.invited_by:
                self.invited_by[guild.id] = {}
            self.invited_by[guild.id][member.id] = inviter.name
        else:
            footer_text = f"{member.name} just joined. I couldn't track the invite (Vanity URL or temporary code)."
            
        embed.set_footer(text=footer_text)

        # --- 2030 UPGRADE: Appending Inviter Avatar to Footer if possible ---
        if inviter:
            embed.set_footer(text=footer_text, icon_url=inviter.display_avatar.url)

        await log_channel.send(embed=embed)

    # --- 2030 UPGRADE: Departure Tracker (New Protocol) ---
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """2030 UPGRADE: Tracks when members leave and exposes their inviter."""
        guild = member.guild
        log_channel = await self.get_log_channel(guild.id)
        
        if not log_channel:
            return

        now = datetime.now(timezone.utc)
        leave_ts = int(now.timestamp())
        
        stay_duration = "Unknown"
        if member.joined_at:
            stay_diff = now - member.joined_at
            stay_duration = f"{stay_diff.days} days, {stay_diff.seconds // 3600} hours"
            
        inviter_name = "Unknown / Vanity"
        if guild.id in self.invited_by and member.id in self.invited_by[guild.id]:
            inviter_name = self.invited_by[guild.id][member.id]
            del self.invited_by[guild.id][member.id] # Clean up memory

        embed = discord.Embed(color=0xED4245) # Deep red to signify departure
        embed.set_author(name="Member Left", icon_url=member.display_avatar.url)
        embed.description = f"{member.mention} {member.name}\n\n**Stay Duration:**\n{stay_duration}\n\n**ID:** {member.id}"
        embed.description += f"\n\n**Departure Time:** <t:{leave_ts}:F> (<t:{leave_ts}:R>)"
        embed.description += f"\n**Originally Invited By:** {inviter_name}"
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"{member.name} has abandoned the server.")
        embed.timestamp = now

        await log_channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(InviteTracker(bot))
    print("✅ LOG: Invite Tracker System [2030 Edition] is ONLINE.")
