from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class PolicyMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_id: str = Field(pattern=r'^[A-Z0-9_-]+$')
    policy_id: str = Field(pattern=r'^[A-Z]+-\d{3}$')
    title: str
    category: str
    department: str
    version: str = Field(pattern=r'^\d+\.\d+$')
    effective_date: date | None = None
    effective_until: date | None = None
    language: Literal['en', 'fr'] = 'en'
    access_level: Literal['public', 'internal', 'restricted'] = 'internal'
    source: str = 'NovaRetail fictional academic policy'
    temporal_basis: Literal['effective_date', 'dataset_snapshot'] = 'effective_date'
    source_revision: str | None = None
    version_origin: Literal['document', 'project_snapshot'] = 'document'
    @model_validator(mode='after')
    def valid_interval(self):
        if self.temporal_basis == 'effective_date' and self.effective_date is None:
            raise ValueError('An effective date is required for dated policy versions')
        if self.temporal_basis == 'dataset_snapshot' and (self.effective_date or self.effective_until):
            raise ValueError('An undated dataset snapshot cannot claim effective dates')
        if self.effective_until and self.effective_date and self.effective_until <= self.effective_date:
            raise ValueError('effective_until is exclusive and must follow effective_date')
        return self

class Chunk(BaseModel):
    chunk_id: str
    text: str
    metadata: PolicyMetadata
    section: str
    page: int = Field(ge=1)
    file_hash: str
    source_file: str
    source_line_start: int | None = None
    source_line_end: int | None = None
    section_title: str | None = None
    section_origin: Literal['document', 'project_segmentation'] = 'document'
    def reference(self):
        return f'{self.metadata.policy_id}@{self.metadata.version}#{self.section}'

class Hit(BaseModel):
    chunk: Chunk
    score: float
    stage: str

class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=6000)
    incident_date: date
    category: str | None = None
    mode: Literal['dense', 'sparse', 'hybrid', 'rerank'] = 'hybrid'
    top_k: int = Field(default=5, ge=1, le=20)

class Citation(BaseModel):
    chunk_id: str
    quote: str = Field(min_length=1)

class GeneratedAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    abstained: bool
    missing_information: list[str] = Field(default_factory=list)
