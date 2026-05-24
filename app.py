from flask import Flask, render_template, request, jsonify, send_file
import requests
import os
import tempfile

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://brixhub.site/api/v1"

cache = {}
history = []


@app.route("/")
def index():
    return render_template("index.html")


def clean_value(value):
    if value is None or value == "":
        return "N/A"
    return str(value)


def format_results(results):
    output = ""

    for item in results:
        telephone = (
            item.get("telephone")
            or item.get("mobile")
            or item.get("tel")
            or item.get("phone")
            or "N/A"
        )

        adresse_complete = (
            item.get("adresse_complete")
            or item.get("adresse")
            or item.get("address")
            or "N/A"
        )

        complement = item.get("complement_adresse")
        if complement and complement not in str(adresse_complete):
            adresse_complete = f"{adresse_complete} {complement}"

        output += "────────────\n"
        output += f"👤 Prénom : {clean_value(item.get('prenom'))}\n"
        output += f"👤 Nom : {clean_value(item.get('nom_famille'))}\n"
        output += f"📧 Email : {clean_value(item.get('email'))}\n"
        output += f"📱 Téléphone : {clean_value(telephone)}\n"
        output += f"🏠 Adresse : {clean_value(adresse_complete)}\n"
        output += f"📍 Ville : {clean_value(item.get('ville'))}\n"
        output += f"📮 Code postal : {clean_value(item.get('code_postal'))}\n"
        output += f"🌍 Pays : {clean_value(item.get('pays'))}\n"
        output += f"🎂 Naissance : {clean_value(item.get('date_naissance'))}\n"
        output += f"💻 Username : {clean_value(item.get('nom_utilisateur'))}\n"
        output += f"🎯 Confiance : {clean_value(item.get('_confidence'))}%\n\n"

    return output


def build_response(results):
    formatted = format_results(results)

    return {
        "type": "text",
        "content": formatted
    }


def call_brixhub(payload):
    try:
        key = str(sorted(payload.items()))

        if key in cache:
            return cache[key]

        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }

        response = requests.post(
            f"{BASE_URL}/search",
            json=payload,
            headers=headers,
            timeout=20
        )

        data = response.json()
        results = data.get("data", {}).get("results", [])

        if not results:
            result = {
                "type": "text",
                "content": "Aucun résultat trouvé"
            }
        else:
            result = build_response(results)

        cache[key] = result
        return result

    except Exception as e:
        return {
            "type": "text",
            "content": f"Erreur API: {str(e)}"
        }


# IMPORTANT : route utilisée par le SITE
# Elle renvoie le format original Brixhub pour que ton frontend continue à marcher.
@app.route("/search", methods=["POST"])
def search():
    data = request.json or {}

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/search",
            json=data,
            headers=headers,
            timeout=20
        )

        result = response.json()
        history.append({
            "type": "site",
            "query": data,
            "result": result
        })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Route API simple pour le bot
@app.route("/api/search")
def api_search():
    query = request.args.get("q")

    if not query:
        return jsonify({
            "type": "text",
            "content": "Aucune recherche"
        }), 400

    result = call_brixhub({"query": query})
    history.append({
        "type": "simple",
        "query": query,
        "result": result
    })

    return jsonify(result)


# Route API multi pour le bot
@app.route("/api/multisearch", methods=["POST"])
def api_multisearch():
    data = request.json or {}

    clean_data = {
        k: v for k, v in data.items()
        if v not in ["", None]
    }

    if not clean_data:
        return jsonify({
            "type": "text",
            "content": "Aucune donnée"
        }), 400

    result = call_brixhub(clean_data)
    history.append({
        "type": "multi",
        "query": clean_data,
        "result": result
    })

    return jsonify(result)


@app.route("/download")
def download():
    path = request.args.get("path")

    if not path or not os.path.exists(path):
        return "Fichier introuvable", 404

    return send_file(path, as_attachment=True)


@app.route("/history")
def get_history():
    return jsonify(history)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
