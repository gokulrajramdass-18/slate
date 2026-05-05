"""
Classification Service - Automatic source classification using LLM analysis.

Classifies sources into a hierarchical taxonomy:
- Level 0: Categories (e.g., "Engineering", "Marketing")
- Level 1: Topics/Projects (e.g., "Machine Learning", "Customer Dashboard")
- Level 2: Subtopics (e.g., "Neural Networks", "User Authentication")

Supports approval workflow with confidence scores.
"""

import json
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from datetime import datetime

from open_notebook.domain.classification import Classification, SourceClassification
from open_notebook.database.repository import repo_query
import logging

# Try to import LangChain
try:
    from langchain_community.chat_models import ChatLiteLLM
    from langchain_core.messages import HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)

# LLM Prompt Template
CLASSIFICATION_PROMPT = """Analyze the following source and classify it into a hierarchical taxonomy.

Title: {title}
Description: {description}
Content Preview: {content_preview}

Create a multi-level classification with hierarchical relationships:

**Level 0 - CATEGORIES** (1-2): High-level domains
Examples: Engineering, Marketing, Sales, HR, Finance, Operations, Product, Design, Legal

**Level 1 - TOPICS/PROJECTS** (2-4): Specific areas within each category
Examples:
- Engineering → Machine Learning, API Development, DevOps, Security, Frontend, Backend
- Marketing → Content Strategy, Brand Design, Analytics, Social Media, SEO
- Product → Feature Planning, User Research, Roadmap, Product Analytics

**Level 2 - SUBTOPICS** (2-5): Granular concepts within topics
Examples:
- Machine Learning → Neural Networks, NLP, Computer Vision, Reinforcement Learning
- API Development → REST APIs, GraphQL, Authentication, Rate Limiting
- Content Strategy → Blog Posts, Whitepapers, Email Marketing, Video Content

**CRITICAL: Create proper hierarchy**
- Subtopics MUST have a parent topic
- Topics MUST have a parent category
- Use parent_name to link the levels

Return strict JSON (no markdown):
{{
  "classifications": [
    {{
      "name": "Engineering",
      "type": "category",
      "level": 0,
      "parent_name": null,
      "confidence": 0.95,
      "description": "Technical and software development",
      "reason": "Document discusses technical implementation details"
    }},
    {{
      "name": "Machine Learning",
      "type": "topic",
      "level": 1,
      "parent_name": "Engineering",
      "confidence": 0.90,
      "description": "AI and ML algorithms",
      "reason": "Content covers neural network training"
    }},
    {{
      "name": "Neural Networks",
      "type": "subtopic",
      "level": 2,
      "parent_name": "Machine Learning",
      "confidence": 0.85,
      "description": "Deep learning architectures",
      "reason": "Specific discussion of CNN and RNN architectures"
    }}
  ]
}}
"""


