import discord
from discord.ext import commands
import random
import io
import aiohttp
import sys
import json
import os
import asyncio # ADDED: Required for thread-safe processing
import sqlite3 # ADDED: For tracking secure Tributes and Interrogations persistently
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageOps, ImageFilter

# --- ADDED: DATABASE INIT FOR SECURE STORAGE ---
with sqlite3.connect("dungeon_ask.db") as conn:
    conn.execute("CREATE TABLE IF NOT EXISTS tributes (req_id INTEGER, tar_id INTEGER, tribute TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS interrogations (msg_id INTEGER, alert_msg_id INTEGER, tar_id INTEGER, question TEXT)")
    # New configuration layout storage block for admin settings
    conn.execute("CREATE TABLE IF NOT EXISTS config (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, role_id INTEGER)")
    conn.commit()

# --- ADDED: BACKUP/RESTORE SYSTEM FOR RAILWAY DEPLOYMENT PERSISTENCE ---
def save_backup_config(guild_id, channel_id=None, role_id=None):
    filename = "ask_backup_config.json"
    data = {}
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
        except:
            data = {}
    
    g_id_str = str(guild_id)
    if g_id_str not in data:
        data[g_id_str] = {"channel_id": None, "role_id": None}
        
    if channel_id is not None:
        data[g_id_str]["channel_id"] = channel_id
    if role_id is not None:
        data[g_id_str]["role_id"] = role_id
        
    with open(filename, "w") as f:
        json.dump(data, f)

def load_backup_config(guild_id):
    filename = "ask_backup_config.json"
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, "r") as f:
            data = json.load(f)
        g_id_str = str(guild_id)
        if g_id_str in data:
            return data[g_id_str]
    except:
        return None
    return None

# --- ADDED: FEATURE 2 - INTERROGATION SYSTEM COMPONENTS ---
class AnswerModal(discord.ui.Modal, title="Submit an answer"):
    answer = discord.ui.TextInput(label="Your Answer", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, tar_id, msg_id, question):
        super().__init__(custom_id=f"ask_ans_modal:{tar_id}:{msg_id}")
        self.tar_id = tar_id
        self.msg_id = msg_id
        self.question = question

    async def on_submit(self, interaction: discord.Interaction):
        try:
            original_msg = await interaction.channel.fetch_message(self.msg_id)
            embed = original_msg.embeds[0]
            
            # --- MODIFIED: Append logs cleanly into the single layout description block ---
            desc = embed.description.replace("\n** **", "")
            embed.description = desc + f"\n**<@{self.tar_id}>:** {self.question}\n**{interaction.user.mention}:** {self.answer.value}\n** **"
            
            await original_msg.edit(embed=embed)
            await interaction.response.send_message("✅ Answer transmitted to the target.", ephemeral=True)
            await interaction.message.delete()
        except Exception as e:
            await interaction.response.send_message(f"❌ Transmission failed: {e}", ephemeral=True)

class AnswerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Submit Answer", style=discord.ButtonStyle.success, emoji="✍️", custom_id="ask_dm_answer_v3")
    async def answer_btn(self, inter: discord.Interaction, btn: discord.ui.Button):
        with sqlite3.connect("dungeon_ask.db") as conn:
            row = conn.execute("SELECT msg_id, tar_id, question FROM interrogations WHERE alert_msg_id=?", (inter.message.id,)).fetchone()
        
        if not row:
            return await inter.response.send_message("❌ Data block corrupted or missing.", ephemeral=True)
            
        orig_msg_id, tar_id, question = row
        await inter.response.send_modal(AnswerModal(tar_id, orig_msg_id, question))

