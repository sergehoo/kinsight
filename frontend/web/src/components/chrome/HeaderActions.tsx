import { Bell, Briefcase } from "@/components/overview/icons";

import { Avatar } from "./Avatar";
import { CircleButton } from "./CircleButton";

/** Actions de l'en-tête : portefeuille, notifications, profil. */
export function HeaderActions() {
  return (
    <div className="flex items-center gap-3">
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
