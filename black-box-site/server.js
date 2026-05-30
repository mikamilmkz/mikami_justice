import express from "express";
import cors from "cors";
import path from "path";
import { fileURLToPath } from "url";

const app = express();
const PORT = process.env.PORT || 3001;

const MIKAMI_API_BASE =
  process.env.MIKAMI_API_BASE || "https://mikami-justice.onrender.com";

app.use(
  cors({
    origin: process.env.FRONTEND_ORIGIN || "http://localhost:5173",
  })
);

app.use(express.json({ limit: "1mb" }));

const allowedServices = new Set([
  "identity",
  "multisearch",
  "flexible",
  "phone",
]);

function cleanPayload(payload = {}) {
  const cleaned = {};

  for (const [key, value] of Object.entries(payload)) {
    if (value === undefined || value === null) continue;

    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!trimmed) continue;
      cleaned[key] = trimmed;
      continue;
    }

    cleaned[key] = value;
  }

  return cleaned;
}

function buildPayload(service, data = {}) {
  const clean = cleanPayload(data);

  if (service === "identity") {
    return cleanPayload({
      prenom: clean.prenom,
      nom_famille: clean.nom_famille,
      ville: clean.ville,
      flexible: true,
    });
  }

  if (service === "multisearch") {
    return cleanPayload({
      prenom: clean.prenom,
      nom_famille: clean.nom_famille,
      ville: clean.ville,
      email: clean.email,
      nom_utilisateur: clean.nom_utilisateur,
      flexible: true,
    });
  }

  if (service === "flexible") {
    return cleanPayload({
      prenom: clean.prenom,
      nom_famille: clean.nom_famille,
      ville: clean.ville,
      email: clean.email,
      nom_utilisateur: clean.nom_utilisateur,
      flexible: true,
      search_mode: "flexible_only",
    });
  }

  if (service === "phone") {
    return cleanPayload({
      telephone: clean.telephone,
      flexible: false,
      search_mode: "phone_exact",
    });
  }

  return clean;
}

function validatePayload(service, payload) {
  if (service === "identity") {
    if (!payload.prenom || !payload.nom_famille) {
      return "Prénom et nom obligatoires pour la recherche identité.";
    }
  }

  if (service === "phone") {
    if (!payload.telephone) {
      return "Numéro de téléphone obligatoire.";
    }
  }

  if (service === "multisearch" || service === "flexible") {
    const usefulKeys = [
      "prenom",
      "nom_famille",
      "ville",
      "email",
      "nom_utilisateur",
    ];

    const hasAtLeastOne = usefulKeys.some((key) => payload[key]);

    if (!hasAtLeastOne) {
      return "Remplis au moins un champ.";
    }
  }

  return null;
}

async function callMikamiApi(payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 70000);

  try {
    const response = await fetch(`${MIKAMI_API_BASE}/api/multisearch`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const body = await response.json().catch(() => null);

    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        message:
          body?.message ||
          body?.error ||
          "Erreur API pendant la recherche.",
      };
    }

    return {
      ok: true,
      status: response.status,
      data: body,
    };
  } catch (error) {
    if (error.name === "AbortError") {
      return {
        ok: false,
        status: 504,
        message: "Recherche trop longue. Réessaie dans quelques secondes.",
      };
    }

    return {
      ok: false,
      status: 502,
      message: error.message || "Impossible de contacter l’API.",
    };
  } finally {
    clearTimeout(timeout);
  }
}

app.get("/api/health", async (req, res) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const response = await fetch(`${MIKAMI_API_BASE}/health`, {
      signal: controller.signal,
    });

    const body = await response.json().catch(() => ({}));

    return res.json({
      ok: response.ok,
      local: "online",
      mikami: body?.status || "unknown",
    });
  } catch {
    return res.json({
      ok: false,
      local: "online",
      mikami: "offline",
    });
  } finally {
    clearTimeout(timeout);
  }
});

app.post("/api/search", async (req, res) => {
  const { service, data } = req.body || {};

  if (!allowedServices.has(service)) {
    return res.status(400).json({
      ok: false,
      message: "Service de recherche invalide.",
    });
  }

  const payload = buildPayload(service, data);
  const validationError = validatePayload(service, payload);

  if (validationError) {
    return res.status(400).json({
      ok: false,
      message: validationError,
    });
  }

  const apiResponse = await callMikamiApi(payload);

  if (!apiResponse.ok) {
    return res.status(apiResponse.status || 500).json({
      ok: false,
      message: apiResponse.message,
    });
  }

  const raw = apiResponse.data || {};
  const results = raw.results || [];
  const total = raw.total ?? results.length;

  return res.json({
    ok: true,
    service,
    searchedAt: new Date().toISOString(),
    total,
    payload,
    results,
  });
});
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);

app.use(express.static(path.join(__dirname, "dist")));

app.use((req, res) => {
  res.sendFile(path.join(__dirname, "dist", "index.html"));
});

app.listen(PORT, () => {
  console.log(`Black Box API lancée sur http://localhost:${PORT}`);
  console.log(`API cible : ${MIKAMI_API_BASE}`);
});
