import sqlite3
import random
import logging
from typing import Dict, List, Optional, Tuple

# Logger Configuration for synchronization and tracing text generation
logger = logging.getLogger("DungeonPets")

# ==============================================================================
# PET DATABASE CONFIGURATION & METRICS
# ==============================================================================

PET_TEMPLATES = {
    "Basic": {
        "luck_boost": 0.03, # SYNCHRONIZED: 3% chance to avoid First Blood
        "names": ["Toy Slave", "Chained Pup", "Leather Mouse", "Floor Crawler", "Whispering Parrot"]
    },
    "Normal": {
        "luck_boost": 0.05, # SYNCHRONIZED: 5% chance
        "names": ["Cell Warden", "Paddle Cat", "Whip Badger", "Key Snatcher", "Collar Guardian"]
    },
    "Rare": {
        "luck_boost": 0.10, # SYNCHRONIZED: 10% chance
        "names": ["Spanking Rabbit", "Masked Ferret", "Dungeon Lynx", "Silk Spider", "Wax Raven"]
    },
    "Epic": {
        "luck_boost": 0.15, # SYNCHRONIZED: 15% chance
        "names": ["Gagged Panther", "Bondage Cobra", "Velvet Fox", "Throne Gargoyle", "Shackle Falcon"]
    },
    "Legendary": {
        "luck_boost": 0.20, # SYNCHRONIZED: 20% chance
        "names": ["Leather Dragon", "Dominant Chimera", "Submissive Phoenix", "Mistress Basilisk", "Iron Cerberus"]
    },
    "Supreme": {
        "luck_boost": 0.30, # SYNCHRONIZED: 30% chance to save owner from first blood
        "names": ["The Dungeon Overlord", "The Leather Monarch", "Kinky Leviathan", "The Supreme Dominator", "Grand Master Beast"]
    }
}

DROP_CHANCES = {
    "Basic": 0.40,       # SYNCHRONIZED: 40% chance after drop confirmation
    "Normal": 0.30,      # SYNCHRONIZED: 30% chance
    "Rare": 0.15,        # SYNCHRONIZED: 15% chance
    "Epic": 0.09,        # SYNCHRONIZED: 9% chance
    "Legendary": 0.05,   # SYNCHRONIZED: 5% chance
    "Supreme": 0.01      # SYNCHRONIZED: 1% chance
}

