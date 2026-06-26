import type * as React from "react";
import { Navigate } from "react-router-dom";

import { canAccess, getCurrentPermissions, type Permission } from "@/lib/permissions";

interface PermissionGuardProps {
  children: React.ReactNode;
  requiredPermissions?: Permission[];
  fallbackTo?: string;
}

export function PermissionGuard({ children, requiredPermissions, fallbackTo = "/dashboard" }: PermissionGuardProps) {
  const permissions = getCurrentPermissions();
  if (!canAccess(requiredPermissions, permissions)) {
    return <Navigate to={fallbackTo} replace />;
  }
  return <>{children}</>;
}
