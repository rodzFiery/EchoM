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
            main.fiery_embed("📜 MEMBER: IDENTITY & PROFILE", 
                "`!me`: Dossier profile. `!rank`: Combat rank. `!ranking`: Leaderboard. `!ranktop`: Top stats. `!mylevel`: Level info. `!setclass`: Pick path. `!achievements`: Scars/Milestones. `!pokedex`: Asset list. `!velvetdex`: Velvet info. `!hall`: Legacy records. `!streaks`: Consistency logs. `!ask`: Query bot. `!leveloff`: XP toggle. `!premium`: Sub info. `!premiumstats`: Status. `!premiumstatus`: Status check."),
            main.fiery_embed("💰 MEMBER: ECONOMY & LABOR", 
                "`!work`: Polish/Serve. `!beg`: Grovel for scraps. `!flirt`: Seduce patrons. `!cumcleaner`: Sanitize. `!experiment`: Trial subject. `!pimp`: Asset management. `!mystery`: Sensory gamble. `!daily`: Reward claim. `!weekly`: Reward claim. `!monthly`: Reward claim. `!dailygear`: Equipment. `!buybox`: Random items. `!checklimits`: View cooldowns. `!questboard`: Active tasks. `!quests`: All quests. `!globalgoal`: Server goals. `!goalhistory`: History. `!collections`: Owned items. `!favor`: Master's boost. `!submit`: Final action."),
            main.fiery_embed("⚔️ MEMBER: COMBAT & GAMES", 
                "`!echostart`: Open pit. `!echopack`: Combat gear. `!lobby`: Current lobby. `!autolobby`: Toggle. `!joinpit`: Join rumble. `!fuck`: Duel challenge. `!fightecho`: Start fight. `!slots`: Triple slots. `!blackjack`: Cards. `!roulette`: Wheel of luck. `!dice`: Guess sum. `!countinglb`: Count records. `!countingtop`: Top counters. `!countstats`: Your stats. `!search`: Blackout looting. `!dungeonbag`: Inventory. `!catch`: Catch assets. `!test`: Verify link. `!flash`: Apply decree. `!switch`: Change mode. `!togglealerts`: Alert toggle."),
            main.fiery_embed("💘 MEMBER: BONDS & SOCIAL", 
                "`!ship`: Compatibility check. `!shiphistory`: History. `!matchmaking`: Voyeur scan. `!matchme`: Scan yourself. `!match3some`: Multi-ship. `!marry`: Propose. `!divorce`: End bond. `!bestfriend`: Add buddy. `!contract`: Service offer. `!accept`: Seal bond. `!bondtrial`: Kink check. `!confess`: Send secret. `!ask`: Interaction."),
            main.fiery_embed("🔞 MEMBER: EROTIC PROTOCOLS", 
                "`!slut`: Labour work. `!winslut`: Labour win. `!cuckold`: Cuckold act. `!deepthroat`: Oral service. `!spit`: Humiliation. `!tease`: Tease act. `!spank`: Discipline. `!slap`: Strike. `!makemedirty`: Filth work. `!3some`: 3-way act. `!dp`: Double penetration. `!anal`: Anal act. `!bendover`: Position act. `!getnaked`: Strip. `!torture`: Pain trial. `!submissive`: Sub role. `!dominant`: Dom role. `!switch`: Switch role. `!exhibitionist`: Show off."),
            main.fiery_embed("⚙️ MEMBER: UTILITY", 
                "`!fiery_guide`: Member guide. `!gallery`: Media storage. `!serverstats`: Stats. `!ping`: Latency check. `!supremeping`: Toggle ping. `!nosupremeping`: Toggle ping. `!freetrial`: Trial access. `!trial`: Trial status.")
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

    @commands.command(name="adminguide")
    @commands.has_permissions(administrator=True)
    async def admin_guide(self, ctx):
        pages = [
            main.fiery_embed("🛠️ ADMIN: SETUP", 
                "`!setadminrole`: Role binding. `!setauto`: Auto settings. `!setlevelchannel`: XP channel. `!setlevelrole`: Level role. `!setticket`: Ticket system. `!setcards`: Card rules. `!setcounting`: Math channel. `!setignis`: Pit settings. `!set_ignis_admin`: Admin pit role. `!setconfesscount`: Confess limit. `!setconfesspost`: Confess log. `!setconfesspost2`: Confess log 2. `!setconfessreview`: Review channel."),
            main.fiery_embed("🛡️ ADMIN: MODERATION", 
                "`!audit`: Log audit. `!trigger_audit`: Force log. `!autopurge`: Auto clean. `!autorole`: Auto role. `!basicnsfw`: NSFW toggle. `!nomorebasic`: Restriction. `!nomorensfw`: Global NSFW ban. `!nsfwtime`: NSFW event. `!openpit`: Enable pit. `!limit`: Set limits. `!unlimit`: Remove limits. `!react`: Media reaction. `!reactoff`: Disable reaction. `!deletereact`: Clear reactions. `!countfix`: Fix math. `!check_servers`: Verify connections."),
            main.fiery_embed("⚙️ ADMIN: SYSTEM & TECH", 
                "`!backup`: DB backup. `!refresh`: Refresh cogs. `!reload`: Reload cog. `!debug_cmd`: Debug info. `!view`: View settings. `!warroom`: Admin hub. `!archives`: Archive channel. `!activate_premium`: Premium flag. `!autoignis`: Start auto pit. `!stopautoignis`: Stop auto pit. `!startrumble`: Start arena. `!reset_arena`: Reset pit. `!collectadmin`: System cleanup. `!flames`: Add/Sub balance. `!testpay`: Test webhook. `!ticket`: Open ticket. `!ticketadmin`: Manage tickets. `!ticketcategory`: Ticket category. `!thread`: Start threading. `!threadall`: Thread all. `!threadoff`: Disable threading. `!stealemoji`: Add emojis. `!math`: Math channel. `!mathfix`: Calibrate count. `!echoon`: Enable echo. `!echooff`: Disable echo. `!echooffall`: Disable all echo. `!echopurge`: Purge echo. `!grantbadge`: Award badge.")
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

async def setup(bot):
    await bot.add_cog(Guide(bot))