class InterrogateModal(discord.ui.Modal, title="Make a question before accept"):
    question = discord.ui.TextInput(label="Your Question", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, req_id, tar_id, msg_id):
        super().__init__(custom_id=f"ask_int_modal:{req_id}:{tar_id}:{msg_id}")
        self.req_id = req_id
        self.tar_id = tar_id
        self.msg_id = msg_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        req_user = interaction.guild.get_member(self.req_id)
        if not req_user:
            try:
                req_user = await interaction.guild.fetch_member(self.req_id)
            except:
                return await interaction.followup.send("❌ Could not retrieve the requester asset.", ephemeral=True)
                
        embed = discord.Embed(title="👁️ Questions:", description=f"{req_user.mention}, you are being interrogated by {interaction.user.mention} before they open the gate.\n\n**QUESTION:** {self.question.value}", color=0xFFD700)
        view = AnswerView()
        alert_msg = await interaction.channel.send(content=req_user.mention, embed=embed, view=view)
        
        with sqlite3.connect("dungeon_ask.db") as conn:
            conn.execute("INSERT INTO interrogations VALUES (?, ?, ?, ?)", (self.msg_id, alert_msg.id, self.tar_id, self.question.value))
            conn.commit()
            
        await interaction.followup.send("✅ Interrogation transmitted.", ephemeral=True)

# --- ADDED: FEATURE 1 - TRIBUTE/ENCRYPTION MODAL ---
class TributeModal(discord.ui.Modal, title="Secure Payload Entry"):
    tribute = discord.ui.TextInput(label="Encryption Key / Tribute", style=discord.TextStyle.paragraph, placeholder="Why should they accept? Enter your tribute here...", required=True, max_length=1000)

    def __init__(self, req_id, tar_id, intents, intent_display):
        super().__init__(custom_id=f"ask_trib_modal:{req_id}:{tar_id}")
        self.req_id = req_id
        self.tar_id = tar_id
        self.intents = intents
        self.intent_display = intent_display

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) 

        # --- FEATURE 3: DYNAMIC VISUAL CALCULATION ---
        intent_color = None
        if any(i in ["NSFW", "Flirting", "Dating vibes", "Open to Anything"] for i in self.intents):
            intent_color = "red"
        elif any(i in ["SFW", "Friends only", "Problem Solving"] for i in self.intents):
            intent_color = "cyan"

        with sqlite3.connect("dungeon_ask.db") as conn:
            conn.execute("INSERT INTO tributes VALUES (?, ?, ?)", (self.req_id, self.tar_id, self.tribute.value))
            conn.commit()

        main_mod = sys.modules.get('__main__')
        
        target_user = interaction.guild.get_member(self.tar_id)
        if not target_user:
            try:
                target_user = await interaction.guild.fetch_member(self.tar_id)
            except:
                return await interaction.followup.send("❌ Error fetching target user data.", ephemeral=True)
                
        requester_user = interaction.guild.get_member(self.req_id)
        if not requester_user:
            try:
                requester_user = await interaction.guild.fetch_member(self.req_id)
            except:
                return await interaction.followup.send("❌ Error fetching requester user data.", ephemeral=True)

        cog = interaction.client.get_cog('DungeonAsk')
        img_buf = await cog.create_dynamic_ask_lobby(requester_user.display_avatar.url, target_user.display_avatar.url, intent_color)
        file = discord.File(img_buf, filename="dynamic_ask.png")

        # --- MODIFIED: Merged Tribute into a single layout block ready to receive logs ---
        final_embed = main_mod.fiery_embed(" 📩 INCOMING DM REQUEST", 
            f"{target_user.mention}, a formal petition to enter your private space has been filed by {requester_user.mention}.\n\n"
            f"### 🫦 INTENT OF CONTACT:\n> {self.intent_display}\n\n"
            f"### 📜 SECURE PAYLOAD & LOGS\n**{requester_user.mention}:** {self.tribute.value}\n** **")
        
        final_embed.set_thumbnail(url=requester_user.display_avatar.url)
        final_embed.color = 0x00BFFF 
        final_embed.set_image(url="attachment://dynamic_ask.png")

        view = RecipientView(self.req_id, self.tar_id)
        await interaction.channel.send(content=target_user.mention, embed=final_embed, view=view, file=file)
        await interaction.followup.send("✅ Verification request dispatched successfully.", ephemeral=True)

# --- PERSISTENT VIEW CLASSES (MOVED AND DECOUPLED FOR TOTAL STABILITY) ---

