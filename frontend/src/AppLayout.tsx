import type { ReactNode } from "react";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppSidebar, type NavigationItem } from "./AppSidebar";
import { AppFooter } from "./ResearchCredits";
import { Brand, SoundToggle, ThemeToggle } from "./PublicLayout";

// Desktop uses a single top bar; the sidebar only exists as the mobile sheet.
function TopNavigation({
  items,
  active,
}: {
  items: NavigationItem[];
  active: string;
}) {
  const { isMobile } = useSidebar();
  if (isMobile) return null;
  return (
    <nav aria-label="Main navigation" className="top-nav">
      {items.map((item) => (
        <a
          key={item.id}
          href={item.href}
          aria-current={active === item.id ? "page" : undefined}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}
function MobileOnly({ children }: { children: ReactNode }) {
  const { isMobile } = useSidebar();
  return isMobile ? <>{children}</> : null;
}
export function AppLayout({
  children,
  heading,
  headerControl,
  ...sidebar
}: {
  children: ReactNode;
  heading: ReactNode;
  headerControl?: ReactNode;
  items: NavigationItem[];
  active: string;
  brandHref?: string;
  onNavigate?: (id: string) => void;
  accountControl?: ReactNode;
  accountName?: string;
  footer?: ReactNode;
}) {
  return (
    <TooltipProvider>
      <SidebarProvider className="app-shell">
        <a
          className="skip-link"
          href="#main-content"
          onClick={(event) => {
            event.preventDefault();
            const main = document.getElementById("main-content");
            main?.focus();
            main?.scrollIntoView();
          }}
        >
          Skip to content
        </a>
        <MobileOnly>
          <AppSidebar {...sidebar} />
        </MobileOnly>
        <div className="app-frame">
          <header className="app-topbar">
            <div className="topbar-heading">
              <MobileOnly>
                <SidebarTrigger aria-label="Open navigation" />
                {heading}
              </MobileOnly>
              <div className="topbar-brand">
                <Brand href={sidebar.brandHref} />
              </div>
              <TopNavigation items={sidebar.items} active={sidebar.active} />
            </div>
            <div className="topbar-controls">
              {headerControl}
              <SoundToggle />
              <ThemeToggle />
              <div className="topbar-account">{sidebar.accountControl}</div>
            </div>
          </header>
          <SidebarInset id="main-content" tabIndex={-1} className="app-main">
            <div className="main-workspace">{children}</div>
          </SidebarInset>
          <AppFooter />
        </div>
      </SidebarProvider>
    </TooltipProvider>
  );
}
