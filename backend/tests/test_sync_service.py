"""
Unit tests for sync service.

Tests cover:
- Sync scheduling
- HANA table sync
- API source sync
- Mock external connections
- Error handling and retries
"""

import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

import pytest

from api.services.sync_service import SyncService, SyncStatus, SyncResult
from open_notebook.sources.hana_table import HANATableSource
from open_notebook.sources.api_source import APISource


@pytest.mark.asyncio
class TestSyncService:
    """Test sync service core functionality."""

    async def test_schedule_sync(self, sqlite_db):
        """Test scheduling a sync job."""
        sync_service = SyncService(sqlite_db)

        # Create test source
        source_id = await sqlite_db.create("sources", {
            "title": "Test API",
            "source_type": "api",
            "sync_config": json.dumps({
                "frequency": "0 */6 * * *",  # Every 6 hours
                "status": "idle",
                "last_sync": None
            })
        })

        # Schedule sync
        result = await sync_service.schedule_sync(
            source_id=source_id,
            frequency="0 */6 * * *"
        )

        assert result["source_id"] == source_id
        assert result["status"] == "scheduled"
        assert result["frequency"] == "0 */6 * * *"

    async def test_schedule_sync_validates_frequency(self, sqlite_db):
        """Test that invalid cron expressions are rejected."""
        sync_service = SyncService(sqlite_db)

        source_id = str(uuid.uuid4())

        with pytest.raises(ValueError):
            await sync_service.schedule_sync(
                source_id=source_id,
                frequency="invalid cron"
            )

    async def test_get_sync_status(self, sqlite_db):
        """Test retrieving sync status."""
        sync_service = SyncService(sqlite_db)

        # Create source with sync config
        last_sync = datetime.utcnow().isoformat()
        source_id = await sqlite_db.create("sources", {
            "title": "Test Source",
            "source_type": "api",
            "sync_config": json.dumps({
                "frequency": "0 * * * *",
                "status": "success",
                "last_sync": last_sync,
                "next_sync": (datetime.utcnow() + timedelta(hours=1)).isoformat()
            })
        })

        # Get status
        status = await sync_service.get_sync_status(source_id)

        assert status["source_id"] == source_id
        assert status["status"] == "success"
        assert status["last_sync"] is not None

    async def test_cancel_sync(self, sqlite_db):
        """Test canceling a scheduled sync."""
        sync_service = SyncService(sqlite_db)

        # Create and schedule sync
        source_id = await sqlite_db.create("sources", {
            "title": "Test Source",
            "source_type": "api",
            "sync_config": json.dumps({
                "frequency": "0 * * * *",
                "status": "scheduled"
            })
        })

        # Cancel sync
        result = await sync_service.cancel_sync(source_id)

        assert result["status"] == "cancelled"

        # Verify status updated
        status = await sync_service.get_sync_status(source_id)
        assert status["status"] == "idle"


