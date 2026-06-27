import { Bell, Briefcase, Network } from "@/components/overview/icons";

import { Avatar } from "./Avatar";
import { CircleButton } from "./CircleButton";
import { RoleSwitcher } from "./RoleSwitcher";

/** Actions de l'en-tête : rôle (permissions), portefeuille, notifications, profil. */
export function HeaderActions() {
  return (
    <div className="flex items-center gap-3">
      <RoleSwitcher />
      <CircleButton label="Connecteurs & Intégrations" to="/admin/integrations">
        <Network width={21} height={21} />
      </CircleButton>
      <CircleButton label="Portefeuille" to="/modules/portefeuille">
        <Briefcase width={21} height={21} />
      </CircleButton>
      <CircleButton label="Notifications" to="/modules/notifications" alert>
        <Bell width={21} height={21} />
      </CircleButton>
      <Avatar />
    </div>
  );
}
