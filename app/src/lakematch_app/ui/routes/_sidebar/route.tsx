import SidebarLayout from "@/components/apx/sidebar-layout";
import { createFileRoute, Link, useLocation } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
import { BarChart3, Keyboard, ListChecks, Sparkles } from "lucide-react";
import { useGenieConfig } from "@/lib/api";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

export const Route = createFileRoute("/_sidebar")({
  component: () => <Layout />,
});

function Layout() {
  const location = useLocation();
  const genie = useGenieConfig({ query: { select: (d) => d.data } });

  const navItems = [
    { to: "/review", label: "Review", icon: <Keyboard size={16} />, match: (p: string) => p === "/review" },
    { to: "/stats", label: "Statistics", icon: <BarChart3 size={16} />, match: (p: string) => p === "/stats" },
    { to: "/labels", label: "Labels", icon: <ListChecks size={16} />, match: (p: string) => p === "/labels" },
    // the Genie panel exists only when paid_features.genie is on for this deployment
    ...(genie.data?.enabled
      ? [{ to: "/genie", label: "Genie", icon: <Sparkles size={16} />, match: (p: string) => p === "/genie" }]
      : []),
  ];

  return (
    <SidebarLayout>
      <SidebarGroup>
        <SidebarGroupContent>
          <SidebarMenu>
            {navItems.map((item) => (
              <SidebarMenuItem key={item.to}>
                <Link
                  to={item.to}
                  className={cn(
                    "flex items-center gap-2 p-2 rounded-lg",
                    item.match(location.pathname)
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  )}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </Link>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarLayout>
  );
}
