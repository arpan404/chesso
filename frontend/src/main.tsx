import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ClerkProvider } from "@clerk/react";
import { ui } from "@clerk/ui";
import { shadcn } from "@clerk/ui/themes";
import App, { Landing } from "./App";
import "./index.css";

try {
  document.documentElement.dataset.theme =
    localStorage.getItem("chesso-theme") === "dark" ? "dark" : "light";
} catch {
  document.documentElement.dataset.theme = "light";
}
const key = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
function Root() {
  const [dark, setDark] = useState(
    document.documentElement.dataset.theme === "dark",
  );
  useEffect(() => {
    const changed = () =>
      setDark(document.documentElement.dataset.theme === "dark");
    window.addEventListener("chesso-theme", changed);
    return () => window.removeEventListener("chesso-theme", changed);
  }, []);
  return key ? (
    <ClerkProvider
      publishableKey={key}
      ui={ui}
      appearance={{
        theme: shadcn,
        variables: {
          colorPrimary: dark ? "#8fd1b0" : "#1d5a43",
          colorPrimaryForeground: dark ? "#0b2018" : "#ffffff",
          colorBackground: dark ? "#16191b" : "#ffffff",
          colorForeground: dark ? "#eceeef" : "#15181b",
          colorMutedForeground: dark ? "#9ba1a7" : "#5c6166",
          colorInput: dark ? "#16191b" : "#ffffff",
          colorInputForeground: dark ? "#eceeef" : "#15181b",
          colorRing: dark ? "#8fd1b0" : "#2f7a5c",
          fontFamily: '"Source Sans 3 Variable", sans-serif',
          fontFamilyButtons: '"Source Sans 3 Variable", sans-serif',
          fontSize: "1rem",
          borderRadius: "0.5rem",
        },
        elements: {
          rootBox: { width: "100%" },
          cardBox: {
            width: "100%",
            boxShadow: "none",
            border: "1px solid var(--border)",
            borderRadius: "12px",
          },
          card: { width: "100%", boxShadow: "none" },
          footer: { background: "var(--card)" },
        },
      }}
    >
      <App />
    </ClerkProvider>
  ) : (
    <Landing configured={false} />
  );
}
createRoot(document.getElementById("root")!).render(<Root />);
