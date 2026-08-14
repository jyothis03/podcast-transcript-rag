from pydantic import BaseModel,Field
from typing import List, Optional

class TranscriptSegment(BaseModel):
    speaker: str = "Unknown"
    start_time: float
    end_time: float
    text: str

class PodcastEpisode(BaseModel):
    title: str
    episode_id: int
    podcast_name: str
    segments: List[TranscriptSegment]

class Chunk(BaseModel):
    chunk_id: str
    episode_id: int
    podcast_name: str
    text: str
    start_time: float
    end_time: float
    speakers: List[str]

class Citation(BaseModel):
    episode_id: int
    title: str
    start_time: float
    end_time: float
    quote: str

class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: List[Citation]

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] 
    top_n: Optional[int] 