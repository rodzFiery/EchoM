import discord
from discord.ext import commands
import sys
import importlib
import os

class HelperSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="refresh")
    @commands.is_owner() # Secure override for the Master
    async def refresh(self, ctx):
        """Hot-reloads all extensions and synchronizes the database link."""
        msg = await ctx.send("🔄 **RECALIBRATING NEURAL NET...**")
        
        try:
            # 1. Clear internal cache for local modules
            # This ensures that if you changed prizes.py or utilis.py, the bot sees it.
            local_modules = ['utilis', 'database', 'prizes', 'worknranks', 'daily', 'social']
            for mod in local_modules:
                if mod in sys.modules:
                    importlib.reload(sys.modules[mod])
            
            # 2. Re-sync Database Connection
            import database as db_module
            db_module.init_db() 
            
            # 3. Reload Cogs
            # These names must match your .py filenames exactly
            extensions = [
                "admin", "classes", "extensions", "ship", "shop", "collect", 
                "fight", "casino", "ask", "premium", "audit", "thread", 
                "levels", "react", "counting", "guessnumber", "reactionrole", 
                "autoignis", "confession"
            ]

            reloaded = []
            failed = []

            for ext in extensions:
                try:
                    # Attempt to reload the extension
                    await self.bot.reload_extension(ext)
                    reloaded.append(f"✅ {ext}")
                except commands.ExtensionNotLoaded:
                    # If it wasn't loaded yet, load it now
                    try:
                        await self.bot.load_extension(ext)
                        reloaded.append(f"✅ {ext}")
                    except Exception as e:
                        failed.append(f"❌ {ext} (Load Fail: {e})")
                except Exception as e:
                    failed.append(f"❌ {ext} (Reload Fail: {e})")

            # Import fiery_embed from utilis or use local logic to match main.py style
            from utilis import fiery_embed
            # Check for nsfw_mode_active in main
            main_mod = sys.modules['__main__']
            nsfw = getattr(main_mod, 'nsfw_mode_active', False)
            
            # Formatting the Status Report
            status_report = "**Synchronized:**\n" + (", ".join(reloaded) if reloaded else "None")
            if failed:
                status_report += "\n\n**Failed Protocols:**\n" + "\n".join(failed)

            embed = fiery_embed(self.bot, nsfw, "⚙️ SYSTEM REFRESH COMPLETE", 
                                f"Neural links restored.\n\n{status_report}\n\n**Database:** Persistent & Online.", 
                                color=0x00FF00)
            
            await msg.edit(content=None, embed=embed)
            print(f"✅ LOG: Manual Refresh triggered by {ctx.author}. Database re-initialized.")

        except Exception as e:
            await msg.edit(content=f"❌ **SYSTEM RECOVERY FAILED:** `{e}`")

async def setup(bot):
    await bot.add_cog(HelperSystem(bot))