@pytest.mark.asyncio
class TestHANATableSync:
    """Test HANA table synchronization."""

    async def test_sync_hana_table_basic(self, sqlite_db, sample_hana_table_source):
        """Test basic HANA table sync."""
        sync_service = SyncService(sqlite_db)

        # Create HANA table source
        source_id = await sqlite_db.create("sources", {
            "title": sample_hana_table_source["title"],
            "source_type": "hana_table",
            "full_text": "",
            "connection_config": json.dumps(sample_hana_table_source["connection_config"]),
            "sync_config": json.dumps(sample_hana_table_source["sync_config"])
        })

        # Mock HANA connection
        mock_hana_data = [
            {"PRODUCT_NAME": "Widget A", "DESCRIPTION": "A useful widget", "CATEGORY": "Tools"},
            {"PRODUCT_NAME": "Widget B", "DESCRIPTION": "Another widget", "CATEGORY": "Tools"},
            {"PRODUCT_NAME": "Gadget C", "DESCRIPTION": "A cool gadget", "CATEGORY": "Electronics"}
        ]

        with patch("open_notebook.sources.hana_table.HANATableSource.fetch_data") as mock_fetch:
            mock_fetch.return_value = mock_hana_data

            # Execute sync
            result = await sync_service.execute_sync(source_id)

        assert result.success == True
        assert result.records_synced == 3
        assert result.error is None

        # Verify full_text was updated
        source = await sqlite_db.query(
            "SELECT full_text FROM sources WHERE id = ?",
            [source_id]
        )

        full_text = source[0]["full_text"]
        assert "Widget A" in full_text
        assert "Widget B" in full_text
        assert "Gadget C" in full_text

    async def test_sync_hana_table_connection_error(self, sqlite_db, sample_hana_table_source):
        """Test HANA table sync with connection error."""
        sync_service = SyncService(sqlite_db)

        source_id = await sqlite_db.create("sources", {
            "title": "Test HANA Source",
            "source_type": "hana_table",
            "connection_config": json.dumps(sample_hana_table_source["connection_config"]),
            "sync_config": json.dumps({"status": "idle"})
        })

        # Mock connection failure
        with patch("open_notebook.sources.hana_table.HANATableSource.fetch_data") as mock_fetch:
            mock_fetch.side_effect = ConnectionError("Failed to connect to HANA")

            result = await sync_service.execute_sync(source_id)

        assert result.success == False
        assert result.error is not None
        assert "Failed to connect" in result.error

    async def test_sync_hana_table_incremental(self, sqlite_db, sample_hana_table_source):
        """Test incremental HANA table sync (only changed data)."""
        sync_service = SyncService(sqlite_db)

        # Create source with existing data
        existing_text = "Widget A: A useful widget\nWidget B: Another widget"

        source_id = await sqlite_db.create("sources", {
            "title": "HANA Source",
            "source_type": "hana_table",
            "full_text": existing_text,
            "connection_config": json.dumps(sample_hana_table_source["connection_config"]),
            "sync_config": json.dumps({
                "status": "idle",
                "last_sync": (datetime.utcnow() - timedelta(hours=1)).isoformat()
            })
        })

        # Mock HANA data with changes
        mock_hana_data = [
            {"PRODUCT_NAME": "Widget A", "DESCRIPTION": "Updated description", "CATEGORY": "Tools"},
            {"PRODUCT_NAME": "Widget B", "DESCRIPTION": "Another widget", "CATEGORY": "Tools"},
            {"PRODUCT_NAME": "Widget C", "DESCRIPTION": "New widget", "CATEGORY": "Tools"}
        ]

        with patch("open_notebook.sources.hana_table.HANATableSource.fetch_data") as mock_fetch:
            mock_fetch.return_value = mock_hana_data

            result = await sync_service.execute_sync(source_id, incremental=True)

        assert result.success == True
        # Should detect changes (1 updated, 1 new)
        assert result.records_synced >= 2


@pytest.mark.asyncio
class TestAPISourceSync:
    """Test API source synchronization."""

    async def test_sync_api_basic_auth(self, sqlite_db):
        """Test API sync with basic authentication."""
        sync_service = SyncService(sqlite_db)

        # Create API source with basic auth
        source_id = await sqlite_db.create("sources", {
            "title": "GitHub API",
            "source_type": "api",
            "connection_config": json.dumps({
                "endpoint": "https://api.github.com/repos/test/repo/issues",
                "method": "GET",
                "auth_type": "basic",
                "username": "test_user",
                "password": "encrypted_password",
                "response_path": "$[*]",
                "text_fields": ["title", "body"]
            }),
            "sync_config": json.dumps({"status": "idle"})
        })

        # Mock API response
        mock_response = [
            {"title": "Issue 1", "body": "Description of issue 1"},
            {"title": "Issue 2", "body": "Description of issue 2"}
        ]

        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
            mock_fetch.return_value = mock_response

            result = await sync_service.execute_sync(source_id)

        assert result.success == True
        assert result.records_synced == 2

        # Verify full_text contains issue data
        source = await sqlite_db.query(
            "SELECT full_text FROM sources WHERE id = ?",
            [source_id]
        )

        full_text = source[0]["full_text"]
        assert "Issue 1" in full_text
        assert "Issue 2" in full_text

    async def test_sync_api_oauth2(self, sqlite_db):
        """Test API sync with OAuth 2.0 bearer token."""
        sync_service = SyncService(sqlite_db)

        source_id = await sqlite_db.create("sources", {
            "title": "OAuth API",
            "source_type": "api",
            "connection_config": json.dumps({
                "endpoint": "https://api.example.com/data",
                "method": "GET",
                "auth_type": "bearer",
                "bearer_token": "encrypted_access_token",
                "response_path": "$.data[*]",
                "text_fields": ["name", "description"]
            }),
            "sync_config": json.dumps({"status": "idle"})
        })

        mock_response = {
            "data": [
                {"name": "Item 1", "description": "First item"},
                {"name": "Item 2", "description": "Second item"}
            ]
        }

        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
            mock_fetch.return_value = mock_response["data"]

            result = await sync_service.execute_sync(source_id)

        assert result.success == True

    async def test_sync_api_token_refresh(self, sqlite_db):
        """Test API sync with automatic token refresh."""
        sync_service = SyncService(sqlite_db)

        source_id = await sqlite_db.create("sources", {
            "title": "OAuth API",
            "source_type": "api",
            "connection_config": json.dumps({
                "endpoint": "https://api.example.com/data",
                "auth_type": "oauth2",
                "access_token": "expired_token",
                "refresh_token": "valid_refresh_token",
                "token_expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat()
            }),
            "sync_config": json.dumps({"status": "idle"})
        })

        # Mock token refresh
        with patch("open_notebook.sources.api_source.APISource.refresh_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new_access_token",
                "expires_in": 3600
            }

            with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
                mock_fetch.return_value = []

                result = await sync_service.execute_sync(source_id)

        assert result.success == True
        # Verify token was refreshed
        mock_refresh.assert_called_once()

    async def test_sync_api_rate_limit_handling(self, sqlite_db):
        """Test API sync with rate limit handling."""
        sync_service = SyncService(sqlite_db)

        source_id = await sqlite_db.create("sources", {
            "title": "Rate Limited API",
            "source_type": "api",
            "connection_config": json.dumps({
                "endpoint": "https://api.example.com/data",
                "auth_type": "bearer",
                "bearer_token": "token"
            }),
            "sync_config": json.dumps({"status": "idle"})
        })

        # Mock rate limit error
        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
            # First call: rate limit error
            # Second call: success
            mock_fetch.side_effect = [
                Exception("Rate limit exceeded. Retry after 60 seconds"),
                [{"data": "success"}]
            ]

            # Should retry after rate limit
            with patch("asyncio.sleep") as mock_sleep:
                result = await sync_service.execute_sync(source_id)

            # Should have waited before retry
            mock_sleep.assert_called()


