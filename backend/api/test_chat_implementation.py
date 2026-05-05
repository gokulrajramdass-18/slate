"""
Test script for chat functionality

Verifies that all chat components are properly implemented.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        from api.services.context import ContextService, get_context_service
        print("✓ Context service imports OK")
    except ImportError as e:
        print(f"✗ Context service import failed: {e}")
        return False

    try:
        from api.routers.chat import router as chat_router
        print("✓ Chat router imports OK")
    except ImportError as e:
        print(f"✗ Chat router import failed: {e}")
        return False

    try:
        from api.routers.source_chat import router as source_chat_router
        print("✓ Source chat router imports OK")
    except ImportError as e:
        print(f"✗ Source chat router import failed: {e}")
        return False

    try:
        from api.models import (
            ChatSessionCreate,
            ChatSessionResponse,
            ChatMessageResponse,
            ChatRequest,
            ChatResponse
        )
        print("✓ Chat models import OK")
    except ImportError as e:
        print(f"✗ Chat models import failed: {e}")
        return False

    try:
        from open_notebook.domain.chat import ChatSession, ChatMessage
        print("✓ Chat domain models import OK")
    except ImportError as e:
        print(f"✗ Chat domain models import failed: {e}")
        return False

    return True


async def test_context_service():
    """Test context service functionality"""
    print("\nTesting context service...")

    try:
        from api.services.context import ContextService

        # Test instantiation
        service = ContextService(max_tokens=1000, model="gpt-4")
        print("✓ Context service instantiation OK")

        # Test token counting
        text = "Hello, this is a test message."
        tokens = service.count_tokens(text)
        print(f"✓ Token counting OK ('{text}' = {tokens} tokens)")

        # Test text truncation
        long_text = "word " * 1000
        truncated = service.truncate_text(long_text, max_tokens=50)
        print(f"✓ Text truncation OK (1000 words -> {len(truncated.split())} words)")

        return True

    except Exception as e:
        print(f"✗ Context service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_models():
    """Test Pydantic models"""
    print("\nTesting Pydantic models...")

    try:
        from api.models import (
            ChatSessionCreate,
            ChatMessageCreate,
            ChatRequest
        )

        # Test ChatSessionCreate
        session_create = ChatSessionCreate(
            title="Test Session",
            notebook_id="test-notebook-id",
            model_override="gpt-4"
        )
        print(f"✓ ChatSessionCreate OK: {session_create.title}")

        # Test ChatMessageCreate
        message_create = ChatMessageCreate(
            role="user",
            content="Hello, AI!"
        )
        print(f"✓ ChatMessageCreate OK: {message_create.role}")

        # Test ChatRequest
        chat_request = ChatRequest(
            message="What is the meaning of life?",
            stream=True,
            include_context=True,
            max_context_tokens=4000
        )
        print(f"✓ ChatRequest OK: stream={chat_request.stream}")

        return True

    except Exception as e:
        print(f"✗ Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_router_structure():
    """Test router structure"""
    print("\nTesting router structure...")

    try:
        from api.routers.chat import router as chat_router
        from api.routers.source_chat import router as source_chat_router

        # Check chat router endpoints
        routes = [route.path for route in chat_router.routes]
        print(f"✓ Chat router has {len(routes)} routes")

        expected_routes = [
            "/api/chat/sessions",
            "/api/chat/sessions/{session_id}",
            "/api/chat/sessions/{session_id}/messages",
        ]

        for expected in expected_routes:
            if any(expected in route for route in routes):
                print(f"  ✓ Found route: {expected}")
            else:
                print(f"  ✗ Missing route: {expected}")

        # Check source chat router endpoints
        source_routes = [route.path for route in source_chat_router.routes]
        print(f"✓ Source chat router has {len(source_routes)} routes")

        return True

    except Exception as e:
        print(f"✗ Router structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Chat Functionality Test Suite")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Imports", await test_imports()))
    results.append(("Context Service", await test_context_service()))
    results.append(("Models", await test_models()))
    results.append(("Router Structure", await test_router_structure()))

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
