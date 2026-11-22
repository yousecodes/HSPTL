import type { ImgHTMLAttributes } from 'react';

export type HsptlMarkVariant = 'primary' | 'compact';
export type HsptlMarkTone = 'brand' | 'mono-dark' | 'mono-light';

type Props = {
  variant?: HsptlMarkVariant;
  tone?: HsptlMarkTone;
  size?: number;
  title?: string | null;
  className?: string;
} & Omit<ImgHTMLAttributes<HTMLImageElement>, 'title' | 'src' | 'alt' | 'width' | 'height'>;

export function HsptlMark({
  variant = 'primary',
  tone = 'brand',
  size = 32,
  title = 'HSPTL Case Mosaic',
  className = '',
  ...props
}: Props) {
  const source = tone === 'mono-light'
    ? '/brand/hsptl-case-mosaic-mono-light.svg'
    : tone === 'mono-dark'
      ? '/brand/hsptl-case-mosaic-mono-dark.svg'
      : '/brand/hsptl-case-mosaic-mark.svg';

  const labelled = title !== null;

  return (
    <img
      src={source}
      width={size}
      height={size}
      alt={labelled ? title : ''}
      aria-hidden={labelled ? undefined : true}
      data-variant={variant}
      className={className}
      draggable={false}
      {...props}
    />
  );
}

export function HsptlLockup({
  tone = 'brand',
  size = 32,
  className = '',
}: {
  tone?: HsptlMarkTone;
  size?: number;
  className?: string;
}) {
  const color = tone === 'mono-light' ? '#FFFFFF' : '#183858';

  return (
    <span
      className={`hsptl-lockup ${className}`}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 9, color }}
    >
      <HsptlMark tone={tone} size={size} title={null} />
      <span style={{ display: 'grid', gap: 2 }}>
        <b style={{ fontSize: size * 0.48, letterSpacing: '0.13em', lineHeight: 1, fontWeight: 850 }}>
          HSPTL
        </b>
        <small style={{ fontSize: Math.max(9, size * 0.23), letterSpacing: '0.12em', fontWeight: 800, opacity: 0.72 }}>
          Dx, Ix, Tx
        </small>
      </span>
    </span>
  );
}