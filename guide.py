import discord
from discord.ext import commands
import main

class GuideView(discord.ui.View):
    def __init__(self, embeds):
        super().__init__(timeout=None)
        self.embeds = embeds
        self.current_page = 0

    async def update_view(self, interaction):
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page - 1) % len(self.embeds)
        await self.update_view(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page + 1) % len(self.embeds)
        await self.update_view(interaction)

class Guide(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="guide")
    async def guide(self, ctx):
        pages = [
            main.fiery_embed(self.bot, False, "📜 MEMBER: PROFILE & IDENTITY", 
                "`!me`, `!rank`, `!ranking`, `!ranktop`, `!mylevel`, `!setclass`, `!achievements`, `!pokedex`, `!velvetdex`, `!hall`, `!streaks`, `!ask`, `!leveloff`, `!premium`, `!premiumstats`, `!premiumstatus`"),
            main.fiery_embed(self.bot, False, "💰 MEMBER: ECONOMY & LABOR", 
                "`!work`, `!beg`, `!flirt`, `!cumcleaner`, `!experiment`, `!pimp`, `!mystery`, `!daily`, `!weekly`, `!monthly`, `!dailygear`, `!buybox`, `!checklimits`, `!questboard`, `!quests`, `!globalgoal`, `!goalhistory`, `!collections`, `!favor`, `!submit`"),
            main.fiery_embed(self.bot, False, "⚔️ MEMBER: COMBAT & GAMES", 
                "`!echostart`, `!echopack`, `!lobby`, `!autolobby`, `!joinpit`, `!fuck`, `!fightecho`, `!slots`, `!blackjack`, `!roulette`, `!dice`, `!countinglb`, `!countingtop`, `!countstats`, `!search`, `!dungeonbag`, `!catch`, `!test`, `!flash`, `!switch`, `!togglealerts`"),
            main.fiery_embed(self.bot, False, "💘 MEMBER: SOCIAL & BONDS", 
                "`!ship`, `!shiphistory`, `!matchmaking`, `!matchme`, `!match3some`, `!marry`, `!divorce`, `!bestfriend`, `!contract`, `!accept`, `!bondtrial`, `!confess`, `!ask`"),
            main.fiery_embed(self.bot, False, "🔞 MEMBER: EROTIC PROTOCOLS", 
                "`!slut`, `!winslut`, `!cuckold`, `!deepthroat`, `!spit`, `!tease`, `!spank`, `!slap`, `!makemedirty`, `!3some`, `!dp`, `!anal`, `!bendover`, `!getnaked`, `!torture`, `!submissive`, `!dominant`, `!switch`, `!exhibitionist`"),
            main.fiery_embed(self.bot, False, "⚙️ MEMBER: UTILITY & SETTINGS", 
                "`!fiery_guide`, `!gallery`, `!serverstats`, `!ping`, `!supremeping`, `!nosupremeping`, `!freetrial`, `!trial`")
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

    @commands.command(name="adminguide")
    @commands.has_permissions(administrator=True)
    async def admin_guide(self, ctx):
        pages = [
            main.fiery_embed(self.bot, False, "🛠️ ADMIN: CONFIG & SETUP", 
                "`!setadminrole`, `!setauto`, `!setlevelchannel`, `!setlevelrole`, `!setticket`, `!setcards`, `!setcounting`, `!setignis`, `!set_ignis_admin`, `!setconfesscount`, `!setconfesspost`, `!setconfesspost2`, `!setconfessreview`"),
            main.fiery_embed(self.bot, False, "🛡️ ADMIN: MODERATION & AUDIT", 
                "`!audit`, `!trigger_audit`, `!autopurge`, `!autorole`, `!basicnsfw`, `!nomorebasic`, `!nomorensfw`, `!nsfwtime`, `!openpit`, `!limit`, `!unlimit`, `!react`, `!reactoff`, `!deletereact`, `!countfix`, `!check_servers`"),
            main.fiery_embed(self.bot, False, "⚙️ ADMIN: SYSTEM & TECHNICAL", 
                "`!backup`, `!refresh`, `!reload`, `!debug_cmd`, `!view`, `!warroom`, `!archives`, `!activate_premium`, `!autoignis`, `!stopautoignis`, `!startrumble`, `!reset_arena`, `!collectadmin`, `!flames`, `!testpay`, `!ticket`, `!ticketadmin`, `!ticketcategory`, `!thread`, `!threadall`, `!threadoff`, `!stealemoji`, `!math`, `!mathfix`, `!echoon`, `!echooff`, `!echooffall`, `!echopurge`, `!grantbadge`")
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

async def setup(bot):
    await bot.add_cog(Guide(bot))
