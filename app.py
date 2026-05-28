from difflib import SequenceMatcher
import os
import re
import threading
import time
import unicodedata

import requests
from flask import Flask, jsonify, render_template, request


app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://brixhub.site/api/v1"
history = []

# Anti-429 : on limite les appels envoyés à Brixhub.
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
MIN_SECONDS_BETWEEN_BRIXHUB_CALLS = float(os.getenv("MIN_SECONDS_BETWEEN_BRIXHUB_CALLS", "0.9"))
MAX_MULTISEARCH_CALLS = int(os.getenv("MAX_MULTISEARCH_CALLS", "3"))
MAX_SIMPLE_SEARCH_CALLS = int(os.getenv("MAX_SIMPLE_SEARCH_CALLS", "2"))

_brixhub_cache = {}
_last_brixhub_call_at = 0.0
_brixhub_lock = threading.Lock()

FIELD_ALIASES = {
    "prenom": ["prenom", "first_name", "firstname", "given_name"],
    "nom_famille": ["nom_famille", "nom", "last_name", "lastname", "surname", "family_name"],
    "ville": ["ville", "city"],
    "email": ["email", "mail"],
    "telephone": ["telephone", "mobile", "tel", "phone"],
    "nom_utilisateur": ["nom_utilisateur", "username", "user", "pseudo"],
}


@app.route("/")
def index():
    return render_template("index.html")


def get_headers():
    return {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
    }


def safe_results(result):
    data_block = result.get("data") or {}
    results = data_block.get("results") or []
    meta = result.get("meta") or {}
    return results, meta


def normalize_text(value):
    if value is None:
        return ""

    text = str(value).lower().strip()
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    text = re.sub(r"[^a-z0-9@.+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_text(value):
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value))


def digits_only(value):
    return re.sub(r"\D+", "", str(value or ""))


def clean_payload(data):
    return {
        key: value.strip() if isinstance(value, str) else value
        for key, value in (data or {}).items()
        if value not in ["", None]
    }


def split_full_name(value):
    parts = normalize_text(value).split()

    if len(parts) < 2:
        return "", ""

    prenom = parts[0]
    nom_famille = " ".join(parts[1:])
    return prenom, nom_famille


def normalize_search_data(data):
    """
    Permet aussi les erreurs de saisie du type :
    - prénom = "Julie Barret", nom vide
    - nom = "Julie Barret", prénom vide
    """
    payload = clean_payload(data)

    prenom = payload.get("prenom", "")
    nom_famille = payload.get("nom_famille", "")

    if prenom and not nom_famille:
        guessed_prenom, guessed_nom = split_full_name(prenom)
        if guessed_prenom and guessed_nom:
            payload["prenom"] = guessed_prenom
            payload["nom_famille"] = guessed_nom
            payload["query"] = prenom

    elif nom_famille and not prenom:
        guessed_prenom, guessed_nom = split_full_name(nom_famille)
        if guessed_prenom and guessed_nom:
            payload["prenom"] = guessed_prenom
            payload["nom_famille"] = guessed_nom
            payload["query"] = nom_famille

    return payload


def get_item_value(item, field_name):
    for key in FIELD_ALIASES.get(field_name, [field_name]):
        value = item.get(key)
        if value not in [None, "", "N/A"]:
            return value
    return ""


def basic_match_score(query_value, item_value):
    query = normalize_text(query_value)
    candidate = normalize_text(item_value)

    if not query or not candidate:
        return 0

    if query == candidate:
        return 100

    query_compact = compact_text(query)
    candidate_compact = compact_text(candidate)

    if query_compact and query_compact == candidate_compact:
        return 96

    if candidate.startswith(query):
        return 88

    if f" {query} " in f" {candidate} ":
        return 82

    if query in candidate:
        return 70

    ratio = SequenceMatcher(None, query, candidate).ratio()
    return int(ratio * 65)


