const pieces: Record<string, string> = {
  K: "King",
  Q: "Queen",
  R: "Rook",
  B: "Bishop",
  N: "Knight",
};

// Reads a SAN move aloud in plain words: "Rxh6+" -> "Rook takes h6, check".
export function describeMove(san: string) {
  const ending = san.endsWith("#")
    ? ", checkmate"
    : san.endsWith("+")
      ? ", check"
      : "";
  const move = san.replace(/[+#!?]+$/, "");
  if (move.startsWith("O-O"))
    return `Castles ${move === "O-O-O" ? "queenside" : "kingside"}${ending}`;
  const piece = pieces[move[0]] || "Pawn";
  const square = move.match(/[a-h][1-8]/g)?.at(-1) || "";
  const promotion = move.match(/=([QRBN])/)?.[1];
  return `${piece} ${move.includes("x") ? "takes" : "to"} ${square}${
    promotion ? `, promotes to ${pieces[promotion].toLowerCase()}` : ""
  }${ending}`;
}
