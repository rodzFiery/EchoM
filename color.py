import discord
from discord.ext import commands
import sys
import inspect

# --- HIGH-POTENCY GRADIENT AND CUSTOM COLOR PALETTE ---
# 100 premium selections split into digestible thematic categories
COLOR_PALETTE = {
    "🔥 Fiery & Lust": [
        {"name": "Crimson Climax", "hex": "FF007F"},
        {"name": "Scarlet Sin", "hex": "FF2400"},
        {"name": "Molten Passion", "hex": "FF4500"},
        {"name": "Blazing Desire", "hex": "FF6700"},
        {"name": "Afterglow Orange", "hex": "FF7F50"},
        {"name": "Deep Lust Rose", "hex": "C71585"},
        {"name": "Seductive Coral", "hex": "FF7F50"},
        {"name": "Volcanic Heat", "hex": "E63946"},
        {"name": "Wild Orchid", "hex": "DA70D6"},
        {"name": "Erotic Amethyst", "hex": "9932CC"}
    ],
    "⛓️ Submission & Shadows": [
        {"name": "Latex Black", "hex": "111111"},
        {"name": "Chained Silver", "hex": "C0C0C0"},
        {"name": "Midnight Velvet", "hex": "191970"},
        {"name": "Obsidian Bond", "hex": "0B0C10"},
        {"name": "Graphite Grip", "hex": "4F5D75"},
        {"name": "Smokey Quartz", "hex": "6D597A"},
        {"name": "Ashen Submissive", "hex": "B5A4A3"},
        {"name": "Shadow Dominion", "hex": "1F2833"},
        {"name": "Subdued Slate", "hex": "708090"},
        {"name": "Leather Matte", "hex": "2B2D42"}
    ],
    "💦 Pleasure & Fluidity": [
        {"name": "Neon Ocean", "hex": "00F5FF"},
        {"name": "Electric Aqua", "hex": "00FFFF"},
        {"name": "Deep Sea Rapture", "hex": "104E8B"},
        {"name": "Fluid Teal", "hex": "008080"},
        {"name": "Submerged Cyan", "hex": "00CED1"},
        {"name": "Siren's Call Blue", "hex": "4169E1"},
        {"name": "Tropical Ecstasy", "hex": "00FA9A"},
        {"name": "Glacial Shudder", "hex": "E0FFFF"},
        {"name": "Bioluminescent", "hex": "7FFFD4"},
        {"name": "Liquid Platinum", "hex": "E5E5E5"}
    ],
    "🍑 Sweet & Flesh": [
        {"name": "Blushing Flesh", "hex": "FFB7B2"},
        {"name": "Juicy Peach", "hex": "FF9F1C"},
        {"name": "Succulent Rose", "hex": "FFC6FF"},
        {"name": "Bubblegum Bliss", "hex": "FF69B4"},
        {"name": "Velvet Cherry", "hex": "D90429"},
        {"name": "Hot Magenta", "hex": "FF00FF"},
        {"name": "Mauve Madness", "hex": "E0AAFF"},
        {"name": "Soft Carnation", "hex": "FFA6C9"},
        {"name": "Neon Fuchsia", "hex": "F72585"},
        {"name": "Gilded Nude", "hex": "E29578"}
    ],
    "🔮 Cosmic Majesty": [
        {"name": "Nebula Nightmare", "hex": "7209B7"},
        {"name": "Supernova Gold", "hex": "FFD700"},
        {"name": "Cosmic Violet", "hex": "4CC9F0"},
        {"name": "Astral Void", "hex": "3A0CA3"},
        {"name": "Starlight Silver", "hex": "F8F9FA"},
        {"name": "Aurora Glow", "hex": "560BAD"},
        {"name": "Solar Flare", "hex": "F94144"},
        {"name": "Plasma Pink", "hex": "F15BB5"},
        {"name": "Interstellar Mint", "hex": "00BBF9"},
        {"name": "Quantum Gold", "hex": "EE9B00"}
    ],
    "🍀 Exotic Botanical": [
        {"name": "Absinthe Green", "hex": "7FFF00"},
        {"name": "Envious Jade", "hex": "00A86B"},
        {"name": "Poison Ivy", "hex": "228B22"},
        {"name": "Neon Lime", "hex": "32CD32"},
        {"name": "Electric Emerald", "hex": "50C878"},
        {"name": "Forest Dominance", "hex": "014421"},
        {"name": "Mint Ecstasy", "hex": "98FF98"},
        {"name": "Toxic Olive", "hex": "808000"},
        {"name": "Malachite Lust", "hex": "0BDA51"},
        {"name": "Psychedelic Moss", "hex": "ADFF2F"}
    ],
    "🔱 Royal Authority": [
        {"name": "Imperial Purple", "hex": "6A0DAD"},
        {"name": "Sovereign Gold", "hex": "D4AF37"},
        {"name": "Majestic Indigo", "hex": "4B0082"},
        {"name": "Royal Champagne", "hex": "F4E0A5"},
        {"name": "Dynasty Ruby", "hex": "9B111E"},
        {"name": "Monarch Bronze", "hex": "CD7F32"},
        {"name": "Baron Orchid", "hex": "B0529F"},
        {"name": "Palace Turquoise", "hex": "2596BE"},
        {"name": "Exalted Platinum", "hex": "E5E4E2"},
        {"name": "Tyrian Velvet", "hex": "66023C"}
    ],
    "⚡ High Voltage": [
        {"name": "Cyber Yellow", "hex": "FFD300"},
        {"name": "Electric Pulse", "hex": "FF003F"},
        {"name": "Laser Cyan", "hex": "00E5FF"},
        {"name": "Static White", "hex": "FFFFFF"},
        {"name": "Hazard Orange", "hex": "FF5500"},
        {"name": "Gamma Violet", "hex": "8A2BE2"},
        {"name": "Atomic Lime", "hex": "CCFF00"},
        {"name": "Tesla Teal", "hex": "00F5D4"},
        {"name": "Overloaded Pink", "hex": "FF007F"},
        {"name": "Sonic Blue", "hex": "0044FF"}
    ],
    "🍷 Vintage Seduction": [
        {"name": "Bordeaux Wine", "hex": "780000"},
        {"name": "Merlot Velvet", "hex": "660708"},
        {"name": "Cognac Glow", "hex": "A1613A"},
        {"name": "Toasted Amber", "hex": "FFBF00"},
        {"name": "Dark Espresso", "hex": "36220F"},
        {"name": "Sangria Blush", "hex": "92000A"},
        {"name": "Tempting Truffle", "hex": "4A3728"},
        {"name": "Spiced Plum", "hex": "4E1A3D"},
        {"name": "Bourbon Honey", "hex": "D2A104"},
        {"name": "Burgundy Lace", "hex": "800020"}
    ],
    "💎 Opulent Luxuries": [
        {"name": "Pure Diamond", "hex": "E3F2FD"},
        {"name": "Flawless Ruby", "hex": "E0115F"},
        {"name": "Deep Sapphire", "hex": "0F52BA"},
        {"name": "Raw Emerald", "hex": "046307"},
        {"name": "Vibrant Topaz", "hex": "FFC87C"},
        {"name": "Pink Tourmaline", "hex": "F8119F"},
        {"name": "Amethyst Shard", "hex": "9966CC"},
        {"name": "Midnight Pearl", "hex": "8A95A5"},
        {"name": "Egyptian Lapis", "hex": "26619C"},
        {"name": "Rose Quartz Glow", "hex": "F7CAC9"}
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
        pigment_list = "\n".join([f"• **{p['name']}** (`#{p['hex']}`)" for p in COLOR_PALETTE[selected_category]])
        embed.add_field(name="🎨 Available Pigments", value=pigment_list, inline=False)
        
        await interaction.response.edit_message(embed=embed, view=new_view)

# --- INTERACTIVE PIGMENT VIEW ---
class ColorPigmentSelect(discord.ui.Select):
    def __init__(self, author, category):
        options = [
            discord.SelectOption(label=p["name"], value=p["hex"], description=f"Apply Hex #{p['hex']}", emoji="✨")
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
                    await existing_role.edit(position=max(1, bot_member.top_role.position - 1))
            except discord.Forbidden:
                return await interaction.followup.send("❌ **Hierarchy Error.** My roles must be higher than the color tokens to apply them.", ephemeral=True)
            except Exception as e:
                return await interaction.followup.send(f"❌ **Protocol Failure:** `{str(e)}`", ephemeral=True)
                
        try:
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