class NatureSelect(discord.ui.Select):
    def __init__(self, requester_id, target_id):
        options = [
            discord.SelectOption(label="SFW", emoji="🛡️"),
            discord.SelectOption(label="NSFW", emoji="🔞"),
            discord.SelectOption(label="Flirting", emoji="🫦"),
            discord.SelectOption(label="Problem Solving", emoji="🧠"),
            discord.SelectOption(label="Casual Chat only", emoji="💬"),
            discord.SelectOption(label="Friends only", emoji="🤝"),
            discord.SelectOption(label="Dating vibes", emoji="💘"),
            discord.SelectOption(label="Open to Anything", emoji="🔞")
        ]
        # We store the IDs in the custom_id so they survive restarts
        super().__init__(placeholder="Nature of the DM (Choose up to 3)", min_values=1, max_values=3, options=options, custom_id=f"ask_sel:{requester_id}:{target_id}")

    async def callback(self, interaction: discord.Interaction):
        # Extract IDs from custom_id if memory is wiped
        _, req_id, tar_id = self.custom_id.split(':')
        req_id, tar_id = int(req_id), int(tar_id)

        if interaction.user.id != req_id:
            return await interaction.response.send_message("❌ This setup belongs to the requester.", ephemeral=True)

        main_mod = sys.modules['__main__']
        intent_display = " | ".join([f"**{val}**" for val in self.values])
        
        # --- ADDED: ROUTE THROUGH TRIBUTE MODAL ---
        await interaction.response.send_modal(TributeModal(req_id, tar_id, self.values, intent_display))

class InitialView(discord.ui.View):
    def __init__(self, requester_id=None, target_id=None):
        super().__init__(timeout=None)
        self.requester_id = requester_id
        self.target_id = target_id

    @discord.ui.button(label="Ask to DM", style=discord.ButtonStyle.primary, emoji="📩", custom_id="ask_dm_init_v3")
    async def dm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Logic to recover IDs from mentions if they aren't in memory
        try:
            req_id = self.requester_id or int(interaction.message.embeds[0].description.split('<@')[1].split('>')[0])
            tar_id = self.target_id or int(interaction.message.embeds[0].description.split('signaling <@')[1].split('>')[0])
        except: return await interaction.response.send_message("❌ Internal link broken. Use the command again.", ephemeral=True)

        if interaction.user.id != req_id: 
            return await interaction.response.send_message("❌ This is not your request, asset.", ephemeral=True)
        
        # We create a temporary view for the select menu which uses a stable custom_id
        dm_view = discord.ui.View(timeout=None)
        dm_view.add_item(NatureSelect(req_id, tar_id))
        await interaction.response.send_message("🫦 **Define the nature of your entry:**", view=dm_view, ephemeral=True)

    @discord.ui.button(label="Ask to Play", style=discord.ButtonStyle.danger, emoji="🫦", custom_id="ask_play_init_v3")
    async def play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            req_id = self.requester_id or int(interaction.message.embeds[0].description.split('<@')[1].split('>')[0])
            tar_id = self.target_id or int(interaction.message.embeds[0].description.split('signaling <@')[1].split('>')[0])
        except: return

        if interaction.user.id != req_id: 
            return await interaction.response.send_message("❌ Access denied.", ephemeral=True)
        
        main_mod = sys.modules['__main__']
        
        target_user = interaction.guild.get_member(tar_id)
        if not target_user:
            try:
                target_user = await interaction.guild.fetch_member(tar_id)
            except: return
            
        requester_user = interaction.guild.get_member(req_id)
        if not requester_user:
            try:
                requester_user = await interaction.guild.fetch_member(req_id)
            except: return

        play_embed = main_mod.fiery_embed("🔞 SEX-BOT TRIAL REQUEST 🔞", 
            f"{target_user.mention}, {requester_user.mention} wants to initiate a deep-sync session.\n\n"
            f"**Will you submit?**")
        
        view = PlayView(req_id, tar_id)
        await interaction.response.send_message(content=target_user.mention, embed=play_embed, view=view)

