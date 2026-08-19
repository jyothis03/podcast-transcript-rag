import os
import re
from typing import List
from app.models.schemas import TranscriptSegment


class TranscriptParser:
    """Parses SRT and TXT transcript files into TranscriptSegment objects."""

    # Regex to match SRT timestamp lines: "00:01:30,500 --> 00:02:15,800"
    SRT_TIMESTAMP_RE = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
    )

    # Regex to detect speaker labels like "[Lex]:" or "Lex:" at the start of text
    SPEAKER_RE = re.compile(r"^\[?([A-Za-z0-9_\s]+?)\]?\s*:\s*")

    @staticmethod
    def _timestamp_to_seconds(hours: str, minutes: str, seconds: str, millis: str) -> float:
        """Convert SRT timestamp components to total seconds as a float."""
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000

    def parse_file(self, file_path: str) -> List[TranscriptSegment]:
        """Read a file from disk and parse it based on its extension (.srt or .txt)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Transcript file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if file_path.lower().endswith(".srt"):
            return self.parse_srt(content)
        else:
            return self.parse_txt(content)

    def parse_srt(self, content: str) -> List[TranscriptSegment]:
        """
        Parse an SRT subtitle file into TranscriptSegments.

        SRT format:
            1
            00:00:12,500 --> 00:00:15,800
            [Speaker]: Some spoken text here.

            2
            00:00:16,100 --> 00:00:22,400
            More text that might span
            multiple lines.
        """
        segments: List[TranscriptSegment] = []

        # Split by blank lines to get individual subtitle blocks
        blocks = re.split(r"\n\s*\n", content.strip())

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 2:
                continue

            # Find the timestamp line
            timestamp_match = None
            timestamp_line_idx = -1
            for i, line in enumerate(lines):
                timestamp_match = self.SRT_TIMESTAMP_RE.search(line)
                if timestamp_match:
                    timestamp_line_idx = i
                    break

            if not timestamp_match:
                continue  # Skip blocks without valid timestamps

            # Extract start and end times
            groups = timestamp_match.groups()
            start_time = self._timestamp_to_seconds(*groups[:4])
            end_time = self._timestamp_to_seconds(*groups[4:])

            # Everything after the timestamp line is the spoken text
            text_lines = lines[timestamp_line_idx + 1:]
            text = " ".join(line.strip() for line in text_lines if line.strip())

            if not text:
                continue

            # Best-effort speaker detection
            speaker = "Unknown"
            speaker_match = self.SPEAKER_RE.match(text)
            if speaker_match:
                speaker = speaker_match.group(1).strip()
                text = text[speaker_match.end():]  # Remove the speaker prefix from text

            segments.append(TranscriptSegment(
                speaker=speaker,
                start_time=start_time,
                end_time=end_time,
                text=text.strip()
            ))

        return segments

    def parse_txt(self, content: str) -> List[TranscriptSegment]:
        """
        Parse a plain text file into TranscriptSegments.

        No timestamps available — start_time and end_time are set to -1.0
        to signal 'unavailable' to downstream components.
        """
        segments: List[TranscriptSegment] = []

        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Best-effort speaker detection even for txt files
            speaker = "Unknown"
            speaker_match = self.SPEAKER_RE.match(line)
            if speaker_match:
                speaker = speaker_match.group(1).strip()
                line = line[speaker_match.end():].strip()

            segments.append(TranscriptSegment(
                speaker=speaker,
                start_time=-1.0,
                end_time=-1.0,
                text=line
            ))

        return segments
