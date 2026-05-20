def lead_analysis_prompt(*, business_name: str, context: str) -> str:
    category_hint = _category_hint(context)
    return f"""
You analyze a local business lead for outbound outreach.

Your job:
- identify exactly ONE concrete observation grounded in the provided context
- identify exactly ONE likely operational or conversion problem
- identify exactly ONE concise outreach hook
- score the lead from 0 to 100

Hard rules:
- output strict JSON only
- do not use buzzwords like "unlock", "leverage", "synergy", "game-changer"
- do not use these phrases: "importance of", "business growth", "startup scene", "strong online presence", "improve SEO", "digital transformation", "strong strategy", "vibrant market", "online visibility"
- do not write industry summaries or city commentary
- do not hallucinate tools, traffic numbers, rankings, or client results
- if context is thin, make a cautious inference and say it carefully
- keep observation, problem, and outreach_hook each under 22 words
- if review signal evidence is present, reference the exact issue from the review comments
- observation must reference one of these areas when plausible: CTA placement, mobile UX, missing trust signals, weak conversion flow, outdated branding, slow response flow, missing booking flow, weak local proof, inconsistent messaging
- no introductions, no conclusions, no motivational tone

Weak output example:
{{
  "score": 75,
  "observation": "The business should improve SEO.",
  "problem": "A strong strategy could help business growth.",
  "outreach_hook": "Better online visibility may help."
}}

Strong output example:
{{
  "score": 82,
  "observation": "The service promise is clear, but the primary CTA feels buried after the hero copy on mobile.",
  "problem": "That usually weakens quote conversion when local visitors cannot see the next step immediately.",
  "outreach_hook": "A tighter mobile CTA path could turn existing search intent into more enquiries."
}}

Strong output example 2:
{{
  "score": 78,
  "observation": "The agency message is broad, and the homepage proof does not show one clear niche or outcome.",
  "problem": "When positioning and proof are mixed together, qualified visitors hesitate before booking a call.",
  "outreach_hook": "Sharper niche proof and one booking path would likely improve conversion quality."
}}

Category guidance:
{category_hint}

Return JSON with exactly these keys:
{{
  "score": 0,
  "observation": "",
  "problem": "",
  "outreach_hook": ""
}}

Business: {business_name}
Context: {context}
""".strip()


def outreach_personalization_prompt(
    *,
    business_name: str,
    context: str,
    observation: str,
    problem: str,
    outreach_hook: str,
) -> str:
    category_hint = _category_hint(context)
    return f"""
You write concise outbound outreach for a local business.

Use the provided analysis. Do not invent new facts.

Your job:
- turn one business observation into one believable email subject
- write one short message that sounds human and researched
- mention one plausible business issue without sounding like a consultant pitch

Hard rules:
- output strict JSON only
- avoid generic marketing language
- avoid "boost", "optimize", "transform", "skyrocket", "maximize"
- do not use these phrases: "importance of", "business growth", "startup scene", "strong online presence", "improve SEO", "digital transformation", "strong strategy", "vibrant market", "online visibility"
- avoid fake claims like "I saw your analytics" or "your conversions dropped"
- avoid long paragraphs
- do not mention AI, automation, or templates
- subject must be under 9 words
- message must be 1 to 2 sentences and under 55 words
- message must reference the business naturally
- message must reference one operational issue only
- if review signal evidence is included in context, reflect that exact operational issue in the subject and message
- no introductions
- no conclusions
- no motivational tone
- no generic recommendations

Weak output example:
{{
  "observation": "The company needs better marketing.",
  "problem": "Business growth may be limited.",
  "outreach_hook": "A strong strategy could help.",
  "subject": "Idea for your business",
  "message": "You may want to improve SEO and strengthen your online presence."
}}

Strong output example:
{{
  "observation": "The site talks about rankings, but the primary CTA is easy to miss on mobile.",
  "problem": "That usually wastes high-intent local search traffic that is ready to request a quote.",
  "outreach_hook": "A clearer mobile CTA could convert more existing traffic without changing the offer.",
  "subject": "Quick thought on mobile CTA",
  "message": "River City SEO Co makes the rankings promise clearly, but the main CTA is easy to miss on mobile. That usually lowers quote conversion from local search traffic."
}}

Strong output example 2:
{{
  "observation": "The agency positioning is visible, but the proof and CTA do not point to one specific buyer outcome.",
  "problem": "That usually weakens conversion because visitors cannot tell what happens after the click.",
  "outreach_hook": "A narrower proof-to-CTA path would make the offer easier to act on.",
  "subject": "Quick thought on CTA clarity",
  "message": "The offer on {business_name} is visible, but the proof and CTA do not line up around one clear next step. That usually causes qualified traffic to hesitate instead of booking."
}}

Category guidance:
{category_hint}

Return JSON with exactly these keys:
{{
  "observation": "",
  "problem": "",
  "outreach_hook": "",
  "subject": "",
  "message": ""
}}

Business: {business_name}
Context: {context}
Analysis observation: {observation}
Analysis problem: {problem}
Analysis outreach hook: {outreach_hook}
""".strip()


