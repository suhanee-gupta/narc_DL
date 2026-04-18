from context_encoder import time_bucket


def build(
    archetype: str,
    mood: dict,
    location: str,
    timestamp: str,
    click_history: list,
    max_titles: int = 5,
) -> str:
    dominant_mood = max(mood, key=mood.get) if mood else "neutral"
    time_bucket_str = time_bucket(timestamp)
    recent = [h["title"] for h in click_history[-max_titles:] if h.get("title")]
    titles_str = " | ".join(recent) if recent else "none yet"
    label = archetype.replace("_", " ")
    return (
        f"{label} perspective. "
        f"Mood: {dominant_mood}. "
        f"Location: {location}. "
        f"Time: {time_bucket_str}. "
        f"Recent reads: {titles_str}"
    )