@pytest.mark.asyncio
class TestSyncRetryLogic:
    """Test sync retry logic and error handling."""

    async def test_sync_retry_on_transient_error(self, sqlite_db):
        """Test retry logic for transient errors."""
        sync_service = SyncService(sqlite_db)

        source_id = await sqlite_db.create("sources", {
            "title": "Flaky API",
            "source_type": "api",
            "connection_config": json.dumps({
                "endpoint": "https://api.example.com/data"
            }),
            "sync_config": json.dumps({"status": "idle"})
        })

        call_count = 0

        def mock_fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count < 3:
                raise Exception("Temporary network error")

            return [{"data": "success"}]

        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch_patch:
            mock_fetch_patch.side_effect = mock_fetch

            result = await sync_service.execute_sync(
                source_id,
                max_retries=5,
                retry_delay=0.1  # Short delay for testing
            )

        assert result.success == True
        assert call_count == 3  # Failed twice, succeeded on third

    async def test_sync_max_retries_exceeded(self, sqlite_db):
        """Test that sync fails after max retries."""
        sync_service = SyncService(sqlite_db)

        source_id = await sqlite_db.create("sources", {
            "title": "Broken API",
            "source_type": "api",
            "connection_config": json.dumps({
                "endpoint": "https://api.example.com/data"
            }),
            "sync_config": json.dumps({"status": "idle"})
        })

        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
            mock_fetch.side_effect = Exception("Persistent error")

            result = await sync_service.execute_sync(
                source_id,
                max_retries=3,
                retry_delay=0.1
            )

        assert result.success == False
        assert "Persistent error" in result.error

    async def test_sync_exponential_backoff(self, sqlite_db):
        """Test exponential backoff in retry logic."""
        sync_service = SyncService(sqlite_db)

        source_id = await sqlite_db.create("sources", {
            "title": "Test API",
            "source_type": "api",
            "connection_config": json.dumps({
                "endpoint": "https://api.example.com/data"
            }),
            "sync_config": json.dumps({"status": "idle"})
        })

        sleep_times = []

        async def mock_sleep(seconds):
            sleep_times.append(seconds)

        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
            mock_fetch.side_effect = Exception("Error")

            with patch("asyncio.sleep", new=mock_sleep):
                result = await sync_service.execute_sync(
                    source_id,
                    max_retries=4,
                    retry_delay=1.0
                )

        # Verify exponential backoff: 1s, 2s, 4s, 8s
        assert len(sleep_times) >= 3
        assert sleep_times[0] == 1.0
        assert sleep_times[1] == 2.0
        assert sleep_times[2] == 4.0


