#!/usr/bin/env python3
"""
Test script for complexity detection
Tests various query sizes to verify routing logic
"""

import sys
sys.path.insert(0, '/opt/sting-ce/app')

from app.utils.complexity_detector import get_complexity_detector, QueryComplexity

def test_complexity_detection():
    """Test complexity detection with various query sizes"""

    detector = get_complexity_detector()

    print("🧪 Testing Complexity Detection")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Interactive threshold: {detector.interactive_threshold} tokens")
    print(f"  Report threshold: {detector.report_threshold} tokens")
    print(f"  Model: {detector.model}")
    print(f"  Tiktoken available: {detector.encoding is not None}")
    print()

    # Test cases
    test_cases = [
        {
            "name": "Very short query",
            "message": "What is GDPR?",
            "expected": QueryComplexity.SIMPLE
        },
        {
            "name": "Short query",
            "message": "Can you explain the key principles of GDPR compliance and how they apply to data processing?",
            "expected": QueryComplexity.SIMPLE
        },
        {
            "name": "Medium query",
            "message": "What is GDPR? " + "Explain in detail. " * 50,
            "expected": QueryComplexity.SIMPLE
        },
        {
            "name": "Long query (should be simple but approaching threshold)",
            "message": "Please analyze " + "the data privacy implications of cloud computing across multiple jurisdictions. " * 200,
            "expected": QueryComplexity.SIMPLE
        },
        {
            "name": "Complex query (over 4096 tokens)",
            "message": "Please provide a comprehensive analysis of " + "GDPR compliance requirements including data subject rights, processing principles, technical measures, organizational requirements, and specific implementation strategies. " * 300,
            "expected": QueryComplexity.COMPLEX
        },
        {
            "name": "Very large query (over 16384 tokens)",
            "message": "Analyze the following: " + ("This is a very detailed analysis point that needs careful consideration. " * 2000),
            "expected": QueryComplexity.TOO_LARGE
        }
    ]

    results = []
    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print("-" * 60)

        complexity, metadata = detector.detect_complexity(
            user_message=test['message'],
            conversation_history=None,
            context=None
        )

        passed = complexity == test['expected']
        status = "✅ PASS" if passed else "❌ FAIL"

        print(f"  Message length: {len(test['message'])} characters")
        print(f"  Token count: {metadata['total_tokens']}")
        print(f"  Expected complexity: {test['expected'].value}")
        print(f"  Detected complexity: {complexity.value}")
        print(f"  Recommendation: {metadata['recommendation']}")
        print(f"  Status: {status}")
        print()

        results.append({
            "test": test['name'],
            "passed": passed,
            "tokens": metadata['total_tokens'],
            "complexity": complexity.value
        })

    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)

    for result in results:
        status = "✅" if result['passed'] else "❌"
        print(f"{status} {result['test']}: {result['tokens']} tokens → {result['complexity']}")

    print()
    print(f"Results: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {total_count - passed_count} test(s) failed")
        return 1


def test_with_conversation_history():
    """Test complexity detection with conversation history"""

    print("\n" + "=" * 60)
    print("🧪 Testing with Conversation History")
    print("=" * 60)

    detector = get_complexity_detector()

    conversation_history = [
        {"role": "user", "content": "Hello, I need help with GDPR compliance."},
        {"role": "assistant", "content": "I'd be happy to help you with GDPR compliance. What specific aspect are you interested in?"},
        {"role": "user", "content": "Can you explain data subject rights?"},
        {"role": "assistant", "content": "Certainly! GDPR grants individuals several key rights including the right to access, rectification, erasure, restriction of processing, data portability, and objection."}
    ]

    # Simple message with history
    message = "Can you give me more details on the right to erasure?"
    complexity, metadata = detector.detect_complexity(
        user_message=message,
        conversation_history=conversation_history,
        context=None
    )

    print(f"User message: '{message}'")
    print(f"User message tokens: {metadata['user_message_tokens']}")
    print(f"Conversation history tokens: {metadata['conversation_tokens']}")
    print(f"Total tokens: {metadata['total_tokens']}")
    print(f"Detected complexity: {complexity.value}")
    print(f"Recommendation: {metadata['recommendation']}")

    if complexity == QueryComplexity.SIMPLE:
        print("✅ Correctly identified as SIMPLE (conversation history included)")
        return 0
    else:
        print(f"❌ Expected SIMPLE but got {complexity.value}")
        return 1


if __name__ == "__main__":
    try:
        # Run basic tests
        exit_code1 = test_complexity_detection()

        # Run conversation history test
        exit_code2 = test_with_conversation_history()

        # Exit with failure if any test failed
        sys.exit(max(exit_code1, exit_code2))

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
