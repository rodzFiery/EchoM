import discord
from discord.ext import commands
import sqlite3
import os
import sys
import urllib.parse  # ADDED: Para gerar links de pagamento seguros
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO PAYPAL (INTEGRAÇÃO WEBHOOK AUTOMÁTICA) ---
# Utilizando variáveis de ambiente (Railway) ou valores padrão
PAYPAL_EMAIL = os.getenv("PAYPAL_EMAIL", "seu-email@paypal.com")
# URL do seu Webhook Handler (onde o bot processará o sinal do PayPal)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://seu-app.railway.app/paypal_webhook")
CURRENCY = "USD"

# --- PRE-CONFIGURED PLANS (20 BUNDLES + 9 A LA CARTE - TOTAL 29 PLANS) ---
PREMIUM_PLANS = {
    "1. Starter Core Pack": {"cost": 6.5, "perks": "Classes + Economy + Shop", "color": 0x3498DB},
    "2. Combat Pack": {"cost": 5.0, "perks": "Echo HangryGames + 1v1 Arena", "color": 0xE74C3C},
    "3. Echo Survival Pack": {"cost": 4.0, "perks": "Echo HangryGames", "color": 0x2ECC71},
    "4. Work & Wealth Pack": {"cost": 3.5, "perks": "Economy System", "color": 0xF1C40F},
    "5. Mega Core Bundle": {"cost": 8.5, "perks": "Classes + Econ + Shop + Utility", "color": 0x9B59B6},
    "6. All-Combat Bundle": {"cost": 7.5, "perks": "Echo HG + Arena + Casino", "color": 0xE67E22},
    "7. Ultimate Progression": {"cost": 10.5, "perks": "Classes + Econ + Shop + Echo", "color": 0x1ABC9C},
    "8. Economy Expansion": {"cost": 4.5, "perks": "Economy + Shop", "color": 0x27AE60},
    "9. Social Interaction": {"cost": 2.5, "perks": "Ship + Ask-to-DM", "color": 0xFD79A8},
    "10. Casino Pack": {"cost": 2.5, "perks": "Casino System", "color": 0xAD1457},
    "11. Exploration Pack": {"cost": 5.5, "perks": "Utility + Economy", "color": 0x74B9FF},
    "12. Advanced Arena": {"cost": 7.0, "perks": "Echo + Arena + Classes", "color": 0xD63031},
    "13. Guild Builder": {"cost": 5.5, "perks": "Economy + Shop + Ship", "color": 0x00B894},
    "14. Complete Battle": {"cost": 12.0, "perks": "Echo + Arena + Casino + Econ + Shop", "color": 0x6C5CE7},
    "15. Merchant Pack": {"cost": 6.5, "perks": "Shop + Econ + Utility", "color": 0xFDCB6E},
    "16. Creators Pack": {"cost": 8.0, "perks": "Classes + Econ + Shop + Ask-to-DM", "color": 0xFF8B94},
    "17. Echo Boost Pack": {"cost": 6.0, "perks": "Echo HG + Utility", "color": 0x81ECEC},
    "18. Arena Combo": {"cost": 11.5, "perks": "Echo + Arena + Classes + Econ + Shop", "color": 0xFF7675},
    "19. Minimal Starter": {"cost": 5.5, "perks": "Economy + Utility", "color": 0xA29BFE},
    "20. Full Premium Everything": {"cost": 19.5, "perks": "ALL SYSTEMS UNLOCKED", "color": 0xFFD700},
    # --- INDIVIDUAL ITEMS (A LA CARTE) ---
    "A1. Classes": {"cost": 2.0, "perks": "Individual System Access", "color": 0x95A5A6},
    "A2. Echo HangryGames": {"cost": 4.0, "perks": "Individual System Access", "color": 0x95A5A6},
    "A3. 1v1 Arena Fight": {"cost": 1.0, "perks": "Individual System Access", "color": 0x95A5A6},
    "A4. Economy": {"cost": 3.5, "perks": "Individual System Access", "color": 0x95A5A6},
    "A5. Shop": {"cost": 1.0, "perks": "Individual System Access", "color": 0x95A5A6},
    "A6. Ship System": {"cost": 1.0, "perks": "Individual System Access", "color": 0x95A5A6},
    "A7. Casino": {"cost": 2.5, "perks": "Individual System Access", "color": 0x95A5A6},
    "A8. Utility": {"cost": 2.0, "perks": "Individual System Access", "color": 0x95A5A6},
    "A9. Ask-to-DM": {"cost": 1.5, "perks": "Individual System Access", "color": 0x95A5A6}
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

    def chunk_plans(self):
        keys = list(PREMIUM_PLANS.keys())
        return [keys[i:i + 3] for i in range(0, len(keys), 3)]

    def create_embed(self):
        current_keys = self.pages[self.page]
        desc = "### 🛡️  ELITE ASSET ACQUISITION GATEWAY  🛡️\n"
        desc += "*Selecione seu nível de acesso. Ativação automática via Protocolo V4.*\n\n"
        
        for key in current_keys:
            plan = PREMIUM_PLANS[key]
            p30, p60, p90, p180 = plan['cost'], plan['cost']*2, plan['cost']*2.8, plan['cost']*5.0
            
            desc += f"➤ **{key.upper()}**\n"
            desc += f"```ml\n"
            desc += f" [ 30D ] : ${p30:,.2f} USD\n"
            desc += f" [ 60D ] : ${p60:,.2f} USD\n"
            desc += f" [ 90D ] : ${p90:,.2f} USD (HOT)\n"
            desc += f" [180D ] : ${p180:,.2f} USD (SAVINGS)\n"
            desc += f"```\n"
            desc += f"✨ **PRIVILEGES:** `{plan['perks']}`\n\n"
            
        embed = self.fiery_embed(f"CATÁLOGO PREMIUM │ PÁGINA {self.page + 1}/{len(self.pages)}", desc)
        embed.set_author(name="THE MASTER'S EXECUTIVE BOUTIQUE", icon_url=self.ctx.author.display_avatar.url)
        return embed

    @discord.ui.button(label="PREVIOUS PAGE", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.create_embed())
        else:
            await interaction.response.send_message("❌ Primeira página alcançada.", ephemeral=True)

    @discord.ui.button(label="NEXT PAGE", style=discord.ButtonStyle.secondary, emoji="▶️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < len(self.pages) - 1:
            self.page += 1
            await interaction.response.edit_message(embed=self.create_embed())
        else:
            await interaction.response.send_message("❌ Última página alcançada.", ephemeral=True)

    async def process_purchase(self, interaction, plan_name):
        plan = PREMIUM_PLANS[plan_name]
        # PAYPAL AUTOMATION LOGIC: Injeta metadados para o Webhook processar
        # custom_data envia ID do Usuário e Nome do Plano de volta para seu servidor
        custom_data = f"{interaction.user.id}|{plan_name}|30"
        query = {
            "business": PAYPAL_EMAIL,
            "cmd": "_xclick",
            "amount": plan['cost'],
            "currency_code": CURRENCY,
            "item_name": f"Elite Premium: {plan_name}",
            "custom": custom_data,
            "notify_url": WEBHOOK_URL, # O PayPal enviará o sinal de sucesso aqui
            "no_shipping": "1",
            "return": "https://discord.com"
        }
        paypal_url = f"https://www.paypal.com/cgi-bin/webscr?{urllib.parse.urlencode(query)}"

        embed = self.fiery_embed("INVOICE GENERATED │ SECURE CHECKOUT", 
                                f"🔞 **Ativo:** {interaction.user.mention}\n"
                                f"💎 **Plano:** `{plan_name}`\n"
                                f"💵 **Total:** `${plan['cost']} USD`\n\n"
                                f"✅ [CLIQUE AQUI PARA FINALIZAR NO PAYPAL]({paypal_url})\n\n"
                                f"⏳ *O sistema detectará o pagamento e liberará seu acesso na hora.*")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="BUY FULL ACCESS", style=discord.ButtonStyle.success, emoji="👑")
    async def full_buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_purchase(interaction, "20. Full Premium Everything")

    @discord.ui.button(label="COMBAT PACK", style=discord.ButtonStyle.danger, emoji="⚔️")
    async def combat_buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_purchase(interaction, "2. Combat Pack")

class PremiumSystem(commands.Cog):
    def __init__(self, bot, get_db_connection, fiery_embed, update_user_stats):
        self.bot = bot
        self.get_db_connection = get_db_connection
        self.fiery_embed = fiery_embed
        self.update_user_stats = update_user_stats

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

    @commands.command(name="activate")
    @commands.has_permissions(administrator=True)
    async def activate_premium(self, ctx, member: discord.Member, plan_number: int):
        """Manually activate premium after payment verification."""
        plan_list = list(PREMIUM_PLANS.keys())
        if plan_number < 1 or plan_number > len(plan_list):
            return await ctx.send("❌ Plano inválido.")
            
        plan_name = plan_list[plan_number - 1]
        p_date = datetime.now().isoformat()
        
        with self.get_db_connection() as conn:
            conn.execute("UPDATE users SET premium_type = ?, premium_date = ? WHERE id = ?", (plan_name, p_date, member.id))
            conn.commit()
            
        await ctx.send(embed=self.fiery_embed("PREMIUM ACTIVATED", f"✅ {member.mention} foi elevado para **{plan_name}**.", color=0x00FF00))

    @commands.command(name="premiumstats")
    async def premium_stats(self, ctx):
        with self.get_db_connection() as conn:
            stats = conn.execute("SELECT premium_type, COUNT(*) as count FROM users GROUP BY premium_type").fetchall()
        desc = "📉 **MARKET DISTRIBUTION REPORT**\n\n"
        for row in stats:
            p_type = row['premium_type'] or "Free"
            desc += f"• **{p_type}:** {row['count']} Units\n"
        await ctx.send(embed=self.fiery_embed("GLOBAL ASSET RECAP", desc, color=0x00FFFF))

    @commands.command(name="premiumstatus")
    @commands.has_permissions(administrator=True)
    async def premium_status(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        with self.get_db_connection() as conn:
            u = conn.execute("SELECT premium_type, premium_date, balance, class, fiery_level FROM users WHERE id = ?", (target.id,)).fetchone()
        if not u or u['premium_type'] == 'Free':
            return await ctx.send(embed=self.fiery_embed("ASSET SEARCH", f"⛓️ {target.display_name} is Standard.", color=0x808080))
        purchase_dt = datetime.fromisoformat(u['premium_date'])
        expiry_dt = purchase_dt + timedelta(days=30)
        remaining = expiry_dt - datetime.now()
        desc = (f"📋 **Plan:** {u['premium_type']}\n⏳ **Remaining:** {max(0, remaining.days)} Days")
        await ctx.send(embed=self.fiery_embed("PRIVATE ASSET OVERVIEW", desc, color=0xFFD700))

    @commands.command(name="echoon")
    @commands.has_permissions(administrator=True)
    async def echo_on(self, ctx):
        p_date = datetime.now().isoformat()
        with self.get_db_connection() as conn:
            conn.execute("UPDATE users SET premium_type = '20. Full Premium Everything', premium_date = ?", (p_date,))
            conn.commit()
        await ctx.send(embed=self.fiery_embed("PROTOCOL: GLOBAL OVERRIDE", "👑 ALL ASSETS ELEVATED.", color=0xFFD700))

    @commands.command(name="echooff")
    @commands.has_permissions(administrator=True)
    async def echo_off(self, ctx):
        with self.get_db_connection() as conn:
            conn.execute("UPDATE users SET premium_type = 'Free', premium_date = NULL")
            conn.commit()
        await ctx.send(embed=self.fiery_embed("PROTOCOL: SYSTEM PURGE", "🌑 ALL UNITS RESET.", color=0x808080))

    @staticmethod
    def is_premium():
        async def predicate(ctx):
            main = sys.modules['__main__']
            user = main.get_user(ctx.author.id)
            if user and user['premium_type'] != 'Free':
                return True
            await ctx.send(embed=main.fiery_embed("ACCESS DENIED", "❌ Premium Collar required."))
            return False
        return commands.check(predicate)

async def setup(bot):
    import sys
    main = sys.modules['__main__']
    with main.get_db_connection() as conn:
        try: conn.execute("ALTER TABLE users ADD COLUMN premium_type TEXT DEFAULT 'Free'")
        except: pass 
        try: conn.execute("ALTER TABLE users ADD COLUMN premium_date TEXT")
        except: pass
    await bot.add_cog(PremiumSystem(bot, main.get_db_connection, main.fiery_embed, main.update_user_stats_async))
