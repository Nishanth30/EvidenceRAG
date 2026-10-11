from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    data_dir: Path = Path('data')
    embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2'
    embedding_revision: str = 'c9745ed1d9f207416be6d2e6f8de32d1f16199bf'
    embedding_device: str = 'cpu'
    embedding_batch_size: int = Field(32, ge=1, le=256)
    chunk_strategy: Literal['fixed', 'recursive'] = 'recursive'
    chunk_size: int = Field(800, ge=50, le=2000)
    chunk_overlap: int = Field(150, ge=0)
    top_k: int = Field(6, ge=1, le=20)
    similarity_threshold: float = Field(0.3, ge=-1, le=1)
    max_upload_mb: int = Field(10, ge=1, le=100)
    max_extracted_chars: int = Field(2_000_000, ge=1000)
    max_context_chars: int = Field(6000, ge=200, le=50000)
    llm_provider: Literal['none', 'openai', 'ollama'] = 'none'
    llm_model: str = ''
    llm_base_url: str = 'http://localhost:11434'
    llm_api_key: SecretStr = SecretStr('')
    llm_timeout_seconds: float = Field(90, gt=0, le=300)

    @model_validator(mode='after')
    def valid_overlap(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError('CHUNK_OVERLAP must be smaller than CHUNK_SIZE')
        return self

    @property
    def index_config(self) -> dict:
        return dict(schema_version=1, model=self.embedding_model,
                    revision=self.embedding_revision, normalized=True,
                    strategy=self.chunk_strategy, size=self.chunk_size,
                    overlap=self.chunk_overlap)
