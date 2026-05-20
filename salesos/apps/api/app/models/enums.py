from enum import StrEnum


class CampaignStatus(StrEnum):
    draft = "draft"
    ready = "ready"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"


class LeadStatus(StrEnum):
    new = "new"
    enriched = "enriched"
    analyzed = "analyzed"
    queued = "queued"
    contacted = "contacted"
    replied = "replied"
    qualified = "qualified"
    archived = "archived"


class LeadState(StrEnum):
    DISCOVERED = "DISCOVERED"
    ENRICHED = "ENRICHED"
    INTELLIGENCE_READY = "INTELLIGENCE_READY"
    QUALIFIED = "QUALIFIED"
    PERSONALIZED = "PERSONALIZED"
    OUTREACH_READY = "OUTREACH_READY"
    IN_REVIEW = "IN_REVIEW"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    INTERESTED = "INTERESTED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    COOLDOWN = "COOLDOWN"
    FAILED = "FAILED"


class LeadPersonalizationTier(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class OutreachChannel(StrEnum):
    email = "email"
    sms = "sms"
    linkedin = "linkedin"


class OutreachStatus(StrEnum):
    pending = "pending"
    prepared = "prepared"
    in_review = "in_review"
    sent = "sent"
    failed = "failed"


class OutreachReviewStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"


class FollowUpStatus(StrEnum):
    pending = "pending"
    scheduled = "scheduled"
    due = "due"
    processing = "processing"
    sent = "sent"
    failed = "failed"
    replied = "replied"
    skipped = "skipped"
    cancelled = "cancelled"


class EscalationStatus(StrEnum):
    none = "none"
    pending = "pending"
    escalated = "escalated"
    resolved = "resolved"


class ConversationStatus(StrEnum):
    open = "open"
    waiting = "waiting"
    qualified = "qualified"
    disqualified = "disqualified"
    closed = "closed"


class MessageDirection(StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class ReplyClassification(StrEnum):
    positive = "positive"
    neutral = "neutral"
    objection = "objection"
    unsubscribe = "unsubscribe"
    spam = "spam"
    manual_review = "manual_review"


class WorkflowStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    dead_lettered = "dead_lettered"


class PipelineStage(StrEnum):
    scrape = "scrape"
    normalize = "normalize"
    dedupe = "dedupe"
    enrich = "enrich"
    intelligence = "intelligence"
    score = "score"
    analyze = "analyze"
    outreach_generate = "outreach_generate"
    outreach_review = "outreach_review"
    follow_up = "follow_up"
    reply_classify = "reply_classify"
    escalate = "escalate"
    notify = "notify"


class FailureCategory(StrEnum):
    validation = "validation"
    dependency = "dependency"
    timeout = "timeout"
    persistence = "persistence"
    ai = "ai"
    delivery = "delivery"
    operator = "operator"
    unknown = "unknown"
