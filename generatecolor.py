import sys
import io
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

# --- HIGH-POTENCY GRADIENT AND CUSTOM COLOR PALETTE ---
# Exact 100 premium selections synchronized from your core wardrobe system
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

def generate_theme_card(category_name):
    """Generates a perfectly clear standalone display card for a single thematic collection."""
    # Sized ideally for native Discord embedded layout scaling (no squinting needed)
    img_w = 650
    row_height = 65
    header_height = 130
    padding = 35
    
    pigments = COLOR_PALETTE[category_name]
    img_h = header_height + (len(pigments) * row_height) + padding
    
    image = Image.new("RGB", (img_w, img_h), "#14141c")
    draw = ImageDraw.Draw(image)
    
    # Large high-clarity font options to preserve sharp lines
    try:
        font = ImageFont.truetype("arial.ttf", 22)
        bold_font = ImageFont.truetype("arial.ttf", 24)
        title_font = ImageFont.truetype("arial.ttf", 32)
    except IOError:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 22)
            bold_font = ImageFont.truetype("DejaVuSans.ttf", 24)
            title_font = ImageFont.truetype("DejaVuSans.ttf", 32)
        except IOError:
            font = ImageFont.load_default()
            bold_font = ImageFont.load_default()
            title_font = ImageFont.load_default()

    # Premium Heading Strip for the individual collection card
    draw.rectangle([(0, 0), (img_w, header_height - 30)], fill="#0d0d12")
    draw.rectangle([(0, header_height - 34), (img_w, header_height - 30)], fill="#d4af37")
    
    draw.text((padding, 35), category_name.upper(), fill="#d4af37", font=title_font)
    
    current_y = header_height
    
    for idx, p in enumerate(pigments):
        # Alternating background row tints for easy line tracking
        if idx % 2 == 0:
            draw.rectangle([(padding - 15, current_y - 2), (img_w - padding + 15, current_y + 52)], fill="#1a1a26")
            
        # Draw metadata fields clearly separated
        draw.text((padding, current_y + 12), p['name'], fill="#e2e2e9", font=font)
        draw.text((padding + 280, current_y + 12), f"#{p['hex']}", fill="#5f6d85", font=font)
        
        # Render the target phrase perfectly in its custom digital pigment color
        rgb_tuple = tuple(int(p['hex'][j:j+2], 16) for j in (0, 2, 4))
        draw.text((padding + 430, current_y + 10), "Echo Bot", fill=rgb_tuple, font=bold_font)
        
        current_y += row_height

    final_buffer = io.BytesIO()
    image.save(final_buffer, format="PNG")
    final_buffer.seek(0)
    return final_buffer

class GenerateColorSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="generatemasterpiece")
    @commands.has_permissions(administrator=True)
    async def run_visual_generator_cmd(self, ctx):
        """Admin command to compile 10 clean display cards and post them seamlessly to the chat channel."""
        await ctx.defer()
        try:
            # Loop through all 10 distinct collections sequentially to deploy perfect isolated frames
            for category in COLOR_PALETTE.keys():
                img_buffer = generate_theme_card(category)
                
                # Format a clean filename matching the theme layout context
                clean_name = "".join([c for c in category if c.isalnum() or c.isspace()]).strip().lower().replace(" ", "_")
                file = discord.File(img_buffer, filename=f"wardrobe_{clean_name}.png")
                
                await ctx.send(file=file)
                
        except Exception as e:
            await ctx.send(f"❌ **Compilation Override Failure:** `{str(e)}`")

async def setup(bot):
    await bot.add_cog(GenerateColorSystem(bot))
