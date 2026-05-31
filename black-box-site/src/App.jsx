import { useMemo, useState } from "react";
import {
  BrowserRouter,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Bot,
  Boxes,
  CheckCircle2,
  CreditCard,
  Crown,
  ExternalLink,
  Home,
  LayoutDashboard,
  LifeBuoy,
  Lock,
  Mail,
  Phone,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
  UserRound,
  Users,
  Zap,
} from "lucide-react";
import "./index.css";

const API_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? "http://localhost:3001" : "");

const DISCORD_URL = "https://discord.gg/MVfsWDVe";
const DISCORD_USERNAME = "@mullvad0817";
const SUPPORT_EMAIL = "mikami41kl@outlook.fr";
const HISTORY_KEY = "blackbox_search_history";

const services = [
  {
    title: "Recherche privée",
    desc: "Panel de recherche connecté à l’API Mikami avec résultats propres.",
    tag: "Search",
    icon: Search,
  },
  {
    title: "Bot Discord",
    desc: "Même logique que le site : panel, résultats privés, logs et pagination.",
    tag: "Discord",
    icon: Bot,
  },
  {
    title: "Dashboard",
    desc: "Vue centrale pour suivre l’activité locale, les accès et les statuts.",
    tag: "Account",
    icon: LayoutDashboard,
  },
  {
    title: "Monitoring",
    desc: "Suivi de disponibilité du site, du backend local et de l’API.",
    tag: "Status",
    icon: Activity,
  },
];

function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}

