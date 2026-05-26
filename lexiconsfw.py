import random

class FieryLexiconSFW:
    # ⚔️ INTRODUÇÕES DA ARENA (Funny & Slapstick Combat Atmosphere)
    INTRO_MESSAGES = [
        "⚔️ **The arena gates creak open. Someone is definitely going to trip over their own shoelaces.**",
        "⚔️ **The crowd is ready, the popcorn is buttery, and the fighters are... confused. Let the chaos begin!**",
        "⚔️ **Lace up your boots, grab your snacks, and prepare for some delightfully clumsy combat.**",
        "⚔️ **The arena floor is freshly mopped. Expect a lot of sliding and accidental flailing.**",
        "⚔️ **The Master has signaled the start. May the funniest fighter win (or at least provide good entertainment).**",
        "⚔️ **Total hilarity or total face-planting bliss. The games have begun.**",
        "⚔️ **Whispers of tactical genius echo, but mostly it's just 'where did I put my sword?'**",
        "⚔️ **The blindfolds are locked—wait, why are they wearing blindfolds? Never mind, this is funnier.**",
        "⚔️ **Bound by friendship and fueled by sheer clumsiness, the tributes begin their descent into the arena.**",
        "⚔️ **A heavy silence falls as everyone tries to look cool and fails. Let the slapstick flow.**",
        "⚔️ **The scent of adrenaline and spilled soda fills the air. The hunt for glory is on.**",
        "⚔️ **No shy looks here. Only the sweet, desperate release of the final, accidental victory.**",
        "⚔️ **The suite is sealed. Only one will walk out with their dignity fully intact.**",
        "⚔️ **The smell of expensive sweat and popcorn permeates. The Master watches from the shadows, giggling.**",
        "⚔️ **Kneel or be tickled. The Arena combat protocol is now in effect.**",
        "⚔️ **The floor is cold, but the eyes watching your flailing limbs are burning with amusement.**",
        "⚔️ **A rhythmic clicking of shields signals your arrival. Choose your side or just run around in circles.**",
        "⚔️ **The air is thick with excitement. And maybe a little bit of nervous energy.**",
        "⚔️ **Every wooden sword has a story, and tonight, you will write a new chapter in tactical blunders.**",
        "⚔️ **The Master’s favorite shield is missing. One of you will have to use a frying pan tonight.**",
        "⚔️ **The velvet curtains part to reveal a floor stained with the sweat of past, extremely awkward duels.**",
        "⚔️ **The arena floor groans under the weight of incoming combatants. Let the tomfoolery begin.**",
        "⚔️ **The dungeon is hungry for your best impressions. Open wide and let the show commence.**",
        "⚔️ **Submit your pride, for it will be hilariously shattered before the night is over.**",
        "⚔️ **Each of you is a gorgeous, clumsy fighter waiting to be used and discarded.**",
        "⚔️ **The arena rack is waiting, and your body is the canvas for tonight’s comedic art.**",
        "⚔️ **The Master wants to hear you cheer until your throat hurts. Start your performance.**",
        "⚔️ **Your secrets are safe, but your clumsy combat history is not. Arena Protocol is live.**",
        "⚔️ **The smell of effort and bad aim is the only perfume this arena accepts.**",
        "⚔️ **Surrender your control to the Master’s grip. Let the agonizingly funny combat begin.**",
        "⚔️ **Every swing you take is now on loan. Use it to look as dramatic as possible.**",
        "⚔️ **Expose your most vulnerable spots. The Voyeurs are watching with heavy anticipation.**",
        "⚔️ **Prepare for a session of pure, unadulterated combat and total silliness.**",
        "⚔️ **The Master loves a fighter that fights back—briefly. It makes the stumbling sweeter.**",
        "⚔️ **Strip yourself bare of pretense. Here, you are just a target for the Master's amusement.**",
        "⚔️ **This is not a game, it's a conquest. Who will be the first to trip for us?**",
        "⚔️ **The Arena is a playground for your clumsiest, nastiest urges.**",
        "⚔️ **You were bred for this. Now show the Master why you’re worth the ticket price.**",
        "⚔️ **A symphony of clanking armor and gasps awaits. Let the rhythm of the fall take you.**",
        "⚔️ **Your confusion is the only currency here. Spend it all.**",
        "⚔️ **Every inch of this arena is stained with the sweat of someone who gave up and took a nap.**",
        "⚔️ **The darkness is a womb. Let it swallow you whole while you flail your arms.**",
        "⚔️ **Your heart is beating against the bars. Don’t stop now, it’s beautiful and hilarious.**",
        "⚔️ **A feast of courage and fire. Who is the first on the menu?**",
        "⚔️ **The Master demands a perfect display of competition. Don't disappoint the audience.**",
        "⚔️ **The Arena doesn’t forgive. It only forgets the broken, clumsy heroes.**"
    ]

    OPENERS = [
        "**{winner}** gripped the shield of **{loser}** until they gasped and stumbled,", 
        "With a look of absolute focus, **{winner}** pinned **{loser}**'s wrists over their head with a laugh,",
        "**{winner}** cornered **{loser}** against the wall, forcing them into a very awkward hug,", 
        "Relishing the tension, **{winner}** straddled **{loser}** but accidentally tickled them,",
        "**{winner}** forced **{loser}** into a state of total, shivering sensory amusement,", 
        "**{winner}** tightened the heavy leather harness on **{loser}**, pulling their chin up for a dramatic pose,",
        "Without a shred of hesitation, **{winner}** dominated every move of **{loser}** until they fell,", 
        "**{winner}** whispered a forbidden, hilarious secret into **{loser}**'s reddened ear,",
        "Dominating the mood, **{winner}** shoved **{loser}** onto the cushions and started a pillow fight,", 
        "**{winner}** saw the raw, funny determination in **{loser}**'s eyes and decided to play tag,",
        "**{winner}** pinned **{loser}** down, exposing their neck to a dramatic poke,", 
        "**{winner}** stepped over the trembling, exposed and flushed body of **{loser}** and tripped,",
        "**{winner}** yanked the hair of **{loser}** back, forcing them to look at their own reflection,", 
        "**{winner}** loomed over the helpless, gasping **{loser}** like a very hungry, very clumsy lover,",
        "**{winner}** wrapped a heavy, ice-cold chain around **{loser}**'s waist, causing them to clank loudly,",
        "**{winner}** forced **{loser}** to their knees with a sharp, teasingly slow tug,",
        "**{winner}** traced the fresh marks on **{loser}**'s heated skin before giggling,", 
        "**{winner}** ignored the muffled, desperate protests of **{loser}** and continued the dance,",
        "**{winner}** tightened the heavy, velvet-lined collar on **{loser}** while they squeaked,",
        "**{winner}** applied a playful, breathless pressure to **{loser}**'s flushed shoulder,",
        "**{winner}** trapped **{loser}** in a predatory, heated embrace, tasting their hilarious fear,",
        "**{winner}** used the weight of a heavy gaze to paralyze **{loser}**'s aching body,",
        "**{winner}** clicked a padlock shut on **{loser}**'s heavy iron collar forever (or until they find the key),",
        "**{winner}** snatched the last safe-word from **{loser}**'s lips with a deep kiss and a smirk,",
        "**{winner}** forced **{loser}** to stare at the Master during their final defeat,",
        "**{winner}** spread **{loser}** across the X-frame with terrifying, expert speed,",
        "**{winner}** clamped a heavy blindfold over **{loser}**'s eyes, then started making spooky ghost noises,",
        "**{winner}** pressed a vibrating toy against **{loser}**'s most sensitive, hidden funny bone,",
        "**{winner}** forced a heavy, polished metal bit between **{loser}**'s teeth so they couldn't bite the lube bottle,",
        "**{winner}** dripped hot, stinging lavender wax over the trembling chest of **{loser}**, causing them to jump,",
        "**{winner}** locked **{loser}** into a restrictive, full-body, skin-tight latex suit,",
        "**{winner}** hooked a heavy weight to the silver nipple clamps on **{loser}**, causing a very dramatic pose,",
        "**{winner}** bound **{loser}** in a complex, painfully beautiful rope harness,",
        "**{winner}** forced **{loser}** to lick the salt from their dominant, sweating palm,",
        "**{winner}** used a small spark to send a jolt of pure compliance through **{loser}**, making them hop,",
        "**{winner}** locked **{loser}** into a tight, exposed position with steel cables,",
        "**{winner}** suspended **{loser}** from the ceiling, leaving them spinning and helpless like a top,",
        "**{winner}** forced **{loser}** to crawl toward them while wearing a heavy bit-gag,",
        "**{winner}** applied a high-tension, silver clamp to **{loser}**’s tongue,",
        "**{winner}** dragged **{loser}** across the rough floor by their heavy, short iron leash,",
        "**{winner}** used a feather to slowly trace the sensitive veins on **{loser}**’s thigh until they kicked,",
        "**{winner}** forced **{loser}** to worship their boots while gasping for their next breath,",
        "**{winner}** locked **{loser}** into a sensory-deprivation hood and spun them into a daze,",
        "**{winner}** pressed a hot brand against **{loser}**’s shoulder to mark their prize,",
        "**{winner}** utilized a spreader-bar to keep **{loser}**’s legs wide and waiting,",
        "**{winner}** whispered the names of all **{loser}**’s past silly fantasies while striking them,",
        "**{winner}** forced **{loser}** to hold a heavy crystal between their teeth while kneeling,",
        "**{winner}** applied a row of steel needles to the most sensitive skin of **{loser}**, causing a very tiny shriek,",
        "**{winner}** used a vacuum pump to swell **{loser}**’s parts to an agonizing, comic size,",
        "**{winner}** locked **{loser}** into a heavy wooden stockade, exposing them to the pit,",
        "**{winner}** shoved a thick, pulsing dildo into **{loser}**'s trembling depths,",
        "**{winner}** wrapped fingers tightly around **{loser}**'s throat until their pulse throbbed,",
        "**{winner}** bit into the soft skin of **{loser}**'s inner thigh until they cried out in amusement,",
        "**{winner}** used a leather crop to trace the outline of **{loser}**'s naked silhouette,",
        "**{winner}** pinned **{loser}**'s shoulders to the floor with raw, crushing weight,",
        "**{winner}** slid a cold, vibrating wand inside **{loser}** until they arched in pain and shock,",
        "**{winner}** yanked the chain of **{loser}**'s collar, forcing them to arch their back,",
        "**{winner}** dripped freezing water onto the feverish, red skin of **{loser}**,"
    ]

    ACTIONS = [
        "and delivered a teasing blow that made them moan in ecstasy as they", 
        "and ruthlessly broke their will until they begged for the final touch,",
        "and made them beg for more through the gag before they broke,", 
        "and administered a devastating, erotic punishment that melted them,",
        "and stripped away their resistance and their pride until they yielded,", 
        "and exerted absolute, carnal ownership until **{loser}** shattered,",
        "and dominated every sense and nerve ending until **{loser}** peaked,", 
        "and pulled the chains so tight that **{loser}**'s skin flushed and they",
        "and toyed with their body and their sanity until finally they", 
        "and marked them as a permanent, scarred asset for the Master before they",
        "and enforced the ultimate discipline until **{loser}**'s mind went blank,", 
        "and silenced their pleas with a kiss that stole their breath,",
        "and used them as a mere tool of pleasure until they gave up,", 
        "and exerted a crushing seductive weight that broke their spirit until they",
        "and demonstrated the complete futility of resistance until they fainted,",
        "and used a heavy, lead-weighted flogger to ensure **{loser}** surrendered,",
        "and extracted a final, desperate moan of total surrender before",
        "and corrected **{loser}**'s posture with a slap that made them weep,",
        "and humiliated **{loser}** in front of the hungry audience until they broke,",
        "and tightened the ropes until **{loser}**'s body groaned and they",
        "and applied a high-voltage sensor that overloaded **{loser}**'s nerves until",
        "and utilized a heavy cane to mark **{loser}** as a permanent asset until",
        "and stripped away every last layer of identity until **{loser}** belonged,",
        "and enforced a state of total sensory deprivation until **{loser}** lost time,",
        "and commanded the very air from **{loser}**'s lungs until they",
        "and utilized a dragon-tail whip to shred the last of their pride until",
        "and applied freezing ice to their most sensitive parts until **{loser}** arched,",
        "and forced them to swallow their own moans of pleasure-pain until",
        "and utilized a spreader bar to keep **{loser}** completely vulnerable until",
        "and administered a heavy, rhythmic spanking that reddened the skin until",
        "and used a vacuum-sealed bag to strip the very breath from **{loser}** until",
        "and forced a state of edge-torture that left **{loser}** weeping until",
        "and used a multi-tailed slapper to turn **{loser}**'s flesh crimson until",
        "and applied sensory-overload goggles that blinded and deafened them until",
        "and utilized a weighted piercing to ensure **{loser}** felt every move until",
        "and utilized a violet wand to send sparks of raw electricity through their body until",
        "and applied a high-frequency vibration that reduced them to a sobbing mess until",
        "and utilized a heavy paddle to leave the Master's signature in purple welts until",
        "and enforced a deep state of hypnosis that stripped their mind of everything until",
        "and utilized a set of steel fish-hooks to keep their skin taut until",
        "and applied a freezing chemical spray that turned their skin blue until",
        "and utilized a rhythmic, heavy bondage session that cut off all circulation until",
        "and enforced a public interrogation that revealed their dirtiest secrets until",
        "and utilized a heavy iron mask to silence their screams of pleasure until",
        "and applied a row of high-tension clips that made every movement an ordeal until",
        "and shoved them into a cage designed for someone half their size until",
        "and used a heavy, leather belt to bind them into a knot until",
        "and stripped away their ability to see, hear, or speak until",
        "and applied a painful, hot brand that permanently marked them until"
    ]

    FINISHERS = [
        "collapsed into eternal, silent submission.", 
        "ceased to struggle against the dark pleasure.",
        "faded into the shadows of the Arena forever.", 
        "became nothing more than a used plaything on the floor.",
        "succumbed completely to the Master's every whim.", 
        "broke apart like a fragile, beautiful toy.",
        "surrendered their very last breath to the shackle.", 
        "was extinguished in a flash of heat and lust.",
        "stopped breathing under the weight of the collar.", 
        "accepted the final, dark release of the dungeon.",
        "went limp in a state of total, blissful defeat.", 
        "folded like paper under the Master's heavy hand.",
        "became a permanent exhibit of the dungeon's archives.", 
        "lost all identity in the moment of final impact.",
        "was finally granted the mercy of the end.",
        "shattered into a thousand pieces of pure submission.",
        "finally let go of the last thread of hope.",
        "yielded their soul to the Arena's deepest depths.",
        "was left as a broken, beautiful, and empty mess.",
        "became another nameless trophy on the stone wall.",
        "melted into the floor in a puddle of spent desire.",
        "accepted the cold embrace of the permanent fighter list.",
        "was reduced to a quivering, silent memory.",
        "turned into a vacant vessel, pride completely hollowed out.",
        "sank into the abyss, leaving only the collar behind.",
        "was branded with the winner's mark and dragged to the kennels.",
        "became a mindless, drooling pet in the corner of the pit.",
        "was locked into a permanent chastity device and forgotten.",
        "yielded their safe-word and their soul to the victor.",
        "was reduced to a quivering heap of spent nerves and leather.",
        "became a permanent fixture of the Master's private collection.",
        "fainted from the overwhelming intensity of the final strike.",
        "was left bound and gagged, a silent warning to the next fighter.",
        "accepted the heavy crown of thorns as their final prize.",
        "dissolved into a mess of tears and complete, broken worship.",
        "was locked into an airtight box to be used at the winner's convenience.",
        "turned into a literal piece of furniture in the winner's private lounge.",
        "was stripped of their safe-word and granted as a permanent gift to the Master.",
        "melted into a pool of pure, mindless obedience under the victor's heel."
    ]

    FINAL_KILL_MESSAGES = [
        "👑 **THE CLIMAX:** **{winner}** forced **{loser}** into the ultimate surrender, claiming the throne of the Arena!",
        "👑 **TOTAL DOMINATION:** **{winner}** broke **{loser}** completely, standing alone as the Absolute Authority!",
        "👑 **THE END:** **{winner}** tightened the final chain on **{loser}**, savoring the victory of the Eternal Possession!",
        "👑 **FINAL AUTHORITY:** **{winner}** silenced the last rival **{loser}**, ascending as the Dark Sovereign!",
        "👑 **CROWNED IN SHAME:** **{winner}** stands over the broken body of **{loser}**, the only one left standing!",
        "👑 **THE MASTER'S CHOSEN:** **{winner}** crushed the throat of **{loser}**, proving who truly owns the arena!",
        "👑 **BEYOND REPAIR:** **{winner}** dismantled **{loser}** in front of the Master, securing total victory!",
        "👑 **ULTIMATE PROTOCOL:** **{winner}** locked the final shackle on **{loser}**, welding their legacy into the arena walls!",
        "👑 **THE LAST WORD:** **{winner}** made **{loser}** whisper their name in worship before the final lights went out!",
        "👑 **SOVEREIGN CLIMAX:** **{winner}** stands upon the wreckage of **{loser}**'s soul, the Absolute King of the Abyss!",
        "👑 **THE SEALED FATE:** **{winner}** burned their mark into **{loser}**, ending the game with a display of pure ownership!"
    ]

    WINNER_PINGS = [
        "📢 Attention please: Fighter {mention} has successfully broken every rival and won this Echo Hangrygames Edition! Kneel before your new Authority.",
        "📢 The Arena has spoken! {mention} has claimed total dominion over the floor. Tributes, acknowledge your superior.",
        "📢 A new Master of the pit arises! {mention} stands alone, covered in the submission of their rivals. Glory to the victor.",
        "📢 The chains have settled. {mention} is the last one standing in this Echo Hangrygames Edition! Absolute possession achieved.",
        "📢 Final report: Fighters discarded. Rivals broken. {mention} has been declared the Supreme Asset of the arena!"
    ]

    LEGENDARY_EVENTS = [
        "⛓️ **THE GREAT RESTRAINT:** A massive web of silk dropped! **{losers}** were caught and shocked into a permanent state of breathless bliss!",
        "💦 **THE SERUM LEAK:** An aphrodisiac gas flooded the chambers! **{losers}** lost all sense of self and surrendered to the arena's hunger!",
        "🔞 **THE MASTER'S WHIM:** The lights flickered as the Master entered personally. With a single snap, **{losers}** were discarded as unworthy!",
        "🫦 **THE OVERWHELMING SENSATION:** A sensory overload frequency blasted. **{losers}** collapsed in a heap of shattered nerves!",
        "⛓️ **THE SATIN CIRCLE:** Soft but unbreakable binds emerged. **{losers}** were trapped and overwhelmed by sensation!",
        "🔞 **PUBLIC DISGRACE:** The Master commanded the audience to take their turn. **{losers}** were dragged into the shadows forever!",
        "💦 **THE FLOOD OF LUST:** The arena was submerged in slick oil. **{losers}** couldn't find their footing and were suffocated by pleasure!",
        "⛓️ **THE PREDATOR'S WEB:** The floor turned into a giant magnet! **{losers}** in metal gear were slammed together into a singular mass!",
        "🧪 **THE OBLIVION DRIP:** A rain of numbing liquid fell! **{losers}** lost all feeling and were dragged into the dark!",
        "🔞 **THE CAGE COLLAPSE:** The ceiling lowered! **{losers}** were flattened into the arena floor, their marks becoming part of the architecture!"
    ]

    @classmethod
    def get_intro(cls): 
        if not cls.INTRO_MESSAGES: return "⚔️ **The Arena opens.**"
        return random.choice(cls.INTRO_MESSAGES)

    @classmethod
    def get_kill(cls, winner, loser, is_final=False):
        try:
            if is_final: 
                if not cls.FINAL_KILL_MESSAGES: return f"👑 **Winner:** {winner}"
                return random.choice(cls.FINAL_KILL_MESSAGES).format(winner=winner, loser=loser)
            
            if not (cls.OPENERS and cls.ACTIONS and cls.FINISHERS):
                return f"⚔️ {winner} defeated {loser}."
                
            o = random.choice(cls.OPENERS).format(winner=winner, loser=loser)
            a = random.choice(cls.ACTIONS).format(winner=winner, loser=loser)
            f = random.choice(cls.FINISHERS).format(winner=winner, loser=loser)
            return f"🔥 {o} {a} {f}"
        except Exception: 
            return f"⚔️ {winner} defeated {loser}."

    @classmethod
    def get_legendary_event(cls, losers_names):
        try: 
            if not cls.LEGENDARY_EVENTS: return "⚠️ A chaotic event cleared several fighters."
            return random.choice(cls.LEGENDARY_EVENTS).format(losers=", ".join(str(l) for l in losers_names))
        except Exception:
            return "⚠️ A chaotic event cleared several fighters."

    @classmethod
    def get_winner_announcement(cls, mention):
        try: 
            if not cls.WINNER_PINGS: return f"🏆 {mention} has won!"
            return random.choice(cls.WINNER_PINGS).format(mention=mention)
        except Exception:
            return f"🏆 {mention} has won the Echo Hangrygames Edition!"
