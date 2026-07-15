import random
import logging
from typing import List, Optional

# Configuração de Logger para sincronização e rastreio de geração de texto
logger = logging.getLogger("SyndicateLexicon")

class PartnersInCrimeLexicon:
    def __init__(self) -> None:
        # 1. Sentenças Gerais de Combate (Retornam exatamente 1 única frase combinando a ação completa)
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

        # 2. Decretos de Strip / Humilhação Extrema
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
        Gera uma narrativa de combate dinâmica de exatamente UMA frase coesa.
        """
        w_name = winner_name if winner_name else "Reigning Partner"
        l_name = loser_name if loser_name else "Defeated Outlaw"

        try:
            # Seleciona exatamente 1 frase da lista combinada
            action = random.choice(self.actions).format(loser=l_name)
            return f"💥 **{w_name}** {action}!"
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