function Shell() {
  const location = useLocation();

  const pageName = useMemo(() => {
    const map = {
      "/": "Accueil",
      "/dashboard": "Dashboard",
      "/services": "Services",
      "/search": "Search",
      "/bot": "Bot Discord",
      "/pricing": "Tarifs",
      "/status": "Statut",
      "/support": "Support",
      "/legal": "Légal",
    };

    return map[location.pathname] || "Black Box";
  }, [location.pathname]);

  return (
    <div className="app">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <div className="brand-icon">
            <Sparkles size={22} />
          </div>
          <div>
            <strong>Black Box</strong>
            <span>Premium Hub</span>
          </div>
        </NavLink>

        <nav className="nav">
          <NavItem to="/" icon={Home} label="Accueil" />
          <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" />
          <NavItem to="/services" icon={Boxes} label="Services" />
          <NavItem to="/search" icon={Search} label="Search" />
          <NavItem to="/bot" icon={Bot} label="Bot Discord" />
          <NavItem to="/pricing" icon={CreditCard} label="Tarifs" />
          <NavItem to="/status" icon={Activity} label="Statut" />
          <NavItem to="/support" icon={LifeBuoy} label="Support" />
          <NavItem to="/legal" icon={ShieldCheck} label="Légal" />
        </nav>

        <div className="sidebar-card">
          <Lock size={18} />
          <p>Accès sécurisé, interface propre, services modulables.</p>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <span className="eyebrow">Black Box Platform</span>
            <h1>{pageName}</h1>
          </div>

          <div className="topbar-actions">
            <a
              className="ghost-btn"
              href={DISCORD_URL}
              target="_blank"
              rel="noreferrer"
            >
              Rejoindre Discord
            </a>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/services" element={<Services />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/bot" element={<BotPage />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/status" element={<Status />} />
          <Route path="/support" element={<Support />} />
          <Route path="/legal" element={<Legal />} />
        </Routes>
      </main>
    </div>
  );
}

function NavItem({ to, icon: Icon, label }) {
  return (
    <NavLink to={to} className="nav-item">
      <Icon size={18} />
      <span>{label}</span>
    </NavLink>
  );
}

function HomePage() {
  return (
    <section className="page-grid">
      <div className="hero card xl">
        <span className="pill">
          <Sparkles size={16} />
          Black Box
        </span>

        <h2>Une interface premium connectée au système Mikami.</h2>

        <p>
          Le site reprend la logique du bot Discord : recherche privée, panel
          simple, résultats propres et connexion au backend existant.
        </p>

        <div className="hero-actions">
          <NavLink to="/search" className="primary-link">
            Ouvrir le search <ArrowRight size={18} />
          </NavLink>

          <a
            href={DISCORD_URL}
            target="_blank"
            rel="noreferrer"
            className="secondary-link"
          >
            Rejoindre Discord
          </a>
        </div>
      </div>

      <div className="stats-grid">
        <Stat icon={Zap} label="API" value="Connected" />
        <Stat icon={Users} label="Interface" value="Private" />
        <Stat icon={Activity} label="Déploiement" value="Railway" />
      </div>

      <div className="section-head">
        <h3>Modules principaux</h3>
        <p>Une base claire pour le site, le bot et les accès.</p>
      </div>

      <ServiceGrid />
    </section>
  );
}

function Dashboard() {
  const [history] = useState(() => loadSearchHistory());

  return (
    <section className="page-grid">
      <div className="dashboard-grid">
        <Stat icon={Search} label="Search" value="Online" />
        <Stat icon={Bot} label="Bot Discord" value="Online" />
        <Stat icon={Crown} label="Premium" value="Discord" />
        <Stat icon={ShieldCheck} label="Sécurité" value="Active" />
      </div>

      <div className="card">
        <h2>Vue générale</h2>
        <p>
          Le dashboard centralise l’état du projet, les accès disponibles, les
          dernières recherches locales et les informations utiles pour les
          membres.
        </p>

        <div className="timeline">
          <TimelineItem
            title="Site public"
            text="Interface Black Box déployée et accessible en ligne."
          />
          <TimelineItem
            title="API connectée"
            text="Le site communique avec le backend Mikami existant."
          />
          <TimelineItem
            title="Accès premium"
            text="Les accès soutien, premium et installation serveur se gèrent via Discord."
          />
        </div>
      </div>

      <div className="card">
        <h2>Dernières recherches locales</h2>
        <p>
          Historique enregistré uniquement dans ton navigateur, pratique pour
          retrouver rapidement les derniers modes utilisés.
        </p>

        {history.length === 0 ? (
          <div className="backend-result-card">
            <h3>Aucune recherche locale</h3>
            <p>Les dernières recherches apparaîtront ici après utilisation.</p>
          </div>
        ) : (
          <div className="status-list">
            {history.map((item, index) => (
              <div className="status-row" key={`${item.date}-${index}`}>
                <span>
                  {item.service} · {item.total} résultat(s)
                </span>
                <b>{item.date}</b>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="cards-3">
        <Feature
          title="Limites"
          text="Les limites et accès étendus sont gérés côté Discord."
        />
        <Feature
          title="Donateurs"
          text="Les rôles soutien/premium peuvent donner des avantages supplémentaires."
        />
        <Feature
          title="Accès bot/site"
          text="Le site et le bot utilisent la même logique de recherche."
        />
      </div>
    </section>
  );
}

function Services() {
  return (
    <section className="page-grid">
      <div className="section-head">
        <h2>Catalogue de services</h2>
        <p>Les services réellement utiles au projet Black Box.</p>
      </div>

      <div className="service-grid">
        <ServiceAction
          icon={UserRound}
          tag="Identity"
          title="Recherche Identité"
          text="Recherche ciblée par prénom et nom, avec ville optionnelle."
        />
        <ServiceAction
          icon={Search}
          tag="Multi"
          title="MultiSearch"
          text="Croisement de plusieurs informations : nom, prénom, ville, email ou username."
        />
        <ServiceAction
          icon={Activity}
          tag="Flex"
          title="Recherche Flexible"
          text="Mode approximatif quand les informations sont incomplètes ou incertaines."
        />
        <ServiceAction
          icon={Phone}
          tag="Phone"
          title="Recherche Téléphone"
          text="Recherche ciblée par numéro exact."
        />
      </div>
    </section>
  );
}

function ServiceAction({ icon: Icon, tag, title, text }) {
  return (
    <div className="service-card">
      <div className="service-icon">
        <Icon size={22} />
      </div>

      <span>{tag}</span>
      <h3>{title}</h3>
      <p>{text}</p>

      <NavLink to="/search" className="secondary-link">
        Utiliser
      </NavLink>
    </div>
  );
}

function SearchPage() {
  const searchServices = [
    {
      id: "identity",
      title: "Recherche Identité",
      badge: "Identity",
      desc: "Recherche ciblée par nom + prénom.",
      icon: UserRound,
      color: "blue",
      fields: [
        {
          name: "prenom",
          label: "Prénom",
          placeholder: "Ex: Julie",
          type: "text",
          optional: false,
        },
        {
          name: "nom_famille",
          label: "Nom",
          placeholder: "Ex: Barret",
          type: "text",
          optional: false,
        },
        {
          name: "ville",
          label: "Ville",
          placeholder: "Optionnel",
          type: "text",
          optional: true,
        },
      ],
    },
    {
      id: "multisearch",
      title: "MultiSearch",
      badge: "Multi",
      desc: "Recherche avancée avec plusieurs champs.",
      icon: Search,
      color: "red",
      fields: [
        {
          name: "prenom",
          label: "Prénom",
          placeholder: "Optionnel",
          type: "text",
          optional: true,
        },
        {
          name: "nom_famille",
          label: "Nom",
          placeholder: "Optionnel",
          type: "text",
          optional: true,
        },
        {
          name: "ville",
          label: "Ville",
          placeholder: "Optionnel",
          type: "text",
          optional: true,
        },
        {
          name: "email",
          label: "Email",
          placeholder: "Optionnel",
          type: "email",
          optional: true,
        },
        {
          name: "nom_utilisateur",
          label: "Username",
          placeholder: "Optionnel",
          type: "text",
          optional: true,
        },
      ],
    },
    {
      id: "flexible",
      title: "Recherche Flexible",
      badge: "Flex",
      desc: "Recherche approximative quand les infos sont incomplètes.",
      icon: Activity,
      color: "yellow",
      fields: [
        {
          name: "prenom",
          label: "Prénom",
          placeholder: "Optionnel",
          type: "text",
          optional: true,
        },
        {
          name: "nom_famille",
          label: "Nom",
          placeholder: "Optionnel",
          type: "text",
          optional: true,
        },
        {
          name: "ville",
          label: "Ville",
          placeholder: "Optionnel",
          type: "text",
          optional: true,
        },
        {
          name: "email",
          label: "Email",
          placeholder: "Optionnel",
          type: "email",
          optional: true,
        },
        {
          name: "nom_utilisateur",
          label: "Username",
          placeholder: "Optionnel",
          type: "text",
          optional: true,
        },
      ],
    },
    {
      id: "phone",
      title: "Recherche Téléphone",
      badge: "Phone",
      desc: "Recherche ciblée par numéro exact.",
      icon: Phone,
      color: "green",
      fields: [
        {
          name: "telephone",
          label: "Téléphone",
          placeholder: "Ex: 0612345678",
          type: "tel",
          optional: false,
        },
      ],
    },
  ];

  const [activeService, setActiveService] = useState(null);
  const [formData, setFormData] = useState({});
  const [accepted, setAccepted] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [searchMeta, setSearchMeta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const openModal = (service) => {
    const data = {};

    service.fields.forEach((field) => {
      data[field.name] = "";
    });

    setFormData(data);
    setAccepted(false);
    setError("");
    setActiveService(service);
  };

  const closeModal = () => {
    setActiveService(null);
    setFormData({});
    setAccepted(false);
  };

  const updateField = (name, value) => {
    setFormData((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const submitSearch = async (event) => {
    event.preventDefault();

    if (!activeService) return;

    if (!accepted) {
      setError("Confirme d'abord que la recherche est autorisée.");
      return;
    }

    setLoading(true);
    setError("");
    setSearchResults([]);
    setSearchMeta(null);

    try {
      const response = await fetch(`${API_URL}/api/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          service: activeService.id,
          data: formData,
        }),
      });

      const payload = await response.json();

      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Erreur pendant la recherche.");
      }

      const meta = {
        service: payload.service,
        searchedAt: payload.searchedAt,
        total: payload.total || 0,
      };

      setSearchResults(payload.results || []);
      setSearchMeta(meta);

      saveSearchHistory({
        service: payload.service,
        total: payload.total || 0,
        date: new Date().toLocaleString("fr-FR"),
      });

      closeModal();
    } catch (err) {
      setError(err.message || "Impossible de contacter le backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-grid">
      <div className="card xl">
        <span className="pill">
          <Search size={16} />
          Black Box Search
        </span>

        <h2>Choisis un mode de recherche</h2>

        <p>
          Même logique que le bot Discord : identité, multisearch, flexible et
          téléphone. Les résultats restent affichés uniquement dans ta session.
        </p>
      </div>

      <div className="search-services-grid">
        {searchServices.map((service) => {
          const Icon = service.icon;

          return (
            <button
              type="button"
              className={`search-service-card ${service.color || ""}`}
              key={service.id}
              onClick={() => openModal(service)}
            >
              <div className="service-icon">
                <Icon size={22} />
              </div>

              <span>{service.badge}</span>
              <h3>{service.title}</h3>
              <p>{service.desc}</p>
              <b>Ouvrir le formulaire</b>
            </button>
          );
        })}
      </div>

      {error && <div className="error-box">{error}</div>}

      {searchMeta && (
        <div className="backend-results">
          <div className="section-head">
            <h2>Résultats</h2>
            <p>
              Service : {searchMeta.service} · Total : {searchMeta.total} ·{" "}
              {searchMeta.searchedAt}
            </p>
          </div>

          {searchResults.length === 0 ? (
            <div className="backend-result-card">
              <div className="result-top">
                <span>Search</span>
                <b>0</b>
              </div>

              <h3>Aucun résultat trouvé</h3>
              <p>Aucune donnée ne correspond à cette recherche.</p>
            </div>
          ) : (
            <div className="results-grid">
              {searchResults.map((result, index) => (
                <ResultCard result={result} index={index} key={index} />
              ))}
            </div>
          )}
        </div>
      )}

      {activeService && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeModal();
          }}
        >
          <div className="modal-card">
            <div className="modal-head">
              <div>
                <span className="pill">{activeService.badge}</span>
                <h2>{activeService.title}</h2>
                <p>{activeService.desc}</p>
              </div>

              <button type="button" className="modal-close" onClick={closeModal}>
                ×
              </button>
            </div>

            <form className="modal-form" onSubmit={submitSearch}>
              {activeService.fields.map((field) => (
                <label key={field.name}>
                  <span>
                    {field.label}
                    {field.optional && <small> optionnel</small>}
                  </span>

                  <input
                    type={field.type}
                    value={formData[field.name] || ""}
                    placeholder={field.placeholder || ""}
                    required={!field.optional}
                    onChange={(event) =>
                      updateField(field.name, event.target.value)
                    }
                  />
                </label>
              ))}

              <label className="check-line">
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(event) => setAccepted(event.target.checked)}
                />

                <span>
                  Je confirme que cette recherche est autorisée et respecte les
                  règles de Black Box.
                </span>
              </label>

              <div className="modal-actions">
                <button type="button" className="ghost-btn" onClick={closeModal}>
                  Annuler
                </button>

                <button type="submit" className="primary-btn" disabled={loading}>
                  {loading ? "Recherche..." : "Lancer la recherche"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}

function ResultCard({ result, index }) {
  const formatKey = (key) => {
    const labels = {
      prenom: "Prénom",
      nom_famille: "Nom",
      nom: "Nom",
      email: "Email",
      telephone: "Téléphone",
      mobile: "Mobile",
      tel: "Téléphone",
      phone: "Téléphone",
      adresse_complete: "Adresse complète",
      adresse: "Adresse",
      address: "Adresse",
      ville: "Ville",
      code_postal: "Code postal",
      pays: "Pays",
      date_naissance: "Date de naissance",
      nom_utilisateur: "Username",
      username: "Username",
      _confidence: "Confiance",
      _sources: "Sources",
    };

    return labels[key] || key.replaceAll("_", " ");
  };

  const formatValue = (value) => {
    if (value === null || value === undefined || value === "") {
      return "";
    }

    if (Array.isArray(value)) {
      return value.join(", ");
    }

    if (typeof value === "object") {
      return JSON.stringify(value, null, 2);
    }

    return String(value);
  };

  const fields = Object.entries(result || {})
    .filter(([, value]) => {
      if (value === undefined || value === null || value === "") return false;
      if (value === "N/A") return false;
      return true;
    })
    .map(([key, value]) => [formatKey(key), formatValue(value)]);

  const title =
    `${result?.prenom || ""} ${result?.nom_famille || result?.nom || ""}`.trim() ||
    result?.email ||
    result?.telephone ||
    result?.mobile ||
    result?.tel ||
    result?.phone ||
    result?.nom_utilisateur ||
    `Résultat ${index + 1}`;

  return (
    <div className="backend-result-card">
      <div className="result-top">
        <span>Résultat {index + 1}</span>
        <b>{result?._confidence ?? "N/A"}</b>
      </div>

      <h3>{title}</h3>

      <div className="result-fields">
        {fields.map(([label, value], fieldIndex) => (
          <p key={`${label}-${fieldIndex}`}>
            <b>{label} :</b>{" "}
            <span style={{ whiteSpace: "pre-wrap" }}>{value}</span>
          </p>
        ))}
      </div>
    </div>
  );
}

function BotPage() {
  return (
    <section className="page-grid">
      <div className="card xl">
        <span className="pill">
          <Bot size={16} />
          Discord
        </span>

        <h2>Bot Discord Black Box</h2>

        <p>
          Le bot Discord utilise la même API que ce site : panel privé, modals,
          pagination, logs et résultats éphémères.
        </p>

        <div className="hero-actions">
          <a
            href={DISCORD_URL}
            target="_blank"
            rel="noreferrer"
            className="primary-link"
          >
            Rejoindre le serveur <ExternalLink size={18} />
          </a>

          <NavLink to="/pricing" className="secondary-link">
            Voir les offres
          </NavLink>
        </div>
      </div>

      <div className="cards-3">
        <Feature
          title="Installation serveur client"
          text={`Le bot peut être installé sur un autre serveur. Contact : ${DISCORD_USERNAME}.`}
        />
        <Feature
          title="Résultats privés"
          text="Chaque recherche reste visible uniquement par l’utilisateur."
        />
        <Feature
          title="Accès premium"
          text="Des options avancées peuvent être proposées selon l’offre choisie."
        />
      </div>
    </section>
  );
}

function Pricing() {
  return (
    <section className="pricing-grid">
      <PriceCard
        name="Gratuit"
        price="0€"
        features={[
          "Accès au serveur Discord",
          "Utilisation de base",
          "Support communautaire",
        ]}
        action="Rejoindre Discord"
        link={DISCORD_URL}
      />

      <PriceCard
        highlight
        name="Soutien"
        price="1€+"
        features={[
          "Rôle soutien",
          "Priorité communautaire",
          "Avantages selon disponibilité",
        ]}
        action={`Contacter ${DISCORD_USERNAME}`}
        link={DISCORD_URL}
      />

      <PriceCard
        name="Installation bot serveur"
        price="Sur demande"
        features={[
          "Bot installé sur votre serveur",
          "Panel dédié",
          "Logs privés",
          "Configuration salons",
        ]}
        action={`Contacter ${DISCORD_USERNAME}`}
        link={DISCORD_URL}
      />

      <PriceCard
        highlight
        name="Premium Gold"
        price="Sur demande"
        features={[
          "La crème de la crème",
          "Accès premium avancé",
          "Priorité maximale",
          "Options personnalisées",
        ]}
        action={`Contacter ${DISCORD_USERNAME}`}
        link={DISCORD_URL}
      />
    </section>
  );
}

function Status() {
  const [status, setStatus] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);

  const checkStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/health`);
      const data = await response.json();
      setStatus(data);
      setUpdatedAt(new Date().toLocaleString("fr-FR"));
    } catch {
      setStatus({
        ok: false,
        local: "offline",
        mikami: "unknown",
      });
      setUpdatedAt(new Date().toLocaleString("fr-FR"));
    }
  };

  return (
    <section className="page-grid">
      <div className="card xl">
        <h2>Statut des services</h2>

        <p>
          Vérifie rapidement si le site, le backend local et l’API Mikami
          répondent.
        </p>

        <button className="primary-btn" onClick={checkStatus}>
          Vérifier le statut
        </button>
      </div>

      <div className="status-list">
        <StatusRow service="Site web" status="Online" />
        <StatusRow service="Backend local" status={status?.local || "À vérifier"} />
        <StatusRow service="API Mikami" status={status?.mikami || "À vérifier"} />
        <StatusRow service="Bot Discord" status="Online" />
        <StatusRow service="Dernière vérification" status={updatedAt || "Jamais"} />
      </div>
    </section>
  );
}

function Support() {
  return (
    <section className="page-grid">
      <div className="card xl">
        <h2>Support</h2>

        <p>
          Pour une question, un problème ou une demande d’accès, utilise le salon
          help du serveur Discord ou contacte l’email support.
        </p>

        <div className="hero-actions">
          <a
            href={DISCORD_URL}
            target="_blank"
            rel="noreferrer"
            className="primary-link"
          >
            Aller sur le Discord <ExternalLink size={18} />
          </a>

          <a href={`mailto:${SUPPORT_EMAIL}`} className="secondary-link">
            Envoyer un email
          </a>
        </div>
      </div>

      <div className="cards-3">
        <Feature
          title="Salon help"
          text="Le support principal passe par le salon help du serveur Discord."
        />
        <Feature
          title="Email"
          text={SUPPORT_EMAIL}
        />
        <Feature
          title="Contact premium"
          text={`Pour les offres payantes ou PayPal : contactez ${DISCORD_USERNAME} en MP Discord.`}
        />
      </div>
    </section>
  );
}

function Legal() {
  return (
    <section className="page-grid">
      <div className="card xl">
        <h2>Légal</h2>
        <p>
          Cette page sera complétée plus tard avec les règles d’utilisation, la
          confidentialité et les conditions du service.
        </p>
      </div>
    </section>
  );
}

function ServiceGrid() {
  return (
    <div className="service-grid">
      {services.map((service) => {
        const Icon = service.icon;

        return (
          <div className="service-card" key={service.title}>
            <div className="service-icon">
              <Icon size={22} />
            </div>

            <span>{service.tag}</span>
            <h3>{service.title}</h3>
            <p>{service.desc}</p>
          </div>
        );
      })}
    </div>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="stat-card">
      <Icon size={22} />

      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

function TimelineItem({ title, text }) {
  return (
    <div className="timeline-item">
      <CheckCircle2 size={18} />

      <div>
        <strong>{title}</strong>
        <span>{text}</span>
      </div>
    </div>
  );
}

function Feature({ title, text }) {
  return (
    <div className="feature-card">
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}

function PriceCard({ name, price, features, highlight, action, link }) {
  return (
    <div className={highlight ? "price-card highlight" : "price-card"}>
      <span>{name}</span>
      <h2>{price}</h2>

      <ul>
        {features.map((feature) => (
          <li key={feature}>
            <CheckCircle2 size={17} />
            {feature}
          </li>
        ))}
      </ul>

      {link ? (
        <a href={link} target="_blank" rel="noreferrer">
          <button>{action || "Voir"}</button>
        </a>
      ) : (
        <button>{action || "Voir"}</button>
      )}
    </div>
  );
}

function StatusRow({ service, status }) {
  return (
    <div className="status-row">
      <span>{service}</span>
      <b>{status}</b>
    </div>
  );
}

function loadSearchHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const parsed = JSON.parse(raw || "[]");

    if (!Array.isArray(parsed)) return [];

    return parsed.slice(0, 8);
  } catch {
    return [];
  }
}

function saveSearchHistory(entry) {
  try {
    const current = loadSearchHistory();

    const next = [
      entry,
      ...current,
    ].slice(0, 8);

    localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  } catch {
    // localStorage indisponible, aucun problème.
  }
}

export default App;