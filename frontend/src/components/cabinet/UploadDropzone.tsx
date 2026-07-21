import { useEffect, useRef, useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { FileAudio, FileSpreadsheet, FileText, UploadCloud, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { ApiError } from "@/api/client";
import { useCreateReview } from "@/hooks/useCreateReview";

const MAX_DECK_SIZE_MB = 50;
const DECK_TYPES = [".pptx", ".pdf"];
const AUDIO_TYPES = ["audio/", "video/"];
const DATA_TYPES = [".xlsx"];

function hasExtension(name: string, extensions: string[]): boolean {
  return extensions.some((ext) => name.toLowerCase().endsWith(ext));
}

interface SelectedFiles {
  deck: File | null;
  audio: File | null;
  data: File | null;
}

export function UploadDropzone() {
  const [files, setFiles] = useState<SelectedFiles>({ deck: null, audio: null, data: null });
  const [error, setError] = useState<string | null>(null);
  // 402 = кончились Разборы. Отдельный флаг, чтобы дать ссылку на тарифы,
  // а не просто показать текст ошибки, из которого некуда идти.
  const [needsTopUp, setNeedsTopUp] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [done, setDone] = useState(false);
  const deckInputRef = useRef<HTMLInputElement>(null);
  const createReview = useCreateReview();

  function acceptDeck(file: File): boolean {
    if (!hasExtension(file.name, DECK_TYPES)) {
      setError("Дека должна быть в формате .pptx или .pdf");
      return false;
    }
    if (file.size > MAX_DECK_SIZE_MB * 1024 * 1024) {
      setError(`Дека больше ${MAX_DECK_SIZE_MB} МБ`);
      return false;
    }
    return true;
  }

  function handleDeckFiles(fileList: FileList | null) {
    const file = fileList?.[0];
    if (!file) return;
    setError(null);
    if (!acceptDeck(file)) return;
    setFiles((f) => ({ ...f, deck: file }));
  }

  function handleAudioFiles(fileList: FileList | null) {
    const file = fileList?.[0];
    if (!file) return;
    if (!AUDIO_TYPES.some((prefix) => file.type.startsWith(prefix))) {
      setError("Запись питча должна быть аудио- или видеофайлом");
      return;
    }
    setError(null);
    setFiles((f) => ({ ...f, audio: file }));
  }

  function handleDataFiles(fileList: FileList | null) {
    const file = fileList?.[0];
    if (!file) return;
    if (!hasExtension(file.name, DATA_TYPES)) {
      setError("Данные должны быть в формате .xlsx");
      return;
    }
    setError(null);
    setFiles((f) => ({ ...f, data: file }));
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    handleDeckFiles(event.dataTransfer.files);
  }

  // fetch() has no upload-progress event; approximate while the request is in
  // flight and snap to 100 on the real response (see design.md #2).
  useEffect(() => {
    if (!createReview.isPending) return;
    setProgress(10);
    const timer = setInterval(() => {
      setProgress((p) => Math.min(90, (p ?? 0) + 10));
    }, 300);
    return () => clearInterval(timer);
  }, [createReview.isPending]);

  async function startUpload() {
    if (!files.deck) {
      setError("Сначала выберите Деку");
      return;
    }
    setError(null);
    try {
      await createReview.mutateAsync({ deck: files.deck, audio: files.audio, data: files.data });
      setProgress(100);
      setDone(true);
    } catch (err) {
      setProgress(null);
      setNeedsTopUp(err instanceof ApiError && err.status === 402);
      setError(
        err instanceof ApiError ? err.message : "Не удалось загрузить файл, попробуйте ещё раз",
      );
    }
  }

  function reset() {
    setFiles({ deck: null, audio: null, data: null });
    setProgress(null);
    setDone(false);
    setError(null);
    createReview.reset();
  }

  if (done) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 text-center">
        <p className="font-medium">Дека загружена — Разбор поставлен в очередь.</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Обычно занимает 2–5 минут. Мы пришлём письмо, когда всё будет готово.
        </p>
        <Button variant="outline" className="mt-4" onClick={reset}>
          Загрузить ещё одну Деку
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => deckInputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-border p-10 text-center transition-colors",
          isDragging && "border-accent bg-accent/5",
        )}
      >
        <UploadCloud className="h-8 w-8 text-muted-foreground" />
        <p className="font-medium">Перетащите файл сюда или нажмите, чтобы его выбрать</p>
        <p className="text-sm text-muted-foreground">PPTX или PDF, до {MAX_DECK_SIZE_MB} МБ</p>
        <input
          ref={deckInputRef}
          type="file"
          accept=".pptx,.pdf"
          className="hidden"
          onChange={(e) => handleDeckFiles(e.target.files)}
        />
      </div>

      {files.deck && (
        <FileChip icon={FileText} name={files.deck.name} onRemove={() => setFiles((f) => ({ ...f, deck: null }))} />
      )}

      <div className="flex flex-wrap gap-3">
        <OptionalFilePicker
          label="Запись питча (опционально)"
          icon={FileAudio}
          accept="audio/*,video/*"
          file={files.audio}
          onSelect={handleAudioFiles}
          onRemove={() => setFiles((f) => ({ ...f, audio: null }))}
        />
        <OptionalFilePicker
          label="Данные Excel (опционально)"
          icon={FileSpreadsheet}
          accept=".xlsx"
          file={files.data}
          onSelect={handleDataFiles}
          onRemove={() => setFiles((f) => ({ ...f, data: null }))}
        />
      </div>

      {error && (
        <p className="text-sm text-severity-critical">
          {error}
          {needsTopUp && (
            <>
              {" "}
              <Link to="/pricing" className="font-medium underline">
                Посмотреть тарифы
              </Link>
            </>
          )}
        </p>
      )}

      {progress !== null ? (
        <Progress value={progress} />
      ) : (
        <Button onClick={startUpload} disabled={!files.deck} className="self-start">
          Запустить Разбор
        </Button>
      )}
    </div>
  );
}

interface FileChipProps {
  icon: typeof FileText;
  name: string;
  onRemove: () => void;
}

function FileChip({ icon: Icon, name, onRemove }: FileChipProps) {
  return (
    <div className="flex w-fit items-center gap-2 rounded-md border border-border bg-background px-3 py-1.5 text-sm">
      <Icon className="h-4 w-4 text-muted-foreground" />
      <span className="max-w-xs truncate">{name}</span>
      <button type="button" onClick={onRemove} aria-label="Убрать файл">
        <X className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
      </button>
    </div>
  );
}

interface OptionalFilePickerProps {
  label: string;
  icon: typeof FileText;
  accept: string;
  file: File | null;
  onSelect: (files: FileList | null) => void;
  onRemove: () => void;
}

function OptionalFilePicker({ label, icon: Icon, accept, file, onSelect, onRemove }: OptionalFilePickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  if (file) {
    return <FileChip icon={Icon} name={file.name} onRemove={onRemove} />;
  }

  return (
    <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
      <Icon className="h-4 w-4" />
      {label}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onSelect(e.target.files)}
      />
    </Button>
  );
}
