import discord
from discord.ext import commands
import sqlite3
import os
import sys
import urllib.parse  # ADDED: To generate secure payment links
from datetime import datetime, timedelta, timezone
import asyncio
import aiohttp # ADDED: For more stable asynchronous requests

# --- PAYPAL CONFIGURATION (AUTOMATIC WEBHOOK INTEGRATION) ---
PAYPAL_EMAIL = os.getenv("PAYPAL_EMAIL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
CURRENCY = "USD"

# --- RECONFIGURED ELITE PLANS (MAX 10 - ABSOLUTELY SYNCED) ---
PREMIUM_PLANS = {
    "1. Starter Core": {"cost": 5.5, "perks": "Classes + Economy + Shop", "color": 0x3498DB},
    "2. Combatant": {"cost": 5.0, "perks": "Echo HangryGames + 1v1 Arena", "color": 0xE74C3C},
    "3. High Roller": {"cost": 4.5, "perks": "Casino + Economy Expansion", "color": 0x9B59B6},
    "4. Social Elite": {"cost": 3.5, "perks": "Ship System + Ask-to-DM", "color": 0xFD79A8},
    "5. Battle Master": {"cost": 8.5, "perks": "Echo HG + Arena + Classes", "color": 0xE67E22},
    "6. Wealth Architect": {"cost": 6.5, "perks": "Economy + Shop + Utility", "color": 0xF1C40F},
    "7. Executioner Bundle": {"cost": 10.5, "perks": "Classes + Echo + Arena + Casino", "color": 0xD63031},
    "8. Dungeon Merchant": {"cost": 7.5, "perks": "Shop + Econ + Social Access", "color": 0x27AE60},
    "9. Utility Pro": {"cost": 4.0, "perks": "Utility + Economy Access", "color": 0x74B9FF},
    "10. Full Premium": {"cost": 19.5, "perks": "ALL SYSTEMS UNLOCKED (GOD MODE)", "color": 0xFFD700}
}

class PremiumShopView(discord.ui.View):
    def __init__(self, ctx, get_db_connection, fiery_embed, update_user_stats):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.get_db_connection = get_db_connection
        self.fiery_embed = fiery_embed
        self.update_user_stats = update_user_stats
        self.page = 0
        self.pages = self.chunk_plans()
        self.update_buttons()

    def chunk_plans(self):
        keys = list(PREMIUM_PLANS.keys())
        return [keys[i:i + 3] for i in range(0, len(keys), 3)]

    def update_buttons(self):
        self.clear_items()
        self.add_item(self.prev_page)
        self.add_item(self.next_page)
        
        current_keys = self.pages[self.page]
        for key in current_keys:
            button = discord.ui.Button(
                label=f"BUY {key[:15]}...", 
                style=discord.ButtonStyle.success,
                custom_id=f"buy_{key}"
            )
            button.callback = self.make_callback(key)
            self.add_item(button)

    def make_callback(self, plan_name):
        async def callback(interaction: discord.Interaction):
            await self.process_purchase(interaction, plan_name)
        return callback

    def create_embed(self):
        current_keys = self.pages[self.page]
        desc = "### 🛡️  ELITE ASSET ACQUISITION GATEWAY  🛡️\n"
        desc += "*Select your access level. Automatic activation via Protocol V4.*\n\n"
        
        for key in current_keys:
            plan = PREMIUM_PLANS[key]
            p30, p60, p90, p180 = plan['cost'], plan['cost']*2, plan['cost']*2.8, plan['cost']*5.0
            
            desc += f"➤ **{key.upper()}**\n"
            desc += f"```ml\n"
            desc += f" [ 30 Days ] : ${p30:,.2f} USD\n"
            desc += f" [ 60 Days ] : ${p60:,.2f} USD\n"
            desc += f" [ 90 Days ] : ${p90:,.2f} USD (HOT)\n"
            desc += f" [ 180 Days] : ${p180:,.2f} USD (SAVINGS)\n"
            desc += f"```\n"
            desc += f"✨ **PRIVILEGES:** `{plan['perks']}`\n\n"
            
        embed = self.fiery_embed(f"PREMIUM CATALOG │ PAGE {self.page + 1}/{len(self.pages)}", desc)
        embed.set_author(name="THE MASTER'S EXECUTIVE BOUTIQUE", icon_url=self.ctx.author.display_avatar.url)
        return embed

    @discord.ui.button(label="PREVIOUS PAGE", style=discord.ButtonStyle.secondary, emoji="◀️", row=4)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("❌ First page reached.", ephemeral=True)

    @discord.ui.button(label="NEXT PAGE", style=discord.ButtonStyle.secondary, emoji="▶️", row=4)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < len(self.pages) - 1:
            self.page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("❌ Last page reached.", ephemeral=True)

    async def send_audit_report(self, interaction, plan_name, cost, action="INVOICE GENERATED"):
        """Sync with audit.py system to log market activity."""
        main_mod = sys.modules['__main__']
        audit_id = getattr(main_mod, "AUDIT_CHANNEL_ID", 1438810509322223677)
        channel = interaction.client.get_channel(audit_id)
        if channel:
            audit_emb = self.fiery_embed("🛒 MARKET TRANSACTION LOG", 
                f"**Action:** `{action}`\n"
                f"**Asset:** {interaction.user.mention}\n"
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
        # SERVER-WIDE LOGIC: If user is admin, purchase is flagged for guild ID
        target_id = f"G{interaction.guild.id}" if interaction.user.guild_permissions.administrator else interaction.user.id
        custom_data = f"{target_id}|{plan_name}|30"
        
        query = {
            "business": PAYPAL_EMAIL,
            "cmd": "_xclick",
            "amount": plan['cost'] if not interaction.user.guild_permissions.administrator else plan['cost'] * 3, # Server license is 3x price
            "currency_code": CURRENCY,
            "item_name": f"Elite Premium: {plan_name} ({'SERVER UNLOCK' if 'G' in str(target_id) else 'USER UNLOCK'})",
            "custom": custom_data,
            "notify_url": WEBHOOK_URL, 
            "no_shipping": "1",
            "return": "https://discord.com"
        }
        paypal_url = f"https://www.paypal.com/cgi-bin/webscr?{urllib.parse.urlencode(query)}"

        scope = "🌐 **SERVER-WIDE LICENSE**" if "G" in str(target_id) else "👤 **PERSONAL LICENSE**"
        final_cost = query['amount']

        embed = self.fiery_embed("INVOICE GENERATED │ SECURE CHECKOUT", 
                                f"🔞 **User:** {interaction.user.mention}\n"
                                f"🏷️ **Scope:** {scope}\n"
                                f"💎 **Plan:** `{plan_name}`\n"
                                f"💵 **Total:** `${final_cost} USD`\n\n"
                                f"✅ [CLICK HERE TO FINALIZE ON PAYPAL]({paypal_url})\n\n"
                                f"⏳ *The system will detect payment and unlock access immediately.*")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.send_audit_report(interaction, plan_name, final_cost)

class PremiumSystem(commands.Cog):
    def __init__(self, bot, get_db_connection, fiery_embed, update_user_stats):
        self.bot = bot
        self.get_db_connection = get_db_connection
        self.fiery_embed = fiery_embed
        self.update_user_stats = update_user_stats
        self.AUDIT_CHANNEL_ID = getattr(sys.modules['__main__'], "AUDIT_CHANNEL_ID", 1438810509322223677)

    async def log_admin_action(self, member, plan_name, action):
        """Helper to log manual overrides to audit channel."""
        main_mod = sys.modules['__main__']
        audit_id = getattr(main_mod, "AUDIT_CHANNEL_ID", self.AUDIT_CHANNEL_ID)
        channel = self.bot.get_channel(audit_id)
        if channel:
            embed = self.fiery_embed("⚖️ ADMINISTRATIVE PREMIUM OVERRIDE", 
                f"**Action:** `{action}`\n"
                f"**Target:** {member.mention if hasattr(member, 'mention') else member}\n"
                f"**Plan Details:** `{plan_name}`", color=0xE74C3C)
            await channel.send(embed=embed)

    @commands.command(name="premium")
    async def premium_shop(self, ctx):
        """Opens the Premium Subscription Lobby."""
        view = PremiumShopView(ctx, self.get_db_connection, self.fiery_embed, self.update_user_stats)
        embed = view.create_embed()
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="premium.jpg")
            embed.set_image(url="attachment://premium.jpg")
            await ctx.send(file=file, embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    @commands.command(name="activateserver")
    @commands.is_owner()
    @commands.has_permissions(administrator=True)
    async def activate_server_premium(self, ctx, guild_id: int, plan_number: int):
        """Manually activate premium for a whole server."""
        plan_list = list(PREMIUM_PLANS.keys())
        plan_name = plan_list[plan_number - 1]
        p_date = datetime.now().isoformat()
        
        with self.get_db_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO server_premium (guild_id, premium_type, premium_date) VALUES (?, ?, ?)",
                         (guild_id, plan_name, p_date))
            conn.commit()
            
        await ctx.send(embed=self.fiery_embed("SERVER PREMIUM ACTIVATED", f"✅ Guild ID `{guild_id}` elevated to **{plan_name}**.", color=0x00FF00))
        await self.log_admin_action(f"Guild {guild_id}", plan_name, "SERVER MANUAL ACTIVATION")

    @commands.command(name="activate")
    @commands.is_owner()
    @commands.has_permissions(administrator=True)
    async def activate_premium(self, ctx, member: discord.Member, plan_number: int):
        plan_list = list(PREMIUM_PLANS.keys())
        if plan_number < 1 or plan_number > len(plan_list):
            return await ctx.send("❌ Invalid plan.")
            
        plan_name = plan_list[plan_number - 1]
        p_date = datetime.now().isoformat()
        
        with self.get_db_connection() as conn:
            current = conn.execute("SELECT premium_type FROM users WHERE id = ?", (member.id,)).fetchone()
            if not current or current['premium_type'] in ['Free', '', None]:
                new_val = plan_name
            else:
                existing_plans = [p.strip() for p in current['premium_type'].split(',')]
                if plan_name not in existing_plans:
                    existing_plans.append(plan_name)
                new_val = ", ".join(existing_plans)
            
            conn.execute("UPDATE users SET premium_type = ?, premium_date = ? WHERE id = ?", (new_val, p_date, member.id))
            conn.commit()
            
        await ctx.send(embed=self.fiery_embed("PREMIUM ACTIVATED", f"✅ {member.mention} has been elevated to **{plan_name}**.", color=0x00FF00))
        await self.log_admin_action(member, plan_name, "MANUAL ACTIVATION")

    @commands.command(name="testpay")
    @commands.is_owner()
    @commands.has_permissions(administrator=True)
    async def test_payment(self, ctx, member: discord.Member, plan_number: int, is_server: bool = False):
        plan_list = list(PREMIUM_PLANS.keys())
        plan_name = plan_list[plan_number - 1]
        target = f"G{ctx.guild.id}" if is_server else member.id
        payload = {'payment_status': 'Completed', 'custom': f"{target}|{plan_name}|30"}
        
        port = os.environ.get("PORT", "8080")
        urls = [f"http://127.0.0.1:{port}/webhook", WEBHOOK_URL]

        async with aiohttp.ClientSession() as session:
            for url in urls:
                if not url: continue
                try:
                    async with session.post(url, data=payload, timeout=5) as resp:
                        if resp.status == 200:
                            return await ctx.send(f"✅ **Success via {url}!**\nType: **{'SERVER' if is_server else 'USER'}** | Plan: **{plan_name}**.")
                except Exception:
                    continue
        await ctx.send("❌ **Test Failed.**")

    @commands.command(name="premiumstats")
    async def premium_stats(self, ctx):
        with self.get_db_connection() as conn:
            stats = conn.execute("SELECT premium_type, COUNT(*) as count FROM users GROUP BY premium_type").fetchall()
            srv_stats = conn.execute("SELECT COUNT(*) FROM server_premium").fetchone()[0]
        desc = "📉 **MARKET DISTRIBUTION REPORT**\n\n"
        desc += f"🌐 **Premium Servers:** {srv_stats} Guilds\n"
        for row in stats:
            p_type = row['premium_type'] or "Free"
            desc += f"• **{p_type}:** {row['count']} Units\n"
        await ctx.send(embed=self.fiery_embed("GLOBAL ASSET RECAP", desc, color=0x00FFFF))

    @commands.command(name="premiumstatus")
    async def premium_status(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        with self.get_db_connection() as conn:
            u = conn.execute("SELECT premium_type, premium_date FROM users WHERE id = ?", (target.id,)).fetchone()
            s = conn.execute("SELECT premium_type FROM server_premium WHERE guild_id = ?", (ctx.guild.id,)).fetchone()
        
        is_user_p = u and u['premium_type'] not in ['Free', '', None]
        is_server_p = s is not None
        
        if not is_user_p and not is_server_p:
            return await ctx.send(embed=self.fiery_embed("ASSET SEARCH", f"⛓️ {target.display_name} is restricted to **Standard Access**.", color=0x808080))
        
        desc = f"### 💎 ELITE ACCOUNT OVERVIEW: {target.display_name.upper()} 💎\n"
        if is_server_p: desc += f"🌐 **SERVER PREMIUM ACTIVE:** `{s['premium_type']}`\n"
        if is_user_p: desc += f"👤 **PERSONAL PREMIUM ACTIVE:** `{u['premium_type']}`\n"
        
        embed = self.fiery_embed("PRIVATE ASSET OVERVIEW", desc, color=0xFFD700)
        await ctx.send(embed=embed)

    @commands.command(name="echoon")
    @commands.is_owner()
    @commands.has_permissions(administrator=True)
    async def echo_on(self, ctx):
        p_date = datetime.now().isoformat()
        with self.get_db_connection() as conn:
            conn.execute("UPDATE users SET premium_type = '10. Full Premium', premium_date = ?", (p_date,))
            conn.commit()
        await ctx.send(embed=self.fiery_embed("PROTOCOL: GLOBAL OVERRIDE", "👑 ALL ASSETS ELEVATED.", color=0xFFD700))

    @commands.command(name="echooff")
    @commands.is_owner()
    @commands.has_permissions(administrator=True)
    async def echo_off(self, ctx):
        with self.get_db_connection() as conn:
            conn.execute("UPDATE users SET premium_type = 'Free', premium_date = NULL")
            conn.execute("DELETE FROM server_premium")
            conn.commit()
        await ctx.send(embed=self.fiery_embed("PROTOCOL: SYSTEM PURGE", "🌑 ALL UNITS RESET.", color=0x808080))

    @staticmethod
    def is_premium():
        async def predicate(ctx):
            main = sys.modules['__main__']
            with main.get_db_connection() as conn:
                user = conn.execute("SELECT premium_type FROM users WHERE id = ?", (ctx.author.id,)).fetchone()
                serv = conn.execute("SELECT premium_type FROM server_premium WHERE guild_id = ?", (ctx.guild.id,)).fetchone()
            
            if (user and user['premium_type'] not in ['Free', '']) or serv:
                return True
            await ctx.send(embed=main.fiery_embed("ACCESS DENIED", "❌ Premium Access Required."))
            return False
        return commands.check(predicate)

async def setup(bot):
    import sys
    main = sys.modules['__main__']
    with main.get_db_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS server_premium (guild_id INTEGER PRIMARY KEY, premium_type TEXT, premium_date TEXT)")
        try: conn.execute("ALTER TABLE users ADD COLUMN premium_type TEXT DEFAULT 'Free'")
        except: pass 
        try: conn.execute("ALTER TABLE users ADD COLUMN premium_date TEXT")
        except: pass
    await bot.add_cog(PremiumSystem(bot, main.get_db_connection, main.fiery_embed, main.update_user_stats_async))
