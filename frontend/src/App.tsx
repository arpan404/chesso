import { lazy, Suspense, useEffect, useState } from "react";
import { SignIn, SignUp, UserButton, useAuth, useClerk } from "@clerk/react";
import { ArrowLeft, LoaderCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button, ButtonLink } from "@/components/ui/button";
import { ApiProvider } from "./api";
import { PublicLayout } from "./PublicLayout";
import { ResearchCredits } from "./ResearchCredits";
import { Board } from "./Board";

const Workspace = lazy(() =>
  import("./Workspace").then((module) => ({ default: module.Workspace })),
);
const previewPosition = {
  fen: "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
  pieces: {
    g8: "k",
    f7: "p",
    g7: "p",
    h7: "p",
    f2: "P",
    g2: "P",
    h2: "P",
    e1: "R",
    g1: "K",
  },
  legal_moves: [],
  turn: "white" as const,
  check: false,
  result: null,
};
function publicRoute() {
  return location.hash.startsWith("#/project")
    ? "project"
    : new URLSearchParams(location.search).get("auth") === "signup"
      ? "signup"
      : "login";
}
export function Landing({ configured = true }: { configured?: boolean }) {
  const [route, setRoute] = useState(publicRoute);
  useEffect(() => {
    const changed = () => setRoute(publicRoute());
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  return (
    <PublicLayout
      control={
        <a className="text-link" href={route === "project" ? "/" : "#/project"}>
          {route === "project" ? "Log in" : "About the project"}
        </a>
      }
    >
      {route === "project" ? (
        <section className="about-page">
          <a className="text-link" href="/">
            <ArrowLeft aria-hidden="true" />
            Back to login
          </a>
          <h1 tabIndex={-1}>Chess learning, under study.</h1>
          <ResearchCredits />
          <p>
            Chesso studies how people solve chess puzzles and use hints. Start
            with ten puzzles to estimate your level, then practice in sessions
            of 10, 20, or 30 puzzles.
          </p>
          <p>
            Research participation is optional. You can change your consent,
            download your records, or delete your Chesso profile at any time.
          </p>
          <ButtonLink href="/">Log in to Chesso</ButtonLink>
        </section>
      ) : (
        <div className="landing-grid">
          <section className="landing-story">
            <h1 tabIndex={-1}>
              Chess, one puzzle
              <br />
              at a time.
            </h1>
            <p className="landing-description">
              Chess puzzles matched to your starting level.
            </p>
            <ResearchCredits />
          </section>
          <figure className="landing-position">
            <Board position={previewPosition} disabled onMove={() => {}} />
            <figcaption>
              <span>White to move, mate in 1.</span>
              <span>Start with 10 puzzles to find your starting level.</span>
            </figcaption>
          </figure>
          <section
            className="auth-panel"
            aria-label={route === "signup" ? "Create an account" : "Log in"}
          >
            {configured ? (
              route === "signup" ? (
                <SignUp
                  routing="hash"
                  signInUrl="/"
                  fallbackRedirectUrl="/#/home"
                />
              ) : (
                <SignIn
                  routing="hash"
                  signUpUrl="/?auth=signup"
                  fallbackRedirectUrl="/#/home"
                />
              )
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>Welcome to Chesso</CardTitle>
                </CardHeader>
                <CardContent>
                  <p>Sign-in is unavailable.</p>
                  <Button className="w-full mt-6" disabled>
                    Log in
                  </Button>
                </CardContent>
              </Card>
            )}
            <p className="auth-note">Your progress stays with your account.</p>
          </section>
        </div>
      )}
    </PublicLayout>
  );
}
export default function App() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { signOut } = useClerk();
  if (!isLoaded)
    return (
      <div className="loading-state" role="status">
        <LoaderCircle className="animate-spin size-5" aria-hidden="true" />
        Loading…
      </div>
    );
  if (!isSignedIn) return <Landing />;
  return (
    <ApiProvider getToken={getToken}>
      <Suspense
        fallback={
          <div className="loading-state" role="status">
            Loading…
          </div>
        }
      >
        <Workspace
          accountControl={<UserButton />}
          signOut={async () => {
            await signOut({ redirectUrl: "/" });
          }}
        />
      </Suspense>
    </ApiProvider>
  );
}
