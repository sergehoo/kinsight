import { Bell, Briefcase, Network } from "@/components/overview/icons";

import { CircleButton } from "./CircleButton";
import { UserMenu } from "./UserMenu";

/** Actions de l'en-tête : intégrations, portefeuille, notifications, utilisateur connecté. */
export function HeaderActions() {
  return (
    <div className="flex items-center gap-3">
      <CircleButton label="Connecteurs & Intégrations" to="/admin/integrations">
        <Network width={21} height={21} />
      </CircleButton>
      <CircleButton label="Portefeuille" to="/modules/portefeuille">
        <Briefcase width={21} height={21} />
      </CircleButton>
      <CircleButton label="Notifications" to="/modules/notifications" alert>
        <Bell width={21} height={21} />
      </CircleButton>
      <UserMenu />
    </div>
  );
}