def phone_match_score(query_value, item_value):
    query = digits_only(query_value)
    candidate = digits_only(item_value)

    if not query or not candidate:
        return 0

    if query == candidate:
        return 100

    if candidate.endswith(query) or query.endswith(candidate):
        return 85

    ratio = SequenceMatcher(None, query, candidate).ratio()
    return int(ratio * 60)


def get_confidence(item):
    try:
        return int(item.get("_confidence") or 0)
    except Exception:
        return 0


def full_name_score(query_data, item):
    query_first = query_data.get("prenom", "")
    query_last = query_data.get("nom_famille", "")

    if not query_first or not query_last:
        return 0

    query_variants = [
        f"{query_first} {query_last}",
        f"{query_last} {query_first}",
    ]

    item_first = get_item_value(item, "prenom")
    item_last = get_item_value(item, "nom_famille")

    item_variants = [
        f"{item_first} {item_last}".strip(),
        f"{item_last} {item_first}".strip(),
        item.get("nom_complet") or "",
        item.get("full_name") or "",
        item.get("name") or "",
    ]

    best = 0

    for query_variant in query_variants:
        for item_variant in item_variants:
            best = max(best, basic_match_score(query_variant, item_variant))

    # Gros bonus si prénom + nom exacts, pour empêcher Julien/Barreteau de passer avant Julie/Barret.
    return best * 10


def result_score(item, query_data):
    score = full_name_score(query_data, item)

    weights = {
        "prenom": 4,
        "nom_famille": 4,
        "ville": 2,
        "email": 5,
        "telephone": 5,
        "nom_utilisateur": 4,
    }

    for field_name, weight in weights.items():
        query_value = query_data.get(field_name)

        if not query_value:
            continue

        item_value = get_item_value(item, field_name)

        if field_name == "telephone":
            score += phone_match_score(query_value, item_value) * weight
        else:
            score += basic_match_score(query_value, item_value) * weight

    return score


def sort_results(results, query_data):
    clean_query = {
        key: value
        for key, value in (query_data or {}).items()
        if key not in ["flexible", "query"] and value not in ["", None]
    }

    if not clean_query:
        return results

    return sorted(
        results,
        key=lambda item: (result_score(item, clean_query), get_confidence(item)),
        reverse=True,
    )


def exact_identity_match(query_data, item):
    query_first = compact_text(query_data.get("prenom", ""))
    query_last = compact_text(query_data.get("nom_famille", ""))

    if query_first and query_last:
        item_first = compact_text(get_item_value(item, "prenom"))
        item_last = compact_text(get_item_value(item, "nom_famille"))

        if item_first == query_first and item_last == query_last:
            return True

        full_variants = [
            compact_text(f"{query_data.get('prenom', '')} {query_data.get('nom_famille', '')}"),
            compact_text(f"{query_data.get('nom_famille', '')} {query_data.get('prenom', '')}"),
        ]
        item_variants = [
            compact_text(f"{get_item_value(item, 'prenom')} {get_item_value(item, 'nom_famille')}"),
            compact_text(f"{get_item_value(item, 'nom_famille')} {get_item_value(item, 'prenom')}"),
            compact_text(item.get("nom_complet") or ""),
            compact_text(item.get("full_name") or ""),
            compact_text(item.get("name") or ""),
        ]

        if any(value and value in full_variants for value in item_variants):
            return True

    query_email = compact_text(query_data.get("email", ""))
    if query_email and compact_text(get_item_value(item, "email")) == query_email:
        return True

    query_phone = digits_only(query_data.get("telephone", ""))
    if query_phone and digits_only(get_item_value(item, "telephone")) == query_phone:
        return True

    return False


def has_exact_identity_match(results, query_data):
    return any(exact_identity_match(query_data, item) for item in results)


def should_stop_search(results, query_data):
    if not results:
        return False

    # Si on a trouvé l'identité exacte, inutile de spammer Brixhub avec d'autres variantes.
    if has_exact_identity_match(results, query_data):
        return True

    # Pour les recherches sans prénom/nom, on garde l'ancien comportement : un bon retour suffit.
    has_identity_name = bool(query_data.get("prenom") or query_data.get("nom_famille"))
    if not has_identity_name:
        return True

    return False


