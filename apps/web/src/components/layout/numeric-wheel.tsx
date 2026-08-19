/**
 * Decorative sacred-geometry-inspired motif: a numeric wheel with 9 nodes
 * (the digits 1-9 of the Pythagorean system) connected by fine lines. Pure
 * inline SVG, no external assets. Purely decorative — always aria-hidden.
 */
export function NumericWheel({ className }: { className?: string }) {
  const radius = 42;
  const center = 50;
  const nodes = Array.from({ length: 9 }, (_, i) => {
    const angle = (i / 9) * Math.PI * 2 - Math.PI / 2;
    return {
      x: center + radius * Math.cos(angle),
      y: center + radius * Math.sin(angle),
      n: i + 1,
    };
  });

  return (
    <svg
      viewBox="0 0 100 100"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <circle cx={center} cy={center} r={radius} fill="none" stroke="#8F6B3E" strokeWidth="0.4" opacity="0.5" />
      <circle cx={center} cy={center} r={radius * 0.55} fill="none" stroke="#8F6B3E" strokeWidth="0.3" opacity="0.35" />
      {nodes.map((a, i) =>
        nodes.map((b, j) => {
          if (j <= i) return null;
          return (
            <line
              key={`${i}-${j}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="#C8A96B"
              strokeWidth="0.15"
              opacity="0.18"
            />
          );
        }),
      )}
      {nodes.map((a) => (
        <circle key={a.n} cx={a.x} cy={a.y} r="2" fill="#C8A96B" opacity="0.85" />
      ))}
      <circle cx={center} cy={center} r="1.4" fill="#F2EBDD" />
    </svg>
  );
}
