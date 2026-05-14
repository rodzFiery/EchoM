import discord
from discord.ext import commands
import sys
import aiohttp
import re
import datetime
import asyncio

class EmojiSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, interaction_or_ctx):
        """Helper to check if user is Server Owner or has the designated Admin Role."""
        # Bot Owner always has access
        if await self.bot.is_owner(interaction_or_ctx.user if isinstance(interaction_or_ctx, discord.Interaction) else interaction_or_ctx.author):
            return True
            
        guild = interaction_or_ctx.guild
        user = interaction_or_ctx.user if isinstance(interaction_or_ctx, discord.Interaction) else interaction_or_ctx.author
        
        # 1. Check if user is Server Owner
        if guild.owner_id == user.id:
            return True
            
        # 2. Check Database for designated !adminrole
        main_mod = sys.modules['__main__']
        try:
            with main_mod.get_db_connection() as conn:
                # We pull from guild_config (synced with audit.py/admin.py logic)
                res = conn.execute("SELECT value FROM guild_config WHERE guild_id = ? AND key = 'admin_role'", (guild.id,)).fetchone()
                if res:
                    admin_role_id = int(res[0])
                    if any(role.id == admin_role_id for role in user.roles):
                        return True
        except:
            pass
            
        return False

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """GLOBAL LISTENER: Handles individual steals and the 'Steal All' protocol."""
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("fiery_"):
            return

        # NEW PERMISSION CHECK
        if not await self.check_permissions(interaction):
            return await interaction.response.send_message("❌ **Neural Lock:** You do not have the required clearance level.", ephemeral=True)

        main_mod = sys.modules['__main__']
        
        # --- PROTOCOL: STEAL ALL ---
        if custom_id.startswith("fiery_all:"):
            await interaction.response.defer(ephemeral=True)
            data_string = custom_id.replace("fiery_all:", "")
            emoji_list = data_string.split("|")
            
            success_count = 0
            errors = []

            for entry in emoji_list:
                try:
                    e_id, e_anim, e_name = entry.split(",")
                    ext = "gif" if e_anim == "1" else "png"
                    url = f"https://cdn.discordapp.com/emojis/{e_id}.{ext}"
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                img = await resp.read()
                                await interaction.guild.create_custom_emoji(name=e_name, image=img, reason=f"Mass Harvest by {interaction.user}")
                                success_count += 1
                            else:
                                errors.append(f"Failed {e_name} (CDN Error)")
                except discord.HTTPException as e:
                    if e.code == 30008:
                        errors.append("Server limit reached.")
                        break
                    errors.append(f"Error {e_name}: {e.text}")
                except Exception:
                    continue

            result_msg = f"✅ **Mass Assimilation Complete.**\nSuccessfully added `{success_count}` assets."
            return await interaction.followup.send(embed=main_mod.fiery_embed("🛰️ MASS HARVEST RESULT", result_msg), ephemeral=True)

        # --- PROTOCOL: INDIVIDUAL STEAL ---
        if custom_id.startswith("fiery_steal:"):
            await interaction.response.defer(ephemeral=True)
            try:
                parts = custom_id.split(":")
                e_id, e_anim, e_name = parts[1], parts[2], parts[3]
                ext = "gif" if e_anim == "1" else "png"
                url = f"https://cdn.discordapp.com/emojis/{e_id}.{ext}"

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        img = await resp.read()
                        new_emoji = await interaction.guild.create_custom_emoji(name=e_name, image=img, reason=f"Harvested by {interaction.user}")
                        await interaction.followup.send(embed=main_mod.fiery_embed("💎 ASSET ACQUIRED", f"Assimilated: {new_emoji}"), ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ **System Error:** `{e}`", ephemeral=True)

    @commands.command(name="stealemoji")
    async def harvest_recent(self, ctx):
        """Scans last 15m of traffic for emojis."""
        # NEW PERMISSION CHECK
        if not await self.check_permissions(ctx):
            return await ctx.send("❌ **Access Denied:** Administrator clearance required.")

        main_mod = sys.modules['__main__']
        status_msg = await ctx.send("🛰️ **Scanning frequencies...**")
        
        time_limit = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
        found_emojis = []
        seen_ids = set()

        try:
            async for message in ctx.channel.history(limit=100, after=time_limit):
                if message.author.bot and message.author.id == self.bot.user.id: continue
                
                matches = re.findall(r'<(a?):(\w+):(\d+)>', message.content)
                for anim, name, e_id in matches:
                    if e_id not in seen_ids:
                        is_anim = "1" if anim == "a" else "0"
                        found_emojis.append({"id": e_id, "name": name, "anim": is_anim})
                        seen_ids.add(e_id)

            if not found_emojis:
                return await status_msg.edit(content=None, embed=main_mod.fiery_embed("📡 SCAN COMPLETE", "No assets detected.", color=0xFFFF00))

            view = discord.ui.View(timeout=None)
            all_data_payload = []

            for e in found_emojis[:24]:
                btn_emoji = discord.PartialEmoji(name=e['name'], id=int(e['id']), animated=(e['anim']=="1"))
                view.add_item(discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    emoji=btn_emoji,
                    custom_id=f"fiery_steal:{e['id']}:{e['anim']}:{e['name']}"
                ))
                all_data_payload.append(f"{e['id']},{e['anim']},{e['name']}")

            payload = "|".join(all_data_payload)
            if len(payload) > 80:
                payload = payload[:80].rsplit('|', 1)[0]

            view.add_item(discord.ui.Button(
                label="STEAL ALL ASSETS",
                style=discord.ButtonStyle.danger,
                emoji="🔥",
                custom_id=f"fiery_all:{payload}"
            ))
            
            embed = main_mod.fiery_embed("🛰️ NEURAL HARVESTER", f"Detected **{len(found_emojis)}** unique frequencies.\n\nSelect one to assimilate or trigger a mass harvest.")
            await status_msg.edit(content=None, embed=embed, view=view)

        except Exception as e:
            await status_msg.edit(content=f"❌ **Scan Interrupted:** `{e}`")

async def setup(bot):
    await bot.add_cog(EmojiSystem(bot))