def result_identity_key(item):
    parts = [
        compact_text(get_item_value(item, "prenom")),
        compact_text(get_item_value(item, "nom_famille")),
        compact_text(get_item_value(item, "ville")),
        compact_text(item.get("date_naissance") or ""),
        digits_only(get_item_value(item, "telephone")),
        compact_text(get_item_value(item, "email")),
    ]

    key = "|".join(part for part in parts if part)

    if key:
        return key

    return compact_text(str(item))[:200]


def merge_results(result_groups):
    merged = []
    seen = set()

    for results in result_groups:
        for item in results:
            key = result_identity_key(item)

            if key in seen:
                continue

            seen.add(key)
            merged.append(item)

    return merged


def add_unique_payload(payloads, payload):
    cleaned = clean_payload(payload)
    marker = tuple(sorted((key, str(value)) for key, value in cleaned.items()))

    for existing in payloads:
        existing_marker = tuple(sorted((key, str(value)) for key, value in existing.items()))
        if marker == existing_marker:
            return

    payloads.append(cleaned)


def build_search_payloads(clean_data):
    """
    Version anti-429 : peu d'appels, dans le bon ordre.
    1) exact structuré
    2) recherche texte exacte prénom + nom
    3) flexible seulement en secours
    """
    base = dict(clean_data)
    base.pop("query", None)

    payloads = []
    identity_fields = bool(base.get("prenom") or base.get("nom_famille"))
    prenom = base.get("prenom", "")
    nom_famille = base.get("nom_famille", "")

    if identity_fields:
        exact_payload = dict(base)
        exact_payload["flexible"] = False
        add_unique_payload(payloads, exact_payload)

    if prenom and nom_famille:
        full_name = f"{prenom} {nom_famille}".strip()
        add_unique_payload(payloads, {"query": full_name, "flexible": False})

    flexible_payload = dict(base)
    flexible_payload["flexible"] = True
    add_unique_payload(payloads, flexible_payload)

    return payloads[:MAX_MULTISEARCH_CALLS]


def cache_key_for_payload(payload):
    cleaned = clean_payload(payload)
    return tuple(sorted((key, str(value)) for key, value in cleaned.items()))


def get_cached_brixhub_response(payload):
    now = time.time()
    cache_key = cache_key_for_payload(payload)
    cached = _brixhub_cache.get(cache_key)

    if not cached:
        return None

    saved_at, result = cached
    if now - saved_at > CACHE_TTL_SECONDS:
        _brixhub_cache.pop(cache_key, None)
        return None

    return result


def save_cached_brixhub_response(payload, result):
    _brixhub_cache[cache_key_for_payload(payload)] = (time.time(), result)

    # Petit nettoyage pour éviter que la RAM grossisse sans fin.
    if len(_brixhub_cache) > 300:
        oldest_keys = sorted(
            _brixhub_cache,
            key=lambda key: _brixhub_cache[key][0],
        )[:100]
        for key in oldest_keys:
            _brixhub_cache.pop(key, None)


def call_brixhub(payload, timeout=35):
    global _last_brixhub_call_at

    if not API_KEY:
        return {"ok": False, "error": "API_KEY manquante côté serveur."}, 500

    cached = get_cached_brixhub_response(payload)
    if cached is not None:
        return {"ok": True, "data": cached, "cached": True}, 200

    try:
        with _brixhub_lock:
            elapsed = time.time() - _last_brixhub_call_at
            wait_time = MIN_SECONDS_BETWEEN_BRIXHUB_CALLS - elapsed
            if wait_time > 0:
                time.sleep(wait_time)

            response = requests.post(
                f"{BASE_URL}/search",
                json=payload,
                headers=get_headers(),
                timeout=timeout,
            )
            _last_brixhub_call_at = time.time()

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_message = f" Attends environ {retry_after} secondes." if retry_after else " Réessaie dans quelques instants."
            return {
                "ok": False,
                "error": "Brixhub limite les requêtes pour le moment." + wait_message,
                "rate_limited": True,
            }, 429

        response.raise_for_status()
        result = response.json()
        save_cached_brixhub_response(payload, result)
        return {"ok": True, "data": result}, 200

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "⏳ API Brixhub trop lente, réessaie dans quelques secondes."}, 504

    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"Erreur réseau API : {str(e)}"}, 502

    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


