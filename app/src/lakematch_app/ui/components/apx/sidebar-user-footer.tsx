import { Suspense } from "react";
import { SidebarMenuButton } from "@/components/ui/sidebar";
import { useSessionSuspense } from "@/lib/api";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import selector from "@/lib/selector";

function SidebarUserFooterSkeleton() {
  return (
    <SidebarMenuButton size="lg">
      <Skeleton className="h-8 w-8 rounded-lg" />
      <div className="grid flex-1 text-left text-sm leading-tight gap-1">
        <Skeleton className="h-4 w-24 rounded" />
        <Skeleton className="h-3 w-46 rounded" />
      </div>
    </SidebarMenuButton>
  );
}

// The reviewer every label is recorded under, and where labels go.
function SidebarUserFooterContent() {
  const { data: s } = useSessionSuspense(selector());
  const initials = s.reviewer.slice(0, 2).toUpperCase();
  return (
    <SidebarMenuButton size="lg" title={`${s.source}\nlabels: ${s.label_store}`}>
      <Avatar className="h-8 w-8 rounded-lg grayscale">
        <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
      </Avatar>
      <div className="grid flex-1 text-left text-sm leading-tight">
        <span className="truncate font-medium">{s.reviewer}</span>
        <span className="text-muted-foreground truncate text-xs">{s.label_store}</span>
      </div>
    </SidebarMenuButton>
  );
}

export default function SidebarUserFooter() {
  return (
    <Suspense fallback={<SidebarUserFooterSkeleton />}>
      <SidebarUserFooterContent />
    </Suspense>
  );
}
