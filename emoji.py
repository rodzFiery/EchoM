import discord
from discord.ext import commands
import sys
import aiohttp
import datetime
import re
import asyncio

class EmojiStealButton(discord.ui.Button):
    def __init__(self, emoji_obj, main_mod):
        # We use a static custom_id prefix + the emoji ID to make it persistent
        super().__init__(
            style=discord.ButtonStyle.secondary, 
            emoji=emoji_obj, 
            custom_id=f"fiery_steal:{emoji_obj.id}:{emoji_obj.animated}:{emoji_obj.name}"
        )
        self.emoji_obj = emoji_obj
        self.main_mod = main_mod

    async def callback(self, interaction: discord.Interaction):
        # Master authorization check
        if not await self.main_mod.bot.is_owner(interaction.user):
            return await interaction.response.send_message("❌ **Neural Lock:** Access restricted to the Master.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        
        # Extract data from the button's own emoji object
        emoji_url = self.emoji_obj.url
        emoji_name = self.emoji_obj.name

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(emoji_url)) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send("❌ Failed to download asset from Discord CDN.", ephemeral=True)
                    emoji_bytes = await resp.read()

            new_emoji = await interaction.guild.create_custom_emoji(
                name=emoji_name, 
                image=emoji_bytes, 
                reason=f"Neural Harvest by {interaction.user}"
            )
            
            await interaction.followup.send(embed=self.main_mod.fiery_embed(
                "💎 ASSET ASSIMILATED", 
                f"Successfully added {new_emoji} (`{new_emoji.name}`) to the server's database."
            ), ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ **Access Denied:** The Red Room lacks `Manage Emojis` permissions.", ephemeral=True)
        except discord.HTTPException as e:
            if e.code == 30008:
                await interaction.followup.send("❌ **Vault Full:** This sector has reached its emoji limit.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ **HTTP Error:** `{e}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ **System Error:** `{e}`", ephemeral=True)

class EmojiPickerView(discord.ui.View):
    def __init__(self, emojis, main_mod):
        super().__init__(timeout=None) # Mandatory for persistence
        for emoji in emojis:
            self.add_item(EmojiStealButton(emoji, main_mod))

class EmojiSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Register the view listener on initialization
        self.bot.loop.create_task(self.prepare_persistence())

    async def prepare_persistence(self):
        """Prepares the bot to listen for any steal buttons across the network."""
        self.bot.add_view(discord.ui.View(timeout=None))

    @commands.command(name="stealemoji")
    @commands.is_owner()
    async def harvest_recent(self, ctx):
        """Scans the last 15 minutes of traffic for extractable emojis."""
        main_mod = sys.modules['__main__']
        
        status_msg = await ctx.send("🛰️ **Scanning frequencies for custom assets...**")
        
        time_limit = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
        found_emojis = []
        seen_ids = set()

        try:
            # Scanning last 150 messages for accuracy
            async for message in ctx.channel.history(limit=150, after=time_limit):
                if message.author.bot and message.author.id == self.bot.user.id:
                    continue
                
                # Regex captures: <(animated):name:ID>
                custom_emojis = re.findall(r'<(a?):(\w+):(\d+)>', message.content)
                
                for animated, name, e_id in custom_emojis:
                    if e_id not in seen_ids:
                        is_animated = bool(animated)
                        partial = discord.PartialEmoji(animated=is_animated, name=name, id=int(e_id))
                        found_emojis.append(partial)
                        seen_ids.add(e_id)

            if not found_emojis:
                return await status_msg.edit(content=None, embed=main_mod.fiery_embed("📡 SCAN COMPLETE", "No unique custom frequencies detected in the recent stream.", color=0xFFFF00))

            # Limit to 25 buttons per Discord UI limits
            found_emojis = found_emojis[:25]
            view = EmojiPickerView(found_emojis, main_mod)
            
            # This registers this specific instance of the view
            self.bot.add_view(view)
            
            embed = main_mod.fiery_embed("🛰️ NEURAL HARVESTER", f"Found **{len(found_emojis)}** unique assets.\n\nSelect a frequency below to assimilate it into this server.")
            await status_msg.edit(content=None, embed=embed, view=view)

        except Exception as e:
            await status_msg.edit(content=f"❌ **Scan Interrupted:** `{e}`")

async def setup(bot):
    await bot.add_cog(EmojiSystem(bot))
