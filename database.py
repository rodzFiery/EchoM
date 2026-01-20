import sqlite3
import os
import json

# --- CONFIGURAÇÃO DE CAMINHO ---
if os.path.exists("/app/data"):
    DATABASE_PATH = "/app/data/economy.db"
else:
    if not os.path.exists("data"):
        os.makedirs("data")
    DATABASE_PATH = "data/economy.db"

def get_db_connection():
    # ADDED: Increased timeout to 30s to prevent 'database is locked' errors during heavy combat
    # FIXED: Using DATABASE_PATH for persistence
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def save_game_config(game_edition, nsfw_mode_active):
    with get_db_connection() as conn:
        conn.execute("UPDATE game_config SET game_edition = ?, nsfw_mode = ? WHERE id = 1", 
                      (game_edition, 1 if nsfw_mode_active else 0))
        conn.commit()

def load_game_config():
    with get_db_connection() as conn:
        row = conn.execute("SELECT game_edition, nsfw_mode FROM game_config WHERE id = 1").fetchone()
        if row:
            return row['game_edition'], bool(row['nsfw_mode'])
        return 1, False

def get_user(user_id):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            conn.execute("INSERT INTO users (id) VALUES (?)", (user_id,))
            conn.commit()
            return get_user(user_id)
        return user

def init_db():
    with get_db_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS global_stats (id INTEGER PRIMARY KEY, total_games INTEGER DEFAULT 0)""")
        
        # NEW TABLE FOR PERSISTENT SETTINGS
        conn.execute("""CREATE TABLE IF NOT EXISTS game_config (
            id INTEGER PRIMARY KEY, 
            game_edition INTEGER DEFAULT 1, 
            nsfw_mode INTEGER DEFAULT 0
        )""")
        conn.execute("INSERT OR IGNORE INTO game_config (id, game_edition, nsfw_mode) VALUES (1, 1, 0)")
        
        # Contract System Table
        conn.execute("""CREATE TABLE IF NOT EXISTS contracts (
            dominant_id INTEGER, 
            submissive_id INTEGER, 
            expiry TEXT, 
            tax_rate REAL DEFAULT 0.2,
            PRIMARY KEY (submissive_id)
        )""")
        
        # ADDED: DUEL HISTORY TABLE (Tracks Victims of !fuck)
        conn.execute("""CREATE TABLE IF NOT EXISTS duel_history (
            winner_id INTEGER,
            loser_id INTEGER,
            win_count INTEGER DEFAULT 0,
            PRIMARY KEY (winner_id, loser_id)
        )""")

        # Quest Table Re-Integrated into init_db
        q_cols = ["user_id INTEGER PRIMARY KEY"]
        for i in range(1, 21): q_cols.append(f"d{i} INTEGER DEFAULT 0")
        for i in range(1, 21): q_cols.append(f"w{i} INTEGER DEFAULT 0")
        q_cols.append("last_reset TEXT")
        conn.execute(f"CREATE TABLE IF NOT EXISTS quests ({', '.join(q_cols)})")

        required_columns = [
            ("balance", "INTEGER DEFAULT 500"), ("xp", "INTEGER DEFAULT 0"),
            ("fiery_xp", "INTEGER DEFAULT 0"), ("fiery_level", "INTEGER DEFAULT 1"),
            ("level", "INTEGER DEFAULT 1"), ("wins", "INTEGER DEFAULT 0"), 
            ("kills", "INTEGER DEFAULT 0"), ("deaths", "INTEGER DEFAULT 0"), 
            ("duel_wins", "INTEGER DEFAULT 0"), # ADDED: Separate stat for !fuck wins
            ("bio", "TEXT DEFAULT 'A tribute.'"), ("last_daily", "TEXT"), 
            ("last_weekly", "TEXT"), ("last_monthly", "TEXT"), ("class", "TEXT DEFAULT 'None'"),
            ("last_work", "TEXT"), ("last_beg", "TEXT"), ("last_cumcleaner", "TEXT"), 
            ("last_pimp", "TEXT"), ("last_experiment", "TEXT"), ("last_mystery", "TEXT"), 
            ("last_flirt", "TEXT"), ("first_bloods", "INTEGER DEFAULT 0"), 
            ("games_played", "INTEGER DEFAULT 0"), ("top_2", "INTEGER DEFAULT 0"), 
            ("top_3", "INTEGER DEFAULT 0"), ("top_4", "INTEGER DEFAULT 0"), 
            ("top_5", "INTEGER DEFAULT 0"), ("current_win_streak", "INTEGER DEFAULT 0"), 
            ("max_win_streak", "INTEGER DEFAULT 0"), ("current_kill_streak", "INTEGER DEFAULT 0"), 
            ("max_kill_streak", "INTEGER DEFAULT 0"), ("titles", "TEXT DEFAULT '[]'"),
            ("spouse", "INTEGER DEFAULT NULL"), ("marriage_date", "TEXT DEFAULT NULL"), # ADDED: Marriage Logic
            ("last_daily_streak", "TEXT"), ("last_weekly_streak", "TEXT"), ("last_monthly_streak", "TEXT"),
            ("daily_streak", "INTEGER DEFAULT 0"), ("weekly_streak", "INTEGER DEFAULT 0"), ("monthly_streak", "INTEGER DEFAULT 0"), # ADDED: STREAK COLUMNS
            ("streak_alerts", "INTEGER DEFAULT 1"), # ADDED: TOGGLE ALERT COLUMN
            ("premium_type", "TEXT DEFAULT 'Free'"), # ADDED: Required for Webhook
            ("premium_date", "TEXT") # ADDED: Required for Webhook
        ]

        cursor = conn.execute("PRAGMA table_info(users)")
        existing_cols = [row[1] for row in cursor.fetchall()]

        for col_name, col_type in required_columns:
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                except: pass

        cursor_gs = conn.execute("PRAGMA table_info(global_stats)")
        existing_gs = [row[1] for row in cursor_gs.fetchall()]
        gs_cols = [("total_kills", "INTEGER DEFAULT 0"), ("total_deaths", "INTEGER DEFAULT 0"), ("first_deaths", "INTEGER DEFAULT 0")]
        for c_n, c_t in gs_cols:
            if c_n not in existing_gs:
                try: conn.execute(f"ALTER TABLE global_stats ADD COLUMN {c_n} {c_t}")
                except: pass
                
        conn.execute("INSERT OR IGNORE INTO global_stats (id) VALUES (1)")
        conn.commit()