def append_history(entry):
    history.append(entry)
    if len(history) > 100:
        del history[: len(history) - 100]


@app.route("/search", methods=["POST"])
def search():
    data = normalize_search_data(request.json or {})

    result, status = call_brixhub(data)

    if not result.get("ok"):
        return jsonify({"error": result.get("error", "Erreur inconnue")}), status

    api_result = result["data"]
    results, meta = safe_results(api_result)
    sorted_results = sort_results(results, data)

    if isinstance(api_result.get("data"), dict):
        api_result["data"]["results"] = sorted_results

    append_history({
        "type": "site",
        "query": data,
        "total": meta.get("total", len(sorted_results)),
        "cached": bool(result.get("cached")),
    })

    return jsonify(api_result)


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify({"type": "raw", "results": [], "total": 0}), 400

    payloads = [
        {"query": query, "flexible": False},
        {"query": query, "flexible": True},
    ][:MAX_SIMPLE_SEARCH_CALLS]

    result_groups = []
    searched_payloads = []
    last_error = None
    last_status = 502

    for payload in payloads:
        result, status = call_brixhub(payload)
        searched_payloads.append({"payload": payload, "status": status, "cached": bool(result.get("cached"))})

        if not result.get("ok"):
            last_error = result.get("error", "Erreur inconnue")
            last_status = status
            if result.get("rate_limited"):
                break
            continue

        api_result = result["data"]
        results, _meta = safe_results(api_result)
        result_groups.append(results)

        if results:
            break

    if not result_groups:
        return jsonify({"type": "error", "message": last_error or "Erreur inconnue"}), last_status

    merged_results = merge_results(result_groups)
    sorted_results = sort_results(merged_results, {"query": query})

    append_history({
        "type": "bot-simple",
        "query": query,
        "payloads": searched_payloads,
        "total": len(sorted_results),
    })

    return jsonify({
        "type": "raw",
        "results": sorted_results,
        "total": len(sorted_results),
    })


@app.route("/api/multisearch", methods=["POST"])
def api_multisearch():
    clean_data = normalize_search_data(request.json or {})

    if not clean_data:
        return jsonify({"type": "raw", "results": [], "total": 0}), 400

    payloads = build_search_payloads(clean_data)
    result_groups = []
    searched_payloads = []
    last_error = None
    last_status = 502

    for payload in payloads:
        result, status = call_brixhub(payload)
        searched_payloads.append({"payload": payload, "status": status, "cached": bool(result.get("cached"))})

        if not result.get("ok"):
            last_error = result.get("error", "Erreur inconnue")
            last_status = status
            if result.get("rate_limited"):
                break
            continue

        api_result = result["data"]
        results, _meta = safe_results(api_result)
        result_groups.append(results)

        if should_stop_search(results, clean_data):
            break

    if not result_groups:
        return jsonify({
            "type": "error",
            "message": last_error or "Erreur inconnue",
        }), last_status

    merged_results = merge_results(result_groups)
    sorted_results = sort_results(merged_results, clean_data)

    append_history({
        "type": "bot",
        "query": clean_data,
        "payloads": searched_payloads,
        "total": len(sorted_results),
    })

    return jsonify({
        "type": "raw",
        "results": sorted_results,
        "total": len(sorted_results),
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "service": "MIKAMI OSINT API",
    })


@app.route("/history")
def get_history():
    return jsonify(history)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
