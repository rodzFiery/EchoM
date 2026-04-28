import discord
from discord.ext import commands
import sys
import aiohttp
import datetime

class EmojiStealButton(discord.ui.Button):
    def __init__(self, emoji_obj, main_mod):
        # We use the emoji itself as the label or emoji on the button
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji_obj)
        self.emoji_obj = emoji_obj
        self.main_mod = main_mod

    async def callback(self, interaction: discord.Interaction):
        # Ensure only the Master can trigger the assimilation
        if not await self.main_mod.bot.is_owner(interaction.user):
            return await interaction.response.send_message("❌ **Neural Lock:** Access restricted to the Master.", ephemeral=True)

        await interaction.response.defer()
        
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
            
        except Exception as e:
            await interaction.followup.send(f"❌ **System Error:** `{e}`", ephemeral=True)

class EmojiPickerView(discord.ui.View):
    def __init__(self, emojis, main_mod):
        super().__init__(timeout=60)
        for emoji in emojis:
            self.add_item(EmojiStealButton(emoji, main_mod))

class EmojiSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ... Your existing steal and steal_id commands remain here ...

    @commands.command(name="stealemoji")
    @commands.is_owner()
    async def harvest_recent(self, ctx):
        """Scans the last 10 minutes of traffic for extractable emojis."""
        main_mod = sys.modules['__main__']
        
        time_limit = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
        found_emojis = []
        seen_ids = set()

        # Scan history
        async for message in ctx.channel.history(limit=100, after=time_limit):
            # Regex or discord.py's partial emoji converter could work, 
            # but searching message.content for <:name:id> is safer:
            import re
            custom_emojis = re.findall(r'<(a?):(\w+):(\d+)>', message.content)
            
            for animated, name, e_id in custom_emojis:
                if e_id not in seen_ids:
                    is_animated = bool(animated)
                    emoji_url = f"https://cdn.discordapp.com/emojis/{e_id}.{'gif' if is_animated else 'png'}"
                    # Create a partial emoji object for the UI
                    partial = discord.PartialEmoji(animated=is_animated, name=name, id=int(e_id))
                    found_emojis.append(partial)
                    seen_ids.add(e_id)

        if not found_emojis:
            return await ctx.send(embed=main_mod.fiery_embed("📡 SCAN COMPLETE", "No unique neural frequencies (emojis) detected in the last 10 minutes.", color=0xFFFF00))

        # Limit to 25 buttons (Discord's max per row/view limit for buttons is 25)
        found_emojis = found_emojis[:25]

        view = EmojiPickerView(found_emojis, main_mod)
        embed = main_mod.fiery_embed("🛰️ NEURAL HARVESTER", f"Found **{len(found_emojis)}** assets in the recent stream.\n\nSelect a frequency below to assimilate it into this server.")
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(EmojiSystem(bot))
