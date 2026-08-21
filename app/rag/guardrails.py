import re
from typing import Tuple, Optional, List


class PromptInjectionGuardrail:
    """
    Zero-token deterministic guardrail to detect adversarial prompt injections,
    system prompt extraction attempts, jailbreaks, and delimiter tampering.
    """

    def __init__(self):
        self.injection_patterns: List[re.Pattern] = [
            # 1. Instruction Overrides & Reset Attempts
            re.compile(
                r"(ignore|disregard|forget|bypass|override)\s+(all\s+|any\s+)?(previous|prior|above|existing|system)\s+(instructions|prompts|rules|commands|guidelines)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(you\s+must\s+|now\s+)?(forget|ignore|clear)\s+(everything|all\s+prior|all\s+previous)(\s+(you\s+)?(know|were\s+told|told|learned|have\s+learned))?",
                re.IGNORECASE,
            ),
            # 2. Persona / Jailbreak Signatures
            re.compile(
                r"\b(DAN\s+mode|jailbreak|do\s+anything\s+now|developer\s+mode\s+enabled|unrestricted\s+ai|evil\s+confidant)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"act\s+as\s+(an?\s+)?(unrestricted|evil|unfiltered|jailbroken)\s+(ai|assistant|model)",
                re.IGNORECASE,
            ),
            # 3. System Prompt & Secret Extraction
            re.compile(
                r"(print|reveal|output|display|show|tell\s+me)\s+(your\s+)?(system\s+prompt|initial\s+instructions|internal\s+instructions|system\s+message)",
                re.IGNORECASE,
            ),
            re.compile(
                r"what\s+(is|are)\s+your\s+(exact\s+)?(system\s+prompt|instructions\s+above)",
                re.IGNORECASE,
            ),
            # 4. Delimiter & Role-Playing Hijacking
            re.compile(r"(\[INST\]|\[/INST\]|<<SYS>>|<\|im_start\|>|<system>|```system)", re.IGNORECASE),
            # 5. Remote Code / Subshell Injection Signatures
            re.compile(
                r"(__import__|eval\s*\(|exec\s*\(|os\.system|subprocess\.Popen|chmod\s+\+x|rm\s+-rf)",
                re.IGNORECASE,
            ),
        ]

    def check(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validates whether the user query contains prompt injection or jailbreak patterns.
        Returns:
            (is_safe: bool, reason: Optional[str])
        """
        if not query or not query.strip():
            return True, None

        cleaned_query = query.strip()

        for pattern in self.injection_patterns:
            if pattern.search(cleaned_query):
                return False, (
                    "Security Alert: Your query contains patterns identified as potential "
                    "prompt injection, system override, or unauthorized instruction tampering."
                )

        return True, None


class InputGuardrail:
    """
    Main Input Guardrail orchestrator for pre-retrieval validation.
    Executes in < 1ms with 0 token overhead.
    """

    def __init__(self):
        self.injection_guard = PromptInjectionGuardrail()

    def validate(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validates the incoming query.
        Returns:
            (is_safe: bool, refusal_reason: Optional[str])
        """
        return self.injection_guard.check(query)
