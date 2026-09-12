/** Connexion K-Insight.
 *
 *  CE QUE CETTE PAGE NE PROPOSE PAS, ET POURQUOI. Ni « mot de passe oublié », ni
 *  MFA, ni SSO : le backend n'expose que `POST /auth/token/` et `GET /auth/me/`.
 *  Afficher ces liens créerait exactement ce que le projet a passé deux missions à
 *  retirer ailleurs — un contrôle qui ne fait rien. À la place, la carte dit à qui
 *  s'adresser, ce qui est vrai et utile.
 *
 *  CE QU'ELLE DIT EN REVANCHE : pourquoi l'utilisateur est ici (session expirée
 *  plutôt qu'arrivée volontaire), s'il est hors ligne avant même d'essayer, et
 *  laquelle des trois étapes a échoué — refus d'identifiants, serveur injoignable,
 *  ou profil illisible. Ces trois cas appellent des gestes différents et ne
 *  peuvent pas partager le même message.
 */
import * as React from "react";
import { motion, useReducedMotion } from "framer-motion";
import { useNavigate, useSearchParams } from "react-router-dom";

import { LoginBackdrop } from "@/components/chrome/LoginBackdrop";
import { BLACK, ORANGE, glass } from "@/components/chrome/theme";
import { EASE_OUT } from "@/lib/motion";
import { LoginError, isAuthenticated, login } from "@/lib/auth";
import { useOnlineStatus } from "@/pwa/useNetwork";

/** Mémorise l'IDENTIFIANT seulement — jamais le mot de passe, jamais un jeton. */
const CLE_IDENTIFIANT = "k-insight-dernier-identifiant";

const ATTERRISSAGE_PAR_DEFAUT = "/dashboard/overview-groupe";

/** Une destination interne, ou rien.
 *
 *  `next` vient de l'URL, donc de n'importe qui. Vérifié dans le navigateur :
 *  l'API History REFUSE un `pushState` hors origine — « //evil.com » lève une
 *  `SecurityError` au lieu de sortir du domaine. Il n'y a donc pas de redirection
 *  ouverte ici, mais l'exception ferait échouer une connexion pourtant réussie,
 *  juste après l'envoi du mot de passe. On n'accepte qu'un chemin absolu à UNE
 *  seule barre oblique.
 */
function destinationSure(brut: string | null): string | null {
  if (!brut) return null;
  if (!brut.startsWith("/") || brut.startsWith("//") || brut.startsWith("/\\")) return null;
  return brut;
}

/** Le message qui correspond à la cause réelle, et le geste qui va avec. */
function messageDErreur(err: unknown): { titre: string; detail: string } {
  if (err instanceof LoginError) {
    if (err.etape === "reseau") {
      return {
        titre: "Serveur injoignable",
        detail: "Vos identifiants n'ont pas été refusés : la requête n'est pas arrivée. Vérifiez votre connexion, puis réessayez.",
      };
    }
    if (err.etape === "profil") {
      return {
        titre: "Profil illisible",
        detail: "Vos identifiants ont été acceptés, mais votre rôle et vos droits n'ont pas pu être chargés. La session a été annulée plutôt que de vous ouvrir un cockpit sans permissions.",
      };
    }
    switch (err.statut) {
      case 400:
        return { titre: "Demande incomplète", detail: "Identifiant et mot de passe sont tous deux requis." };
      case 401:
        return { titre: "Identifiant ou mot de passe incorrect", detail: "Vérifiez la saisie. Les majuscules comptent." };
      case 403:
        return { titre: "Compte désactivé", detail: "Ce compte existe mais n'est plus autorisé à se connecter. Contactez un administrateur." };
      case 429:
        return { titre: "Trop de tentatives", detail: "Patientez une minute avant de réessayer." };
      default:
        return {
          titre: `Le serveur a répondu ${err.statut}`,
          detail: "L'erreur vient du service d'authentification, pas de votre saisie.",
        };
    }
  }
  return { titre: "Connexion impossible", detail: "Cause inconnue. Réessayez ; si cela persiste, prévenez un administrateur." };
}

