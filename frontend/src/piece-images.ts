const images = import.meta.glob<string>("./assets/pieces/*.svg", {
  eager: true,
  query: "?url",
  import: "default",
});

export function pieceImage(symbol: string) {
  const color = symbol === symbol.toUpperCase() ? "w" : "b";
  return images[`./assets/pieces/${color}${symbol.toUpperCase()}.svg`];
}
