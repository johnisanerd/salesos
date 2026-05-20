def hot_lead_message(*, business_name: str, score: float, summary: str) -> str:
    return (
        f"Hot lead detected\n"
        f"Business: {business_name}\n"
        f"Score: {score:.2f}\n"
        f"Summary: {summary}"
    )


def reply_alert_message(*, business_name: str, classification: str, snippet: str) -> str:
    return (
        f"Reply received\n"
        f"Business: {business_name}\n"
        f"Classification: {classification}\n"
        f"Snippet: {snippet}"
    )
