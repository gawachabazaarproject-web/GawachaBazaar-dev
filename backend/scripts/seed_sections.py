"""Seeds the "Ready to Cook" and "Juices" storefront sections - each a
top-level category with subcategories, a photo on every one, and a few
sellable products - on top of whatever the catalog already holds.

Safe to re-run (get-or-create on slug). Everything seeded here can be
renamed, re-imaged, deactivated or deleted from the Admin panel's
Categories page.

Usage (from backend/, with the venv active):
    python scripts/seed_sections.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from seed_dummy_data import get_or_create_location, get_or_create_supplier, seed_product

from app.db.session import SessionLocal
from app.models.category import Category

_U = "https://images.unsplash.com/photo-{}?w=800&h=800&fit=crop&q=80"

# (name, slug, description, image, [subcategories])
SECTIONS = [
    (
        "Ready to Cook",
        "ready-to-cook",
        "Marinated, chopped and pre-mixed - dinner in minutes.",
        _U.format("1567188040759-fb8a883dc6d8"),
        [
            ("Marinated Paneer & Tikka", "marinated-paneer-tikka", "Pre-marinated and ready for the pan.", _U.format("1567188040759-fb8a883dc6d8")),
            ("Curry & Gravy Bases", "curry-gravy-bases", "Slow-cooked bases - just add your vegetables.", _U.format("1596797038530-2c107229654b")),
            ("Cut Vegetables", "cut-vegetables", "Washed, chopped and ready for the wok.", _U.format("1498837167922-ddd27525d352")),
            ("Salad & Bowl Kits", "salad-bowl-kits", "Fresh bowls assembled in one minute.", _U.format("1512621776951-a57141f2eefd")),
        ],
    ),
    (
        "Juices",
        "juices",
        "Cold-pressed juices, smoothies and seasonal coolers.",
        _U.format("1603569283847-aa295f0d016a"),
        [
            ("Fresh Fruit Juices", "fresh-fruit-juices", "Squeezed fresh, nothing added.", _U.format("1600271886742-f049cd451bba")),
            ("Green & Detox", "green-detox", "Greens, cucumber and mint.", _U.format("1610970881699-44a5587cabec")),
            ("Smoothies & Shakes", "smoothies-shakes", "Thick, fruity and filling.", _U.format("1589733955941-5eeaf752f6dd")),
            ("Bottled & Seasonal", "bottled-seasonal", "Family-size bottles and seasonal specials.", _U.format("1621506289937-a8e4df240d0b")),
        ],
    ),
]

# (subcategory_slug, name, slug, description, unit, pack, price, image)
PRODUCTS = [
    ("marinated-paneer-tikka", "Paneer Tikka Kit", "paneer-tikka-kit", "Paneer cubes in a smoky tikka marinade.", "G", "250", "140.00", _U.format("1567188040759-fb8a883dc6d8")),
    ("curry-gravy-bases", "Restaurant-Style Curry Base", "restaurant-curry-base", "Onion-tomato gravy base for any curry.", "G", "400", "95.00", _U.format("1596797038530-2c107229654b")),
    ("cut-vegetables", "Stir-Fry Veg Mix", "stir-fry-veg-mix", "Colourful chopped vegetables for soups and stir-fries.", "G", "500", "70.00", _U.format("1498837167922-ddd27525d352")),
    ("salad-bowl-kits", "Garden Salad Bowl Kit", "garden-salad-bowl-kit", "Greens, veggies, chickpeas and dressing.", "G", "350", "110.00", _U.format("1512621776951-a57141f2eefd")),
    ("fresh-fruit-juices", "Cold-Pressed Orange Juice", "cold-pressed-orange-juice", "Fresh-squeezed oranges, no sugar added.", "ML", "500", "90.00", _U.format("1600271886742-f049cd451bba")),
    ("green-detox", "Green Detox Juice", "green-detox-juice", "Apple, cucumber, kiwi and mint.", "ML", "300", "80.00", _U.format("1610970881699-44a5587cabec")),
    ("smoothies-shakes", "Strawberry Smoothie", "strawberry-smoothie", "Strawberries blended with fresh curd.", "ML", "300", "95.00", _U.format("1589733955941-5eeaf752f6dd")),
    ("bottled-seasonal", "Mixed Fruit Juice", "mixed-fruit-juice", "Family-size bottle of citrus fruit juice.", "ML", "1000", "120.00", _U.format("1621506289937-a8e4df240d0b")),
]


def get_or_create(db, name, slug, description, image, parent_id=None) -> Category:
    cat = db.query(Category).filter_by(slug=slug).first()
    if cat is None:
        cat = Category(
            name=name, slug=slug, description=description, image_url=image,
            parent_id=parent_id, status="ACTIVE",
        )
        db.add(cat)
        db.commit()
        db.refresh(cat)
        print(f"  + category: {name}")
    return cat


def main() -> None:
    db = SessionLocal()
    try:
        for name, slug, desc, image, subs in SECTIONS:
            parent = get_or_create(db, name, slug, desc, image)
            for s_name, s_slug, s_desc, s_image in subs:
                get_or_create(db, s_name, s_slug, s_desc, s_image, parent.id)

        supplier = get_or_create_supplier(db)
        location = get_or_create_location(db)
        for spec in PRODUCTS:
            seed_product(db, supplier, location, spec)
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