class RecipientView(discord.ui.View):
    def __init__(self, req_id=0, tar_id=0):
        super().__init__(timeout=None)
        self.req_id = req_id
        self.tar_id = tar_id

    # Helper execution step added directly inside to extract correct user IDs during a persistent state recovery 
    def check_permissions(self, inter: discord.Interaction):
        current_target_id = self.tar_id
        current_requester_id = self.req_id
        if current_target_id == 0 or current_requester_id == 0:
            try:
                desc = inter.message.embeds[0].description
                current_target_id = int(desc.split('<@')[1].split('>')[0])
                current_requester_id = int(desc.split('filed by <@')[1].split('>')[0])
            except:
                pass
        return current_target_id, current_requester_id

    # --- ADDED: THE INTERROGATION TRIGGER ---
    @discord.ui.button(label="👁️ Make a question first", style=discord.ButtonStyle.primary, custom_id="ask_dm_interrogate_v3")
    async def interrogate(self, inter: discord.Interaction, btn: discord.ui.Button):
        target_id, requester_id = self.check_permissions(inter)
        if inter.user.id != target_id: 
            return await inter.response.send_message("❌ Access denied. Only the target recipient can interact with these controls.", ephemeral=True)
        
        await inter.open_modal(InterrogateModal(requester_id, target_id, inter.message.id))

    @discord.ui.button(label="Accept DM", style=discord.ButtonStyle.success, emoji="🫦", custom_id="ask_dm_accept_v3")
    async def accept(self, inter: discord.Interaction, btn: discord.ui.Button):
        target_id, requester_id = self.check_permissions(inter)
        if inter.user.id != target_id: 
            return await inter.response.send_message("❌ Access denied. Only the target recipient can interact with these controls.", ephemeral=True)
        
        main_mod = sys.modules['__main__']
        
        success_emb = main_mod.fiery_embed("💖 DM ACCEPTED", f"**ACCEPTED.** The request was accepted by {inter.user.mention}.")
        await inter.response.send_message(embed=success_emb)

    @discord.ui.button(label="Reject DM request", style=discord.ButtonStyle.danger, emoji="❌", custom_id="ask_dm_reject_v3")
    async def deny(self, inter: discord.Interaction, btn: discord.ui.Button):
        target_id, requester_id = self.check_permissions(inter)
        if inter.user.id != target_id: 
            return await inter.response.send_message("❌ Access denied. Only the target recipient can interact with these controls.", ephemeral=True)
            
        main_mod = sys.modules['__main__']
        fail_emb = main_mod.fiery_embed("❌ REQUEST DENIED", f"**DENIED.** {inter.user.mention} has rejected the request.")
        await inter.response.send_message(embed=fail_emb)

class PlayView(discord.ui.View):
    def __init__(self, req_id=0, tar_id=0):
        super().__init__(timeout=None)
        self.req_id = req_id
        self.tar_id = tar_id

    # Helper execution step added directly inside to extract correct user IDs during a persistent state recovery 
    def check_permissions(self, inter: discord.Interaction):
        current_target_id = self.tar_id
        if current_target_id == 0:
            try:
                desc = inter.message.embeds[0].description
                current_target_id = int(desc.split('<@')[1].split('>')[0])
            except:
                pass
        return current_target_id

    @discord.ui.button(label="Accept Sync", style=discord.ButtonStyle.success, emoji="🔥", custom_id="ask_play_accept_v3")
    async def accept_play(self, inter: discord.Interaction, btn: discord.ui.Button):
        target_id = self.check_permissions(inter)
        if inter.user.id != target_id:
            return await inter.response.send_message("❌ Access denied. Only the target recipient can interact with these controls.", ephemeral=True)
        await inter.response.send_message(f"🔞 **SYNC INITIALIZED.** {inter.user.mention} is ready.")

    @discord.ui.button(label="Abort Sync", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="ask_play_deny_v3")
    async def deny_play(self, inter: discord.Interaction, btn: discord.ui.Button):
        target_id = self.check_permissions(inter)
        if inter.user.id != target_id:
            return await inter.response.send_message("❌ Access denied. Only the target recipient can interact with these controls.", ephemeral=True)
        await inter.response.send_message(f"🔒 **SYNC ABORTED.** {inter.user.mention} has locked their gate.")

