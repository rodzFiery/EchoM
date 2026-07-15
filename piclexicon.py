import random
import logging
from typing import List, Optional

# Configuração de Logger para sincronização e rastreio de geração de texto
logger = logging.getLogger("SyndicateLexicon")

class PartnersInCrimeLexicon:
    def __init__(self) -> None:
        # 1. Fase de Encontro Inicial (Dark Alley Encounters)
        self.encounters: List[str] = [
            "corners {loser} against a graffiti-stained wall in a pitch-black dead end...",
            "blindsides {loser} right outside the active heist grid, ripping away their tactical comms...",
            "intercepts {loser} as they attempt to drag their heavy vault bags to the extraction vehicle...",
            "glares down {loser} with pure predatory lust beneath the flickering pink neon light...",
            "cuts off the exit gate, forcing {loser} to back up into a tight, cage-like loading dock...",
            "ambushes {loser} while they are completely distracted, bent over hacking the biometric vault terminal...",
            "shoves {loser} hard onto the damp asphalt, stepping heavily onto their chest...",
            "catches {loser} off-guard during a desperate escape sprint, tackling them straight to the floor...",
            "corrupts {loser}'s safe route, blocking their path with loaded shotguns and handcuffs...",
            "pins {loser} face-first against a rusty steel shipping container..."
        ]

        # 2. Fase de Ataque (Aggressive NSFW Strikes)
        self.attacks: List[str] = [
            "rips off their protective body armor, exposing their shivering bare chest",
            "strips away their primary weapon holster, leaving them entirely defenseless and exposed",
            "unleashes a painful volley of rubber-coated riot rounds straight to their thighs",
            "swipes low with a cold titanium blade, slicing cleanly through their leather cargo pants",
            "tears off their tactical utility belt, scattering their keys and tools across the wet ground",
            "grabs them roughly by the collar, forcing them onto their knees in complete submission",
            "disarms them completely with a brutal, knee-to-gut takedown",
            "presses a hot gun barrel directly against their exposed throat",
            "slams a gold-plated crowbar into their armor plates, shattering their defenses to pieces",
            "shoves an EMP device down their pants, causing absolute chaotic static shocks"
        ]

        # 3. Fase de Defesa (Defense & Counter Struggles)
        self.defenses: List[str] = [
            "forcing them to whimper and plead for a split-second mercy!",
            "leaving them completely bare, trembling under the dark syndicate night!",
            "nearly tearing their remaining undergarments to absolute shreds!",
            "making them gasping for air as their hands are pinned tightly behind their back!",
            "forcing them to surrender their weapons and show their dirty, illicit crimes!",
            "screaming in desperate panic as they try to cover their exposed body!",
            "leaving them shivering, exposed, and vulnerable to any penalty!",
            "letting out an embarrassing gasp as all their armor layers fall away!",
            "making them beg their partners for help that will absolutely never arrive!",
            "forcing them flat onto their belly, utterly surrendered on the concrete floor!"
        ]

        # 4. Fase de Transição (Environmental Transitions)
        self.evasions: List[str] = [
            "Vault alarm sirens blare loudly through the city, multiplying the hot tension.",
            "Heavy rain pours down, soaking their exposed skin as the countdown timer ticks.",
            "Neon lights flicker aggressively, painting their desperate struggle in deep shades of pink.",
            "The heavy scent of burnt currency, ozone, and wet asphalt hangs thick in the air.",
            "There is absolutely no honor left among outlaws in this locked-down cell block.",
            "The undercity surveillance cameras record every single second of their humiliating defeat.",
            "Syndicate guards watch from the shadows, laughing at the total lack of dignity.",
            "The cold steel of the cage blocks out any remaining dream of escape."
        ]

        # 5. Golpes de Misericórdia (Finisher Executions)
        self.finishers: List[str] = [
            "delivers a devastating point-blank strike, stripping away every single piece of their remaining clothes!",
            "snaps heavy iron handcuffs around their wrists, demanding their complete and total surrender!",
            "completely overpowers them, forcing them into a state of absolute, hot humiliation!",
            "neutralizes their escape plan, leaving them completely naked, stranded, and bound!",
            "claims their total syndicate tax, leaving them bruised, exposed, and entirely at their mercy!",
            "forces them to sign the final surrender contract with a gun pressed hard against their bare back!",
            "drag them kicking and screaming into the deep shadows of the syndicate prison cells!",
            "neutralizes their defenses completely, making them submit to the ultimate undercity exposure!"
        ]

        # 6. Decretos de Strip / Humilhação Extrema
        self.humiliations: List[str] = [
            "Your heist failed miserably. Take off every single piece of your clothes and pay the ultimate syndicate tax.",
            "Caught red-handed and totally bare. Shed your armor, show your dirty crimes, and submit right now.",
            "No honor among vault breakers. Strip down completely on the wet asphalt and expose your hot surrender.",
            "The Overlords have spoken. Hand over the loot, strip off those clothes, and bow down in complete shame.",
            "Partners in chains, partners in shame. The sirens are coming, and you are caught totally bare. Start stripping!",
            "The contract is signed and your bodies are owned. Strip down, kneel, and face your complete exposure.",
            "Your armor is ours, your pride is ours. Take off those clothes and let the entire undercity witness your shame."
        ]

    def generate_fight_flavor(self, winner_name: Optional[str], loser_name: Optional[str]) -> str:
        """
        Gera uma narrativa de combate dinâmica, brutal e temática de dominação 
        combinando múltiplos elementos do léxico. Protegido contra falhas de inputs nulos.
        """
        # Proteção Fallback caso o motor passe objetos vazios por erro de carregamento do Discord
        w_name = winner_name if winner_name else "Reigning Partner"
        l_name = loser_name if loser_name else "Defeated Outlaw"

        try:
            encounter = random.choice(self.encounters).format(loser=l_name)
            attack = random.choice(self.attacks)
            defense = random.choice(self.defenses)
            evasion = random.choice(self.evasions)
            finisher = random.choice(self.finishers)
            
            narrative = (
                f"💥 **{w_name}** {encounter}\n"
                f"⚡ **{w_name}** {attack}, {defense}\n"
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
