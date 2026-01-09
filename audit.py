import discord
from discord.ext import commands
import sys

class AuditManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Storage for current active audit channels (Max 2)
        self.active_audit_channels = []

    @commands.command(name="audit")
    @commands.has_permissions(administrator=True)
    async def set_audit_channels(self, ctx, *channels: discord.TextChannel):
        """
        ADMIN ONLY: Sets the audit destination channels (Max 2).
        Usage: !audit #channel1 #channel2
        """
        main_mod = sys.modules['__main__']
        
        if not channels:
            return await ctx.send("❌ **ERROR:** You must mention at least one channel. Usage: `!audit #channel`")

        if len(channels) > 2:
            return await ctx.send("❌ **PROTOCOL BREACH:** You can only monitor a maximum of **2 audit channels** simultaneously.")

        # Update the local list
        self.active_audit_channels = [c.id for c in channels]
        
        # Access the FieryShip cog to update its internal ID
        # UPDATED: Matches the class name 'FieryShip' from your ship.py
        ship_cog = self.bot.get_cog("FieryShip")
        
        if ship_cog:
            # We update the first channel as the primary AUDIT_CHANNEL_ID for the Ship logic
            ship_cog.AUDIT_CHANNEL_ID = self.active_audit_channels[0]
            
            # Prepare confirmation message
            channel_mentions = ", ".join([c.mention for c in channels])
            
            emb = main_mod.fiery_embed(
                "🕵️ VOYEUR REDIRECTED", 
                f"The Master has updated the surveillance parameters.\n\n"
                f"**Monitoring Channels:** {channel_mentions}\n"
                f"**Primary Feed:** {channels[0].mention}\n\n"
                f"All future soul synchronizations will be recorded in these sectors.",
                color=0x5865F2
            )
            
            await ctx.send(embed=emb)
            
            # Optional: Log the change in the new primary channel
            log_emb = main_mod.fiery_embed("🛰️ AUDIT FEED ACTIVE", "This channel has been designated for synchronization monitoring.")
            await channels[0].send(embed=log_emb)
            
        else:
            await ctx.send("❌ **SYSTEM ERROR:** The `FieryShip` module was not detected. Ensure it is loaded first.")

    @set_audit_channels.error
    async def audit_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("🚫 **ACCESS DENIED:** Only high-ranking Admins can redirect the Voyeur feeds.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ **INVALID SECTOR:** Please mention actual text channels (e.g., #channel).")

async def setup(bot):
    await bot.add_cog(AuditManager(bot))
    print("✅ LOG: Audit Extension (Feed Management) is ONLINE.")
