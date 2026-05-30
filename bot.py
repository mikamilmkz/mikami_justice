import asyncio
import json
import os
import threading
import time
from datetime import datetime, timezone

import discord
import requests
from discord.ext import commands
from discord.ui import Button, Modal, TextInput, View


TOKEN = os.getenv("DISCORD_TOKEN")

SEARCH_CHANNEL_ID = 1507891823031619746
RESULTS_CHANNEL_ID = 1507891868489482431


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


ADMIN_LOG_CHANNEL_ID = 1509730558685483108

BASE_URL = "https://mikami-justice.onrender.com"
API_MULTI = f"{BASE_URL}/api/multisearch"
LOGO_URL = f"{BASE_URL}/static/logo.png"
BANNER_URL = f"{BASE_URL}/static/blackbox_banner.png"
BANNER_PATH = os.getenv("BANNER_PATH", "static/blackbox_banner.png")
BANNER_ATTACHMENT_NAME = "blackbox_banner.png"

RESULTS_PER_PAGE = 2

# Limites quotidiennes
NORMAL_DAILY_SEARCH_LIMIT = 30
QUOTA_FILE = os.getenv("QUOTA_FILE", "data/user_search_quota.json")

# Donateurs illimités :
# - soit via un rôle dont le nom est dans DONATOR_ROLE_NAMES
# - soit en ajoutant directement l'ID du rôle dans DONATOR_ROLE_IDS
DONATOR_ROLE_IDS = {
    # 123456789012345678,
}
DONATOR_ROLE_NAMES = {
    "soutien",
    "donateur",
    "donnateur",
    "donator",
    "supporter",
    "premium",
    "vip",
}

_quota_lock = threading.Lock()

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


def today_utc_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_quota_state():
    today = today_utc_key()

    try:
        with open(QUOTA_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)
    except Exception:
        state = {"date": today, "users": {}}

    if not isinstance(state, dict):
        state = {"date": today, "users": {}}

    if state.get("date") != today:
        state = {"date": today, "users": {}}

    if not isinstance(state.get("users"), dict):
        state["users"] = {}

    return state


def save_quota_state(state):
    try:
        os.makedirs(os.path.dirname(QUOTA_FILE) or ".", exist_ok=True)
        with open(QUOTA_FILE, "w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Impossible de sauvegarder le quota utilisateur : {e}")


def user_has_unlimited_searches(user):
    # Les administrateurs gardent un accès illimité.
    permissions = getattr(user, "guild_permissions", None)
    if permissions and getattr(permissions, "administrator", False):
        return True

    roles = getattr(user, "roles", []) or []

    for role in roles:
        if getattr(role, "id", None) in DONATOR_ROLE_IDS:
            return True

        role_name = str(getattr(role, "name", "")).strip().lower()
        if role_name in DONATOR_ROLE_NAMES:
            return True

    return False


def consume_daily_quota(user):
    if user_has_unlimited_searches(user):
        return True, None, NORMAL_DAILY_SEARCH_LIMIT

    user_id = str(user.id)

    with _quota_lock:
        state = load_quota_state()
        users = state["users"]
        used = int(users.get(user_id, 0) or 0)

        if used >= NORMAL_DAILY_SEARCH_LIMIT:
            return False, used, NORMAL_DAILY_SEARCH_LIMIT

        used += 1
        users[user_id] = used
        save_quota_state(state)

    return True, used, NORMAL_DAILY_SEARCH_LIMIT


async def log_quota_blocked(user, search_type, payload, used, limit):
    channel = await get_admin_log_channel()

    if not channel:
        return

    embed = discord.Embed(
        title="⛔ Recherche bloquée",
        color=0xED4245,
    )

    embed.add_field(
        name="Utilisateur",
        value=f"{user.mention}\n`{user}`",
        inline=True,
    )

    embed.add_field(
        name="Mode",
        value=f"**{search_type}**",
        inline=True,
    )

    embed.add_field(
        name="Limite",
        value=f"`{used}/{limit}` recherches aujourd’hui",
        inline=True,
    )

    embed.add_field(
        name="Champs utilisés",
        value=f"`{payload_fields(payload)}`",
        inline=False,
    )

    embed.set_footer(
        text="BLACKBOX • Limite quotidienne utilisateur",
        icon_url=LOGO_URL,
    )

    embed.timestamp = discord.utils.utcnow()

    try:
        await channel.send(embed=embed)
    except Exception:
        pass


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
            title=f"⬛ {self.title}",
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
            text="BLACKBOX • Résultats privés",
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


