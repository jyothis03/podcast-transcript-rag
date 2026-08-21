from pydantic import BaseModel, Field
from typing import List, Optional, Union


class TranscriptSegment(BaseModel):
    speaker: str = "Unknown"
    start_time: float
    end_time: float
    text: str


class PodcastEpisode(BaseModel):
    title: str
    episode_id: Union[int, str]
    podcast_name: str
    segments: List[TranscriptSegment]


class Chunk(BaseModel):
    chunk_id: str
    episode_id: Union[int, str]
    podcast_name: str
    text: str
    start_time: float
    end_time: float
    speakers: List[str]


class Citation(BaseModel):
    episode_id: Union[int, str]
    title: str
    start_time: float
    end_time: float
    quote: str


class QueryResponse(BaseModel):
    query: str
    answer: str
    thread_id: str = "default_session"
    citations: List[Citation] = Field(default_factory=list)


class QueryRequest(BaseModel):
    query: str
    thread_id: Optional[str] = "default_session"
    podcast_name: Optional[str] = None
    episode_id: Optional[Union[int, str]] = None
    top_k: Optional[int] = 20
    top_n: Optional[int] = 5


class IngestRequest(BaseModel):
    file_path: str
    podcast_name: str = "Default Podcast"
    episode_id: Union[int, str] = 1