class DungeonPetsManager:
    def __init__(self, get_db_connection) -> None:
        self.get_db_connection = get_db_connection
        self._init_db()

    def _init_db(self) -> None:
        """Initializes the user pets database table safely if it does not exist."""
        with self.get_db_connection() as conn:
            # We check if the existing table already has the correct composite Primary Key
            pk_columns = []
            try:
                cursor = conn.execute("PRAGMA table_info(user_pets)")
                cols = cursor.fetchall()
                for col in cols:
                    if col[5] > 0:
                        pk_columns.append(col[1])
            except Exception:
                pass

            # Rebuilds the table using backup migration if keys do not match
            if not pk_columns or set(pk_columns) != {"guild_id", "user_id", "pet_name"}:
                has_table = False
                try:
                    conn.execute("SELECT 1 FROM user_pets LIMIT 1")
                    has_table = True
                except sqlite3.OperationalError:
                    pass

                if has_table:
                    # Gather compatible columns from the old table
                    cursor = conn.execute("PRAGMA table_info(user_pets)")
                    existing_cols = [c[1] for c in cursor.fetchall()]
                    
                    conn.execute("DROP TABLE IF EXISTS user_pets_backup")
                    conn.execute("ALTER TABLE user_pets RENAME TO user_pets_backup")
                    
                    # Create the correct table structure
                    conn.execute("""
                        CREATE TABLE user_pets (
                            guild_id INTEGER,
                            user_id INTEGER,
                            pet_name TEXT,
                            rarity TEXT,
                            luck_boost REAL,
                            avatar_owner_id INTEGER,
                            avatar_owner_name TEXT,
                            PRIMARY KEY (guild_id, user_id, pet_name)
                        )
                    """)
                    
                    target_columns = ["guild_id", "user_id", "pet_name", "rarity", "luck_boost", "avatar_owner_id", "avatar_owner_name"]
                    common_cols = [col for col in target_columns if col in existing_cols]
                    
                    if "user_id" in common_cols:
                        select_statements = []
                        for col in common_cols:
                            select_statements.append(col)
                        
                        # Populate mandatory values for non-existent primary keys
                        if "guild_id" not in common_cols:
                            common_cols.append("guild_id")
                            select_statements.append("0 as guild_id")
                        if "pet_name" not in common_cols:
                            common_cols.append("pet_name")
                            select_statements.append("'Legacy Pet' as pet_name")
                            
                        insert_cols_str = ", ".join(common_cols)
                        select_cols_str = ", ".join(select_statements)
                        
                        try:
                            conn.execute(f"INSERT OR IGNORE INTO user_pets ({insert_cols_str}) SELECT {select_cols_str} FROM user_pets_backup")
                        except Exception as e:
                            logger.error(f"Error restoring old pets during migration in pets.py: {e}")
                    
                    conn.execute("DROP TABLE IF EXISTS user_pets_backup")
                else:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS user_pets (
                            guild_id INTEGER,
                            user_id INTEGER,
                            pet_name TEXT,
                            rarity TEXT,
                            luck_boost REAL,
                            avatar_owner_id INTEGER,
                            avatar_owner_name TEXT,
                            PRIMARY KEY (guild_id, user_id, pet_name)
                        )
                    """)
            conn.commit()

    def roll_pet_drop(self, participants_members: List[any]) -> Optional[Dict]:
        """
        Determines if a pet was dropped.
        MODIFICATION: Configured for 100% guaranteed drop chance for one of the winners of each match.
        Chooses a rarity, a random pet from templates, and a random participant to serve
        as the avatar/figure of the pet.
        """
        # FORCED: 100% pet drop chance per game. Previous 50% validation was removed.

        # Selects rarity based on adjusted relative probabilities
        rarities = list(DROP_CHANCES.keys())
        weights = list(DROP_CHANCES.values())
        chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

        # Selects a random name from that rarity
        chosen_template_name = random.choice(PET_TEMPLATES[chosen_rarity]["names"])
        luck_boost = PET_TEMPLATES[chosen_rarity]["luck_boost"]

        # Selects a participant from the lobby to become the pet's avatar
        if participants_members:
            chosen_member = random.choice(participants_members)
            avatar_owner_id = chosen_member.id
            avatar_owner_name = chosen_member.display_name
        else:
            avatar_owner_id = 0
            avatar_owner_name = "Mysterious Sub"

        # Final pet name fuses template name with the honored member's name
        final_pet_name = f"{chosen_template_name} ({avatar_owner_name})"

        return {
            "pet_name": final_pet_name,
            "rarity": chosen_rarity,
            "luck_boost": luck_boost,
            "avatar_owner_id": avatar_owner_id,
            "avatar_owner_name": avatar_owner_name
        }

    def save_user_pet(self, guild_id: int, user_id: int, pet_data: Dict) -> None:
        """Saves or updates the pet claimed by the winning user in the database."""
        with self.get_db_connection() as conn:
            conn.execute("""
                INSERT INTO user_pets (guild_id, user_id, pet_name, rarity, luck_boost, avatar_owner_id, avatar_owner_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, pet_name) DO UPDATE SET
                    luck_boost = excluded.luck_boost,
                    avatar_owner_id = excluded.avatar_owner_id,
                    avatar_owner_name = excluded.avatar_owner_name
            """, (
                guild_id,
                user_id,
                pet_data["pet_name"],
                pet_data["rarity"],
                pet_data["luck_boost"],
                pet_data["avatar_owner_id"],
                pet_data["avatar_owner_name"]
            ))
            conn.commit()

    def get_user_equipped_pets(self, guild_id: int, user_id: int) -> List[Dict]:
        """Retrieves the list of pets owned by the user on the server."""
        pets_list = []
        try:
            with self.get_db_connection() as conn:
                rows = conn.execute("""
                    SELECT pet_name, rarity, luck_boost, avatar_owner_id, avatar_owner_name
                    FROM user_pets
                    WHERE guild_id = ? AND user_id = ?
                """, (guild_id, user_id)).fetchall()
                for r in rows:
                    pets_list.append({
                        "pet_name": r[0],
                        "rarity": r[1],
                        "luck_boost": r[2],
                        "avatar_owner_id": r[3],
                        "avatar_owner_name": r[4]
                    })
        except Exception as e:
            logger.error(f"Error fetching equipped pets: {e}")
        return pets_list

    def calculate_total_luck(self, guild_id: int, user_id: int) -> float:
        """
        Calculates accumulated luck boost from all user pets.
        Capped at 85% maximum threshold to prevent game loop failure.
        """
        pets = self.get_user_equipped_pets(guild_id, user_id)
        if not pets:
            return 0.0
        
        # Accumulates luck values across all pets
        total_luck = sum(p["luck_boost"] for p in pets)
        return min(total_luck, 0.85)
