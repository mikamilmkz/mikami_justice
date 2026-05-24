import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import requests
import threading
import time

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = 1507891823031619746  # remplace par l'ID du salon

BASE_URL = "https://mikami-justice.onrender.com"
API_MULTI = f"{BASE_URL}/api/multisearch"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def keep_alive():
    while True:
        try:
            requests.get(BASE_URL, timeout=10)
        except:
            pass
        time.sleep(300)


async def send_result(interaction, data, title, color):
    if data.get("type") == "text":
        embed = discord.Embed(
            title=title,
            description=data.get("content", "Aucun résultat"),
            color=color
        )
        embed.set_footer(text="MIKAMI OSINT")
        await interaction.followup.send(embed=embed)

    elif data.get("type") == "file":
        await interaction.followup.send(
            content=f"📁 Résultats complets : {BASE_URL}{data.get('url')}"
        )

    else:
        await interaction.followup.send(
            content=f"⚠️ Réponse inattendue : {data}",
            ephemeral=True
        )


class NameModal(Modal, title="Recherche Nom + Prénom"):
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
            await send_result(
                interaction,
                data,
                "👤 Résultat Nom + Prénom",
                0x5865F2
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


class MultiModal(Modal, title="MultiSearch"):
    nom = TextInput(label="Nom", required=False, placeholder="Nom de famille")
    prenom = TextInput(label="Prénom", required=False)
    ville = TextInput(label="Ville", required=False)
    email = TextInput(label="Email", required=False)
    username = TextInput(label="Username", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        payload = {
            "nom_famille": self.nom.value.strip(),
            "prenom": self.prenom.value.strip(),
            "ville": self.ville.value.strip(),
            "email": self.email.value.strip(),
            "nom_utilisateur": self.username.value.strip(),
            "flexible": True
        }

        payload = {k: v for k, v in payload.items() if v}

        try:
            r = requests.post(API_MULTI, json=payload, timeout=30)
            data = r.json()
            await send_result(
                interaction,
                data,
                "⚡ Résultat MultiSearch",
                0xED4245
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


class Panel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="👤 Nom + Prénom",
        style=discord.ButtonStyle.primary,
        custom_id="btn_name"
    )
    async def name(self, interaction: discord.Interaction, button: Button):
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
        title="MIKAMI OSINT ⚖️",
        description="Choisis une méthode de recherche.",
        color=0x2B2D31
    )
    embed.add_field(
        name="👤 Nom + Prénom",
        value="Recherche ciblée avec nom de famille + prénom.",
        inline=False
    )
    embed.add_field(
        name="⚡ MultiSearch",
        value="Recherche avancée avec plusieurs champs.",
        inline=False
    )
    embed.set_footer(text="MIKAMI OSINT")

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
    raise RuntimeError("DISCORD_TOKEN manquant. Fais: export DISCORD_TOKEN='TON_TOKEN'")

bot.run(TOKEN)
