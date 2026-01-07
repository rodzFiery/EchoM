import discord
from discord.ext import commands
import sqlite3
import os
import sys
from datetime import datetime, timedelta

# --- PRE-CONFIGURED PLANS ---
PREMIUM_PLANS = {
    "Bronze": {"cost": 50000, "perks": "Access to !work command", "color": 0xCD7F32},
    "Silver": {"cost": 150000, "perks": "Access to !work & 1.5x Multiplier", "color": 0xC0C0C0},
    "Gold": {"cost": 500000, "perks": "All previous + Exclusive Badge", "color": 0xFFD700}
}

class PremiumShopView(discord.ui.View):
    def __init__(self, ctx, get_db_connection, fiery_embed, update_user_stats):
        # FIX: Changed timeout to None to keep the Premium Lobby persistent
        super().__init__(timeout=None)
        self.ctx = ctx
        self.get_db_connection = get_db_connection
        self.fiery_embed = fiery_embed
        self.update_user_stats = update_user_stats

    async def process_purchase(self, interaction, plan_name):
        plan = PREMIUM_PLANS[plan_name]
        u_id = interaction.user.id
        # ADDED: Record current date for subscription tracking
        purchase_date = datetime.now().isoformat()
        
        with self.get_db_connection() as conn:
            user = conn.execute("SELECT balance, premium_type FROM users WHERE id = ?", (u_id,)).fetchone()
            
            if not user:
                return await interaction.response.send_message("You are not registered in the pit yet.", ephemeral=True)
            
            if user['balance'] < plan['cost']:
                return await interaction.response.send_message(f"❌ You need {plan['cost']:,} Flames for {plan_name}.", ephemeral=True)
            
            if user['premium_type'] == plan_name:
                return await interaction.response.send_message(f"🫦 You already possess the {plan_name} collar.", ephemeral=True)

            # Deduct flames and update premium status + date in the centralized DB
            conn.execute("UPDATE users SET balance = balance - ?, premium_type = ?, premium_date = ? WHERE id = ?", (plan['cost'], plan_name, purchase_date, u_id))
            conn.commit()

        embed = self.fiery_embed("PREMIUM UPGRADE SEALED", 
                                f"🔞 {interaction.user.mention} has upgraded to **{plan_name} Status**!\n\n"
                                f"💰 **Price Paid:** {plan['cost']:,} Flames\n"
                                f"✨ **New Perks:** {plan['perks']}", color=plan['color'])
        
        # ADDED: Send confirmation to the channel so everyone sees the new Elite asset
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Bronze Plan", style=discord.ButtonStyle.secondary, emoji="🥉", custom_id="buy_bronze")
    async def bronze_buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_purchase(interaction, "Bronze")

    @discord.ui.button(label="Silver Plan", style=discord.ButtonStyle.primary, emoji="🥈", custom_id="buy_silver")
    async def silver_buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_purchase(interaction, "Silver")

    @discord.ui.button(label="Gold Plan", style=discord.ButtonStyle.success, emoji="🥇", custom_id="buy_gold")
    async def gold_buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_purchase(interaction, "Gold")

