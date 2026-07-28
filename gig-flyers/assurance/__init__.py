"""Post-generation assurance plane (photo + gig facts)."""

__all__ = [
    "build_fact_lock_prompt_block",
    "enrich_wild_poster",
    "validate_gig_facts_on_image",
]


def __getattr__(name: str):
    if name == "build_fact_lock_prompt_block":
        from assurance.fact_locks import build_fact_lock_prompt_block

        return build_fact_lock_prompt_block
    if name == "enrich_wild_poster":
        from assurance.pipeline import enrich_wild_poster

        return enrich_wild_poster
    if name == "validate_gig_facts_on_image":
        from assurance.facts import validate_gig_facts_on_image

        return validate_gig_facts_on_image
    raise AttributeError(name)
