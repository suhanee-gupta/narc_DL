from datetime import datetime


def _time_bucket(timestamp: str) -> str:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
                "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(timestamp.strip(), fmt)
            break
        except ValueError:
            continue
    else:
        return "evening"
    hour = dt.hour
    if hour < 6:   return "morning"
    if hour < 12:  return "afternoon"
    if hour < 18:  return "evening"
    return "night"


def build(
    archetype: str,
    mood: dict,
    location: str,
    timestamp: str,
    click_history: list,
    max_titles: int = 5,
) -> str:
    dominant_mood = max(mood, key=mood.get) if mood else "neutral"
    time_bucket   = _time_bucket(timestamp)
    recent = [h["title"] for h in click_history[-max_titles:]]
    titles_str = " | ".join(recent) if recent else "none yet"
    label = archetype.replace("_", " ")
    return (
        f"{label} perspective. "
        f"Mood: {dominant_mood}. "
        f"Location: {location}. "
        f"Time: {time_bucket}. "
        f"Recent reads: {titles_str}"
    )
