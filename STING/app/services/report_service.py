"""
Report Service for STING-CE
Orchestrates report generation, queue management, and integration with HiveScrambler.
"""

import os
import logging
import json
import redis
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from app.models.report_models import (
    Report, ReportTemplate, ReportQueue, ReportStatus, ReportPriority,
    get_report_by_id, get_queue_status
)
from app.database import get_db_session
from app.services.hive_scrambler import HiveScrambler
from app.services.file_service import get_file_service

logger = logging.getLogger(__name__)

@dataclass
class ReportJobData:
    """Data structure for report processing jobs"""
    report_id: str
    template_id: str
    user_id: str
    parameters: Dict[str, Any]
    honey_jar_id: Optional[str] = None
    scrambling_enabled: bool = True
    priority: str = 'normal'

class ReportServiceError(Exception):
    """Custom exception for report service errors"""
    pass

class ReportService:
    """Main service for managing report generation and processing"""
    
    def __init__(self):
        self.redis_client = self._get_redis_client()
        self.scrambler = HiveScrambler()
        self.file_service = get_file_service()
        
        # Queue configuration
        self.queue_name = os.environ.get('REPORT_QUEUE_NAME', 'sting:reports')
        self.processing_queue = f"{self.queue_name}:processing"
        self.failed_queue = f"{self.queue_name}:failed"
        
        # Report processing settings
        self.max_processing_time = int(os.environ.get('REPORT_MAX_PROCESSING_TIME', '1800'))  # 30 minutes
        self.max_retries = int(os.environ.get('REPORT_MAX_RETRIES', '3'))
        
    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client for queue management"""
        try:
            redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
            client = redis.from_url(redis_url, decode_responses=True)
            
            # Test connection
            client.ping()
            logger.info("Connected to Redis for report queue management")
            return client
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise ReportServiceError(f"Redis connection failed: {str(e)}")
    
    def queue_report(self, report_id: str) -> Dict[str, Any]:
        """Queue a report for processing"""
        try:
            with get_db_session() as session:
                report = get_report_by_id(session, report_id)
                if not report:
                    return {'success': False, 'error': 'Report not found'}
                
                # Skip if report is already queued AND actually exists in Redis
                status_value = report.status.value if hasattr(report.status, 'value') else report.status
                if status_value == 'queued':
                    # Check if actually in Redis queue (not just database status)
                    jobs = self.redis_client.zrange(self.queue_name, 0, -1)
                    report_in_redis = any(
                        report_id in (job.decode() if hasattr(job, 'decode') else str(job))
                        for job in jobs
                    )

                    if report_in_redis:
                        # Report is already queued in Redis, return success
                        return {
                            'success': True,
                            'queue_position': report.queue_position,
                            'estimated_completion': report.estimated_completion.isoformat() if report.estimated_completion else None
                        }
                    else:
                        # Database says queued but not in Redis - proceed with queueing
                        logger.warning(f"Report {report_id} marked as queued in DB but not in Redis - re-queueing")
                
                # Create job data
                job_data = ReportJobData(
                    report_id=report.id,
                    template_id=report.template_id,
                    user_id=report.user_id,
                    parameters=report.parameters or {},
                    honey_jar_id=report.honey_jar_id,
                    scrambling_enabled=report.scrambling_enabled,
                    priority=report.priority.value if hasattr(report.priority, 'value') else (report.priority if report.priority else 'normal')
                )
                
                # Calculate priority score for queue ordering
                priority_scores = {
                    'urgent': 1000,
                    'high': 100,
                    'normal': 10,
                    'low': 1
                }
                priority_score = priority_scores.get(job_data.priority, 10)
                
                # Add timestamp for FIFO within same priority
                timestamp_score = int(datetime.utcnow().timestamp())
                final_score = priority_score * 1000000 + timestamp_score
                
                # Add to Redis sorted set (higher score = higher priority)
                job_payload = {
                    'report_id': job_data.report_id,
                    'template_id': job_data.template_id,
                    'user_id': job_data.user_id,
                    'parameters': job_data.parameters,
                    'honey_jar_id': job_data.honey_jar_id,
                    'scrambling_enabled': job_data.scrambling_enabled,
                    'priority': job_data.priority,
                    'queued_at': datetime.utcnow().isoformat(),
                    'timeout_at': (datetime.utcnow() + timedelta(seconds=self.max_processing_time)).isoformat()
                }
                
                self.redis_client.zadd(
                    self.queue_name,
                    {json.dumps(job_payload): final_score}
                )
                
                # Update report status (use string value to match database enum)
                report.status = 'queued'
                report.queue_position = self._get_queue_position(report_id)
                report.estimated_completion = self._estimate_completion_time()
                session.commit()
                
                logger.info(f"Queued report {report_id} with priority {job_data.priority}")
                
                return {
                    'success': True,
                    'queue_position': report.queue_position,
                    'estimated_completion': report.estimated_completion.isoformat() if report.estimated_completion else None
                }
                
        except Exception as e:
            logger.error(f"Error queuing report {report_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_queue_position(self, report_id: str) -> Optional[int]:
        """Get current position of report in queue"""
        try:
            # Get all jobs in queue ordered by score (priority)
            jobs = self.redis_client.zrevrange(self.queue_name, 0, -1)
            
            for idx, job_json in enumerate(jobs):
                job_data = json.loads(job_json)
                if job_data['report_id'] == report_id:
                    return idx + 1
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting queue position for {report_id}: {e}")
            return None
    
    def _estimate_completion_time(self) -> Optional[datetime]:
        """Estimate when the next job will be completed"""
        try:
            # Simple estimation: current queue size * average processing time
            queue_size = self.redis_client.zcard(self.queue_name)
            
            with get_db_session() as session:
                status = get_queue_status(session)
                avg_processing_time = status.get('avg_processing_time_seconds', 300)  # Default 5 minutes
            
            estimated_seconds = queue_size * avg_processing_time
            return datetime.utcnow() + timedelta(seconds=estimated_seconds)
            
        except Exception as e:
            logger.warning(f"Error estimating completion time: {e}")
            return None
    
    def get_next_job(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get next job from queue for processing"""
        try:
            # Get highest priority job from queue
            jobs = self.redis_client.zrevrange(self.queue_name, 0, 0)
            if not jobs:
                return None
            
            job_json = jobs[0]
            job_data = json.loads(job_json)
            
            # Remove from main queue and add to processing queue
            pipe = self.redis_client.pipeline()
            pipe.zrem(self.queue_name, job_json)
            pipe.hset(self.processing_queue, job_data['report_id'], json.dumps({
                **job_data,
                'worker_id': worker_id,
                'started_at': datetime.utcnow().isoformat()
            }))
            pipe.execute()
            
            # Update report status in database
            with get_db_session() as session:
                report = get_report_by_id(session, job_data['report_id'])
                if report:
                    report.status = 'processing'
                    report.started_at = datetime.utcnow()
                    report.queue_position = None
                    session.commit()
            
            logger.info(f"Assigned job {job_data['report_id']} to worker {worker_id}")
            return job_data
            
        except Exception as e:
            logger.error(f"Error getting next job for worker {worker_id}: {e}")
            return None
    
    def complete_job(self, report_id: str, result_file_id: str, result_summary: Dict[str, Any] = None) -> bool:
        """Mark job as completed"""
        try:
            with get_db_session() as session:
                report = get_report_by_id(session, report_id)
                if not report:
                    logger.error(f"Report {report_id} not found for completion")
                    return False
                
                # Update report
                report.status = 'completed'
                report.completed_at = datetime.utcnow()
                report.progress_percentage = 100
                report.result_file_id = result_file_id
                report.result_summary = result_summary
                
                # Get file size if available
                if result_file_id:
                    file_metadata = self.file_service.get_file_metadata(result_file_id, report.user_id)
                    if file_metadata:
                        report.result_size_bytes = file_metadata.get('file_size', 0)
                
                session.commit()
            
            # Remove from processing queue
            self.redis_client.hdel(self.processing_queue, report_id)
            
            logger.info(f"Completed report {report_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error completing job {report_id}: {e}")
            return False
    
    def fail_job(self, report_id: str, error_message: str, retry: bool = True) -> bool:
        """Mark job as failed with optional retry"""
        try:
            with get_db_session() as session:
                report = get_report_by_id(session, report_id)
                if not report:
                    logger.error(f"Report {report_id} not found for failure")
                    return False
                
                report.error_message = error_message
                report.retry_count += 1
                
                if retry and report.can_retry:
                    # Queue for retry
                    report.status = 'pending'
                    report.progress_percentage = 0
                    session.commit()
                    
                    # Re-queue the job
                    self.queue_report(report_id)
                    
                    logger.info(f"Queued report {report_id} for retry (attempt {report.retry_count})")
                else:
                    # Mark as permanently failed
                    report.status = 'failed'
                    report.completed_at = datetime.utcnow()
                    session.commit()
                    
                    # Move to failed queue for analysis
                    processing_data = self.redis_client.hget(self.processing_queue, report_id)
                    if processing_data:
                        self.redis_client.hset(self.failed_queue, report_id, processing_data)
                    
                    logger.error(f"Failed report {report_id} permanently: {error_message}")
            
            # Remove from processing queue
            self.redis_client.hdel(self.processing_queue, report_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error failing job {report_id}: {e}")
            return False
    
    def update_progress(self, report_id: str, progress_percentage: int, status_message: str = None) -> bool:
        """Update job progress"""
        try:
            with get_db_session() as session:
                report = get_report_by_id(session, report_id)
                if not report:
                    return False
                
                report.progress_percentage = min(100, max(0, progress_percentage))
                if status_message:
                    # Could store in metadata or separate status table
                    pass
                
                session.commit()
            
            # Update heartbeat in processing queue
            processing_data = self.redis_client.hget(self.processing_queue, report_id)
            if processing_data:
                job_data = json.loads(processing_data)
                job_data['last_heartbeat'] = datetime.utcnow().isoformat()
                job_data['progress_percentage'] = progress_percentage
                self.redis_client.hset(self.processing_queue, report_id, json.dumps(job_data))
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating progress for {report_id}: {e}")
            return False
    
    def cancel_report(self, report_id: str) -> bool:
        """Cancel a report (remove from queue)"""
        try:
            # Remove from main queue
            jobs = self.redis_client.zrange(self.queue_name, 0, -1)
            for job_json in jobs:
                job_data = json.loads(job_json)
                if job_data['report_id'] == report_id:
                    self.redis_client.zrem(self.queue_name, job_json)
                    break
            
            # Remove from processing queue
            self.redis_client.hdel(self.processing_queue, report_id)
            
            logger.info(f"Cancelled report {report_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling report {report_id}: {e}")
            return False
    
    def cleanup_stale_jobs(self) -> Dict[str, int]:
        """Clean up stale processing jobs that have timed out"""
        try:
            stale_count = 0
            processing_jobs = self.redis_client.hgetall(self.processing_queue)
            
            for report_id, job_json in processing_jobs.items():
                try:
                    job_data = json.loads(job_json)
                    timeout_str = job_data.get('timeout_at')
                    
                    if timeout_str:
                        timeout_time = datetime.fromisoformat(timeout_str)
                        if datetime.utcnow() > timeout_time:
                            # Job has timed out
                            self.fail_job(report_id, "Job timed out", retry=True)
                            stale_count += 1
                            
                except Exception as e:
                    logger.warning(f"Error processing stale job {report_id}: {e}")
                    # Remove corrupted job data
                    self.redis_client.hdel(self.processing_queue, report_id)
                    stale_count += 1
            
            return {'stale_jobs_cleaned': stale_count}
            
        except Exception as e:
            logger.error(f"Error cleaning up stale jobs: {e}")
            return {'stale_jobs_cleaned': 0, 'error': str(e)}
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics"""
        try:
            queue_size = self.redis_client.zcard(self.queue_name)
            processing_count = self.redis_client.hlen(self.processing_queue)
            failed_count = self.redis_client.hlen(self.failed_queue)
            
            # Get database stats
            with get_db_session() as session:
                db_stats = get_queue_status(session)
            
            return {
                'queue_size': queue_size,
                'processing_count': processing_count,
                'failed_count': failed_count,
                'database_stats': db_stats,
                'queue_name': self.queue_name,
                'max_processing_time': self.max_processing_time,
                'max_retries': self.max_retries,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {'error': str(e)}

    def create_bee_service_report(
        self,
        user_id: str,
        user_message: str,
        conversation_id: Optional[str] = None,
        honey_jar_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a service-generated report for complex Bee queries.

        This method is called when a user's query exceeds the interactive token threshold
        and should be processed as an asynchronous report instead.

        Args:
            user_id: ID of the user requesting the report
            user_message: The complex query from the user
            conversation_id: Optional conversation ID for context
            honey_jar_id: Optional honey jar ID to query against
            context: Optional additional context

        Returns:
            Dict with report creation status and metadata
        """
        try:
            with get_db_session() as session:
                # Find or create a dynamic report template for Bee-generated reports
                template = session.query(ReportTemplate).filter(
                    ReportTemplate.name == 'bee_conversational_report'
                ).first()

                if not template:
                    # Create template if it doesn't exist
                    template = ReportTemplate(
                        name='bee_conversational_report',
                        display_name='Bee Conversational Report',
                        description='Dynamic report generated from complex Bee chat queries',
                        category='conversational',
                        generator_class='BeeConversationalReportGenerator',
                        parameters={},
                        template_config={
                            'supports_honey_jar': True,
                            'supports_conversation_context': True
                        },
                        output_formats=['pdf', 'md', 'html'],
                        estimated_time_minutes=10,
                        requires_scrambling=True,
                        is_active=True,
                        created_by='bee-service'
                    )
                    session.add(template)
                    session.flush()

                # Generate report title from user message (first 100 chars)
                title_preview = user_message[:100]
                if len(user_message) > 100:
                    title_preview += "..."

                title = f"Bee Report: {title_preview}"

                # Create the service-generated report
                report = Report(
                    template_id=template.id,
                    user_id=user_id,
                    title=title,
                    description=f"Report generated from conversation {conversation_id or 'N/A'}",
                    priority='normal',
                    parameters={
                        'user_query': user_message,
                        'conversation_id': conversation_id,
                        'generation_mode': 'conversational',
                        'context': context or {}
                    },
                    output_format='pdf',
                    honey_jar_id=honey_jar_id,
                    scrambling_enabled=True,
                    expires_at=datetime.utcnow() + timedelta(days=30),
                    # Access control - service-generated
                    generated_by='bee-service',
                    access_type='service-generated',
                    access_grants=[]  # User must grant themselves access (AAL2)
                )

                session.add(report)
                session.commit()

                # Queue the report for processing
                queue_result = self.queue_report(report.id)

                if not queue_result['success']:
                    logger.error(f"Failed to queue Bee service report {report.id}")
                    return {
                        'success': False,
                        'error': 'Failed to queue report for processing',
                        'report_id': report.id
                    }

                logger.info(
                    f"Created service-generated report {report.id} for user {user_id} "
                    f"from complex query (conversation: {conversation_id})"
                )

                return {
                    'success': True,
                    'report_id': report.id,
                    'report': report.to_dict(),
                    'queue_position': queue_result.get('queue_position'),
                    'estimated_completion': queue_result.get('estimated_completion'),
                    'message': 'Your query is complex and will be processed as a report. You will be notified when it\'s ready.'
                }

        except Exception as e:
            logger.error(f"Error creating Bee service report: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Failed to create report: {str(e)}'
            }

    def health_check(self) -> bool:
        """Check if report service is healthy"""
        try:
            # Test Redis connection
            self.redis_client.ping()
            
            # Test database connection
            with get_db_session() as session:
                session.query(Report).limit(1).all()
            
            # Test HiveScrambler
            test_result = self.scrambler.detect_pii("test@example.com")
            
            return True
            
        except Exception as e:
            logger.error(f"Report service health check failed: {e}")
            return False

# Global service instance
_report_service = None

def get_report_service() -> ReportService:
    """Get the global report service instance"""
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service