import discord
from discord.ext import commands
import sqlite3
import os
import sys
from datetime import datetime, timedelta

# --- PRE-CONFIGURED PLANS (20 BUNDLES + 9 A LA CARTE - TOTAL 29 PLANS) ---
# PRICES ARE IN USD ($) AS REQUESTED
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
        # FIX: Changed timeout to None to keep the Premium Lobby persistent
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
        
        # --- PROFESSIONAL MARKETING UI ---
        desc = "### ▬▬▬  ACQUIRING ELITE STATUS  ▬▬▬\n"
        desc += "*Nível de Acesso: Autorizado. Ledger: Red Room Protocol.*\n\n"
        
        for key in current_keys:
            plan = PREMIUM_PLANS[key]
            # Advanced Tiered Pricing Strategy
            p30, p60, p90, p180 = plan['cost'], plan['cost']*2, plan['cost']*2.8, plan['cost']*5.0
            save_long = round(((p30 * 6) - p180) / (p30 * 6) * 100)

            desc += f"➤ **{key.upper()}**\n"
            desc += f"```ml\n"
            desc += f" [ 30D ] : ${p30:,.2f} USD\n"
            desc += f" [ 60D ] : ${p60:,.2f} USD\n"
            desc += f" [ 90D ] : ${p90:,.2f} USD (HOT)\n"
            desc += f" [180D ] : ${p180:,.2f} USD ({save_long}% OFF)\n"
            desc += f"```\n"
            desc += f"✨ **BENEFITS:** `{plan['perks']}`\n\n"
            
        embed = self.fiery_embed(f"ELITE LOUNGE │ INDEX {self.page + 1}/{len(self.pages)}", desc)
        embed.set_author(name="THE MASTER'S EXECUTIVE BOUTIQUE", icon_url=self.ctx.author.display_avatar.url)
        embed.set_footer(text="System status: Secure | Payments processed via Private Ledger")
        return embed

    @discord.ui.button(label="PREVIOUS PAGE", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.create_embed())
        else:
            await interaction.response.send_message("❌ Primeir página alcançada.", ephemeral=True)

    @discord.ui.button(label="NEXT PAGE", style=discord.ButtonStyle.secondary, emoji="▶️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < len(self.pages) - 1:
            self.page += 1
            await interaction.response.edit_message(embed=self.create_embed())
        else:
            await interaction.response.send_message("❌ Última página alcançada.", ephemeral=True)

    async def process_purchase(self, interaction, plan_name):
        plan = PREMIUM_PLANS[plan_name]
        u_id = interaction.user.id
        # ADDED: Record current date for subscription tracking
        purchase_date = datetime.now().isoformat()
        
        with self.get_db_connection() as conn:
            user = conn.execute("SELECT premium_type FROM users WHERE id = ?", (u_id,)).fetchone()
            
            if not user:
                return await interaction.response.send_message("ERROR: User profile not detected in central DB.", ephemeral=True)
            
            # Note: Prices in USD require manual sync or specialized gateway
            conn.execute("UPDATE users SET premium_type = ?, premium_date = ? WHERE id = ?", (plan_name, purchase_date, u_id))
            conn.commit()

        embed = self.fiery_embed("TRANSACTION ENCRYPTED", 
                                f"🔞 {interaction.user.mention} has secured **{plan_name} Status**!\n\n"
                                f"💎 **Asset Status:** {plan['perks']}", color=plan['color'])
        
        # ADDED: Send confirmation to the channel so everyone sees the new Elite asset
        await interaction.response.send_message(embed=embed)

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
        """Opens the Premium Subscription Lobby with Paginated Pages and USD Prices."""
        view = PremiumShopView(ctx, self.get_db_connection, self.fiery_embed, self.update_user_stats)
        embed = view.create_embed()
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="premium.jpg")
            embed.set_image(url="attachment://premium.jpg")
            await ctx.send(file=file, embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    @commands.command(name="premiumstats")
    async def premium_stats(self, ctx):
        """Shows the distribution of premium plans in the dungeon."""
        with self.get_db_connection() as conn:
            stats = conn.execute("SELECT premium_type, COUNT(*) as count FROM users GROUP BY premium_type").fetchall()
        
        desc = "📉 **MARKET DISTRIBUTION REPORT**\n\n"
        for row in stats:
            p_type = row['premium_type'] or "Free"
            desc += f"• **{p_type}:** {row['count']} Units\n"
        
        embed = self.fiery_embed("GLOBAL ASSET RECAP", desc, color=0x00FFFF)
        await ctx.send(embed=embed)

    @commands.command(name="premiumstatus")
    @commands.has_permissions(administrator=True)
    async def premium_status(self, ctx, member: discord.Member = None):
        """ADDED: Admin command to check subscription details and days remaining."""
        target = member or ctx.author
        with self.get_db_connection() as conn:
            u = conn.execute("SELECT premium_type, premium_date, balance, class, fiery_level FROM users WHERE id = ?", (target.id,)).fetchone()
        
        if not u or u['premium_type'] == 'Free':
            embed = self.fiery_embed("ASSET SEARCH", f"⛓️ **{target.display_name}** is currently a **Standard Asset** (Free).", color=0x808080)
            if os.path.exists("LobbyTopRight.jpg"):
                file = discord.File("LobbyTopRight.jpg", filename="status_logo.jpg")
                embed.set_thumbnail(url="attachment://status_logo.jpg")
                return await ctx.send(file=file, embed=embed)
            return await ctx.send(embed=embed)

        purchase_dt = datetime.fromisoformat(u['premium_date'])
        expiry_dt = purchase_dt + timedelta(days=30)
        remaining = expiry_dt - datetime.now()
        days_left = max(0, remaining.days)

        desc = (f"📋 **Target Identity:** {target.mention}\n"
                f"🎖️ **Elite Plan:** {u['premium_type']}\n"
                f"📅 **Enrolled On:** {purchase_dt.strftime('%d/%m/%Y')}\n"
                f"⏳ **Time Remaining:** {days_left} Days\n\n"
                f"**📊 PERFORMANCE METRICS:**\n"
                f"🔥 **Vault Balance:** {u['balance']:,} Flames\n"
                f"🧬 **Assigned Class:** {u['class']}\n"
                f"🔝 **Dungeon Level:** {u['fiery_level']}\n\n"
                f"🔞 **Contract Status:** SECURED")

        embed = self.fiery_embed("PRIVATE ASSET OVERVIEW", desc, color=0xFFD700)
        embed.set_author(name="MASTER'S ANALYTICS", icon_url=target.display_avatar.url)
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="status_logo.jpg")
            embed.set_thumbnail(url="attachment://status_logo.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

    @commands.command(name="echoon")
    @commands.has_permissions(administrator=True)
    async def echo_on(self, ctx):
        """ADDED: Force enables Gold Premium for ALL registered assets in any server."""
        p_date = datetime.now().isoformat()
        with self.get_db_connection() as conn:
            conn.execute("UPDATE users SET premium_type = '20. Full Premium Everything', premium_date = ?", (p_date,))
            conn.commit()
        
        embed = self.fiery_embed("PROTOCOL: GLOBAL OVERRIDE", "👑 **OVERRIDE SUCCESSFUL.** All assets elevated to **FULL PREMIUM**.\n\n*Unlimited access granted.*", color=0xFFD700)
        await ctx.send(embed=embed)

    @commands.command(name="echooff")
    @commands.has_permissions(administrator=True)
    async def echo_off(self, ctx):
        """ADDED: Revokes ALL premium statuses in any server."""
        with self.get_db_connection() as conn:
            conn.execute("UPDATE users SET premium_type = 'Free', premium_date = NULL")
            conn.commit()
        
        embed = self.fiery_embed("PROTOCOL: SYSTEM PURGE", "🌑 **PURGE SUCCESSFUL.** Elite privileges terminated. All units reset to Standard.", color=0x808080)
        await ctx.send(embed=embed)

    # --- DECORATOR/CHECK FOR PREMIUM COMMANDS ---
    @staticmethod
    def is_premium():
        async def predicate(ctx):
            main = sys.modules['__main__']
            user = main.get_user(ctx.author.id)
            if user and user['premium_type'] != 'Free':
                return True
            
            embed = main.fiery_embed("ACCESS DENIED", "❌ Premium Collar required. Visit `!premium` to upgrade.")
            await ctx.send(embed=embed)
            return False
        return commands.check(predicate)

async def setup(bot):
    import sys
    main = sys.modules['__main__']
    
    with main.get_db_connection() as conn:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN premium_type TEXT DEFAULT 'Free'")
        except:
            pass 
        try:
            conn.execute("ALTER TABLE users ADD COLUMN premium_date TEXT")
        except:
            pass
            
    await bot.add_cog(PremiumSystem(
        bot, 
        main.get_db_connection, 
        main.fiery_embed, 
        main.update_user_stats_async
    ))
