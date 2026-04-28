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
        """Global listener that catches any 'steal' button click regardless of when it was sent."""
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("fiery_steal:"):
            return

        # 1. Access Main Module for Embeds
        main_mod = sys.modules['__main__']
        
        # 2. Authorization Check (Master Only)
        if not await self.bot.is_owner(interaction.user):
            return await interaction.response.send_message("❌ **Neural Lock:** Access restricted to the Master.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # 3. Parse Data from Custom ID (Format: fiery_steal:ID:IS_ANIMATED:NAME)
        try:
            parts = custom_id.split(":")
            emoji_id = parts[1]
            is_animated = parts[2] == "1"
            emoji_name = parts[3]
            
            ext = "gif" if is_animated else "png"
            emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
        except Exception as e:
            return await interaction.followup.send(f"❌ **Data Corruption:** `{e}`", ephemeral=True)

        # 4. Processing Protocol
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(emoji_url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send("❌ Failed to download asset from Discord CDN.", ephemeral=True)
                    emoji_bytes = await resp.read()

            # Upload to the current server
            new_emoji = await interaction.guild.create_custom_emoji(
                name=emoji_name, 
                image=emoji_bytes, 
                reason=f"Neural Harvest by {interaction.user}"
            )
            
            await interaction.followup.send(embed=main_mod.fiery_embed(
                "💎 ASSET ASSIMILATED", 
                f"Successfully added {new_emoji} (`{emoji_name}`) to the server's database."
            ), ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ **Access Denied:** The bot needs `Manage Emojis` permissions in this server.", ephemeral=True)
        except discord.HTTPException as e:
            if e.code == 30008:
                await interaction.followup.send("❌ **Vault Full:** This server has reached its emoji limit.", ephemeral=True)
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
        
        time_limit = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
        found_emojis = []
        seen_ids = set()

        try:
            # Scanning last 150 messages
            async for message in ctx.channel.history(limit=150, after=time_limit):
                if message.author.bot and message.author.id == self.bot.user.id:
                    continue
                
                # Regex to find <:name:ID> or <a:name:ID>
                custom_emojis = re.findall(r'<(a?):(\w+):(\d+)>', message.content)
                
                for animated, name, e_id in custom_emojis:
                    if e_id not in seen_ids:
                        is_animated = "1" if animated == "a" else "0"
                        # We store a dict to help build buttons
                        found_emojis.append({
                            "id": e_id,
                            "name": name,
                            "anim": is_animated,
                            "raw": f"<{animated}:{name}:{e_id}>"
                        })
                        seen_ids.add(e_id)

            if not found_emojis:
                return await status_msg.edit(content=None, embed=main_mod.fiery_embed("📡 SCAN COMPLETE", "No unique custom frequencies detected recently.", color=0xFFFF00))

            # UI Construction (Max 25 buttons per message)
            view = discord.ui.View(timeout=None)
            for e in found_emojis[:25]:
                # We build a PartialEmoji just for the button icon
                btn_emoji = discord.PartialEmoji(name=e['name'], id=int(e['id']), animated=(e['anim']=="1"))
                
                btn = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    emoji=btn_emoji,
                    custom_id=f"fiery_steal:{e['id']}:{e['anim']}:{e['name']}"
                )
                view.add_item(btn)
            
            embed = main_mod.fiery_embed("🛰️ NEURAL HARVESTER", f"Found **{len(found_emojis[:25])}** unique assets in the stream.\n\nSelect a frequency below to assimilate it into this sector.")
            await status_msg.edit(content=None, embed=embed, view=view)

        except Exception as e:
            await status_msg.edit(content=f"❌ **Scan Interrupted:** `{e}`")

async def setup(bot):
    await bot.add_cog(EmojiSystem(bot))
