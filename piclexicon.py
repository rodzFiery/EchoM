import random
import logging
from typing import List, Optional

# Configuração de Logger para sincronização e rastreio de geração de texto
logger = logging.getLogger("SyndicateLexicon")

class PartnersInCrimeLexicon:
    def __init__(self) -> None:
        # 1. Ações Diretas de Dominação & Submissão (Sentenças Gerais de Combate)
        self.actions: List[str] = [
            "shoves {loser} roughly onto the soft leather mattress, securing their wrists high above their head while they plead for mercy",
            "blindsides {loser} near the St. Andrew's cross, snapping a heavy padded leather collar shut around their neck with an ominous click",
            "corners {loser} against the mirrored wall of the dungeon, stripping away their lace harness to expose their shivering skin",
            "glares down {loser} beneath the dim red lights, forcing them onto their knees in complete, trembling submission",
            "pins {loser} face-first against the cold steel suspension frame, completely trapping them with swift rope wraps",
            "catches {loser} off-guard, sliding a smooth silicone ball gag between their lips to muffle their breathless gasps",
            "unleashes a stinging volley of leather crop strikes straight to {loser}'s thighs, breaking their stubborn willpower",
            "disarms {loser}'s resistance completely with a tight, inescapable velvet harness that forces their chin upward",
            "lures {loser} onto the heavy suspension platform, locking their ankle cuffs to the floor rings to take away all control",
            "slams a heavy leather paddle onto {loser}'s bare skin, leaving them writhing in helpless pleasure on the rug",
            "unbuckles {loser}'s leather corset, leaving their chest completely bare and exposed to the cool air of the chamber",
            "traces a cold metal flogger slowly along {loser}'s ribs, sending intense shivers of anticipation down their spine",
            "forces {loser} down onto the custom velvet kneeling cushion, securing their hands behind their back with silk ties",
            "tears away {loser}'s delicate lace top, leaving them completely bare and flushing red under the red chandelier",
            "runs a cold ice cube slowly down {loser}'s spine, forcing a broken, high-pitched whimper from their lips",
            "traps {loser} inside the padded sensory cage, locking their wrists behind them with absolute playroom authority",
            "squeezes a pair of soft velvet-lined clamps onto {loser}'s sensitive areas, completely shattering their sensory defenses",
            "locks {loser}'s fingers in heavy leather mitts, leaving them totally defenseless and at the mercy of their Master",
            "applies a drop of warm, skin-safe lavender wax directly onto {loser}'s bare shoulder, making them gasp dramatically",
            "pulls {loser}'s collar leash with sudden force, dragging them flat onto the leather spanking bench in submission",
            "slides a thick leather blindfold over {loser}'s eyes, plunging their world into complete, helpless sensory darkness",
            "runs a cold metal wheel over {loser}'s warm, exposed stomach, raising goosebumps along their sensitive skin",
            "tightens the ropes around {loser}'s thighs, forcing them to hold a vulnerable, submissive kneeling posture",
            "rips off {loser}'s satin undershirt, leaving them standing naked and trembling under the glaring spotlight",
            "shackles {loser}'s wrists to the heavy wooden pillory, completely neutralizing any remaining hope of escape",
            "subdues {loser} beneath the soft glow of the hanging chandelier, forcing them to surrender their pride on all fours",
            "unleashes a rhythmic spanking with a wide wooden ruler across {loser}'s rear, leaving a warm red glow behind",
            "pins {loser} to the padded examination table, securing their ankles to the steel stirrups in complete exposure",
            "runs a soft fur whip slowly along {loser}'s spine, sending intense shivers through their body to their hips",
            "tightens the leather handcuffs around {loser}'s wrists, completely restricting their movement to absolute zero",
            "strips away {loser}'s silk underwear with a decisive pull, exposing their bound posture in the playroom mirror"
        ]

        # 2. Transições Ambientais (Environmental Transitions)
        self.evasions: List[str] = [
            "Low-frequency dungeon music echoes through the chamber, multiplying the hot tension.",
            "Warm wax drops slowly from the ceiling candles, keeping their exposed skin highly sensitive.",
            "Deep crimson lights pulse aggressively, painting their desperate struggles in shades of ruby and pink.",
            "The heavy scent of premium leather, lavender oil, and heated skin hangs thick in the air.",
            "There is absolutely no escape left for submissives once the dungeon door is locked from the outside.",
            "The multi-angle security cameras record every single second of their delicious, humiliating defeat.",
            "Dominants watch from behind the tinted glass, whispering and laughing at the total lack of dignity.",
            "The cold steel of the wrist shackles cuts off any remaining illusion of control.",
            "Thick steam escapes from the underground heating pipes, covering their bound bodies in hot, damp mist.",
            "The intercom cracks with static as the master of ceremonies announces the next playtime rotation.",
            "The main dungeon lights fade out completely, leaving them illuminated only by the warm glow of wax candles.",
            "A heavy leather curtain sweeps closed across the play area, isolating them from the rest of the club.",
            "Heavy bass rumbles from the dance floor upstairs, shaking the timber foundations of the private playroom.",
            "The soft chime of a brass bell echoes through the hall, signaling that their time of submission has begun.",
            "A cool draft sweeps through the dungeon floor, making their exposed, damp skin shiver intensely.",
            "The low hum of the air ventilation system keeps the scent of leather and oil circulating through the room.",
            "A red laser line sweeps across the floor, marking the boundary of the master's private play space.",
            "The distinct sound of a leather whip cracking in the adjacent room raises the tension to its peak.",
            "Soft classical music begins to play from the hidden speakers, contrastingly highlighting their heavy gasps.",
            "The clicking sound of a high heel heel on the concrete floor echoes, signaling the master's approach.",
            "Damp mist rises from the floor drains, wrapping their bound legs in a thin, cold fog."
        ]

        # 3. Golpes de Misericórdia (Finisher Executions)
        self.finishers: List[str] = [
            "delivers a devastating flurry of flogger strikes, stripping away every single piece of their remaining garments!",
            "snaps heavy steel padlocks around their wrist chains, demanding their complete and absolute surrender!",
            "completely overpowers their senses, forcing them into a state of absolute, heavy subspace!",
            "neutralizes their desperate struggle, leaving them completely naked, bound, and blindfolded!",
            "claims their total sensory tribute, leaving them breathless, exposed, and entirely at their Master's mercy!",
            "forces them to sign the submissive contract with a cold metal whip handle pressed hard against their bare back!",
            "drags them kicking and whimpering into the dark VIP playroom for their private punishment!",
            "neutralizes their defenses completely, making them submit to the ultimate, breathless dungeon exposure!",
            "shackles their ankles to the steel suspension ring, leaving them completely bare and suspended in the air!",
            "locks a heavy leather posture collar around their neck, claiming absolute playroom ownership over their body!",
            "slams their hands into the matching wall restraints, forcing them to watch their own naked surrender in the mirror!",
            "confiscates all their remaining clothing and pride, leaving them stripped, bound, and kneeling on the rug!",
            "marks their bare, flushed skin with a soft, warm wax seal of complete submissive dedication!",
            "forces them to bow down before the master's throne, placing a heavy leather boot on their bound hands!",
            "locks them in the iron playroom cage, leaving them completely exposed to any passing dungeon guest!"
        ]

        # 4. Decretos de Strip / Humilhação Extrema
        self.humiliations: List[str] = [
            "Your resistance failed miserably. Shed every single piece of your clothing and accept your ultimate dungeon punishment.",
            "Caught red-handed and totally defenseless. Strip off your armor, show your submission, and kneel right now.",
            "No mercy for disobedient pets. Strip down completely on the cold leather mattress and expose your hot surrender.",
            "The Dominants have spoken. Hand over your pride, strip off those clothes, and bow down in complete submission.",
            "Bound in chains, bound in shame. The Master is coming, and you are caught totally bare. Start stripping!",
            "The playroom contract is signed and your body is owned. Strip down, kneel, and face your complete exposure.",
            "Your clothing is ours, your submission is ours. Take off those garments and let the chamber witness your sweet shame."
        ]

    def generate_fight_flavor(self, winner_name: Optional[str], loser_name: Optional[str]) -> str:
        """
        Gera uma narrativa de combate dinâmica, brutal e temática de dominação 
        combinando múltiplos elementos do léxico. Protegido contra falhas de inputs nulos.
        """
        w_name = winner_name if winner_name else "Reigning Partner"
        l_name = loser_name if loser_name else "Defeated Outlaw"

        try:
            # Seleciona uma única sentença geral de ação (combinando ataque e submissão)
            action = random.choice(self.actions).format(loser=l_name)
            evasion = random.choice(self.evasions)
            finisher = random.choice(self.finishers)
            
            narrative = (
                f"💥 **{w_name}** {action}.\n"
                f"🚨 *{evasion}*\n"
                f"👑 **{w_name}** {finisher}"
            )
            return narrative
        except Exception as e:
            logger.error(f"Failed to generate combat narrative: {e}")
            return f"💥 **{w_name}** completely overpowers **{l_name}** in a brutal showdown, claiming absolute victory!"

    def get_random_humiliation(self) -> str:
        """Retorna uma frase altamente temática de strip/humilhação do banco de dados."""
        try:
            return random.choice(self.humiliations)
        except Exception as e:
            logger.error(f"Failed to fetch random humiliation: {e}")
            return "Your heist failed. Pay the ultimate tax of complete exposure!"
