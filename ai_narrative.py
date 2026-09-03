"""Optional AI-assisted narrative extension (NOT required, disabled by default).

This does NOT replace the rule-based assessment in analysis.py. It only
drafts a short, clearly labelled narrative on top of numbers that have
already been computed and verified. Wire it into app.py / report.qmd
yourself if you want to use it, and keep the "AI-assisted" label.
"""
import os
from typing import Optional


def generate_ai_narrative(
    address: str,
    category: str,
    match_count: int,
    radius_m: int,
    closest_distance_m: Optional[float],
) -> str:
    """Ask an LLM for a short 2-3 sentence business interpretation.

    Requires OPENAI_API_KEY (or a compatible provider key) in the environment.
    Every number in the prompt is already verified/retrieved data - the LLM
    is only asked to phrase it, not to invent new facts.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY to use the optional AI narrative.")

    from openai import OpenAI  # imported here so this dependency stays optional

    client = OpenAI(api_key=api_key)

    closest_txt = f"{closest_distance_m:.0f} m" if closest_distance_m is not None else "n/a"
    prompt = (
        "Write a neutral, 2-3 sentence business interpretation for a HORECA "
        "entrepreneur, based ONLY on these verified facts:\n"
        f"- Address: {address}\n"
        f"- Category: {category}\n"
        f"- Matching mapped establishments within {radius_m} m: {match_count}\n"
        f"- Distance to closest match: {closest_txt}\n"
        "Do not invent any numbers beyond what is given. Remind the reader "
        "this is based on OpenStreetMap data only and should be validated."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    narrative = response.choices[0].message.content.strip()
    return "**AI-assisted narrative:** " + narrative
