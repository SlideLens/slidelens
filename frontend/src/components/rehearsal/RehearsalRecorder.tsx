import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Circle, Loader2, Mic, Square, TriangleAlert } from "lucide-react";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCreateRehearsal } from "@/hooks/useCreateRehearsal";
import { useSlides } from "@/hooks/useSlides";
import { SlideTimingTracker } from "@/lib/slideTimingTracker";

export interface RehearsalRecorderProps {
  reviewId: string;
  onRecorded: (rehearsalId: string) => void;
  onCancel: () => void;
}

type Phase = "idle" | "recording" | "uploading";

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function RehearsalRecorder({ reviewId, onRecorded, onCancel }: RehearsalRecorderProps) {
  const { data: slides, isLoading, isError, error } = useSlides(reviewId);
  const createRehearsal = useCreateRehearsal();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [micError, setMicError] = useState<string | null>(null);

  const trackerRef = useRef<SlideTimingTracker>(new SlideTimingTracker());
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const tickRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (tickRef.current !== null) window.clearInterval(tickRef.current);
      mediaRecorderRef.current?.stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function goToSlide(index: number) {
    if (!slides || index < 0 || index >= slides.length) return;
    if (phase === "recording") trackerRef.current.switchTo(slides[index].slide_num);
    setCurrentIndex(index);
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "ArrowLeft") goToSlide(currentIndex - 1);
      else if (e.key === "ArrowRight") goToSlide(currentIndex + 1);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentIndex, phase, slides]);

  async function startRecording() {
    if (!slides || slides.length === 0) return;
    setMicError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      trackerRef.current.start(slides[currentIndex].slide_num);
      startedAtRef.current = performance.now();
      setElapsedSeconds(0);
      setPhase("recording");
      tickRef.current = window.setInterval(() => {
        setElapsedSeconds((performance.now() - startedAtRef.current) / 1000);
      }, 250);
    } catch {
      setMicError(
        "Не удалось получить доступ к микрофону. Разрешите доступ в настройках браузера и попробуйте снова.",
      );
    }
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current;
    if (!recorder) return;
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
    const timings = trackerRef.current.stop();

    recorder.addEventListener(
      "stop",
      () => {
        const audioBlob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        recorder.stream.getTracks().forEach((t) => t.stop());
        setPhase("uploading");
        createRehearsal.mutate(
          { reviewId, audio: audioBlob, audioFilename: "rehearsal.webm", slideTimings: timings },
          {
            onSuccess: (rehearsal) => onRecorded(rehearsal.id),
            onError: () => setPhase("idle"),
          },
        );
      },
      { once: true },
    );
    recorder.stop();
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
        <Skeleton className="aspect-video w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (isError || !slides) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-status-failed/30 bg-status-failed/5 px-6 py-16 text-center">
        <TriangleAlert className="h-10 w-10 text-status-failed" />
        <p className="text-lg font-medium">Не удалось загрузить слайды</p>
        <p className="max-w-md text-sm text-muted-foreground">
          {error instanceof ApiError ? error.message : "Попробуйте обновить страницу."}
        </p>
      </div>
    );
  }

  const slide = slides[currentIndex];

  return (
    <div className="flex flex-col gap-4">
      <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-border bg-gradient-to-br from-slate-50 to-slate-100">
        <img
          src={slide.url}
          alt={`Слайд ${slide.slide_num}`}
          className="absolute inset-0 h-full w-full object-contain"
        />
        <div className="absolute left-3 top-3 rounded bg-black/60 px-2 py-0.5 text-xs font-medium text-white">
          Слайд {currentIndex + 1} из {slides.length}
        </div>
        {phase === "recording" && (
          <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded bg-black/60 px-2 py-0.5 text-xs font-medium text-white">
            <Circle className="h-2.5 w-2.5 fill-severity-critical text-severity-critical" />
            {formatElapsed(elapsedSeconds)}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            disabled={currentIndex === 0}
            onClick={() => goToSlide(currentIndex - 1)}
            aria-label="Предыдущий слайд"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            disabled={currentIndex === slides.length - 1}
            onClick={() => goToSlide(currentIndex + 1)}
            aria-label="Следующий слайд"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground">← → для листания</span>
        </div>

        <div className="flex items-center gap-2">
          {phase === "idle" && (
            <>
              <Button variant="outline" onClick={onCancel}>
                Отмена
              </Button>
              <Button onClick={startRecording}>
                <Mic className="h-4 w-4" />
                Начать запись
              </Button>
            </>
          )}
          {phase === "recording" && (
            <Button variant="destructive" onClick={stopRecording}>
              <Square className="h-4 w-4" />
              Остановить
            </Button>
          )}
          {phase === "uploading" && (
            <Button disabled>
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем запись…
            </Button>
          )}
        </div>
      </div>

      {micError && (
        <p className="flex items-center gap-1.5 text-sm text-severity-critical">
          <TriangleAlert className="h-4 w-4 shrink-0" />
          {micError}
        </p>
      )}
      {createRehearsal.isError && (
        <p className="text-sm text-severity-critical">
          {createRehearsal.error instanceof ApiError
            ? createRehearsal.error.message
            : "Не удалось отправить запись, попробуйте ещё раз"}
        </p>
      )}
    </div>
  );
}
