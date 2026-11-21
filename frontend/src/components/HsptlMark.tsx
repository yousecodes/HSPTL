import type { ImgHTMLAttributes } from 'react';

/** Reference-derived geometric HSPTL monogram used consistently across the app. */
export type HsptlMarkVariant = 'primary' | 'compact';
export type HsptlMarkTone = 'brand' | 'mono-dark' | 'mono-light';
type Props = {
  variant?: HsptlMarkVariant;
  tone?: HsptlMarkTone;
  size?: number;
  title?: string | null;
  className?: string;
} & Omit<ImgHTMLAttributes<HTMLImageElement>, 'title' | 'src' | 'alt' | 'width' | 'height'>;

export function HsptlMark({ variant = 'primary', tone = 'brand', size = 32, title = 'HSPTL', className = '', ...props }: Props) {
  const source = tone === 'mono-light'
    ? '/brand/hsptl-mark-mono-light.svg'
    : tone === 'mono-dark'
      ? '/brand/hsptl-mark-mono-dark.svg'
      : '/brand/hsptl-mark-brand.svg';
  const labelled = title !== null;
  return <img
    src={source}
    width={size}
    height={Math.round(size * 614 / 485)}
    alt={labelled ? title : ''}
    aria-hidden={labelled ? undefined : true}
    data-variant={variant}
    className={className}
    draggable={false}
    {...props}
  />;
}

export function HsptlLockup({
  tone = 'brand', size = 32, className = '',
}: { tone?: HsptlMarkTone; size?: number; className?: string }) {
  const color = tone === 'mono-light' ? '#FFFFFF' : tone === 'mono-dark' ? '#111827' : '#142F40';
  return (
    <span className={`hsptl-lockup ${className}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 9, color }}>
      <HsptlMark tone={tone} size={size * 0.78} title={null}/>
      <span style={{ display: 'grid', gap: 2 }}>
        <b style={{ fontSize: size * 0.48, letterSpacing: '0.13em', lineHeight: 1, fontWeight: 850 }}>HSPTL</b>
        <small style={{ fontSize: Math.max(9, size * 0.23), letterSpacing: '0.12em', fontWeight: 800, opacity: 0.72 }}>CLINICAL LEARNING</small>
      </span>
    </span>
  );
}
