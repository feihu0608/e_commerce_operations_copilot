from pydantic import BaseModel, Field, field_validator


class DiagnosisOutput(BaseModel):
    target_audience: str = Field(min_length=8, max_length=1000)
    price_analysis: str = Field(min_length=8, max_length=2000)
    selling_points: list[str] = Field(min_length=3, max_length=8)
    conversion_barriers: list[str] = Field(min_length=2, max_length=8)
    actions: list[str] = Field(min_length=3, max_length=8)

    @field_validator("selling_points", "conversion_barriers", "actions")
    @classmethod
    def validate_nonempty_unique(cls, values: list[str]):
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(values) or len(set(cleaned)) != len(cleaned):
            raise ValueError("items must be non-empty and unique")
        return cleaned


class ImageDirection(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    layout: str = Field(min_length=4, max_length=500)
    copy_text: str = Field(min_length=2, max_length=200, alias="copy")
    selling_point: str = Field(min_length=2, max_length=300)


class VideoScript(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    hook: str = Field(min_length=4, max_length=300)
    shots: list[str] = Field(min_length=3, max_length=12)
    voiceover: str = Field(min_length=4, max_length=1000)
    cta: str = Field(min_length=2, max_length=200)


class CreativeOutput(BaseModel):
    image_directions: list[ImageDirection] = Field(min_length=3, max_length=8)
    video_scripts: list[VideoScript] = Field(min_length=3, max_length=8)

    @field_validator("image_directions")
    @classmethod
    def unique_image_directions(cls, values: list[ImageDirection]):
        if len({item.title for item in values}) != len(values):
            raise ValueError("image direction titles must be unique")
        return values

    @field_validator("video_scripts")
    @classmethod
    def unique_video_scripts(cls, values: list[VideoScript]):
        if len({item.title for item in values}) != len(values):
            raise ValueError("video script titles must be unique")
        return values


class StrategyOutput(BaseModel):
    audience: str = Field(min_length=8, max_length=500)
    channel: str = Field(min_length=2, max_length=50)
    budget: float = Field(gt=0, le=1000000)
    period: str = Field(min_length=2, max_length=50)
    creative_angle: str = Field(min_length=8, max_length=500)
    target_ctr: float = Field(gt=0, le=100)
    stop_roas: float = Field(ge=0, le=100)
    rationale: list[str] = Field(min_length=3, max_length=8)

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, values: list[str]):
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(values) or len(set(cleaned)) != len(cleaned):
            raise ValueError("rationale items must be non-empty and unique")
        return cleaned


class ReviewOutput(BaseModel):
    executive_summary: str = Field(min_length=8, max_length=1500)
    goal_vs_actual: dict[str, str | float | int | None]
    observations: list[str] = Field(min_length=2, max_length=8)
    possible_causes: list[str] = Field(min_length=2, max_length=8)
    next_actions: list[str] = Field(min_length=3, max_length=8)
    evidence_limitations: list[str] = Field(min_length=1, max_length=6)

    @field_validator("observations", "possible_causes", "next_actions", "evidence_limitations")
    @classmethod
    def validate_review_lists(cls, values: list[str]):
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(values) or len(set(cleaned)) != len(cleaned):
            raise ValueError("review items must be non-empty and unique")
        return cleaned


AI_OUTPUT_SCHEMAS = {
    "diagnosis": DiagnosisOutput,
    "creative": CreativeOutput,
    "strategy": StrategyOutput,
    "review": ReviewOutput,
}
