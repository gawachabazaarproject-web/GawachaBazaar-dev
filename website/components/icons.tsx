type IconProps = { className?: string };

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24",
};

export function IconLeaf({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M4 19c8-1 14-6 15.5-15.5C11 3 4.5 8.5 4 17" />
      <path d="M4 19c2-4 5-7 9-9" />
    </svg>
  );
}

export function IconCrate({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M3 8h18l-1.5 12h-15L3 8Z" />
      <path d="M3 8 6 3h12l3 5" />
      <path d="M3 12h18M9 8v12M15 8v12" />
    </svg>
  );
}

export function IconCheckBadge({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M12 3 14.5 5H18v3.5L20 11l-2 2.5V17h-3.5L12 19l-2.5-2H6v-3.5L4 11l2-2.5V5h3.5Z" />
      <path d="M9 12l2 2 4-4.5" />
    </svg>
  );
}

export function IconWarehouse({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M3 10 12 4l9 6v10H3V10Z" />
      <path d="M9 20v-6h6v6" />
    </svg>
  );
}

export function IconBasket({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M5 10h14l-1.5 9h-11L5 10Z" />
      <path d="M8 10 10 4M16 10 14 4M3 10h18" />
    </svg>
  );
}

export function IconCart({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <circle cx="9" cy="20" r="1" />
      <circle cx="17" cy="20" r="1" />
      <path d="M3 4h2l2.4 12.2a2 2 0 0 0 2 1.8h7.2a2 2 0 0 0 2-1.6L20 8H6" />
    </svg>
  );
}

export function IconPayment({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M3 10h18M7 15h4" />
    </svg>
  );
}

export function IconTruck({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M3 7h11v9H3V7Z" />
      <path d="M14 10h4l3 3v3h-7v-6Z" />
      <circle cx="7.5" cy="18" r="1.6" />
      <circle cx="17.5" cy="18" r="1.6" />
    </svg>
  );
}

export function IconBike({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <circle cx="6" cy="17" r="3" />
      <circle cx="18" cy="17" r="3" />
      <path d="M6 17l4-8h4l3 4M10 9h3M14 13h4" />
    </svg>
  );
}

export function IconHeart({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M12 20s-7-4.35-9.5-9C.8 7.2 3 4 6.3 4c2 0 3.3 1.2 4.2 2.4C11.4 5.2 12.7 4 14.7 4 18 4 20.2 7.2 18.5 11 16 15.65 12 20 12 20Z" />
    </svg>
  );
}

export function IconHome({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M4 11 12 4l8 7" />
      <path d="M6 10v9h12v-9" />
      <path d="M10 19v-5h4v5" />
    </svg>
  );
}

export function IconVillage({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M3 20V11l4-3 4 3v9" />
      <path d="M11 20v-6l5-4 5 4v6" />
      <path d="M3 20h18" />
    </svg>
  );
}

export function IconMapPin({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21Z" />
      <circle cx="12" cy="9.5" r="2.3" />
    </svg>
  );
}

export function IconArrowRight({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export function IconCheck({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 12.5l2.5 2.5L16 9" />
    </svg>
  );
}

export function IconSprout({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M12 21v-8" />
      <path d="M12 13c0-4-3-6-7-6 0 4 3 6 7 6Z" />
      <path d="M12 11c0-3.5 2.5-5.5 6-5.5 0 3.5-2.5 5.5-6 5.5Z" />
    </svg>
  );
}

export function IconGrain({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M12 3c2 3-2 4 0 7s-2 4 0 7" />
      <path d="M9 6c1 1 1 2 0 3M15 6c-1 1-1 2 0 3M9 13c1 1 1 2 0 3M15 13c-1 1-1 2 0 3" />
    </svg>
  );
}

export function IconDairy({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M9 3h6l1 4-2 2v10a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1V9L8 7l1-4Z" />
    </svg>
  );
}

export function IconFruit({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M12 8c-4 0-6.5 3-6.5 6.5A5.5 5.5 0 0 0 11 20c.7 0 1.3-.1 1.9-.4.6.3 1.2.4 1.9.4a5.5 5.5 0 0 0 5.5-5.5C20.3 11 17.8 8 14 8" />
      <path d="M12 8V5c0-1 .8-2 2-2" />
    </svg>
  );
}
