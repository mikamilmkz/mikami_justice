import os
import time
import threading
import asyncio
import requests
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

TOKEN = os.getenv("DISCORD_TOKEN")

SEARCH_CHANNEL_ID = 1507891823031619746
RESULTS_CHANNEL_ID = 1507891868489482431

BASE_URL = "https://mikami-justice.onrender.com"
API_MULTI = f"{BASE_URL}/api/multisearch"
LOGO_URL = f"{BASE_URL}/static/logo.png"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def safe_text(text, limit=1800):
    text = str(text)

    if len(text) > limit:
        return text[:limit] + "\n...[coupé]"

    return text


def keep_alive():
    while True:
        try:
            requests.get(f"{BASE_URL}/health", timeout=10)
        except Exception:
            pass

        time.sleep(300)


def post_api(payload):
    response = requests.post(
        API_MULTI,
        json=payload,
        timeout=60
    )
    return response.json()


async def call_api(payload):
    return await asyncio.to_thread(post_api, payload)


def format_person(item):
    sources = item.get("_sources")

    if isinstance(sources, list):
        sources = ", ".join(sources)

    fields = {
        "👤 Prénom": item.get("prenom"),
        "👤 Nom": item.get("nom_famille"),
        "📧 Email": item.get("email"),
        "📱 Téléphone": (
            item.get("telephone")
            or item.get("mobile")
            or item.get("tel")
            or item.get("phone")
        ),
        "🏠 Adresse": (
            item.get("adresse_complete")
            or item.get("adresse")
            or item.get("address")
        ),
        "📍 Ville": item.get("ville"),
        "📮 Code postal": item.get("code_postal"),
        "🌍 Pays": item.get("pays"),
        "🎂 Naissance": item.get("date_naissance"),
        "💻 Username": item.get("nom_utilisateur"),
        "🎯 Confiance": item.get("_confidence"),
        "📁 Source": sources
    }

    lines = []

    for label, value in fields.items():
        if value not in [None, "", "N/A"]:
            lines.append(f"{label} : {value}")

    return "\n".join(lines) or "Aucune donnée exploitable"


def get_confidence(item):
    try:
        return int(item.get("_confidence") or 0)
    except Exception:
        return 0


def color_from_confidence(score, default):
    if score >= 70:
        return 0x57F287

    if score >= 40:
        return 0xFEE75C

    if score > 0:
        return 0xED4245

    return default


def confidence_label(score):
    if score >= 70:
        return "🟢 Haute confiance"

    if score >= 40:
        return "🟠 Confiance moyenne"

    if score > 0:
        return "🔴 Faible confiance"

    return "⚫ Confiance inconnue"


class ResultPages(View):
    def __init__(self, results, title, default_color):
        super().__init__(timeout=300)
        self.results = results
        self.title = title
        self.default_color = default_color
        self.page = 0

    def make_embed(self):
        item = self.results[self.page]
        confidence = get_confidence(item)

        embed = discord.Embed(
            title=f"⚖️ {self.title}",
            description=f"```txt\n{format_person(item)[:3200]}\n```",
            color=color_from_confidence(confidence, self.default_color)
        )

        embed.add_field(
            name="📊 Évaluation",
            value=confidence_label(confidence),
            inline=True
        )

        embed.add_field(
            name="📄 Résultat",
            value=f"{self.page + 1}/{len(self.results)}",
            inline=True
        )

        embed.set_thumbnail(url=LOGO_URL)
        embed.set_footer(
            text="MIKAMI OSINT • Résultat privé",
            icon_url=LOGO_URL
        )

        return embed

    @discord.ui.button(
        label="⬅️ Précédent",
        style=discord.ButtonStyle.secondary,
        custom_id="prev_result"
    )
    async def previous(self, interaction: discord.Interaction, button: Button):
        if self.page > 0:
            self.page -= 1

        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self
        )

    @discord.ui.button(
        label="➡️ Suivant",
        style=discord.ButtonStyle.secondary,
        custom_id="next_result"
    )
    async def next(self, interaction: discord.Interaction, button: Button):
        if self.page < len(self.results) - 1:
            self.page += 1

        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self
        )


async def log_search(user, search_type, total):
    channel = bot.get_channel(RESULTS_CHANNEL_ID)

    if not channel:
        return

    embed = discord.Embed(
        title="📡 Nouvelle recherche",
        description=(
            f"👤 Utilisateur : {user.mention}\n"
            f"🔎 Type : **{search_type}**\n"
            f"📊 Résultats : **{total}**\n"
            f"🔒 Données : privées"
        ),
        color=0x2B2D31
    )

    embed.set_footer(
        text="MIKAMI OSINT • Logs",
        icon_url=LOGO_URL
    )

    try:
        await channel.send(embed=embed)
    except Exception:
        pass


