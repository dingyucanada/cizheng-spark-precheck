from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
import re


def no_unfounded_certification(value):
    if re.search(r'真品率|真品概率|百分之百|100\s*[%％]|确认为真品|确认为赝品|确定为真|确定为假|保证为真|包真', value):
        raise ValueError('不允许未经校准的概率或确定性真伪认证')
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Observation(StrictModel):
    id: str = Field(pattern=r"^O[0-9]{1,2}$")
    photo_id: str = Field(pattern=r"^P[1-6]$")
    dimension: Literal["器型", "纹饰", "胎釉", "款识", "修补", "表面痕迹"]
    description: str = Field(min_length=3, max_length=140)
    location: str = Field(min_length=1, max_length=35)
    bbox: list[float] = Field(min_length=4, max_length=4)
    kind: Literal["feature", "repair_candidate", "anomaly_candidate", "unreadable"]
    alternative: str = Field(max_length=100)

    @field_validator('description','alternative')
    @classmethod
    def bound_language(cls,value):
        return no_unfounded_certification(value)

    @model_validator(mode="after")
    def valid_bbox(self):
        x1, y1, x2, y2 = self.bbox
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("bbox must be normalized [left, top, right, bottom]")
        return self


class ObservationSet(StrictModel):
    object_name: str = Field(min_length=1, max_length=24)
    object_consistency: Literal["consistent", "uncertain", "mixed"]
    visible_roles: list[Literal["overall", "base", "mouth", "detail", "mark"]] = Field(max_length=5)
    ceramic: Literal["yes", "uncertain", "no"]
    observations: list[Observation] = Field(min_length=1, max_length=12)
    # Controlled vocabulary; no owner name, filename, collector narrative or location goes online.
    search_terms: list[Literal["ceramics", "porcelain", "stoneware", "bowl", "vase", "jar", "dish", "beaker", "teapot", "celadon", "Longquan", "blue and white", "Jingdezhen", "Chinese"]] = Field(max_length=5)
    missing_views: list[str] = Field(max_length=5)


class Comparison(StrictModel):
    id: str = Field(pattern=r"^C[0-9]{1,2}$")
    observation_ids: list[str] = Field(min_length=1, max_length=4)
    reference_id: str = Field(min_length=1, max_length=40)
    quote: str = Field(min_length=3, max_length=220)
    relation: Literal["compatible", "conflict", "insufficient"]
    explanation: str = Field(min_length=3, max_length=140)
    alternative: str = Field(min_length=3, max_length=120)
    # A difference from a reference is not a contradiction of the submitted claim.
    claim_relevance: Literal["direct", "style_only", "uncertain"]

    @field_validator('explanation','alternative')
    @classmethod
    def bound_language(cls,value):
        return no_unfounded_certification(value)


class ComparisonSet(StrictModel):
    comparisons: list[Comparison] = Field(max_length=6)


class ReviewItem(StrictModel):
    comparison_id: str = Field(max_length=10)
    verdict: Literal["supported", "unsupported", "uncertain"]
    reason: str = Field(min_length=3, max_length=140)


class ReviewSet(StrictModel):
    items: list[ReviewItem] = Field(max_length=6)


class CaseInput(StrictModel):
    name: str = Field(default="待检瓷器", min_length=1, max_length=30)
    claim: str = Field(default="", max_length=180)
    online: bool = False
    cloud_review: bool = False
    source: Literal["现场拍摄", "持有人提供", "公开馆藏", "来源待核"] = "持有人提供"
    roles: list[Literal["overall", "base", "mouth", "detail", "mark", "unknown"]] = Field(default_factory=list, max_length=6)


class DemoInput(StrictModel):
    object_id: Literal[48450, 48607, 51185] = 48450


class StartInput(StrictModel):
    force_new: bool = False
    mode: Literal["analyze", "catalog"] = "analyze"
