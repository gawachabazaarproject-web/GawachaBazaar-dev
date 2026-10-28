/**
 * Customer-facing legal and policy text. The same text is mirrored in
 * mobile/src/features/legal/content.ts - keep the two files identical when editing.
 * Wording comes from the owner's policy documents; do not paraphrase it here.
 */

export const BUSINESS = {
  name: "GAWACHA BAAZAAR",
  phone: "+91 7387995504",
  phoneHref: "tel:+917387995504",
  email: "gawachabazaar@gmail.com",
  website: "gawachabazaar.in",
  websiteUrl: "https://gawachabazaar.in",
  address:
    "Gondane Palace, 09, Shende Nagar, Teka Naka, Kamptee Road, Behind PWS College, Nagpur – 440026, Maharashtra, India.",
  fssai: "21526055002532",
} as const;

export type PolicySection = { heading?: string; paragraphs?: string[]; bullets?: string[] };
export type Policy = {
  slug: string;
  title: string;
  /** Short label for menus. */
  menuLabel: string;
  intro?: string;
  sections: PolicySection[];
};

const CONTACT_BLOCK: PolicySection = {
  heading: "Contact Information",
  paragraphs: [
    `${BUSINESS.name}`,
    `Address: ${BUSINESS.address}`,
    `Customer Support: ${BUSINESS.phone}`,
    `Email: ${BUSINESS.email}`,
    `Website: ${BUSINESS.website}`,
    `FSSAI License No.: ${BUSINESS.fssai}`,
  ],
};

