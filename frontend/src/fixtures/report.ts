import type { DeliveryMetrics, ReportOut } from "@/api/schemas";
import { findings } from "@/fixtures/findings";

const delivery: DeliveryMetrics = {
  words_per_minute: 168,
  filler_words: { ну: 9, короче: 4, "как бы": 3 },
  long_pauses: [42.5, 118.2],
};

/** With a Запись питча attached: DELIVERY + SPEECH_MISMATCH findings + Подача. */
export const reportWithAudio: ReportOut = {
  review_id: "a0000000-0000-0000-0000-000000000001",
  score: 61,
  n_slides: 8,
  findings,
  delivery,
  auto_fixed_count: findings.filter((f) => f.auto_fixed).length,
  pdf_asset_id: "b0000000-0000-0000-0000-000000000001",
  fixed_pptx_asset_id: "b0000000-0000-0000-0000-000000000002",
};

/** No Запись питча: no DELIVERY/SPEECH_MISMATCH findings, no Подача block. */
export const reportNoAudio: ReportOut = {
  ...reportWithAudio,
  review_id: "a0000000-0000-0000-0000-000000000002",
  findings: findings.filter((f) => f.category !== "DELIVERY" && f.category !== "SPEECH_MISMATCH"),
  delivery: null,
};

/** Clean deck: zero Находок. */
export const reportEmpty: ReportOut = {
  review_id: "a0000000-0000-0000-0000-000000000003",
  score: 100,
  n_slides: 6,
  findings: [],
  delivery: null,
  auto_fixed_count: 0,
  pdf_asset_id: null,
  fixed_pptx_asset_id: null,
};
