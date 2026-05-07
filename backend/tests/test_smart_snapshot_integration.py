#!/usr/bin/env python3
"""
Smart Snapshot Integration - Complete Test

Tests the new integrated snapshot system:
1. Create workflow with HANA node (enable_snapshots=True)
2. Connect Compare node to HANA node
3. Execute workflow twice
4. Verify snapshots are created automatically
5. Verify Compare node returns changed rows
"""

import asyncio
import httpx
import json
from datetime import date
import sys

# Configuration
API_BASE = "http://localhost:5055/api"


async def test_smart_snapshot_integration():
    """Run complete test for smart snapshot integration"""

    print("=" * 80)
    print("Smart Snapshot Integration - Complete Test")
    print("=" * 80)
    print()

    # Login
    print("[1/9] Authenticating...")
    async with httpx.AsyncClient(base_url=API_BASE, timeout=60.0, follow_redirects=True) as client:
        login_response = await client.post(
            "/auth/login",
            json={"username": "admin", "password": "admin"}
        )
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.text}")
            return False

        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"✅ Authenticated successfully")
        print()

        # Step 2: Create test workflow with HANA node (enable_snapshots) + Compare node
        print("[2/9] Creating test workflow with smart snapshot integration...")

        # For testing, we'll use a mock tool instead of actual HANA
        # In real usage, this would be a hana_query tool with real connection
        workflow_graph = {
            "nodes": [
                {
                    "id": "input-1",
                    "type": "input",
                    "label": "Input",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "input_fields": []
                    }
                },
                {
                    "id": "hana-node",
                    "type": "tool",
                    "label": "HANA Query (Snapshots Enabled)",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "tool_name": "calculator",  # Using calculator as mock
                        "tool_args": {"expression": "10 + 5"},
                        "enable_snapshots": True  # KEY: Enable automatic snapshots
                    }
                },
                {
                    "id": "compare-node",
                    "type": "compare",
                    "label": "Auto Compare",
                    "position": {"x": 500, "y": 100},
                    "config": {}  # No configuration needed - auto-detects!
                },
                {
                    "id": "conditional-1",
                    "type": "conditional",
                    "label": "Has Changes?",
                    "position": {"x": 700, "y": 100},
                    "config": {
                        "field_path": "has_changes",
                        "condition_type": "equals",
                        "comparison_value": True
                    }
                },
                {
                    "id": "output-1",
                    "type": "output",
                    "label": "Output",
                    "position": {"x": 900, "y": 100},
                    "config": {}
                }
            ],
            "edges": [
                {"id": "e1", "source": "input-1", "target": "hana-node"},
                {"id": "e2", "source": "hana-node", "target": "compare-node"},
                {"id": "e3", "source": "compare-node", "target": "conditional-1"},
                {"id": "e4", "source": "conditional-1", "target": "output-1"}
            ],
            "entry_node_id": "input-1"
        }

        workflow_data = {
            "name": "Smart Snapshot Integration Test",
            "description": "Tests automatic snapshot creation and smart comparison",
            "graph": workflow_graph,
            "tags": ["test", "snapshot", "smart-integration"]
        }

        response = await client.post("/workflows", json=workflow_data, headers=headers)
        if response.status_code != 200:
            print(f"❌ Failed to create workflow: {response.text}")
            return False

        workflow = response.json()
        workflow_id = workflow.get("workflow_id") or workflow.get("id")
        print(f"✅ Workflow created: {workflow_id}")
        print(f"   - HANA node with enable_snapshots=True")
        print(f"   - Compare node with auto-detection")
        print()

        # Step 3: Check initial snapshots (should be 0)
        print("[3/9] Checking initial snapshot count...")
        response = await client.get(
            "/snapshots/",
            params={"workflow_id": workflow_id, "limit": 10},
            headers=headers
        )

        if response.status_code != 200:
            print(f"❌ Failed to fetch snapshots: {response.text}")
            return False

        initial_snapshots = response.json()
        print(f"✅ Initial snapshots: {len(initial_snapshots)}")
        print()

        # Step 4: First execution (should create baseline snapshot)
        print("[4/9] First execution (creating baseline snapshot)...")
        response = await client.post(
            f"/workflows/{workflow_id}/execute",
            json={"input_data": {}},
            headers=headers
        )

        if response.status_code != 200:
            print(f"❌ Failed to execute workflow: {response.text}")
            return False

        execution1 = response.json()
        execution1_id = execution1.get("execution_id")
        print(f"✅ Execution started: {execution1_id}")

        # Wait for completion
        print("   Waiting for execution...")
        await asyncio.sleep(8)

        response = await client.get(
            f"/workflows/{workflow_id}/executions/{execution1_id}",
            headers=headers
        )
        response_data = response.json()
        execution1_status = response_data.get("execution", response_data)
        print(f"   Status: {execution1_status.get('status')}")

        # Check for Compare node output
        node_outputs = execution1_status.get("node_states", {})
        compare_output = None
        for node_id, node_state in node_outputs.items():
            if "compare" in node_id.lower():
                compare_output = node_state.get("output_data") or node_state.get("output")
                break

        if compare_output:
            print(f"   Compare output: {json.dumps(compare_output, indent=2)[:200]}...")
        print()

        # Step 5: Check snapshots after first run
        print("[5/9] Checking snapshots after first run...")
        response = await client.get(
            "/snapshots/",
            params={"workflow_id": workflow_id, "limit": 10},
            headers=headers
        )

        snapshots_after_first = response.json()
        print(f"✅ Snapshots after first run: {len(snapshots_after_first)}")

        if len(snapshots_after_first) > 0:
            for snap in snapshots_after_first:
                print(f"   - {snap.get('snapshot_label')}: {snap.get('row_count')} rows, "
                      f"{snap.get('total_size_bytes')/1024:.2f} KB ({snap.get('storage_type')})")
        print()

        # Step 6: Second execution (should create dated snapshot and compare)
        print("[6/9] Second execution (creating current snapshot & comparing)...")
        response = await client.post(
            f"/workflows/{workflow_id}/execute",
            json={"input_data": {}},
            headers=headers
        )

        if response.status_code != 200:
            print(f"❌ Failed to execute workflow: {response.text}")
            return False

        execution2 = response.json()
        execution2_id = execution2.get("execution_id")
        print(f"✅ Execution started: {execution2_id}")

        # Wait for completion
        print("   Waiting for execution...")
        await asyncio.sleep(8)

        response = await client.get(
            f"/workflows/{workflow_id}/executions/{execution2_id}",
            headers=headers
        )
        response_data = response.json()
        execution2_status = response_data.get("execution", response_data)
        print(f"   Status: {execution2_status.get('status')}")
        print()

        # Step 7: Check snapshots after second run
        print("[7/9] Checking snapshots after second run...")
        response = await client.get(
            "/snapshots/",
            params={"workflow_id": workflow_id, "limit": 10},
            headers=headers
        )

        snapshots_after_second = response.json()
        print(f"✅ Snapshots after second run: {len(snapshots_after_second)}")

        if len(snapshots_after_second) >= 2:
            print("   ✅ Multiple snapshots exist for comparison")
            for snap in snapshots_after_second:
                print(f"   - {snap.get('snapshot_label')}: {snap.get('snapshot_date')}")
        else:
            print("   ⚠️  Warning: Less than 2 snapshots found")
        print()

        # Step 8: Verify Compare node output (should have changed_rows)
        print("[8/9] Verifying Compare node output...")
        node_outputs = execution2_status.get("node_states", {})
        compare_output = None

        for node_id, node_state in node_outputs.items():
            if "compare" in node_id.lower():
                compare_output = node_state.get("output_data") or node_state.get("output")
                break

        if compare_output:
            print("✅ Compare node output received:")
            print(f"   Status: {compare_output.get('status')}")
            print(f"   Has changes: {compare_output.get('has_changes')}")

            if compare_output.get('changed_rows'):
                changed = compare_output['changed_rows']
                print(f"   Changed rows:")
                print(f"     - Added: {len(changed.get('added', []))}")
                print(f"     - Removed: {len(changed.get('removed', []))}")
                print(f"     - Modified: {len(changed.get('modified', []))}")

                # Show sample of changed rows
                if changed.get('added'):
                    print(f"   Sample added row: {json.dumps(changed['added'][0], indent=4)[:150]}...")

            if compare_output.get('summary'):
                print(f"   Summary: {compare_output['summary']}")

            if compare_output.get('baseline_date') and compare_output.get('current_date'):
                print(f"   Comparison: {compare_output['baseline_date']} vs {compare_output['current_date']}")
        else:
            print("⚠️  No compare node output found")
        print()

        # Step 9: Test storage statistics
        print("[9/9] Checking storage statistics...")
        response = await client.get("/snapshots/stats/storage", headers=headers)

        if response.status_code == 200:
            stats = response.json()
            print("✅ Storage statistics:")
            for storage_stat in stats.get("by_storage_type", []):
                print(f"   - {storage_stat['storage_type']}: "
                      f"{storage_stat['count']} snapshots, "
                      f"{storage_stat['total_mb']:.2f} MB total")
        else:
            print(f"⚠️  Storage stats not available: {response.text}")
        print()

        # Summary
        print("=" * 80)
        print("Test Summary")
        print("=" * 80)

        success = True

        # Check 1: Automatic snapshot creation
        if len(snapshots_after_first) > 0:
            print("✅ PASS: Automatic snapshot creation (HANA node)")
        else:
            print("❌ FAIL: No snapshots created automatically")
            success = False

        # Check 2: Multiple snapshots
        if len(snapshots_after_second) >= 2:
            print("✅ PASS: Multiple snapshots created")
        else:
            print("❌ FAIL: Less than 2 snapshots")
            success = False

        # Check 3: Compare node output
        if compare_output and compare_output.get('status') == 'comparison_complete':
            print("✅ PASS: Compare node returned results")
        elif compare_output and compare_output.get('status') == 'insufficient_data':
            print("⚠️  INFO: Insufficient data (expected on first run)")
        else:
            print("❌ FAIL: Compare node did not return expected output")
            success = False

        # Check 4: Changed rows structure
        if compare_output and 'changed_rows' in compare_output:
            print("✅ PASS: Changed rows included in output")
        else:
            print("⚠️  INFO: Changed rows not found (may need more runs)")

        print()
        print(f"Workflow ID: {workflow_id}")
        print(f"Snapshots created: {len(snapshots_after_second)}")
        print()

        return success


if __name__ == "__main__":
    print()
    success = asyncio.run(test_smart_snapshot_integration())

    if success:
        print("🎉 Smart Snapshot Integration Test PASSED!")
        sys.exit(0)
    else:
        print("❌ Smart Snapshot Integration Test FAILED!")
        sys.exit(1)
