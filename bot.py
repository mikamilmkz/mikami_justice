import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import requests
import threading
import time

import os

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = 1507891823031619746

BASE_URL = "https://mikami-justice.onrender.com"

API_SINGLE = f"{BASE_URL}/api/search?q="
API_MULTI = f"{BASE_URL}/api/multisearch"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# KEEP ALIVE (ANTI SLEEP)
# =========================
def keep_alive():
    while True:
        try:
            requests.get(BASE_URL)
        except:
            pass
        time.sleep(300)


# =========================
# MODAL NOM
# =========================
class NameModal(Modal, title="Recherche Nom + Prénom"):
    nom = TextInput(label="Nom")
    prenom = TextInput(label="Prénom")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        query = f"{self.nom.value} {self.prenom.value}"

        try:
            for _ in range(2):
                try:
                    r = requests.get(API_SINGLE + query, timeout=30)
                    break
                except:
                    continue

            data = r.json()

            if data["type"] == "text":
                embed = discord.Embed(
                    title="👤 Résultat",
                    description=data["content"],
                    color=0x5865F2
                )
                await interaction.followup.send(embed=embed)

            else:
                await interaction.followup.send(
                    content=f"📁 Résultats complets : {BASE_URL}{data['url']}"
                )

        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


# =========================
# MODAL MULTI
# =========================
class MultiModal(Modal, title="MultiSearch"):
    nom = TextInput(label="Nom", required=False)
    prenom = TextInput(label="Prénom", required=False)
    ville = TextInput(label="Ville", required=False)
    email = TextInput(label="Email", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        payload = {
            "nom": self.nom.value,
            "prenom": self.prenom.value,
            "ville": self.ville.value,
            "email": self.email.value
        }

        try:
            for _ in range(2):
                try:
                    r = requests.post(API_MULTI, json=payload, timeout=30)
                    break
                except:
                    continue

            data = r.json()

            if data["type"] == "text":
                embed = discord.Embed(
                    title="⚡ Résultat",
                    description=data["content"],
                    color=0xED4245
                )
                await interaction.followup.send(embed=embed)

            else:
                await interaction.followup.send(
                    content=f"📁 Résultats complets : {BASE_URL}{data['url']}"
                )

        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


# =========================
# PANEL
# =========================
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


# =========================
# SETUP PANEL
# =========================
async def setup_panel():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)

    async for msg in channel.history(limit=10):
        if msg.author == bot.user:
            await msg.delete()

    embed = discord.Embed(
        title="MIKAMI OSINT ⚖️",
        description="Choisis une recherche",
        color=0x2B2D31
    )

    await channel.send(embed=embed, view=Panel())


# =========================
# READY
# =========================
@bot.event
async def on_ready():
    print(f"Connecté : {bot.user}")

    bot.add_view(Panel())
    bot.loop.create_task(setup_panel())

    threading.Thread(target=keep_alive).start()


bot.run(TOKEN)
