/** Заглушечные превью слайдов для фикстуры Отчёта на лендинге и в сторибуке компонентов. */

function svgToDataUrl(svg: string): string {
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

const FONT = "font-family='Arial, Helvetica, sans-serif'";

/** Слайд 1 — титульный: крупный подзаголовок набран мельче заголовка (см. TYPOGRAPHY finding). */
const slide1 = svgToDataUrl(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">
  <rect width="960" height="540" fill="#0f172a"/>
  <rect x="70" y="60" width="360" height="14" rx="7" fill="#38bdf8"/>
  <text x="70" y="150" ${FONT} font-size="18" fill="#e2e8f0">Orbit — платформа для стартапов</text>
  <text x="70" y="200" ${FONT} font-size="24" font-weight="700" fill="#f8fafc">Раунд A: рост ×3 за 12 месяцев</text>
  <rect x="70" y="420" width="180" height="40" rx="6" fill="#38bdf8"/>
  <text x="105" y="445" ${FONT} font-size="14" fill="#0f172a">Инвесторам</text>
</svg>
`);

/** Слайд 2 — фото-фон со светлым участком, поверх белый нечитаемый текст (READABILITY finding). */
const slide2 = svgToDataUrl(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">
  <defs>
    <linearGradient id="photo" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#475569"/>
      <stop offset="45%" stop-color="#cbd5e1"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
  </defs>
  <rect width="960" height="540" fill="url(#photo)"/>
  <text x="60" y="70" ${FONT} font-size="22" font-weight="700" fill="#f8fafc">Проблема</text>
  <text x="120" y="330" ${FONT} font-size="20" fill="#ffffff">87% команд теряют питч на этом слайде</text>
</svg>
`);

/** Слайд 3 — ключевая метрика набрана тем же кеглем, что остальной текст (HIERARCHY finding). */
const slide3 = svgToDataUrl(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">
  <rect width="960" height="540" fill="#ffffff"/>
  <text x="60" y="70" ${FONT} font-size="22" font-weight="700" fill="#0f172a">Решение</text>
  <text x="60" y="140" ${FONT} font-size="16" fill="#334155">Автоматический Разбор Деки за 5 минут вместо найма дизайнера</text>
  <text x="560" y="260" ${FONT} font-size="18" fill="#334155">Рост конверсии инвесторов</text>
  <text x="560" y="300" ${FONT} font-size="18" fill="#334155">×3 роста</text>
</svg>
`);

/** Слайд 4 — обрезанная ось Y визуально преувеличивает рост выручки (CHART finding). */
const slide4 = svgToDataUrl(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">
  <rect width="960" height="540" fill="#ffffff"/>
  <text x="60" y="60" ${FONT} font-size="22" font-weight="700" fill="#0f172a">Выручка, млн ₽</text>
  <line x1="120" y1="470" x2="120" y2="120" stroke="#94a3b8" stroke-width="2"/>
  <line x1="120" y1="470" x2="860" y2="470" stroke="#94a3b8" stroke-width="2"/>
  <text x="90" y="470" ${FONT} font-size="12" fill="#64748b" text-anchor="end">80</text>
  <text x="90" y="120" ${FONT} font-size="12" fill="#64748b" text-anchor="end">100</text>
  <rect x="220" y="380" width="120" height="90" fill="#38bdf8"/>
  <rect x="440" y="260" width="120" height="210" fill="#38bdf8"/>
  <rect x="660" y="120" width="120" height="350" fill="#0ea5e9"/>
  <text x="280" y="500" ${FONT} font-size="14" fill="#334155" text-anchor="middle">Q1</text>
  <text x="500" y="500" ${FONT} font-size="14" fill="#334155" text-anchor="middle">Q2</text>
  <text x="720" y="500" ${FONT} font-size="14" fill="#334155" text-anchor="middle">Q3</text>
</svg>
`);

/** Слайд 5 — доли круговой диаграммы не суммируются в 100% (CHART finding). */
const slide5 = svgToDataUrl(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">
  <rect width="960" height="540" fill="#ffffff"/>
  <text x="60" y="60" ${FONT} font-size="22" font-weight="700" fill="#0f172a">Доли рынка</text>
  <circle cx="480" cy="300" r="150" fill="#e2e8f0"/>
  <path d="M480 300 L480 150 A150 150 0 0 1 610 375 Z" fill="#0ea5e9"/>
  <path d="M480 300 L610 375 A150 150 0 0 1 400 440 Z" fill="#38bdf8"/>
  <path d="M480 300 L400 440 A150 150 0 0 1 480 150 Z" fill="#7dd3fc"/>
  <text x="480" y="470" ${FONT} font-size="14" fill="#334155" text-anchor="middle">35% + 30% + 27% = 92%</text>
</svg>
`);

/** Слайд 6 — слайд показывает рост доли, хотя спикер говорит о потере доли (SPEECH_MISMATCH finding). */
const slide6 = svgToDataUrl(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">
  <rect width="960" height="540" fill="#ffffff"/>
  <text x="60" y="60" ${FONT} font-size="22" font-weight="700" fill="#0f172a">Динамика доли рынка</text>
  <polyline points="120,400 300,360 480,320 660,240 840,160" fill="none" stroke="#22c55e" stroke-width="4"/>
  <circle cx="840" cy="160" r="6" fill="#22c55e"/>
  <text x="780" y="140" ${FONT} font-size="16" fill="#16a34a">+12%</text>
</svg>
`);

/** Слайд 7 — типографика: мелкая сноска источника данных (TYPOGRAPHY finding). */
const slide7 = svgToDataUrl(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">
  <rect width="960" height="540" fill="#ffffff"/>
  <text x="60" y="60" ${FONT} font-size="22" font-weight="700" fill="#0f172a">Команда</text>
  <circle cx="140" cy="220" r="40" fill="#cbd5e1"/>
  <circle cx="300" cy="220" r="40" fill="#cbd5e1"/>
  <circle cx="460" cy="220" r="40" fill="#cbd5e1"/>
  <text x="60" y="500" ${FONT} font-size="9" fill="#94a3b8">Источник: внутренняя аналитика, 2026</text>
</svg>
`);

export const SLIDE_IMAGES: Record<number, string> = {
  1: slide1,
  2: slide2,
  3: slide3,
  4: slide4,
  5: slide5,
  6: slide6,
  7: slide7,
};
