"""Dev-only seed script: dummy categories, products, variants, prices, and
enough supplier/batch/inventory-lot stock behind each variant that a real
checkout (cart -> reservation -> COD confirm -> fulfillment -> delivery)
can actually be exercised end-to-end from the mobile app.

Not part of the application - never imported by app/ code, never run in
CI or against gawachabazaar_test. Safe to re-run: every insert is
get-or-create keyed on the same natural key (slug/sku/code), so running
this twice does not duplicate data or fail on a unique-constraint clash.

Usage (from backend/, with the venv active):
    python scripts/seed_dummy_data.py
"""

import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.batch import Batch
from app.models.category import Category
from app.models.inventory_location import InventoryLocation
from app.models.inventory_lot import InventoryLot
from app.models.price import Price
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant
from app.models.supplier import Supplier

# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

CATEGORIES = [
    {"name": "Fruits & Vegetables", "slug": "fruits-vegetables"},
    {"name": "Dairy & Bakery", "slug": "dairy-bakery"},
    {"name": "Staples & Grains", "slug": "staples-grains"},
    {"name": "Snacks & Beverages", "slug": "snacks-beverages"},
    {"name": "Personal Care", "slug": "personal-care"},
]

# (category_slug, name, slug, description, unit, pack_quantity, price, image_url)
# Real product photography (Unsplash, hotlink-friendly CDN) - not the
# earlier picsum.photos random-photo placeholders, which had no relation
# to the actual product.
_UNSPLASH = "https://images.unsplash.com/photo-{}?w=600&h=600&fit=crop&q=80"
PRODUCTS = [
    ("fruits-vegetables", "Fresh Bananas", "fresh-bananas", "Naturally ripened, sweet bananas.", "G", "500", "40.00", _UNSPLASH.format("1587132137056-bfbf0166836e")),
    ("fruits-vegetables", "Ripe Tomatoes", "ripe-tomatoes", "Farm-fresh, firm and juicy tomatoes.", "KG", "1", "35.00", _UNSPLASH.format("1582284540020-8acbe03f4924")),
    ("fruits-vegetables", "Red Onions", "red-onions", "Everyday cooking onions.", "KG", "1", "30.00", _UNSPLASH.format("1618512496248-a07fe83aa8cb")),
    ("fruits-vegetables", "Potatoes", "potatoes", "Farm-fresh potatoes, great for every recipe.", "KG", "1", "28.00", _UNSPLASH.format("1518977676601-b53f82aba655")),
    ("dairy-bakery", "Toned Milk", "toned-milk", "Fresh pasteurized toned milk.", "ML", "500", "32.00", _UNSPLASH.format("1634141510639-d691d86f47be")),
    ("dairy-bakery", "Brown Bread", "brown-bread", "Soft whole-wheat brown bread.", "G", "400", "45.00", _UNSPLASH.format("1534620808146-d33bb39128b2")),
    ("dairy-bakery", "Paneer", "paneer", "Fresh, soft cottage cheese.", "G", "200", "80.00", _UNSPLASH.format("1733907557463-915a34237e8e")),
    ("dairy-bakery", "Curd", "curd", "Thick, creamy fresh curd.", "G", "400", "38.00", _UNSPLASH.format("1571212515416-fef01fc43637")),
    ("staples-grains", "Basmati Rice", "basmati-rice", "Long-grain aromatic basmati rice.", "KG", "1", "120.00", _UNSPLASH.format("1586201375761-83865001e31c")),
    ("staples-grains", "Wheat Atta", "wheat-atta", "Stone-ground whole wheat flour.", "KG", "5", "260.00", _UNSPLASH.format("1610725664285-7c57e6eeac3f")),
    ("staples-grains", "Toor Dal", "toor-dal", "Premium quality split pigeon peas.", "KG", "1", "150.00", _UNSPLASH.format("1701166175567-2f55dd40e662")),
    ("snacks-beverages", "Potato Chips", "potato-chips", "Crispy salted potato chips.", "G", "150", "40.00", _UNSPLASH.format("1599490659213-e2b9527bd087")),
    ("snacks-beverages", "Orange Juice", "orange-juice", "100% fresh orange juice, no added sugar.", "ML", "1000", "110.00", _UNSPLASH.format("1600271886742-f049cd451bba")),
    ("snacks-beverages", "Green Tea", "green-tea", "Antioxidant-rich green tea bags.", "G", "100", "180.00", _UNSPLASH.format("1627435601361-ec25f5b1d0e5")),
    ("fruits-vegetables", "Fresh Fenugreek", "fresh-fenugreek", "Leafy fenugreek (methi), bunched fresh.", "G", "250", "18.00", _UNSPLASH.format("1707065879790-256dec8f3760")),
    ("fruits-vegetables", "Green Peas", "green-peas", "Fresh green peas, still in the pod.", "G", "500", "45.00", _UNSPLASH.format("1690023614293-ac2ba2eb0731")),
    ("fruits-vegetables", "Chillies & Coriander", "chillies-coriander", "Green chillies and fresh coriander combo pack.", "G", "200", "22.00", _UNSPLASH.format("1602811380389-27f19e2664e3")),
    ("fruits-vegetables", "Fresh Oranges", "fresh-oranges", "Juicy, naturally sweetened oranges.", "KG", "1", "85.00", _UNSPLASH.format("1593278684776-62f6e2dc7604")),
    ("fruits-vegetables", "Fresh Coriander", "fresh-coriander", "Fresh coriander (kothimbir), bunched.", "G", "100", "12.00", _UNSPLASH.format("1601493700603-43461216807a")),
    ("fruits-vegetables", "Green Chillies", "green-chillies", "Fresh green chillies.", "G", "100", "15.00", _UNSPLASH.format("1576763595295-c0371a32af78")),
    ("fruits-vegetables", "Fresh Lemons", "fresh-lemons", "Juicy, thin-skinned lemons.", "UNIT", "4", "15.00", _UNSPLASH.format("1590502593747-42a996133562")),
    ("fruits-vegetables", "Curry Leaves", "curry-leaves", "Fresh curry leaves (kadi patta).", "G", "100", "8.00", _UNSPLASH.format("1623048839784-a5608f7a7097")),
    ("personal-care", "Hand Wash", "hand-wash", "Gentle, moisturizing liquid hand wash.", "ML", "250", "95.00", _UNSPLASH.format("1597931752949-98c74b5b159f")),
    ("personal-care", "Toothpaste", "toothpaste", "Cavity protection toothpaste.", "G", "200", "85.00", _UNSPLASH.format("1594178990090-ca641059a506")),
]

