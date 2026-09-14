import IntroLoader from "@/components/IntroLoader";
import SmoothScroll from "@/components/SmoothScroll";
import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import RouteFlow from "@/components/RouteFlow";
import AerialLocation from "@/components/AerialLocation";
import VillageCulture from "@/components/VillageCulture";
import HubSpec from "@/components/HubSpec";
import InfiniteLoopPanels from "@/components/InfiniteLoopPanels";
import Traceability from "@/components/Traceability";
import SeasonBoard from "@/components/SeasonBoard";
import FreshGallery from "@/components/FreshGallery";
import Delivery from "@/components/Delivery";
import OurGrowers from "@/components/OurGrowers";
import Testimonial from "@/components/Testimonial";
import WhyChooseUs from "@/components/WhyChooseUs";
import CompanyInfo from "@/components/CompanyInfo";
import Products from "@/components/Products";
import AppCTA from "@/components/AppCTA";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <>
      <IntroLoader />
      <SmoothScroll>
        <Nav />
        <main>
          <Hero />
          <RouteFlow />
          <AerialLocation />
          <VillageCulture />
          <HubSpec />
          <InfiniteLoopPanels />
          <Traceability />
          <SeasonBoard />
          <FreshGallery />
          <Delivery />
          <OurGrowers />
          <Testimonial />
          <WhyChooseUs />
          <CompanyInfo />
          <Products />
          <AppCTA />
        </main>
        <Footer />
      </SmoothScroll>
    </>
  );
}
