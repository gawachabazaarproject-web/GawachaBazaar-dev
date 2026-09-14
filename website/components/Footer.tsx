import Image from "next/image";

export default function Footer() {
  return (
    <footer id="contact" className="bg-primary-900 pb-8 pt-20 text-neutral-100/70">
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <div className="grid grid-cols-1 gap-12 border-b border-neutral-100/10 pb-14 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="flex items-center gap-3">
              <Image
                src="/images/logo.jpeg"
                alt="Gawacha Bazaar"
                width={44}
                height={44}
                className="h-11 w-11 rounded-full object-cover ring-1 ring-secondary-400/50"
              />
              <span className="font-deva text-lg font-bold text-secondary-400">गावाचा बाजार</span>
            </div>
            <p className="mt-5 max-w-xs text-sm leading-relaxed">
              Connecting Nagpur households directly to family farms across Maharashtra —
              fresh, fair, and fully traceable.
            </p>
          </div>

          <div>
            <p className="eyebrow text-neutral-100/40">Explore</p>
            <div className="mt-5 flex flex-col gap-3 text-sm">
              <a href="#story" className="hover:text-secondary-400">Our Story</a>
              <a href="#journey" className="hover:text-secondary-400">Traceability</a>
              <a href="#products" className="hover:text-secondary-400">Products</a>
              <a href="#delivery" className="hover:text-secondary-400">Delivery</a>
            </div>
          </div>

          <div>
            <p className="eyebrow text-neutral-100/40">Sales &amp; Support</p>
            <div className="mt-5 flex flex-col gap-3 text-sm">
              <a href="tel:+917100000000" className="hover:text-secondary-400">+91 710 000 0000</a>
              <a href="mailto:hello@gawachabazaar.in" className="hover:text-secondary-400">
                hello@gawachabazaar.in
              </a>
              <p>Nagpur, Maharashtra, India</p>
            </div>
          </div>

          <div>
            <p className="eyebrow text-neutral-100/40">Get the App</p>
            <div className="mt-5 flex flex-col gap-3 text-sm">
              <a href="#app" className="hover:text-secondary-400">Download for Android</a>
              <a href="#app" className="hover:text-secondary-400">Download for iOS</a>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-center justify-between gap-4 pt-8 text-xs text-neutral-100/40 sm:flex-row">
          <p>Gawacha Bazaar. © 2026 All rights reserved.</p>
          <div className="flex gap-6">
            <a href="#" className="hover:text-secondary-400">Privacy Policy</a>
            <a href="#" className="hover:text-secondary-400">Terms of Use</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
