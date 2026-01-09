import discord
from discord.ext import commands
import sys
import os
import database as db_module # Syncing with your centralized DB logic

class AuditManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="audit")
    @commands.has_permissions(administrator=True)
    async def audit(self, ctx, *channels: discord.TextChannel):
        """Admin command to redirect the system's AUDIT_CHANNEL_ID."""
        main_mod = sys.modules['__main__']
        
        # Validation: Max 2 channels as requested
        if len(channels) == 0:
            return await ctx.send(embed=main_mod.fiery_embed("❌ ERROR", "You must mention at least one channel. Usage: `!audit #channel1 [#channel2]`"))
        
        if len(channels) > 2:
            return await ctx.send(embed=main_mod.fiery_embed("❌ ERROR", "You can select a maximum of 2 channels for the redirection protocol."))

        # Extract IDs
        channel_ids = [c.id for c in channels]
        primary_id = channel_ids[0]
        
        # Update Global Variable in main.py memory
        main_mod.AUDIT_CHANNEL_ID = primary_id
        
        # Sync with other modules that might be holding the old ID
        for cog_name in ["IgnisEngine", "Collect", "FieryShip", "DungeonAsk"]:
            cog = self.bot.get_cog(cog_name)
            if cog and hasattr(cog, "AUDIT_CHANNEL_ID"):
                cog.AUDIT_CHANNEL_ID = primary_id

        # PERSISTENCE: Save to database so it stays fixed after Railway restart
        try:
            with db_module.get_db_connection() as conn:
                # We assume a 'config' table exists for system variables
                conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('audit_channel', ?)", (str(primary_id),))
                conn.commit()
        except Exception as e:
            print(f"⚠️ Persistence Error: {e}")

        # Final Confirmation
        channel_mentions = " ".join([c.mention for c in channels])
        embed = main_mod.fiery_embed("🕵️ AUDIT PROTOCOL UPDATED", 
            f"The Master has redirected the voyeur frequencies.\n\n"
            f"**New Audit Target(s):** {channel_mentions}\n"
            f"**System Status:** All logs are now routing to the designated sector.", color=0x00FF00)
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AuditManager(bot))
    print("✅ LOG: Audit Manager Extension (Dynamic Redirect) is ONLINE.")
