import asyncio
import os
import threading
import time

import discord
import requests
from discord.ext import commands
from discord.ui import Button, Modal, TextInput, View


TOKEN = os.getenv("DISCORD_TOKEN")

SEARCH_CHANNEL_ID = 1507891823031619746
RESULTS_CHANNEL_ID = 1507891868489482431

BASE_URL = "https://mikami-justice.onrender.com"
API_MULTI = f"{BASE_URL}/api/multisearch"
LOGO_URL = f"{BASE_URL}/static/logo.png"
BANNER_URL = f"{BASE_URL}/static/banner.png"
BANNER_PATH = os.getenv("BANNER_PATH", "static/banner.png")
BANNER_ATTACHMENT_NAME = "mikami_banner.png"

RESULTS_PER_PAGE = 2

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
        timeout=60,
    )
    return response.json()


async def call_api(payload):
    return await asyncio.to_thread(post_api, payload)


def format_person(item):
    sources = item.get("_sources")

    if isinstance(sources, list):
        sources = ", ".join(sources)

    fields = {
        " Prénom": item.get("prenom"),
        " Nom": item.get("nom_famille") or item.get("nom"),
        " Email": item.get("email"),
        " Téléphone": (
            item.get("telephone")
            or item.get("mobile")
            or item.get("tel")
            or item.get("phone")
        ),
        " Adresse": (
            item.get("adresse_complete")
            or item.get("adresse")
            or item.get("address")
        ),
        " Ville": item.get("ville"),
        " Code postal": item.get("code_postal"),
        " Pays": item.get("pays"),
        " Naissance": item.get("date_naissance"),
        " Username": item.get("nom_utilisateur"),
        " Confiance": item.get("_confidence"),
        " Source": sources,
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
        return " Haute confiance"

    if score >= 40:
        return " Confiance moyenne"

    if score > 0:
        return " Faible confiance"

    return "⚫ Confiance inconnue"


class ResultPages(View):
    def __init__(self, results, title, default_color):
        super().__init__(timeout=300)
        self.results = results
        self.title = title
        self.default_color = default_color
        self.page = 0
        self.per_page = RESULTS_PER_PAGE
        self.update_buttons()

    def total_pages(self):
        return max(1, (len(self.results) + self.per_page - 1) // self.per_page)

    def page_slice(self):
        start = self.page * self.per_page
        end = start + self.per_page
        return start, min(end, len(self.results)), self.results[start:end]

    def update_buttons(self):
        total_pages = self.total_pages()

        for child in self.children:
            if child.custom_id == "prev_result":
                child.disabled = self.page <= 0

            if child.custom_id == "next_result":
                child.disabled = self.page >= total_pages - 1

    def make_embed(self):
        self.update_buttons()

        start, end, page_results = self.page_slice()
        best_confidence = max([get_confidence(item) for item in page_results] or [0])

        blocks = []

        for index, item in enumerate(page_results, start=start + 1):
            confidence = get_confidence(item)
            person_text = safe_text(format_person(item), 1500)

            blocks.append(
                f"RÉSULTAT {index}\n"
                f"{person_text}\n"
                f"Évaluation : {confidence_label(confidence)}"
            )

        description = "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(blocks)
        description = safe_text(description, 3900)

        embed = discord.Embed(
            title=f"⚖️ {self.title}",
            description=f"```txt\n{description}\n```",
            color=color_from_confidence(best_confidence, self.default_color),
        )

        embed.add_field(
            name=" Résultats affichés",
            value=f"{start + 1}-{end}/{len(self.results)}",
            inline=True,
        )

        embed.add_field(
            name=" Page",
            value=f"{self.page + 1}/{self.total_pages()}",
            inline=True,
        )

        embed.set_thumbnail(url=LOGO_URL)

        embed.set_footer(
            text="MIKAMI OSINT • Résultats privés",
            icon_url=LOGO_URL,
        )

        return embed

    @discord.ui.button(
        label="⬅️ Précédent",
        style=discord.ButtonStyle.secondary,
        custom_id="prev_result",
    )
    async def previous(self, interaction: discord.Interaction, button: Button):
        if self.page > 0:
            self.page -= 1

        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self,
        )

    @discord.ui.button(
        label="➡️ Suivant",
        style=discord.ButtonStyle.secondary,
        custom_id="next_result",
    )
    async def next(self, interaction: discord.Interaction, button: Button):
        if self.page < self.total_pages() - 1:
            self.page += 1

        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self,
        )


