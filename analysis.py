"""Rule-based competition assessment.

Kept intentionally simple and transparent (no LLM) so the exact same
logic can be reused by the Flask app and the Quarto report, and so it is
easy to explain and defend in the workshop.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Assessment:
    level: str  # "lower", "moderate", "higher"
    text: str   # human-readable paragraph, ready to drop into the report


def assess_competition(
    match_count: int,
    closest_distance_m: Optional[float],
    category: str,
) -> Assessment:
    """Return a rule-based competition assessment.

    Rules:
      0-1 matches within radius -> lower observed direct competition
      2-4 matches within radius -> moderate observed direct competition
      5+ matches within radius  -> higher observed direct competition
      + extra note if the closest match is under 250 m away
    """
    if match_count <= 1:
        level, level_word = "lower", "Lower"
    elif match_count <= 4:
        level, level_word = "moderate", "Moderate"
    else:
        level, level_word = "higher", "Higher"

    if closest_distance_m is None:
        distance_sentence = (
            f"No mapped {category} establishments were found within the search radius."
        )
    else:
        distance_sentence = (
            f"The nearest mapped {category} is approximately "
            f"{closest_distance_m:.0f} metres away."
        )

    nearby_note = ""
    if closest_distance_m is not None and closest_distance_m < 250:
        nearby_note = (
            " Note: a direct competitor is very nearby (under 250 m), which may "
            "strongly affect footfall and visibility."
        )

    text = (
        f"Indicative competition assessment: {level_word.lower()}. "
        f"The OpenStreetMap query identified {match_count} mapped {category} "
        f"establishment(s) within the search radius. {distance_sentence}"
        f"{nearby_note} Validate these results through local field research and a "
        f"clearer definition of the intended concept before making a location decision."
    )

    return Assessment(level=level, text=text)
