/**
 * Category photography. Categories have no image field in the backend
 * (see app/models/category.py), so this is a client-side slug -> photo
 * lookup, same "illustrative presentation layer" pattern as
 * productEmbellishments.ts - real, relevant photography (not generated
 * placeholders), just not sourced from the API. A hashed fallback photo
 * covers any category added later with no explicit entry.
 */
const _UNSPLASH = (id: string) => `https://images.unsplash.com/photo-${id}?w=500&h=500&fit=crop&q=80`;

const CATEGORY_PHOTOS: Record<string, string> = {
  "fruits-vegetables": _UNSPLASH("1488459716781-31db52582fe9"),
  "dairy-bakery": _UNSPLASH("1634141510639-d691d86f47be"),
  "staples-grains": _UNSPLASH("1621956838481-f8f616950454"),
  "snacks-beverages": _UNSPLASH("1599490659213-e2b9527bd087"),
  "personal-care": _UNSPLASH("1618840313409-66c0d92d6f26"),
};

const FALLBACK_PHOTOS = [
  _UNSPLASH("1488459716781-31db52582fe9"),
  _UNSPLASH("1621956838481-f8f616950454"),
];

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function getCategoryPhoto(slug: string): string {
  return CATEGORY_PHOTOS[slug] ?? FALLBACK_PHOTOS[hashString(slug) % FALLBACK_PHOTOS.length];
}
