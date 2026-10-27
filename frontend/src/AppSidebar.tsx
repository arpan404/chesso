import { type ReactNode, useEffect, useRef } from "react";
import {
  BookOpenText,
  ChessKnight,
  FlaskConical,
  Gamepad2,
  LayoutDashboard,
  History,
  LogIn,
  Puzzle,
  UserRound,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";

export type NavigationItem = { id: string; label: string; href?: string };
const icons = {
  home: Puzzle,
  history: History,
  game: Gamepad2,
  puzzle: Puzzle,
  study: FlaskConical,
  profile: UserRound,
  login: LogIn,
  project: BookOpenText,
};

export function AppSidebar({
  items,
  active,
  onNavigate,
  brandHref = "/",
  accountControl,
  accountName,
  footer,
}: {
  items: NavigationItem[];
  active: string;
  onNavigate?: (id: string) => void;
  brandHref?: string;
  accountControl?: ReactNode;
  accountName?: string;
  footer?: ReactNode;
}) {
  const { setOpenMobile, isMobile, openMobile } = useSidebar();
  const navigateOnClose = useRef(false);
  useEffect(() => {
    if (openMobile) navigateOnClose.current = false;
  }, [openMobile]);
  return (
    <Sidebar
      className="project-sidebar"
      collapsible="icon"
      mobileFinalFocus={() =>
        navigateOnClose.current
          ? document.querySelector<HTMLElement>("main h1")
          : document.querySelector<HTMLElement>('[data-slot="sidebar-trigger"]')
      }
    >
      <SidebarHeader className="project-sidebar-header">
        <a className="project-brand" href={brandHref} aria-label="Chesso home">
          <span className="brand-mark">
            <ChessKnight className="size-6" aria-hidden="true" />
          </span>
          <span className="brand-label">
            <strong>Chesso</strong>
            <small>Chess learning</small>
          </span>
        </a>
      </SidebarHeader>
      <SidebarSeparator />
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>
            {active === "login" || active === "project"
              ? "Project"
              : "Workspace"}
          </SidebarGroupLabel>
          <nav aria-label="Main navigation">
            <SidebarMenu>
              {items.map((item) => {
                const Icon =
                  icons[item.id as keyof typeof icons] || BookOpenText;
                return (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      isActive={active === item.id}
                      tooltip={item.label}
                      aria-current={active === item.id ? "page" : undefined}
                      aria-label={item.label}
                      render={item.href ? <a href={item.href} /> : undefined}
                      onClick={() => {
                        onNavigate?.(item.id);
                        if (isMobile) {
                          navigateOnClose.current = true;
                          setOpenMobile(false);
                        }
                      }}
                    >
                      <Icon
                        className="nav-icon size-5"
                        strokeWidth={1.75}
                        aria-hidden="true"
                      />
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </nav>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="project-sidebar-footer">
        {accountControl || accountName ? (
          <div className="sidebar-user">
            {accountControl}
            <span>{accountName}</span>
          </div>
        ) : null}
        {footer}
      </SidebarFooter>
    </Sidebar>
  );
}
