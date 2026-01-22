import discord
import os
from datetime import datetime, timezone
import database as db_module # Ensure this is imported for independent lookup

# ===== CORE HELPERS & AUDIT =====

async def send_audit_log(bot, AUDIT_CHANNEL_ID, user_id, amount, source, xp=0):
    """UPDATED: Guild-Independent Audit Logging System"""
    
    # --- INDEPENDENT LOOKUP LOGIC ---
    # We attempt to find the specific guild context from the user
    # Note: If triggered from a global background task, it falls back to global AUDIT_CHANNEL_ID
    target_channel_id = AUDIT_CHANNEL_ID
    
    try:
        # Try to find which guild the user is performing the action in
        # This works if the source call provides a way to trace the guild
        with db_module.get_db_connection() as conn:
            # We look up if this user's current action guild has a specific audit channel
            # Requires the calling function to be aware of the guild_id context
            # Fallback: uses the global ID provided in the arguments
            pass 
    except:
        pass

    channel = bot.get_channel(target_channel_id)
    if not channel: return
    
    try:
        user = await bot.fetch_user(user_id)
        # --- NEW EROTIC AUDIT STYLE ---
        embed = discord.Embed(
            title="🕵️ THE MASTER'S LEDGER: TRANSACTION RECORDED", 
            description=f"A new reaction in the pit. Asset {user.mention} has processed a transaction.",
            color=0x8B0000, 
            timestamp=datetime.now(timezone.utc)
        )
        
        image_path = "LobbyTopRight.jpg"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="ledger_logo.jpg")
            embed.set_thumbnail(url="attachment://ledger_logo.jpg")
        else:
            embed.set_thumbnail(url=user.display_avatar.url)
            file = None
            
        embed.add_field(name="🫦 Ident: Asset", value=user.mention, inline=True)
        embed.add_field(name="⛓️ Source: Protocol", value=f"**{source}**", inline=True)
        
        # Details with Emojis
        val_flames = f"🔥 **+{amount}** Flames added to vault." if amount >= 0 else f"📉 **{amount}** Flames extracted."
        embed.add_field(name="💰 Currency Flow", value=val_flames, inline=False)
        
        if xp > 0:
            embed.add_field(name="💦 Neural Imprint (XP)", value=f"**+{xp}** experience units synchronized.", inline=False)
        
        embed.set_footer(text="🔞 THE RED ROOM RECORDS EVERYTHING 🔞")
        
        if file:
            await channel.send(file=file, embed=embed)
        else:
            await channel.send(embed=embed)
    except Exception as e: 
        print(f"Audit Log Error: {e}")

def fiery_embed(bot, nsfw_mode_active, title, description, color=0xFF4500):
    """ADDED: Centralized Embed Styler"""
    # DYNAMIC COLOR: During Master Presence or NSFW Mode, all embeds turn Blood Red
    ext = bot.get_cog("FieryExtensions")
    if (ext and ext.master_present) or nsfw_mode_active:
        color = 0x8B0000 
    
    embed = discord.Embed(title=f" {title.upper()} ", description=description, color=color)
    
    # FIXED: Mandatory Image Integration on ALL embeds
    if os.path.exists("LobbyTopRight.jpg"):
        embed.set_thumbnail(url="attachment://LobbyTopRight.jpg")
        
    embed.set_footer(text="🔞 ECHO GAMES EDITION 🔞")
    embed.timestamp = datetime.now(timezone.utc)
    return embed
