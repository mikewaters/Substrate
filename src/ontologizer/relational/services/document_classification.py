import logging
from datetime import datetime

from ontologizer.relational.repository.classifier import DocumentClassificationRepository

logger = logging.getLogger(__name__)
from ontologizer.relational.models import Taxonomy as TaxonomyORM
from ontologizer.relational.models import Topic as TopicORM
from ontologizer.relational.repository import TopicRepository
from ontologizer.relational.repository import TaxonomyRepository
from ontologizer.schema.classifier import (
    DocumentClassificationRequest,
    DocumentClassificationResponse,
    FeedbackRequest,
    TaxonomySuggestion,
    TopicSuggestion,
)


class DocumentClassificationService:
    """Service for LLM-based document classification.

    This service implements the two-stage classification process:
    1. Classify document into taxonomy
    2. Classify document into topics within that taxonomy

    Uses PydanticAI for structured LLM interactions with support for:
    - Remote providers: Anthropic, OpenAI
    - Local models: LM Studio, vLLM, Ollama (via OpenAI-compatible APIs)
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    PROMPT_VERSION = "1.0.0"

    def __init__(
        self,
        classification_repo: "DocumentClassificationRepository",
        taxonomy_repo: TaxonomyRepository,
        topic_repo: "TopicRepository",
        model_name: str | None = None,
        provider: str | None = None,
        openai_base_url: str | None = None,
        api_key: str | None = None,
    ):
        from pydantic_ai import Agent

        from ontologizer.settings import get_settings

        self.classification_repo = classification_repo
        self.taxonomy_repo = taxonomy_repo
        self.topic_repo = topic_repo

        # Load settings
        settings = get_settings()
        llm_settings = settings.llm

        # Use provided values or fall back to settings
        self.model_name = model_name or llm_settings.model_name
        provider = provider or llm_settings.provider
        openai_base_url = openai_base_url or llm_settings.openai_base_url
        api_key = api_key or llm_settings.api_key

        logger.info(
            f"Initializing DocumentClassificationService with provider={provider}, "
            f"model={self.model_name}"
        )

        # Create model instance based on provider
        if provider == "openai-compatible":
            model = self._create_openai_compatible_model(
                self.model_name, openai_base_url, api_key
            )
        else:
            # Default to Anthropic
            from pydantic_ai.models.anthropic import AnthropicModel

            model = AnthropicModel(self.model_name)

        # Initialize PydanticAI agents
        self.taxonomy_agent = Agent(
            model,
            output_type=list[TaxonomySuggestion],
            system_prompt=self._build_taxonomy_system_prompt(),
        )

        self.topic_agent = Agent(
            model,
            output_type=list[TopicSuggestion],
            system_prompt=self._build_topic_system_prompt(),
        )

        from ontologizer.schema.catalog import NewTopicProposal

        self.new_topic_agent = Agent(
            model,
            output_type=list[NewTopicProposal],
            system_prompt=self._build_new_topic_system_prompt(),
        )

        from ontologizer.schema.classifier import ParentSuggestion

        self.parent_agent = Agent(
            model,
            output_type=list[ParentSuggestion],
            system_prompt=self._build_parent_suggestion_system_prompt(),
        )

    @staticmethod
    def _create_openai_compatible_model(
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        """Create an OpenAI-compatible model instance.

        Args:
            model_name: Model identifier (e.g., "neural-chat-7b", "mistral-7b")
            base_url: API endpoint (e.g., http://localhost:1234/v1 for LM Studio)
            api_key: API key (can be dummy for local models)

        Returns:
            OpenAIChatModel instance configured for the endpoint

        Examples:
            - LM Studio: base_url="http://localhost:1234/v1"
            - vLLM: base_url="http://localhost:8000/v1"
            - Ollama: base_url="http://localhost:11434/v1"
        """
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.ollama import OllamaProvider

        if not base_url:
            raise ValueError(
                "base_url is required for OpenAI-compatible endpoint. "
                "Examples: http://localhost:1234/v1 (LM Studio), "
                "http://localhost:8000/v1 (vLLM)"
            )

        # Create OllamaProvider with custom base_url for local endpoints
        # OllamaProvider works with any OpenAI-compatible endpoint, not just Ollama
        provider = OllamaProvider(
            base_url=base_url,
            api_key=api_key or "not-used-for-local-models",
        )

        # Return model with the configured provider
        return OpenAIChatModel(model_name, provider=provider)

    def _build_taxonomy_system_prompt(self) -> str:
        """Build system prompt for taxonomy classification."""
        return """You are a document classification expert. Your task is to analyze document content and suggest which taxonomy (or taxonomies) the document belongs to.

You will be provided with:
1. Document content
2. A list of available taxonomies with descriptions

Your task:
1. Analyze the main themes and topics in the document
2. Match the content to the most appropriate taxonomy or taxonomies
3. Provide a confidence score (0.0 to 1.0) for each suggestion
4. Provide brief reasoning for each suggestion

Guidelines:
- Confidence > 0.8: Document clearly and primarily belongs to this taxonomy
- Confidence 0.5-0.8: Document has significant content related to this taxonomy
- Confidence 0.3-0.5: Document has some content related to this taxonomy
- Confidence < 0.3: Weak or tangential relationship

Return your suggestions as a list ordered by confidence (highest first)."""

    def _build_topic_system_prompt(self) -> str:
        """Build system prompt for topic classification."""
        return """You are a document classification expert. Your task is to suggest relevant topics for a document within a specific taxonomy.

You will be provided with:
1. Document content
2. The taxonomy the document belongs to
3. A list of available topics within that taxonomy

Your task:
1. Identify the key concepts and themes in the document
2. Match them to the most relevant topics in the provided list
3. Rank topics by relevance (1 = most relevant)
4. Provide confidence scores (0.0 to 1.0)
5. Provide brief reasoning for each topic suggestion

Guidelines:
- Suggest 1-5 topics per document
- Confidence > 0.7: Topic is clearly central to the document
- Confidence 0.4-0.7: Topic is relevant but not central
- Confidence < 0.4: Topic has weak relevance

Return suggestions ordered by rank (1, 2, 3, ...)."""

    def _build_new_topic_system_prompt(self) -> str:
        """Build system prompt for new topic generation (FEAT-006 Phase 3)."""
        return """You are a knowledge organization expert. Your task is to analyze document content and propose NEW topics that should be added to a taxonomy when existing topics don't adequately capture the document's concepts.

You will be provided with:
1. Document content (note/article/etc.)
2. The target taxonomy
3. A list of existing topics that were already considered but didn't match well

Your task:
1. Identify key concepts in the document that are NOT well-represented by existing topics
2. Propose 1-3 new topics that would better categorize this content
3. For each new topic, provide:
   - A clear, concise title (2-5 words)
   - A brief description explaining what the topic covers
   - Confidence score (0.0-1.0) on whether this new topic is needed
   - Reasoning for why this new topic should be added
   - Suggested parent topic IDs from the existing taxonomy (if applicable)

Guidelines:
- Only suggest new topics when truly needed - don't create duplicates
- Keep titles concise and descriptive
- Confidence > 0.7: Clear gap in the taxonomy that this topic would fill
- Confidence 0.4-0.7: Moderately useful addition
- Confidence < 0.4: Not strongly needed

Return 1-3 proposals ordered by confidence (highest first)."""

    def _build_parent_suggestion_system_prompt(self) -> str:
        """Build system prompt for parent topic suggestion (FEAT-006 Phase 4)."""
        return """You are a taxonomy expert. Your task is to suggest appropriate parent topics for a given topic within a taxonomy hierarchy.

You will be provided with:
1. A topic that needs parent(s)
2. The taxonomy it belongs to
3. A list of candidate parent topics from the same taxonomy

Your task:
1. Analyze the topic's title and description
2. Understand its conceptual scope and specificity
3. Identify which candidate topics are appropriate parents (broader concepts)
4. Rank parent suggestions by appropriateness
5. Provide confidence scores (0.0-1.0) and reasoning

Guidelines for parent-child relationships:
- Parent should be a BROADER, more general concept than the child
- Avoid circular relationships (A is parent of B, B is parent of A)
- Prefer specific, direct parents over distant ancestors
- A topic can have multiple parents if it fits into multiple hierarchies
- Confidence > 0.8: Clear and direct parent-child relationship
- Confidence 0.5-0.8: Reasonable parent-child relationship
- Confidence < 0.5: Weak or questionable relationship

Return 1-5 parent suggestions ordered by confidence (highest first)."""

    async def classify_document(
        self, request: DocumentClassificationRequest
    ) -> DocumentClassificationResponse:
        """Classify a document into taxonomy and topics.

        This is the main entry point for document classification.

        Process:
        1. Load all available taxonomies
        2. Call LLM to suggest taxonomy
        3. Load topics for suggested taxonomy
        4. Call LLM to suggest topics
        5. Optionally persist results
        6. Return structured response

        Args:
            request: Classification request with document content

        Returns:
            Complete classification response with taxonomy and topics
        """
        logger.info(f"Classifying document (length={len(request.content)})")

        # Stage 1: Classify into taxonomy
        taxonomy_suggestions = await self._classify_taxonomy(
            content=request.content,
            taxonomy_hint=request.taxonomy_hint,
            top_k=3,
            min_confidence=request.min_confidence,
        )

        if not taxonomy_suggestions:
            raise ValueError("No taxonomy suggestions met the confidence threshold")

        primary_taxonomy = taxonomy_suggestions[0]
        alternative_taxonomies = (
            taxonomy_suggestions[1:] if len(taxonomy_suggestions) > 1 else []
        )

        logger.info(
            f"Selected taxonomy: {primary_taxonomy.taxonomy_id} "
            f"(confidence={primary_taxonomy.confidence:.2f})"
        )

        # Stage 2: Classify into topics within the selected taxonomy
        topic_suggestions = await self._classify_topics(
            content=request.content,
            taxonomy_id=primary_taxonomy.taxonomy_id,
            max_topics=request.max_topics,
            min_confidence=request.min_confidence,
        )

        logger.info(f"Suggested {len(topic_suggestions)} topics")

        # Build response
        response = DocumentClassificationResponse(
            content_preview=request.content[:200],
            document_id=request.document_id,
            document_type=request.document_type,
            suggested_taxonomy=primary_taxonomy,
            alternative_taxonomies=alternative_taxonomies,
            suggested_topics=topic_suggestions,
            model_name=self.model_name,
            model_version=self.DEFAULT_MODEL,
            prompt_version=self.PROMPT_VERSION,
            created_at=datetime.utcnow(),
        )

        # Optionally persist
        if request.store_result and request.document_id:
            classification_id = await self._persist_classification(
                request=request,
                taxonomy_suggestion=primary_taxonomy,
                topic_suggestions=topic_suggestions,
            )
            response.classification_id = classification_id

        return response

    async def _classify_taxonomy(
        self,
        content: str,
        taxonomy_hint: str | None,
        top_k: int,
        min_confidence: float,
    ) -> list[TaxonomySuggestion]:
        """Classify content into taxonomy using LLM.

        Args:
            content: Document content
            taxonomy_hint: Optional taxonomy to prioritize
            top_k: Number of suggestions to return
            min_confidence: Minimum confidence threshold

        Returns:
            List of taxonomy suggestions ordered by confidence
        """
        # Load available taxonomies
        taxonomies = await self.taxonomy_repo.get_all_active()

        if not taxonomies:
            raise ValueError("No taxonomies available for classification")

        # Build taxonomy context for LLM
        taxonomy_context = self._format_taxonomies_for_prompt(taxonomies)

        # Construct prompt
        user_prompt = f"""Classify the following document into one or more taxonomies.

Document content:
---
{content[:5000]}
---

Available taxonomies:
{taxonomy_context}

Provide up to {top_k} taxonomy suggestions with confidence scores and reasoning.
Only include suggestions with confidence >= {min_confidence}."""

        # Call LLM via PydanticAI
        result = await self.taxonomy_agent.run(user_prompt)

        # Filter and sort - result.output is the actual list of suggestions
        suggestions = [s for s in result.output if s.confidence >= min_confidence]
        suggestions.sort(key=lambda s: s.confidence, reverse=True)

        return suggestions[:top_k]

    async def _classify_topics(
        self,
        content: str,
        taxonomy_id: str,
        max_topics: int,
        min_confidence: float,
    ) -> list[TopicSuggestion]:
        """Classify content into topics using LLM.

        Args:
            content: Document content
            taxonomy_id: Selected taxonomy
            max_topics: Maximum topics to suggest
            min_confidence: Minimum confidence threshold

        Returns:
            List of topic suggestions ordered by rank
        """
        # Load taxonomy and its topics
        taxonomy, topics = await self.taxonomy_repo.get_with_topics(
            taxonomy_id, status="active"
        )

        if not topics:
            logger.warning(f"No active topics in taxonomy {taxonomy_id}")
            return []

        # Build topic context for LLM
        topic_context = self._format_topics_for_prompt(topics)

        # Construct prompt
        user_prompt = f"""Classify the following document into relevant topics within the "{taxonomy.title}" taxonomy.

Document content:
---
{content[:5000]}
---

Available topics in "{taxonomy.title}":
{topic_context}

Suggest up to {max_topics} topics with confidence scores, ranking, and reasoning.
Only include suggestions with confidence >= {min_confidence}.
Rank the topics by relevance (1 = most relevant)."""

        # Call LLM via PydanticAI
        result = await self.topic_agent.run(user_prompt)

        # Filter and sort by rank - result.output is the actual list of suggestions
        suggestions = [s for s in result.output if s.confidence >= min_confidence]
        suggestions.sort(key=lambda s: s.rank)

        return suggestions[:max_topics]

    def _format_taxonomies_for_prompt(self, taxonomies: list[TaxonomyORM]) -> str:
        """Format taxonomies for LLM prompt."""
        lines = []
        for taxonomy in taxonomies:
            desc = taxonomy.description or "No description"
            lines.append(f"- {taxonomy.id} ({taxonomy.title}): {desc}")
        return "\n".join(lines)

    def _format_topics_for_prompt(self, topics: list[TopicORM]) -> str:
        """Format topics for LLM prompt."""
        lines = []
        for topic in topics:
            desc = topic.description or "No description"
            lines.append(f"- {topic.id} ({topic.title}): {desc}")
        return "\n".join(lines)

    async def _persist_classification(
        self,
        request: DocumentClassificationRequest,
        taxonomy_suggestion: TaxonomySuggestion,
        topic_suggestions: list[TopicSuggestion],
    ) -> str:
        """Persist classification results to database.

        Args:
            request: Original classification request
            taxonomy_suggestion: Selected taxonomy
            topic_suggestions: Topic suggestions

        Returns:
            ID of persisted classification
        """
        from ontologizer.relational.models.classifier import (
            DocumentClassification as DocumentClassificationORM,
        )
        from ontologizer.relational.models.classifier import (
            DocumentTopicAssignment as DocumentTopicAssignmentORM,
        )

        # Create ORM model for classification
        classification_orm = DocumentClassificationORM(
            document_id=request.document_id,
            document_type=request.document_type or "unknown",
            taxonomy_id=taxonomy_suggestion.taxonomy_id,
            confidence=taxonomy_suggestion.confidence,
            reasoning=taxonomy_suggestion.reasoning,
            model_name=self.model_name,
            model_version=self.DEFAULT_MODEL,
            prompt_version=self.PROMPT_VERSION,
            meta={},
        )

        # Create ORM models for topic assignments
        topic_assignments_orm = [
            DocumentTopicAssignmentORM(
                topic_id=topic.topic_id,
                confidence=topic.confidence,
                rank=topic.rank,
                reasoning=topic.reasoning,
                meta={},
            )
            for topic in topic_suggestions
        ]

        # Persist
        classification_orm = await self.classification_repo.add_with_topics(
            classification=classification_orm,
            topic_assignments=topic_assignments_orm,
        )

        await self.classification_repo.session.commit()

        return classification_orm.id

    async def get_classification_history(
        self,
        document_id: str,
        document_type: str,
        limit: int = 10,
    ) -> list[DocumentClassificationResponse]:
        """Get classification history for a document.

        Args:
            document_id: Document identifier
            document_type: Type of document
            limit: Maximum results

        Returns:
            List of historical classifications
        """
        classifications = await self.classification_repo.get_by_document(
            document_id=document_id,
            document_type=document_type,
            limit=limit,
        )

        # Convert to response format
        responses = []
        for classification in classifications:
            _, topics = await self.classification_repo.get_with_topics(
                classification.id
            )

            # Get taxonomy details
            taxonomy = await self.taxonomy_repo.get(classification.taxonomy_id)

            response = DocumentClassificationResponse(
                content_preview="[Historical record]",
                document_id=classification.document_id,
                document_type=classification.document_type,
                suggested_taxonomy=TaxonomySuggestion(
                    taxonomy_id=taxonomy.id,  # taxonomy.id is the CURIE
                    taxonomy_title=taxonomy.title,
                    taxonomy_description=taxonomy.description,
                    confidence=classification.confidence,
                    reasoning=classification.reasoning,
                ),
                suggested_topics=[
                    TopicSuggestion(
                        topic_id=t.topic.id,
                        topic_title=t.topic.title,
                        topic_description=t.topic.description,
                        confidence=t.confidence,
                        rank=t.rank,
                        reasoning=t.reasoning,
                    )
                    for t in topics
                ],
                model_name=classification.model_name,
                model_version=classification.model_version,
                prompt_version=classification.prompt_version,
                classification_id=classification.id,
                created_at=classification.created_at,
            )
            responses.append(response)

        return responses

    async def submit_feedback(self, request: FeedbackRequest) -> None:
        """Record user feedback on a classification.

        Args:
            request: Feedback request with corrections
        """
        await self.classification_repo.update_feedback(
            classification_id=request.classification_id,
            feedback=request.feedback,
            corrected_taxonomy_id=request.corrected_taxonomy_id,
        )

        await self.classification_repo.session.commit()

    async def suggest_new_topics(
        self,
        content: str,
        taxonomy_id: str,
        existing_suggestions: list[TopicSuggestion],
        max_proposals: int = 3,
    ) -> list:
        """Suggest new topics that should be added to the taxonomy (FEAT-006 Phase 3).

        This method uses an LLM to analyze content and propose new topics when
        existing topics don't adequately capture the document's concepts.

        Args:
            content: Document content to analyze
            taxonomy_id: Target taxonomy for new topics
            existing_suggestions: Topics that were already suggested (for context)
            max_proposals: Maximum number of new topic proposals (default: 3)

        Returns:
            List of NewTopicProposal objects
        """

        # Get taxonomy and its topics
        taxonomy, topics = await self.taxonomy_repo.get_with_topics(
            taxonomy_id, status="active"
        )

        # Build context about existing suggestions
        existing_context = "\n".join(
            [
                f"- {s.topic_title} (confidence: {s.confidence:.2f})"
                for s in existing_suggestions
            ]
        )

        # Build prompt
        user_prompt = f"""Analyze the following content and propose NEW topics for the "{taxonomy.title}" taxonomy.

Document content:
---
{content[:5000]}
---

Existing topics that were already suggested but may not be adequate:
{existing_context if existing_context else "None - no existing topics matched well"}

Existing topics in "{taxonomy.title}" (for reference, to avoid duplicates):
{self._format_topics_for_prompt(topics[:50])}

Propose up to {max_proposals} new topics that would better categorize this content.
Only suggest topics if there's a clear gap in the taxonomy."""

        # Call LLM via PydanticAI
        result = await self.new_topic_agent.run(user_prompt)

        # Filter by confidence and limit - result.output is the actual list of proposals
        proposals = [p for p in result.output if p.confidence >= 0.4]
        proposals.sort(key=lambda p: p.confidence, reverse=True)

        logger.info(
            f"Generated {len(proposals)} new topic proposals for taxonomy {taxonomy_id}"
        )

        return proposals[:max_proposals]

    async def suggest_parent_topics(
        self,
        topic_id: str,
        candidate_parent_ids: list[str] | None = None,
        max_suggestions: int = 5,
    ) -> list:
        """Suggest parent topics for a given topic (FEAT-006 Phase 4).

        This method uses an LLM to analyze a topic and suggest appropriate
        parent topics from the same taxonomy.

        Args:
            topic_id: Topic to find parents for
            candidate_parent_ids: Optional list of candidate parent IDs. If not provided,
                will consider all topics in the same taxonomy
            max_suggestions: Maximum number of parent suggestions (default: 5)

        Returns:
            List of ParentSuggestion objects
        """

        # Get the topic
        topic = await self.topic_repo.get(topic_id)
        if not topic:
            raise ValueError(f"Topic with ID {topic_id} not found")

        # Get taxonomy and candidate parents
        taxonomy, all_topics = await self.taxonomy_repo.get_with_topics(
            topic.taxonomy_id, status="active"
        )

        # Filter candidate parents
        if candidate_parent_ids:
            candidates = [
                t
                for t in all_topics
                if t.id in candidate_parent_ids and t.id != topic_id
            ]
        else:
            # Exclude the topic itself and any topics that already have edges from this topic
            existing_children = {edge.child_id for edge in topic.child_edges}
            candidates = [
                t
                for t in all_topics
                if t.id != topic_id and t.id not in existing_children
            ]

        if not candidates:
            logger.warning(f"No candidate parents available for topic {topic_id}")
            return []

        # Build prompt
        user_prompt = f"""Suggest parent topics for the following topic in the "{taxonomy.title}" taxonomy.

Topic to parent:
- Title: {topic.title}
- Description: {topic.description or "No description"}

Candidate parent topics (choose the most appropriate):
{self._format_topics_for_prompt(candidates[:50])}

Select 1-5 parent topics that are broader, more general concepts than "{topic.title}".
Order by confidence (highest first)."""

        # Call LLM via PydanticAI
        result = await self.parent_agent.run(user_prompt)

        # Filter by confidence and limit - result.output is the actual list of suggestions
        suggestions = [s for s in result.output if s.confidence >= 0.5]
        suggestions.sort(key=lambda s: s.confidence, reverse=True)

        logger.info(
            f"Generated {len(suggestions)} parent suggestions for topic {topic_id}"
        )

        return suggestions[:max_suggestions]