@pytest.mark.asyncio
class TestSyncScheduler:
    """Test sync scheduler functionality."""

    async def test_scheduler_runs_due_syncs(self, sqlite_db):
        """Test that scheduler executes syncs that are due."""
        sync_service = SyncService(sqlite_db)

        # Create source with sync due now
        source_id = await sqlite_db.create("sources", {
            "title": "Due Sync",
            "source_type": "api",
            "connection_config": json.dumps({"endpoint": "https://api.example.com/data"}),
            "sync_config": json.dumps({
                "frequency": "0 * * * *",  # Hourly
                "last_sync": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                "next_sync": datetime.utcnow().isoformat(),
                "status": "scheduled"
            })
        })

        # Mock fetch
        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
            mock_fetch.return_value = []

            # Run scheduler
            results = await sync_service.run_scheduled_syncs()

        assert len(results) >= 1
        assert any(r["source_id"] == source_id for r in results)

    async def test_scheduler_skips_future_syncs(self, sqlite_db):
        """Test that scheduler doesn't execute future syncs."""
        sync_service = SyncService(sqlite_db)

        # Create source with sync in future
        source_id = await sqlite_db.create("sources", {
            "title": "Future Sync",
            "source_type": "api",
            "connection_config": json.dumps({"endpoint": "https://api.example.com/data"}),
            "sync_config": json.dumps({
                "frequency": "0 * * * *",
                "next_sync": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "status": "scheduled"
            })
        })

        # Run scheduler
        results = await sync_service.run_scheduled_syncs()

        # Should not include future sync
        assert not any(r["source_id"] == source_id for r in results)

    async def test_scheduler_handles_concurrent_syncs(self, sqlite_db):
        """Test scheduler handles multiple concurrent syncs."""
        sync_service = SyncService(sqlite_db)

        # Create multiple sources due for sync
        source_ids = []
        for i in range(5):
            source_id = await sqlite_db.create("sources", {
                "title": f"Source {i}",
                "source_type": "api",
                "connection_config": json.dumps({"endpoint": f"https://api.example.com/data{i}"}),
                "sync_config": json.dumps({
                    "next_sync": datetime.utcnow().isoformat(),
                    "status": "scheduled"
                })
            })
            source_ids.append(source_id)

        # Mock fetch
        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
            mock_fetch.return_value = []

            # Run scheduler (should handle all concurrently)
            results = await sync_service.run_scheduled_syncs(max_concurrent=3)

        assert len(results) == 5


@pytest.mark.asyncio
class TestSyncMonitoring:
    """Test sync monitoring and metrics."""

    async def test_sync_history_tracking(self, sqlite_db):
        """Test that sync history is tracked."""
        sync_service = SyncService(sqlite_db)

        source_id = await sqlite_db.create("sources", {
            "title": "Test Source",
            "source_type": "api",
            "connection_config": json.dumps({"endpoint": "https://api.example.com/data"}),
            "sync_config": json.dumps({"status": "idle"})
        })

        # Execute multiple syncs
        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
            mock_fetch.return_value = []

            for _ in range(3):
                await sync_service.execute_sync(source_id)

        # Get sync history
        history = await sync_service.get_sync_history(source_id, limit=10)

        assert len(history) == 3
        assert all("timestamp" in h for h in history)
        assert all("status" in h for h in history)

    async def test_sync_metrics(self, sqlite_db):
        """Test sync metrics collection."""
        sync_service = SyncService(sqlite_db)

        source_id = await sqlite_db.create("sources", {
            "title": "Test Source",
            "source_type": "api",
            "connection_config": json.dumps({"endpoint": "https://api.example.com/data"}),
            "sync_config": json.dumps({"status": "idle"})
        })

        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
            mock_fetch.return_value = [{"data": f"item {i}"} for i in range(100)]

            result = await sync_service.execute_sync(source_id)

        # Verify metrics
        assert result.records_synced == 100
        assert result.duration is not None
        assert result.duration > 0

    async def test_sync_failure_alerts(self, sqlite_db):
        """Test alerts after repeated sync failures."""
        sync_service = SyncService(sqlite_db)

        source_id = await sqlite_db.create("sources", {
            "title": "Failing Source",
            "source_type": "api",
            "connection_config": json.dumps({"endpoint": "https://api.example.com/data"}),
            "sync_config": json.dumps({
                "status": "idle",
                "failure_count": 0
            })
        })

        # Simulate repeated failures
        with patch("open_notebook.sources.api_source.APISource.fetch_data") as mock_fetch:
            mock_fetch.side_effect = Exception("Sync error")

            for _ in range(10):
                await sync_service.execute_sync(source_id, max_retries=0)

        # Get sync config
        source = await sqlite_db.query(
            "SELECT sync_config FROM sources WHERE id = ?",
            [source_id]
        )

        sync_config = json.loads(source[0]["sync_config"])

        # Should have high failure count
        assert sync_config.get("failure_count", 0) >= 10

        # Should be disabled after 10 consecutive failures
        assert sync_config.get("status") == "disabled"
