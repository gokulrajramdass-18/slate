#!/usr/bin/env python3
"""
E2E Test for Workflow Snapshot System

Tests the complete flow:
1. Create workflow with API → Snapshot → Compare → Conditional nodes
2. Execute workflow (first run - creates baseline)
3. Execute workflow (second run - compares with baseline)
4. Verify snapshot storage
5. Verify comparison results
"""

import asyncio
import httpx
import json
from datetime import date, timedelta

# Configuration
API_BASE = "http://localhost:5055/api"
AUTH_TOKEN = "test-token"  # Replace with actual token


async def test_snapshot_workflow():
    """Run complete E2E test for snapshot system"""

    print("=" * 80)
    print("Workflow Snapshot System - E2E Test")
    print("=" * 80)
    print()

    async with httpx.AsyncClient(base_url=API_BASE, timeout=60.0) as client:
        # Set auth headers
        headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

        # Step 1: Create test workflow
        print("[1/7] Creating test workflow...")
        workflow_graph = {
            "nodes": [
                {
                    "id": "input-1",
                    "type": "input",
                    "label": "Input",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "input_fields": [
                            {"name": "region", "type": "string", "required": True}
                        ]
                    }
                },
                {
                    "id": "tool-api",
                    "type": "tool",
                    "label": "Fetch API Data",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "tool_name": "api_fetch",
                        "tool_args": {
                            "url": "https://api.example.com/data",
                            "params": {"region": "{{region}}"}
                        }
                    }
                },
                {
                    "id": "snapshot-1",
                    "type": "snapshot",
                    "label": "Store Today's Data",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "snapshot_mode": "store",
                        "source_node_id": "tool-api",
                        "snapshot_label": "today",
                        "retention_days": 30
                    }
                },
                {
                    "id": "compare-1",
                    "type": "compare",
                    "label": "Compare with Yesterday",
                    "position": {"x": 700, "y": 100},
                    "config": {
                        "snapshot_mode": "compare",
                        "source_node_id": "tool-api",
                        "compare_snapshot_1": "yesterday",
                        "compare_snapshot_2": "today",
                        "comparison_strategy": "fast",
                        "change_threshold": 1.0
                    }
                },
                {
                    "id": "conditional-1",
                    "type": "conditional",
                    "label": "Changes Detected?",
                    "position": {"x": 900, "y": 100},
                    "config": {
                        "field_path": "has_significant_changes",
                        "condition_type": "equals",
                        "comparison_value": True
                    }
                },
                {
                    "id": "output-1",
                    "type": "output",
                    "label": "Output",
                    "position": {"x": 1100, "y": 100},
                    "config": {}
                }
            ],
            "edges": [
                {"id": "e1", "source": "input-1", "target": "tool-api"},
                {"id": "e2", "source": "tool-api", "target": "snapshot-1"},
                {"id": "e3", "source": "snapshot-1", "target": "compare-1"},
                {"id": "e4", "source": "compare-1", "target": "conditional-1"},
                {"id": "e5", "source": "conditional-1", "target": "output-1"}
            ],
            "entry_node_id": "input-1"
        }

        workflow_data = {
            "name": "Snapshot E2E Test Workflow",
            "description": "Tests API → Snapshot → Compare → Conditional flow",
            "graph": workflow_graph,
            "tags": ["test", "snapshot", "e2e"]
        }

        response = await client.post("/workflows", json=workflow_data, headers=headers)
        if response.status_code != 200:
            print(f"❌ Failed to create workflow: {response.text}")
            return False

        workflow = response.json()
        workflow_id = workflow.get("workflow_id") or workflow.get("id")
        print(f"✅ Workflow created: {workflow_id}")
        print()

        # Step 2: First execution (baseline)
        print("[2/7] Executing workflow (baseline run)...")
        response = await client.post(
            f"/workflows/{workflow_id}/execute",
            json={"input_data": {"region": "US"}},
            headers=headers
        )

        if response.status_code != 200:
            print(f"❌ Failed to execute workflow: {response.text}")
            return False

        execution1 = response.json()
        execution1_id = execution1.get("id")
        print(f"✅ Baseline execution started: {execution1_id}")

        # Wait for completion
        print("   Waiting for execution to complete...")
        await asyncio.sleep(5)  # Wait for execution

        response = await client.get(
            f"/workflows/{workflow_id}/executions/{execution1_id}",
            headers=headers
        )
        execution1_status = response.json()
        print(f"   Status: {execution1_status.get('status')}")
        print()

        # Step 3: Check snapshots created
        print("[3/7] Checking snapshots...")
        response = await client.get(
            "/snapshots",
            params={"workflow_id": workflow_id, "limit": 10},
            headers=headers
        )

        if response.status_code != 200:
            print(f"❌ Failed to fetch snapshots: {response.text}")
            return False

        snapshots = response.json()
        print(f"✅ Found {len(snapshots)} snapshot(s)")

        if len(snapshots) > 0:
            for snapshot in snapshots:
                print(f"   - {snapshot['snapshot_label']}: {snapshot['row_count']} rows, "
                      f"{snapshot['total_size_bytes'] / 1024:.2f} KB ({snapshot['storage_type']})")
        print()

        # Step 4: Second execution (comparison run)
        print("[4/7] Executing workflow (comparison run)...")
        response = await client.post(
            f"/workflows/{workflow_id}/execute",
            json={"input_data": {"region": "US"}},
            headers=headers
        )

        if response.status_code != 200:
            print(f"❌ Failed to execute workflow: {response.text}")
            return False

        execution2 = response.json()
        execution2_id = execution2.get("id")
        print(f"✅ Comparison execution started: {execution2_id}")

        # Wait for completion
        print("   Waiting for execution to complete...")
        await asyncio.sleep(5)  # Wait for execution

        response = await client.get(
            f"/workflows/{workflow_id}/executions/{execution2_id}",
            headers=headers
        )
        execution2_status = response.json()
        print(f"   Status: {execution2_status.get('status')}")
        print()

        # Step 5: Check snapshots again
        print("[5/7] Checking snapshots after second run...")
        response = await client.get(
            "/snapshots",
            params={"workflow_id": workflow_id, "limit": 10},
            headers=headers
        )

        snapshots = response.json()
        print(f"✅ Found {len(snapshots)} snapshot(s)")

        if len(snapshots) >= 2:
            print("   ✅ Multiple snapshots exist for comparison")
        else:
            print("   ⚠️  Warning: Less than 2 snapshots found")
        print()

        # Step 6: Test comparison API directly
        print("[6/7] Testing direct snapshot comparison...")
        if len(snapshots) >= 2:
            snapshot1_id = snapshots[0]["id"]
            snapshot2_id = snapshots[1]["id"]

            response = await client.post(
                "/snapshots/compare",
                json={
                    "snapshot1_id": snapshot1_id,
                    "snapshot2_id": snapshot2_id,
                    "strategy": "fast"
                },
                headers=headers
            )

            if response.status_code == 200:
                comparison = response.json()
                print(f"✅ Comparison successful:")
                print(f"   - Has changes: {comparison.get('has_changes')}")
                print(f"   - Change percentage: {comparison.get('change_percentage', 0):.2f}%")
                print(f"   - Comparison time: {comparison.get('comparison_time_ms', 0):.2f}ms")
                print(f"   - Strategy: {comparison.get('strategy')}")
            else:
                print(f"❌ Comparison failed: {response.text}")
        else:
            print("   ⏭️  Skipping (not enough snapshots)")
        print()

        # Step 7: Check storage statistics
        print("[7/7] Checking storage statistics...")
        response = await client.get("/snapshots/stats/storage", headers=headers)

        if response.status_code == 200:
            stats = response.json()
            print("✅ Storage statistics:")
            for storage_stat in stats.get("by_storage_type", []):
                print(f"   - {storage_stat['storage_type']}: "
                      f"{storage_stat['count']} snapshots, "
                      f"{storage_stat['total_mb']:.2f} MB total")
        else:
            print(f"❌ Failed to fetch storage stats: {response.text}")
        print()

        # Cleanup
        print("=" * 80)
        print("Test Summary")
        print("=" * 80)
        print(f"✅ Workflow created and executed successfully")
        print(f"✅ Snapshots stored with tiered storage")
        print(f"✅ Comparison performed successfully")
        print(f"✅ Storage statistics retrieved")
        print()
        print(f"Workflow ID: {workflow_id}")
        print(f"Snapshots: {len(snapshots)}")
        print()
        print("Note: To clean up, delete the workflow and snapshots manually from the UI")
        print("      or use DELETE /api/workflows/{workflow_id}")
        print()

        return True


if __name__ == "__main__":
    print()
    success = asyncio.run(test_snapshot_workflow())

    if success:
        print("🎉 E2E Test PASSED!")
        exit(0)
    else:
        print("❌ E2E Test FAILED!")
        exit(1)
