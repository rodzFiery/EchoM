import discord
from discord.ext import commands
import sys
import inspect

# --- HIGH-POTENCY GRADIENT AND CUSTOM COLOR PALETTE ---
# 100 premium selections split into digestible thematic categories
# --- ADDED: Matched-color emoji fields for every pigment option to provide an instant visual color preview ---
COLOR_PALETTE = {
    "🔥 Fiery & Lust": [
        {"name": "Crimson Climax", "hex": "FF007F", "emoji": "🔴"},
        {"name": "Scarlet Sin", "hex": "FF2400", "emoji": "🔴"},
        {"name": "Molten Passion", "hex": "FF4500", "emoji": "🔸"},
        {"name": "Blazing Desire", "hex": "FF6700", "emoji": "🔸"},
        {"name": "Afterglow Orange", "hex": "FF7F50", "emoji": "🟠"},
        {"name": "Deep Lust Rose", "hex": "C71585", "emoji": "🟣"},
        {"name": "Seductive Coral", "hex": "FF7F50", "emoji": "🟠"},
        {"name": "Volcanic Heat", "hex": "E63946", "emoji": "🔴"},
        {"name": "Wild Orchid", "hex": "DA70D6", "emoji": "🟣"},
        {"name": "Erotic Amethyst", "hex": "9932CC", "emoji": "🟣"}
    ],
    "⛓️ Submission & Shadows": [
        {"name": "Latex Black", "hex": "111111", "emoji": "⚫"},
        {"name": "Chained Silver", "hex": "C0C0C0", "emoji": "⚪"},
        {"name": "Midnight Velvet", "hex": "191970", "emoji": "🔵"},
        {"name": "Obsidian Bond", "hex": "0B0C10", "emoji": "⚫"},
        {"name": "Graphite Grip", "hex": "4F5D75", "emoji": "⚫"},
        {"name": "Smokey Quartz", "hex": "6D597A", "emoji": "🟤"},
        {"name": "Ashen Submissive", "hex": "B5A4A3", "emoji": "⚪"},
        {"name": "Shadow Dominion", "hex": "1F2833", "emoji": "⚫"},
        {"name": "Subdued Slate", "hex": "708090", "emoji": "⚫"},
        {"name": "Leather Matte", "hex": "2B2D42", "emoji": "⚫"}
    ],
    "💦 Pleasure & Fluidity": [
        {"name": "Neon Ocean", "hex": "00F5FF", "emoji": "🔵"},
        {"name": "Electric Aqua", "hex": "00FFFF", "emoji": "🔵"},
        {"name": "Deep Sea Rapture", "hex": "104E8B", "emoji": "🔵"},
        {"name": "Fluid Teal", "hex": "008080", "emoji": "🟢"},
        {"name": "Submerged Cyan", "hex": "00CED1", "emoji": "🔵"},
        {"name": "Siren's Call Blue", "hex": "4169E1", "emoji": "🔵"},
        {"name": "Tropical Ecstasy", "hex": "00FA9A", "emoji": "🟢"},
        {"name": "Glacial Shudder", "hex": "E0FFFF", "emoji": "⚪"},
        {"name": "Bioluminescent", "hex": "7FFFD4", "emoji": "🟢"},
        {"name": "Liquid Platinum", "hex": "E5E5E5", "emoji": "⚪"}
    ],
    "🍑 Sweet & Flesh": [
        {"name": "Blushing Flesh", "hex": "FFB7B2", "emoji": "💮"},
        {"name": "Juicy Peach", "hex": "FF9F1C", "emoji": "🟠"},
        {"name": "Succulent Rose", "hex": "FFC6FF", "emoji": "🌸"},
        {"name": "Bubblegum Bliss", "hex": "FF69B4", "emoji": "🌸"},
        {"name": "Velvet Cherry", "hex": "D90429", "emoji": "🔴"},
        {"name": "Hot Magenta", "hex": "FF00FF", "emoji": "🟣"},
        {"name": "Mauve Madness", "hex": "E0AAFF", "emoji": "🟣"},
        {"name": "Soft Carnation", "hex": "FFA6C9", "emoji": "🌸"},
        {"name": "Neon Fuchsia", "hex": "F72585", "emoji": "🟣"},
        {"name": "Gilded Nude", "hex": "E29578", "emoji": "🟤"}
    ],
    "🔮 Cosmic Majesty": [
        {"name": "Nebula Nightmare", "hex": "7209B7", "emoji": "🟣"},
        {"name": "Supernova Gold", "hex": "FFD700", "emoji": "🟡"},
        {"name": "Cosmic Violet", "hex": "4CC9F0", "emoji": "🔵"},
        {"name": "Astral Void", "hex": "3A0CA3", "emoji": "🔵"},
        {"name": "Starlight Silver", "hex": "F8F9FA", "emoji": "⚪"},
        {"name": "Aurora Glow", "hex": "560BAD", "emoji": "🟣"},
        {"name": "Solar Flare", "hex": "F94144", "emoji": "🔴"},
        {"name": "Plasma Pink", "hex": "F15BB5", "emoji": "🌸"},
        {"name": "Interstellar Mint", "hex": "00BBF9", "emoji": "🔵"},
        {"name": "Quantum Gold", "hex": "EE9B00", "emoji": "🟠"}
    ],
    "🍀 Exotic Botanical": [
        {"name": "Absinthe Green", "hex": "7FFF00", "emoji": "🟢"},
        {"name": "Envious Jade", "hex": "00A86B", "emoji": "🟢"},
        {"name": "Poison Ivy", "hex": "228B22", "emoji": "🟢"},
        {"name": "Neon Lime", "hex": "32CD32", "emoji": "🟢"},
        {"name": "Electric Emerald", "hex": "50C878", "emoji": "🟢"},
        {"name": "Forest Dominance", "hex": "014421", "emoji": "🟢"},
        {"name": "Mint Ecstasy", "hex": "98FF98", "emoji": "🟢"},
        {"name": "Toxic Olive", "hex": "808000", "emoji": "🟤"},
        {"name": "Malachite Lust", "hex": "0BDA51", "emoji": "🟢"},
        {"name": "Psychedelic Moss", "hex": "ADFF2F", "emoji": "🟢"}
    ],
    "🔱 Royal Authority": [
        {"name": "Imperial Purple", "hex": "6A0DAD", "emoji": "🟣"},
        {"name": "Sovereign Gold", "hex": "D4AF37", "emoji": "🟡"},
        {"name": "Majestic Indigo", "hex": "4B0082", "emoji": "🟣"},
        {"name": "Royal Champagne", "hex": "F4E0A5", "emoji": "🟡"},
        {"name": "Dynasty Ruby", "hex": "9B111E", "emoji": "🔴"},
        {"name": "Monarch Bronze", "hex": "CD7F32", "emoji": "🟤"},
        {"name": "Baron Orchid", "hex": "B0529F", "emoji": "🟣"},
        {"name": "Palace Turquoise", "hex": "2596BE", "emoji": "🔵"},
        {"name": "Exalted Platinum", "hex": "E5E4E2", "emoji": "⚪"},
        {"name": "Tyrian Velvet", "hex": "66023C", "emoji": "🟣"}
    ],
    "⚡ High Voltage": [
        {"name": "Cyber Yellow", "hex": "FFD300", "emoji": "🟡"},
        {"name": "Electric Pulse", "hex": "FF003F", "emoji": "🔴"},
        {"name": "Laser Cyan", "hex": "00E5FF", "emoji": "🔵"},
        {"name": "Static White", "hex": "FFFFFF", "emoji": "⚪"},
        {"name": "Hazard Orange", "hex": "FF5500", "emoji": "🟠"},
        {"name": "Gamma Violet", "hex": "8A2BE2", "emoji": "🟣"},
        {"name": "Atomic Lime", "hex": "CCFF00", "emoji": "🟢"},
        {"name": "Tesla Teal", "hex": "00F5D4", "emoji": "🟢"},
        {"name": "Overloaded Pink", "hex": "FF007F", "emoji": "🔴"},
        {"name": "Sonic Blue", "hex": "0044FF", "emoji": "🔵"}
    ],
    "🍷 Vintage Seduction": [
        {"name": "Bordeaux Wine", "hex": "780000", "emoji": "🔴"},
        {"name": "Merlot Velvet", "hex": "660708", "emoji": "🔴"},
        {"name": "Cognac Glow", "hex": "A1613A", "emoji": "🟤"},
        {"name": "Toasted Amber", "hex": "FFBF00", "emoji": "🟡"},
        {"name": "Dark Espresso", "hex": "36220F", "emoji": "⚫"},
        {"name": "Sangria Blush", "hex": "92000A", "emoji": "🔴"},
        {"name": "Tempting Truffle", "hex": "4A3728", "emoji": "🟤"},
        {"name": "Spiced Plum", "hex": "4E1A3D", "emoji": "🟣"},
        {"name": "Bourbon Honey", "hex": "D2A104", "emoji": "🟡"},
        {"name": "Burgundy Lace", "hex": "800020", "emoji": "🟣"}
    ],
    "💎 Opulent Luxuries": [
        {"name": "Pure Diamond", "hex": "E3F2FD", "emoji": "⚪"},
        {"name": "Flawless Ruby", "hex": "E0115F", "emoji": "🔴"},
        {"name": "Deep Sapphire", "hex": "0F52BA", "emoji": "🔵"},
        {"name": "Raw Emerald", "hex": "046307", "emoji": "🟢"},
        {"name": "Vibrant Topaz", "hex": "FFC87C", "emoji": "🟠"},
        {"name": "Pink Tourmaline", "hex": "F8119F", "emoji": "🌸"},
        {"name": "Amethyst Shard", "hex": "9966CC", "emoji": "🟣"},
        {"name": "Midnight Pearl", "hex": "8A95A5", "emoji": "⚫"},
        {"name": "Egyptian Lapis", "hex": "26619C", "emoji": "🔵"},
        {"name": "Rose Quartz Glow", "hex": "F7CAC9", "emoji": "🌸"}
    ]
}