# --- COG CLASS ---

class DungeonAsk(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.AUDIT_CHANNEL_ID = getattr(sys.modules['__main__'], "AUDIT_CHANNEL_ID", 1482071248631758865)

    async def create_ask_lobby(self, u1_url, u2_url, title="DM REQUEST"):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(u1_url) as r1, session.get(u2_url) as r2:
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())

            def process():
                canvas_width, canvas_height = 1200, 600
                canvas = Image.open("askdm.jpg").convert("RGBA").resize((canvas_width, canvas_height)) if os.path.exists("askdm.jpg") else Image.new("RGBA", (canvas_width, canvas_height), (15, 0, 8, 255))
                draw = ImageDraw.Draw(canvas)
                av_size = 350
                av1 = Image.open(p1_data).convert("RGBA").resize((av_size, av_size))
                av2 = Image.open(p2_data).convert("RGBA").resize((av_size, av_size))
                canvas.paste(av1, (100, 120), av1)
                canvas.paste(av2, (750, 120), av2)
                buf = io.BytesIO()
                canvas.save(buf, format="PNG")
                buf.seek(0)
                return buf
            
            return await asyncio.to_thread(process)
        except Exception as e:
            print(f"Visual Error: {e}")
            return None

    # --- ADDED: FEATURE 3 - DYNAMIC SMART CANVAS (Color Grading) ---
    async def create_dynamic_ask_lobby(self, u1_url, u2_url, intent_color=None):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(u1_url) as r1, session.get(u2_url) as r2:
                    p1_data = io.BytesIO(await r1.read())
                    p2_data = io.BytesIO(await r2.read())

            def process():
                canvas_width, canvas_height = 1200, 600
                canvas = Image.open("askdm.jpg").convert("RGBA").resize((canvas_width, canvas_height)) if os.path.exists("askdm.jpg") else Image.new("RGBA", (canvas_width, canvas_height), (15, 0, 8, 255))
                av_size = 350
                av1 = Image.open(p1_data).convert("RGBA").resize((av_size, av_size))
                av2 = Image.open(p2_data).convert("RGBA").resize((av_size, av_size))
                
                canvas.paste(av1, (100, 120), av1)
                canvas.paste(av2, (750, 120), av2)

                if intent_color:
                    overlay = Image.new("RGBA", canvas.size, (255, 0, 0, 80) if intent_color == "red" else (0, 255, 255, 80))
                    canvas = Image.alpha_composite(canvas, overlay)
                    
                    vignette = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
                    draw = ImageDraw.Draw(vignette)
                    draw.rectangle([0, 0, canvas_width, canvas_height], fill=None, outline=(0, 0, 0, 200), width=40)
                    canvas = Image.alpha_composite(canvas, vignette)

                buf = io.BytesIO()
                canvas.save(buf, format="PNG")
                buf.seek(0)
                return buf
            
            return await asyncio.to_thread(process)
        except Exception as e:
            print(f"Visual Error: {e}")
            return None

    # --- ADDED: CONFIGURATION COMMAND GROUP FOR SYSTEM SETUP ---
    @commands.group(name="askadmin", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def askadmin(self, ctx):
        await ctx.send("ℹ️ **Usage:** `!askadmin channel #channel` or `!askadmin role @role`")

    @askadmin.command(name="channel")
    @commands.has_permissions(administrator=True)
    async def askadmin_channel(self, ctx, channel: discord.TextChannel):
        with sqlite3.connect("dungeon_ask.db") as conn:
            conn.execute("INSERT INTO config (guild_id, channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id", (ctx.guild.id, channel.id))
            conn.commit()
        save_backup_config(ctx.guild.id, channel_id=channel.id)
        await ctx.send(f"✅ **Admin Reporting Channel locked to:** {channel.mention}")

    @askadmin.command(name="role")
    @commands.has_permissions(administrator=True)
    async def askadmin_role(self, ctx, role: discord.Role):
        with sqlite3.connect("dungeon_ask.db") as conn:
            conn.execute("INSERT INTO config (guild_id, role_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET role_id=excluded.role_id", (ctx.guild.id, role.id))
            conn.commit()
        save_backup_config(ctx.guild.id, role_id=role.id)
        await ctx.send(f"✅ **Admin Notification Role locked to:** {role.mention}")

    @commands.command(name="ask")
    async def ask(self, ctx, member: discord.Member):
        if member.id == ctx.author.id:
            return await ctx.send("❌ You can't ask to DM yourself.")

        # --- ADDED: SECURITY GATE FOR CLOSED ROLES ---
        has_closed_role = False
        blocked_by_role_name = ""
        for role in member.roles:
            if "closed" in role.name.lower():
                has_closed_role = True
                blocked_by_role_name = role.name
                break

        if has_closed_role:
            block_msg = await ctx.send(f"❌ Request blocked. {member.mention} currently has private gates closed.")
            
            # --- ADDED: FANCY REPORT DISPATCH TO ADMIN CHANNEL ---
            try:
                with sqlite3.connect("dungeon_ask.db") as conn:
                    row = conn.execute("SELECT channel_id, role_id FROM config WHERE guild_id=?", (ctx.guild.id,)).fetchone()
                
                # If database was wiped on deploy, restore it using backup config values
                if not row:
                    backup = load_backup_config(ctx.guild.id)
                    if backup:
                        target_channel_id = backup.get("channel_id")
                        ping_role_id = backup.get("role_id")
                        with sqlite3.connect("dungeon_ask.db") as conn:
                            conn.execute("INSERT INTO config (guild_id, channel_id, role_id) VALUES (?, ?, ?)", (ctx.guild.id, target_channel_id, ping_role_id))
                            conn.commit()
                        row = (target_channel_id, ping_role_id)

                if row:
                    target_channel_id, ping_role_id = row
                    report_channel = ctx.guild.get_channel(target_channel_id)
                    
                    if report_channel:
                        main_mod = sys.modules['__main__']
                        
                        # Generating the highly detailed tracking embed
                        report_embed = main_mod.fiery_embed("🚨 BLOCKED TRANSMISSION ATTEMPT", 
                            f"An initial DM request handshake was auto-terminated due to user role locks.\n\n"
                            f"### ⚔️ INTERCEPT SUMMARY:\n"
                            f"* **Initiator Asset:** {ctx.author.mention} (`{ctx.author.id}`)\n"
                            f"* **Target Target:** {member.mention} (`{member.id}`)\n"
                            f"* **Active Gate Block:** `{blocked_by_role_name}`\n\n"
                            f"### 🗓️ TIMESTAMP OF INCIDENT:\n> <t:{int(datetime.now(timezone.utc).timestamp())}:F>")
                        
                        report_embed.set_thumbnail(url=ctx.author.display_avatar.url)
                        report_embed.color = 0xFF0000
                        
                        ping_content = ""
                        if ping_role_id:
                            ping_content = f"<@&{ping_role_id}>"
                            
                        await report_channel.send(content=ping_content, embed=report_embed)
            except Exception as report_error:
                print(f"Logging System Incident Failure: {report_error}")

            await asyncio.sleep(10)
            try:
                await block_msg.delete()
                await ctx.message.delete()
            except:
                pass
            return

        main_mod = sys.modules['__main__']
        img = await self.create_ask_lobby(ctx.author.display_avatar.url, member.display_avatar.url, "")
        file = discord.File(img, filename="ask.png")
        
        embed = main_mod.fiery_embed("🔞 ASK TO DM ALERT 🔞", 
            f"{ctx.author.mention} is signaling {member.mention}.\n\n"
            f"**Select the nature of your request below:**")
        embed.set_image(url="attachment://ask.png")
        
        view = InitialView(ctx.author.id, member.id)
        await ctx.send(file=file, embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(DungeonAsk(bot))
    # Register views for persistence after setup
    bot.add_view(InitialView())
    bot.add_view(RecipientView())
    bot.add_view(PlayView())
    bot.add_view(AnswerView()) # ADDED: Ensure Answer Phase is fully persistent
    print("✅ LOG: Ask Extension is ONLINE (V3 Persistence with Dynamic Protocols).")
