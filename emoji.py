import discord
from discord.ext import commands
import sys
import aiohttp
import datetime
import re
import asyncio

class EmojiStealButton(discord.ui.Button):
    def __init__(self, emoji_obj, main_mod):
        # Unique custom_id is MANDATORY for persistent buttons to work after restart
        super().__init__(
            style=discord.ButtonStyle.secondary, 
            emoji=emoji_obj, 
            custom_id=f"steal_{emoji_obj.id}"
        )
        self.emoji_obj = emoji_obj
        self.main_mod = main_mod

    async def callback(self, interaction: discord.Interaction):
        # Authorization check
        if not await self.main_mod.bot.is_owner(interaction.user):
            return await interaction.response.send_message("❌ **Neural Lock:** Access restricted to the Master.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.emoji_obj.url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send("❌ Failed to download asset.", ephemeral=True)
                    emoji_bytes = await resp.read()

            new_emoji = await interaction.guild.create_custom_emoji(
                name=self.emoji_obj.name, 
                image=emoji_bytes, 
                reason=f"Neural Harvest by {interaction.user}"
            )
            
            await interaction.followup.send(embed=self.main_mod.fiery_embed(
                "💎 ASSET ASSIMILATED", 
                f"Successfully added {new_emoji} to the server's database."
            ), ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ **Access Denied:** Bot needs `Manage Emojis` permissions.", ephemeral=True)
        except discord.HTTPException as e:
            if e.code == 30008:
                await interaction.followup.send("❌ **Vault Full:** Maximum emoji limit reached.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ **HTTP Error:** `{e}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ **System Error:** `{e}`", ephemeral=True)

class EmojiPickerView(discord.ui.View):
    def __init__(self, emojis, main_mod):
        # timeout=None makes the view stay active until the bot restarts
        super().__init__(timeout=None)
        self.main_mod = main_mod
        for emoji in emojis:
            self.add_item(EmojiStealButton(emoji, main_mod))

class EmojiSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="stealemoji")
    @commands.is_owner()
    async def harvest_recent(self, ctx):
        """Scans the last 10 minutes of traffic for extractable emojis."""
        main_mod = sys.modules['__main__']
        
        status_msg = await ctx.send("🛰️ **Scanning frequencies for assets...**")
        
        # Increase the time window slightly to be safe
        time_limit = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
        found_emojis = []
        seen_ids = set()

        try:
            # We search the last 200 messages with no limit on the loop itself
            async for message in ctx.channel.history(limit=200, after=time_limit):
                # Improved RegEx to catch all custom emojis accurately
                custom_emojis = re.findall(r'<(a?):(\w+):(\d+)>', message.content)
                
                for animated, name, e_id in custom_emojis:
                    if e_id not in seen_ids:
                        is_animated = bool(animated)
                        partial = discord.PartialEmoji(animated=is_animated, name=name, id=int(e_id))
                        found_emojis.append(partial)
                        seen_ids.add(e_id)

            if not found_emojis:
                return await status_msg.edit(content=None, embed=main_mod.fiery_embed("📡 SCAN COMPLETE", "No unique neural frequencies (custom emojis) detected recently.", color=0xFFFF00))

            # Limit to 25 to stay within Discord's button-per-row limit
            found_emojis = found_emojis[:25]
            view = EmojiPickerView(found_emojis, main_mod)
            
            # This registers the view so it handles interactions permanently
            self.bot.add_view(view)
            
            embed = main_mod.fiery_embed("🛰️ NEURAL HARVESTER", f"Found **{len(found_emojis)}** assets.\n\nSelect a frequency below to assimilate it.")
            await status_msg.edit(content=None, embed=embed, view=view)

        except Exception as e:
            await status_msg.edit(content=f"❌ **Scan Interrupted:** `{e}`")

async def setup(bot):
    await bot.add_cog(EmojiSystem(bot))