async def log_search(user, search_type, total):
    channel = bot.get_channel(RESULTS_CHANNEL_ID)

    if not channel:
        return

    embed = discord.Embed(
        title=" Nouvelle recherche",
        description=(
            f" Utilisateur : {user.mention}\n"
            f" Type : **{search_type}**\n"
            f" Résultats : **{total}**\n"
            f" Données : privées"
        ),
        color=0x2B2D31,
    )

    embed.set_footer(
        text="MIKAMI OSINT • Logs",
        icon_url=LOGO_URL,
    )

    try:
        await channel.send(embed=embed)
    except Exception:
        pass


async def send_result(interaction, data, title, color):
    if not isinstance(data, dict):
        await interaction.followup.send(
            f"⚠️ Réponse invalide : {safe_text(data)}",
            ephemeral=True,
        )
        return 0

    if data.get("type") == "raw":
        results = data.get("results") or []
        total = data.get("total", len(results))

        if not results:
            embed = discord.Embed(
                title=f"⚖️ {title}",
                description="Aucun résultat trouvé",
                color=color,
            )

            embed.set_thumbnail(url=LOGO_URL)
            embed.set_footer(
                text="MIKAMI OSINT",
                icon_url=LOGO_URL,
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )
            return total

        paginator = ResultPages(results, title, color)

        if len(results) > RESULTS_PER_PAGE:
            await interaction.followup.send(
                embed=paginator.make_embed(),
                view=paginator,
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=paginator.make_embed(),
                ephemeral=True,
            )

        return total

    if data.get("type") == "error":
        await interaction.followup.send(
            f"❌ Erreur API : {safe_text(data.get('message'))}",
            ephemeral=True,
        )
        return 0

    await interaction.followup.send(
        f"⚠️ Réponse inattendue : {safe_text(data)}",
        ephemeral=True,
    )
    return 0