async def send_result(interaction, data, title, color):
    if not isinstance(data, dict):
        await interaction.followup.send(
            f"⚠️ Réponse invalide : {safe_text(data)}",
            ephemeral=True
        )
        return 0

    if data.get("type") == "raw":
        results = data.get("results") or []
        total = data.get("total", len(results))

        if not results:
            embed = discord.Embed(
                title=f"⚖️ {title}",
                description="Aucun résultat trouvé",
                color=color
            )
            embed.set_thumbnail(url=LOGO_URL)
            embed.set_footer(
                text="MIKAMI OSINT",
                icon_url=LOGO_URL
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True
            )
            return total

        paginator = ResultPages(results, title, color)

        if len(results) > 1:
            await interaction.followup.send(
                embed=paginator.make_embed(),
                view=paginator,
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=paginator.make_embed(),
                ephemeral=True
            )

        return total

    if data.get("type") == "error":
        await interaction.followup.send(
            f"❌ Erreur API : {safe_text(data.get('message'))}",
            ephemeral=True
        )
        return 0

    await interaction.followup.send(
        f"⚠️ Réponse inattendue : {safe_text(data)}",
        ephemeral=True
    )
    return 0


class NameModal(Modal, title="Recherche Identité"):
    nom = TextInput(
        label="Nom",
        placeholder="Ex: Renier"
    )
    prenom = TextInput(
        label="Prénom",
        placeholder="Ex: Noah"
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(
            thinking=True,
            ephemeral=True
        )

        payload = {
            "nom_famille": self.nom.value.strip(),
            "prenom": self.prenom.value.strip(),
            "flexible": True
        }

        try:
            data = await call_api(payload)

            total = await send_result(
                interaction,
                data,
                "Recherche Identité",
                0x5865F2
            )

            await log_search(
                interaction.user,
                "Identité",
                total
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur : {safe_text(e)}",
                ephemeral=True
            )


class MultiModal(Modal, title="MultiSearch"):
    nom = TextInput(
        label="Nom",
        required=False,
        placeholder="Nom de famille"
    )
    prenom = TextInput(
        label="Prénom",
        required=False
    )
    ville = TextInput(
        label="Ville",
        required=False
    )
    email = TextInput(
        label="Email",
        required=False
    )
    username = TextInput(
        label="Username",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(
            thinking=True,
            ephemeral=True
        )

        payload = {
            "nom_famille": self.nom.value.strip(),
            "prenom": self.prenom.value.strip(),
            "ville": self.ville.value.strip(),
            "email": self.email.value.strip(),
            "nom_utilisateur": self.username.value.strip(),
            "flexible": True
        }

        payload = {
            k: v for k, v in payload.items()
            if v not in ["", None]
        }

        try:
            data = await call_api(payload)

            total = await send_result(
                interaction,
                data,
                "MultiSearch",
                0xED4245
            )

            await log_search(
                interaction.user,
                "MultiSearch",
                total
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur : {safe_text(e)}",
                ephemeral=True
            )


class PhoneModal(Modal, title="Recherche Téléphone"):
    telephone = TextInput(
        label="Téléphone",
        placeholder="Ex: 0612345678"
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(
            thinking=True,
            ephemeral=True
        )

        payload = {
            "telephone": self.telephone.value.strip(),
            "flexible": True
        }

        try:
            data = await call_api(payload)

            total = await send_result(
                interaction,
                data,
                "Recherche Téléphone",
                0x57F287
            )

            await log_search(
                interaction.user,
                "Téléphone",
                total
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur : {safe_text(e)}",
                ephemeral=True
            )


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

    @discord.ui.button(
        label="📱 Téléphone",
        style=discord.ButtonStyle.success,
        custom_id="btn_phone"
    )
    async def phone(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(PhoneModal())


async def setup_panel():
    await bot.wait_until_ready()

    channel = bot.get_channel(SEARCH_CHANNEL_ID)

    if not channel:
        print("Salon search introuvable")
        return

    try:
        async for msg in channel.history(limit=20):
            if msg.author == bot.user:
                await msg.delete()
    except Exception:
        pass

    embed = discord.Embed(
        title="⚖️ MIKAMI OSINT",
        description=(
            "**Panel de recherche privé.**\n\n"
            "👤 **Identité** — recherche ciblée par nom + prénom.\n"
            "⚡ **MultiSearch** — recherche avancée avec plusieurs champs.\n"
            "📱 **Téléphone** — recherche ciblée par numéro.\n\n"
            "🔒 Les résultats sont visibles uniquement par l’utilisateur."
        ),
        color=0x2B2D31
    )

    embed.add_field(
        name="🟢 API",
        value="Online",
        inline=True
    )

    embed.add_field(
        name="📡 Bot",
        value="Railway Connected",
        inline=True
    )

    embed.set_thumbnail(url=LOGO_URL)
    embed.set_footer(
        text="MIKAMI OSINT • Analyse. Comprends. Agis.",
        icon_url=LOGO_URL
    )

    await channel.send(
        embed=embed,
        view=Panel()
    )


@bot.event
async def on_ready():
    print(f"Connecté : {bot.user}")

    bot.add_view(Panel())

    if not getattr(bot, "panel_loaded", False):
        bot.panel_loaded = True
        bot.loop.create_task(setup_panel())
        threading.Thread(
            target=keep_alive,
            daemon=True
        ).start()


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN manquant")

bot.run(TOKEN)