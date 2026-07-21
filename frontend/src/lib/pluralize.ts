/** Russian plural-form index: 0 = one (1, 21…), 1 = few (2–4, 22–24…), 2 = many (0, 5–20…). */
function ruPluralIndex(n: number): 0 | 1 | 2 {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return 0;
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return 1;
  return 2;
}

/** Picks the matching Russian plural form: pluralizeRu(21, ["слайд", "слайда", "слайдов"]) → "слайд". */
export function pluralizeRu(n: number, forms: [one: string, few: string, many: string]): string {
  return forms[ruPluralIndex(n)];
}