STOCK_QUANTITY = Decimal("500")
CURRENCY = "INR"


def get_or_create_category(db, name: str, slug: str) -> Category:
    category = db.query(Category).filter_by(slug=slug).first()
    if category:
        return category
    category = Category(name=name, slug=slug, status="ACTIVE")
    db.add(category)
    db.commit()
    db.refresh(category)
    print(f"  + category: {name}")
    return category


def get_or_create_supplier(db) -> Supplier:
    supplier = db.query(Supplier).filter_by(business_name="GawachaBazaar Dev Supplier").first()
    if supplier:
        return supplier
    supplier = Supplier(
        business_name="GawachaBazaar Dev Supplier",
        status="ACTIVE",
        contact_person="Dev Seed",
        phone="+919999999999",
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    print("  + supplier: GawachaBazaar Dev Supplier")
    return supplier


def get_or_create_location(db) -> InventoryLocation:
    location = db.query(InventoryLocation).filter_by(code="DEVHUB").first()
    if location:
        return location
    location = InventoryLocation(
        name="Dev Fulfillment Hub",
        code="DEVHUB",
        type="WAREHOUSE",
        address_line_1="1 Warehouse Road",
        city="Nagpur",
        state="Maharashtra",
        postal_code="440001",
        status="ACTIVE",
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    print("  + inventory location: Dev Fulfillment Hub")
    return location


def seed_product(db, supplier: Supplier, location: InventoryLocation, spec: tuple) -> None:
    category_slug, name, slug, description, unit, pack_quantity, price, image_url = spec
    category = db.query(Category).filter_by(slug=category_slug).first()
    if category is None:
        raise RuntimeError(f"Category '{category_slug}' not seeded yet")

    product = db.query(Product).filter_by(slug=slug).first()
    if product is None:
        product = Product(
            category_id=category.id,
            name=name,
            slug=slug,
            description=description,
            status="ACTIVE",
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        print(f"  + product: {name}")

    image = db.query(ProductImage).filter_by(product_id=product.id).first()
    if image is None:
        db.add(
            ProductImage(
                product_id=product.id,
                image_url=image_url,
                alt_text=name,
                is_primary=True,
                sort_order=0,
            )
        )
        db.commit()
        print(f"    image: {image_url}")
    elif image.image_url != image_url:
        # Re-running with an updated PRODUCTS entry (e.g. swapping in real
        # photography) should actually update the stored image, not skip
        # it silently just because a row already exists.
        image.image_url = image_url
        db.commit()
        print(f"    image updated: {image_url}")

    sku = f"DEV-{slug.upper()}"
    variant = db.query(ProductVariant).filter_by(sku=sku).first()
    if variant is None:
        variant = ProductVariant(
            product_id=product.id,
            name=f"{pack_quantity} {unit.lower()}",
            sku=sku,
            unit=unit,
            quantity=Decimal(pack_quantity),
            status="ACTIVE",
        )
        db.add(variant)
        db.commit()
        db.refresh(variant)
        print(f"    variant: {variant.name} ({sku})")

    if not db.query(Price).filter_by(variant_id=variant.id, is_active=True).first():
        db.add(
            Price(
                variant_id=variant.id,
                price=Decimal(price),
                currency=CURRENCY,
                valid_from=datetime.now(UTC) - timedelta(days=1),
                valid_to=None,
                is_active=True,
            )
        )
        db.commit()
        print(f"    price: {CURRENCY} {price}")

    batch_code = f"DEVBATCH-{slug}"
    batch = db.query(Batch).filter_by(batch_code=batch_code).first()
    if batch is None:
        batch = Batch(
            supplier_id=supplier.id,
            product_id=product.id,
            batch_code=batch_code,
            harvest_date=date.today(),
            quantity=STOCK_QUANTITY,
            unit=unit,
            status="APPROVED",
            purchase_price=(Decimal(price) * Decimal("0.6")).quantize(Decimal("0.01")),
            purchase_currency=CURRENCY,
            received_date=date.today(),
            receiving_reference=f"DEV-GRN-{slug}",
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)

    if not db.query(InventoryLot).filter_by(batch_id=batch.id, variant_id=variant.id, location_id=location.id).first():
        db.add(
            InventoryLot(
                batch_id=batch.id,
                variant_id=variant.id,
                location_id=location.id,
                quantity=STOCK_QUANTITY,
                status="ACTIVE",
            )
        )
        db.commit()
        print(f"    stock: {STOCK_QUANTITY} {unit.lower()} at Dev Fulfillment Hub")


def main() -> None:
    db = SessionLocal()
    try:
        print("Seeding categories...")
        for cat in CATEGORIES:
            get_or_create_category(db, cat["name"], cat["slug"])

        print("Seeding supplier and inventory location...")
        supplier = get_or_create_supplier(db)
        location = get_or_create_location(db)

        print("Seeding products, variants, prices, and stock...")
        for spec in PRODUCTS:
            seed_product(db, supplier, location, spec)

        print(f"\nDone. {len(CATEGORIES)} categories, {len(PRODUCTS)} products seeded/verified.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
