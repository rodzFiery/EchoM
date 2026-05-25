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
`!mylevel` Current XP & level across all servers
`!streaks` Discipline ranks
`!hall` Server records

**🎒 Assets & Premium**
`!premium` Perks info
`!premiumstats` Server limits
`!premiumstatus` Active days
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
`!globalgoal` Server target
`!goalhistory` Completed goals
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
`!flash` Winner's decree

**🎰 Casino & Numbers**
`!slots` Slot machine
`!blackjack` Play 21
`!roulette` Wheel bet
`!dice` Bet on sum
`!countinglb` Math top 10
`!countingtop` Top math stats
`!countstats` Your personal math numbers

**🔦 Field Operations**
`!search` Loot blackouts
            """),

            main.fiery_embed("🐾 MEMBER: CATCH MEMBERS", """
**🔍 Capture & Tracking**
`!catch` Capture triggered members
`!pokedex` View collected members
`!velvetdex` View special velvet collection
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
`!getnaked` Display
`!torture` Pain trial
            """),

            main.fiery_embed("⚙️ MEMBER: UTILITY", """
**🛠️ System Information**
`!fiery_guide` Read full system manual
`!gallery` View collected media
`!serverstats` Global server data
`!ping` Latency check (ms)

**🔔 Access & Pings**
`!supremeping` Toggle supreme role ping
`!nosupremeping` Turn off ping
`!freetrial` Claim initial trial access
`!trial` Check remaining trial time
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
`!setauto` Toggle auto settings
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
`!limit` Cap user stats
`!unlimit` Uncap user stats
`!checklimits` View cooldowns
`!leveloff` Disable XP gain
`!basicnsfw` Enable SFW mode
`!nomorebasic` Strict mode enforcement
`!nomorensfw` Global NSFW ban lock
`!nsfwtime` Activate 2x event
`!openpit` Unlock locked arena

**🧹 Cleanup & Logs**
`!audit` Set transaction ledger
`!trigger_audit` Force ledger log
`!autopurge` Auto-wipe chat
`!autorole` Toggle auto-assign roles
`!check_servers` View connected guilds

**📸 Media & Math**
`!react` Set image reaction
`!reactoff` Disable image reaction
`!deletereact` Clear active emotes
`!countfix` Override math count
            """),

            main.fiery_embed("⚙️ ADMIN: SYSTEM & TECH", """
**🎛️ Core Engine**
`!backup` DB to file
`!refresh` Sync cogs
`!reload` Reboot cog
`!debug_cmd` System errors
`!view` Active config
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
`!flames` Add/Sub currency
`!activate_premium` Grant sub to user
`!autoignis` Hourly pit
`!stopautoignis` Halt auto pit
`!startrumble` Force rumble
`!echostart` Open pit
`!reset_arena` Clear lobby
`!echoon` Free access
`!echooff` Lock access
`!echooffall` Hard lock
`!echopurge` Pit wipe

**🔧 Misc Utilities**
`!testpay` Check IPN
`!stealemoji` Copy emote
`!math` Set math channel
`!mathfix` Calibrate math
`!grantbadge` Award custom title
            """)
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

async def setup(bot):
    await bot.add_cog(Guide(bot))
