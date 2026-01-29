"""
Interview management service.

Handles interview scheduling, transcription, and AI-powered analysis.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge_preservation import (
    Interview, InterviewTemplate, SubjectMatterExpert,
    KnowledgeDomain, InterviewStatus
)
from utils.logging import ServiceLogger
from utils.ai_client import ai_client
from config.settings import settings


class InterviewService:
    """
    Service for managing knowledge capture interviews.
    
    Provides:
    - Interview scheduling and tracking
    - Transcript processing
    - AI-powered topic extraction
    - Interview question templates
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("interview")
    
    async def schedule_interview(
        self,
        title: str,
        knowledge_domain_id: str,
        sme_id: str,
        scheduled_date: datetime,
        interviewer_id: str | None = None,
        template_id: str | None = None,
        description: str | None = None,
    ) -> Interview:
        """
        Schedule a new interview.
        
        Args:
            title: Interview title
            knowledge_domain_id: Related knowledge domain
            sme_id: Subject matter expert ID
            scheduled_date: Scheduled date/time
            interviewer_id: Interviewer user ID
            template_id: Interview template to use
            description: Interview description
            
        Returns:
            Created Interview instance
        """
        self.logger.log_operation_start(
            "schedule_interview",
            tenant_id=self.tenant_id,
            sme_id=sme_id,
        )
        
        interview = Interview(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            title=title,
            description=description,
            knowledge_domain_id=knowledge_domain_id,
            sme_id=sme_id,
            scheduled_date=scheduled_date,
            interviewer_id=interviewer_id,
            question_template_id=template_id,
            status=InterviewStatus.SCHEDULED,
        )
        
        # Load template questions if provided
        if template_id:
            template = await self._get_template(template_id)
            if template:
                interview.questions_asked = template.questions
        
        self.session.add(interview)
        await self.session.flush()
        
        self.logger.log_operation_complete(
            "schedule_interview",
            tenant_id=self.tenant_id,
            interview_id=interview.id,
        )
        
        return interview
    
    async def start_interview(self, interview_id: str) -> Interview | None:
        """Mark an interview as in progress."""
        interview = await self.get_interview(interview_id)
        if not interview or interview.status != InterviewStatus.SCHEDULED:
            return None
        
        interview.status = InterviewStatus.IN_PROGRESS
        interview.actual_start_time = datetime.utcnow()
        
        await self.session.flush()
        return interview
    
    async def complete_interview(
        self,
        interview_id: str,
        recording_path: str | None = None,
        interviewer_notes: str | None = None,
    ) -> Interview | None:
        """
        Mark an interview as completed.
        
        Args:
            interview_id: Interview to complete
            recording_path: Path to recording file
            interviewer_notes: Notes from interviewer
            
        Returns:
            Updated Interview or None
        """
        interview = await self.get_interview(interview_id)
        if not interview or interview.status != InterviewStatus.IN_PROGRESS:
            return None
        
        interview.status = InterviewStatus.COMPLETED
        interview.actual_end_time = datetime.utcnow()
        
        if interview.actual_start_time:
            duration = interview.actual_end_time - interview.actual_start_time
            interview.duration_minutes = int(duration.total_seconds() / 60)
        
        if recording_path:
            interview.recording_storage_path = recording_path
        
        if interviewer_notes:
            interview.interviewer_notes = interviewer_notes
        
        await self.session.flush()
        return interview
    
    async def submit_transcript(
        self,
        interview_id: str,
        transcript: str,
    ) -> Interview | None:
        """
        Submit a transcript for processing.
        
        Args:
            interview_id: Interview ID
            transcript: Raw transcript text
            
        Returns:
            Updated Interview or None
        """
        self.logger.log_operation_start(
            "submit_transcript",
            tenant_id=self.tenant_id,
            interview_id=interview_id,
        )
        
        interview = await self.get_interview(interview_id)
        if not interview:
            return None
        
        interview.transcript_raw = transcript
        interview.status = InterviewStatus.TRANSCRIBED
        
        await self.session.flush()
        
        # Trigger async processing
        await self._process_transcript(interview)
        
        self.logger.log_operation_complete(
            "submit_transcript",
            tenant_id=self.tenant_id,
            interview_id=interview_id,
        )
        
        return interview
    
    async def process_transcript(self, interview_id: str) -> Interview | None:
        """
        Process a transcript to extract structured knowledge.
        
        Args:
            interview_id: Interview to process
            
        Returns:
            Updated Interview with extracted data
        """
        interview = await self.get_interview(interview_id)
        if not interview or not interview.transcript_raw:
            return None
        
        interview.status = InterviewStatus.PROCESSING
        await self.session.flush()
        
        await self._process_transcript(interview)
        
        return interview
    
    async def _process_transcript(self, interview: Interview) -> None:
        """Internal method to process transcript with AI."""
        try:
            # Clean transcript
            cleaned = await self._clean_transcript(interview.transcript_raw)
            interview.transcript_cleaned = cleaned
            
            # Extract topics
            topics = await self._extract_topics(cleaned)
            interview.extracted_topics = topics
            
            # Extract procedures
            procedures = await self._extract_procedures(cleaned)
            interview.extracted_procedures = procedures
            
            # Generate summary
            summary = await self._generate_summary(cleaned)
            interview.ai_summary = summary
            
            # Extract key insights
            insights = await self._extract_insights(cleaned)
            interview.key_insights = insights
            
            # Segment transcript
            segments = await self._segment_transcript(cleaned)
            interview.transcript_segments = segments
            
            interview.status = InterviewStatus.PROCESSED
            interview.processing_metadata = {
                "processed_at": datetime.utcnow().isoformat(),
                "topics_count": len(topics),
                "procedures_count": len(procedures),
                "segments_count": len(segments),
            }
            
        except Exception as e:
            self.logger.log_operation_failed(
                "process_transcript",
                e,
                tenant_id=self.tenant_id,
                interview_id=interview.id,
            )
            interview.status = InterviewStatus.FAILED
            interview.processing_metadata = {
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat(),
            }
        
        await self.session.flush()
    
    async def _clean_transcript(self, raw_transcript: str) -> str:
        """Clean and normalize transcript text."""
        prompt = """
Clean and normalize this interview transcript:

1. Fix obvious transcription errors
2. Remove filler words (um, uh, like)
3. Fix punctuation and capitalization
4. Preserve technical terms accurately
5. Keep the speaker attributions if present

Transcript:
{transcript}

Return the cleaned transcript only.
""".format(transcript=raw_transcript[:8000])  # Limit for API
        
        return await ai_client.generate_text(
            prompt,
            system_prompt="You are a transcript editor. Clean the text while preserving accuracy.",
            max_tokens=4000,
        )
    
    async def _extract_topics(self, transcript: str) -> list[str]:
        """Extract main topics from transcript."""
        prompt = f"""
Extract the main topics discussed in this interview transcript.
Focus on manufacturing procedures, processes, and knowledge areas.

Transcript:
{transcript[:6000]}

Return a JSON array of topic strings.
"""
        
        result = await ai_client.generate_structured(
            prompt,
            {"type": "array", "items": {"type": "string"}},
            system_prompt="Extract manufacturing topics from the interview.",
        )
        
        return result if isinstance(result, list) else []
    
    async def _extract_procedures(self, transcript: str) -> list[dict]:
        """Extract procedural knowledge from transcript."""
        prompt = f"""
Extract any procedures, processes, or step-by-step instructions mentioned 
in this interview transcript.

Transcript:
{transcript[:6000]}

For each procedure found, provide:
- name: Name of the procedure
- description: Brief description
- steps: Array of step descriptions
- cautions: Any safety considerations mentioned
- tips: Any tips or best practices mentioned
"""
        
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "cautions": {"type": "array", "items": {"type": "string"}},
                    "tips": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
        
        result = await ai_client.generate_structured(prompt, schema)
        return result if isinstance(result, list) else []
    
    async def _generate_summary(self, transcript: str) -> str:
        """Generate executive summary of interview."""
        prompt = f"""
Generate an executive summary of this knowledge capture interview.

Include:
1. Main topics covered
2. Key procedures discussed
3. Important insights or tribal knowledge
4. Recommended follow-up topics

Transcript:
{transcript[:6000]}
"""
        
        return await ai_client.generate_text(
            prompt,
            system_prompt="Summarize manufacturing knowledge interviews concisely.",
            max_tokens=1000,
        )
    
    async def _extract_insights(self, transcript: str) -> list[dict]:
        """Extract key insights and tribal knowledge."""
        prompt = f"""
Extract key insights and "tribal knowledge" from this interview.
Focus on:
- Undocumented best practices
- Common pitfalls and how to avoid them
- Time-saving techniques
- Quality tips
- Safety considerations not in manuals

Transcript:
{transcript[:6000]}
"""
        
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "insight": {"type": "string"},
                    "category": {"type": "string"},
                    "importance": {"type": "string"},
                },
            },
        }
        
        result = await ai_client.generate_structured(prompt, schema)
        return result if isinstance(result, list) else []
    
    async def _segment_transcript(self, transcript: str) -> list[dict]:
        """Segment transcript into logical sections."""
        prompt = f"""
Segment this interview transcript into logical sections based on topics discussed.

For each segment, provide:
- start_text: First few words of the segment
- topic: What topic this segment covers
- summary: Brief summary of the segment

Transcript:
{transcript[:6000]}
"""
        
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_text": {"type": "string"},
                    "topic": {"type": "string"},
                    "summary": {"type": "string"},
                },
            },
        }
        
        result = await ai_client.generate_structured(prompt, schema)
        return result if isinstance(result, list) else []
    
    async def get_interview(self, interview_id: str) -> Interview | None:
        """Get an interview by ID."""
        result = await self.session.execute(
            select(Interview).where(
                and_(
                    Interview.id == interview_id,
                    Interview.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_interviews(
        self,
        knowledge_domain_id: str | None = None,
        sme_id: str | None = None,
        status: InterviewStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Interview], int]:
        """List interviews with filters."""
        conditions = [Interview.tenant_id == self.tenant_id]
        
        if knowledge_domain_id:
            conditions.append(Interview.knowledge_domain_id == knowledge_domain_id)
        
        if sme_id:
            conditions.append(Interview.sme_id == sme_id)
        
        if status:
            conditions.append(Interview.status == status)
        
        # Count
        count_result = await self.session.execute(
            select(func.count(Interview.id)).where(and_(*conditions))
        )
        total = count_result.scalar_one()
        
        # Get interviews
        result = await self.session.execute(
            select(Interview)
            .where(and_(*conditions))
            .order_by(Interview.scheduled_date.desc())
            .limit(limit)
            .offset(offset)
        )
        interviews = result.scalars().all()
        
        return list(interviews), total
    
    async def _get_template(self, template_id: str) -> InterviewTemplate | None:
        """Get interview template."""
        result = await self.session.execute(
            select(InterviewTemplate).where(
                and_(
                    InterviewTemplate.id == template_id,
                    InterviewTemplate.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def create_template(
        self,
        name: str,
        questions: list[dict],
        target_category: str | None = None,
        description: str | None = None,
        estimated_duration_minutes: int = 60,
    ) -> InterviewTemplate:
        """Create an interview question template."""
        template = InterviewTemplate(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            name=name,
            description=description,
            questions=questions,
            estimated_duration_minutes=estimated_duration_minutes,
        )
        
        self.session.add(template)
        await self.session.flush()
        
        return template
    
    async def suggest_follow_up_questions(
        self,
        interview_id: str,
    ) -> list[str]:
        """
        Suggest follow-up questions based on interview content.
        
        Args:
            interview_id: Interview to analyze
            
        Returns:
            List of suggested follow-up questions
        """
        interview = await self.get_interview(interview_id)
        if not interview or not interview.transcript_cleaned:
            return []
        
        prompt = f"""
Based on this interview transcript, suggest follow-up questions to capture 
any missing knowledge or unclear points.

Focus on:
1. Procedures that need more detail
2. Edge cases not covered
3. Troubleshooting scenarios
4. Safety considerations
5. Quality checkpoints

Summary: {interview.ai_summary or 'Not available'}
Topics covered: {', '.join(interview.extracted_topics or [])}

Provide 5-10 specific follow-up questions.
"""
        
        schema = {
            "type": "array",
            "items": {"type": "string"},
        }
        
        result = await ai_client.generate_structured(prompt, schema)
        
        if isinstance(result, list):
            interview.follow_up_questions = result
            await self.session.flush()
            return result
        
        return []
