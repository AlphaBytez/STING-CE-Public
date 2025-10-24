"""
Complexity Detection Utility for Bee Assistant

Determines whether a user query should be handled as:
- Interactive chat (simple, ≤4096 tokens)
- Report generation (complex, >4096 and ≤16384 tokens)
- Error (exceeds limits, >16384 tokens)

Uses tiktoken for accurate token counting.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import tiktoken, fallback to character-based estimation if unavailable
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not available, falling back to character-based token estimation")


class QueryComplexity(Enum):
    """Query complexity levels"""
    SIMPLE = "simple"           # ≤4096 tokens - interactive chat
    COMPLEX = "complex"          # >4096 and ≤16384 tokens - generate report
    TOO_LARGE = "too_large"      # >16384 tokens - error


class ComplexityDetector:
    """
    Detects query complexity based on token count and routes accordingly.
    """

    def __init__(
        self,
        interactive_threshold: int = 4096,
        report_threshold: int = 16384,
        model: str = "gpt-3.5-turbo"
    ):
        """
        Initialize complexity detector.

        Args:
            interactive_threshold: Max tokens for interactive chat (default: 4096)
            report_threshold: Max tokens for report generation (default: 16384)
            model: Model name for tiktoken encoding (default: gpt-3.5-turbo)
        """
        self.interactive_threshold = int(
            os.getenv('BEE_INTERACTIVE_THRESHOLD_TOKENS', interactive_threshold)
        )
        self.report_threshold = int(
            os.getenv('BEE_REPORT_THRESHOLD_TOKENS', report_threshold)
        )
        self.model = os.getenv('BEE_TOKENIZER_MODEL', model)

        # Initialize tiktoken encoding if available
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoding = tiktoken.encoding_for_model(self.model)
                logger.info(f"Initialized tiktoken with model: {self.model}")
            except KeyError:
                # Fallback to cl100k_base encoding (used by GPT-3.5/4)
                logger.warning(f"Model {self.model} not found, using cl100k_base encoding")
                self.encoding = tiktoken.get_encoding("cl100k_base")
        else:
            self.encoding = None

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken or fallback estimation.

        Args:
            text: Input text to count tokens for

        Returns:
            Token count
        """
        if not text:
            return 0

        if TIKTOKEN_AVAILABLE and self.encoding:
            # Use tiktoken for accurate counting
            try:
                tokens = self.encoding.encode(text)
                return len(tokens)
            except Exception as e:
                logger.warning(f"tiktoken encoding failed: {e}, falling back to estimation")

        # Fallback: character-based estimation (1 token ≈ 4 characters)
        return len(text) // 4

    def count_conversation_tokens(
        self,
        messages: List[Dict[str, str]],
        include_system_prompt: bool = True
    ) -> Dict[str, int]:
        """
        Count tokens in a conversation history.

        Args:
            messages: List of message dicts with 'role' and 'content'
            include_system_prompt: Whether to include system prompt tokens

        Returns:
            Dict with token counts: {
                'user_messages': int,
                'assistant_messages': int,
                'system_messages': int,
                'total': int
            }
        """
        counts = {
            'user_messages': 0,
            'assistant_messages': 0,
            'system_messages': 0,
            'total': 0
        }

        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            token_count = self.count_tokens(content)

            if role == 'user':
                counts['user_messages'] += token_count
            elif role == 'assistant':
                counts['assistant_messages'] += token_count
            elif role == 'system':
                if include_system_prompt:
                    counts['system_messages'] += token_count

            # Add overhead for role/message structure (~4 tokens per message)
            counts['total'] += token_count + 4

        return counts

    def detect_complexity(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict] = None
    ) -> Tuple[QueryComplexity, Dict[str, any]]:
        """
        Detect query complexity and determine routing strategy.

        Args:
            user_message: Current user message
            conversation_history: Optional conversation history
            context: Optional additional context (honey jar data, etc.)

        Returns:
            Tuple of (QueryComplexity enum, metadata dict)

        Metadata includes:
            - user_message_tokens: Token count of user message
            - conversation_tokens: Token count of conversation history
            - context_tokens: Token count of additional context
            - total_tokens: Total token count
            - threshold_interactive: Interactive threshold value
            - threshold_report: Report threshold value
            - recommendation: String describing recommended action
        """
        # Count user message tokens
        user_tokens = self.count_tokens(user_message)

        # Count conversation history tokens
        conversation_tokens = 0
        if conversation_history:
            counts = self.count_conversation_tokens(conversation_history)
            conversation_tokens = counts['total']

        # Count context tokens (if provided)
        context_tokens = 0
        if context:
            # Estimate context size (honey jar data, retrieved docs, etc.)
            context_str = str(context)
            context_tokens = self.count_tokens(context_str)

        # Total tokens
        total_tokens = user_tokens + conversation_tokens + context_tokens

        # Determine complexity
        if total_tokens <= self.interactive_threshold:
            complexity = QueryComplexity.SIMPLE
            recommendation = "Route to interactive chat"
        elif total_tokens <= self.report_threshold:
            complexity = QueryComplexity.COMPLEX
            recommendation = "Generate report asynchronously"
        else:
            complexity = QueryComplexity.TOO_LARGE
            recommendation = "Request exceeds maximum size, suggest query refinement"

        metadata = {
            'user_message_tokens': user_tokens,
            'conversation_tokens': conversation_tokens,
            'context_tokens': context_tokens,
            'total_tokens': total_tokens,
            'threshold_interactive': self.interactive_threshold,
            'threshold_report': self.report_threshold,
            'complexity': complexity.value,
            'recommendation': recommendation,
            'tiktoken_available': TIKTOKEN_AVAILABLE
        }

        logger.info(
            f"Complexity detection: {total_tokens} tokens "
            f"({user_tokens} user + {conversation_tokens} history + {context_tokens} context) "
            f"→ {complexity.value}"
        )

        return complexity, metadata

    def should_generate_report(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict] = None
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Convenience method to determine if query should generate a report.

        Args:
            user_message: Current user message
            conversation_history: Optional conversation history
            context: Optional additional context

        Returns:
            Tuple of (should_generate_report: bool, metadata: dict)
        """
        complexity, metadata = self.detect_complexity(
            user_message,
            conversation_history,
            context
        )

        should_generate = complexity == QueryComplexity.COMPLEX
        return should_generate, metadata


# Singleton instance
_detector_instance = None


def get_complexity_detector() -> ComplexityDetector:
    """Get or create singleton complexity detector instance"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ComplexityDetector()
    return _detector_instance
