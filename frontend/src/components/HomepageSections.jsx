import { motion, animate, useInView } from 'framer-motion';
import { useRef, useEffect, useState } from 'react';
import {
  Activity, Fingerprint, Cpu, Wrench, Layers, BarChart3, Share2,
  ZapOff, Mic2, Database,
  Microscope, Users, FileAudio, GitBranch, ChevronRight,
  Waves, Bot, MapPin,
} from 'lucide-react';

// ── Easing ────────────────────────────────────────────────────────────
const EASE = [0.22, 1, 0.36, 1];

// ── Shared variants ───────────────────────────────────────────────────
const fadeUp = {
  hidden: { opacity: 0, y: 32 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } },
};
const fadeLeft = {
  hidden: { opacity: 0, x: -28 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.65, ease: EASE } },
};
const fadeRight = {
  hidden: { opacity: 0, x: 28 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.65, ease: EASE } },
};
const stagger = (delay = 0.1) => ({
  hidden: {},
  visible: { transition: { staggerChildren: delay, delayChildren: 0.05 } },
});

// ── AnimatedNumber — counts up when scrolled into view ────────────────
function AnimatedNumber({ raw }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });
  const [display, setDisplay] = useState('0');
  const num = parseFloat(String(raw).replace(/[^0-9.]/g, '')) || 0;
  const isText = isNaN(parseFloat(String(raw)));

  useEffect(() => {
    if (!inView || isText) return;
    const controls = animate(0, num, {
      duration: 1.4,
      ease: 'easeOut',
      onUpdate: (v) => setDisplay(
        num >= 100 ? Math.round(v).toLocaleString() : v.toFixed(0)
      ),
    });
    return () => controls.stop();
  }, [inView, num, isText]);

  if (isText) {
    return (
      <code style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: 500, color: 'var(--charcoal)', background: 'transparent' }}>
        {raw}
      </code>
    );
  }

  return (
    <span ref={ref}>
      <code style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: 500, color: 'var(--charcoal)', background: 'transparent' }}>
        {inView ? display : '0'}
      </code>
    </span>
  );
}

// ── GlowCard — hover lifts + sienna border glow ───────────────────────
function GlowCard({ children, style = {}, variants = fadeUp }) {
  return (
    <motion.div
      variants={variants}
      whileHover={{
        y: -5,
        boxShadow: '0 12px 40px rgba(226,112,58,0.13), 0 0 0 1.5px rgba(226,112,58,0.22)',
        transition: { duration: 0.2 },
      }}
      style={{
        background: '#ffffff',
        border: '0.5px solid rgba(26,26,26,0.1)',
        borderRadius: 12,
        padding: '1.25rem 1.35rem',
        cursor: 'default',
        ...style,
      }}
    >
      {children}
    </motion.div>
  );
}

// ── SectionLabel — animated uppercase heading with accent dot ─────────
function SectionLabel({ children }) {
  return (
    <motion.div
      variants={fadeLeft}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: '-80px' }}
      style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem' }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--sienna)', flexShrink: 0, display: 'inline-block' }} />
      <h2 style={{
        fontFamily: 'var(--font)',
        fontSize: '0.7rem',
        fontWeight: 600,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'rgba(26,26,26,0.5)',
        margin: 0,
      }}>
        {children}
      </h2>
    </motion.div>
  );
}

// ── HR divider ────────────────────────────────────────────────────────
function Divider() {
  return (
    <motion.hr
      initial={{ scaleX: 0, opacity: 0 }}
      whileInView={{ scaleX: 1, opacity: 1 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.8, ease: EASE }}
      style={{
        border: 'none',
        borderTop: '0.5px solid rgba(26,26,26,0.1)',
        margin: 0,
        transformOrigin: 'left',
      }}
    />
  );
}

