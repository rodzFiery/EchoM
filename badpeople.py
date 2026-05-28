import discord
from discord.ext import commands
import random
import os
from collections import Counter
import json # Added: Required for saving data to a file

# Added: Persistent view for the Lobby that never times out
class BadPeopleLobby(discord.ui.View):
    def __init__(self, prompts, color_sassy, prompt_number=1, last_prompt=None):
        super().__init__(timeout=None) # timeout=None prevents the view from expiring
        self.prompts = prompts
        self.color_sassy = color_sassy
        self.prompt_number = prompt_number
        self.last_prompt = last_prompt

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, custom_id="bp_persistent_next", emoji="⏭️")
    async def next_prompt(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Logic to display previous results before moving to the next prompt
        if self.last_prompt:
            mentions = []
            async for message in interaction.channel.history(limit=50):
                if message.mentions:
                    for user in message.mentions:
                        # Only count the mention if the user's ID is explicitly typed in the message content
                        if f"<@{user.id}>" in message.content or f"<@!{user.id}>" in message.content:
                            mentions.append(user)
            
            if mentions:
                counts = Counter(mentions)
                most_common = counts.most_common(1)[0]
                winner = most_common[0]
                total = most_common[1]

                embed_results = discord.Embed(
                    title="🏆 Previous Round Results",
                    description=f"For the prompt: *{self.last_prompt}*\n\n**{winner.mention}** is the most likely party! ({total} votes)",
                    color=self.color_sassy
                )
                await interaction.channel.send(embed=embed_results)
                
                # Added: Saving the winner to a persistent JSON file
                try:
                    with open("badpeople_stats.json", "r") as f:
                        stats = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    stats = {}
                
                user_id_str = str(winner.id)
                if user_id_str not in stats:
                    stats[user_id_str] = {"name": winner.display_name, "wins": 0}
                
                stats[user_id_str]["wins"] += 1
                stats[user_id_str]["name"] = winner.display_name # Update name in case they changed it
                
                with open("badpeople_stats.json", "w") as f:
                    json.dump(stats, f, indent=4)

        next_number = self.prompt_number + 1
        new_prompt = random.choice(self.prompts)
        
        embed = discord.Embed(
            title=f"😈 Bad People Protocol | #{next_number}",
            description=f"**{new_prompt}**\n\n👇 *Tag the guilty party below. Don't be shy.*",
            color=self.color_sassy
        )
        
        embed.set_footer(text=f"Requested by {interaction.user.display_name} • Let the drama begin.", icon_url=interaction.user.display_avatar.url)
        
        # We send a new message instead of editing the old one
        new_view = BadPeopleLobby(self.prompts, self.color_sassy, prompt_number=next_number, last_prompt=new_prompt)
        await interaction.channel.send(embed=embed, view=new_view)
        
        # Acknowledge the interaction
        await interaction.response.defer()


class BadPeople(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color_sassy = 0x8A2BE2 # A dark, sassy purple to fit the NSFW theme
        
        # Massive list of NSFW 'Who is most likely to...' prompts
        self.prompts = [
            "Who is most likely to accidentally send a nude to their family group chat?",
            "Who is most likely to fake an orgasm just so they can go to sleep?",
            "Who is most likely to have a secret, highly successful OnlyFans?",
            "Who is most likely to sleep with their best friend's ex?",
            "Who is most likely to get caught hooking up in a public bathroom?",
            "Who is most likely to own a shockingly expensive collection of adult toys?",
            "Who is most likely to have a kink they are absolutely terrified to admit?",
            "Who is most likely to catch feelings after a one-night stand?",
            "Who is most likely to hook up with someone just because they were bored?",
            "Who is most likely to suggest a threesome and then instantly regret it?",
            "Who is most likely to have a completely separate, secret social media account for their thirst traps?",
            "Who is most likely to ghost someone immediately after sleeping with them?",
            "Who is most likely to have slept with more than three people in a single 24-hour period?",
            "Who is most likely to send a 'U up?' text at 3 AM on a Tuesday?",
            "Who is most likely to cry during sex?",
            "Who is most likely to be undeniably loud in bed?",
            "Who is most likely to get off on being degraded?",
            "Who is most likely to have an extremely detailed 'hit list' of people they want to sleep with?",
            "Who is most likely to hook up with a coworker and make the office unbearably awkward?",
            "Who is most likely to use a safe word and actually mean it?",
            "Who is most likely to secretly enjoy being tied up?",
            "Who is most likely to fall asleep while someone is going down on them?",
            "Who is most likely to have a completely unhinged search history?",
            "Who is most likely to start stripping after exactly two drinks?",
            "Who is most likely to have matching sexy underwear and actually wear it daily?",
            "Who is most likely to ruin a perfectly good date by being too horny?",
            "Who is most likely to accidentally say the wrong name in bed?",
            "Who is most likely to record a sex tape and instantly lose the phone?",
            "Who is most likely to be the easiest to seduce at a party?",
            "Who is most likely to have the highest body count in this entire server?",
            "Who is most likely to get kicked out of a club for public indecency?",
            "Who is most likely to slide into a celebrity's DMs with a highly inappropriate picture?",
            "Who is most likely to try a dangerous sex position and end up in the emergency room?",
            "Who is most likely to be a sub in the sheets but a dom in the streets?",
            "Who is most likely to date someone strictly for their money and pretend it's true love?",
            "Who is most likely to have a sugar daddy/mommy on speed dial?",
            "Who is most likely to secretly read the dirtiest, most unhinged fanfiction?",
            "Who is most likely to own handcuffs that aren't meant for a costume?",
            "Who is most likely to brag about their sex life when it's actually completely dead?",
            "Who is most likely to have kissed their cousin by 'accident'?",
            "Who is most likely to propose roleplay and make it incredibly awkward?",
            "Who is most likely to have a 'friends with benefits' arrangement that ruins their life?",
            "Who is most likely to sleep with someone purely to get revenge?",
            "Who is most likely to have the wildest, most unbelievable sex stories that are actually 100% true?",
            "Who is most likely to need a gag order after a wild weekend?",
            "Who is most likely to catch an STD and pretend it's just a 'rash'?",
            "Who is most likely to get turned on by toxic behavior?",
            "Who is most likely to have an entire hidden photo album on their phone requiring a 6-digit passcode?",
            "Who is most likely to use food in the bedroom and make a disgusting mess?",
            "Who is most likely to leave a visible hickey on someone right before a family event?",
            "Who is most likely to be entirely too vocal about their fetishes?",
            "Who is most likely to date a stripper?",
            "Who is most likely to be banned from Tinder for inappropriate behavior?",
            "Who is most likely to get off on the risk of getting caught?",
            "Who is most likely to sleep with someone who is currently in a relationship?",
            "Who is most likely to have an affair with someone twice their age?",
            "Who is most likely to completely forget the name of the person they woke up next to?",
            "Who is most likely to be into feet?",
            "Who is most likely to accidentally send an explicitly dirty text to their boss?",
            "Who is most likely to have the lowest standards at 2 AM?",
            "Who is most likely to initiate a spicy game of Truth or Dare just to target one specific person?",
            "Who is most likely to walk in on someone and just stand there watching?",
            "Who is most likely to be aggressively vanilla while acting like a freak on the timeline?",
            "Who is most likely to unironically use the phrase 'Daddy' in bed?",
            "Who is most likely to choke on something that isn't food?",
            "Who is most likely to sell their bathwater for a quick profit?",
            "Who is most likely to get way too attached after a mediocre hookup?",
            "Who is most likely to have an active profile on an illicit dating site?",
            "Who is most likely to ruin the mood by laughing uncontrollably during sex?",
            "Who is most likely to keep a secret stash of adult magazines in the digital age?",
            "Who is most likely to have hooked up with a completely random stranger from the internet?",
            "Who is most likely to have absolutely zero gag reflex?",
            "Who is most likely to ask for spit and actually mean it?",
            "Who is most likely to need an exorcism after their internet history gets leaked?",
            "Who is most likely to be a massive disappointment in bed despite looking incredible?",
            "Who is most likely to have a praise kink that controls their entire life?",
            "Who is most likely to let someone completely ruin their life just because the sex was good?",
            "Who is most likely to own a sex swing?",
            "Who is most likely to accidentally broadcast audio of their intimate moments in a Discord voice channel?",
            "Who is most likely to have a custom-made outfit specifically for roleplay?",
            "Who is most likely to get caught tracking their partner's live location out of pure horniness?",
            "Who is most likely to ask for feedback or a rating directly after a hookup?",
            "Who is most likely to have a completely separate drawer just for ropes and leather?",
            "Who is most likely to match with their friend's parent on a dating app?",
            "Who is most likely to spend their entire paycheck on a premium adult subscription?",
            "Who is most likely to download a dating app purely for a single night of validation?",
            "Who is most likely to fall in love with an adult entertainer?",
            "Who is most likely to look through their partner's phone specifically looking for spicy photos?",
            "Who is most likely to get caught sneaking someone out of their window at 4 AM?",
            "Who is most likely to hook up with someone just because they have a nice car?",
            "Who is most likely to have a list of criteria for their one-night stands that reads like a grocery list?",
            "Who is most likely to be into voyeurism?",
            "Who is most likely to text their ex immediately after getting turned down by someone new?",
            "Who is most likely to get a tattoo of someone's name that they've only known for a month?",
            "Who is most likely to send a spicy picture intended for their partner to a complete stranger?",
            "Who is most likely to have a collection of polaroids hidden under their mattress?",
            "Who is most likely to search for explicit videos of their favorite fictional characters?",
            "Who is most likely to suggest checking into a love hotel for a lunch break?",
            "Who is most likely to get off on playing games on their phone during intimacy?",
            "Who is most likely to talk clean but act completely unhinged behind closed doors?",
            "Who is most likely to leave an explicit voice note by accident?",
            "Who is most likely to get matching piercings with their casual hookup partner?",
            "Who is most likely to use an alias during a one-night stand so they can never be found?",
            "Who is most likely to be into exhibitionism but text like a nun?",
            "Who is most likely to accidentally like an explicit post from five years ago on their crush's timeline?",
            "Who is most likely to have a secret collection of explicit audiobooks?",
            "Who is most likely to get caught looking at spicy subreddits during a company presentation?",
            "Who is most likely to pretend they are a completely different profession just to look hot at a bar?",
            "Who is most likely to wake up with a mysterious scratch or bite mark and have no idea how it got there?",
            "Who is most likely to buy their partner an adult toy that they secretly wanted to use on themselves?",
            "Who is most likely to use their roommate's explicit supplies without asking?",
            "Who is most likely to get super defensive when someone asks about their body count?",
            "Who is most likely to look up instructions on how to do a specific bedroom trick mid-act?",
            "Who is most likely to have a playlist specifically curated for their sneaky links?",
            "Who is most likely to fall for a toxic person just because they are incredibly good in bed?",
            "Who is most likely to try an explicit challenge they saw on TikTok?",
            "Who is most likely to bring a spare set of clothes to a first date just in case they stay over?",
            "Who is most likely to get caught checking out their best friend's partner?",
            "Who is most likely to have an explicit dream about someone in this server and make it weird next time they talk?",
            "Who is most likely to make their partner wear a specific wig during roleplay?",
            "Who is most likely to brag about a hookup that never actually happened?",
            "Who is most likely to have their adult toys delivered to a neighbor's house by accident?",
            "Who is most likely to suggest a quickie in the middle of a family dinner?",
            "Who is most likely to be completely submissive but pretend they run the relationship?",
            "Who is most likely to slide into the DMs of their partner's sibling?",
            "Who is most likely to have a dedicated mirror next to their bed for purely aesthetic reasons?",
            "Who is most likely to try ice cubes in the bedroom and end up regretting life choices?",
            "Who is most likely to leave a spicy item in their partner's car on purpose as a marker?",
            "Who is most likely to lie about their age on an adult site?",
            "Who is most likely to write anonymous erotic stories about people they know in real life?",
            "Who is most likely to order something highly inappropriate from a restaurant delivery app by mistake?",
            "Who is most likely to look through someone's nightstand the moment they leave the room?",
            "Who is most likely to get a thrill from doing it while someone else is in the next room?",
            "Who is most likely to keep a journal ranking all of their past encounters?",
            "Who is most likely to break a piece of furniture during a passionate moment?",
            "Who is most likely to get way too competitive during a game of strip poker?",
            "Who is most likely to download an adult game on Steam 'for the plot'?",
            "Who is most likely to try blindfolds and immediately get disoriented and fall off the bed?",
            "Who is most likely to use a cheesy pickup line that actually ends up working?",
            "Who is most likely to have an experimental phase that lasted ten years?",
            "Who is most likely to get caught wearing something incredibly scandalous under their formal work clothes?",
            "Who is most likely to ask their partner to talk dirty but get completely embarrassed when they do?",
            "Who is most likely to get turned on by someone explaining complex scientific or code theories?",
            "Who is most likely to lose an article of clothing at a party and never find it?",
            "Who is most likely to invite a casual hookup to a major holiday dinner as their plus one?",
            "Who is most likely to have their search history exposed by screen sharing on a Discord call?",
            "Who is most likely to have a secret preference for being completely dominated?",
            "Who is most likely to buy luxury sheets strictly to impress a casual date?",
            "Who is most likely to get caught taking a suggestive selfie in a public dressing room?",
            "Who is most likely to fall out of bed while trying to change positions gracefully?",
            "Who is most likely to have a crush on a virtual AI assistant?",
            "Who is most likely to text their partner an explicit description of what they want to do later while sitting right across from them?",
            "Who is most likely to give a fake phone number to a persistent admirer at a club?",
            "Who is most likely to spend hours editing a single spicy photo before sending it?",
            "Who is most likely to accidentally turn on their camera during an explicit late-night conversation?",
            "Who is most likely to have a specific phrase that instantly makes them entirely too compliant?",
            "Who is most likely to use a dating app while they are already out on a date?",
            "Who is most likely to keep an emergency kit of mints and protection in every bag they own?",
            "Who is most likely to have an intense obsession with a specific uniform?",
            "Who is most likely to get caught sneaking an extra glance when someone is changing?",
            "Who is most likely to plan an elaborate getaway purely for the intimacy aspect?",
            "Who is most likely to fall asleep immediately after the main event without saying a word?",
            "Who is most likely to leave a trail of clothes from the front door to the bedroom?",
            "Who is most likely to get flustered by a simple wink?",
            "Who is most likely to use an excessive amount of oils or lotions and ruin their mattress?",
            "Who is most likely to get a thrill from sneaking into a restricted area for a quick hookup?",
            "Who is most likely to have a highly active secret premium folder on their computer labeled 'Tax Returns'?",
            "Who is most likely to fall in love with someone based entirely on their voice?",
            "Who is most likely to have an unread folder full of unhinged confessions?",
            "Who is most likely to agree to a dare that involves doing something completely scandalous in public?",
            "Who is most likely to overthink a simple compliment and turn it into an existential crisis of horniness?",
            "Who is most likely to have a secret preference for being drawn or animated explicitly?",
            "Who is most likely to break out the handcuffs on a first date?",
            "Who is most likely to get caught looking at someone's lips instead of listening to what they are saying?",
            "Who is most likely to buy adult items in person just for the adrenaline rush of checking out?",
            "Who is most likely to have a hidden tattoo in a highly intimate location?",
            "Who is most likely to post a highly suggestive status update just to see if one specific person views it?",
            "Who is most likely to send a spicy picture that accidentally reveals something incredibly messy or embarrassing in the background?",
            "Who is most likely to get distracted by food in the middle of an intimate session?",
            "Who is most likely to have a secret collection of specialized alternative fashion meant strictly for private hours?",
            "Who is most likely to whisper something completely unhinged in someone's ear during a quiet public event?",
            "Who is most likely to spend way too much time picking out the perfect aesthetic light setting before a date arrives?",
            "Who is most likely to get caught practicing their seductive face in the bathroom mirror?",
            "Who is most likely to have a massive crush on their best friend's sibling?",
            "Who is most likely to use a technical or code term as an explicit double entendre?",
            "Who is most likely to get caught checking themselves out in a storefront window while walking with a date?",
            "Who is most likely to write a highly detailed, highly inappropriate review for an adult toy online?",
            "Who is most likely to have their spicy photos leaked because they backed them up to a public cloud by accident?",
            "Who is most likely to let out a surprisingly weird noise when startled or caught off guard during an intimate moment?",
            "Who is most likely to get completely lost in a fantasy world instead of paying attention to real-world relationships?",
            "Who is most likely to purchase a ridiculous luxury item just because it looked exceptionally provocative in an ad?",
            "Who is most likely to accidentally open a highly explicit tab while showing a video to their parents?",
            "Who is most likely to get caught sending a risky text under the table during a serious dinner?",
            "Who is most likely to spend an hour picking out the perfect perfume or cologne for a casual meetup?",
            "Who is most likely to have a secret folder of screenshots containing spicy texts they received months ago?",
            "Who is most likely to get easily manipulated just because someone called them a good boy or good girl?",
            "Who is most likely to make a total scene at a bar after catching their casual link with someone else?",
            "Who is most likely to have an incredibly wild bucket list that they will never actually show anyone?"
        ]

    # Added: channel argument (discord.TextChannel = None) so !badpeople #channel triggers the lobby branch
    @commands.command(aliases=['who', 'bp', 'badpeople'])
    async def whois(self, ctx, channel: discord.TextChannel = None):
        """The ultimate NSFW 'Who is most likely to...' game."""
        prompt = random.choice(self.prompts)
        
        embed = discord.Embed(
            title="😈 Bad People Protocol | #1",
            description=f"**{prompt}**\n\n👇 *Tag the guilty party below. Don't be shy.*",
            color=self.color_sassy
        )
        
        # Adding a sassy footer
        embed.set_footer(text=f"Requested by {ctx.author.display_name} • Let the drama begin.", icon_url=ctx.author.display_avatar.url)
        
        # Adding the lobby image if it exists, matching your main bot aesthetic
        import os
        
        # Added: Branching logic for when a channel is targeted
        if channel:
            view = BadPeopleLobby(self.prompts, self.color_sassy, prompt_number=1, last_prompt=prompt)
            if os.path.exists("LobbyTopRight.jpg"):
                embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
                file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
                await channel.send(file=file, embed=embed, view=view)
            else:
                await channel.send(embed=embed, view=view)
            
            await ctx.send(f"✅ Bad People lobby opened in {channel.mention}")
        else:
            if os.path.exists("LobbyTopRight.jpg"):
                embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
                file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
                await ctx.send(file=file, embed=embed)
            else:
                await ctx.send(embed=embed)

    # Added: Command to check the stats
    @commands.command(aliases=['bpstats', 'badpeoplestats'])
    async def bad_people_stats(self, ctx):
        """Shows the all-time leaderboard of who gets tagged the most."""
        try:
            with open("badpeople_stats.json", "r") as f:
                stats = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            await ctx.send("No stats have been recorded yet!")
            return
            
        if not stats:
            await ctx.send("No stats have been recorded yet!")
            return
            
        # Sort by wins descending
        sorted_stats = sorted(stats.items(), key=lambda x: x[1]['wins'], reverse=True)
        
        description = ""
        for index, (user_id, data) in enumerate(sorted_stats[:10]): # Top 10
            description += f"**{index + 1}.** {data['name']} - {data['wins']} times\n"
            
        embed = discord.Embed(
            title="😈 Bad People - All-Time Hall of Shame",
            description=description,
            color=self.color_sassy
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['bphelp', 'bplist', 'bpc'])
    async def bp_commands(self, ctx):
        """Displays a list of commands available in the Bad People module."""
        embed = discord.Embed(
            title="😈 Bad People - Commands List",
            description="Here are the commands you can use in this module:",
            color=self.color_sassy
        )
        
        embed.add_field(
            name="`!whois` (Aliases: `!who`, `!bp`, `!badpeople`)", 
            value="The ultimate NSFW 'Who is most likely to...' game. Generates a random spicy prompt.", 
            inline=False
        )
        embed.add_field(
            name="`!whois #channel` (Or: `!badpeople #channel`)", 
            value="Opens a continuous interactive lobby in the tagged channel with a 'Next' button.", 
            inline=False
        )
        embed.add_field(
            name="`!bpstats` (Aliases: `!badpeoplestats`)", 
            value="Shows the all-time leaderboard of who gets tagged the most.", 
            inline=False
        )
        embed.add_field(
            name="`!bp_commands` (Aliases: `!bphelp`, `!bplist`, `!bpc`)", 
            value="Displays this list of commands.", 
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(BadPeople(bot))
    print("✅ LOG: BadPeople (NSFW Who is Most Likely) Module ONLINE.")