class NameModal(Modal, title="Recherche Identité"):
    nom = TextInput(
        label="Nom",
        placeholder="Ex: Renier",
    )

    prenom = TextInput(
        label="Prénom",
        placeholder="Ex: Noah",
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        payload = {
            "nom_famille": self.nom.value.strip(),
            "prenom": self.prenom.value.strip(),
            "flexible": True,
        }

        try:
            data = await call_api(payload)
            total = await send_result(
                interaction,
                data,
                "Recherche Identité",
                0x5865F2,
            )
            await log_search(
                interaction.user,
                "Identité",
                total,
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur : {safe_text(e)}",
                ephemeral=True,
            )


class MultiModal(Modal, title="MultiSearch"):
    nom = TextInput(
        label="Nom",
        required=False,
        placeholder="Nom de famille",
    )

    prenom = TextInput(
        label="Prénom",
        required=False,
    )

    ville = TextInput(
        label="Ville",
        required=False,
    )

    email = TextInput(
        label="Email",
        required=False,
    )

    username = TextInput(
        label="Username",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        payload = {
            "nom_famille": self.nom.value.strip(),
            "prenom": self.prenom.value.strip(),
            "ville": self.ville.value.strip(),
            "email": self.email.value.strip(),
            "nom_utilisateur": self.username.value.strip(),
            "flexible": True,
        }

        payload = {
            key: value
            for key, value in payload.items()
            if value not in ["", None]
        }

        try:
            data = await call_api(payload)
            total = await send_result(
                interaction,
                data,
                "MultiSearch",
                0xED4245,
            )
            await log_search(
                interaction.user,
                "MultiSearch",
                total,
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur : {safe_text(e)}",
                ephemeral=True,
            )


class MultiFlexibleModal(Modal, title="MultiSearch Flexible"):
    nom = TextInput(
        label="Nom",
        required=False,
        placeholder="Nom de famille",
    )

    prenom = TextInput(
        label="Prénom",
        required=False,
    )

    ville = TextInput(
        label="Ville",
        required=False,
    )

    email = TextInput(
        label="Email",
        required=False,
    )

    username = TextInput(
        label="Username",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        payload = {
            "nom_famille": self.nom.value.strip(),
            "prenom": self.prenom.value.strip(),
            "ville": self.ville.value.strip(),
            "email": self.email.value.strip(),
            "nom_utilisateur": self.username.value.strip(),
            "flexible": True,
            "search_mode": "flexible_only",
        }

        payload = {
            key: value
            for key, value in payload.items()
            if value not in ["", None]
        }

        try:
            data = await call_api(payload)
            total = await send_result(
                interaction,
                data,
                "MultiSearch Flexible",
                0xFEE75C,
            )
            await log_search(
                interaction.user,
                "MultiSearch Flexible",
                total,
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur : {safe_text(e)}",
                ephemeral=True,
            )


class PhoneModal(Modal, title="Recherche Téléphone"):
    telephone = TextInput(
        label="Téléphone",
        placeholder="Ex: 0612345678 / +33612345678",
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        payload = {
            "telephone": self.telephone.value.strip(),
            "flexible": False,
            "search_mode": "phone_exact",
        }

        try:
            data = await call_api(payload)
            total = await send_result(
                interaction,
                data,
                "Recherche Téléphone",
                0x57F287,
            )
            await log_search(
                interaction.user,
                "Téléphone",
                total,
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur : {safe_text(e)}",
                ephemeral=True,
            )


class Panel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🪪 Identité",
        style=discord.ButtonStyle.primary,
        custom_id="btn_identity",
    )
    async def identity(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(NameModal())

    @discord.ui.button(
        label="🧬 MultiSearch",
        style=discord.ButtonStyle.danger,
        custom_id="btn_multi",
    )
    async def multi(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MultiModal())

    @discord.ui.button(
        label="🌫️ Flexible",
        style=discord.ButtonStyle.secondary,
        custom_id="btn_multi_flexible",
    )
    async def multi_flexible(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MultiFlexibleModal())

    @discord.ui.button(
        label="📞 Téléphone",
        style=discord.ButtonStyle.success,
        custom_id="btn_phone",
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
        title="⚖️ MIKAMI JUSTICE",
        description=(
            "```ansi\n"
            "MIKAMI OSINT • CONTROL PANEL\n"
            "```\n"
            "🪪 **Identité** — Nom + prénom uniquement\n"
            "🧬 **MultiSearch** — Plusieurs infos à croiser\n"
            "🌫️ **Flexible** — Infos approximatives ou orthographe incertaine\n"
            "📞 **Téléphone** — Recherche par numéro\n\n"
            "`API Online` • `Résultats privés`"
        ),
        color=0x111318,
    )

    embed.set_thumbnail(url=LOGO_URL)

    banner_file = None
    if os.path.exists(BANNER_PATH):
        embed.set_image(url=f"attachment://{BANNER_ATTACHMENT_NAME}")
        banner_file = discord.File(
            BANNER_PATH,
            filename=BANNER_ATTACHMENT_NAME,
        )
    else:
        embed.set_image(url=BANNER_URL)

    embed.timestamp = discord.utils.utcnow()

    embed.set_footer(
        text="MIKAMI JUSTICE • Analyse. Comprends. Agis.",
        icon_url=LOGO_URL,
    )

    if banner_file:
        await channel.send(
            embed=embed,
            view=Panel(),
            file=banner_file,
        )
    else:
        await channel.send(
            embed=embed,
            view=Panel(),
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
        daemon=True,
    ).start()


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN manquant")

bot.run(TOKEN)