// ── IconChip — a small icon in a rounded pill ─────────────────────────
function IconChip({ icon: Icon, color = 'var(--sienna)', bg = 'rgba(226,112,58,0.08)' }) {
  return (
    <div style={{
      width: 36, height: 36, borderRadius: 10,
      background: bg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexShrink: 0, marginBottom: '0.75rem',
    }}>
      <Icon size={18} color={color} strokeWidth={1.75} />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// RESEARCH CONTEXT
// ══════════════════════════════════════════════════════════════════════

// ── Animated spectrogram — before vs after noise removal ──────────────
function SpectrogramPreview() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });

  // "Noisy" columns — jagged + tall
  const noisyBars  = [28,14,36,20,42,18,38,24,44,12,40,26,34,16,30,22];
  // "Clean" columns — smooth, elephant harmonic shape
  const cleanBars  = [4, 6, 10,16,24,36,42,38,28,18,10, 6, 4, 3, 2, 2];
  const accent = (i) => i >= 4 && i <= 8;  // harmonic peak region

  return (
    <div ref={ref} style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
      {/* Noisy */}
      <div style={{ flex: 1 }}>
        <p style={{ fontSize: '0.62rem', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'rgba(26,26,26,0.4)', marginBottom: 8 }}>
          Raw recording
        </p>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 56, background: 'rgba(26,26,26,0.03)', borderRadius: 8, padding: '8px 10px' }}>
          {noisyBars.map((h, i) => (
            <motion.div
              key={i}
              initial={{ scaleY: 0 }}
              animate={inView ? { scaleY: 1 } : { scaleY: 0 }}
              transition={{ duration: 0.4, delay: 0.05 * i, ease: 'easeOut' }}
              style={{
                flex: 1, height: `${h}px`,
                background: 'rgba(226,112,58,0.35)',
                borderRadius: 2,
                transformOrigin: 'bottom',
              }}
            />
          ))}
        </div>
      </div>

      {/* Arrow */}
      <motion.div
        initial={{ opacity: 0, scale: 0 }}
        animate={inView ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0 }}
        transition={{ duration: 0.3, delay: 0.8 }}
        style={{ flexShrink: 0, color: 'var(--sienna)' }}
      >
        <ChevronRight size={20} strokeWidth={2} />
      </motion.div>

      {/* Clean */}
      <div style={{ flex: 1 }}>
        <p style={{ fontSize: '0.62rem', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'rgba(26,26,26,0.4)', marginBottom: 8 }}>
          After Tribal
        </p>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 56, background: 'rgba(26,26,26,0.03)', borderRadius: 8, padding: '8px 10px' }}>
          {cleanBars.map((h, i) => (
            <motion.div
              key={i}
              initial={{ scaleY: 0 }}
              animate={inView ? { scaleY: 1 } : { scaleY: 0 }}
              transition={{ duration: 0.5, delay: 0.9 + 0.05 * i, ease: 'easeOut' }}
              style={{
                flex: 1, height: `${h}px`,
                background: accent(i) ? 'var(--sienna)' : 'rgba(26,26,26,0.15)',
                borderRadius: 2,
                transformOrigin: 'bottom',
                boxShadow: accent(i) ? '0 0 6px rgba(226,112,58,0.4)' : 'none',
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ResearchSection() {
  const facts = [
    { label: 'Fundamental frequency', raw: '10–20 Hz', note: 'Below human hearing — only visible in spectrogram' },
    { label: 'Harmonic ceiling', raw: 'up to 1,000 Hz', note: 'Higher harmonics attenuate with distance' },
    { label: 'What you actually hear', raw: 'upper harmonics only', note: 'Lowest frequencies lost on standard speakers' },
  ];

  return (
    <section className="hp-section" id="hp-research">
      <Divider />
      <div className="hp-section-inner">
        {/* Prose column */}
        <motion.div
          className="hp-prose-col"
          variants={stagger()}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
        >
          <SectionLabel>Research context</SectionLabel>

          <motion.blockquote
            variants={fadeLeft}
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.05rem',
              fontStyle: 'italic',
              fontWeight: 400,
              lineHeight: 1.75,
              color: 'var(--charcoal)',
              borderLeft: '2px solid var(--sienna)',
              paddingLeft: '1.25rem',
              margin: '0 0 1.5rem',
            }}
          >
            <p>"When an elephant rumble overlaps in both time and frequency with noise sources, it becomes difficult or impossible to measure the acoustic properties of the call without influence from the noise source."</p>
            <footer style={{ fontFamily: 'var(--font)', fontSize: '0.78rem', fontStyle: 'normal', fontWeight: 500, color: 'rgba(26,26,26,0.5)', marginTop: '0.75rem' }}>
              — Dr. Mickey Pardo, ElephantVoices
            </footer>
          </motion.blockquote>

          {/* Spectrogram visual */}
          <motion.div
            variants={fadeUp}
            style={{
              background: '#fff',
              border: '0.5px solid rgba(26,26,26,0.1)',
              borderRadius: 12,
              padding: '1rem 1.15rem',
              marginBottom: '1rem',
            }}
          >
            <SpectrogramPreview />
          </motion.div>

          <motion.p variants={fadeUp} className="hp-body">
            ElephantVoices has been recording elephant calls since the 1980s. Decades of field work in Kenya and Mozambique have produced thousands of recordings — many partially or entirely unusable because mechanical noise overlaps the infrasound band.
          </motion.p>
        </motion.div>

        {/* Field site cards column */}
        <motion.div
          className="hp-cards-col"
          variants={stagger(0.12)}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              {
                label: 'Amboseli, Kenya',
                desc: "Long-term behavioral study — core of ElephantVoices' research archive.",
                color: 'rgba(122,158,126,0.12)',
                iconColor: '#4a7c59',
              },
              {
                label: 'Maasai Mara, Kenya',
                desc: 'Cross-population analysis — comparing call structure across social groups.',
                color: 'rgba(226,112,58,0.08)',
                iconColor: 'var(--sienna)',
              },
              {
                label: 'Gorongosa, Mozambique',
                desc: 'Post-conflict recovery — examining how trauma affects communication and social bonds.',
                color: 'rgba(59,130,246,0.07)',
                iconColor: '#3b82f6',
              },
            ].map((site) => (
              <GlowCard key={site.label} variants={fadeRight} style={{ background: site.color, border: '0.5px solid rgba(26,26,26,0.08)' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                  <MapPin size={16} color={site.iconColor} style={{ marginTop: 2, flexShrink: 0 }} strokeWidth={2} />
                  <div>
                    <span style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--charcoal)', marginBottom: '0.3rem' }}>
                      {site.label}
                    </span>
                    <p style={{ fontSize: '0.83rem', lineHeight: 1.6, color: 'rgba(26,26,26,0.6)', margin: 0 }}>
                      {site.desc}
                    </p>
                  </div>
                </div>
              </GlowCard>
            ))}

            {/* Stat strip within column */}
            <motion.div
              variants={fadeUp}
              style={{
                background: '#fff',
                border: '0.5px solid rgba(26,26,26,0.1)',
                borderRadius: 12,
                padding: '1rem 1.15rem',
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '0.5rem',
              }}
            >
              {facts.map((f, i) => (
                <div key={f.label} style={{
                  display: 'flex', flexDirection: 'column', gap: '0.2rem',
                  paddingRight: i < 2 ? '0.5rem' : 0,
                  borderRight: i < 2 ? '0.5px solid rgba(26,26,26,0.1)' : 'none',
                }}>
                  <span style={{ fontSize: '0.62rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'rgba(26,26,26,0.4)' }}>
                    {f.label}
                  </span>
                  <AnimatedNumber raw={f.raw} />
                </div>
              ))}
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ══════════════════════════════════════════════════════════════════════
// WHY IT'S HARD
// ══════════════════════════════════════════════════════════════════════
function WhySection() {
  const cards = [
    {
      title: 'Frequency overlap',
      body: 'Generator harmonics and airplane noise land directly in the 10–1,000 Hz band where elephant calls live. Simple high-pass filters remove the signal along with the noise.',
      icon: Waves,
      iconColor: '#3b82f6',
      iconBg: 'rgba(59,130,246,0.08)',
    },
    {
      title: 'No clean reference',
      body: "Field recordings rarely include a noise-only segment. Standard spectral subtraction requires one. NMF-based separation doesn't.",
      icon: ZapOff,
      iconColor: 'var(--sienna)',
      iconBg: 'rgba(226,112,58,0.08)',
    },
    {
      title: 'Simultaneous callers',
      body: 'Multiple elephants often rumble at the same time. Their calls overlap in frequency, making it hard to isolate individual F0 tracks without a second decomposition pass.',
      icon: Mic2,
      iconColor: '#7c3aed',
      iconBg: 'rgba(124,58,237,0.08)',
    },
    {
      title: 'Scale of the archive',
      body: 'Decades of recordings — too many to clean by hand. Any solution has to run unattended across hundreds of files and flag its own uncertainty.',
      icon: Database,
      iconColor: '#059669',
      iconBg: 'rgba(5,150,105,0.08)',
    },
  ];

  return (
    <section className="hp-section" id="hp-why">
      <Divider />
      <div className="hp-section-inner hp-section-inner--full">
        <SectionLabel>Why it&apos;s hard</SectionLabel>
        <motion.div
          variants={stagger(0.1)}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}
          className="hp-card-grid--4-override"
        >
          {cards.map((c) => (
            <GlowCard key={c.title}>
              <IconChip icon={c.icon} color={c.iconColor} bg={c.iconBg} />
              <h3 style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--charcoal)', marginBottom: '0.6rem' }}>{c.title}</h3>
              <p style={{ fontSize: '0.83rem', lineHeight: 1.7, color: 'rgba(26,26,26,0.65)', margin: 0 }}>{c.body}</p>
            </GlowCard>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

// ══════════════════════════════════════════════════════════════════════
// WHO IT'S FOR
// ══════════════════════════════════════════════════════════════════════
function WhoSection() {
  const cards = [
    {
      title: 'Field biologists',
      body: 'Drop a WAV file and get a cleaned version back with acoustic measurements. No signal processing expertise required.',
      icon: Microscope,
      iconColor: '#059669',
      iconBg: 'rgba(5,150,105,0.08)',
    },
    {
      title: 'Acoustic researchers',
      body: 'Access per-call F0 estimates, harmonic completeness scores, and SNR deltas. Cluster views surface recurring call patterns across the dataset.',
      icon: BarChart3,
      iconColor: '#3b82f6',
      iconBg: 'rgba(59,130,246,0.08)',
    },
    {
      title: 'Conservation teams',
      body: 'Behavioral hypotheses generated from the cluster structure give non-specialists a starting point for interpreting what the data might mean.',
      icon: Users,
      iconColor: 'var(--sienna)',
      iconBg: 'rgba(226,112,58,0.08)',
    },
  ];

  return (
    <section className="hp-section" id="hp-who">
      <Divider />
      <div className="hp-section-inner hp-section-inner--full">
        <SectionLabel>Who it&apos;s for</SectionLabel>
        <motion.div
          variants={stagger(0.12)}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}
        >
          {cards.map((c) => (
            <GlowCard key={c.title}>
              <IconChip icon={c.icon} color={c.iconColor} bg={c.iconBg} />
              <h3 style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--charcoal)', marginBottom: '0.6rem' }}>{c.title}</h3>
              <p style={{ fontSize: '0.83rem', lineHeight: 1.7, color: 'rgba(26,26,26,0.65)', margin: 0 }}>{c.body}</p>
            </GlowCard>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

// ══════════════════════════════════════════════════════════════════════
// WHAT YOU GET — bento-style grid
// ══════════════════════════════════════════════════════════════════════

// ── Simple SVG waveform illustration for the bento hero card ──────────
function WaveformIllustration() {
  const bars = [3, 7, 12, 18, 22, 28, 18, 14, 20, 26, 30, 22, 16, 10, 6, 4];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3, height: 40 }}>
      {bars.map((h, i) => (
        <motion.div
          key={i}
          initial={{ scaleY: 0 }}
          whileInView={{ scaleY: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4, delay: i * 0.04, ease: 'easeOut' }}
          style={{
            width: 6,
            height: `${h}px`,
            background: i === 10 || i === 11 ? 'var(--sienna)' : 'rgba(26,26,26,0.15)',
            borderRadius: 3,
            transformOrigin: 'bottom',
          }}
        />
      ))}
    </div>
  );
}

// ── Mini cluster scatter illustration ─────────────────────────────────
function ClusterIllustration() {
  const dots = [
    { x: 20, y: 30, c: 'var(--sienna)' }, { x: 28, y: 22, c: 'var(--sienna)' }, { x: 35, y: 28, c: 'var(--sienna)' },
    { x: 65, y: 20, c: '#3b82f6' }, { x: 72, y: 28, c: '#3b82f6' }, { x: 60, y: 30, c: '#3b82f6' },
    { x: 42, y: 55, c: '#059669' }, { x: 50, y: 60, c: '#059669' }, { x: 55, y: 52, c: '#059669' },
    { x: 80, y: 58, c: '#7c3aed' }, { x: 75, y: 65, c: '#7c3aed' },
  ];
  return (
    <svg viewBox="0 0 100 80" style={{ width: '100%', height: 56, display: 'block' }}>
      {dots.map((d, i) => (
        <motion.circle
          key={i}
          cx={d.x} cy={d.y} r={3.5}
          fill={d.c}
          fillOpacity={0.7}
          initial={{ scale: 0, opacity: 0 }}
          whileInView={{ scale: 1, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.35, delay: 0.1 * i, ease: 'backOut' }}
        />
      ))}
    </svg>
  );
}

function WhatSection() {
  const cards = [
    { title: 'Cleaned WAV files', body: 'Noise removed via NMF soft-mask. Original dynamic range preserved. Harmonic structure reconstructed where the noise obscured it.', large: true },
    {
      title: 'Separated callers',
      body: 'Dual-F0 detection identifies simultaneous calls. Each caller gets their own output track when two distinct fundamentals are found.',
      icon: Layers, iconColor: '#3b82f6', iconBg: 'rgba(59,130,246,0.08)',
    },
    {
      title: 'Behavioural clusters',
      body: 'UMAP + K-means groups calls by acoustic similarity. Each cluster gets a label, a summary, and a similarity graph across herds.',
      icon: GitBranch, iconColor: '#059669', iconBg: 'rgba(5,150,105,0.08)',
    },
    {
      title: 'AI hypotheses',
      body: 'Claude reads the cluster summaries and returns plain-language hypotheses about what each group of calls might represent behaviourally.',
      icon: Bot, iconColor: '#7c3aed', iconBg: 'rgba(124,58,237,0.08)',
    },
  ];

  return (
    <section className="hp-section" id="hp-what">
      <Divider />
      <div className="hp-section-inner hp-section-inner--full">
        <SectionLabel>What you get</SectionLabel>
        <motion.div
          variants={stagger(0.1)}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          style={{
            display: 'grid',
            gridTemplateColumns: '2fr 1fr 1fr',
            gridTemplateRows: 'auto auto',
            gap: 12,
          }}
        >
          {/* Large card — spans 2 rows */}
          <motion.div
            variants={fadeUp}
            whileHover={{
              y: -5,
              boxShadow: '0 12px 40px rgba(226,112,58,0.13), 0 0 0 1.5px rgba(226,112,58,0.22)',
              transition: { duration: 0.2 },
            }}
            style={{
              background: 'linear-gradient(145deg, #fff 55%, rgba(226,112,58,0.04) 100%)',
              border: '0.5px solid rgba(26,26,26,0.1)',
              borderRadius: 12,
              padding: '2rem 1.75rem',
              gridRow: '1 / 3',
              cursor: 'default',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'flex-end',
            }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.85 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.7, ease: EASE, delay: 0.1 }}
              style={{ marginBottom: '1.5rem' }}
            >
              <WaveformIllustration />
            </motion.div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem' }}>
              <FileAudio size={16} color="var(--sienna)" strokeWidth={2} />
              <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--charcoal)', margin: 0 }}>
                {cards[0].title}
              </h3>
            </div>
            <p style={{ fontSize: '0.85rem', lineHeight: 1.7, color: 'rgba(26,26,26,0.65)', margin: 0 }}>
              {cards[0].body}
            </p>
          </motion.div>

          {/* Cluster card with mini scatter */}
          <GlowCard key={cards[2].title}>
            <ClusterIllustration />
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.4rem' }}>
              <GitBranch size={14} color="#059669" strokeWidth={2} />
              <h3 style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--charcoal)', margin: 0 }}>{cards[2].title}</h3>
            </div>
            <p style={{ fontSize: '0.83rem', lineHeight: 1.7, color: 'rgba(26,26,26,0.65)', margin: 0 }}>{cards[2].body}</p>
          </GlowCard>

          {/* Regular cards */}
          {[cards[1], cards[3]].map((c) => (
            <GlowCard key={c.title}>
              <IconChip icon={c.icon} color={c.iconColor} bg={c.iconBg} />
              <h3 style={{ fontSize: '0.88rem', fontWeight: 500, color: 'var(--charcoal)', marginBottom: '0.6rem' }}>{c.title}</h3>
              <p style={{ fontSize: '0.83rem', lineHeight: 1.7, color: 'rgba(26,26,26,0.65)', margin: 0 }}>{c.body}</p>
            </GlowCard>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

// ══════════════════════════════════════════════════════════════════════
// PIPELINE — visual snake layout with animated beams
// ══════════════════════════════════════════════════════════════════════

const agentDefs = [
  { name: 'PreprocessAgent',    desc: 'Resample → bandpass 10–1000 Hz', icon: Activity,    highlight: false, num: 1, iconColor: '#059669', iconBg: 'rgba(5,150,105,0.1)' },
  { name: 'FingerprintAgent',   desc: 'Classify noise type',             icon: Fingerprint, highlight: false, num: 2, iconColor: '#7c3aed', iconBg: 'rgba(124,58,237,0.1)' },
  { name: 'NMFMaskingAgent',    desc: 'STFT → NMF n=10 → Wiener mask',  icon: Cpu,         highlight: true,  num: 3, badge: 'Core ML', iconColor: '#1E40AF', iconBg: 'rgba(59,130,246,0.12)' },
  { name: 'ReconstructionAgent',desc: 'Rebuild damaged harmonics',       icon: Wrench,      highlight: false, num: 4, iconColor: 'var(--sienna)', iconBg: 'rgba(226,112,58,0.1)' },
  { name: 'OverlapAgent',       desc: 'Dual-F0 separation',              icon: Layers,      highlight: false, num: 5, iconColor: '#0891b2', iconBg: 'rgba(8,145,178,0.1)' },
  { name: 'QualityScorerAgent', desc: 'SNR delta + validity flag',       icon: BarChart3,   highlight: false, num: 6, iconColor: '#dc2626', iconBg: 'rgba(220,38,38,0.08)' },
  { name: 'ClusteringAgent',    desc: 'UMAP + K-means → hypotheses',    icon: Share2,      highlight: false, num: 7, iconColor: '#4f46e5', iconBg: 'rgba(79,70,229,0.1)' },
];

// ── Traveling-dot horizontal beam ─────────────────────────────────────
function HBeam({ reverse = false, inView = false }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      height: '100%', width: '100%',
    }}>
      <div style={{
        width: '100%', height: 1.5,
        background: 'rgba(226,112,58,0.2)',
        borderRadius: 2, position: 'relative',
      }}>
        {inView && (
          <motion.div
            style={{
              position: 'absolute',
              width: 7, height: 7, borderRadius: '50%',
              background: 'var(--sienna)',
              top: -2.75,
              boxShadow: '0 0 6px rgba(226,112,58,0.8)',
            }}
            animate={{ left: reverse ? ['calc(100% - 4px)', '-3px'] : ['-3px', 'calc(100% - 4px)'] }}
            transition={{ duration: 1.1, repeat: Infinity, ease: 'easeInOut', repeatDelay: 0.5 }}
          />
        )}
      </div>
    </div>
  );
}

// ── Traveling-dot vertical beam ────────────────────────────────────────
function VBeam({ inView = false }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      width: '100%', height: '100%',
    }}>
      <div style={{
        width: 1.5, flex: 1,
        background: 'rgba(226,112,58,0.2)',
        borderRadius: 2, position: 'relative',
      }}>
        {inView && (
          <motion.div
            style={{
              position: 'absolute',
              width: 7, height: 7, borderRadius: '50%',
              background: 'var(--sienna)',
              left: -2.75,
              boxShadow: '0 0 6px rgba(226,112,58,0.8)',
            }}
            animate={{ top: ['-3px', 'calc(100% - 4px)'] }}
            transition={{ duration: 0.85, repeat: Infinity, ease: 'easeIn', repeatDelay: 0.7 }}
          />
        )}
      </div>
      {/* Arrowhead pointing down */}
      <div style={{
        width: 0, height: 0,
        borderLeft: '5px solid transparent',
        borderRight: '5px solid transparent',
        borderTop: '6px solid rgba(226,112,58,0.45)',
      }} />
    </div>
  );
}

// ── Single pipeline node card ─────────────────────────────────────────
function PipelineNode({ agent, delay = 0 }) {
  const Icon = agent.icon;
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.45, ease: EASE, delay }}
      whileHover={
        agent.highlight
          ? { y: -5, boxShadow: '0 12px 32px rgba(59,130,246,0.2), 0 0 0 1.5px rgba(59,130,246,0.4)', transition: { duration: 0.2 } }
          : { y: -5, boxShadow: '0 12px 32px rgba(226,112,58,0.12), 0 0 0 1.5px rgba(226,112,58,0.25)', transition: { duration: 0.2 } }
      }
      style={{
        display: 'flex', flexDirection: 'column', gap: '0.35rem',
        background: agent.highlight ? '#EBF5FF' : '#ffffff',
        border: agent.highlight ? '1px solid #93C5FD' : '0.5px solid rgba(26,26,26,0.1)',
        borderRadius: 12,
        padding: '1rem 1.1rem',
        cursor: 'default',
        position: 'relative',
        height: '100%',
        boxSizing: 'border-box',
      }}
    >
      {/* Step number badge */}
      <div style={{
        position: 'absolute', top: 10, right: 10,
        width: 20, height: 20, borderRadius: '50%',
        background: agent.highlight ? 'rgba(30,64,175,0.12)' : 'rgba(26,26,26,0.06)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '0.6rem', fontWeight: 700,
        color: agent.highlight ? '#1E40AF' : 'rgba(26,26,26,0.4)',
        fontFamily: 'var(--font-mono)',
      }}>
        {agent.num}
      </div>

      {/* Icon chip */}
      <div style={{
        width: 30, height: 30, borderRadius: 8,
        background: agent.iconBg,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: '0.1rem',
      }}>
        <Icon size={15} color={agent.iconColor} strokeWidth={2} />
      </div>

      {agent.badge && (
        <span style={{
          fontSize: '0.58rem', fontWeight: 700,
          letterSpacing: '0.1em', textTransform: 'uppercase',
          color: '#1E40AF', background: 'rgba(30,64,175,0.1)',
          borderRadius: 4, padding: '0.1rem 0.4rem',
          alignSelf: 'flex-start',
        }}>
          {agent.badge}
        </span>
      )}

      <span style={{
        fontFamily: 'var(--font-mono)', fontSize: '0.7rem', fontWeight: 600,
        color: agent.highlight ? '#1E40AF' : 'var(--charcoal)', lineHeight: 1.3,
      }}>
        {agent.name}
      </span>
      <span style={{
        fontSize: '0.68rem', lineHeight: 1.5,
        color: agent.highlight ? 'rgba(30,64,175,0.65)' : 'rgba(26,26,26,0.5)',
      }}>
        {agent.desc}
      </span>
    </motion.div>
  );
}

// ── Snake pipeline layout using explicit CSS grid ─────────────────────
// Grid columns: [a1][gap][a2][gap][a3][gap][a4]   (7 cols)
// Grid rows:    [row1-nodes][vbeam][row2-nodes]     (3 rows)
// Row 1: agents 1→4 (left to right), beams between
// Row 2: only the VBeam cell in col 7
// Row 3: agents 7←6←5 (right-to-left snake back), beams between
//         empty cells in cols 1-2

function PipelineSection() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  // col indices (1-based)
  // Agent columns:  1, 3, 5, 7
  // Beam columns:   2, 4, 6
  const COL = { a1: 1, b12: 2, a2: 3, b23: 4, a3: 5, b34: 6, a4: 7 };
  const COLS = '1fr 28px 1fr 28px 1fr 28px 1fr';
  const ROWS = 'auto 48px auto';

  return (
    <section className="hp-section" id="hp-pipeline" ref={ref}>
      <Divider />
      <div className="hp-section-inner hp-section-inner--full">
        <SectionLabel>Pipeline</SectionLabel>

        <div style={{ display: 'grid', gridTemplateColumns: COLS, gridTemplateRows: ROWS, gap: '8px 0', alignItems: 'stretch' }}>

          {/* ── Row 1: agents 1–4 left→right ── */}
          <div style={{ gridColumn: 1, gridRow: 1 }}><PipelineNode agent={agentDefs[0]} delay={0} /></div>
          <div style={{ gridColumn: 2, gridRow: 1, display: 'flex', alignItems: 'center', padding: '0 4px' }}><HBeam inView={inView} /></div>
          <div style={{ gridColumn: 3, gridRow: 1 }}><PipelineNode agent={agentDefs[1]} delay={0.08} /></div>
          <div style={{ gridColumn: 4, gridRow: 1, display: 'flex', alignItems: 'center', padding: '0 4px' }}><HBeam inView={inView} /></div>
          <div style={{ gridColumn: 5, gridRow: 1 }}><PipelineNode agent={agentDefs[2]} delay={0.16} /></div>
          <div style={{ gridColumn: 6, gridRow: 1, display: 'flex', alignItems: 'center', padding: '0 4px' }}><HBeam inView={inView} /></div>
          <div style={{ gridColumn: 7, gridRow: 1 }}><PipelineNode agent={agentDefs[3]} delay={0.24} /></div>

          {/* ── Row 2: vertical beam drops from agent 4 (col 7) ── */}
          <div style={{ gridColumn: 7, gridRow: 2, display: 'flex', justifyContent: 'center', padding: '2px 0' }}><VBeam inView={inView} /></div>

          {/* ── Row 3: agents 5←6←7 right→left snake ── */}
          {/* Col 7: Agent 5 (receives the down-beam from agent 4) */}
          <div style={{ gridColumn: 7, gridRow: 3 }}><PipelineNode agent={agentDefs[4]} delay={0.32} /></div>
          {/* Col 6: beam going left (reverse) */}
          <div style={{ gridColumn: 6, gridRow: 3, display: 'flex', alignItems: 'center', padding: '0 4px' }}><HBeam reverse inView={inView} /></div>
          {/* Col 5: Agent 6 */}
          <div style={{ gridColumn: 5, gridRow: 3 }}><PipelineNode agent={agentDefs[5]} delay={0.4} /></div>
          {/* Col 4: beam going left (reverse) */}
          <div style={{ gridColumn: 4, gridRow: 3, display: 'flex', alignItems: 'center', padding: '0 4px' }}><HBeam reverse inView={inView} /></div>
          {/* Col 3: Agent 7 */}
          <div style={{ gridColumn: 3, gridRow: 3 }}><PipelineNode agent={agentDefs[6]} delay={0.48} /></div>
          {/* Cols 1-2 intentionally empty — snake only covers 3 agents */}
        </div>

        {/* Flow legend */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.6 }}
          style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            marginTop: '1rem',
            paddingTop: '0.75rem',
            borderTop: '0.5px solid rgba(26,26,26,0.08)',
          }}
        >
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--sienna)' }} />
          <span style={{ fontSize: '0.68rem', color: 'rgba(26,26,26,0.45)' }}>
            Animated dots show live data flowing through the pipeline
          </span>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: 'rgba(26,26,26,0.35)' }}>
            7 agents · sequential mode
          </span>
        </motion.div>
      </div>
    </section>
  );
}