class PremiumSystem(commands.Cog):
    def __init__(self, bot, get_db_connection, fiery_embed, update_user_stats):
        self.bot = bot
        self.get_db_connection = get_db_connection
        self.fiery_embed = fiery_embed
        self.update_user_stats = update_user_stats

    @commands.command(name="premium")
    async def premium_shop(self, ctx):
        """Opens the Premium Subscription Lobby."""
        desc = "🔞 **THE ELITE LOUNGE** 🔞\n\nChoose your level of submission and unlock restricted commands.\n\n"
        for name, data in PREMIUM_PLANS.items():
            desc += f"**{name}:** {data['cost']:,} Flames\n└ *{data['perks']}*\n\n"
        
        embed = self.fiery_embed("Master's Premium Boutique", desc)
        view = PremiumShopView(ctx, self.get_db_connection, self.fiery_embed, self.update_user_stats)
        
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
        
        desc = "📊 **DUNGEON SUBSCRIPTION LEDGER**\n\n"
        for row in stats:
            p_type = row['premium_type'] or "Free"
            desc += f"• **{p_type}:** {row['count']} Assets\n"
        
        embed = self.fiery_embed("Premium Population Recap", desc, color=0x00FFFF)
        await ctx.send(embed=embed)

    @commands.command(name="premiumstatus")
    @commands.has_permissions(administrator=True)
    async def premium_status(self, ctx, member: discord.Member = None):
        """ADDED: Admin command to check subscription details and days remaining."""
        target = member or ctx.author
        with self.get_db_connection() as conn:
            u = conn.execute("SELECT premium_type, premium_date, balance, class, fiery_level FROM users WHERE id = ?", (target.id,)).fetchone()
        
        if not u or u['premium_type'] == 'Free':
            embed = self.fiery_embed("Subscription Status Check", f"⛓️ **{target.display_name}** has no active collar.\n\n**Current Status:** Free Asset", color=0x808080)
            if os.path.exists("LobbyTopRight.jpg"):
                file = discord.File("LobbyTopRight.jpg", filename="status_logo.jpg")
                embed.set_thumbnail(url="attachment://status_logo.jpg")
                return await ctx.send(file=file, embed=embed)
            return await ctx.send(embed=embed)

        # Calculate time remaining
        purchase_dt = datetime.fromisoformat(u['premium_date'])
        expiry_dt = purchase_dt + timedelta(days=30)
        remaining = expiry_dt - datetime.now()
        days_left = max(0, remaining.days)

        desc = (f"📋 **Target Identity:** {target.mention}\n"
                f"🎖️ **Elite Plan:** {u['premium_type']}\n"
                f"📅 **Enrolled On:** {purchase_dt.strftime('%Y-%m-%d')}\n"
                f"⏳ **Time Remaining:** {days_left} Days\n\n"
                f"**📊 ASSET METRICS:**\n"
                f"🔥 **Vault Balance:** {u['balance']:,} Flames\n"
                f"🧬 **Assigned Class:** {u['class']}\n"
                f"🔝 **Dungeon Level:** {u['fiery_level']}\n\n"
                f"🔞 **Status:** Under Active Premium Contract")

        embed = self.fiery_embed("Premium Subscription Status", desc, color=0xFFD700)
        embed.set_author(name="MASTER'S PRIVATE LEDGER", icon_url=target.display_avatar.url)
        
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
            conn.execute("UPDATE users SET premium_type = 'Gold', premium_date = ?", (p_date,))
            conn.commit()
        
        embed = self.fiery_embed("ECHO ON: GLOBAL DOMINANCE", "👑 **PROTOCOL ACTIVATED.** Every asset in the dungeon has been elevated to **Gold Premium Status**.\n\n*The Master grants unlimited access to all.*", color=0xFFD700)
        await ctx.send(embed=embed)

    @commands.command(name="echooff")
    @commands.has_permissions(administrator=True)
    async def echo_off(self, ctx):
        """ADDED: Revokes ALL premium statuses in any server."""
        with self.get_db_connection() as conn:
            conn.execute("UPDATE users SET premium_type = 'Free', premium_date = NULL")
            conn.commit()
        
        embed = self.fiery_embed("ECHO OFF: GLOBAL RESET", "🌑 **PROTOCOL TERMINATED.** All elite privileges have been revoked. Every asset has returned to **Free Status**.\n\n*The favor of the Master has faded.*", color=0x808080)
        await ctx.send(embed=embed)

    # --- DECORATOR/CHECK FOR PREMIUM COMMANDS ---
    @staticmethod
    def is_premium():
        async def predicate(ctx):
            # CONNECTED TO MAIN: Uses the main module to check user status
            main = sys.modules['__main__']
            user = main.get_user(ctx.author.id)
            if user and user['premium_type'] != 'Free':
                return True
            
            embed = main.fiery_embed("Restricted Access", "❌ This command is restricted to **Premium Assets**. Use `!premium` to upgrade.")
            await ctx.send(embed=embed)
            return False
        return commands.check(predicate)

async def setup(bot):
    import sys
    main = sys.modules['__main__']
    
    # Migração Silenciosa: Garante que as colunas existem no DB centralizado
    with main.get_db_connection() as conn:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN premium_type TEXT DEFAULT 'Free'")
        except:
            pass # Coluna já existe
        try:
            # ADDED: premium_date column for tracking
            conn.execute("ALTER TABLE users ADD COLUMN premium_date TEXT")
        except:
            pass
            
    await bot.add_cog(PremiumSystem(
        bot, 
        main.get_db_connection, 
        main.fiery_embed, 
        main.update_user_stats_async
    ))
