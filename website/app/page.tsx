import SmoothScroll from "@/components/SmoothScroll";
import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import RouteFlow from "@/components/RouteFlow";
import AerialLocation from "@/components/AerialLocation";
import VillageCulture from "@/components/VillageCulture";
import HubSpec from "@/components/HubSpec";
import Traceability from "@/components/Traceability";
import Testimonial from "@/components/Testimonial";
import Delivery from "@/components/Delivery";
import WhyChooseUs from "@/components/WhyChooseUs";
import OurGrowers from "@/components/OurGrowers";
import CompanyInfo from "@/components/CompanyInfo";
import FreshGallery from "@/components/FreshGallery";
import SeasonBoard from "@/components/SeasonBoard";
import Products from "@/components/Products";
import AppCTA from "@/components/AppCTA";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <SmoothScroll>
      <Nav />
      <main>
        <Hero />
        <RouteFlow />
        <AerialLocation />
        <VillageCulture />
        <HubSpec />
        <Traceability />
        <Testimonial />
        <Delivery />
        <WhyChooseUs />
        <OurGrowers />
        <CompanyInfo />
        <FreshGallery />
        <SeasonBoard />
        <Products />
        <AppCTA />
      </main>
      <Footer />
    </SmoothScroll>
  );
}
