import discord
from discord.ext import commands
import sys
import aiohttp
import re
import datetime

class EmojiSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """
        GLOBAL LISTENER: This is the secret. 
        It watches for ANY button click with the prefix 'fiery_steal:'
        This works even if the bot was restarted after the buttons were sent.
        """
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("fiery_steal:"):
            return

        # 1. Access Main Module for the fiery_embed look
        main_mod = sys.modules['__main__']
        
        # 2. Authorization Check (Only the Master/Owner)
        if not await self.bot.is_owner(interaction.user):
            return await interaction.response.send_message("❌ **Neural Lock:** Access restricted to the Master.", ephemeral=True)

        # Defer so the interaction doesn't expire during download/upload
        await interaction.response.defer(ephemeral=True)

        # 3. Parse data from the Custom ID
        # Format: fiery_steal : EMOJI_ID : IS_ANIMATED : EMOJI_NAME
        try:
            parts = custom_id.split(":")
            e_id = parts[1]
            is_animated = parts[2] == "1"
            e_name = parts[3]
            
            extension = "gif" if is_animated else "png"
            emoji_url = f"https://cdn.discordapp.com/emojis/{e_id}.{extension}"
        except Exception as e:
            return await interaction.followup.send(f"❌ **Data Corruption:** `{e}`", ephemeral=True)

        # 4. Extraction & Assimilation Protocol
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(emoji_url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send("❌ Failed to download asset from Discord CDN.", ephemeral=True)
                    emoji_bytes = await resp.read()

            # Create the emoji in the guild where the button was clicked
            new_emoji = await interaction.guild.create_custom_emoji(
                name=e_name, 
                image=emoji_bytes, 
                reason=f"Neural Harvest by {interaction.user}"
            )
            
            await interaction.followup.send(embed=main_mod.fiery_embed(
                "💎 ASSET ASSIMILATED", 
                f"Successfully added {new_emoji} (`{e_name}`) to the server's database."
            ), ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ **Access Denied:** Ensure the bot has `Manage Emojis` permissions.", ephemeral=True)
        except discord.HTTPException as e:
            if e.code == 30008:
                await interaction.followup.send("❌ **Vault Full:** This server has reached its emoji limit (50/50).", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ **HTTP Error:** `{e}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ **System Error:** `{e}`", ephemeral=True)

    @commands.command(name="stealemoji")
    @commands.is_owner()
    async def harvest_recent(self, ctx):
        """Scans the last 15 minutes of traffic for extractable custom emojis."""
        main_mod = sys.modules['__main__']
        status_msg = await ctx.send("🛰️ **Scanning frequencies for custom assets...**")
        
        # Scans last 15 minutes
        time_limit = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
        found_emojis = []
        seen_ids = set()

        try:
            # Checking the last 100 messages for emoji patterns
            async for message in ctx.channel.history(limit=100, after=time_limit):
                if message.author.bot and message.author.id == self.bot.user.id:
                    continue
                
                # Regex for <:name:ID> or <a:name:ID>
                custom_emojis = re.findall(r'<(a?):(\w+):(\d+)>', message.content)
                
                for animated, name, e_id in custom_emojis:
                    if e_id not in seen_ids:
                        found_emojis.append({
                            "id": e_id,
                            "name": name,
                            "anim": "1" if animated == "a" else "0"
                        })
                        seen_ids.add(e_id)

            if not found_emojis:
                return await status_msg.edit(content=None, embed=main_mod.fiery_embed("📡 SCAN COMPLETE", "No unique custom frequencies detected recently.", color=0xFFFF00))

            # Build the View (No timeout so buttons stay active)
            view = discord.ui.View(timeout=None)
            
            # Discord limits to 25 buttons per message
            for e in found_emojis[:25]:
                btn_emoji = discord.PartialEmoji(name=e['name'], id=int(e['id']), animated=(e['anim'] == "1"))
                
                # Create button with custom_id containing all necessary info
                btn = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    emoji=btn_emoji,
                    custom_id=f"fiery_steal:{e['id']}:{e['anim']}:{e['name']}"
                )
                view.add_item(btn)
            
            embed = main_mod.fiery_embed("🛰️ NEURAL HARVESTER", f"Found **{len(found_emojis[:25])}** assets in the stream.\n\nSelect a frequency below to assimilate it into this sector.")
            await status_msg.edit(content=None, embed=embed, view=view)

        except Exception as e:
            await status_msg.edit(content=f"❌ **Scan Interrupted:** `{e}`")

async def setup(bot):
    await bot.add_cog(EmojiSystem(bot))
