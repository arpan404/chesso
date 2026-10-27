import { useState } from "react";
import { createRoot } from "react-dom/client";
import { Board } from "../../src/Board";
import { Workspace } from "../../src/Workspace";
import { Landing } from "../../src/App";
import { ApiProvider } from "../../src/api";
import { startingPosition } from "../../src/starting-position";
import "../../src/index.css";

const scenario = new URLSearchParams(location.search).get("scenario");
function BoardFixture() {
  const [move, setMove] = useState("");
  const promotion = scenario === "promotion";
  const position = promotion
    ? {
        fen: "4k3/P7/8/8/8/8/8/4K3 w - - 0 1",
        pieces: { e1: "K", e8: "k", a7: "P" },
        legal_moves: ["a7a8q", "a7a8r", "a7a8b", "a7a8n"],
        turn: "white" as const,
        check: false,
        result: null,
      }
    : { ...startingPosition, legal_moves: ["e2e3", "e2e4", "b1a3", "b1c3"] };
  return (
    <main className="main-workspace">
      <h1>Chessboard</h1>
      <div className="max-w-xl mt-6">
        <Board
          position={position}
          disabled={scenario === "readonly"}
          onMove={setMove}
        />
        <output aria-label="Recorded move">{move}</output>
      </div>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(
  scenario === "public" ? (
    <Landing configured={false} />
  ) : scenario === "workspace" ? (
    <ApiProvider getToken={async () => "test-fixture-token"}>
      <Workspace signOut={async () => {}} />
    </ApiProvider>
  ) : (
    <BoardFixture />
  ),
);
