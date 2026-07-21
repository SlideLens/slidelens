import { useNavigate, useParams } from "react-router-dom";
import { RehearsalRecorder } from "@/components/rehearsal/RehearsalRecorder";

export default function RehearsalRecordPage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const navigate = useNavigate();
  if (!reviewId) return null;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Репетиция</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Запишите питч, листая слайды — так мы засечём точный тайминг по слайдам.
        </p>
      </div>
      <RehearsalRecorder
        reviewId={reviewId}
        onRecorded={(rehearsalId) => navigate(`/rehearsal/${reviewId}/attempts/${rehearsalId}`)}
        onCancel={() => navigate(`/rehearsal/${reviewId}`)}
      />
    </div>
  );
}
