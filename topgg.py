import discord
from discord.ext import commands
import aiohttp
import os
import sys
import database as db_module
from datetime import datetime, timedelta

class TopGG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.token = os.getenv("TOPGG_TOKEN")
        self.bot_id = os.getenv("BOT_ID")
        self.owner_id = 1482648173016252439  # ADDED: Owner bypass ID
        
        self.locked_cogs = [] 
        
        self.locked_commands = [
            "daily", "weekly", "monthly", "work", "experiment", "mystery", 
            "cumcleaner", "beg", "flirt", "pimp", "slut", "cuckold", 
            "deepthroat", "spit", "tease", "spank", "slap", "makemedirty", 
            "3some", "dp", "anal", "me", "achievements", "balance", 
            "ranking", "hall", "streaks", "quests", "catch", "pokedex", 
            "collections", "velvetdex", "dice", "blackjack", "roulette", 
            "slots", "bendover", "setclass", "dominant", "submissive", 
            "switch", "exhibitionist", "countstats", "serverstats", 
            "countinglb", "countingtop", "globalgoal", "goalhistory", 
            "contract", "accept", "ship", "match3some", "flirtyship", 
            "matchme", "shiphistory", "marry", "divorce", "bestfriend", 
            "submit", "lustprofile", "lovescore", "matchmaking", "bondtrial", 
            "torture", "fuck", "duel", "fightecho", "shop", "sell", 
            "inv", "checkbuffs", "limit", "react"
        ]
        
        self.bot.add_check(self.global_vote_interceptor)
        
        # --- ADDED: INJECT WEBHOOK INTO MAIN.PY FLASK SERVER ---
        self.setup_webhook()

    def setup_webhook(self):
        """Silently attaches a Top.gg webhook route to your existing Flask app."""
        main_mod = sys.modules.get('__main__')
        if not main_mod or not hasattr(main_mod, 'app'):
            print("⚠️ [TOP.GG] Could not find Flask app. Instant Webhook disabled.")
            return

        app = main_mod.app
        endpoint_name = 'topgg_webhook_receiver'
        
        if endpoint_name in app.view_functions:
            return 

        @app.route('/topgg', methods=['POST'], endpoint=endpoint_name)
        def topgg_webhook_receiver():
            from flask import request
            auth = request.headers.get('Authorization')
            secret = os.getenv("TOPGG_WEBHOOK_SECRET")
            
            if secret and auth != secret:
                print("⚠️ [TOP.GG] Unauthorized webhook attempt.")
                return "Unauthorized", 401
                
            data = request.json
            if not data:
                return "Bad Request", 400
                
            user_id = data.get('user')
            if user_id:
                try:
                    with db_module.get_db_connection() as conn:
                        conn.execute("CREATE TABLE IF NOT EXISTS topgg_votes (user_id INTEGER PRIMARY KEY, vote_time TEXT)")
                        expire = (datetime.now() + timedelta(hours=12)).isoformat()
                        conn.execute("INSERT OR REPLACE INTO topgg_votes (user_id, vote_time) VALUES (?, ?)", (int(user_id), expire))
                        conn.commit()
                    print(f"🔥 [TOP.GG WEBHOOK] INSTANT VOTE REGISTERED FOR ID {user_id}!")
                except Exception as e:
                    print(f"❌ [TOP.GG WEBHOOK] Database error: {e}")
            return "OK", 200

    def cog_unload(self):
        self.bot.remove_check(self.global_vote_interceptor)

    async def global_vote_interceptor(self, ctx):
        if not ctx.command:
            return True
        
        # OWNER BYPASS
        if ctx.author.id == self.owner_id:
            return True
            
        cog_name = ctx.command.cog_name
        command_name = ctx.command.name
        
        if cog_name not in self.locked_cogs and command_name not in self.locked_commands:
            return True 
            
        voted = await self.has_voted(ctx.author.id)
        if voted:
            return True 
            
        target_id = self.bot_id or self.bot.user.id
        embed = self.bot.fiery_embed(
            "🚫 LOCK PROTOCOL: VOTE REQUIRED",
            f"Please vote here to unlock commands for the next 12 hours:\n"
            f"🔗 https://top.gg/bot/{target_id}/vote"
        )
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)
            
        return False

    async def has_voted(self, user_id):
        # 1. INSTANT CHECK: Look at the local database first
        with db_module.get_db_connection() as conn:
            try:
                row = conn.execute("SELECT vote_time FROM topgg_votes WHERE user_id = ?", (int(user_id),)).fetchone()
                if row:
                    expire_time = datetime.fromisoformat(row['vote_time'])
                    if datetime.now() < expire_time:
                        return True
                    else:
                        conn.execute("DELETE FROM topgg_votes WHERE user_id = ?", (int(user_id),))
                        conn.commit()
            except Exception:
                pass 

        # 2. FALLBACK CHECK: If local DB fails, ping Top.gg API
        if not self.token:
            return False
            
        target_id = self.bot_id or self.bot.user.id
        url = f"https://top.gg/api/bots/{target_id}/check?userId={user_id}"
        headers = {"Authorization": self.token}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('voted') == 1
            except Exception:
                pass
        return False

    @commands.command()
    async def checkvote(self, ctx):
        voted = await self.has_voted(ctx.author.id)
        target_id = self.bot_id or self.bot.user.id
        
        if voted:
            embed = self.bot.fiery_embed("✅ VOTE VERIFIED", "You have voted! Your access to premium perks is active.")
        else:
            embed = self.bot.fiery_embed("❌ VOTE REQUIRED", f"You haven't voted in the last 12 hours.\nVote here to support the system: https://top.gg/bot/{target_id}/vote")
        
        if os.path.exists("LobbyTopRight.jpg"):
            file = discord.File("LobbyTopRight.jpg", filename="LobbyTopRight.jpg")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TopGG(bot))
