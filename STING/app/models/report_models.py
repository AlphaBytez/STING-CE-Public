"""
Report Models for STING-CE
Handles report generation, templates, and queue management.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Enum
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import enum
import uuid

from app.database import db

Base = db.Model

class ReportStatus(enum.Enum):
    """Report processing status"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ReportPriority(enum.Enum):
    """Report processing priority"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class ReportAccessType(enum.Enum):
    """Report access type for agentic Bee implementation"""
    USER_OWNED = "user-owned"
    SERVICE_GENERATED = "service-generated"

class ReportTemplate(Base):
    """Report template definitions"""
    __tablename__ = 'report_templates'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100), nullable=False)  # analytics, security, compliance, etc.
    
    # Template configuration
    generator_class = Column(String(255), nullable=False)  # The Python class that generates this report
    parameters = Column(JSON, nullable=False)  # Parameter definitions for the template
    template_config = Column(JSON, nullable=False, default={})  # Additional config like queries, etc.
    output_formats = Column(JSON, default=['pdf', 'xlsx', 'csv'])  # Supported output formats
    estimated_time_minutes = Column(Integer, default=5)
    
    # Privacy and security settings
    requires_scrambling = Column(Boolean, default=True)
    scrambling_profile = Column(String(100), default='gdpr_compliant')
    security_level = Column(String(50), default='standard')  # standard, high, critical
    
    # Availability and permissions
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    required_role = Column(String(50), default='user')  # user, admin, analyst
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255))
    
    # Relationships
    reports = relationship("Report", back_populates="template")
    
    def to_dict(self, include_config: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        data = {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'category': self.category,
            'generator_class': self.generator_class,
            'output_formats': self.output_formats,
            'estimated_time_minutes': self.estimated_time_minutes,
            'requires_scrambling': self.requires_scrambling,
            'scrambling_profile': self.scrambling_profile,
            'security_level': self.security_level,
            'is_active': self.is_active,
            'is_premium': self.is_premium,
            'required_role': self.required_role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by
        }
        
        if include_config:
            data['parameters'] = self.parameters
            data['template_config'] = self.template_config
        
        return data

class Report(Base):
    """Individual report requests and results"""
    __tablename__ = 'reports'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, ForeignKey('report_templates.id'), nullable=False)
    
    # User and request info
    user_id = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Processing status
    status = Column(Enum('queued', 'processing', 'completed', 'failed', 'cancelled', name='report_status'), default='queued')
    priority = Column(Enum('low', 'normal', 'high', 'urgent', name='report_priority'), default='normal')
    progress_percentage = Column(Integer, default=0)
    
    # Queue management
    queue_position = Column(Integer)
    estimated_completion = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Configuration and parameters
    parameters = Column(JSON, default={})  # User-provided parameters
    output_format = Column(String(20), default='pdf')
    honey_jar_id = Column(String(255))  # Optional source honey jar
    
    # Privacy and processing
    scrambling_enabled = Column(Boolean, default=True)
    scrambling_mapping_id = Column(String(255))  # Reference to scrambling mappings
    pii_detected = Column(Boolean, default=False)
    risk_level = Column(String(50), default='low')  # low, medium, high

    # Access control fields
    generated_by = Column(String(255))  # User ID or 'bee-service'
    access_grants = Column(JSON, default=[])  # List of user_ids granted access
    access_type = Column(Enum('user-owned', 'service-generated', name='report_access_type'), default='user-owned')
    
    # Results and files
    result_file_id = Column(String(255))  # Reference to generated file
    result_summary = Column(JSON)  # Summary statistics, key insights
    result_size_bytes = Column(Integer)
    download_count = Column(Integer, default=0)
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)  # Auto-delete after this time
    
    # Relationships
    template = relationship("ReportTemplate", back_populates="reports")
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        data = {
            'id': self.id,
            'template_id': self.template_id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'status': self.status.value if hasattr(self.status, 'value') else self.status,
            'priority': self.priority.value if hasattr(self.priority, 'value') else self.priority,
            'progress_percentage': self.progress_percentage,
            'queue_position': self.queue_position,
            'estimated_completion': self.estimated_completion.isoformat() if self.estimated_completion else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'output_format': self.output_format,
            'honey_jar_id': self.honey_jar_id,
            'scrambling_enabled': self.scrambling_enabled,
            'pii_detected': self.pii_detected,
            'risk_level': self.risk_level,
            'result_file_id': self.result_file_id,
            'result_size_bytes': self.result_size_bytes,
            'download_count': self.download_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'template': self.template.to_dict() if self.template else None,
            # Agentic Bee fields
            'generated_by': self.generated_by,
            'access_type': self.access_type.value if hasattr(self.access_type, 'value') else self.access_type,
            'access_grants': self.access_grants
        }
        
        if include_sensitive:
            data.update({
                'parameters': self.parameters,
                'scrambling_mapping_id': self.scrambling_mapping_id,
                'result_summary': self.result_summary,
                'error_message': self.error_message,
                'retry_count': self.retry_count
            })

        return data

    @property
    def is_processing(self) -> bool:
        """Check if report is currently being processed"""
        status_value = self.status.value if hasattr(self.status, 'value') else self.status
        return status_value in ['queued', 'processing']

    @property
    def is_completed(self) -> bool:
        """Check if report completed successfully"""
        status_value = self.status.value if hasattr(self.status, 'value') else self.status
        return status_value == 'completed'

    @property
    def is_failed(self) -> bool:
        """Check if report failed or was cancelled"""
        status_value = self.status.value if hasattr(self.status, 'value') else self.status
        return status_value in ['failed', 'cancelled']

    @property
    def can_retry(self) -> bool:
        """Check if report can be retried"""
        return self.is_failed and self.retry_count < self.max_retries

    # Access control helper methods
    @property
    def is_service_generated(self) -> bool:
        """Check if report was generated by Bee service"""
        access_type_value = self.access_type.value if hasattr(self.access_type, 'value') else self.access_type
        return access_type_value == 'service-generated'

    def has_access(self, user_id: str) -> bool:
        """Check if a user has access to this report"""
        # User always has access to their own reports
        if self.user_id == user_id:
            return True

        # For service-generated reports, check access_grants
        if self.is_service_generated:
            access_grants = self.access_grants or []
            return user_id in access_grants

        return False

    def grant_access(self, user_id: str) -> bool:
        """Grant access to a user for service-generated report"""
        if not self.is_service_generated:
            return False

        access_grants = self.access_grants or []
        if user_id not in access_grants:
            access_grants.append(user_id)
            self.access_grants = access_grants
            return True

        return False

    def revoke_access(self, user_id: str) -> bool:
        """Revoke access from a user for service-generated report"""
        if not self.is_service_generated:
            return False

        access_grants = self.access_grants or []
        if user_id in access_grants:
            access_grants.remove(user_id)
            self.access_grants = access_grants
            return True

        return False

class ReportQueue(Base):
    """Report processing queue management"""
    __tablename__ = 'report_queue'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String, ForeignKey('reports.id'), nullable=False)
    
    # Queue metadata
    worker_id = Column(String(255))  # Which worker is processing
    queue_name = Column(String(100), default='default')
    
    # Processing tracking
    assigned_at = Column(DateTime)
    heartbeat_at = Column(DateTime)
    timeout_at = Column(DateTime)
    
    # Retry management
    attempt_number = Column(Integer, default=1)
    last_error = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'report_id': self.report_id,
            'worker_id': self.worker_id,
            'queue_name': self.queue_name,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'heartbeat_at': self.heartbeat_at.isoformat() if self.heartbeat_at else None,
            'timeout_at': self.timeout_at.isoformat() if self.timeout_at else None,
            'attempt_number': self.attempt_number,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# Database utility functions
def get_report_by_id(session: Session, report_id: str, user_id: str = None) -> Optional[Report]:
    """Get report by ID with optional user filtering"""
    query = session.query(Report).filter(Report.id == report_id)
    if user_id:
        query = query.filter(Report.user_id == user_id)
    return query.first()

def get_user_reports(session: Session, user_id: str, limit: int = 50, offset: int = 0) -> List[Report]:
    """Get reports for a specific user (includes user-owned and granted access)"""
    from sqlalchemy import or_, cast, JSON

    # Get reports that user owns OR has been granted access to
    return session.query(Report)\
        .filter(
            or_(
                Report.user_id == user_id,
                cast(Report.access_grants, JSON).contains([user_id])
            )
        )\
        .order_by(Report.created_at.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()

def get_user_owned_reports(session: Session, user_id: str, limit: int = 50, offset: int = 0) -> List[Report]:
    """Get only reports directly owned by a user (excludes granted access)"""
    return session.query(Report)\
        .filter(Report.user_id == user_id)\
        .order_by(Report.created_at.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()

def get_report_templates(session: Session, category: str = None, user_role: str = 'user') -> List[ReportTemplate]:
    """Get available report templates for user role"""
    query = session.query(ReportTemplate)\
        .filter(ReportTemplate.is_active == True)
    
    if category:
        query = query.filter(ReportTemplate.category == category)
    
    # Filter by role (admin can see all, users see user-level templates)
    if user_role != 'admin':
        query = query.filter(ReportTemplate.required_role.in_(['user', user_role]))
    
    return query.order_by(ReportTemplate.category, ReportTemplate.display_name).all()

def get_queue_status(session: Session, queue_name: str = 'default') -> Dict[str, Any]:
    """Get current queue status and statistics"""
    total_pending = session.query(Report)\
        .filter(Report.status.in_(['pending', 'queued']))\
        .count()

    currently_processing = session.query(Report)\
        .filter(Report.status == 'processing')\
        .count()
    
    avg_processing_time = session.query(func.avg(
        func.extract('epoch', Report.completed_at - Report.started_at)
    )).filter(
        Report.status == 'completed',
        Report.completed_at >= datetime.utcnow() - timedelta(days=7)
    ).scalar()
    
    return {
        'total_pending': total_pending,
        'currently_processing': currently_processing,
        'avg_processing_time_seconds': avg_processing_time or 0,
        'queue_name': queue_name,
        'timestamp': datetime.utcnow().isoformat()
    }

def cleanup_expired_reports(session: Session) -> int:
    """Clean up expired reports and return count cleaned"""
    expired_reports = session.query(Report)\
        .filter(Report.expires_at < datetime.utcnow())\
        .all()
    
    count = len(expired_reports)
    for report in expired_reports:
        session.delete(report)
    
    session.commit()
    return count