"""Domain constants shared across analyzers (no I/O, no logic)."""

from __future__ import annotations

from enum import StrEnum

RU_FILLER_WORDS: frozenset[str] = frozenset(
    {
        "э",
        "ээ",
        "эээ",
        "эм",
        "эмм",
        "мм",
        "ммм",
        "ну",
        "ну вот",
        "как бы",
        "типа",
        "короче",
        "в общем",
        "в принципе",
        "вот",
        "и вот",
        "значит",
        "собственно",
        "скажем так",
        "так сказать",
        "как сказать",
        "это самое",
        "получается",
        "как его",
        "как её",
        "блин",
        "да уж",
    }
)

EN_FILLER_WORDS: frozenset[str] = frozenset(
    {
        "uh",
        "um",
        "uhm",
        "er",
        "erm",
        "ah",
        "eh",
        "like",
        "you know",
        "i mean",
        "kind of",
        "sort of",
        "basically",
        "actually",
        "literally",
        "right",
        "well",
        "so yeah",
        "you see",
        "or something",
        "and stuff",
        "whatever",
        "anyway",
    }
)

FILLER_WORDS: frozenset[str] = RU_FILLER_WORDS | EN_FILLER_WORDS


class AllowedDeckFormat(StrEnum):
    """Deck formats accepted for upload / ingest."""

    PPTX = ".pptx"
    PDF = ".pdf"


MAX_DECK_SIZE_MB = 50
# Экономический, а не технический потолок: один Разбор = одно списание с баланса
# независимо от размера Деки, поэтому размер обязан быть ограничен сверху. При
# ~1.2 ₽/слайд 25 слайдов дают ~30 ₽ — верхняя граница себестоимости одной единицы.
MAX_DECK_SLIDES = 25
# Транскрипция тарифицируется поминутно, поэтому длина записи — прямая статья
# расходов, и без потолка один Разбор может стоить сколько угодно. Размер ловит
# грубые случаи на входе, минуты — реальные: час речи в mp3 занимает ~30 МБ.
MAX_AUDIO_SIZE_MB = 200
MAX_AUDIO_MINUTES = 30
# ffmpeg приводит запись к 16 кГц моно 16 бит — длительность считается из размера
# без ещё одного вызова ffprobe.
WAV_16K_MONO_BYTES_PER_SECOND = 16000 * 2
DECK_RENDER_TIMEOUT_SECONDS = 120
SLIDE_PNG_DPI = 150
LONG_PAUSE_SECONDS = 3.0

MAX_ZOOMS_PER_SLIDE = 3
ZOOM_UPSCALE_FACTOR = 2
DEDUP_IOU_THRESHOLD = 0.5
# Шкала родного формата рамок Gemini: [ymin, xmin, ymax, xmax] в целых 0..1000.
# Модели обучены выдавать координаты именно так — просить у них float 0..1
# заметно хуже по попаданию. Конвертация в BBox — core/geometry.box_2d_to_bbox.
BOX_2D_SCALE = 1000
# Доля площади слайда, начиная с которой bbox уже ни на что не указывает: модель
# не нашла конкретную область и вернула рамку «во весь слайд». Такие рамки не
# рисуем — они накрывают собой настоящие области под ними (та же константа
# продублирована в SlideViewer.tsx как SLIDE_WIDE_AREA).
SLIDE_WIDE_BBOX_AREA = 0.8

CONTACT_SHEET_MAX_SLIDES_PER_SHEET = 30
CONTACT_SHEET_MAX_IMAGES = 2
CONTACT_SHEET_THUMBNAIL_SIZE = (320, 240)
CONTACT_SHEET_GRID_COLUMNS = 5

AXIS_MANIPULATION_RATIO_THRESHOLD = 2.0
PIE_SUM_TOLERANCE = 1.0
EXCEL_VALUE_RELATIVE_TOLERANCE = 0.01

MIN_COMFORTABLE_WPM = 100.0
MAX_COMFORTABLE_WPM = 170.0
FILLER_COUNT_THRESHOLD = 5
SLIDE_TOO_LONG_SECONDS = 150.0
SLIDE_TOO_SHORT_SECONDS = 10.0

MAX_FINDINGS_PER_SLIDE = 7
SCORE_FLOOR = 5
SEVERITY_WEIGHTS: dict[str, int] = {"CRITICAL": 12, "MAJOR": 5, "MINOR": 1}