class ClassificationService:
    """Service for automatic source classification with LLM."""

    def __init__(
        self,
        model: Optional[str] = None,
        max_content_words: int = 1000
    ):
        """
        Initialize classification service.

        Args:
            model: LLM model to use (defaults to configured model)
            max_content_words: Max words from content to analyze
        """
        self.model = model or "gpt-4o-mini"  # Default to fast model
        self.max_content_words = max_content_words

    async def classify_source(
        self,
        source_id: str,
        force: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Classify a single source with hierarchical taxonomy.

        Args:
            source_id: Source ID to classify
            force: If True, reclassify even if classifications exist

        Returns:
            Dict with pending classifications grouped by confidence:
            {
              "high_confidence": [...],  # confidence >= 0.8
              "medium_confidence": [...], # 0.5 <= confidence < 0.8
              "low_confidence": [...]     # confidence < 0.5
            }
        """
        try:
            # Check if already classified (unless force)
            if not force:
                existing = await repo_query(
                    "SELECT COUNT(*) as count FROM source_classifications WHERE source_id = :source_id",
                    {"source_id": source_id}
                )
                if existing and existing[0]["count"] > 0:
                    logger.info(f"Source {source_id} already classified (use force=True to reclassify)")
                    return {"high_confidence": [], "medium_confidence": [], "low_confidence": []}

            # Get source content
            source_data = await repo_query(
                "SELECT id, title, source_type, full_text FROM sources WHERE id = :source_id",
                {"source_id": source_id}
            )

            if not source_data:
                logger.error(f"Source {source_id} not found")
                return {"high_confidence": [], "medium_confidence": [], "low_confidence": []}

            source = source_data[0]

            # Build prompt with content preview
            content_preview = self._extract_content_preview(source.get("full_text", ""))
            prompt = CLASSIFICATION_PROMPT.format(
                title=source.get("title", "Untitled"),
                description=source.get("source_type", "unknown"),
                content_preview=content_preview
            )

            # Call LLM
            if not LANGCHAIN_AVAILABLE or not self.model:
                logger.warning("LLM not available - cannot classify")
                return {"high_confidence": [], "medium_confidence": [], "low_confidence": []}

            llm = ChatLiteLLM(model=self.model, temperature=0)
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content

            # Parse response
            try:
                # Clean markdown code blocks
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                classification_result = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response: {e}")
                logger.error(f"Response: {content}")
                return {"high_confidence": [], "medium_confidence": [], "low_confidence": []}

            # Process classifications and create hierarchy
            classifications_data = classification_result.get("classifications", [])
            created_classifications = await self._create_classification_hierarchy(
                source_id,
                classifications_data
            )

            # Group by confidence
            high_conf = [c for c in created_classifications if c["confidence"] >= 0.8]
            medium_conf = [c for c in created_classifications if 0.5 <= c["confidence"] < 0.8]
            low_conf = [c for c in created_classifications if c["confidence"] < 0.5]

            return {
                "high_confidence": high_conf,
                "medium_confidence": medium_conf,
                "low_confidence": low_conf
            }

        except Exception as e:
            logger.error(f"Error classifying source {source_id}: {e}", exc_info=True)
            return {"high_confidence": [], "medium_confidence": [], "low_confidence": []}

    async def _create_classification_hierarchy(
        self,
        source_id: str,
        classifications_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create classification nodes and link to source with proper hierarchy.

        Args:
            source_id: Source to link classifications to
            classifications_data: List of classification dicts from LLM

        Returns:
            List of created source_classification records
        """
        created = []
        name_to_id = {}  # Track created classifications by name

        # Sort by level to ensure parents are created first
        classifications_data.sort(key=lambda x: x.get("level", 0))

        for class_data in classifications_data:
            name = class_data.get("name", "").strip()
            classification_type = class_data.get("type", "topic")
            level = class_data.get("level", 1)
            parent_name = class_data.get("parent_name")
            confidence = class_data.get("confidence", 0.5)
            description = class_data.get("description", "")
            reason = class_data.get("reason", "")

            if not name:
                continue

            # Get parent_id if parent_name specified
            parent_id = None
            if parent_name and parent_name in name_to_id:
                parent_id = name_to_id[parent_name]

            # Get or create classification node
            classification = await Classification.get_or_create(
                name=name,
                classification_type=classification_type,
                level=level,
                parent_id=parent_id,
                description=description,
                metadata={"ai_generated": True}
            )

            # Track for parent references
            name_to_id[name] = classification.id

            # Link to source (pending approval)
            source_classification = SourceClassification(
                source_id=source_id,
                classification_id=classification.id,
                confidence=confidence,
                status="pending",
                metadata={
                    "reason": reason,
                    "ai_explanation": description
                }
            )
            await source_classification.save()

            created.append({
                "id": source_classification.id,
                "classification_id": classification.id,
                "name": name,
                "type": classification_type,
                "level": level,
                "parent_name": parent_name,
                "confidence": confidence,
                "description": description,
                "reason": reason,
                "status": "pending"
            })

        return created

    def _extract_content_preview(self, full_text: Optional[str]) -> str:
        """
        Extract first N words from content for classification.

        Args:
            full_text: Full source text

        Returns:
            First max_content_words words
        """
        if not full_text:
            return ""

        words = full_text.split()
        preview_words = words[:self.max_content_words]
        preview = " ".join(preview_words)

        if len(words) > self.max_content_words:
            preview += "..."

        return preview

    async def classify_multiple_sources(
        self,
        source_ids: List[str],
        batch_size: int = 5
    ) -> Dict[str, Any]:
        """
        Classify multiple sources in parallel batches.

        Args:
            source_ids: List of source IDs
            batch_size: Number to process concurrently

        Returns:
            Dict with results: {source_id: classification_result}
        """
        results = {}

        # Process in batches
        for i in range(0, len(source_ids), batch_size):
            batch = source_ids[i:i + batch_size]
            tasks = [self.classify_source(source_id) for source_id in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for source_id, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error classifying {source_id}: {result}")
                    results[source_id] = {"error": str(result)}
                else:
                    results[source_id] = result

        return results

    async def reclassify_all_sources(self) -> Dict[str, int]:
        """
        Background job to reclassify all sources.

        Returns:
            Dict with counts: {total, success, failed}
        """
        # Get all source IDs
        sources = await repo_query("SELECT id FROM sources", {})
        source_ids = [s["id"] for s in sources]

        logger.info(f"Starting reclassification of {len(source_ids)} sources")

        results = await self.classify_multiple_sources(source_ids, batch_size=3)

        success = sum(1 for r in results.values() if "error" not in r)
        failed = len(results) - success

        logger.info(f"Reclassification complete: {success} success, {failed} failed")

        return {
            "total": len(source_ids),
            "success": success,
            "failed": failed
        }

    async def detect_classification_relationships(self) -> int:
        """
        Analyze relationships between classification nodes.
        Currently creates parent-child relationships based on parent_id.
        Future: Could use LLM to detect 'related' and 'similar' relationships.

        Returns:
            Number of relationships created
        """
        # Get all classifications with parents
        classifications = await repo_query(
            """SELECT id, parent_id FROM classification_types
               WHERE parent_id IS NOT NULL""",
            {}
        )

        created_count = 0

        for classification in classifications:
            # Check if parent_child relationship already exists
            existing = await repo_query(
                """SELECT id FROM classification_relationships
                   WHERE source_classification_id = :parent_id
                   AND target_classification_id = :child_id
                   AND relationship_type = 'parent_child'""",
                {
                    "parent_id": classification["parent_id"],
                    "child_id": classification["id"]
                }
            )

            if not existing:
                # Create parent-child relationship
                relationship_id = str(uuid.uuid4())
                await repo_query(
                    """INSERT INTO classification_relationships
                       (id, source_classification_id, target_classification_id, relationship_type, strength, created)
                       VALUES (:id, :parent_id, :child_id, 'parent_child', 1.0, :created)""",
                    {
                        "id": relationship_id,
                        "parent_id": classification["parent_id"],
                        "child_id": classification["id"],
                        "created": datetime.utcnow().isoformat()
                    }
                )
                created_count += 1

        logger.info(f"Created {created_count} parent-child relationships")
        return created_count
