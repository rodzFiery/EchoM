import discord
from discord.ext import commands
import random
import os
from collections import Counter
import json # Required for saving data to a file

# Persistent view for the Lobby that never times out
class BadPeopleLobby(discord.ui.View):
    def __init__(self, prompts, color_sassy, prompt_number=1, last_prompt=None):
        super().__init__(timeout=None) # timeout=None prevents the view from expiring
        self.prompts = prompts
        self.color_sassy = color_sassy
        self.prompt_number = prompt_number
        self.last_prompt = last_prompt

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, custom_id="bp_persistent_next", emoji="⏭️")
    async def next_prompt(self, interaction: discord.Interaction, button: discord.ui.Button):
        # FIXED: Defer immediately at the top of the interaction loop to prevent 3-second gateway timeouts
        await interaction.response.defer()

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
                
                # Saving the winner to a persistent JSON file
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
        
        # FIXED: Passes the tracking counter state context down into the new view constructor cleanly so it never resets
        new_view = BadPeopleLobby(self.prompts, self.color_sassy, prompt_number=next_number, last_prompt=new_prompt)
        await interaction.channel.send(embed=embed, view=new_view)


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

    @commands.command(aliases=['who', 'bp', 'badpeople'])
    async def whois(self, ctx, channel: discord.TextChannel = None):
        """The ultimate NSFW 'Who is most likely to...' game."""
        prompt = random.choice(self.prompts)
        
        embed = discord.Embed(
            title="😈 Bad People Protocol | #1",
            description=f"**{prompt}**\n\n👇 *Tag the guilty party below. Don't be shy.*",
            color=self.color_sassy
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name} • Let the drama begin.", icon_url=ctx.author.display_avatar.url)
        
        import os
        
        # FIXED: Injected view payload calls to all text message routes so single triggers can transition into fully automated multi-round game loops
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
            # FIXED: Attached functional interactive instances right here to prevent standard executions from hitting a progression block
            view = BadPeopleLobby(self.prompts, self.color_sassy, prompt_number=1, last_prompt=prompt)
            if os.path.exists("LobbyTopRight.jpg"):
                embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
                file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
                await ctx.send(file=file, embed=embed, view=view)
            else:
                await ctx.send(embed=embed, view=view)

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
