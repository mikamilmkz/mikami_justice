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
# RECHERCHE POUR TON SITE
# =========================
@app.route("/search", methods=["POST"])
def search():
    data = request.json
    query = data.get("query")

    if not query:
        return jsonify({"error": "Aucune recherche"}), 400

    result = call_brixhub(query)

    history.append({"query": query, "result": result})

    return jsonify({"result": result})


# =========================
# API POUR DISCORD BOT
# =========================
@app.route("/api/search")
def api_search():
    query = request.args.get("q")

    if not query:
        return jsonify({"result": "Aucune recherche"}), 400

    result = call_brixhub(query)

    history.append({"query": query, "result": result})

    return jsonify({"result": result})


# =========================
# APPEL BRIXHUB
# =========================
def call_brixhub(query):
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

        # 🔥 FORMAT PROPRE
        results = data.get("data", {}).get("results", [])

        if not results:
            return "Aucun résultat trouvé"

        # 👉 exemple : afficher les 3 premiers
        output = ""
        for item in results[:3]:
            output += f"• {item}\n"

        return output

    except Exception as e:
        return f"Erreur API: {str(e)}"
           
# =========================
# HISTORIQUE (OPTION)
# =========================
@app.route("/history")
def get_history():
    return jsonify(history)


# =========================
# LANCEMENT
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
