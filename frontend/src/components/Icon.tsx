import type { ReactNode, SVGProps } from 'react';

export type IconName = 'clinic' | 'specialties' | 'pearls' | 'sun' | 'moon' | 'arrow' | 'check' | 'clock' | 'search' | 'book' | 'chevron' | 'external' | 'sparkles' | 'file' | 'file-code' | 'shield-check' | 'workflow' | 'x' | 'upload' | 'download' | 'refresh' | 'stethoscope' | 'heart' | 'lungs' | 'brain' | 'kidney' | 'droplet' | 'baby' | 'shield' | 'tooth' | 'activity' | 'plus' | 'close' | 'save' | 'bookmark' | 'clipboard' | 'flask' | 'database' | 'image' | 'microscope' | 'filePlus' | 'osce' | 'play' | 'target' | 'layers' | 'fileSearch' | 'trophy' | 'graduation-cap' | 'clipboard-list' | 'bed-double' | 'siren' | 'shuffle';

const paths: Record<IconName, ReactNode> = {
  clinic: <><path d="M12 3v18M3 12h18"/><rect x="4" y="4" width="16" height="16" rx="3"/></>,
  specialties: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/><path d="M8 7h8M8 11h8"/></>,
  pearls: <><path d="M9 18h6M10 22h4"/><path d="M8.2 14.4A7 7 0 1 1 15.8 14.4C14.8 15.2 14 16 14 17h-4c0-1-.8-1.8-1.8-2.6Z"/></>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></>,
  moon: <path d="M20.9 13A8.5 8.5 0 0 1 11 3.1 8.5 8.5 0 1 0 20.9 13Z"/>,
  arrow: <><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 1 4 18.5Z"/><path d="M4 18.5A2.5 2.5 0 0 1 6.5 16H20M8 7h8M8 11h7"/></>,
  chevron: <path d="m6 9 6 6 6-6"/>,
  external: <><path d="M14 3h7v7M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></>,
  sparkles: <><path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3Z"/><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z"/></>,
  file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h8"/></>,
  'file-code': <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M10 12l-2 2 2 2M14 12l2 2-2 2"/></>,
  'shield-check': <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/></>,
  workflow: <><rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/><path d="M9 6h3a3 3 0 0 1 3 3v6"/><path d="m12 12 3 3 3-3"/></>,
  x: <><path d="m18 6-12 12M6 6l12 12"/></>,
  upload: <><path d="M12 16V4m-4 4 4-4 4 4"/><path d="M20 16.5v3A1.5 1.5 0 0 1 18.5 21h-13A1.5 1.5 0 0 1 4 19.5v-3"/></>,
  download: <><path d="M12 4v12m-4-4 4 4 4-4"/><path d="M4 20h16"/></>,
  refresh: <><path d="M20 7v5h-5"/><path d="M4 17v-5h5"/><path d="M5.5 9A7 7 0 0 1 18 6l2 6M4 12l2 6a7 7 0 0 0 12.5-3"/></>,
  stethoscope: <><path d="M6 3v5a4 4 0 0 0 8 0V3M4 3h4m4 0h4"/><path d="M10 12v2a4 4 0 0 0 8 0v-1"/><circle cx="18" cy="10" r="2"/><path d="M18 17v2a3 3 0 0 0 6 0v-3"/></>,
  heart: <path d="M20.8 8.7c0 5.4-8.8 11.3-8.8 11.3S3.2 14.1 3.2 8.7A4.7 4.7 0 0 1 12 6.1a4.7 4.7 0 0 1 8.8 2.6Z"/>,
  lungs: <><path d="M12 3v9"/><path d="M10 12c-2-4-4-5-5-2-1 3-3 7-2 9 2 3 6 1 8-2v-5"/><path d="M14 12c2-4 4-5 5-2 1 3 3 7 2 9-2 3-6 1-8-2v-5"/></>,
  brain: <><path d="M12 5a4 4 0 0 0-7.5 2A4 4 0 0 0 4 14a4 4 0 0 0 4 6h4Z"/><path d="M12 5a4 4 0 0 1 7.5 2 4 4 0 0 1 .5 7 4 4 0 0 1-4 6h-4Z"/><path d="M8 9h.01M16 9h.01M8 15h.01M16 15h.01"/></>,
  kidney: <><path d="M8 3c-4 0-6 4-5 9 1 4 4 6 7 4 2-1 2-4 1-6-.7-2 .7-7-3-7Z"/><path d="M16 3c4 0 6 4 5 9-1 4-4 6-7 4-2-1-2-4-1-6 .7-2-.7-7 3-7Z"/></>,
  droplet: <path d="M12 2.5S5 10 5 15a7 7 0 0 0 14 0c0-5-7-12.5-7-12.5Z"/>,
  baby: <><circle cx="12" cy="12" r="8"/><path d="M9 14s1 2 3 2 3-2 3-2M9 9h.01M15 9h.01M12 4V2"/></>,
  shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/></>,
  tooth: <path d="M12 4c-2-2-7-1-8 3-1 4 2 7 3 11 .5 2 1 4 2.5 4 2 0 1-5 2.5-5s.5 5 2.5 5c1.5 0 2-2 2.5-4 1-4 4-7 3-11-1-4-6-5-8-3Z"/>,
  activity: <path d="M3 12h4l2-6 4 12 3-8 2 2h3"/>,
  plus: <><path d="M12 5v14M5 12h14"/></>,
  close: <><path d="m18 6-12 12M6 6l12 12"/></>,
  save: <><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"/><path d="M17 21v-8H7v8M7 3v5h8"/></>,
  bookmark: <path d="M6 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18l-6-4-6 4Z"/>,
  clipboard: <><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4.5h6a1.5 1.5 0 0 0-3-1.5h-1.5A1.5 1.5 0 0 0 9 4.5ZM8 10h8M8 14h8"/></>,
  flask: <><path d="M9 3h6M10 3v7l-5 8a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-8V3"/><path d="M8 15h8"/></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></>,

image: <><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></>,
microscope: <><path d="M6 18h8"/><path d="M3 22h18"/><path d="M14 22a7 7 0 1 0 0-14h-1"/><path d="M9 14h2"/><path d="M9 12a2 2 0 0 1-2-2V6h6v4a2 2 0 0 1-2 2Z"/><path d="M12 6V3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3"/></>,
filePlus: <><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></>,
osce: <><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><path d="M9 14l2 2 4-4"/></>,
  play: <path d="m8 5 11 7-11 7V5Z"/>,
  target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
  fileSearch: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h8"/><path d="M14 2v6h6M8 13h5"/><circle cx="17" cy="17" r="3"/><path d="m19.2 19.2 2 2"/></>,
  trophy: <><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4Z"/><path d="M7 6H4v2a4 4 0 0 0 4 4M17 6h3v2a4 4 0 0 1-4 4"/></>,
  'graduation-cap': <><path d="m2 10 10-5 10 5-10 5-10-5Z"/><path d="M6 12v5c3 2.5 9 2.5 12 0v-5M22 10v6"/></>,
  'clipboard-list': <><rect x="5" y="4" width="14" height="18" rx="2"/><path d="M9 4V2h6v2M9 10h6M9 14h6M9 18h3"/></>,
  'bed-double': <><path d="M3 7v14M21 7v14M3 17h18M3 11h18v6H3Z"/><path d="M7 11V8h4v3m2 0V8h4v3"/></>,
  siren: <><path d="M5 18h14l-1.5-8a5.5 5.5 0 0 0-11 0L5 18Z"/><path d="M3 21h18M12 2V1M3.5 5 2 4m18.5 1L22 4"/></>,
  shuffle: <><path d="m18 14 4 4-4 4"/><path d="m18 2 4 4-4 4"/><path d="M2 18h2.5a5 5 0 0 0 4-2l7-10a5 5 0 0 1 4-2H22"/><path d="M2 6h2.5a5 5 0 0 1 4 2l7 10a5 5 0 0 0 4 2H22"/></>,
};

export function Icon({ name, size = 18, className = '', ...props }: { name: IconName; size?: number; className?: string } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
