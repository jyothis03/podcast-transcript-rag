from app.models.schemas import Chunk, TranscriptSegment, PodcastEpisode
from typing import List

class PodcastChunker:
    def __init__(self,chunk_size:int=500,chunk_overlap:int=80):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def format_segment(self,segment: TranscriptSegment)->str:
        return f"[{segment.speaker}]: {segment.text}"

    def create_chunk(self, buffer:List[TranscriptSegment], 
        formatted_texts: List[str],episode_id: int,
        podcast_name:str,chunk_index:int)->Chunk:

        seen = set()
        speakers = []
        for seg in buffer:
            if seg.speaker not in seen:
                seen.add(seg.speaker)
                speakers.append(seg.speaker)

        return Chunk(
            chunk_id=f"{episode_id}_chunk_{chunk_index}",
            episode_id=episode_id,
            podcast_name=podcast_name,
            text=" ".join(formatted_texts),
            start_time=buffer[0].start_time,
            end_time=buffer[-1].end_time,
            speakers=speakers,
        )

    def _compute_overlap(
        self,
        buffer: List[TranscriptSegment],
        formatted_texts: List[str],
    ) -> tuple:
        
        overlap_segments: List[TranscriptSegment] = []
        overlap_texts: List[str]= []
        char_count = 0

        for seg,text in zip(reversed(buffer),reversed(formatted_texts)):
            char_count += len(text)
            overlap_segments.append(seg)
            overlap_texts.append(text)

            if char_count >= self.chunk_overlap:
                break

        overlap_segments.reverse()
        overlap_texts.reverse()
        return overlap_segments, overlap_texts

    def chunk_episode(self, episode: PodcastEpisode) -> List[Chunk]:
        if not episode.segments:
            return []

        chunks : List[Chunk]= []
        chunk_index = 0 

        buffer: List[TranscriptSegment] = []
        formatted_texts: List[str] = []
        current_length = 0

        for segment in episode.segments:
            formatted = self.format_segment(segment)

            new_length = current_length + len(formatted) + (1 if buffer else 0)

            if new_length > self.chunk_size and buffer:
                chunks.append(self.create_chunk(
                    buffer, formatted_texts,
                    episode.episode_id, episode.podcast_name,
                    chunk_index
                ))
                chunk_index += 1

                buffer, formatted_texts = self._compute_overlap(buffer, formatted_texts)
                current_length = sum(len(t) for t in formatted_texts) + max(0, len(formatted_texts) - 1)

            buffer.append(segment)
            formatted_texts.append(formatted)
            current_length += len(formatted) + (1 if len(buffer) > 1 else 0)

        if buffer:
            chunks.append(self._create_chunk(
                buffer, formatted_texts,
                episode.episode_id, episode.podcast_name, chunk_index
            ))
        return chunks