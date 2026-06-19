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

def generate_masterpiece_chart():
    """Generates a master 100-color visual encyclopedia layout sheet directly into memory bytes."""
    col_width = 460
    row_height = 45
    header_height = 140
    padding = 30
    
    categories = list(COLOR_PALETTE.keys())
    columns_mapping = [
        categories[0:2],
        categories[2:4],
        categories[4:6],
        categories[6:8],
        categories[8:10]
    ]
    
    img_w = (col_width * 5) + (padding * 2)
    img_h = header_height + (20 * row_height) + (padding * 4)
    
    image = Image.new("RGB", (img_w, img_h), "#121218")
    draw = ImageDraw.Draw(image)
    
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        bold_font = ImageFont.truetype("arial.ttf", 18)
        title_font = ImageFont.truetype("arial.ttf", 36)
    except IOError:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 16)
            bold_font = ImageFont.truetype("DejaVuSans.ttf", 18)
            title_font = ImageFont.truetype("DejaVuSans.ttf", 36)
        except IOError:
            font = ImageFont.load_default()
            bold_font = ImageFont.load_default()
            title_font = ImageFont.load_default()

    draw.rectangle([(0, 0), (img_w, header_height - 20)], fill="#0b0b0f")
    draw.rectangle([(0, header_height - 24), (img_w, header_height - 20)], fill="#d4af37")
    
    draw.text((padding + 10, 25), "ECHO BOT OMNI-WARDROBE ENCYCLOPEDIA", fill="#d4af37", font=title_font)
    draw.text((padding + 12, 75), "Official 100-Pigment Identity Palette Matrix Checklist", fill="#8a95a5", font=font)

    for col_idx, col_cats in enumerate(columns_mapping):
        x_start = padding + (col_idx * col_width)
        current_y = header_height
        
        for cat_name in col_cats:
            draw.rectangle([(x_start, current_y), (x_start + col_width - 20, current_y + 35)], fill="#1a1a24")
            draw.text((x_start + 10, current_y + 7), cat_name.upper(), fill="#f4e0a5", font=bold_font)
            current_y += 50
            
            for idx, p in enumerate(COLOR_PALETTE[cat_name]):
                if idx % 2 == 0:
                    draw.rectangle([(x_start, current_y - 2), (x_start + col_width - 20, current_y + 32)], fill="#16161f")
                
                draw.text((x_start + 10, current_y + 5), f"{p['name']}", fill="#b5a4a3", font=font)
                draw.text((x_start + 190, current_y + 5), f"#{p['hex']}", fill="#4f5d75", font=font)
                
                rgb_tuple = tuple(int(p['hex'][j:j+2], 16) for j in (0, 2, 4))
                draw.text((x_start + 290, current_y + 3), "Echo Bot", fill=rgb_tuple, font=bold_font)
                
                current_y += row_height
            
            current_y += 30

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
        """Admin command to compile image directly in memory and upload straight to the showroom."""
        await ctx.defer()
        try:
            img_buffer = generate_masterpiece_chart()
            file = discord.File(img_buffer, filename="wardrobe_masterpiece.png")
            await ctx.send("🔥 **Omni-Wardrobe Encyclopedia compiled perfectly.** Here is your master color map:", file=file)
        except Exception as e:
            await ctx.send(f"❌ **Compilation Error:** `{str(e)}`")

async def setup(bot):
    await bot.add_cog(GenerateColorSystem(bot))
