import os
import time
import threading
import requests
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = 1507891823031619746  # remplace par l'ID de ton salon

BASE_URL = "https://mikami-justice.onrender.com"
API_MULTI = f"{BASE_URL}/api/multisearch"
LOGO_URL = f"{BASE_URL}/static/logo.png"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def keep_alive():
    while True:
        try:
            requests.get(BASE_URL, timeout=10)
        except:
            pass
        time.sleep(300)


def split_results(content):
    blocks = [b.strip() for b in content.split("────────────") if b.strip()]
    return blocks or ["Aucun résultat"]


def get_confidence(block):
    for line in block.splitlines():
        if "Confiance" in line:
            digits = "".join(c for c in line if c.isdigit())
            if digits:
                return int(digits)
    return 0


def confidence_label(score):
    if score >= 70:
        return "🟢 Haute confiance"
    if score >= 40:
        return "🟠 Confiance moyenne"
    if score > 0:
        return "🔴 Faible confiance"
    return "⚫ Confiance inconnue"


def color_from_confidence(score, default_color):
    if score >= 70:
        return 0x57F287
    if score >= 40:
        return 0xFEE75C
    if score > 0:
        return 0xED4245
    return default_color


def clean_block(block):
    lines = []
    for line in block.splitlines():
        if "N/A" in line:
            continue
        lines.append(line)
    return "\n".join(lines) or "Aucune donnée exploitable"


class ResultPages(View):
    def __init__(self, blocks, title, default_color):
        super().__init__(timeout=300)
        self.blocks = blocks
        self.title = title
        self.default_color = default_color
        self.page = 0

    def make_embed(self):
        block = clean_block(self.blocks[self.page])
        confidence = get_confidence(self.blocks[self.page])
        color = color_from_confidence(confidence, self.default_color)

        embed = discord.Embed(
            title=f"⚖️ {self.title}",
            description=(
                "```txt\n"
                f"{block[:3200]}\n"
                "```"
            ),
            color=color
        )

        embed.add_field(
            name="📊 Évaluation",
            value=confidence_label(confidence),
            inline=True
        )

        embed.add_field(
            name="📄 Résultat",
            value=f"{self.page + 1}/{len(self.blocks)}",
            inline=True
        )

        embed.set_thumbnail(url=LOGO_URL)
        embed.set_footer(
            text="MIKAMI OSINT • Analyse. Comprends. Agis.",
            icon_url=LOGO_URL
        )

        return embed

    @discord.ui.button(
        label="⬅️ Précédent",
        style=discord.ButtonStyle.secondary,
        custom_id="result_previous"
    )
    async def previous(self, interaction: discord.Interaction, button: Button):
        if self.page > 0:
            self.page -= 1
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(
        label="➡️ Suivant",
        style=discord.ButtonStyle.secondary,
        custom_id="result_next"
    )
    async def next(self, interaction: discord.Interaction, button: Button):
        if self.page < len(self.blocks) - 1:
            self.page += 1
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


async def send_result(interaction, data, title, default_color):
    if data.get("type") == "text":
        content = data.get("content", "Aucun résultat")
        blocks = split_results(content)

        paginator = ResultPages(blocks, title, default_color)

        await interaction.followup.send(
            embed=paginator.make_embed(),
            view=paginator if len(blocks) > 1 else None
        )

    elif data.get("type") == "file":
        embed = discord.Embed(
            title="📁 Résultats complets",
            description=f"[Télécharger le fichier complet]({BASE_URL}{data.get('url')})",
            color=0x57F287
        )
        embed.set_thumbnail(url=LOGO_URL)
        embed.set_footer(
            text="MIKAMI OSINT • Export complet",
            icon_url=LOGO_URL
        )

        await interaction.followup.send(embed=embed)

    else:
        await interaction.followup.send(
            content=f"⚠️ Réponse inattendue : {data}",
            ephemeral=True
        )


class NameModal(Modal, title="Recherche Identité"):
    nom = TextInput(label="Nom", placeholder="Ex: Renier")
    prenom = TextInput(label="Prénom", placeholder="Ex: Noah")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        payload = {
            "nom_famille": self.nom.value.strip(),
            "prenom": self.prenom.value.strip(),
            "flexible": True
        }

        try:
            r = requests.post(API_MULTI, json=payload, timeout=30)
            data = r.json()
            await send_result(interaction, data, "Recherche Identité", 0x5865F2)

        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


class MultiModal(Modal, title="MultiSearch"):
    nom = TextInput(label="Nom", required=False, placeholder="Nom de famille")
    prenom = TextInput(label="Prénom", required=False)
    ville = TextInput(label="Ville", required=False)
    email = TextInput(label="Email", required=False)
    telephone = TextInput(label="Téléphone", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        payload = {
            "nom_famille": self.nom.value.strip(),
            "prenom": self.prenom.value.strip(),
            "ville": self.ville.value.strip(),
            "email": self.email.value.strip(),
            "telephone": self.telephone.value.strip(),
            "flexible": True
        }

        payload = {k: v for k, v in payload.items() if v}

        try:
            r = requests.post(API_MULTI, json=payload, timeout=30)
            data = r.json()
            await send_result(interaction, data, "MultiSearch", 0xED4245)

        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


class Panel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="👤 Identité",
        style=discord.ButtonStyle.primary,
        custom_id="btn_identity"
    )
    async def identity(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(NameModal())

    @discord.ui.button(
        label="⚡ MultiSearch",
        style=discord.ButtonStyle.danger,
        custom_id="btn_multi"
    )
    async def multi(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MultiModal())


async def setup_panel():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)

    if not channel:
        print("Salon introuvable")
        return

    async for msg in channel.history(limit=10):
        if msg.author == bot.user:
            await msg.delete()

    embed = discord.Embed(
        title="⚖️ MIKAMI OSINT",
        description=(
            "**Panel de recherche connecté à la plateforme.**\n\n"
            "👤 **Identité** — recherche ciblée par nom + prénom.\n"
            "⚡ **MultiSearch** — recherche avancée avec plusieurs champs.\n\n"
            "Sélectionne une action pour commencer."
        ),
        color=0x2B2D31
    )

    embed.set_thumbnail(url=LOGO_URL)
    embed.set_footer(
        text="MIKAMI OSINT • Analyse. Comprends. Agis.",
        icon_url=LOGO_URL
    )

    await channel.send(embed=embed, view=Panel())


@bot.event
async def on_ready():
    print(f"Connecté : {bot.user}")

    bot.add_view(Panel())

    if not getattr(bot, "panel_loaded", False):
        bot.panel_loaded = True
        bot.loop.create_task(setup_panel())
        threading.Thread(target=keep_alive, daemon=True).start()


if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN manquant. Fais: export DISCORD_TOKEN='TON_TOKEN'"
    )

bot.run(TOKEN)
