"""The only thing the router LLM produces: a small, validated plan. Python does everything else."""
from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal["rank_region", "compare", "long_haul_share", "unmet_demand", "airport_profile",
                 "explain_previous", "out_of_scope"]


class Plan(BaseModel):
    intent: Intent = Field(description="Which analysis the user wants.")
    airports: list[str] = Field(default_factory=list,
                                description="Airports exactly as the user named them (code or city).")
    region: str | None = Field(default=None, description="Region or state phrase, only for rank_region.")
    threshold_miles: int | None = Field(default=None, description="Long-haul distance, only if the user gave one.")
    top_n: int | None = Field(default=None, description="How many ranked airports to show, only if asked.")