// ══════════════════════════════════════════════════════════════════════
// FOOTER
// ══════════════════════════════════════════════════════════════════════
function Footer() {
  return (
    <footer className="hp-footer">
      <Divider />
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-40px' }}
        transition={{ duration: 0.5, ease: EASE }}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '1.25rem 2rem',
          maxWidth: 1200,
          margin: '0 auto',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <p style={{ fontSize: '0.78rem', color: 'rgba(26,26,26,0.5)', margin: 0 }}>
          © 2026 Tribal. All rights reserved.
        </p>
        <p style={{ fontSize: '0.78rem', color: 'rgba(26,26,26,0.5)', margin: 0 }}>
          Built at <strong style={{ color: 'rgba(26,26,26,0.75)', fontWeight: 500 }}>HackSMU</strong>
          {' · '}in partnership with <strong style={{ color: 'rgba(26,26,26,0.75)', fontWeight: 500 }}>ElephantVoices</strong>
        </p>
      </motion.div>
    </footer>
  );
}

// ══════════════════════════════════════════════════════════════════════
// HOW IT WORKS — first thing you see on scroll; dead simple 3 steps
// ══════════════════════════════════════════════════════════════════════
function HowItWorksSection() {
  const steps = [
    {
      num: '01',
      title: 'Upload a noisy recording',
      body: 'Drop a .wav file — field recordings with airplane, car, or generator noise overlapping the elephant calls.',
      icon: FileAudio,
      iconColor: 'var(--sienna)',
      iconBg: 'rgba(226,112,58,0.1)',
    },
    {
      num: '02',
      title: '7 AI agents strip the noise',
      body: 'A pipeline detects the noise type, runs NMF decomposition, reconstructs missing harmonics, and separates simultaneous callers.',
      icon: Cpu,
      iconColor: '#1E40AF',
      iconBg: 'rgba(59,130,246,0.1)',
    },
    {
      num: '03',
      title: 'Get clean audio + insights',
      body: 'Download de-noised WAVs, explore call clusters by acoustic similarity, and read AI-generated hypotheses about elephant behaviour.',
      icon: Share2,
      iconColor: '#059669',
      iconBg: 'rgba(5,150,105,0.1)',
    },
  ];

  return (
    <section className="hp-section" id="hp-how" style={{ paddingTop: '2.5rem' }}>
      <div className="hp-section-inner hp-section-inner--full" style={{ paddingBottom: 0 }}>
      {/* Top strip — one-sentence summary */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ duration: 0.5, ease: EASE }}
        style={{
          background: 'var(--charcoal)',
          borderRadius: 14,
          padding: '1.1rem 1.75rem',
          marginBottom: 0,
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.65rem',
          fontWeight: 700,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: 'var(--sienna)',
          flexShrink: 0,
        }}>
          Tribal
        </span>
        <span style={{
          fontSize: '0.92rem',
          fontWeight: 500,
          color: '#FAF0E6',
          lineHeight: 1.5,
        }}>
          Removes mechanical noise from elephant infrasound recordings and surfaces communication patterns across herds — automatically.
        </span>
      </motion.div>
      </div>

      {/* 3 steps */}
      <div className="hp-section-inner hp-section-inner--full">
        <motion.div
          variants={stagger(0.12)}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-60px' }}
          style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}
        >
          {steps.map((s, i) => (
            <motion.div
              key={s.num}
              variants={fadeUp}
              whileHover={{ y: -4, boxShadow: '0 10px 32px rgba(226,112,58,0.1)', transition: { duration: 0.18 } }}
              style={{
                background: '#ffffff',
                border: '0.5px solid rgba(26,26,26,0.1)',
                borderRadius: 14,
                padding: '1.4rem 1.35rem 1.25rem',
                cursor: 'default',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              {/* Step number — large background watermark */}
              <span style={{
                position: 'absolute',
                top: 10, right: 14,
                fontFamily: 'var(--font-display)',
                fontSize: '4.5rem',
                fontWeight: 700,
                lineHeight: 1,
                color: 'rgba(26,26,26,0.04)',
                userSelect: 'none',
              }}>
                {s.num}
              </span>

              {/* Icon */}
              <div style={{
                width: 38, height: 38, borderRadius: 10,
                background: s.iconBg,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: '0.9rem',
              }}>
                <s.icon size={18} color={s.iconColor} strokeWidth={1.75} />
              </div>

              {/* Step pill */}
              <span style={{
                display: 'inline-block',
                fontSize: '0.58rem', fontWeight: 700,
                letterSpacing: '0.1em', textTransform: 'uppercase',
                color: 'rgba(26,26,26,0.4)',
                marginBottom: '0.45rem',
              }}>
                Step {s.num}
              </span>

              <h3 style={{
                fontSize: '0.95rem', fontWeight: 700,
                color: 'var(--charcoal)',
                marginBottom: '0.55rem',
                lineHeight: 1.35,
              }}>
                {s.title}
              </h3>
              <p style={{
                fontSize: '0.82rem', lineHeight: 1.7,
                color: 'rgba(26,26,26,0.6)', margin: 0,
              }}>
                {s.body}
              </p>

              {/* Connector arrow — not on last card */}
              {i < steps.length - 1 && (
                <div style={{
                  position: 'absolute',
                  right: -14, top: '50%',
                  transform: 'translateY(-50%)',
                  zIndex: 2,
                  width: 28, height: 28,
                  background: 'var(--linen)',
                  border: '0.5px solid rgba(26,26,26,0.1)',
                  borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <ChevronRight size={13} color="var(--sienna)" strokeWidth={2.5} />
                </div>
              )}
            </motion.div>
          ))}
        </motion.div>

        {/* Quick-stat row */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-40px' }}
          transition={{ duration: 0.45, ease: EASE, delay: 0.35 }}
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 0,
            marginTop: 12,
            background: '#fff',
            border: '0.5px solid rgba(26,26,26,0.1)',
            borderRadius: 12,
            overflow: 'hidden',
          }}
        >
          {[
            { value: '44', label: 'WAV recordings' },
            { value: '212', label: 'documented calls' },
            { value: '7', label: 'pipeline agents' },
            { value: '10–20 Hz', label: 'infrasound band' },
          ].map((stat, i, arr) => (
            <div key={stat.label} style={{
              padding: '0.9rem 1.1rem',
              borderRight: i < arr.length - 1 ? '0.5px solid rgba(26,26,26,0.08)' : 'none',
            }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '1.25rem', fontWeight: 700,
                color: 'var(--charcoal)',
                marginBottom: '0.2rem',
              }}>
                {stat.value}
              </div>
              <div style={{
                fontSize: '0.68rem', fontWeight: 500,
                letterSpacing: '0.06em', textTransform: 'uppercase',
                color: 'rgba(26,26,26,0.45)',
              }}>
                {stat.label}
              </div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

// ══════════════════════════════════════════════════════════════════════
// ROOT
// ══════════════════════════════════════════════════════════════════════
export default function HomepageSections() {
  return (
    <div id="homepage-sections" style={{ background: '#FAF0E6', color: 'var(--charcoal)', width: '100%' }}>
      <HowItWorksSection />
      <Divider />
      <WhatSection />
      <PipelineSection />
      <WhySection />
      <WhoSection />
      <ResearchSection />
      <Footer />
    </div>
  );
}
