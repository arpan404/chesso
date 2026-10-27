import type { ReactNode } from "react";
import { ChessKnight, Moon, Sun, Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AppFooter } from "./ResearchCredits";
import { useEffect, useState } from "react";
import { setSoundEnabled, soundEnabled } from "./sound";

export function Brand({ href = "/" }: { href?: string }) {
  return (
    <a href={href} className="brand" aria-label="Chesso home">
      <ChessKnight aria-hidden="true" />
      <span>Chesso</span>
    </a>
  );
}
export function ThemeToggle() {
  const [dark, setDark] = useState(
    () => document.documentElement.dataset.theme === "dark",
  );
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={dark ? "Use light theme" : "Use dark theme"}
      onClick={() => {
        const next = !dark;
        setDark(next);
        document.documentElement.dataset.theme = next ? "dark" : "light";
        try {
          localStorage.setItem("chesso-theme", next ? "dark" : "light");
        } catch {
          /* Theme works without storage. */
        }
        window.dispatchEvent(new Event("chesso-theme"));
      }}
    >
      {dark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
    </Button>
  );
}
export function SoundToggle() {
  const [on, setOn] = useState(soundEnabled);
  useEffect(() => {
    const changed = () => setOn(soundEnabled());
    window.addEventListener("chesso-sound-setting", changed);
    return () => window.removeEventListener("chesso-sound-setting", changed);
  }, []);
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Sound effects"
      aria-pressed={on}
      title={on ? "Sound effects on" : "Sound effects off"}
      onClick={() => setSoundEnabled(!on)}
    >
      {on ? <Volume2 aria-hidden="true" /> : <VolumeX aria-hidden="true" />}
    </Button>
  );
}
export function PublicLayout({
  children,
  control,
}: {
  children: ReactNode;
  control?: ReactNode;
}) {
  return (
    <div className="public-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="public-header">
        <Brand />
        <div className="public-header-actions">
          {control}
          <SoundToggle />
          <ThemeToggle />
        </div>
      </header>
      <main id="main-content" tabIndex={-1}>
        {children}
      </main>
      <AppFooter />
    </div>
  );
}
