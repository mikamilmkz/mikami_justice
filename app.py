from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://brixhub.site/api/v1"

# 🔥 HISTORIQUE EN MÉMOIRE
history = []


# =========================
# PAGE PRINCIPALE
# =========================
@app.route("/")
def index():
    return render_template("index.html")


# =========================
# RECHERCHE SIMPLE (SITE)
# =========================
@app.route("/search", methods=["POST"])
def search():
    data = request.json
    query = data.get("query")

    if not query:
        return jsonify({"error": "Aucune recherche"}), 400

    result = call_brixhub_simple(query)

    history.append({"type": "simple", "query": query, "result": result})

    return jsonify({"result": result})


# =========================
# API BOT (RECHERCHE SIMPLE)
# =========================
@app.route("/api/search")
def api_search():
    query = request.args.get("q")

    if not query:
        return jsonify({"result": "Aucune recherche"}), 400

    result = call_brixhub_simple(query)

    history.append({"type": "simple", "query": query, "result": result})

    return jsonify({"result": result})


# =========================
# API BOT (MULTI SEARCH)
# =========================
@app.route("/api/multisearch", methods=["POST"])
def api_multisearch():
    data = request.json

    result = call_brixhub_multi(data)

    history.append({"type": "multi", "query": data, "result": result})

    return jsonify({"result": result})


# =========================
# BRIxHUB SIMPLE
# =========================
def call_brixhub_simple(query):
    try:
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }

        payload = {
            "query": query
        }

        url = f"{BASE_URL}/search"

        r = requests.post(url, json=payload, headers=headers, timeout=10)
        data = r.json()

        results = data.get("data", {}).get("results", [])

        if not results:
            return "Aucun résultat trouvé"

        output = ""
        for item in results[:3]:
            output += f"• {item}\n"

        return output

    except Exception as e:
        return f"Erreur API: {str(e)}"


# =========================
# BRIxHUB MULTI
# =========================
def call_brixhub_multi(data):
    try:
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }

        # 👉 envoie directement les champs remplis
        url = f"{BASE_URL}/search"

        r = requests.post(url, json=data, headers=headers, timeout=10)
        res = r.json()

        results = res.get("data", {}).get("results", [])

        if not results:
            return "Aucun résultat trouvé"

        output = ""
        for item in results[:3]:
            output += f"• {item}\n"

        return output

    except Exception as e:
        return f"Erreur API: {str(e)}"


# =========================
# HISTORIQUE
# =========================
@app.route("/history")
def get_history():
    return jsonify(history)


# =========================
# LANCEMENT
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
