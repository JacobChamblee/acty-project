// Cactus Insights — Design Tokens (mirrors Android app theme)
export const C = {
  // Brand blues
  blue:        '#1E40AF',  // CactusBlue
  blueMid:     '#3B82F6',  // CactusBlueMid
  blueLight:   '#60A5FA',  // lighter accent
  bluePale:    '#EFF6FF',  // CactusBluePale — card tints
  blueGlass:   'rgba(59,130,246,0.08)',

  // Backgrounds
  bgDeep:      '#F8FAFC',  // slate-50
  bgWhite:     '#FFFFFF',
  bgCard:      'rgba(255,255,255,0.90)',
  bgCardHover: 'rgba(255,255,255,0.97)',

  // Text
  textPrimary:   '#0F172A',  // slate-900
  textSecondary: '#475569',  // slate-600
  textDim:       '#94A3B8',  // slate-400

  // Status
  green:   '#10B981',
  greenPale: '#ECFDF5',
  amber:   '#F59E0B',
  amberPale: '#FFFBEB',
  red:     '#EF4444',
  redPale: '#FEF2F2',

  // Borders
  border:      '#E2E8F0',
  borderLight: '#F1F5F9',

  // Gradients
  heroGrad: 'linear-gradient(135deg, #EFF6FF 0%, #F8FAFC 50%, #F0FDF4 100%)',
  blueGrad: 'linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%)',
  cardGrad: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(239,246,255,0.70) 100%)',
};

export const shadow = {
  sm:   '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
  md:   '0 4px 16px rgba(30,64,175,0.07), 0 2px 6px rgba(0,0,0,0.05)',
  lg:   '0 8px 32px rgba(30,64,175,0.10), 0 2px 8px rgba(0,0,0,0.06)',
  xl:   '0 16px 48px rgba(30,64,175,0.14), 0 4px 12px rgba(0,0,0,0.07)',
  blue: '0 8px 24px rgba(59,130,246,0.25)',
};
