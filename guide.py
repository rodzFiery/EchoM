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
            main.fiery_embed(self.bot, False, "📜 THE SLAVE'S DOSSIER", 
                "**IDENTITY & GROWTH**\n"
                "`!me` `!mylevel` `!rank` `!ranking` `!ranktop` `!hall` `!achievements` `!streaks` `!setclass` `!pokedex` `!velvetdex` `!premium` `!premiumstats` `!premiumstatus` `!leveloff` `!ask`"),
            main.fiery_embed(self.bot, False, "💰 THE RED ROOM HARVEST", 
                "**LABOR & OBEDIENCE**\n"
                "`!work` `!beg` `!flirt` `!cumcleaner` `!experiment` `!pimp` `!mystery` `!daily` `!weekly` `!monthly` `!dailygear` `!buybox` `!checklimits` `!questboard` `!quests` `!globalgoal` `!goalhistory` `!collections` `!favor` `!submit`"),
            main.fiery_embed(self.bot, False, "⚔️ THE PIT OF SLAUGHTER", 
                "**COMBAT PROTOCOLS**\n"
                "`!echostart` `!echopack` `!lobby` `!autolobby` `!joinpit` `!fuck` `!fightecho` `!slots` `!blackjack` `!roulette` `!dice` `!countinglb` `!countingtop` `!countstats` `!search` `!dungeonbag` `!catch` `!flash` `!test` `!switch` `!togglealerts`"),
            main.fiery_embed(self.bot, False, "💘 THE BONDS OF SERVICE", 
                "**SOCIAL & COLLARS**\n"
                "`!ship` `!shiphistory` `!matchmaking` `!matchme` `!match3some` `!marry` `!divorce` `!bestfriend` `!contract` `!accept` `!bondtrial` `!confess` `!ask`"),
            main.fiery_embed(self.bot, False, "🔞 THE CHAMBER OF LUST", 
                "**EROTIC COMMANDS**\n"
                "`!slut` `!winslut` `!cuckold` `!deepthroat` `!spit` `!tease` `!spank` `!slap` `!makemedirty` `!3some` `!dp` `!anal` `!bendover` `!getnaked` `!torture` `!submissive` `!dominant` `!switch` `!exhibitionist`"),
            main.fiery_embed(self.bot, False, "⚙️ SYSTEM PROTOCOLS", 
                "**UTILITY**\n"
                "`!fiery_guide` `!gallery` `!serverstats` `!ping` `!supremeping` `!nosupremeping` `!freetrial` `!trial`")
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

    @commands.command(name="adminguide")
    @commands.has_permissions(administrator=True)
    async def admin_guide(self, ctx):
        pages = [
            main.fiery_embed(self.bot, False, "🛠️ ADMIN: CORE CONFIGURATION", 
                "`!setadminrole` `!setauto` `!setlevelchannel` `!setlevelrole` `!setticket` `!setcards` `!setcounting` `!setignis` `!set_ignis_admin` `!setconfesscount` `!setconfesspost` `!setconfesspost2` `!setconfessreview`"),
            main.fiery_embed(self.bot, False, "🛡️ ADMIN: DISCIPLINE & AUDIT", 
                "`!audit` `!trigger_audit` `!autopurge` `!autorole` `!basicnsfw` `!nomorebasic` `!nomorensfw` `!nsfwtime` `!openpit` `!limit` `!unlimit` `!react` `!reactoff` `!deletereact` `!countfix` `!check_servers`"),
            main.fiery_embed(self.bot, False, "⚙️ ADMIN: MASTER ENGINE", 
                "`!backup` `!refresh` `!reload` `!debug_cmd` `!view` `!warroom` `!archives` `!activate_premium` `!autoignis` `!stopautoignis` `!startrumble` `!reset_arena` `!collectadmin` `!flames` `!testpay` `!ticket` `!ticketadmin` `!ticketcategory` `!thread` `!threadall` `!threadoff` `!stealemoji` `!math` `!mathfix` `!echoon` `!echooff` `!echooffall` `!echopurge` `!grantbadge`")
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

async def setup(bot):
    await bot.add_cog(Guide(bot))
