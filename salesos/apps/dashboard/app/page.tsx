import { AlertTriangle, Clock3, MailCheck, Radar, Rows3, ShieldAlert } from "lucide-react";

import { Card } from "@/components/ui/card";

const apiBaseUrl = process.env.SALESOS_API_BASE_URL ?? "http://api:8000/api";

type DashboardData = {
  jobs: Array<{ job_id: string; status: string; created_at?: string | null }>;
  leads: Array<{ id: string; business_name: string; lifecycle_state: string; heuristic_score?: number | null }>;
  outreach: Array<{ id: string; status: string; review_status: string; subject?: string | null }>;
  failures: Array<{ id: string; pipeline_stage: string; failure_category: string; error_message: string }>;
  escalations: Array<{ id: string; reason: string; status: string }>;
  metrics: {
    total_leads: number;
    review_queue: number;
    dead_letters: number;
    open_escalations: number;
    avg_score: number;
    stage_counts: Record<string, number>;
  };
};

async function getDashboardData(): Promise<DashboardData | null> {
  try {
    const response = await fetch(`${apiBaseUrl}/ops/dashboard`, { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch {
    return null;
  }
}

function MetricCard({
  title,
  value,
  detail,
  icon: Icon,
}: {
  title: string;
  value: string;
  detail: string;
  icon: typeof MailCheck;
}) {
  return (
    <Card className="border-white/8 bg-white/[0.04] p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm uppercase tracking-[0.2em] text-zinc-500">{title}</p>
        <Icon className="h-4 w-4 text-ember-300" />
      </div>
      <p className="mt-4 text-3xl font-semibold text-white">{value}</p>
      <p className="mt-2 text-sm text-zinc-400">{detail}</p>
    </Card>
  );
}

function DataList({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; detail: string; tone?: "default" | "warn" }>;
}) {
  return (
    <Card className="border-white/8 bg-black/20 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        <Rows3 className="h-4 w-4 text-zinc-500" />
      </div>
      <div className="mt-4 space-y-3">
        {rows.length ? (
          rows.map((row) => (
            <div key={`${title}-${row.label}-${row.detail}`} className="rounded-2xl border border-white/6 bg-white/[0.03] p-3">
              <p className={`text-sm font-medium ${row.tone === "warn" ? "text-amber-200" : "text-white"}`}>{row.label}</p>
              <p className="mt-1 text-sm text-zinc-400">{row.detail}</p>
            </div>
          ))
        ) : (
          <p className="text-sm text-zinc-500">No records yet.</p>
        )}
      </div>
    </Card>
  );
}

export default async function HomePage() {
  const data = await getDashboardData();

  return (
    <main className="relative overflow-hidden">
      <div className="mx-auto min-h-screen max-w-7xl px-6 py-10 lg:px-10">
        <section className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="space-y-5">
            <p className="inline-flex rounded-full border border-ember-300/20 bg-ember-300/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-ember-200">
              SalesOS outbound operations engine
            </p>
            <div className="space-y-4">
              <h1 className="max-w-4xl text-5xl font-semibold tracking-tight text-white md:text-7xl">
                Practical outbound ops with explicit stages, review gates, and operator control.
              </h1>
              <p className="max-w-3xl text-lg leading-8 text-zinc-300">
                Local-first lead intelligence, deterministic scoring, reviewable outreach, follow-up scheduling, reply classification, and dead-letter visibility in one small system.
              </p>
            </div>
          </div>
          <Card className="border-white/8 bg-zinc-900/70 p-6">
            <p className="text-sm uppercase tracking-[0.2em] text-zinc-500">Pipeline now</p>
            <p className="mt-3 text-lg font-medium text-white">
              Scrape → Normalize → Dedupe → Intelligence → Score → Analyze → Outreach → Review → Follow-up → Reply → Escalate
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {Object.entries(data?.metrics.stage_counts ?? {}).slice(0, 6).map(([stage, count]) => (
                <div key={stage} className="rounded-2xl border border-white/8 bg-black/25 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">{stage}</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{count}</p>
                </div>
              ))}
            </div>
          </Card>
        </section>

        <section className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <MetricCard
            title="Leads"
            value={String(data?.metrics.total_leads ?? 0)}
            detail="Total persisted leads in the engine."
            icon={Radar}
          />
          <MetricCard
            title="Review Queue"
            value={String(data?.metrics.review_queue ?? 0)}
            detail="Outreach drafts waiting for operator approval."
            icon={MailCheck}
          />
          <MetricCard
            title="Dead Letters"
            value={String(data?.metrics.dead_letters ?? 0)}
            detail="Pipeline runs that exhausted retries."
            icon={AlertTriangle}
          />
          <MetricCard
            title="Escalations"
            value={String(data?.metrics.open_escalations ?? 0)}
            detail="Replies or workflow issues needing human attention."
            icon={ShieldAlert}
          />
          <MetricCard
            title="Avg Score"
            value={`${Math.round(data?.metrics.avg_score ?? 0)}`}
            detail="Average opportunity score across saved leads."
            icon={Clock3}
          />
        </section>

        <section className="mt-10 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          <DataList
            title="Jobs"
            rows={(data?.jobs ?? []).map((job) => ({
              label: `${job.status.toUpperCase()} · ${job.job_id.slice(0, 8)}`,
              detail: job.created_at ? new Date(job.created_at).toLocaleString() : "Pending timestamp",
            }))}
          />
          <DataList
            title="Leads"
            rows={(data?.leads ?? []).map((lead) => ({
              label: `${lead.business_name} · ${lead.lifecycle_state}`,
              detail: lead.heuristic_score != null ? `Score ${lead.heuristic_score}` : "No score yet",
            }))}
          />
          <DataList
            title="Outreach"
            rows={(data?.outreach ?? []).map((item) => ({
              label: `${item.review_status} · ${item.status}`,
              detail: item.subject || "No subject generated yet",
            }))}
          />
          <DataList
            title="Failures"
            rows={(data?.failures ?? []).map((item) => ({
              label: `${item.pipeline_stage} · ${item.failure_category}`,
              detail: item.error_message,
              tone: "warn",
            }))}
          />
          <DataList
            title="Escalations"
            rows={(data?.escalations ?? []).map((item) => ({
              label: `${item.status} · ${item.reason}`,
              detail: item.id.slice(0, 8),
              tone: "warn",
            }))}
          />
        </section>
      </div>
    </main>
  );
}
