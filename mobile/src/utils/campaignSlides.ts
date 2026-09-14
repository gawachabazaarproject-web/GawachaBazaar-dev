/**
 * Home screen promotional carousel content - illustrative presentation
 * layer, explicitly authorized as mock content (same convention as
 * productEmbellishments.ts / categoryDepartments.ts). No fake discounts,
 * prices, or statistics appear here.
 *
 * Slides 1 and 2 reuse the app's existing, already-authorized brand copy
 * verbatim (previously shown in ExclusiveBanner / BrandPromiseCard).
 * Slides 3 and 4 are clearly-replaceable placeholder campaign entries
 * built only from real, already-shipped app concepts (the "Vidarbha
 * Regional Specialties" section and the "Today's Morning Harvest"
 * section) - swap `image`/copy here once real campaign assets exist.
 */
export interface CampaignSlide {
  id: string;
  /** Short chapter label, e.g. "SEASONAL MARKET" - the "0N / 0M — " prefix
   * (matching the website's "01 / 08 — LOCAL NAGPUR CONNECTION" pattern)
   * is composed at render time from the slide's position, not stored here. */
  label: string;
  title: string;
  scriptSuffix?: string;
  body: string;
  image: string;
  ctaLabel: string;
}

export const CAMPAIGN_SLIDES: CampaignSlide[] = [
  {
    id: "gaon-to-nagpur",
    label: "SEASONAL MARKET",
    title: "Gaon se Nagpur",
    scriptSuffix: "tak.",
    body: "Fresh, unadulterated harvest picked at dawn from Katol, Wardha & Saoner orchards.",
    image: "https://images.unsplash.com/photo-1489450278009-822e9be04dff?w=1200&h=1500&fit=crop&q=80",
    ctaLabel: "Explore today's market",
  },
  {
    id: "swad-vachan",
    label: "OUR PROMISE",
    title: "Gawacha",
    scriptSuffix: "Swad Vachan.",
    body: "Every rupee you spend directly empowers Vidarbha smallholders, with no middlemen commissions.",
    image: "https://images.unsplash.com/photo-1500937386664-56d1dfef3854?w=1200&h=1500&fit=crop&q=80",
    ctaLabel: "Read our story",
  },
  {
    id: "vidarbha-specials",
    label: "VILLAGE SPECIALS",
    title: "Vidarbha,",
    scriptSuffix: "on your plate.",
    body: "Toor dal, cold-pressed oils and dryland staples sourced directly from Vidarbha's smallholder belt.",
    image: "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=1200&h=1500&fit=crop&q=80",
    ctaLabel: "Shop the specialties",
  },
  {
    id: "picked-at-dawn",
    label: "FRESHNESS",
    title: "Picked",
    scriptSuffix: "at dawn.",
    body: "Nothing sits in cold storage - today's harvest reaches Nagpur kitchens the same evening.",
    image: "https://images.unsplash.com/photo-1610348725531-843dff563e2c?w=1200&h=1500&fit=crop&q=80",
    ctaLabel: "See today's harvest",
  },
];
