import discord
from discord.ext import commands
import sys
import aiohttp
import datetime
import re

class EmojiStealButton(discord.ui.Button):
    def __init__(self, emoji_obj, main_mod):
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji_obj)
        self.emoji_obj = emoji_obj
        self.main_mod = main_mod

    async def callback(self, interaction: discord.Interaction):
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
            if e.code == 30008: # Maximum emojis reached
                await interaction.followup.send("❌ **Vault Full:** This server has reached its maximum emoji limit.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ **HTTP Error:** `{e}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ **System Error:** `{e}`", ephemeral=True)

class EmojiPickerView(discord.ui.View):
    def __init__(self, emojis, main_mod):
        super().__init__(timeout=120) # Increased timeout to 2 minutes
        self.main_mod = main_mod
        for emoji in emojis:
            self.add_item(EmojiStealButton(emoji, main_mod))

    async def on_timeout(self):
        # Disable all buttons when the view expires so people don't click "dead" buttons
        for item in self.children:
            item.disabled = True
        # Note: We can't edit the message here easily without saving the message object

class EmojiSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="stealemoji")
    @commands.is_owner()
    async def harvest_recent(self, ctx):
        """Scans the last 10 minutes of traffic for extractable emojis."""
        main_mod = sys.modules['__main__']
        
        # ADDED: Feedback so you know the bot is actually working
        status_msg = await ctx.send("🛰️ **Scanning frequencies...**")
        
        time_limit = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
        found_emojis = []
        seen_ids = set()

        try:
            async for message in ctx.channel.history(limit=100, after=time_limit):
                custom_emojis = re.findall(r'<(a?):(\w+):(\d+)>', message.content)
                
                for animated, name, e_id in custom_emojis:
                    if e_id not in seen_ids:
                        is_animated = bool(animated)
                        partial = discord.PartialEmoji(animated=is_animated, name=name, id=int(e_id))
                        found_emojis.append(partial)
                        seen_ids.add(e_id)

            if not found_emojis:
                return await status_msg.edit(content=None, embed=main_mod.fiery_embed("📡 SCAN COMPLETE", "No unique neural frequencies (emojis) detected in the last 10 minutes.", color=0xFFFF00))

            found_emojis = found_emojis[:25]
            view = EmojiPickerView(found_emojis, main_mod)
            
            embed = main_mod.fiery_embed("🛰️ NEURAL HARVESTER", f"Found **{len(found_emojis)}** assets in the recent stream.\n\nSelect a frequency below to assimilate it into this server.")
            await status_msg.edit(content=None, embed=embed, view=view)

        except Exception as e:
            await status_msg.edit(content=f"❌ **Scan Interrupted:** `{e}`")

async def setup(bot):
    await bot.add_cog(EmojiSystem(bot))
