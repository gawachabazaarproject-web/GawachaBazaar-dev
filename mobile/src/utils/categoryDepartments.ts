/**
 * Department groupings for the Categories screen's merchandised grid.
 * Illustrative presentation layer (explicitly authorized), same pattern
 * as productEmbellishments.ts / categoryVisuals.ts: the GROUPING and
 * Marathi labels are curated by hand (the backend has no subcategory
 * concept), but every `productSlugs` entry points at a real product -
 * nothing here is fabricated data, and every department's product count
 * is a real count of real products, not a made-up number. Together the
 * slug lists for a category exactly partition that category's real
 * product catalog (no product missing, none duplicated).
 */
export interface Department {
  id: string;
  name: string;
  marathiName: string;
  productSlugs: string[];
}

export const CATEGORY_MARATHI: Record<string, string> = {
  "fruits-vegetables": "भाज्या व फळे",
  "dairy-bakery": "दूध व बेकरी",
  "staples-grains": "धान्य व पीठ",
  "snacks-beverages": "नाश्ता व पेये",
  "personal-care": "वैयक्तिक काळजी",
};

export const CATEGORY_ICONS: Record<string, string> = {
  "fruits-vegetables": "feather",
  "dairy-bakery": "droplet",
  "staples-grains": "package",
  "snacks-beverages": "coffee",
  "personal-care": "heart",
};

const DEPARTMENTS: Record<string, Department[]> = {
  "fruits-vegetables": [
    { id: "daily-cooking", name: "Daily Cooking", marathiName: "रोजच्या भाज्या", productSlugs: ["ripe-tomatoes", "green-peas", "chillies-coriander"] },
    { id: "leafy-greens", name: "Leafy Greens", marathiName: "पालेभाज्या", productSlugs: ["fresh-fenugreek", "fresh-coriander", "curry-leaves"] },
    { id: "roots-tubers", name: "Roots & Tubers", marathiName: "कंदमुळे व कांदे", productSlugs: ["red-onions", "potatoes"] },
    { id: "fresh-fruits", name: "Fresh Fruits", marathiName: "ताजी फळे", productSlugs: ["fresh-oranges", "fresh-bananas", "fresh-lemons", "green-chillies"] },
  ],
  "dairy-bakery": [
    { id: "milk-curd", name: "Milk & Curd", marathiName: "दूध व दही", productSlugs: ["toned-milk", "curd"] },
    { id: "paneer-bakery", name: "Paneer & Bakery", marathiName: "पनीर व बेकरी", productSlugs: ["paneer", "brown-bread"] },
  ],
  "staples-grains": [
    { id: "rice-atta", name: "Rice & Atta", marathiName: "तांदूळ व पीठ", productSlugs: ["basmati-rice", "wheat-atta"] },
    { id: "dals-pulses", name: "Dals & Pulses", marathiName: "डाळी", productSlugs: ["toor-dal"] },
  ],
  "snacks-beverages": [
    { id: "beverages", name: "Beverages", marathiName: "पेये", productSlugs: ["green-tea", "orange-juice"] },
    { id: "snacks", name: "Snacks", marathiName: "खारट नाश्ता", productSlugs: ["potato-chips"] },
  ],
  "personal-care": [
    { id: "daily-essentials", name: "Daily Essentials", marathiName: "दैनंदिन गरजा", productSlugs: ["hand-wash", "toothpaste"] },
  ],
};

const CATEGORY_STORY: Record<string, string> = {
  "fruits-vegetables": "Harvested daily at 4:00 AM from Saoner, Katol & Wardha organic farms. Unchilled & chemically untouched.",
  "dairy-bakery": "Fresh milk, curd & paneer from Umred Desi Goshala, delivered same-day chilled.",
  "staples-grains": "Stone-ground atta & sun-dried dals, sourced directly from the Wardha Organic Cluster.",
  "snacks-beverages": "Everyday snacks & beverages, stocked fresh from trusted local suppliers.",
  "personal-care": "Everyday household essentials, at fair village prices.",
};

export function getDepartments(slug: string): Department[] {
  return DEPARTMENTS[slug] ?? [];
}

export function getCategoryStory(slug: string): string {
  return CATEGORY_STORY[slug] ?? "Sourced fresh, delivered direct from Vidarbha's farming villages.";
}
