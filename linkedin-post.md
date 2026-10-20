## Main post (paste into LinkedIn)

🚀 Launching on 1 November 2026: Gawacha Bazaar, a farm-to-home fresh-food marketplace for Nagpur, India.

I'm proud to share a client project I've been building end to end: the complete platform behind a fresh-food delivery business.

The brief: let customers order fresh vegetables, fruit and groceries from their phone, and give the client's team the tools to run orders, stock, delivery and payments every day.

What I delivered:

📱 Customer mobile app (Expo / React Native)
Browse, voice search, wishlist, cart, order tracking, one-tap reorder. Sign in with email, Google or phone OTP.

🖥️ Admin web panel (Next.js)
The client's staff manage orders, products, inventory, delivery, payments, refunds, promotions and content. A live sound alarm rings when a new order arrives, and every role sees only what it is permitted to.

⚙️ FastAPI + PostgreSQL backend
193 API routes, 50 data models, 38 migrations. The backend alone decides every price, fee, discount and status change.

Features built around the client's business:

🚚 Smart delivery pricing: 15+ different products in a basket = free delivery (a "Bazaar"). Smaller baskets pay a base fee plus a per-km charge based on road distance.

📦 Stock that doesn't lie: lot-level inventory, FIFO allocation, a 30-minute reservation at checkout, and stock consumed only on delivery.

💳 Cash on Delivery or Razorpay, with server-side verification, idempotent webhooks and an admin-approved refund workflow.

🏢 Bulk orders: businesses request quantities, receive versioned quotes, accept, and staff convert them to orders.

🔐 Security by design: Firebase handles identity, roles are re-checked from the database on every request, and an authorization test fails if any route's access rules change unreviewed.

🧪 About 900 automated backend tests run against a real PostgreSQL database, plus an independent QA audit.

Working with a real client taught me that the unglamorous parts (state machines, idempotency, careful money handling, honest documentation) are what keep a business's money and stock correct from day one.

Reports, reviews and an audit-log viewer are planned for the next phase.

Huge thanks to the Gawacha Bazaar team for their trust. Launch day is 1 Nov 🌱

Stack: FastAPI · PostgreSQL · SQLAlchemy · Expo · React Native · Next.js · Firebase Auth · Razorpay · Cloudinary · Docker

#ClientProject #Launch #FastAPI #ReactNative #NextJS #PostgreSQL #Agritech #FreshFood #Nagpur #SoftwareEngineering

---

## Short version

🚀 Launching 1 Nov 2026: Gawacha Bazaar, a farm-fresh grocery delivery platform for Nagpur, built for a client.

Customer mobile app + admin panel + FastAPI backend. Free delivery for 15+ product baskets, distance-based fees, live stock reservations, Razorpay + COD, bulk quotes and about 900 backend tests.

Grateful to the client for the trust. Can't wait for launch day! 🥬

#ClientProject #Launch #FastAPI #ReactNative #NextJS

---

## Tips
- Attach 3-4 screenshots: home screen, cart with the free-delivery progress bar, order tracker, admin Orders page. Check none show customer data or secrets.
- Confirm with the client that you may name them and share screenshots before posting.
- Counts (193 routes, 50 models, 38 migrations, ~900 tests) come from docs verified on 2026-10-14, not re-checked now.
- Tag the client's LinkedIn page if they have one.
