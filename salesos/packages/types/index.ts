export type PipelineStage =
  | "scrape"
  | "lead_storage"
  | "enrichment"
  | "analysis"
  | "personalization"
  | "outreach_preparation"
  | "reply_detection"
  | "telegram_alert";

export interface LeadSnapshot {
  id: string;
  businessName: string;
  city?: string;
  state?: string;
  status: string;
}