async def get_admin_log_channel():
    channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)

    if channel:
        return channel

    try:
        return await bot.fetch_channel(ADMIN_LOG_CHANNEL_ID)
    except Exception:
        return None


def payload_fields(payload):
    labels = {
        "nom_famille": "nom",
        "nom": "nom",
        "prenom": "prénom",
        "ville": "ville",
        "email": "email",
        "telephone": "téléphone",
        "mobile": "téléphone",
        "tel": "téléphone",
        "phone": "téléphone",
        "nom_utilisateur": "username",
        "username": "username",
        "date_naissance": "date de naissance",
        "code_postal": "code postal",
        "pays": "pays",
    }

    ignored = {"flexible", "search_mode"}
    fields = []

    for key, value in payload.items():
        if key in ignored or value in [None, ""]:
            continue

        fields.append(labels.get(key, key))

    return ", ".join(dict.fromkeys(fields)) or "aucun champ"


def search_mode_label(payload):
    mode = payload.get("search_mode")

    if mode == "flexible_only":
        return "Flexible direct"

    if mode == "phone_exact":
        return "Exact téléphone"

    if payload.get("flexible") is False:
        return "Exact"

    return "Intelligent"


def outcome_label(data, total, error=None):
    if error:
        return "❌ Erreur"

    if not isinstance(data, dict):
        return "⚠️ Réponse invalide"

    if data.get("type") == "error":
        return "❌ Erreur API"

    if data.get("type") == "raw":
        if total and total > 0:
            return "✅ Résultat trouvé"

        return "🔎 Aucun résultat"

    return "⚠️ Réponse inattendue"


async def log_admin_search(user, search_type, payload, total, elapsed_ms, data=None, error=None):
    channel = await get_admin_log_channel()

    if not channel:
        return

    embed = discord.Embed(
        title="📊 Log recherche",
        color=0x2B2D31,
    )

    embed.add_field(
        name="Utilisateur",
        value=f"{user.mention}\n`{user}`",
        inline=True,
    )

    embed.add_field(
        name="Mode",
        value=f"**{search_type}**\n`{search_mode_label(payload)}`",
        inline=True,
    )

    embed.add_field(
        name="Statut",
        value=outcome_label(data, total, error),
        inline=True,
    )

    embed.add_field(
        name="Champs utilisés",
        value=f"`{payload_fields(payload)}`",
        inline=False,
    )

    embed.add_field(
        name="Résultats",
        value=f"`{total}`",
        inline=True,
    )

    embed.add_field(
        name="Temps API",
        value=f"`{elapsed_ms} ms`",
        inline=True,
    )

    if error:
        embed.add_field(
            name="Erreur",
            value=f"```txt\n{safe_text(error, 500)}\n```",
            inline=False,
        )
    elif isinstance(data, dict) and data.get("type") == "error":
        embed.add_field(
            name="Erreur API",
            value=f"```txt\n{safe_text(data.get('message'), 500)}\n```",
            inline=False,
        )

    embed.set_footer(
        text="BLACKBOX • Logs admin • Données sensibles masquées",
        icon_url=LOGO_URL,
    )

    embed.timestamp = discord.utils.utcnow()

    try:
        await channel.send(embed=embed)
    except Exception:
        pass


