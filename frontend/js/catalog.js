
export function matchCatalog(catalog, text, limit = 8) {
  const q = String(text).trim().toLowerCase();
  if (!q) return catalog.filter((e) => e.official).slice(0, limit);
  const score = (entry) => {
    const label = entry.label.toLowerCase();
    const simbad = entry.simbad.toLowerCase();
    const cat = entry.category.toLowerCase();
    const hint = entry.hint.toLowerCase();
    const aliases = (entry.aliases || []).map((a) => a.toLowerCase());
    if (label === q || simbad === q) return 0;
    if (label.startsWith(q) || simbad.startsWith(q)) return 1;
    if (aliases.some((a) => a === q || a.startsWith(q))) return 2;
    if (label.includes(q) || simbad.includes(q)) return 3;
    if (aliases.some((a) => a.includes(q))) return 4;
    if (cat.includes(q) || hint.includes(q)) return 5;
    return -1;
  };
  return catalog
    .map((entry) => ({ entry, rank: score(entry) }))
    .filter((x) => x.rank >= 0)
  .sort((a, b) => a.rank - b.rank || a.entry.label.localeCompare(b.entry.label))
    .slice(0, limit)
    .map((x) => x.entry);
}