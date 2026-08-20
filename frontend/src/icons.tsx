import type { SVGProps } from "react";

type Props = SVGProps<SVGSVGElement>;
const Icon = ({ children, ...props }: Props) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
    {children}
  </svg>
);

export const LeafIcon = (props: Props) => <Icon {...props}><path d="M20 4C12.5 4.2 6.2 7.8 5.3 14.2c-.4 2.8 1.7 5.3 4.5 5.1C16.1 18.9 19.6 12 20 4Z"/><path d="M4 21c2.1-5.2 6.5-9.3 11.3-11.6"/></Icon>;
export const PlusIcon = (props: Props) => <Icon {...props}><path d="M12 5v14M5 12h14"/></Icon>;
export const ArrowIcon = (props: Props) => <Icon {...props}><path d="m9 18 6-6-6-6"/></Icon>;
export const EditIcon = (props: Props) => <Icon {...props}><path d="m4 16-.8 4.8L8 20 19 9l-4-4L4 16Z"/><path d="m13.5 6.5 4 4"/></Icon>;
export const TrashIcon = (props: Props) => <Icon {...props}><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></Icon>;
export const CloseIcon = (props: Props) => <Icon {...props}><path d="m6 6 12 12M18 6 6 18"/></Icon>;
