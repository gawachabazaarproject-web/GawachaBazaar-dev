import type { ElementType, ComponentPropsWithoutRef } from "react";
import { IconArrowRight } from "./icons";

type Tone = "dark" | "light";

type EditorialLinkOwnProps<T extends ElementType> = {
  as?: T;
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
};

type EditorialLinkProps<T extends ElementType> = EditorialLinkOwnProps<T> &
  Omit<ComponentPropsWithoutRef<T>, keyof EditorialLinkOwnProps<T>>;

export default function EditorialLink<T extends ElementType = "a">({
  as,
  tone = "dark",
  className = "",
  children,
  ...rest
}: EditorialLinkProps<T>) {
  const Comp = (as || "a") as ElementType;
  const line = tone === "dark" ? "bg-primary-800" : "bg-neutral-100";
  const text = tone === "dark" ? "text-primary-800" : "text-neutral-100";

  return (
    <Comp
      className={`group inline-flex items-center gap-2.5 text-xs font-semibold uppercase tracking-widest2 ${text} ${className}`}
      {...rest}
    >
      <span className="relative pb-1">
        {children}
        <span
          className={`absolute inset-x-0 bottom-0 h-px origin-left scale-x-100 transition-transform duration-500 ease-editorial ${line} group-hover:scale-x-0`}
        />
        <span
          className={`absolute inset-x-0 bottom-0 h-px origin-right scale-x-0 transition-transform delay-100 duration-500 ease-editorial ${line} group-hover:scale-x-100`}
        />
      </span>
      <IconArrowRight className="h-3.5 w-3.5 shrink-0 transition-transform duration-500 ease-editorial group-hover:translate-x-1.5" />
    </Comp>
  );
}