# --- INTERACTIVE CATEGORY VIEW ---
class ColorCategorySelect(discord.ui.Select):
    def __init__(self, author):
        options = [
            discord.SelectOption(label=cat, description=f"Explore the {cat} collection", emoji=cat.split()[0])
            for cat in COLOR_PALETTE.keys()
        ]
        super().__init__(placeholder="🫦 Select Aura Category...", min_values=1, max_values=1, options=options)
        self.author = author

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ This wardrobe option belongs to another.", ephemeral=True)
        
        selected_category = self.values[0]
        new_view = ColorWardrobeView(self.author, selected_category, view_instance=self.view)
        
        main_mod = sys.modules['__main__']
        desc = (
            f"## {selected_category} WARDROBE\n"
            "Pick a pigment below to dye your identity on the server immediately.\n\n"
            "⚡ *Note: Custom color roles are cleanly managed by the system.*"
        )
        embed = main_mod.fiery_embed("IDENTITY DYE PROTOCOL", desc, color=0xd4af37)
        
        # Display available pigments in this menu view
        # --- ADDED: Visual color preview indicators included next to the text titles within the main info panel layout ---
        pigment_list = "\n".join([f"• {p['emoji']} **{p['name']}** (`#{p['hex']}`)" for p in COLOR_PALETTE[selected_category]])
        embed.add_field(name="🎨 Available Pigments", value=pigment_list, inline=False)
        
        await interaction.response.edit_message(embed=embed, view=new_view)

