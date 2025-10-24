#!/usr/bin/env python3
"""
Redis-based conversation history cache for Bee
Provides fast, persistent conversation memory across requests
"""

import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import redis

logger = logging.getLogger(__name__)

class ConversationCache:
    """Manages conversation history in Redis for fast retrieval"""

    def __init__(self, redis_host: str = "redis", redis_port: int = 6379):
        """Initialize Redis connection"""
        try:
            self.redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis.ping()
            logger.info(f"✅ Connected to Redis at {redis_host}:{redis_port}")
            self.enabled = True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            logger.warning("Conversation history will not be cached")
            self.redis = None
            self.enabled = False

    def _get_conversation_key(self, conversation_id: str) -> str:
        """Generate Redis key for conversation"""
        return f"bee:conversation:{conversation_id}"

    def _get_user_conversations_key(self, user_id: str) -> str:
        """Generate Redis key for user's conversation list"""
        return f"bee:user:{user_id}:conversations"

    async def add_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a message to the conversation history"""
        if not self.enabled:
            return False

        try:
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            key = self._get_conversation_key(conversation_id)

            # Add message to conversation (list)
            self.redis.lpush(key, json.dumps(message))

            # Keep only last 50 messages (configurable)
            self.redis.ltrim(key, 0, 49)

            # Set expiration (24 hours)
            self.redis.expire(key, 86400)

            # Track user's conversations
            user_key = self._get_user_conversations_key(user_id)
            self.redis.sadd(user_key, conversation_id)
            self.redis.expire(user_key, 86400)

            logger.debug(f"Added {role} message to conversation {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add message to Redis: {e}")
            return False

    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        if not self.enabled:
            return []

        try:
            key = self._get_conversation_key(conversation_id)

            # Get messages (most recent first)
            messages_json = self.redis.lrange(key, 0, limit - 1)

            # Parse and reverse to get chronological order
            messages = [json.loads(msg) for msg in messages_json]
            messages.reverse()

            logger.debug(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
            return messages

        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []

    async def get_conversation_summary(self, conversation_id: str) -> Dict[str, Any]:
        """Get summary of conversation (message count, last activity, etc.)"""
        if not self.enabled:
            return {}

        try:
            key = self._get_conversation_key(conversation_id)

            # Get message count
            count = self.redis.llen(key)

            # Get TTL
            ttl = self.redis.ttl(key)

            # Get most recent message
            recent_json = self.redis.lrange(key, 0, 0)
            recent_message = json.loads(recent_json[0]) if recent_json else None

            return {
                "conversation_id": conversation_id,
                "message_count": count,
                "ttl_seconds": ttl,
                "last_activity": recent_message["timestamp"] if recent_message else None
            }

        except Exception as e:
            logger.error(f"Failed to get conversation summary: {e}")
            return {}

    async def get_user_conversations(self, user_id: str) -> List[str]:
        """Get list of conversation IDs for a user"""
        if not self.enabled:
            return []

        try:
            user_key = self._get_user_conversations_key(user_id)
            conversations = list(self.redis.smembers(user_key))
            logger.debug(f"User {user_id} has {len(conversations)} conversations")
            return conversations

        except Exception as e:
            logger.error(f"Failed to get user conversations: {e}")
            return []

    async def clear_conversation(self, conversation_id: str) -> bool:
        """Clear a specific conversation"""
        if not self.enabled:
            return False

        try:
            key = self._get_conversation_key(conversation_id)
            self.redis.delete(key)
            logger.info(f"Cleared conversation {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear conversation: {e}")
            return False

    async def extend_conversation_ttl(self, conversation_id: str, ttl_seconds: int = 86400) -> bool:
        """Extend conversation expiration time"""
        if not self.enabled:
            return False

        try:
            key = self._get_conversation_key(conversation_id)
            self.redis.expire(key, ttl_seconds)
            return True

        except Exception as e:
            logger.error(f"Failed to extend conversation TTL: {e}")
            return False

    def format_history_for_prompt(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 2000
    ) -> str:
        """Format conversation history for inclusion in LLM prompt"""
        if not messages:
            return ""

        # Build conversation history string
        history_parts = ["## Recent Conversation:"]

        total_chars = 0
        max_chars = max_tokens * 4  # Rough estimate: 1 token ≈ 4 chars

        for msg in messages:
            role = msg["role"].capitalize()
            content = msg["content"]

            # Format message
            formatted = f"{role}: {content}"

            # Check if adding this message would exceed limit
            if total_chars + len(formatted) > max_chars:
                history_parts.append("...[Earlier messages truncated]")
                break

            history_parts.append(formatted)
            total_chars += len(formatted)

        return "\n".join(history_parts)

    async def health_check(self) -> Dict[str, Any]:
        """Check Redis connection health"""
        if not self.enabled:
            return {"status": "disabled", "error": "Redis not connected"}

        try:
            # Test ping
            self.redis.ping()

            # Get stats
            info = self.redis.info("stats")

            return {
                "status": "healthy",
                "enabled": True,
                "total_commands": info.get("total_commands_processed", 0),
                "connected_clients": info.get("connected_clients", 0)
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "enabled": False,
                "error": str(e)
            }


# Global instance
_conversation_cache = None

def get_conversation_cache() -> ConversationCache:
    """Get or create global conversation cache instance"""
    global _conversation_cache
    if _conversation_cache is None:
        _conversation_cache = ConversationCache()
    return _conversation_cache


# Test the conversation cache
if __name__ == "__main__":
    import asyncio

    async def test_conversation_cache():
        cache = ConversationCache()

        print("Testing conversation cache...")

        # Test adding messages
        conv_id = "test_conv_123"
        user_id = "test_user"

        await cache.add_message(conv_id, user_id, "user", "Hello, how are you?")
        await cache.add_message(conv_id, user_id, "assistant", "I'm doing great! How can I help you today?")
        await cache.add_message(conv_id, user_id, "user", "What is STING?")
        await cache.add_message(conv_id, user_id, "assistant", "STING is a secure platform for enterprise AI...")

        # Get history
        history = await cache.get_conversation_history(conv_id, limit=10)
        print(f"\nConversation history ({len(history)} messages):")
        for msg in history:
            print(f"  {msg['role']}: {msg['content'][:50]}...")

        # Get summary
        summary = await cache.get_conversation_summary(conv_id)
        print(f"\nConversation summary:")
        print(f"  Message count: {summary['message_count']}")
        print(f"  Last activity: {summary['last_activity']}")
        print(f"  TTL: {summary['ttl_seconds']} seconds")

        # Format for prompt
        formatted = cache.format_history_for_prompt(history)
        print(f"\nFormatted for prompt:\n{formatted}")

        # Health check
        health = await cache.health_check()
        print(f"\nHealth check: {health}")

        # Clean up
        await cache.clear_conversation(conv_id)
        print(f"\nCleared test conversation")

    asyncio.run(test_conversation_cache())
