import discord
from discord.ext import commands
import sqlite3
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
import asyncio
import aiohttp
from aiohttp import web

# --- PAYPAL CONFIGURATION (AUTOMATIC WEBHOOK INTEGRATION) ---
PAYPAL_EMAIL = os.getenv("PAYPAL_EMAIL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
CURRENCY = "USD"

# --- RECONFIGURED ELITE PLANS (MULTI-PACK MARKETING TIERS) ---
PREMIUM_PLANS = {
    "Server Premium": {"cost": 15.0, "perks": "Full Server-Wide Unlock (30 Days)", "color": 0xFFD700, "duration": 30},
    "Server Premium (3 Months)": {"cost": 40.0, "perks": "Full Server-Wide Unlock (90 Days) - 💥 SAVE $5", "color": 0xFFD700, "duration": 90},
    "Server Premium (6 Months)": {"cost": 70.0, "perks": "Full Server-Wide Unlock (180 Days) - 🔥 SAVE $20", "color": 0xFFD700, "duration": 180},
    "Server Premium (1 Year)": {"cost": 128.0, "perks": "Full Server-Wide Unlock (365 Days) - 🌟 BEST VALUE (SAVE $52)", "color": 0xFFD700, "duration": 365}
}

class PremiumShopView(discord.ui.View):
    def __init__(self, ctx, get_db_connection, fiery_embed, update_user_stats):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.get_db_connection = get_db_connection
        self.fiery_embed = fiery_embed
        self.update_user_stats = update_user_stats
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        for key in PREMIUM_PLANS.keys():
            # Format button labels for better UI
            if "3 Months" in key:
                btn_label = "BUY 3 MONTHS"
                btn_style = discord.ButtonStyle.success
            elif "6 Months" in key:
                btn_label = "BUY 6 MONTHS"
                btn_style = discord.ButtonStyle.success
            elif "1 Year" in key:
                btn_label = "BUY 1 YEAR"
                btn_style = discord.ButtonStyle.primary # Highlight the best value
            else:
                btn_label = "BUY 1 MONTH"
                btn_style = discord.ButtonStyle.secondary

            button = discord.ui.Button(
                label=btn_label, 
                style=btn_style,
                custom_id=f"buy_{key.replace(' ', '_').replace('(', '').replace(')', '')}"
            )
            button.callback = self.make_callback(key)
            self.add_item(button)

    def make_callback(self, plan_name):
        async def callback(interaction: discord.Interaction):
            await self.process_purchase(interaction, plan_name)
        return callback

    def create_embed(self):
        desc = "### 🛡️ ELITE SERVER UNLOCK 🛡️\n"
        desc += "*Unlock full premium privileges for your entire server. Choose your term below:*\n\n"
        
        for key, plan in PREMIUM_PLANS.items():
            desc += f"➤ **PLAN:** {key}\n"
            desc += f"➤ **PRICE:** ${plan['cost']:,.2f} USD\n"
            desc += f"✨ **PRIVILEGES:** `{plan['perks']}`\n\n"
        
        embed = self.fiery_embed("PREMIUM GATEWAY", desc)
        embed.set_author(name="THE MASTER'S EXECUTIVE BOUTIQUE", icon_url=self.ctx.author.display_avatar.url)
        return embed

    async def send_audit_report(self, interaction, plan_name, cost, action="INVOICE GENERATED"):
        main_mod = sys.modules['__main__']
        audit_id = getattr(main_mod, "AUDIT_CHANNEL_ID", 1438810509322223677)
        channel = interaction.client.get_channel(audit_id)
        if channel:
            audit_emb = self.fiery_embed("🛒 MARKET TRANSACTION LOG", 
                f"**Action:** `{action}`\n"
                f"**Asset:** {interaction.user.mention}\n"
                f"**Server:** `{interaction.guild.name}`\n"
                f"**Plan:** `{plan_name}`\n"
                f"**Value:** `${cost} USD`", color=0xF1C40F)
            if os.path.exists("LobbyTopRight.jpg"):
                file = discord.File("LobbyTopRight.jpg", filename="audit_premium.jpg")
                audit_emb.set_thumbnail(url="attachment://audit_premium.jpg")
                await channel.send(file=file, embed=audit_emb)
            else:
                await channel.send(embed=audit_emb)

    async def process_purchase(self, interaction, plan_name):
        plan = PREMIUM_PLANS[plan_name]
        duration = plan.get("duration", 30)
        custom_data = f"G{interaction.guild.id}|{plan_name}|{duration}"
        query = {
            "business": PAYPAL_EMAIL,
            "cmd": "_xclick",
            "amount": plan['cost'],
            "currency_code": CURRENCY,
            "item_name": f"Server Premium: {plan_name} (Guild: {interaction.guild.id})",
            "custom": custom_data,
            "notify_url": WEBHOOK_URL, 
            "no_shipping": "1",
            "return": "https://discord.com"
        }
        paypal_url = f"https://www.paypal.com/cgi-bin/webscr?{urllib.parse.urlencode(query)}"

        embed = self.fiery_embed("INVOICE GENERATED │ SECURE CHECKOUT", 
                                f"🔞 **Server:** {interaction.guild.name}\n"
                                f"💎 **Plan:** `{plan_name}`\n"
                                f"💵 **Total:** `${plan['cost']} USD`\n\n"
                                f"✅ [CLICK HERE TO FINALIZE ON PAYPAL]({paypal_url})\n\n"
                                f"⏳ *The system will unlock {duration} days of premium for this server upon payment.*")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.send_audit_report(interaction, plan_name, plan['cost'])

class PremiumSystem(commands.Cog):
    def __init__(self, bot, get_db_connection, fiery_embed, update_user_stats):
        self.bot = bot
        self.get_db_connection = get_db_connection
        self.fiery_embed = fiery_embed
        self.update_user_stats = update_user_stats
        self.AUDIT_CHANNEL_ID = getattr(sys.modules['__main__'], "AUDIT_CHANNEL_ID", 1438810509322223677)
        self.webhook_task = self.bot.loop.create_task(self.start_webhook_server())
        
        # --- ADDED: BACKGROUND TASK FOR FREE TRIAL EXPIRATIONS ---
        self.trial_expiration_task = self.bot.loop.create_task(self.check_trial_expirations())
        
        # --- START ADDITION: BACKGROUND TASK FOR PAID EXPIRATIONS ---
        self.paid_expiration_task = self.bot.loop.create_task(self.check_paid_expirations())
        # --- END ADDITION ---

        # --- ADDED: GLOBAL PREMIUM COMMAND LIST ---
        self.premium_commands = [
            "setadminrole", "audit", "collectadmin", "setcards", "setconfessreview", 
            "setconfesspost", "setconfesspost2", "confesspanel", "setcounting", 
            "set_ignis_admin", "setlevelchannel", "react", "achievements", "balance", 
            "ranking", "hall", "streaks", "quests", "ask", "dice", "blackjack", 
            "roulette", "slots", "stealemoji", "echopurge", "limit", "echostart", 
            "autorole", "setroles", "ticket", "match3some", "flirtyship", "matchme", 
            "matchmaking", "thread", "threadall", "math"
        ]
        self.bot.add_check(self.global_premium_interceptor)
        
        # --- START ADDITION: SLASH COMMAND TREE REGISTRATION ---
        self.bot.tree.interaction_check = self.global_slash_premium_interceptor
        # --- END ADDITION ---

    def cog_unload(self):
        # Cleanly remove the check if the cog is ever reloaded or unloaded
        self.bot.remove_check(self.global_premium_interceptor)
        
        # --- ADDED: CANCEL TRIAL TASK ON UNLOAD ---
        self.trial_expiration_task.cancel()
        
        # --- START ADDITION: CANCEL PAID EXPIRATION TASK ---
        self.paid_expiration_task.cancel()
        # --- END ADDITION ---

    async def check_trial_expirations(self):
        """Background loop to check and remove expired free trials."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                with self.get_db_connection() as conn:
                    now_str = datetime.now().isoformat()
                    expired_trials = conn.execute("SELECT guild_id FROM free_trial_usage WHERE expires_at <= ? AND expires_at IS NOT NULL", (now_str,)).fetchall()
                    
                    for row in expired_trials:
                        g_id = row['guild_id']
                        
                        # Ensure we only remove it if they are still on the trial plan
                        serv = conn.execute("SELECT premium_type FROM server_premium WHERE guild_id = ?", (g_id,)).fetchone()
                        if serv and serv['premium_type'] == '10-Day Free Trial':
                            conn.execute("DELETE FROM server_premium WHERE guild_id = ?", (g_id,))
                        
                        # Mark as expired but keep the record so they can't claim again
                        conn.execute("UPDATE free_trial_usage SET expires_at = NULL WHERE guild_id = ?", (g_id,))
                    
                    if expired_trials:
                        conn.commit()
            except Exception as e:
                print(f"[PremiumSystem] Error in check_trial_expirations: {e}")
            
            await asyncio.sleep(3600)  # Check every hour

    # --- START ADDITION: PAID PLAN EXPIRATIONS LOOP ---
    async def check_paid_expirations(self):
        """Background loop to check and remove expired paid premium plans."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                with self.get_db_connection() as conn:
                    now_str = datetime.now().isoformat()
                    expired_plans = conn.execute("SELECT guild_id FROM server_premium WHERE expires_at <= ? AND expires_at IS NOT NULL AND premium_type != '10-Day Free Trial'", (now_str,)).fetchall()
                    
                    for row in expired_plans:
                        g_id = row['guild_id']
                        conn.execute("DELETE FROM server_premium WHERE guild_id = ?", (g_id,))
                    
                    if expired_plans:
                        conn.commit()
            except Exception as e:
                print(f"[PremiumSystem] Error in check_paid_expirations: {e}")
            
            await asyncio.sleep(3600)  # Check every hour
    # --- END ADDITION ---

    async def global_premium_interceptor(self, ctx):
        """Intercepts all commands and blocks execution if they are on the premium list and the server is not premium."""
        # --- START ADDITION: SUBCOMMAND PROTECTION ---
        if ctx.command and hasattr(ctx.command, "root_parent") and ctx.command.root_parent:
            if ctx.command.root_parent.name in self.premium_commands:
                if ctx.command.name not in self.premium_commands:
                    self.premium_commands.append(ctx.command.name)
        # --- END ADDITION ---
        
        if not ctx.command:
            return True
            
        if ctx.command.name in self.premium_commands:
            if ctx.guild is None:
                await ctx.send("❌ This command must be used in a server.")
                return False
                
            main = sys.modules['__main__']
            with self.get_db_connection() as conn:
                serv = conn.execute("SELECT premium_type FROM server_premium WHERE guild_id = ?", (ctx.guild.id,)).fetchone()
            
            if serv and serv['premium_type'] not in ['Free', '', None]:
                return True
                
            embed = main.fiery_embed("ACCESS DENIED", "❌ This command requires an active **Server Premium** subscription.\nType `!premium` to unlock all features for this server.\n\n*Server Owners can also try `!freetrial` once per server!*")
            if os.path.exists("LobbyTopRight.jpg"):
                file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
                await ctx.send(file=file, embed=embed)
            else:
                await ctx.send(embed=embed)
            return False
            
        return True

    # --- START ADDITION: SLASH COMMAND INTERCEPTOR ---
    async def global_slash_premium_interceptor(self, interaction: discord.Interaction):
        if not interaction.command: 
            return True
            
        cmd_name = interaction.command.name
        if hasattr(interaction.command, "parent") and interaction.command.parent:
            cmd_name = interaction.command.parent.name

        if cmd_name in self.premium_commands:
            if interaction.guild is None:
                await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
                return False

            main = sys.modules['__main__']
            with self.get_db_connection() as conn:
                serv = conn.execute("SELECT premium_type FROM server_premium WHERE guild_id = ?", (interaction.guild.id,)).fetchone()

            if serv and serv['premium_type'] not in ['Free', '', None]:
                return True

            embed = main.fiery_embed("ACCESS DENIED", "❌ This command requires an active **Server Premium** subscription.\nType `/premium` to unlock.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
            
        return True
    # --- END ADDITION ---

    async def start_webhook_server(self):
        app = web.Application()
        app.router.add_post('/webhook', self.handle_paypal_webhook)
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()

    async def handle_paypal_webhook(self, request):
        data = await request.post()
        
        # --- START ADDITION: PAYPAL IPN SECURITY VERIFICATION ---
        verify_payload = dict(data)
        verify_payload['cmd'] = '_notify-validate'
        paypal_url = "https://ipnpb.paypal.com/cgi-bin/webscr"
        async with aiohttp.ClientSession() as session:
            async with session.post(paypal_url, data=verify_payload) as resp:
                verification_text = await resp.text()
                if verification_text != "VERIFIED":
                    print(f"[SECURITY] Blocked fake premium webhook attempt: {verification_text}")
                    return web.Response(status=403, text="Forbidden")
        # --- END ADDITION ---

        if data.get('payment_status') == 'Completed':
            custom = data.get('custom', '')
            if custom.startswith('G'):
                parts = custom[1:].split('|')
                if len(parts) >= 2:
                    guild_id = int(parts[0])
                    plan_name = parts[1]
                    p_date = datetime.now().isoformat()
                    with self.get_db_connection() as conn:
                        conn.execute("INSERT OR REPLACE INTO server_premium (guild_id, premium_type, premium_date) VALUES (?, ?, ?)",
                                     (guild_id, plan_name, p_date))
                        
                        # --- START ADDITION: PAID PLAN EXPIRATION SAVE ---
                        duration = int(parts[2]) if len(parts) > 2 else 30
                        expires_at = (datetime.now() + timedelta(days=duration)).isoformat()
                        conn.execute("UPDATE server_premium SET expires_at = ? WHERE guild_id = ?", (expires_at, guild_id))
                        # --- END ADDITION ---
                        
                        conn.commit()
                await self.log_admin_action(f"Guild ID: {guild_id}", plan_name, "AUTOMATIC WEBHOOK ACTIVATION")
        return web.Response(text="OK")

    async def log_admin_action(self, guild_name, plan_name, action):
        audit_id = getattr(sys.modules['__main__'], "AUDIT_CHANNEL_ID", self.AUDIT_CHANNEL_ID)
        channel = self.bot.get_channel(audit_id)
        if channel:
            embed = self.fiery_embed("⚖️ ADMINISTRATIVE SERVER OVERRIDE", 
                f"**Action:** `{action}`\n"
                f"**Server:** `{guild_name}`\n"
                f"**Plan Details:** `{plan_name}`", color=0xE74C3C)
            await channel.send(embed=embed)

    @commands.command(name="premium")
    async def premium_shop(self, ctx):
        view = PremiumShopView(ctx, self.get_db_connection, self.fiery_embed, self.update_user_stats)
        embed = view.create_embed()
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="premium.jpg")
            embed.set_image(url="attachment://premium.jpg")
            await ctx.send(file=file, embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    # --- ADDED: FREE TRIAL COMMAND ---
    @commands.command(name="freetrial")
    async def free_trial(self, ctx):
        """Activates a one-time 10-day free premium trial for the server."""
        if ctx.guild is None:
            return await ctx.send("❌ This command must be used in a server.")
            
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send(embed=self.fiery_embed("ACCESS DENIED", "❌ Only the server owner can activate the free trial.", color=0xFF0000))

        with self.get_db_connection() as conn:
            # Check if trial was already used
            used = conn.execute("SELECT * FROM free_trial_usage WHERE guild_id = ?", (ctx.guild.id,)).fetchone()
            
            if used:
                return await ctx.send(embed=self.fiery_embed("TRIAL UNAVAILABLE", "❌ This server has already claimed its lifetime one-time 10-day free trial.", color=0xFF0000))
            
            # Check if server is already premium
            serv = conn.execute("SELECT premium_type FROM server_premium WHERE guild_id = ?", (ctx.guild.id,)).fetchone()
            if serv and serv['premium_type'] not in ['Free', '', None]:
                return await ctx.send(embed=self.fiery_embed("ALREADY PREMIUM", f"❌ This server already has an active premium subscription: **{serv['premium_type']}**.", color=0xFF0000))

            # Activate the trial
            now = datetime.now()
            expires_at = now + timedelta(days=10)
            
            # Log usage permanently
            conn.execute("INSERT INTO free_trial_usage (guild_id, used_date, expires_at) VALUES (?, ?, ?)", 
                         (ctx.guild.id, now.isoformat(), expires_at.isoformat()))
            
            # Add to premium table
            conn.execute("INSERT OR REPLACE INTO server_premium (guild_id, premium_type, premium_date) VALUES (?, ?, ?)",
                         (ctx.guild.id, '10-Day Free Trial', now.isoformat()))
            
            # --- START ADDITION: ENSURE EXPIRATION COLUMN POPULATED FOR TRIAL ---
            conn.execute("UPDATE server_premium SET expires_at = ? WHERE guild_id = ?", (expires_at.isoformat(), ctx.guild.id))
            # --- END ADDITION ---
            conn.commit()

        embed = self.fiery_embed("FREE TRIAL ACTIVATED", 
                                 f"✅ **{ctx.guild.name}** has been granted a 10-Day Free Trial of Server Premium!\n\n"
                                 f"⏳ **Expires On:** `{expires_at.strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                                 f"All elite features are now unlocked for everyone in the server.", color=0x00FF00)
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="trial.jpg")
            embed.set_thumbnail(url="attachment://trial.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)
            
        await self.log_admin_action(ctx.guild.name, "10-Day Free Trial", "FREE TRIAL CLAIMED")

    @commands.command(name="activate")
    @commands.is_owner()
    @commands.has_permissions(administrator=True)
    async def activate_premium(self, ctx, guild_id: int):
        plan_name = "Server Premium"
        p_date = datetime.now().isoformat()
        
        with self.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO server_premium (guild_id, premium_type, premium_date) VALUES (?, ?, ?)",
                         (guild_id, plan_name, p_date))
            conn.commit()
            
        await ctx.send(embed=self.fiery_embed("SERVER PREMIUM ACTIVATED", f"✅ Guild `{guild_id}` elevated to **{plan_name}**.", color=0x00FF00))
        await self.log_admin_action(f"Guild ID: {guild_id}", plan_name, "MANUAL SERVER ACTIVATION")

    @commands.command(name="testpay")
    @commands.is_owner()
    @commands.has_permissions(administrator=True)
    async def test_payment(self, ctx):
        plan_name = "Server Premium"
        payload = {'payment_status': 'Completed', 'custom': f"G{ctx.guild.id}|{plan_name}|30"}
        
        port = os.environ.get("PORT", "8080")
        urls = [f"http://127.0.0.1:{port}/webhook", WEBHOOK_URL]

        async with aiohttp.ClientSession() as session:
            for url in urls:
                if not url: continue
                try:
                    async with session.post(url, data=payload, timeout=5) as resp:
                        if resp.status == 200:
                            return await ctx.send(f"✅ **Success via {url}!**\nPremium active for entire server: **{plan_name}**.")
                except Exception:
                    continue
        
        await ctx.send("❌ **Test Failed.**")

    @commands.command(name="premiumstats")
    async def premium_stats(self, ctx):
        with self.get_db_connection() as conn:
            stats = conn.execute("SELECT premium_type, COUNT(*) as count FROM server_premium GROUP BY premium_type").fetchall()
        desc = "📉 **SERVER MARKET DISTRIBUTION**\n\n"
        for row in stats:
            p_type = row['premium_type'] or "Standard"
            desc += f"• **{p_type}:** {row['count']} Servers\n"
        await ctx.send(embed=self.fiery_embed("GLOBAL SERVER ASSET RECAP", desc, color=0x00FFFF))

    @commands.command(name="premiumstatus")
    async def premium_status(self, ctx):
        with self.get_db_connection() as conn:
            s = conn.execute("SELECT premium_type, premium_date FROM server_premium WHERE guild_id = ?", (ctx.guild.id,)).fetchone()
        
        if not s or s['premium_type'] in ['Free', '', None]:
            return await ctx.send(embed=self.fiery_embed("SERVER ASSET SEARCH", f"⛓️ {ctx.guild.name} is currently restricted to **Standard Access**.", color=0x808080))
        
        desc = f"### 💎 ELITE SERVER OVERVIEW: {ctx.guild.name.upper()} 💎\n"
        desc += f"*Verification confirmed. Server-wide access granted.*\n\n"
        desc += f"➤ **PLAN:** `{s['premium_type']}`\n"
        desc += f"➤ **SYNC DATE:** `{s['premium_date']}`\n\n"
        desc += "*Every member in this server now holds Elite Privileges.*"

        embed = self.fiery_embed("PRIVATE SERVER OVERVIEW", desc, color=0xFFD700)
        await ctx.send(embed=embed)

    @commands.command(name="checkservers")
    @commands.is_owner()
    async def check_servers(self, ctx):
        # Adding database connection to check premium status per server
        with self.get_db_connection() as conn:
            premium_data = {row['guild_id']: row['premium_type'] for row in conn.execute("SELECT guild_id, premium_type FROM server_premium").fetchall()}
        
        total_users = sum([g.member_count for g in self.bot.guilds if hasattr(g, 'member_count') and g.member_count])
        server_count = len(self.bot.guilds)
        
        desc = f"### ❖ O.R.I.O.N. NETWORK INTERFACE v2030 ❖\n"
        desc += f"**SYSTEM UPLINK ESTABLISHED**\n"
        desc += f"➤ **CONNECTED NODES:** `{server_count}`\n"
        desc += f"➤ **TOTAL USER ENTITIES:** `{total_users:,}`\n"
        desc += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        guild_chunks_data = []
        current_chunk_text = desc
        current_view = discord.ui.View(timeout=None)
        button_count = 0

        for g in self.bot.guilds:
            p_type = premium_data.get(g.id, "Standard Access")
            icon = "💎" if "Premium" in p_type or "Trial" in p_type else "📡"
            mem_count = g.member_count if hasattr(g, 'member_count') else "N/A"
            
            # --- START INVITE LINK GENERATION LOGIC ---
            invite_url = None
            channels_to_try = []
            if g.system_channel:
                channels_to_try.append(g.system_channel)
            channels_to_try.extend([c for c in g.text_channels if c != g.system_channel])
            
            for channel in channels_to_try:
                perms = channel.permissions_for(g.me)
                if perms.create_instant_invite:
                    try:
                        invite = await channel.create_invite(max_age=300, max_uses=1, reason="Owner server audit link.")
                        invite_url = invite.url
                        break
                    except Exception:
                        continue
            # --- END INVITE LINK GENERATION LOGIC ---

            entry = (
                f"{icon} **{g.name.upper()}**\n"
                f"└─ 🆔 `ID: {g.id}`\n"
                f"└─ 👥 `Population: {mem_count}`\n"
                f"└─ 🔐 `Clearance: {p_type}`\n"
            )

            # Check if adding this entry or an additional button exceeds Discord component layout thresholds (Max 5 per row, max 25 total)
            if len(current_chunk_text) + len(entry) + 5 > 4000 or button_count >= 20:
                guild_chunks_data.append((current_chunk_text, current_view))
                current_chunk_text = entry + "\n"
                current_view = discord.ui.View(timeout=None)
                button_count = 0
            else:
                current_chunk_text += entry + "\n"

            # If an invite link was retrieved successfully, create an actual clickable Link Button
            if invite_url:
                # Truncate guild name to fit within button bounds cleanly if needed
                btn_name = g.name if len(g.name) <= 15 else f"{g.name[:12]}..."
                current_view.add_item(discord.ui.Button(label=f"Join {btn_name.upper()}", url=invite_url, style=discord.ButtonStyle.link))
                button_count += 1
        
        if current_chunk_text:
            guild_chunks_data.append((current_chunk_text, current_view))
        
        for i, (chunk, view) in enumerate(guild_chunks_data):
            title = "🌐 GLOBAL SERVER DIRECTORY" if i == 0 else "🌐 GLOBAL SERVER DIRECTORY (CONT.)"
            embed = self.fiery_embed(title, chunk)
            embed.color = 0x00FFCC # Cyan / Futuristic
            embed.set_footer(text=f"PAGE {i+1}/{len(guild_chunks_data)} • YEAR 2030 SECURE PROTOCOL")
            
            # Send view only if clickable join buttons exist for this chunk page
            if len(view.children) > 0:
                await ctx.send(embed=embed, view=view)
            else:
                await ctx.send(embed=embed)

    @commands.command(name="echoon")
    @commands.is_owner()
    async def echo_on(self, ctx):
        p_date = datetime.now().isoformat()
        with self.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO server_premium (guild_id, premium_type, premium_date) VALUES (?, ?, ?)", 
                         (ctx.guild.id, 'Server Premium', p_date))
            conn.commit()
        await ctx.send(embed=self.fiery_embed("PROTOCOL: SERVER OVERRIDE", f"👑 {ctx.guild.name} ELEVATED TO GOD MODE.", color=0xFFD700))

    @commands.command(name="echooff")
    @commands.is_owner()
    async def echo_off(self, ctx):
        with self.get_db_connection() as conn:
            conn.execute("DELETE FROM server_premium WHERE guild_id = ?", (ctx.guild.id,))
            conn.commit()
        await ctx.send(embed=self.fiery_embed("PROTOCOL: SYSTEM PURGE", f"🌑 {ctx.guild.name} RESET TO STANDARD ACCESS.", color=0x808080))

    @commands.command(name="echooffall")
    @commands.is_owner()
    async def echo_off_all(self, ctx):
        with self.get_db_connection() as conn:
            conn.execute("DELETE FROM server_premium")
            conn.commit()
        await ctx.send(embed=self.fiery_embed("PROTOCOL: GLOBAL SYSTEM PURGE", "🌑 ALL SERVERS RESET TO STANDARD ACCESS.", color=0x808080))

    @staticmethod
    def is_premium():
        async def predicate(ctx):
            main = sys.modules['__main__']
            with main.get_db_connection() as conn:
                serv = conn.execute("SELECT premium_type FROM server_premium WHERE guild_id = ?", (ctx.guild.id,)).fetchone()
            
            if serv and serv['premium_type'] not in ['Free', '']:
                return True
            await ctx.send(embed=main.fiery_embed("ACCESS DENIED", "❌ Server-Wide Premium Required."))
            return False
        return commands.check(predicate)

async def setup(bot):
    import sys
    main = sys.modules['__main__']
    with main.get_db_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS server_premium (guild_id INTEGER PRIMARY KEY, premium_type TEXT, premium_date TEXT)")
        
        # --- START ADDITION: ADD EXPIRES_AT COLUMN SAFELY ---
        try:
            conn.execute("ALTER TABLE server_premium ADD COLUMN expires_at TEXT")
        except sqlite3.OperationalError:
            pass # Column already exists
        # --- END ADDITION ---

        # --- ADDED: FREE TRIAL TRACKING TABLE ---
        conn.execute("CREATE TABLE IF NOT EXISTS free_trial_usage (guild_id INTEGER PRIMARY KEY, used_date TEXT, expires_at TEXT)")
        conn.commit()
    await bot.add_cog(PremiumSystem(bot, main.get_db_connection, main.fiery_embed, main.update_user_stats_async))
