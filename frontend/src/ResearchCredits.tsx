export function ResearchCredits({ className = "" }: { className?: string }) {
  return (
    <p className={`research-credits ${className}`}>
      A research project by{" "}
      <a href="https://arpan.sh/" target="_blank" rel="noopener noreferrer">
        Arpan
      </a>
      {" and "}
      <a href="https://rijan.sh/" target="_blank" rel="noopener noreferrer">
        Rijan
      </a>
    </p>
  );
}
export function AppFooter() {
  return (
    <footer className="app-footer">
      <span className="footer-brand">Chesso</span>
      <ResearchCredits />
      <nav aria-label="Legal" className="research-credits">
        <a href="/privacy">Privacy</a>
        {" · "}
        <a href="/terms">Terms</a>
      </nav>
    </footer>
  );
}
