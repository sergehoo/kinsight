import { ModulePage } from "@/pages/ModulePage";

interface DashboardLayoutProps {
  moduleKey: string;
}

export function DashboardLayout({ moduleKey }: DashboardLayoutProps) {
  return <ModulePage moduleKey={moduleKey} />;
}
