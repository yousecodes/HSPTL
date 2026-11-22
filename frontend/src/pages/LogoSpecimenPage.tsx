import { HsptlMark, HsptlLockup } from '../components/HsptlMark';

type Props = {
  theme: 'light' | 'dark';
  onThemeToggle: () => void;
  onBack: () => void;
};

/**
 * Logo specimen page. Reachable at `#logo-specimen`; it is a development
 * surface, not a learner destination, so it is deliberately not in the
 * navigation registry.
 *
 * It renders the mark at true pixel sizes (16px and 32px) on light and dark
 * backgrounds in both monochrome treatments, plus enlarged samples. The
 * honest 16px limitation is stated rather than glossed over.
 */

const SIZES = [16, 32] as const;

function Swatch({
  title,
  background,
  children,
  note,
}: {
  title: string;
  background: string;
  children: React.ReactNode;
  note?: string;
}) {
  return (
    <div className="spec-swatch">
      <h3>{title}</h3>
      <div className="spec-surface" style={{ background }}>
        {children}
      </div>
      {note && <p className="spec-note">{note}</p>}
    </div>
  );
}

function Row({ tone, label }: { tone: 'brand' | 'mono-dark' | 'mono-light'; label: string }) {
  return (
    <div className="spec-row">
      <span className="spec-row-label">{label}</span>
      <div className="spec-sizes">
        {SIZES.map((size) => (
          <div className="spec-cell" key={size}>
            <HsptlMark size={size} tone={tone} variant="primary" />
            <span>{size}px</span>
          </div>
        ))}
        <div className="spec-cell">
          <HsptlMark size={16} tone={tone} variant="compact" />
          <span>16px compact</span>
        </div>
        <div className="spec-cell">
          <HsptlMark size={32} tone={tone} variant="compact" />
          <span>32px compact</span>
        </div>
      </div>
    </div>
  );
}

export default function LogoSpecimenPage({ theme, onThemeToggle, onBack }: Props) {
  return (
    <div className="spec-page">
      <header className="spec-head">
        <div>
          <div className="s-eyebrow">Brand verification</div>
          <h1>HSPTL Case Mosaic identity</h1>
          <p>
            True pixel sizes, not scaled previews. The Case Mosaic mark is tested at actual icon sizes.
          </p>
        </div>
        <div className="s-toolbar">
          <button type="button" className="s-btn s-btn-secondary" onClick={onThemeToggle}>
            Theme: {theme}
          </button>
          <button type="button" className="s-btn s-btn-primary" onClick={onBack}>
            Back to app
          </button>
        </div>
      </header>

      <section className="spec-section">
        <h2>Light background</h2>
        <Swatch title="Primary mark" background="#FFFFFF">
          <Row tone="brand" label="Brand plate" />
        </Swatch>
        <Swatch title="Monochrome dark" background="#FFFFFF">
          <Row tone="mono-dark" label="One-colour black" />
        </Swatch>
      </section>

      <section className="spec-section">
        <h2>Dark background</h2>
        <Swatch title="Primary mark" background="#172B40">
          <Row tone="brand" label="Brand plate" />
        </Swatch>
        <Swatch title="Monochrome light" background="#172B40">
          <Row tone="mono-light" label="One-colour white" />
        </Swatch>
      </section>

      <section className="spec-section">
        <h2>Enlarged samples</h2>
        <div className="spec-enlarged">
          {([64, 128, 192] as const).map((size) => (
            <div className="spec-cell" key={size}>
              <HsptlMark size={size} />
              <span>{size}px</span>
            </div>
          ))}
          <div className="spec-cell">
            <HsptlMark size={128} tone="mono-dark" />
            <span>128px mono</span>
          </div>
        </div>
      </section>

      <section className="spec-section">
        <h2>Horizontal lockup</h2>
        <div className="spec-lockups">
          <HsptlLockup size={40} />
          <span className="spec-lockup-dark">
            <HsptlLockup size={40} tone="mono-light" />
          </span>
        </div>
      </section>

      <section className="spec-section spec-limits">
        <h2>Small-size legibility</h2>
        <p>
          The Case Mosaic symbol brings four case tiles together around a central insight spark. Its palette combines deep navy, discovery blue, teal, community green and amber.
        </p>
        <p>
          At <b>16px</b>, check that the four case tiles and central insight spark remain distinct on both light and dark backgrounds. Use the compact asset only where the full mark loses clarity.
        </p>
        <p className="spec-note">
          Verify with a rasteriser at exact pixel sizes before shipping. Do not rely on a
          browser-scaled preview, which anti-aliases differently.
        </p>
      </section>
    </div>
  );
}
