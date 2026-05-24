from flask import Flask, render_template, request, jsonify, send_file
import requests
import os
import tempfile

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://brixhub.site/api/v1"

# 🔥 CACHE MÉMOIRE
cache = {}

history = []


# =========================
# PAGE
# =========================
@app.route("/")
def index():
    return render_template("index.html")


# =========================
# FORMAT RESULTATS
# =========================
def format_results(results):
    output = ""

    for item in results:
        output += "────────────\n"

        output += f"👤 Prénom : {item.get('prenom', 'N/A')}\n"
        output += f"👤 Nom : {item.get('nom_famille', 'N/A')}\n"
        output += f"📧 Email : {item.get('email', 'N/A')}\n"
        output += f"📍 Ville : {item.get('ville', 'N/A')}\n"
        output += f"📮 Code postal : {item.get('code_postal', 'N/A')}\n"
        output += f"🎂 Naissance : {item.get('date_naissance', 'N/A')}\n"
        output += f"💻 Username : {item.get('nom_utilisateur', 'N/A')}\n"

        output += "\n"

    return output


# =========================
# GESTION LIMITE DISCORD
# =========================
def build_response(results):
    formatted = format_results(results)

    if len(formatted) > 3500:
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
        temp.write(formatted)
        temp.close()

        return {
            "type": "file",
            "url": f"/download?path={temp.name}"
        }

    return {
        "type": "text",
        "content": formatted
    }


# =========================
# APPEL API (AVEC CACHE)
# =========================
def call_brixhub(payload):
    try:
        key = str(payload)

        # 🔥 CACHE
        if key in cache:
            return cache[key]

        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }

        r = requests.post(f"{BASE_URL}/search", json=payload, headers=headers, timeout=15)
        data = r.json()

        results = data.get("data", {}).get("results", [])

        if not results:
            result = {"type": "text", "content": "Aucun résultat trouvé"}
        else:
            result = build_response(results)

        cache[key] = result

        return result

    except Exception as e:
        return {"type": "text", "content": f"Erreur API: {str(e)}"}


# =========================
# API SIMPLE
# =========================
@app.route("/api/search")
def api_search():
    query = request.args.get("q")

    if not query:
        return jsonify({"type": "text", "content": "Aucune recherche"}), 400

    result = call_brixhub({"query": query})
    history.append(result)

    return jsonify(result)


# =========================
# API MULTI (OPTIMISÉ)
# =========================
@app.route("/api/multisearch", methods=["POST"])
def api_multisearch():
    data = request.json

    if not data:
        return jsonify({"type": "text", "content": "Aucune donnée"}), 400

    # 🔥 SUPPRIME CHAMPS VIDES
    clean_data = {k: v for k, v in data.items() if v}

    result = call_brixhub(clean_data)
    history.append(result)

    return jsonify(result)


# =========================
# DOWNLOAD
# =========================
@app.route("/download")
def download():
    path = request.args.get("path")

    if not path or not os.path.exists(path):
        return "Fichier introuvable", 404

    return send_file(path, as_attachment=True)


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
