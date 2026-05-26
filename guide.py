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
            main.fiery_embed("📜 MEMBER: IDENTITY & PROFILE", """
**👤 Personal Dossier**
`!me` View dossier
`!achievements` Unlocked badges

**🏆 Hierarchy & Status**
`!ranking` Echo Hangryames
`!ranktop` Highest levels
`!mylevel` Current XP & level
`!streaks` Discipline ranks
`!hall` Server records

**🎒 Assets & Premium**
`!premium` Perks info
            """),
            
            main.fiery_embed("🎭 MEMBER: CLASSES", """
**🧬 Choose Your Path**
`!setclass` Open the class selection menu

**✨ Specific Role Commands**
`!dominant` Claim the Dominant role & bonus
`!submissive` Claim the Submissive role & bonus
`!switch` Claim the Switch role & bonus
`!exhibitionist` Claim the Exhibitionist role & bonus
            """),

            main.fiery_embed("💰 MEMBER: ECONOMY & LABOR", """
**⏱️ Routine Claims**
`!daily` 24h reward
`!weekly` 7d reward
`!monthly` 30d reward
`!dailygear` Claim equipment

**💼 Labor Extractions**
`!work` Base labor
`!beg` Low-tier extraction
`!flirt` Mid-tier extraction
`!cumcleaner` Cleanup duty
`!experiment` Trial subject
`!mystery` Random gamble
`!pimp` Asset management

**📜 Progression & Goals**
`!questboard` Active tasks
`!quests` All available
`!collections` Full inventory
`!buybox` Random gacha box
`!favor` Bribe to force Peak Heat
`!submit` Accept outcome
            """),

            main.fiery_embed("⚔️ MEMBER: COMBAT & GAMES", """
**⚔️ The Arena**
`!lobby` Waiting fighters
`!autolobby` Auto-join
`!joinpit` Enter rumble
`!echopack` Combat supply
`!dungeonbag` Rumble gear
`!fuck` 1v1 duel challenge
`!fightecho` PvE fight

**🎰 Casino**
`!slots` Slot machine
`!blackjack` Play 21
`!roulette` Wheel bet
`!dice` Bet on sum

**🔦 Field Operations**
`!search` Loot blackouts
`!switch` Shift combat mode
            """),

            main.fiery_embed("🔢 MEMBER: COUNTING", """
**📈 Statistical Tracking**
`!countinglb` Math top 10
`!countingtop` Top math stats
`!countstats` Your personal math numbers

**🎯 Goal Tracking**
`!globalgoal` Server target
`!goalhistory` Completed goals
            """),

            main.fiery_embed("🐾 MEMBER: CATCH MEMBERS", """
**🔍 Capture & Tracking**
`!catch` Capture triggered members
`!pokedex` View collected members
`!velvetdex` View special velvet collection
`!supremeping` Toggle supreme role ping
`!nosupremeping` Turn off ping
            """),

            main.fiery_embed("💘 MEMBER: BONDS & SOCIAL", """
**🔍 Matchmaking & Synergy**
`!ship` Check synergy %
`!shiphistory` View past pairings
`!matchmaking` Scan tension lobby
`!matchme` Scan your synergy
`!match3some` Trio synergy scan

**💍 Bonds & Contracts**
`!marry` Bind souls
`!divorce` Break bond
`!bestfriend` Add allied bond
`!contract` Offer service deal
`!accept` Approve pending bond/contract
`!bondtrial` Test synergy limits

**💌 Confessions**
`!confess` Send secret message
            """),

            main.fiery_embed("🔞 MEMBER: EROTIC PROTOCOLS", """
**🫦 Acts & Labor (3h Cooldowns)**
`!slut` Base labor
`!winslut` Variant labor
`!cuckold` Passive labor
`!deepthroat` High XP labor
`!spit` Humiliation labor
`!tease` Sensory labor
`!spank` Discipline labor
`!slap` Strike labor
`!makemedirty` Intense labor

**🔥 Advanced Protocols**
`!3some` Trio act
`!dp` Double act
`!anal` Heavy act
`!bendover` Stance
`!torture` Pain trial
            """),
            
            main.fiery_embed("🔮 MEMBER: MASTER INTERACTION", """
**💬 Inquiry**
`!ask` Query the system / master interaction
            """)
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

    @commands.command(name="adminguide")
    @commands.has_permissions(administrator=True)
    async def admin_guide(self, ctx):
        pages = [
            main.fiery_embed("🛠️ ADMIN: SETUP", """
**⚙️ Base Configuration**
`!setadminrole` Bind override role
`!setauto` Turn ON the auto Echo HG
`!setlevelchannel` Assign level-up logs
`!setlevelrole` Milestone ranks
`!setticket` Setup support desk
`!setcards` Configure card rules

**⚖️ Mod & Pit Rules**
`!setignis` Arena setup
`!set_ignis_admin` Assign pit moderator
`!setcounting` Designate math pit

**🤫 Confession System**
`!setconfesscount` Set secret limits
`!setconfessreview` Review queue
`!setconfesspost` Designate log 1
`!setconfesspost2` Designate log 2
            """),

            main.fiery_embed("🛡️ ADMIN: MODERATION", """
**🛡️ Enforcement**
`!limit` Cap user pings
`!unlimit` Uncap user pings
`!checklimits` View cooldowns
`!leveloff` Disable XP gain
`!basicnsfw` Enable SFW mode
`!nomorebasic` Strict mode enforcement
`!nomorensfw` Global NSFW ban lock
`!nsfwtime` Activate 2x event
`!openpit` Echo RoyalRumble

**🧹 Cleanup & Logs**
`!audit` Set transaction ledger
`!trigger_audit` Force ledger log
`!autorole` Toggle auto-assign roles

**📸 Media & Math**
`!react` Set image reaction
`!reactoff` Disable image reaction
`!deletereact` Clear active emotes
`!countfix` Override math count
            """),

            main.fiery_embed("⚙️ ADMIN: SYSTEM & TECH", """
**🎛️ Core Engine**
`!warroom` Mod hub
`!collectadmin` Wipe collections
`!archives` Save archive data
`!test` Verify ping
`!togglealerts` Guardian pings

**🧵 Threads & Tickets**
`!thread` Start threading
`!threadall` Thread all
`!threadoff` Halt threading
`!ticket` Create ticket panel
`!ticketadmin` Mod ticket panel
`!ticketcategory` Group setup

**💰 Currency & Pit Automation**
`!activate_premium` Grant sub to user
`!autoignis` Hourly pit
`!stopautoignis` Halt auto pit
`!startrumble` Force rumble
`!echostart` Echo hangrygames
`!reset_arena` Clear lobby
`!echopurge` Clean messages

**🔧 Misc Utilities**
`!stealemoji` Copy emote
`!math` Set math channel to flash
`!mathfix` Calibrate math
`!grantbadge` Award custom title
            """)
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

async def setup(bot):
    await bot.add_cog(Guide(bot))
    # Important: If you want these buttons to work after a restart,
    # you must add the following line in your main bot file's setup:
    # bot.add_view(GuideView(embeds=[]))
