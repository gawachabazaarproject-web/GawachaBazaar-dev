/**
 * "Pairs well with" relations between real product slugs - used to build
 * the search results page's recommendation rail. Illustrative curation
 * (explicitly authorized), but every slug it names is a real, addable
 * product; nothing here is fabricated data, just a hand-picked grouping.
 */
export const RELATED_PRODUCTS: Record<string, string[]> = {
  "ripe-tomatoes": ["fresh-coriander", "green-chillies", "red-onions"],
  "red-onions": ["ripe-tomatoes", "green-chillies", "fresh-coriander"],
  "potatoes": ["red-onions", "ripe-tomatoes"],
  "toned-milk": ["curd", "paneer"],
  "curd": ["toned-milk", "paneer"],
  "basmati-rice": ["toor-dal", "wheat-atta"],
  "toor-dal": ["basmati-rice", "curry-leaves", "green-chillies"],
  "wheat-atta": ["toned-milk", "toor-dal"],
  "fresh-fenugreek": ["fresh-coriander", "green-chillies"],
  "green-peas": ["potatoes", "ripe-tomatoes"],
  "fresh-oranges": ["fresh-lemons"],
};

export const DEFAULT_QUICK_SEARCH_TERMS = ["Tomato", "Onion", "Milk", "Rice", "Bread", "Dal"];
