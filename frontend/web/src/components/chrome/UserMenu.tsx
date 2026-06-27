import { useNavigate } from "react-router-dom";

import { ChevronDown } from "@/components/overview/icons";
import { Menu, MenuItem } from "@/components/ui/Menu";
import { glass } from "@/components/chrome/theme";
import { getStoredUser, logout } from "@/lib/auth";

const ROLE_LABELS: Record<string, string> = {
  ADMIN_CA: "Admin / CA",
  ADMIN_INTEGRATION: "Admin intégrations",
  DG_GROUP: "Directeur Général",
  CODIR: "Membre du CODIR",
  DAF: "DAF",
  DRH: "DRH",
  DIR_OPS: "Dir. Opérations",
  RESP_METIER: "Responsable métier",
  READER: "Lecteur",
};

export function UserMenu() {
  const navigate = useNavigate();
  const user = getStoredUser();
  const name = user?.full_name || user?.username || "Utilisateur";
  const roleLabel = user?.is_superuser ? "Super Admin" : ROLE_LABELS[user?.role ?? ""] ?? user?.role ?? "—";
  const initials = name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase() || "U";
  const scopeLabel = user ? (user.scope === "GROUP" ? "Groupe — toutes filiales" : (user.scope as string[]).join(", ") || "Aucune filiale") : "";

  const doLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <Menu
      align="right"
      width={250}
      trigger={({ open, toggle }) => (
        <button
          type="button"
          onClick={toggle}
          aria-haspopup="menu"
          aria-expanded={open}
          className="flex h-12 items-center gap-2.5 rounded-full pl-1.5 pr-3 text-[#222]"
          style={glass}
        >
          <span className="grid h-9 w-9 place-items-center rounded-full bg-[#16191A] text-[12px] font-bold text-white">{initials}</span>
          <span className="hidden text-left sm:block">
            <span className="block text-[12.5px] font-bold leading-none text-[#16191A]">{name}</span>
            <span className="block text-[10.5px] font-semibold text-[#8A9291]">{roleLabel}</span>
          </span>
          <ChevronDown width={14} height={14} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" }} />
        </button>
      )}
    >
      {(close) => (
        <div className="p-1">
          <div className="px-3 py-2">
            <div className="text-[13px] font-bold text-[#16191A]">{name}</div>
            <div className="text-[11px] font-semibold text-[#8A9291]">{roleLabel}</div>
            <div className="mt-1 text-[10.5px] font-medium text-[#A0A6A3]">{scopeLabel}</div>
          </div>
          <div className="my-1 h-px bg-black/8" />
          <MenuItem onClick={() => { close(); navigate(user?.landing || "/"); }}>
            <span className="font-semibold text-[#2C3132]">Mon cockpit</span>
          </MenuItem>
          <MenuItem onClick={() => { close(); doLogout(); }}>
            <span className="font-semibold text-[#C0203F]">Se déconnecter</span>
          </MenuItem>
        </div>
      )}
    </Menu>
  );
}
