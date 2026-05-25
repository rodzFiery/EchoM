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
                "`!me`: View dossier. `!rank`: Check combat tier. `!ranking`: Global top members. `!ranktop`: Highest levels. `!mylevel`: Current XP & level. `!setclass`: Choose class bonus. `!achievements`: View unlocked badges. `!pokedex`: View collected assets. `!velvetdex`: View special collection. `!hall`: View server records. `!streaks`: View discipline ranks. `!ask`: Query the system. `!leveloff`: Disable XP gain. `!premium`: View premium perks. `!premiumstats`: Check server premium limits. `!premiumstatus`: Check your active days."),
            main.fiery_embed("💰 MEMBER: ECONOMY & LABOR", 
                "`!work`: Base labor (Flames). `!beg`: Low-tier extraction. `!flirt`: Mid-tier extraction. `!cumcleaner`: Cleanup duty (Flames). `!experiment`: Trial subject. `!pimp`: Asset management. `!mystery`: Random gamble extraction. `!daily`: 24h reward claim. `!weekly`: 7d reward claim. `!monthly`: 30d reward claim. `!dailygear`: Claim daily equipment. `!buybox`: Buy random gacha box. `!checklimits`: View your active cooldowns. `!questboard`: View active tasks. `!quests`: Check all available quests. `!globalgoal`: View server-wide target. `!goalhistory`: View past completed goals. `!collections`: View full inventory. `!favor`: Bribe to force Peak Heat. `!submit`: Accept current outcome."),
            main.fiery_embed("⚔️ MEMBER: COMBAT & GAMES", 
                "`!echostart`: Open the arena. `!echopack`: View combat supply. `!lobby`: View waiting fighters. `!autolobby`: Auto-join matches. `!joinpit`: Enter rumble simulation. `!fuck`: Challenge to 1v1 duel. `!fightecho`: PvE system fight. `!slots`: Slot machine gamble. `!blackjack`: Play 21 for Flames. `!roulette`: Wheel bet game. `!dice`: Bet on number sum. `!countinglb`: Math top 10. `!countingtop`: Top server math stats. `!countstats`: Your personal math numbers. `!search`: Loot during blackouts. `!dungeonbag`: Check rumble gear. `!catch`: Capture triggered assets. `!test`: Verify system ping. `!flash`: Winner's forced decree. `!switch`: Shift combat mode. `!togglealerts`: Toggle Guardian pings."),
            main.fiery_embed("💘 MEMBER: BONDS & SOCIAL", 
                "`!ship`: Check synergy percentage. `!shiphistory`: View past pairings. `!matchmaking`: Scan tension lobby. `!matchme`: Scan your personal synergy. `!match3some`: Trio synergy scan. `!marry`: Bind souls for bonuses. `!divorce`: Break current bond. `!bestfriend`: Add allied bond. `!contract`: Offer service deal. `!accept`: Approve pending bond/contract. `!bondtrial`: Test synergy limits. `!confess`: Send secret message. `!ask`: Query master interaction."),
            main.fiery_embed("🔞 MEMBER: EROTIC PROTOCOLS", 
                "**Labor System (Earn Flames & XP on 3h cooldowns):**\n"
                "`!slut`: Base labor. `!winslut`: Variant labor. `!cuckold`: Passive labor. `!deepthroat`: High-yield XP labor. `!spit`: Humiliation labor. `!tease`: Sensory labor. `!spank`: Discipline labor. `!slap`: Strike labor. `!makemedirty`: Intense labor. `!3some`: Trio labor. `!dp`: Double labor. `!anal`: Heavy labor. `!bendover`: Stance labor. `!getnaked`: Display labor. `!torture`: Pain trial labor.\n\n"
                "**Roles:** `!submissive`: Sub bonus. `!dominant`: Dom bonus. `!switch`: Switch bonus. `!exhibitionist`: Exh bonus."),
            main.fiery_embed("⚙️ MEMBER: UTILITY", 
                "`!fiery_guide`: Read full system manual. `!gallery`: View collected media. `!serverstats`: Global server data. `!ping`: Latency check (ms). `!supremeping`: Toggle supreme role ping. `!nosupremeping`: Turn off supreme ping. `!freetrial`: Claim initial trial access. `!trial`: Check remaining trial time.")
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

    @commands.command(name="adminguide")
    @commands.has_permissions(administrator=True)
    async def admin_guide(self, ctx):
        pages = [
            main.fiery_embed("🛠️ ADMIN: SETUP", 
                "`!setadminrole`: Bind admin override role. `!setauto`: Toggle auto settings. `!setlevelchannel`: Assign level-up logs. `!setlevelrole`: Configure level milestone ranks. `!setticket`: Setup support desk. `!setcards`: Configure card rules. `!setcounting`: Designate math pit. `!setignis`: Arena setup. `!set_ignis_admin`: Assign pit moderator. `!setconfesscount`: Set secret limits. `!setconfesspost`: Designate secret log 1. `!setconfesspost2`: Designate secret log 2. `!setconfessreview`: Designate review queue channel."),
            main.fiery_embed("🛡️ ADMIN: MODERATION", 
                "`!audit`: Set transaction ledger. `!trigger_audit`: Force ledger log. `!autopurge`: Auto-wipe chat configuration. `!autorole`: Toggle auto-assign roles. `!basicnsfw`: Enable SFW mode. `!nomorebasic`: Strict mode enforcement. `!nomorensfw`: Global NSFW ban lock. `!nsfwtime`: Activate 2x event. `!openpit`: Unlock locked arena. `!limit`: Cap user stats. `!unlimit`: Uncap user stats. `!react`: Set image reaction. `!reactoff`: Disable image reaction. `!deletereact`: Clear active emotes. `!countfix`: Override broken math count. `!check_servers`: View connected guilds."),
            main.fiery_embed("⚙️ ADMIN: SYSTEM & TECH", 
                "`!backup`: Save database to file. `!refresh`: Sync cog modules. `!reload`: Reboot specific cog. `!debug_cmd`: Check system errors. `!view`: Check active config. `!warroom`: Open mod hub. `!archives`: Save archive data. `!activate_premium`: Grant sub to user. `!autoignis`: Start hourly automated pit. `!stopautoignis`: Halt automated pit. `!startrumble`: Force rumble event. `!reset_arena`: Clear stuck lobby. `!collectadmin`: Wipe collection data. `!flames`: Add/Subtract user currency. `!testpay`: Check webhook IPN. `!ticket`: Create ticket panel. `!ticketadmin`: Mod ticket panel. `!ticketcategory`: Ticket group setup. `!thread`: Start media threading. `!threadall`: Thread all messages. `!threadoff`: Halt threading protocol. `!stealemoji`: Copy emote to server. `!math`: Set math channel. `!mathfix`: Calibrate math count. `!echoon`: Global free access. `!echooff`: Global lock access. `!echooffall`: Hard lock server. `!echopurge`: Pit wipe execution. `!grantbadge`: Award custom title/badge.")
        ]
        view = GuideView(pages)
        await ctx.send(embed=pages[0], view=view)

async def setup(bot):
    await bot.add_cog(Guide(bot))