async def log_public_search(user, search_type, total, data=None, error=None):
    channel = bot.get_channel(RESULTS_CHANNEL_ID)

    if not channel:
        try:
            channel = await bot.fetch_channel(RESULTS_CHANNEL_ID)
        except Exception:
            return

    if error or (isinstance(data, dict) and data.get("type") == "error"):
        status = "Erreur"
    elif total and total > 0:
        status = "Résultat trouvé"
    else:
        status = "Aucun résultat"

    embed = discord.Embed(
        title=" Nouvelle recherche",
        description=(
            f" Utilisateur : {user.mention}\n"
            f" Type : **{search_type}**\n"
            f" Statut : **{status}**\n"
            f" Résultats : **{total}**\n"
            f" Données : privées"
        ),
        color=0x2B2D31,
    )

    embed.set_footer(
        text="BLACKBOX • Logs publics",
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
                title=f"⬛ {title}",
                description="Aucun résultat trouvé",
                color=color,
            )

            embed.set_thumbnail(url=LOGO_URL)
            embed.set_footer(
                text="BLACKBOX",
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


async def execute_search(interaction, payload, title, color, search_type):
    start_time = time.perf_counter()

    allowed, used, limit = consume_daily_quota(interaction.user)

    if not allowed:
        await interaction.followup.send(
            (
                "⛔ Limite quotidienne atteinte.\n"
                f"Tu as déjà utilisé **{used}/{limit}** recherches aujourd’hui.\n"
                "Les donateurs ont un accès illimité."
            ),
            ephemeral=True,
        )

        await log_quota_blocked(
            interaction.user,
            search_type,
            payload,
            used,
            limit,
        )
        return

    try:
        data = await call_api(payload)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        total = await send_result(
            interaction,
            data,
            title,
            color,
        )

        await log_admin_search(
            interaction.user,
            search_type,
            payload,
            total,
            elapsed_ms,
            data=data,
        )

        await log_public_search(
            interaction.user,
            search_type,
            total,
            data=data,
        )

    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        await interaction.followup.send(
            f"❌ Erreur : {safe_text(e)}",
            ephemeral=True,
        )

        await log_admin_search(
            interaction.user,
            search_type,
            payload,
            0,
            elapsed_ms,
            error=e,
        )

        await log_public_search(
            interaction.user,
            search_type,
            0,
            error=e,
        )


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

        await execute_search(
            interaction,
            payload,
            "Recherche Identité",
            0x5865F2,
            "Identité",
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

        await execute_search(
            interaction,
            payload,
            "MultiSearch",
            0xED4245,
            "MultiSearch",
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

        await execute_search(
            interaction,
            payload,
            "MultiSearch Flexible",
            0xFEE75C,
            "Flexible",
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

        await execute_search(
            interaction,
            payload,
            "Recherche Téléphone",
            0x57F287,
            "Téléphone",
        )


async def open_modal_safely(interaction: discord.Interaction, modal: Modal):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_modal(modal)
            return

        await interaction.followup.send(
            "⚠️ Interaction déjà traitée. Reclique sur le bouton.",
            ephemeral=True,
        )
    except discord.NotFound:
        # Discord renvoie souvent 10062 quand l'interaction a expiré
        # ou si deux instances du bot essaient de répondre au même clic.
        print("Interaction expirée ou déjà consommée avant l'ouverture du modal.")
    except discord.HTTPException as e:
        print(f"Erreur Discord pendant l'ouverture du modal : {e}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⚠️ Impossible d’ouvrir le formulaire. Réessaie dans quelques secondes.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "⚠️ Impossible d’ouvrir le formulaire. Réessaie dans quelques secondes.",
                    ephemeral=True,
                )
        except Exception:
            pass


class Panel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🪪 Identité",
        style=discord.ButtonStyle.primary,
        custom_id="btn_identity",
    )
    async def identity(self, interaction: discord.Interaction, button: Button):
        await open_modal_safely(interaction, NameModal())

    @discord.ui.button(
        label="🧬 MultiSearch",
        style=discord.ButtonStyle.danger,
        custom_id="btn_multi",
    )
    async def multi(self, interaction: discord.Interaction, button: Button):
        await open_modal_safely(interaction, MultiModal())

    @discord.ui.button(
        label="🌫️ Flexible",
        style=discord.ButtonStyle.secondary,
        custom_id="btn_multi_flexible",
    )
    async def multi_flexible(self, interaction: discord.Interaction, button: Button):
        await open_modal_safely(interaction, MultiFlexibleModal())

    @discord.ui.button(
        label="📞 Téléphone",
        style=discord.ButtonStyle.success,
        custom_id="btn_phone",
    )
    async def phone(self, interaction: discord.Interaction, button: Button):
        await open_modal_safely(interaction, PhoneModal())


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
        title="⬛ BLACKBOX",
        description=(
            "```ansi\n"
            "BLACKBOX // QUERY PANEL\n"
            "```\n"
            "**Interface privée de recherche et de recoupement.**\n\n"
            "`IDENTITY`  Nom + prénom uniquement\n"
            "`MULTI`     Plusieurs informations à croiser\n"
            "`FLEX`      Données approximatives\n"
            "`PHONE`     Recherche par numéro exact\n\n"
            "`status: online` • `output: private`"
        ),
        color=0x050505,
    )

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
        text="BLACKBOX • private query interface",
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