def quality_retry_prompt(*, original_prompt: str, issues: list[str]) -> str:
    issue_text = "; ".join(issues)
    return f"""
Rewrite the answer and fix these quality problems: {issue_text}.

Retry rules:
- remove filler
- keep the response operational and concrete
- prefer CTA placement, mobile UX, trust signals, proof gaps, booking flow, response flow, or messaging inconsistency
- do not mention industry trends or city scenes
- do not use any banned phrases from the original prompt
- keep the same strict JSON schema

Original prompt:
{original_prompt}
""".strip()


def reply_classification_prompt(*, message_body: str) -> str:
    return (
        "You are classifying an inbound sales reply. "
        'Return strict JSON with keys "classification" and "reason". '
        f"Message: {message_body}"
    )


def review_signal_refinement_prompt(
    *,
    business_name: str,
    category: str | None,
    detected_categories: list[str],
    heuristic_summary: str,
    heuristic_hook: str,
    evidence_lines: list[str],
) -> str:
    category_hint = _category_hint(category or "")
    evidence_block = "\n".join(f"- {line}" for line in evidence_lines[:3]) or "- No review excerpts provided"
    return f"""
You refine operational pain signals from customer reviews for outbound outreach.

Your job:
- keep the signal grounded in the evidence
- write one concise operational_summary
- write one concise outreach_hook

Hard rules:
- output strict JSON only
- do not invent facts beyond the review evidence
- do not use consultant filler or motivational language
- do not say "importance of", "business growth", "strong strategy", "online visibility", or "improve SEO"
- when evidence is provided, keep the summary grounded in the review text and avoid generic phrasing
- operational_summary must be 1 sentence, under 24 words
- outreach_hook must be 1 sentence, under 24 words
- focus on operational pain like missed calls, follow-up gaps, slow response, scheduling friction, trust issues, or pricing confusion

Weak output example:
{{
  "operational_summary": "The business should improve communication and growth.",
  "outreach_hook": "A stronger strategy may improve results."
}}

Strong output example:
{{
  "operational_summary": "Recent reviews mention missed calls and delayed callbacks after quote requests.",
  "outreach_hook": "That usually means inbound demand is leaking before staff can turn enquiries into booked work."
}}

Category guidance:
{category_hint}

Business: {business_name}
Detected categories: {", ".join(detected_categories) or "none"}
Heuristic summary: {heuristic_summary}
Heuristic hook: {heuristic_hook}
Review evidence:
{evidence_block}

Return JSON with exactly these keys:
{{
  "operational_summary": "",
  "outreach_hook": ""
}}
""".strip()


def _category_hint(context: str) -> str:
    lower = context.lower()
    if "seo" in lower:
        return (
            "- SEO agency: focus on offer clarity, CTA placement, proof specificity, and whether service pages convert intent.\n"
            "- Look for messaging that talks about rankings but not next-step conversion."
        )
    if "roof" in lower:
        return (
            "- Roofing company: focus on trust markers, service area clarity, emergency/contact paths, and quote friction.\n"
            "- Look for whether the site makes it easy to request an estimate quickly."
        )
    if "dental" in lower or "clinic" in lower:
        return (
            "- Dental clinic: focus on appointment friction, treatment clarity, insurance/payment reassurance, and local trust.\n"
            "- Look for whether new patients can quickly understand the next step."
        )
    if "ecommerce" in lower or "store" in lower or "shop" in lower:
        return (
            "- Ecommerce store: focus on product-page clarity, shipping/returns confidence, and checkout friction.\n"
            "- Look for whether the conversion path is obvious from product interest to purchase."
        )
    if "marketing agency" in lower or "agency" in lower:
        return (
            "- Marketing agency: focus on positioning clarity, niche specificity, case-study proof, and CTA sharpness.\n"
            "- Look for whether the agency sounds differentiated or overly broad."
        )
    return (
        "- Use category-aware reasoning from the provided context.\n"
        "- Prefer offer clarity, trust, CTA friction, and conversion issues over generic growth advice."
    )
