import discord
from discord.ext import commands
from datetime import datetime, timezone
import sys

class InviteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # This will cache all invites for all servers: {guild_id: {invite_code: uses}}
        self.invites = {}

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

        # Build the Embed
        embed = discord.Embed(color=0x2b2d31)
        embed.set_author(name="Member Joined", icon_url=member.display_avatar.url)
        embed.description = f"{member.mention} {member.name}\n\n**Account Age**\n{age_str}\n\n**ID:** {member.id}"
        embed.set_thumbnail(url=member.display_avatar.url)

        if inviter:
            footer_text = f"{member.name} just joined. They were invited by {inviter.name} who now has {total_invites} invites!"
        else:
            footer_text = f"{member.name} just joined. I couldn't track the invite (Vanity URL or temporary code)."
            
        embed.set_footer(text=footer_text)

        await log_channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(InviteTracker(bot))
    print("✅ LOG: Invite Tracker System is ONLINE.")