export const POLICIES: Policy[] = [
  {
    slug: "terms",
    title: "Terms & Conditions",
    menuLabel: "Terms & Conditions",
    intro:
      "Welcome to GAWACHA BAAZAAR! GAWACHA BAAZAAR is an online shopping platform offering fresh fruits, vegetables, groceries, and other available food products. By accessing or using our application, you agree to the following Terms & Conditions.",
    sections: [
      {
        heading: "1. General Terms",
        bullets: [
          "Customers must comply with these Terms & Conditions while using our app.",
          "Customers must provide accurate and complete information.",
          "GAWACHA BAAZAAR reserves the right to update these terms when necessary.",
        ],
      },
      {
        heading: "2. Product Information",
        bullets: [
          "All products are subject to stock availability.",
          "The size, shape, color, and weight of fresh fruits and vegetables may vary naturally.",
          "Product images are for reference purposes only. Actual products may differ slightly.",
        ],
      },
      {
        heading: "3. Pricing & Weight",
        bullets: [
          "All prices are displayed in Indian Rupees (₹).",
          "Prices may change depending on market conditions.",
          "Products sold by weight may be billed according to their actual weight.",
          "Any additional charges will be disclosed before order confirmation.",
        ],
      },
      {
        heading: "4. Order Placement & Confirmation",
        bullets: [
          "Orders are accepted based on product availability and delivery service areas.",
          "GAWACHA BAAZAAR reserves the right to cancel orders due to stock shortages, incorrect information, or other valid reasons.",
          "Payments received for orders cancelled by us will be refunded according to the applicable refund policy.",
        ],
      },
      {
        heading: "5. Delivery Policy",
        bullets: [
          "Delivery services are available only within designated service areas.",
          "Free delivery will be provided wherever the Free Delivery offer is applicable.",
          "Delivery times may vary due to weather conditions, traffic, operational issues, or unforeseen circumstances.",
          "Customers must provide accurate delivery addresses and contact details.",
        ],
      },
      {
        heading: "6. Order Cancellation",
        bullets: [
          "Customers may request cancellation before an order is packed or dispatched.",
          "Cancellation after dispatch will depend on the product category and applicable cancellation policy.",
          "Eligible prepaid cancellations will be refunded according to the refund policy.",
        ],
      },
      {
        heading: "7. Returns & Refunds",
        bullets: [
          "Customers may report incorrect, damaged, spoiled, or poor-quality products.",
          "Complaints should be submitted as soon as possible after delivery.",
          "Customers may be requested to provide photographs or other relevant information.",
          "After verification, eligible complaints may be resolved through replacement, refund, or another appropriate solution.",
          "Customers' statutory consumer rights remain protected.",
        ],
      },
      {
        heading: "8. Payment Terms",
        bullets: [
          "Payments can be made using the payment methods available in the application.",
          "Online transactions are subject to the terms of the respective payment service providers.",
          "Customers may contact our support team regarding failed payments or incorrect deductions.",
        ],
      },
      {
        heading: "9. Customer Responsibilities",
        bullets: [
          "Customers must not place fraudulent or misleading orders.",
          "Customers must not misuse the application or engage in illegal activities.",
          "Customers are responsible for maintaining the security of their accounts and login credentials.",
        ],
      },
      {
        heading: "10. Offers, Discounts & Loyalty Programs",
        bullets: [
          "Promotional offers are subject to their respective eligibility criteria and validity periods.",
          "Discounts, combo offers, and loyalty programs may have additional conditions.",
          "GAWACHA BAAZAAR may modify or discontinue promotional offers, subject to applicable laws and commitments already made to customers.",
        ],
      },
      {
        heading: "11. Privacy & Data Protection",
        bullets: [
          "Customer information may be collected and processed for order management, payments, delivery, customer support, and other purposes described in our Privacy Policy.",
          "Personal information will be handled in accordance with applicable Indian data protection laws.",
          "Relevant information may be shared with authorized service providers when necessary to deliver our services.",
          "For more details, customers should refer to our separate Privacy Policy.",
        ],
      },
      {
        heading: "12. Limitation of Liability",
        bullets: [
          "GAWACHA BAAZAAR makes reasonable efforts to maintain product quality, accurate information, and timely delivery.",
          "Delivery delays or service interruptions may occur due to circumstances beyond our reasonable control.",
          "Nothing in these Terms & Conditions limits any rights or remedies available to consumers under applicable law.",
        ],
      },
      {
        heading: "13. Governing Law",
        paragraphs: [
          "These Terms & Conditions shall be governed by the applicable laws of India. Consumer complaints and disputes shall be handled in accordance with applicable legal provisions.",
        ],
      },
      { ...CONTACT_BLOCK, heading: "14. Contact Information" },
      {
        paragraphs: [
          "By using the GAWACHA BAAZAAR application, you acknowledge that you have read, understood, and agreed to these Terms & Conditions.",
        ],
      },
    ],
  },
  {
    slug: "privacy",
    title: "Privacy Policy",
    menuLabel: "Privacy Policy",
    sections: [
      {
        heading: "What we collect and why",
        bullets: [
          "Customer information may be collected and processed for order management, payments, delivery, customer support, and other purposes described in this policy.",
          "Customers must provide accurate and complete information, including delivery addresses and contact details.",
        ],
      },
      {
        heading: "How it is handled",
        bullets: [
          "Personal information will be handled in accordance with applicable Indian data protection laws.",
          "Relevant information may be shared with authorized service providers when necessary to deliver our services.",
          "Online transactions are subject to the terms of the respective payment service providers. Never share your UPI PIN, OTP, or banking passwords with anyone claiming to represent GAWACHA BAAZAAR.",
        ],
      },
      {
        heading: "Deleting your information",
        paragraphs: [
          "You may request deletion of your account and eligible personal information at any time by contacting us. See the Account & Data Deletion Policy.",
        ],
      },
      {
        heading: "Privacy concerns",
        paragraphs: [
          `For privacy questions, contact us on ${BUSINESS.phone} or ${BUSINESS.email}.`,
        ],
      },
    ],
  },
  {
    slug: "refund",
    title: "Cancellation, Return & Refund",
    menuLabel: "Cancellation, Return & Refund",
    sections: [
      {
        heading: "Order Cancellation",
        bullets: [
          "Customers may request cancellation before an order is packed or dispatched.",
          "Cancellation after dispatch will depend on the product category and applicable cancellation policy.",
          "Eligible prepaid cancellations will be refunded according to this policy.",
          "Orders cancelled by GAWACHA BAAZAAR (for example due to stock shortages or incorrect information) will have any payment received refunded.",
        ],
      },
      {
        heading: "Returns & Complaints",
        bullets: [
          "Customers may report incorrect, damaged, spoiled, or poor-quality products.",
          "Complaints should be submitted as soon as possible after delivery.",
          "Customers may be requested to provide photographs or other relevant information.",
          "After verification, eligible complaints may be resolved through replacement, refund, or another appropriate solution.",
          "Customers' statutory consumer rights remain protected.",
        ],
      },
      {
        heading: "Refund Method and Timing",
        bullets: [
          "Approved refunds will generally be returned through the original payment method where feasible.",
          "The expected processing period will be communicated to the customer. Actual credit timing may depend on the bank or payment provider.",
          "Where Cash on Delivery is available, any approved refund will be arranged through an appropriate method communicated to the customer.",
        ],
      },
      {
        heading: "Help",
        paragraphs: [`Customer Support: ${BUSINESS.phone}`, `Email: ${BUSINESS.email}`],
      },
    ],
  },
  {
    slug: "shipping",
    title: "Shipping & Delivery",
    menuLabel: "Shipping & Delivery",
    sections: [
      {
        heading: "1. Delivery Areas",
        paragraphs: [
          "GAWACHA BAAZAAR delivers products only within its designated service areas. Delivery availability will be confirmed based on the customer's delivery address.",
        ],
      },
      {
        heading: "2. Delivery Timelines",
        paragraphs: [
          "Estimated delivery times will be communicated through the application or WhatsApp, where applicable. Delivery may be delayed due to traffic, weather, product availability, or other operational circumstances.",
        ],
      },
      {
        heading: "3. Delivery Charges",
        paragraphs: [
          "Delivery charges, if applicable, will be displayed before order confirmation. Free delivery offers will be subject to the applicable offer conditions.",
        ],
      },
      {
        heading: "4. Order Acceptance",
        paragraphs: ["Orders are subject to product availability and confirmation by GAWACHA BAAZAAR."],
      },
      {
        heading: "5. Incorrect Address or Unavailability",
        paragraphs: [
          "Customers are responsible for providing accurate delivery details and remaining reachable during delivery. Additional delivery arrangements, if required, will be communicated to the customer.",
        ],
      },
      {
        heading: "6. Fresh Products",
        paragraphs: [
          "Fresh fruits and vegetables will be selected and packed with reasonable care. Natural variations in size, shape, color, and weight may occur.",
        ],
      },
      {
        heading: "7. Contact Information",
        paragraphs: [`Phone: ${BUSINESS.phone}`, `Email: ${BUSINESS.email}`, `Website: ${BUSINESS.websiteUrl}`],
      },
    ],
  },
  {
    slug: "complaints",
    title: "Complaint & Grievance Policy",
    menuLabel: "Complaints & Grievances",
    sections: [
      {
        heading: "1. Customer Support",
        paragraphs: [
          "Customers may contact GAWACHA BAAZAAR regarding orders, payments, delivery, product quality, refunds, or privacy concerns.",
        ],
      },
      {
        heading: "2. How to Submit a Complaint",
        bullets: [`Phone: ${BUSINESS.phone}`, `Email: ${BUSINESS.email}`, `Website: ${BUSINESS.websiteUrl}`],
        paragraphs: [
          "Please provide your Order ID, registered or contact mobile number, and a description of the issue.",
        ],
      },
      {
        heading: "3. Complaint Acknowledgement",
        paragraphs: [
          "Complaints will be acknowledged within the time required by applicable law. Under the currently applicable Consumer Protection (E-Commerce) Rules, 2020, grievances must be acknowledged within 48 hours.",
        ],
      },
      {
        heading: "4. Complaint Resolution",
        paragraphs: [
          "Complaints will be investigated and resolved as promptly as possible and within the applicable statutory time limits. The currently applicable rules provide for redressal within one month from receipt of the complaint.",
        ],
      },
      {
        heading: "5. Escalation",
        paragraphs: [
          `If a complaint remains unresolved, you may request escalation to the designated Grievance Officer by contacting ${BUSINESS.phone} or ${BUSINESS.email}. Customers retain the right to approach the appropriate consumer dispute redressal authority under applicable law.`,
        ],
      },
    ],
  },
  {
    slug: "pricing",
    title: "Pricing, Weighing & Substitution",
    menuLabel: "Pricing, Weighing & Substitution",
    sections: [
      {
        heading: "1. Product Prices",
        paragraphs: [
          "All prices are displayed in Indian Rupees (INR). Prices and availability may change before an order is confirmed.",
        ],
      },
      {
        heading: "2. Products Sold by Weight",
        paragraphs: [
          "For products sold by weight, the applicable unit price and estimated amount will be displayed wherever feasible. The final amount will be calculated using the actual sale weight and the applicable unit price.",
        ],
      },
      {
        heading: "3. Final Bill",
        paragraphs: [
          "The customer will be informed of the final payable amount, including applicable delivery charges, discounts, taxes, and other disclosed charges, before payment or final confirmation where applicable.",
        ],
      },
      {
        heading: "4. Product Substitution",
        paragraphs: [
          "If an ordered product is unavailable, GAWACHA BAAZAAR may contact the customer to offer an alternative. A substitute product will not be charged at a higher price without the customer's consent.",
        ],
      },
      {
        heading: "5. Quantity or Price Changes",
        paragraphs: [
          "Any material change in the order quantity or payable amount must be communicated to the customer and handled with appropriate consent before finalizing the order.",
        ],
      },
      {
        heading: "6. Market Variations",
        paragraphs: [
          "Fresh produce prices may change according to market conditions. The price applicable to a confirmed order will be communicated to the customer in accordance with the order terms.",
        ],
      },
    ],
  },
  {
    slug: "offers",
    title: "Offers, Loyalty & Promotions",
    menuLabel: "Offers & Loyalty",
    sections: [
      {
        heading: "1. Eligibility",
        paragraphs: [
          "Offers, discounts, combo deals, loyalty benefits, and promotional campaigns are subject to their published eligibility conditions.",
        ],
      },
      {
        heading: "2. Validity",
        paragraphs: [
          "Each offer may have a specified validity period, minimum order value, product restriction, area restriction, or usage limit.",
        ],
      },
      {
        heading: "3. Combining Offers",
        paragraphs: ["Unless expressly stated otherwise, multiple offers cannot be combined automatically."],
      },
      {
        heading: "4. Misuse of Offers",
        paragraphs: [
          "Offers may be withheld or cancelled where there is reasonable evidence of fraud, duplicate claims, or misuse, subject to applicable law.",
        ],
      },
      {
        heading: "5. Changes to Offers",
        paragraphs: [
          "GAWACHA BAAZAAR may modify or discontinue future promotional offers in accordance with applicable law and any commitments already made to eligible customers.",
        ],
      },
      {
        heading: "6. Loyalty Programs",
        paragraphs: [
          "Specific benefits, qualification requirements, redemption conditions, and expiry dates for loyalty programs will be communicated separately.",
        ],
      },
    ],
  },
  {
    slug: "payments",
    title: "Payment & Refund Processing",
    menuLabel: "Payments & Refund Processing",
    sections: [
      {
        heading: "1. Accepted Payment Methods",
        paragraphs: [
          "Available payment methods will be displayed during checkout or communicated through the official ordering channel.",
        ],
      },
      {
        heading: "2. Payment Confirmation",
        paragraphs: [
          "An order requiring online payment will be processed according to the payment status and order confirmation process. Customers should not share their UPI PIN, OTP, or banking passwords with anyone claiming to represent GAWACHA BAAZAAR.",
        ],
      },
      {
        heading: "3. Failed Transactions",
        paragraphs: [
          "If an amount is debited but the order is not confirmed, the customer should contact customer support with the transaction reference and relevant order details.",
        ],
      },
      {
        heading: "4. Refund Eligibility",
        paragraphs: [
          "Refunds will be assessed under the applicable Cancellation, Return & Refund Policy and consumer protection laws.",
        ],
      },
      {
        heading: "5. Refund Method and Timing",
        paragraphs: [
          "Approved refunds will generally be returned through the original payment method where feasible. The expected processing period will be communicated to the customer. Actual credit timing may depend on the bank or payment provider.",
        ],
      },
      {
        heading: "6. Cash-on-Delivery Orders",
        paragraphs: [
          "Where Cash on Delivery is available, any approved refund will be arranged through an appropriate method communicated to the customer.",
        ],
      },
      {
        heading: "7. Payment Disputes",
        paragraphs: [
          "Customers may contact GAWACHA BAAZAAR to resolve billing discrepancies, duplicate charges, or other payment concerns.",
          `Customer Support: ${BUSINESS.phone}`,
          `Email: ${BUSINESS.email}`,
        ],
      },
    ],
  },
  {
    slug: "data-deletion",
    title: "Account & Data Deletion",
    menuLabel: "Account & Data Deletion",
    sections: [
      {
        paragraphs: [
          "You may request deletion of your account and eligible personal information by contacting:",
          `Email: ${BUSINESS.email}`,
          `Phone: ${BUSINESS.phone}`,
          "Requests will be verified and processed in accordance with applicable data protection laws. Certain records may need to be retained for tax, accounting, fraud prevention, dispute resolution, or other legal obligations.",
          "Deleting personal information does not automatically cancel an existing order, refund a payment, or remove records that must legally be retained.",
        ],
      },
    ],
  },
];

export function getPolicy(slug: string | undefined): Policy | undefined {
  return POLICIES.find((p) => p.slug === slug);
}