# --- INTERACTIVE PIGMENT VIEW ---
class ColorPigmentSelect(discord.ui.Select):
    def __init__(self, author, category):
        # --- MODIFIED: Word 'Echo Bot' added into the primary label path to replace the graphic circle icons natively ---
        options = [
            discord.SelectOption(label=f"Echo Bot [ {p['name']} ]", value=p["hex"], description=f"Apply Pigment Hex #{p['hex']}", emoji="✨")
            for p in COLOR_PALETTE[category]
        ]
        super().__init__(placeholder="🎨 Select Specific Pigment Aura...", min_values=1, max_values=1, options=options)
        self.author = author

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ Hands off the palette.", ephemeral=True)
        
        hex_code = self.values[0]
        color_name = next(p["name"] for cat in COLOR_PALETTE.values() for p in cat if p["hex"] == hex_code)
        
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        role_prefix = "🎨-Aura-"
        
        # Clean up any previously assigned color role
        for role in list(member.roles):
            if role.name.startswith(role_prefix):
                try:
                    await member.remove_roles(role)
                    # Delete the role if no other users occupy it
                    if len(role.members) == 0:
                        await role.delete()
                except Exception:
                    pass
                    
        # Construct or find the specific color role
        target_role_name = f"{role_prefix}{hex_code}"
        existing_role = discord.utils.get(guild.roles, name=target_role_name)
        
        if not existing_role:
            try:
                # Resolve color hex values safely
                int_color = int(hex_code, 16)
                existing_role = await guild.create_role(
                    name=target_role_name,
                    color=discord.Color(int_color),
                    reason=f"Identity Dye: {color_name}"
                )
                
                # Position the new role cleanly below the bot's highest role hierarchy marker
                bot_member = guild.get_member(interaction.client.user.id)
                if bot_member and bot_member.top_role:
                    # --- ADDED: DYNAMIC AUTO-HIERARCHY ESCALATOR ---
                    # To combat Discord ignoring colors under higher colored roles, this calculates 
                    # the absolute highest legal location available beneath the bot's clearance limit.
                    target_position = max(1, bot_member.top_role.position - 1)
                    await existing_role.edit(position=target_position)
            except discord.Forbidden:
                return await interaction.followup.send("❌ **Hierarchy Error.** My roles must be higher than the color tokens to apply them.", ephemeral=True)
            except Exception as e:
                return await interaction.followup.send(f"❌ **Protocol Failure:** `{str(e)}`", ephemeral=True)
                
        try:
            # --- ADDED: EXTRA HIERARCHY VERIFICATION CHECK ---
            # If the role already existed but is currently sitting below other colored roles assigned to the member,
            # we scale it upwards toward the ceiling to guarantee the visual color takes priority.
            bot_member = guild.get_member(interaction.client.user.id)
            if bot_member and bot_member.top_role and existing_role.position < (bot_member.top_role.position - 1):
                try:
                    await existing_role.edit(position=max(1, bot_member.top_role.position - 1))
                except Exception:
                    pass

            await member.add_roles(existing_role)
            main_mod = sys.modules['__main__']
            desc = f"### 🔞 IDENTITY COATED\n\nYour presence has been bathed in **{color_name}** (`#{hex_code}`)."
            embed = main_mod.fiery_embed("WARDROBE SUCCESS", desc, color=int(hex_code, 16))
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ **Role Assignment Failure:** `{str(e)}`", ephemeral=True)

# --- BASEWARDROBE MANAGER VIEW ---
class ColorWardrobeView(discord.ui.View):
    def __init__(self, author, category=None, view_instance=None):
        super().__init__(timeout=120)
        self.author = author
        
        # Always retain Category navigation selector
        self.add_item(ColorCategorySelect(author))
        
        # Contextual display mapping specific chosen category
        if category:
            self.add_item(ColorPigmentSelect(author, category))

class ColorSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setcolor")
    @commands.guild_only()
    async def set_color_dashboard(self, ctx):
        main_mod = sys.modules['__main__']
        view = ColorWardrobeView(ctx.author)
        
        desc = (
            "## 🫦 THE LUXURY WARDROBE\n"
            "Alter your presentation aura dynamically across the server landscape.\n\n"
            "**⛓️ WARDROBE SPECS:**\n"
            "• **10 Themes** curated uniquely for aesthetics.\n"
            "• **100 Masterful Pigments** available dynamically.\n"
            "• **Automated Role Management** preserves clean hierarchies."
        )
        embed = main_mod.fiery_embed("COLOR WARDROBE DEPLOYED", desc, color=0xd4af37)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ColorSystem(bot))
    print("✅ LOG: High-Potency 100-Pigment Color System Integrated Perfectly.")
