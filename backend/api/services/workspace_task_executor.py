"""
Workspace Task Executor Service

Automatically executes tasks in AI-guided workspaces by:
- Monitoring tasks that are ready to start
- Triggering agent execution for assigned tasks
- Updating task status based on execution results
- Managing task dependencies and flow
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from open_notebook.database.repository import repo_execute, repo_query
from api.services.http_client import http_client_manager

# Configure logging for this module
logging.basicConfig(
    level=logging.INFO,  # Back to INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # INFO level


class WorkspaceTaskExecutor:
    """
    Background service that automatically executes workspace tasks
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._executing_tasks: Set[str] = set()  # Track tasks currently executing

    async def start(self):
        """Start the task executor background service"""
        if self._running:
            logger.warning("Task executor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._execution_loop())
        logger.info("✅ Workspace task executor started")

    async def stop(self):
        """Stop the task executor background service"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("⏸️  Workspace task executor stopped")

    async def _execution_loop(self):
        """Main execution loop - checks for tasks to execute every 2 seconds"""
        logger.info("🔄 Task execution loop started")

        while self._running:
            try:
                await self._process_pending_tasks()
                await asyncio.sleep(2)  # Check every 2 seconds (faster polling)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in task execution loop: {e}", exc_info=True)
                await asyncio.sleep(2)

    async def _process_pending_tasks(self):
        """Find and execute tasks that are ready to start"""
        print(f"[DEBUG] _process_pending_tasks called at {datetime.utcnow()}")
        logger.debug("_process_pending_tasks called")
        try:
            # Debug: Check database path
            try:
                db_path_result = await repo_query("PRAGMA database_list", fetch_one=True)
                print(f"[DEBUG] Database path: {db_path_result}")
            except Exception as e:
                print(f"[DEBUG] Could not get database path: {e}")

            # Find all workspaces with pending tasks
            print("[DEBUG] About to query for workspaces with pending tasks")
            workspaces = await repo_query("""
                SELECT DISTINCT wp.workspace_id
                FROM workspace_plans wp
                JOIN workspace_plan_tasks wpt ON wpt.plan_id = wp.id
                WHERE wpt.status = 'pending'
                AND wp.status != 'completed'
            """)
            print(f"[DEBUG] Query returned {len(workspaces) if workspaces else 0} workspaces")

            # Debug: Check total count of workspace_plans
            try:
                count_result = await repo_query("SELECT COUNT(*) as count FROM workspace_plans", fetch_one=True)
                print(f"[DEBUG] Total workspace_plans in DB: {count_result['count'] if count_result else 'unknown'}")
                count_tasks = await repo_query("SELECT COUNT(*) as count FROM workspace_plan_tasks WHERE status = 'pending'", fetch_one=True)
                print(f"[DEBUG] Total pending tasks in DB: {count_tasks['count'] if count_tasks else 'unknown'}")
            except Exception as e:
                print(f"[DEBUG] Could not get counts: {e}")

            if workspaces:
                logger.info(f"🔍 Found {len(workspaces)} workspace(s) with pending tasks")
                for workspace in workspaces:
                    workspace_id = workspace["workspace_id"]
                    logger.info(f"  Processing workspace: {workspace_id}")
                    await self._process_workspace_tasks(workspace_id)
            else:
                # Log every 10th check (every ~20 seconds) to avoid spam
                if not hasattr(self, '_check_counter'):
                    self._check_counter = 0
                self._check_counter += 1
                if self._check_counter % 10 == 0:
                    logger.debug("No workspaces with pending tasks found")
                    print(f"[DEBUG] No workspaces found (check #{self._check_counter})")

        except Exception as e:
            print(f"[DEBUG] Exception in _process_pending_tasks: {e}")
            logger.error(f"Error processing pending tasks: {e}", exc_info=True)

    async def _process_workspace_tasks(self, workspace_id: str):
        """Process tasks for a specific workspace"""
        try:
            # Get workspace plan
            plan = await repo_query(
                "SELECT id, status FROM workspace_plans WHERE workspace_id = :workspace_id",
                {"workspace_id": workspace_id},
                fetch_one=True
            )

            if not plan or plan["status"] == "completed":
                return

            # Get all tasks for this workspace
            tasks = await repo_query("""
                SELECT
                    id, name, phase_name, status, dependencies,
                    assigned_agent_id, description, required_tools, required_sources
                FROM workspace_plan_tasks
                WHERE plan_id = :plan_id
                ORDER BY created ASC
            """, {"plan_id": plan["id"]})

            # Parse dependencies
            import json
            for task in tasks:
                task["dependencies"] = json.loads(task.get("dependencies") or "[]")

            # Find tasks ready to execute
            ready_tasks = self._find_ready_tasks(tasks)

            # Execute ready tasks (limit to 5 concurrent tasks per workspace for faster execution)
            executing_count = sum(1 for t in tasks if t["id"] in self._executing_tasks)
            available_slots = 5 - executing_count  # Increased from 2 to 5 for better parallelization

            for task in ready_tasks[:available_slots]:
                if task["id"] not in self._executing_tasks:
                    asyncio.create_task(self._execute_task(workspace_id, task))

        except Exception as e:
            logger.error(f"Error processing workspace {workspace_id}: {e}", exc_info=True)

    def _find_ready_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """Find tasks that are ready to start (dependencies met, not already executing)"""
        ready = []
        completed_task_ids = {t["id"] for t in tasks if t["status"] == "completed"}
        completed_task_names = {t["name"] for t in tasks if t["status"] == "completed"}
        failed_task_ids = {t["id"] for t in tasks if t["status"] == "failed"}
        failed_task_names = {t["name"] for t in tasks if t["status"] == "failed"}

        # Create name-to-id mapping for dependency resolution
        task_name_to_id = {t["name"]: t["id"] for t in tasks}

        logger.info(f"  📋 Checking {len(tasks)} tasks")
        logger.info(f"  ✅ Completed task IDs: {completed_task_ids}")
        logger.info(f"  ✅ Completed task names: {completed_task_names}")
        logger.info(f"  ❌ Failed task IDs: {failed_task_ids}")

        for task in tasks:
            # Skip if not pending or already executing
            if task["status"] != "pending":
                logger.debug(f"  ⏭️  Skip task '{task['name']}' - status is {task['status']}")
                continue

            if task["id"] in self._executing_tasks:
                logger.debug(f"  ⏭️  Skip task '{task['name']}' - already executing")
                continue

            # Check dependencies (can be either task IDs or task names)
            dependencies = task.get("dependencies", [])
            logger.info(f"  🔗 Task '{task['name']}' has dependencies: {dependencies}")

            # Resolve dependencies - check if they are IDs or names
            resolved_deps = []
            for dep in dependencies:
                # Check if it's a UUID (task ID) or a name
                if dep in task_name_to_id.values():
                    # It's an ID
                    resolved_deps.append(dep)
                elif dep in task_name_to_id:
                    # It's a name, resolve to ID
                    resolved_deps.append(task_name_to_id[dep])
                else:
                    logger.warning(f"  ⚠️  Unknown dependency '{dep}' for task '{task['name']}'")

            # If any dependency failed, skip this task (it can't be executed)
            if any(dep in failed_task_ids or dep in failed_task_names for dep in dependencies):
                logger.info(f"  ⏭️  Task '{task['name']}' skipped - dependency failed")
                continue

            # Check if all dependencies are completed
            if all(dep in completed_task_ids or dep in completed_task_names for dep in dependencies):
                logger.info(f"  ✅ Task '{task['name']}' is READY - all dependencies met!")
                ready.append(task)
            else:
                unmet_deps = [dep for dep in dependencies if dep not in completed_task_ids and dep not in completed_task_names]
                logger.info(f"  ⏸️  Task '{task['name']}' waiting - unmet dependencies: {unmet_deps}")

        logger.info(f"  🎯 Found {len(ready)} ready task(s)")
        return ready

    async def _execute_task(self, workspace_id: str, task: Dict):
        """Execute a single task"""
        task_id = task["id"]
        task_name = task["name"]

        try:
            # Mark as executing
            self._executing_tasks.add(task_id)
            logger.info(f"▶️  Starting task: {task_name} (workspace: {workspace_id})")
            logger.info(f"   Task ID: {task_id}")

            # Update task status to in_progress
            await repo_execute("""
                UPDATE workspace_plan_tasks
                SET status = 'in_progress',
                    started_at = :started_at,
                    updated = :updated
                WHERE id = :task_id
            """, {
                "task_id": task_id,
                "started_at": datetime.utcnow().isoformat(),
                "updated": datetime.utcnow().isoformat()
            })

            # Execute the task
            logger.info(f"🚀 Calling _run_task_logic...")
            result = await self._run_task_logic(workspace_id, task)
            logger.info(f"✓ _run_task_logic returned: {result}")

            # Mark as completed and save result.
            # `result` is a TEXT column in SQLite — dicts/lists must be JSON-encoded
            # before binding (sqlite3 only accepts str/int/float/bytes/None).
            if result is None:
                result_value = None
            elif isinstance(result, (dict, list)):
                result_value = json.dumps(result)
            else:
                result_value = str(result)

            await repo_execute("""
                UPDATE workspace_plan_tasks
                SET status = 'completed',
                    result = :result,
                    completed_at = :completed_at,
                    updated = :updated
                WHERE id = :task_id
            """, {
                "task_id": task_id,
                "result": result_value,
                "completed_at": datetime.utcnow().isoformat(),
                "updated": datetime.utcnow().isoformat()
            })

            logger.info(f"✅ Completed task: {task_name} (workspace: {workspace_id})")

            # Check if all tasks in workspace are completed
            await self._check_workspace_completion(workspace_id)

        except Exception as e:
            logger.error(f"❌ Failed to execute task {task_name}: {e}", exc_info=True)
            print(f"❌ Task execution failed: {e}")

            # Store error message in task
            error_message = str(e)

            # Mark task as failed with error details
            await repo_execute("""
                UPDATE workspace_plan_tasks
                SET status = 'failed',
                    error = :error,
                    updated = :updated
                WHERE id = :task_id
            """, {
                "task_id": task_id,
                "error": error_message,
                "updated": datetime.utcnow().isoformat()
            })

            # Create a note documenting the failure
            import uuid
            error_note_id = str(uuid.uuid4())

            error_note_content = f"""<h2>{task_name}</h2>
<p><strong>Status:</strong> ❌ Failed<br>
<strong>Phase:</strong> {task["phase_name"]}<br>
<strong>Workspace:</strong> {workspace_id}</p>

<h3>Error Details</h3>
<div class="bg-red-50 border border-red-200 rounded p-4">
<p class="text-red-800 font-mono text-sm">{error_message}</p>
</div>

<h3>Task Description</h3>
<p>{task.get("description", "No description")}</p>

<hr>
<p><em>Task failed on {datetime.utcnow().strftime('%Y-%m-%d at %H:%M UTC')}</em></p>
"""

            try:
                # Get workspace plan to find execution_folder_id
                plan = await repo_query(
                    "SELECT execution_folder_id FROM workspace_plans WHERE workspace_id = :workspace_id",
                    {"workspace_id": workspace_id},
                    fetch_one=True
                )
                execution_folder_id = plan.get("execution_folder_id") if plan else None

                # Create error note
                await repo_execute("""
                    INSERT INTO notes (id, title, content, content_html, notebook_id, folder_id, created, updated)
                    VALUES (:id, :title, :content, :content_html, :notebook_id, :folder_id, :created, :updated)
                """, {
                    "id": error_note_id,
                    "title": f"❌ {task_name} (Failed)",
                    "content": error_note_content,
                    "content_html": error_note_content,
                    "notebook_id": workspace_id,  # Set notebook_id for direct querying
                    "folder_id": execution_folder_id,  # Assign to execution folder
                    "created": datetime.utcnow().isoformat(),
                    "updated": datetime.utcnow().isoformat()
                })

                # Link error note to workspace
                await repo_execute("""
                    INSERT OR IGNORE INTO notebook_note (notebook_id, note_id, created)
                    VALUES (:notebook_id, :note_id, :created)
                """, {
                    "notebook_id": workspace_id,
                    "note_id": error_note_id,
                    "created": datetime.utcnow().isoformat()
                })

                logger.info(f"Created error note for failed task: {task_name}")
            except Exception as note_error:
                logger.error(f"Failed to create error note: {note_error}", exc_info=True)

        finally:
            self._executing_tasks.discard(task_id)

    async def _run_task_logic(self, workspace_id: str, task: Dict) -> Dict:
        """
        Execute the actual task logic and generate outputs using assigned agents.

        Routes task to its assigned agent or team for execution.
        Creates notes with task results that appear in the workspace.
        """
        task_name = task["name"]
        description = task.get("description", "")
        phase = task["phase_name"]
        assigned_agent_id = task.get("assigned_agent_id")

        print(f"\n{'='*80}")
        print(f"🔨 STARTING _run_task_logic for task: {task_name}")
        print(f"   workspace_id: {workspace_id}, phase: {phase}")
        print(f"   assigned_agent_id: {assigned_agent_id}")
        print(f"{'='*80}\n")
        logger.info(f"🔨 STARTING _run_task_logic for task: {task_name}")
        logger.info(f"   workspace_id: {workspace_id}, phase: {phase}, agent: {assigned_agent_id}")

        # Execute task with assigned agent
        from api.services.agent_task_executor import get_agent_task_executor

        agent_executor = get_agent_task_executor()

        print(f"🤖 Routing task to agent executor...")
        logger.info(f"🤖 Routing task to assigned agent...")

        try:
            execution_result = await agent_executor.execute_task_with_agent(
                task=task,
                workspace_id=workspace_id,
                agent_id=assigned_agent_id
            )

            # Get the result text
            result_text = execution_result.get("result", "")
            agent_name = execution_result.get("agent_name", "Unknown Agent")
            agent_type = execution_result.get("agent_type", "unknown")

            print(f"✅ Agent '{agent_name}' ({agent_type}) completed task")
            logger.info(f"✅ Agent '{agent_name}' ({agent_type}) completed task '{task_name}'")

            # Wrap the result in HTML with agent attribution
            note_content = f"""<h2>{task_name}</h2>
<p><strong>Status:</strong> ✅ Completed<br>
<strong>Phase:</strong> {phase}<br>
<strong>Executed By:</strong> {agent_name} ({agent_type})</p>

{result_text}

<hr>
<p><em>Completed by {agent_name} on {datetime.utcnow().strftime('%Y-%m-%d at %H:%M UTC')}</em></p>
"""

        except Exception as e:
            print(f"❌ Agent execution failed: {e}")
            logger.error(f"❌ Agent execution failed for task '{task_name}': {e}", exc_info=True)

            # Fall back to generating generic content
            print(f"⚠️ Falling back to basic task completion...")
            note_content = await self._generate_ai_task_output(
                workspace_id=workspace_id,
                task_name=task_name,
                description=description,
                phase=phase,
                task=task
            )

        print(f"✓ Generated {len(note_content)} characters of AI-analyzed content")
        logger.info(f"✓ Generated {len(note_content)} characters of AI-analyzed content")

        # Create note with results
        import uuid
        note_id = str(uuid.uuid4())
        print(f"💾 Creating note with ID: {note_id}")
        logger.info(f"💾 Creating note with ID: {note_id}")

        try:
            # Get workspace plan to find execution_folder_id
            plan = await repo_query(
                "SELECT execution_folder_id FROM workspace_plans WHERE workspace_id = :workspace_id",
                {"workspace_id": workspace_id},
                fetch_one=True
            )
            execution_folder_id = plan.get("execution_folder_id") if plan else None

            # Create the note
            await repo_execute("""
                INSERT INTO notes (id, title, content, content_html, notebook_id, folder_id, created, updated)
                VALUES (:id, :title, :content, :content_html, :notebook_id, :folder_id, :created, :updated)
            """, {
                "id": note_id,
                "title": f"✅ {task_name}",
                "content": note_content,  # HTML content
                "content_html": note_content,  # Same HTML content
                "notebook_id": workspace_id,  # Set notebook_id for direct querying
                "folder_id": execution_folder_id,  # Assign to execution folder
                "created": datetime.utcnow().isoformat(),
                "updated": datetime.utcnow().isoformat()
            })
            print(f"✓ Note inserted into notes table")
            logger.info(f"✓ Note inserted into notes table")

            # Verify note was created
            verify_note = await repo_query(
                "SELECT id, title FROM notes WHERE id = :id",
                {"id": note_id},
                fetch_one=True
            )
            if verify_note:
                print(f"✓ Verified note exists: {verify_note['title']}")
                logger.info(f"✓ Verified note exists: {verify_note['title']}")
            else:
                print(f"❌ Note NOT found after insert!")
                logger.error(f"❌ Note NOT found after insert!")

            # Link note to workspace
            print(f"🔗 Linking note to workspace {workspace_id}")
            logger.info(f"🔗 Linking note to workspace {workspace_id}")
            await repo_execute("""
                INSERT OR IGNORE INTO notebook_note (notebook_id, note_id, created)
                VALUES (:notebook_id, :note_id, :created)
            """, {
                "notebook_id": workspace_id,
                "note_id": note_id,
                "created": datetime.utcnow().isoformat()
            })
            print(f"✓ Note linked to workspace")
            logger.info(f"✓ Note linked to workspace")

            # Verify link was created
            verify_link = await repo_query(
                "SELECT * FROM notebook_note WHERE notebook_id = :notebook_id AND note_id = :note_id",
                {"notebook_id": workspace_id, "note_id": note_id},
                fetch_one=True
            )
            if verify_link:
                print(f"✓ Verified link exists in notebook_note table")
                logger.info(f"✓ Verified link exists in notebook_note table")
            else:
                print(f"❌ Link NOT found after insert!")
                logger.error(f"❌ Link NOT found after insert!")

            # Count total notes for this workspace
            note_count = await repo_query(
                "SELECT COUNT(*) as count FROM notebook_note WHERE notebook_id = :notebook_id",
                {"notebook_id": workspace_id},
                fetch_one=True
            )
            print(f"📊 Workspace now has {note_count['count']} total notes")
            logger.info(f"📊 Workspace now has {note_count['count']} total notes")

            print(f"\n✨ Task execution completed successfully with note: {note_id}\n")
            logger.info(f"✨ Task execution completed successfully with note: {note_id}")

        except Exception as e:
            print(f"\n❌ EXCEPTION in _run_task_logic: {e}\n")
            logger.error(f"❌ EXCEPTION in _run_task_logic: {e}", exc_info=True)
            raise

        return {"success": True, "note_id": note_id, "phase": phase}

    async def _generate_ai_task_output(
        self,
        workspace_id: str,
        task_name: str,
        description: str,
        phase: str,
        task: Dict
    ) -> str:
        """
        Generate task output using AI-powered analysis of workspace sources and context.

        This method actually uses an LLM to analyze the data and generate meaningful insights.
        """
        try:
            # 1. Get workspace context
            workspace = await repo_query(
                "SELECT name, goal FROM notebooks WHERE id = :id",
                {"id": workspace_id},
                fetch_one=True
            )

            if not workspace:
                return await self._generate_task_output(task_name, description, phase, workspace_id)

            goal = workspace.get("goal", "")
            workspace_name = workspace.get("name", "Workspace")

            # 2. Get workspace sources
            sources = await repo_query("""
                SELECT s.id, s.title, s.source_type, s.full_text, s.asset_data
                FROM sources s
                JOIN notebook_source ns ON s.id = ns.source_id
                WHERE ns.notebook_id = :workspace_id
            """, {"workspace_id": workspace_id})

            # 3. Build context for LLM
            sources_context = []
            for source in sources:
                source_info = f"**{source['title']}** ({source['source_type']})"
                if source.get('full_text'):
                    # Limit content to first 2000 chars to avoid token limits
                    content_preview = source['full_text'][:2000]
                    if len(source['full_text']) > 2000:
                        content_preview += "... (truncated)"
                    source_info += f"\n{content_preview}"
                sources_context.append(source_info)

            sources_text = "\n\n---\n\n".join(sources_context) if sources_context else "No sources available"

            # 4. Create prompt for LLM
            prompt = f"""You are an AI assistant helping execute a task in a workspace.

**Workspace**: {workspace_name}
**Goal**: {goal}

**Task**: {task_name}
**Description**: {description}
**Phase**: {phase}

**Available Data Sources**:
{sources_text}

**Your Task**:
Analyze the available data and generate a detailed, actionable analysis for this task.

IMPORTANT REQUIREMENTS:
1. **Use Actual Data**: Reference specific data points, numbers, companies, or findings from the sources
2. **Be Specific**: Don't use generic statements like "patterns identified" - say WHAT patterns
3. **Provide Evidence**: Back up claims with data from the sources
4. **Actionable Insights**: Give concrete recommendations based on the analysis
5. **Structured Output**: Use clear sections with bullet points and numbered lists
6. **VISUALIZATIONS**: If you identify numerical data, metrics, or quantifiable patterns, include charts:
   - Format: `<chart type="TYPE" data='JSON_ARRAY' xKey="KEY" yKeys='["KEY"]' title="TITLE" />`
   - Types: "bar", "pie", "line", "area"
   - Example for comparisons: `<chart type="bar" data='[{{"label":"Q1","value":100}},{{"label":"Q2","value":150}}]' xKey="label" yKeys='["value"]' title="Quarterly Sales" />`
   - Example for distribution: `<chart type="pie" data='[{{"category":"A","count":45}},{{"category":"B","count":55}}]' xKey="category" yKeys='["count"]' title="Distribution" />`
   - Example for trends: `<chart type="line" data='[{{"month":"Jan","revenue":1000}},{{"month":"Feb","revenue":1200}}]' xKey="month" yKeys='["revenue"]' title="Revenue Trend" />`

Generate a comprehensive analysis in **clean HTML format** (use <h3>, <h4>, <p>, <ul>, <li>, <strong>, <em> tags, and <chart> tags for visualizations).

Start with an <h3> heading for the task name, then provide your detailed analysis with visualizations where appropriate.
"""

            # 5. Call LLM to generate real analysis
            print(f"🤖 Calling LLM for AI-powered analysis...")
            logger.info(f"🤖 Calling LLM for AI-powered analysis...")

            try:
                import httpx
                from api.services.settings import get_setting
                from api.services.credential_manager import get_credential_manager

                # Get configured LLM
                model_id = await get_setting("language_model_id", "")
                if not model_id:
                    print("⚠️  No LLM configured - skipping AI analysis")
                    logger.warning("No LLM configured")
                    return f"<h3>{task_name}</h3><p>{description}</p><p><em>Task completed (AI analysis unavailable - no LLM configured)</em></p>"

                # Use credential manager for flexible lookup (supports ID or name)
                credential_manager = get_credential_manager()
                credential = credential_manager.get(model_id)

                # Fallback to legacy store if not found
                if not credential:
                    from api.routers.credentials import _credentials_store
                    credential = _credentials_store.get(model_id)
                    if credential:
                        logger.info(f"Found credential in legacy store: {model_id}")

                if not credential:
                    print("⚠️  LLM credential not found")
                    logger.warning(f"LLM credential not found for model: {model_id}")
                    return f"<h3>{task_name}</h3><p>{description}</p><p><em>Task completed (AI analysis unavailable - LLM credential not found for model: {model_id})</em></p>"

                # Make LLM API call
                client = http_client_manager.get_client()
                response = await client.post(
                    f"{credential['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {credential['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": credential.get("model_name", "gpt-4"),
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an expert data analyst and business consultant. Provide detailed, data-driven analysis with specific insights and actionable recommendations. Always output clean HTML using <h3>, <h4>, <p>, <ul>, <li>, <strong> tags."
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000,
                    },
                    timeout=120.0,
                )

                if response.status_code != 200:
                    print(f"❌ LLM API error {response.status_code}")
                    logger.error(f"LLM API error {response.status_code}: {response.text[:200]}")
                    return f"<h3>{task_name}</h3><p>{description}</p><p><em>Task completed (AI analysis failed - API error)</em></p>"

                result = response.json()
                ai_content = result["choices"][0]["message"]["content"]

                print(f"✅ AI analysis generated ({len(ai_content)} chars)")
                logger.info(f"✅ AI analysis completed")

                # Wrap with metadata
                final_content = f"""<h2>{task_name}</h2>
<p><strong>Status:</strong> ✅ Completed<br>
<strong>Phase:</strong> {phase}<br>
<strong>Workspace:</strong> {workspace_name}</p>

{ai_content}

<hr>
<p><em>AI analysis generated on {datetime.utcnow().strftime('%Y-%m-%d at %H:%M UTC')}</em></p>
"""
                return final_content

            except Exception as e:
                print(f"❌ Error calling LLM: {e}")
                logger.error(f"Error calling LLM: {e}", exc_info=True)
                # Return graceful fallback instead of raising exception
                return f"""<h3>{task_name}</h3>
<p>{description}</p>

<div style="padding: 16px; background-color: #FEF3C7; border-left: 4px solid #F59E0B; margin: 16px 0;">
<p><strong>⚠️ Task Completed with Limited Output</strong></p>
<p>The AI analysis could not be generated due to: <em>{str(e)}</em></p>
<p>Please ensure an LLM is properly configured in Settings → Models.</p>
</div>

<hr>
<p><em>Task marked as completed on {datetime.utcnow().strftime('%Y-%m-%d at %H:%M UTC')}</em></p>
"""

        except Exception as e:
            print(f"❌ Error in _generate_ai_task_output: {e}")
            logger.error(f"Error in AI task generation: {e}", exc_info=True)
            # Return graceful fallback instead of raising exception
            return f"""<h3>{task_name if 'task_name' in locals() else 'Task'}</h3>
<p>{description if 'description' in locals() else 'Task execution attempted'}</p>

<div style="padding: 16px; background-color: #FEE2E2; border-left: 4px solid #EF4444; margin: 16px 0;">
<p><strong>❌ Task Generation Error</strong></p>
<p>An unexpected error occurred: <em>{str(e)}</em></p>
<p>Please check the logs for more details or contact support.</p>
</div>

<hr>
<p><em>Task attempted on {datetime.utcnow().strftime('%Y-%m-%d at %H:%M UTC')}</em></p>
"""

    async def _check_workspace_completion(self, workspace_id: str):
        """Check if all tasks in workspace are completed and update workspace status"""
        try:
            # Get plan
            plan = await repo_query(
                "SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id",
                {"workspace_id": workspace_id},
                fetch_one=True
            )

            if not plan:
                return

            # Check if there are any pending or in_progress tasks
            active_tasks = await repo_query("""
                SELECT COUNT(*) as count
                FROM workspace_plan_tasks
                WHERE plan_id = :plan_id
                AND status IN ('pending', 'in_progress')
            """, {"plan_id": plan["id"]}, fetch_one=True)

            # Check if there are any failed tasks
            failed_tasks = await repo_query("""
                SELECT COUNT(*) as count
                FROM workspace_plan_tasks
                WHERE plan_id = :plan_id
                AND status = 'failed'
            """, {"plan_id": plan["id"]}, fetch_one=True)

            # Only mark as completed if no active tasks and no failed tasks
            if active_tasks["count"] == 0 and failed_tasks["count"] == 0:
                # Mark workspace plan as completed
                await repo_execute("""
                    UPDATE workspace_plans
                    SET status = 'completed',
                        updated = :updated
                    WHERE id = :plan_id
                """, {
                    "plan_id": plan["id"],
                    "updated": datetime.utcnow().isoformat()
                })

                logger.info(f"🎉 Workspace {workspace_id} completed all tasks successfully!")

                # Create consolidated summary with AI
                await self._create_ai_consolidated_summary(workspace_id, plan["id"])

            elif active_tasks["count"] == 0 and failed_tasks["count"] > 0:
                # Mark workspace as failed if all tasks are done but some failed
                await repo_execute("""
                    UPDATE workspace_plans
                    SET status = 'failed',
                        updated = :updated
                    WHERE id = :plan_id
                """, {
                    "plan_id": plan["id"],
                    "updated": datetime.utcnow().isoformat()
                })

                logger.warning(f"⚠️  Workspace {workspace_id} completed with {failed_tasks['count']} failed task(s)")

        except Exception as e:
            logger.error(f"Error checking workspace completion: {e}", exc_info=True)

    async def _create_ai_consolidated_summary(self, workspace_id: str, plan_id: str):
        """Create AI-powered deep analysis and consolidated summary of all task results"""
        try:
            print(f"\n{'='*80}")
            print(f"📊 CREATING DEEP ANALYSIS CONSOLIDATED SUMMARY for workspace {workspace_id}")
            print(f"{'='*80}\n")

            # Get workspace info
            workspace = await repo_query(
                "SELECT name, goal FROM notebooks WHERE id = :id",
                {"id": workspace_id},
                fetch_one=True
            )

            # Get all completed task notes with full content
            task_notes = await repo_query("""
                SELECT n.title, n.content, n.created
                FROM notes n
                JOIN notebook_note nn ON n.id = nn.note_id
                WHERE nn.notebook_id = :workspace_id
                AND n.title LIKE '%✅%'
                ORDER BY n.created
            """, {"workspace_id": workspace_id})

            if not task_notes:
                print("⚠️  No task notes found, skipping summary")
                return

            # Get workspace sources for additional context
            sources = await repo_query("""
                SELECT s.id, s.title, s.source_type, s.full_text
                FROM sources s
                JOIN notebook_source ns ON s.id = ns.source_id
                WHERE ns.notebook_id = :workspace_id
            """, {"workspace_id": workspace_id})

            # Build comprehensive context
            notes_context = []
            for i, note in enumerate(task_notes, 1):
                # Extract more content from each task result
                content_preview = note['content'][:3000] if len(note['content']) > 3000 else note['content']
                notes_context.append(f"## Task {i}: {note['title']}\n{content_preview}")

            notes_text = "\n\n---\n\n".join(notes_context)

            # Build sources summary
            sources_summary = f"\n\n**Data Sources Used ({len(sources)})**:\n"
            for source in sources[:5]:  # Limit to top 5 sources
                sources_summary += f"- {source['title']} ({source['source_type']})\n"

            # Deep analysis prompt with multi-phase approach
            prompt = f"""You are an expert analyst conducting a comprehensive deep dive analysis of workspace results.

**WORKSPACE CONTEXT**:
- **Name**: {workspace['name']}
- **Goal**: {workspace.get('goal', '')}
- **Tasks Completed**: {len(task_notes)}
{sources_summary}

**ALL TASK RESULTS** (Full Analysis):
{notes_text}

**YOUR MISSION**:
Conduct a **DEEP, COMPREHENSIVE ANALYSIS** following this multi-phase approach:

**PHASE 1: SYNTHESIS & KEY FINDINGS**
- Synthesize ALL task results into coherent insights
- Extract the TOP 5-10 most important findings
- Identify data-driven patterns, trends, and correlations
- Highlight surprising or counter-intuitive discoveries

**PHASE 2: STRATEGIC ANALYSIS**
- What are the strategic implications of these findings?
- What opportunities or risks does the data reveal?
- What are the strongest evidence-based conclusions?
- What are the key success factors or barriers identified?

**PHASE 3: CROSS-CUTTING INSIGHTS**
- Connect insights across different tasks and data sources
- Identify themes that emerge when viewing all results holistically
- What story does the complete picture tell?
- What are the underlying root causes or drivers?

**PHASE 4: RECOMMENDATIONS & ACTION PLAN**
- Prioritized recommendations based on findings
- Concrete, actionable next steps with clear owners/timelines
- Quick wins vs. long-term strategic initiatives
- Metrics to track progress

**PHASE 5: EXECUTIVE SUMMARY**
- One-paragraph TL;DR of the entire analysis
- Key numbers, metrics, or KPIs that matter most
- Most critical decision or action required

**OUTPUT REQUIREMENTS**:
1. Use **clean HTML** with <h2>, <h3>, <h4>, <p>, <ul>, <li>, <strong>, <em> tags
2. Include **specific data points** and numbers from the task results
3. Use **bold** for key insights and **italics** for emphasis
4. Create visual hierarchy with proper headings
5. Minimum 1500 words - be thorough and comprehensive
6. Include concrete examples from the data
7. Use bullet points and numbered lists for clarity
8. Add a "Key Metrics Dashboard" section with important numbers

Begin with an <h2>Executive Summary</h2> section, then proceed through all phases.
"""

            # Call LLM with extended timeout for deep analysis
            try:
                import httpx
                from api.services.settings import get_setting
                from api.routers.credentials import _credentials_store

                model_id = await get_setting("language_model_id", "")
                if not model_id:
                    print("⚠️  No LLM configured, skipping AI summary")
                    return

                credential = _credentials_store.get(model_id)
                if not credential:
                    return

                print("🤖 Calling LLM for deep analysis (this may take 30-60 seconds)...")
                logger.info("🤖 Starting deep analysis consolidated summary generation")

                client = http_client_manager.get_client()
                response = await client.post(  # 3 minute timeout for deep analysis
                    f"{credential['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {credential['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": credential.get("model_name", "gpt-4"),
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a world-class strategic analyst and business consultant. You excel at deep analysis, pattern recognition, and actionable insights. You always provide comprehensive, data-driven analysis with specific examples and concrete recommendations."
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.2,  # Lower temperature for more focused analysis
                        "max_tokens": 4000,   # Extended token limit for comprehensive output
                    },
                    timeout=180.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    summary_content = result["choices"][0]["message"]["content"]

                    print(f"✅ Deep analysis completed ({len(summary_content)} chars)")
                    logger.info(f"✅ Deep analysis completed ({len(summary_content)} chars)")

                    # Create comprehensive final deliverable note
                    import uuid
                    note_id = str(uuid.uuid4())

                    # Get execution folder from plan
                    plan = await repo_query(
                        "SELECT execution_folder_id FROM workspace_plans WHERE id = :plan_id",
                        {"plan_id": plan_id},
                        fetch_one=True
                    )
                    execution_folder_id = plan.get("execution_folder_id") if plan else None

                    final_content = f"""<div class="final-deliverable">
<div class="badge-container" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; margin-bottom: 20px; color: white;">
<h1 style="margin: 0; color: white;">🎯 FINAL DELIVERABLE - Comprehensive Workspace Analysis</h1>
<p style="margin: 10px 0 0 0; opacity: 0.9;"><strong>Workspace:</strong> {workspace['name']} | <strong>Goal:</strong> {workspace.get('goal', 'N/A')}</p>
<p style="margin: 5px 0 0 0; opacity: 0.9;"><strong>Analysis Completed:</strong> {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')} | <strong>Tasks Analyzed:</strong> {len(task_notes)}</p>
</div>

{summary_content}

<hr style="margin: 40px 0; border: none; border-top: 2px solid #ddd;">

<div style="background: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #667eea;">
<h3 style="margin-top: 0;">📋 Analysis Metadata</h3>
<ul>
<li><strong>Total Tasks Analyzed:</strong> {len(task_notes)}</li>
<li><strong>Data Sources Integrated:</strong> {len(sources)}</li>
<li><strong>Analysis Type:</strong> Comprehensive Deep Dive with Multi-Phase Approach</li>
<li><strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d at %H:%M UTC')}</li>
<li><strong>Confidence Level:</strong> High (based on {len(task_notes)} completed analysis tasks)</li>
</ul>
</div>

<p style="margin-top: 20px; font-style: italic; color: #666;">This final deliverable represents a comprehensive analysis synthesizing all workspace tasks and data sources using advanced AI-powered deep research methodology.</p>
</div>
"""

                    await repo_execute("""
                        INSERT INTO notes (id, title, content, content_html, notebook_id, folder_id, created, updated)
                        VALUES (:id, :title, :content, :content_html, :notebook_id, :folder_id, :created, :updated)
                    """, {
                        "id": note_id,
                        "title": "🎯 FINAL DELIVERABLE - Workspace Analysis",
                        "content": final_content,
                        "content_html": final_content,
                        "notebook_id": workspace_id,  # Set notebook_id for direct querying
                        "folder_id": execution_folder_id,  # Assign to execution folder
                        "created": datetime.utcnow().isoformat(),
                        "updated": datetime.utcnow().isoformat()
                    })

                    await repo_execute("""
                        INSERT OR IGNORE INTO notebook_note (notebook_id, note_id, created)
                        VALUES (:notebook_id, :note_id, :created)
                    """, {
                        "notebook_id": workspace_id,
                        "note_id": note_id,
                        "created": datetime.utcnow().isoformat()
                    })

                    print(f"✅ Deep analysis final deliverable created!")
                    logger.info(f"✅ Final deliverable note created with ID: {note_id}")

                else:
                    print(f"❌ LLM API error: {response.status_code}")
                    logger.error(f"LLM API error {response.status_code}: {response.text[:200]}")

            except Exception as e:
                print(f"❌ Failed to create deep analysis summary: {e}")
                logger.error(f"Failed to create AI summary: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error creating consolidated summary: {e}", exc_info=True)


# Singleton instance
_task_executor: Optional[WorkspaceTaskExecutor] = None


def get_task_executor() -> WorkspaceTaskExecutor:
    """Get or create the task executor singleton"""
    global _task_executor
    if _task_executor is None:
        _task_executor = WorkspaceTaskExecutor()
    return _task_executor
