/** Une section du Capital Humain : ses onglets, chacun rendant la page EXISTANTE de
 *  son module (mêmes données, mêmes droits), sans recréer de page.
 *
 *  L'onglet actif vit dans l'adresse (`?onglet=`) : un lien partagé rouvre le même
 *  onglet avec les mêmes filtres. Les exports (Excel, PDF, PowerPoint) reprennent
 *  les filtres courants et le périmètre serveur, comme l'écran.
 */
import * as React from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { downloadHrReport } from "@/api/governance";
import { PageShell, PageShellIntegree } from "@/components/chrome/PageShell";
import { glass } from "@/components/chrome/theme";
import { StructureRh } from "@/components/overview/StructureRh";
import { Users } from "@/components/overview/icons";
import { ongletsVisibles, sectionParCle } from "@/config/sectionsRh";
import { getCurrentPermissions, getCurrentRole } from "@/lib/permissions";
import { libelleFiltrePeriode, parametresFiltres, useFilters } from "@/store/filters";

import { AttendancePage } from "./AttendancePage";
import { ModulePage } from "./ModulePage";

function Exports() {
  const filtres = useFilters();
  const [enCours, setEnCours] = React.useState<string | null>(null);
  const [echec, setEchec] = React.useState<string | null>(null);
  const exporter = async (ext: "xlsx" | "pdf" | "pptx") => {
    setEnCours(ext);
    setEchec(null);
    try {
      await downloadHrReport(ext, parametresFiltres(filtres).toString(), libelleFiltrePeriode(filtres));
    } catch (e) {
      setEchec(e instanceof Error && / 403 /.test(e.message) ? "Export non autorisé pour votre profil." : "Export impossible pour le moment.");
    } finally {
      setEnCours(null);
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      {(["xlsx", "pdf", "pptx"] as const).map((ext) => (
        <button key={ext} type="button" disabled={enCours !== null} onClick={() => exporter(ext)}
                className="rounded-full bg-white px-3 py-1.5 text-[11.5px] font-bold text-[#2C3132] disabled:opacity-50">
          {enCours === ext ? "Export…" : ext === "xlsx" ? "Excel" : ext === "pdf" ? "PDF" : "PowerPoint"}
        </button>
      ))}
      {echec ? <span role="alert" className="text-[11.5px] font-semibold text-[#C43252]">{echec}</span> : null}
    </div>
  );
}

export function SectionRhPage({ sectionKey }: { sectionKey: string }) {
  const section = sectionParCle(sectionKey);
  const [params, setParams] = useSearchParams();
  const onglets = section ? ongletsVisibles(section, getCurrentPermissions(), getCurrentRole()) : [];
  if (!section || !onglets.length) return <Navigate to="/dashboard/capital-humain" replace />;
  const actif = onglets.find((o) => o.cle === params.get("onglet")) ?? onglets[0];

  const choisir = (cle: string) => {
    const suivants = new URLSearchParams(window.location.search);   // garde les filtres
    suivants.set("onglet", cle);
    setParams(suivants, { replace: true });
  };

  return (
    <PageShell title={section.titre} subtitle={section.sousTitre} icon={<Users width={22} height={22} />} accent="#416FF4">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label={section.titre} className="flex flex-wrap gap-1.5 rounded-[20px] p-1.5" style={glass}>
          {onglets.map((o) => (
            <button key={o.cle} type="button" role="tab" aria-selected={o.cle === actif.cle} onClick={() => choisir(o.cle)}
                    className={`rounded-[14px] px-3.5 py-2 text-[12.5px] font-bold transition ${
                      o.cle === actif.cle ? "bg-[#16191A] text-white" : "text-[#3C4142] hover:bg-white/70"}`}>
              {o.libelle}
            </button>
          ))}
        </div>
        <Exports />
      </div>
      <PageShellIntegree.Provider value>
        {actif.composant === "structure" ? <StructureRh />
          : actif.moduleKey === "hr-attendance" ? <AttendancePage />
            : <ModulePage key={actif.moduleKey} moduleKey={actif.moduleKey} />}
      </PageShellIntegree.Provider>
    </PageShell>
  );
}