export function LoginPage() {
  const [username, setUsername] = React.useState(
    () => (typeof window === "undefined" ? "" : window.localStorage.getItem(CLE_IDENTIFIANT) ?? ""),
  );
  const [password, setPassword] = React.useState("");
  const [memoriser, setMemoriser] = React.useState(
    () => typeof window !== "undefined" && Boolean(window.localStorage.getItem(CLE_IDENTIFIANT)),
  );
  const [motDePasseVisible, setMotDePasseVisible] = React.useState(false);
  const [verrMaj, setVerrMaj] = React.useState(false);
  const [erreur, setErreur] = React.useState<{ titre: string; detail: string } | null>(null);
  const [enCours, setEnCours] = React.useState(false);

  const navigate = useNavigate();
  const [params] = useSearchParams();
  const destination = destinationSure(params.get("next"));
  // `on401` renvoie ici AVEC un `next` : la présence du paramètre distingue donc
  // une session expirée d'une arrivée volontaire sur /login. Sans cette phrase,
  // l'utilisateur éjecté en pleine consultation croit à une panne.
  const sessionExpiree = params.has("next");
  const enLigne = useOnlineStatus();

  const champMotDePasse = React.useRef<HTMLInputElement>(null);
  const zoneErreur = React.useRef<HTMLDivElement>(null);
  // `enCours` est un ÉTAT : il ne devient vrai qu'au re-rendu suivant. Deux
  // pressions rapprochées sur Entrée passaient donc au travers du `disabled` et
  // envoyaient deux requêtes — et le backend n'a aucun amortisseur de débit.
  // Cette référence, elle, est vraie immédiatement.
  const envoiEnVol = React.useRef(false);
  const animationsReduites = useReducedMotion();

  // Déjà connecté → on saute le login. La redirection vit dans un effet, donc
  // APRÈS la première peinture : sans ce garde, l'utilisateur déjà authentifié
  // voyait le formulaire clignoter une image avant d'être redirigé, ce qui se lit
  // comme une déconnexion.
  const dejaConnecte = isAuthenticated();
  React.useEffect(() => {
    if (dejaConnecte) navigate(destination ?? ATTERRISSAGE_PAR_DEFAUT, { replace: true });
  }, [navigate, destination, dejaConnecte]);

  // L'identifiant revient prérempli : le curseur va donc au mot de passe, là où
  // le travail reste à faire.
  React.useEffect(() => {
    if (username) champMotDePasse.current?.focus();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const surTouche = (e: React.KeyboardEvent<HTMLInputElement>) => {
    // `getModifierState` dit l'état réel de la touche, y compris quand elle était
    // déjà enclenchée avant l'arrivée sur la page.
    setVerrMaj(e.getModifierState?.("CapsLock") ?? false);
  };

  const soumettre = async (e: React.FormEvent) => {
    e.preventDefault();
    if (envoiEnVol.current || !username.trim() || !password) return;
    envoiEnVol.current = true;
    setEnCours(true);
    setErreur(null);
    try {
      const identifiant = username.trim();
      const me = await login(identifiant, password);
      if (memoriser) window.localStorage.setItem(CLE_IDENTIFIANT, identifiant);
      else window.localStorage.removeItem(CLE_IDENTIFIANT);
      navigate(destination ?? me.landing ?? ATTERRISSAGE_PAR_DEFAUT, { replace: true });
    } catch (err) {
      setErreur(messageDErreur(err));
      // Le mot de passe est vidé, jamais l'identifiant : retaper les deux après
      // une faute de frappe est une punition inutile.
      setPassword("");
      champMotDePasse.current?.focus();
      // L'annonce vocale suit le déplacement du focus, sinon elle passe inaperçue.
      window.setTimeout(() => zoneErreur.current?.focus(), 60);
    } finally {
      envoiEnVol.current = false;
      setEnCours(false);
    }
  };

  if (dejaConnecte) return null;

  const champ =
    "h-12 w-full rounded-2xl border border-white/70 bg-white/80 px-4 text-[14px] font-semibold text-[#1A1F1F] outline-none transition-colors focus:border-[#416FF4] placeholder:text-[#6E7573]";

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden p-4">
      <LoginBackdrop />

      <motion.div
        className="relative z-10 w-full max-w-[440px] rounded-[32px] p-8 sm:p-10"
        style={{ ...glass, background: "linear-gradient(160deg,rgba(255,255,255,0.94),rgba(240,245,246,0.88))" }}
        initial={animationsReduites ? false : { opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={animationsReduites ? { duration: 0 } : { duration: 0.5, ease: EASE_OUT }}
      >
        <div className="flex items-center gap-2.5">
          <span className="grid h-10 w-10 place-items-center rounded-2xl text-white" style={{ background: BLACK }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={ORANGE} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M3 13h4l3 7 4-16 3 9h4" />
            </svg>
          </span>
          <div>
            <div className="text-[19px] font-extrabold leading-none tracking-tight text-[#16191A]">K-Insight</div>
            <div className="mt-0.5 text-[11px] font-semibold text-[#8A9291]">Gouvernance &amp; Intelligence — Groupe Kaydan</div>
          </div>
        </div>

        <h1 className="mt-8 text-[24px] font-semibold text-[#151818]">Connexion</h1>
        <p className="mt-1 text-[13px] font-medium text-[#5F6664]">Accédez à votre cockpit selon votre rôle.</p>

        {/* Deux avis qui précèdent toute tentative : ils expliquent une situation,
            ils ne signalent pas une erreur de l'utilisateur. */}
        {sessionExpiree ? (
          <p className="mt-4 rounded-xl bg-[rgba(224,128,30,0.10)] px-4 py-2.5 text-[12.5px] font-semibold text-[#8A5B12]">
            Votre session a expiré. Reconnectez-vous : vous reviendrez à la page que vous consultiez.
          </p>
        ) : null}
        {!enLigne ? (
          <p className="mt-3 rounded-xl bg-[rgba(92,99,112,0.10)] px-4 py-2.5 text-[12.5px] font-semibold text-[#4A5260]">
            Vous êtes hors ligne. La connexion exige le réseau — elle échouera tant qu'il n'est pas revenu.
          </p>
        ) : null}

        <form className="mt-6 grid gap-3.5" onSubmit={soumettre} noValidate>
          <div className="grid gap-1.5">
            <label htmlFor="identifiant" className="text-[12px] font-bold text-[#586061]">Identifiant</label>
            <input
              id="identifiant"
              name="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              autoFocus={!username}
              aria-invalid={Boolean(erreur)}
              className={champ}
              placeholder="nom.utilisateur"
            />
          </div>

          <div className="grid gap-1.5">
            <label htmlFor="motdepasse" className="text-[12px] font-bold text-[#586061]">Mot de passe</label>
            <div className="relative">
              <input
                id="motdepasse"
                name="password"
                ref={champMotDePasse}
                type={motDePasseVisible ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyUp={surTouche}
                onKeyDown={surTouche}
                onBlur={() => setVerrMaj(false)}
                autoComplete="current-password"
                aria-invalid={Boolean(erreur)}
                aria-describedby={verrMaj ? "verr-maj" : undefined}
                className={`${champ} pr-12`}
                placeholder="••••••••"
              />
              {/* `tabIndex={-1}` : la bascule ne doit pas s'intercaler entre le mot
                  de passe et le bouton de connexion dans l'ordre de tabulation. */}
              <button
                type="button"
                tabIndex={-1}
                onClick={() => setMotDePasseVisible((v) => !v)}
                aria-label={motDePasseVisible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                aria-pressed={motDePasseVisible}
                className="absolute right-1.5 top-1.5 grid h-9 w-9 place-items-center rounded-xl text-[#8A9291] transition-colors hover:bg-black/5 hover:text-[#3A3E3E]"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12Z" />
                  <circle cx="12" cy="12" r="2.6" />
                  {motDePasseVisible ? <path d="M4 20 20 4" /> : null}
                </svg>
              </button>
            </div>
            {verrMaj ? (
              <p id="verr-maj" className="text-[11.5px] font-semibold text-[#8A5B12]">
                Verrouillage majuscules actif.
              </p>
            ) : null}
          </div>

          <label className="flex cursor-pointer items-start gap-2.5 text-[12.5px] font-semibold text-[#586061]">
            <input
              type="checkbox"
              checked={memoriser}
              onChange={(e) => setMemoriser(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-[#C9CFCD] accent-[#416FF4]"
            />
            <span className="min-w-0">
              Mémoriser mon identifiant
              {/* Sur sa propre ligne : la précision est le cœur du sujet, pas une
                  parenthèse. « Se souvenir de moi » laisse croire que la session
                  reste ouverte, ce qui serait faux et dangereux sur un poste
                  partagé — seul l'identifiant est conservé. */}
              <span className="mt-0.5 block font-medium leading-snug text-[#6E7573]">
                Le mot de passe n'est jamais conservé, et la session n'est pas prolongée.
              </span>
            </span>
          </label>

          {erreur ? (
            <div
              ref={zoneErreur}
              tabIndex={-1}
              role="alert"
              aria-live="assertive"
              className="rounded-xl bg-[rgba(217,43,85,0.08)] px-4 py-3 outline-none"
            >
              <p className="text-[12.5px] font-bold text-[#C0203F]">{erreur.titre}</p>
              <p className="mt-0.5 text-[12px] font-medium leading-relaxed text-[#96394F]">{erreur.detail}</p>
            </div>
          ) : null}

          <button
            type="submit"
            disabled={enCours || !username.trim() || !password}
            aria-busy={enCours}
            className="mt-1 flex h-12 items-center justify-center gap-2 rounded-2xl text-[14px] font-bold text-white shadow-[0_16px_32px_rgba(0,0,0,0.16)] outline-none transition-transform hover:-translate-y-0.5 focus-visible:ring-2 focus-visible:ring-[#416FF4] focus-visible:ring-offset-2 disabled:translate-y-0 disabled:opacity-50"
            style={{ background: BLACK }}
          >
            {enCours ? (
              <>
                <span className="ki-sync-dot h-1.5 w-1.5 rounded-full bg-white" aria-hidden />
                Connexion…
              </>
            ) : (
              "Se connecter"
            )}
          </button>
        </form>

        <p className="mt-6 text-[11px] font-medium leading-relaxed text-[#6E7573]">
          Accès gouverné : vous ne voyez que les domaines autorisés par votre rôle. Toute action
          sensible reste soumise à validation.{" "}
          {/* Pas de lien « mot de passe oublié » : aucune réinitialisation n'existe
              côté serveur. On dit le vrai recours plutôt qu'un lien mort. */}
          <span className="text-[#8A9291]">
            Mot de passe perdu ou compte bloqué : contactez l'administrateur K-Insight de votre entité.
          </span>
        </p>

        <div className="mt-5 flex items-center justify-center border-t border-[#E2E6E2]/80 pt-4">
          <img
            src="/assets/logo_kaydanG_B.png"
            alt="Groupe Kaydan"
            width={72}
            height={30}
            className="h-[30px] w-auto opacity-80"
          />
        </div>
      </motion.div>
    </div>
  );
}
