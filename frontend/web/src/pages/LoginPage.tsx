import * as React from "react";
import { motion } from "framer-motion";
import { useNavigate, useSearchParams } from "react-router-dom";

import { BLACK, ORANGE, glass } from "@/components/chrome/theme";
import { EASE_OUT } from "@/lib/motion";
import { isAuthenticated, login } from "@/lib/auth";

export function LoginPage() {
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next");

  // Déjà connecté → on saute le login.
  React.useEffect(() => {
    if (isAuthenticated()) navigate(next || "/dashboard/overview-groupe", { replace: true });
  }, [navigate, next]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setLoading(true);
    setError(null);
    try {
      const me = await login(username.trim(), password);
      // Redirection selon le profil/rôle (landing fournie par le backend), ou la page demandée.
      navigate(next || me.landing || "/dashboard/overview-groupe", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connexion impossible.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center bg-[#B8B7B4] p-4">
      <motion.div
        className="w-full max-w-[420px] rounded-[32px] p-8 sm:p-10"
        style={{ ...glass, background: "linear-gradient(160deg,rgba(255,255,255,0.92),rgba(240,245,246,0.86))" }}
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: EASE_OUT }}
      >
        <div className="flex items-center gap-2.5">
          <span className="grid h-10 w-10 place-items-center rounded-2xl text-white" style={{ background: BLACK }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={ORANGE} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 13h4l3 7 4-16 3 9h4" /></svg>
          </span>
          <div>
            <div className="text-[19px] font-extrabold leading-none tracking-tight text-[#16191A]">K-Insight</div>
            <div className="mt-0.5 text-[11px] font-semibold text-[#8A9291]">Gouvernance & Intelligence — Groupe Kaydan</div>
          </div>
        </div>

        <h1 className="mt-8 text-[24px] font-semibold text-[#151818]">Connexion</h1>
        <p className="mt-1 text-[13px] font-medium text-[#777C7D]">Accédez à votre cockpit selon votre rôle.</p>

        <form className="mt-6 grid gap-3" onSubmit={submit}>
          <label className="grid gap-1.5">
            <span className="text-[12px] font-bold text-[#586061]">Identifiant</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              className="h-12 rounded-2xl border border-white/70 bg-white/80 px-4 text-[14px] font-semibold text-[#1A1F1F] outline-none focus:border-[#416FF4] placeholder:text-[#9AA09D]"
              placeholder="nom.utilisateur"
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-[12px] font-bold text-[#586061]">Mot de passe</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="h-12 rounded-2xl border border-white/70 bg-white/80 px-4 text-[14px] font-semibold text-[#1A1F1F] outline-none focus:border-[#416FF4] placeholder:text-[#9AA09D]"
              placeholder="••••••••"
            />
          </label>

          {error ? (
            <div className="rounded-xl bg-[rgba(217,43,85,0.08)] px-4 py-2.5 text-[12.5px] font-semibold text-[#C0203F]">{error}</div>
          ) : null}

          <button
            type="submit"
            disabled={loading || !username.trim() || !password}
            className="mt-2 h-12 rounded-2xl text-[14px] font-bold text-white shadow-[0_16px_32px_rgba(0,0,0,0.16)] transition-transform hover:-translate-y-0.5 disabled:opacity-50"
            style={{ background: BLACK }}
          >
            {loading ? "Connexion…" : "Se connecter"}
          </button>
        </form>

        <p className="mt-6 text-[11px] font-medium leading-relaxed text-[#9AA09D]">
          Accès gouverné : vous ne voyez que les domaines autorisés par votre rôle. Toute action
          sensible reste soumise à validation.
        </p>
      </motion.div>
    </div>
  );
}
