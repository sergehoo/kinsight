import { DynamicSidebar } from "@/components/navigation/DynamicSidebar";

/** Compatibilité avec l'ancien shell : la sidebar est désormais contextuelle. */
export function SideRail() {
  return <DynamicSidebar />;
}
