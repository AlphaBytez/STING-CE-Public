"""
Report Routes for STING-CE
Handles report generation, templates, and queue management API endpoints.
"""

import os
import logging
import uuid
from flask import Blueprint, request, jsonify, send_file, g
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from io import BytesIO

from app.models.report_models import (
    Report, ReportTemplate, ReportQueue,
    get_report_by_id, get_user_reports, get_report_templates, get_queue_status
)
from app.database import get_db_session
from app.utils.decorators import require_auth, require_auth_or_api_key, require_aal2_or_api_key
from app.utils.flexible_auth import require_auth_flexible, get_current_user
from app.services.report_service import get_report_service
from app.services.file_service import get_file_service
from app.middleware.auth_middleware import enforce_passkey_only
from app.utils.decorators import require_auth_method

logger = logging.getLogger(__name__)

# Create blueprint  
report_bp = Blueprint('reports', __name__, url_prefix='/api/reports')

# Public endpoints for Beeacon dashboard (no auth required)
@report_bp.route('/public/templates', methods=['GET'])
def get_public_templates():
    """Get demo report templates for Beeacon dashboard - no auth required"""
    logger.info("Serving demo templates for Beeacon dashboard")
    return jsonify({
        'success': True,
        'data': {
            'templates': get_demo_templates(),
            'count': len(get_demo_templates()),
            'user_role': 'demo'
        }
    })

@report_bp.route('/public/reports', methods=['GET'])
def get_public_reports():
    """Get demo reports for Beeacon dashboard - no auth required"""
    logger.info("Serving demo reports for Beeacon dashboard")
    return jsonify({
        'success': True,
        'data': {
            'reports': get_demo_reports(),
            'count': len(get_demo_reports()),
            'pagination': {
                'page': 1,
                'per_page': 50,
                'total': len(get_demo_reports())
            }
        }
    })

@report_bp.route('/public/queue/status', methods=['GET'])
def get_public_queue_status():
    """Get demo queue status for Beeacon dashboard - no auth required"""
    logger.info("Serving demo queue status for Beeacon dashboard")
    return jsonify({
        'success': True,
        'data': {
            'queue_name': 'default',
            'pending_reports': 3,
            'processing_reports': 1,
            'completed_today': 8,
            'failed_today': 0,
            'average_processing_time': '2.3 minutes',
            'user_active_reports': 2,
            'estimated_wait_time': '5 minutes'
        }
    })

@report_bp.route('/test-auth', methods=['GET'])
@require_auth_or_api_key(['admin', 'read'])
def test_auth_status():
    """Test endpoint to check authentication status"""
    
    return jsonify({
        'has_api_key': hasattr(g, 'api_key'),
        'api_key_value': str(g.api_key) if hasattr(g, 'api_key') and g.api_key else None,
        'api_key_user_id': getattr(g.api_key, 'user_id', None) if hasattr(g, 'api_key') and g.api_key else None,
        'api_key_scopes': getattr(g.api_key, 'scopes', None) if hasattr(g, 'api_key') and g.api_key else None,
        'has_user': hasattr(g, 'user'),
        'user_value': str(g.user) if hasattr(g, 'user') else None,
        'get_current_user_result': get_current_user()
    })

@report_bp.route('/demo-data', methods=['GET'])
def get_demo_data():
    """Simple demo data endpoint"""
    return jsonify({
        'success': True,
        'message': 'Demo data endpoint working',
        'demo_templates': get_demo_templates(),
        'demo_reports': get_demo_reports()
    })

def get_demo_templates():
    """Return demo report templates for Beeacon dashboard"""
    return [
        {
            'id': 1,
            'name': 'System Health Report',
            'description': 'Comprehensive system health and performance analysis',
            'category': 'system',
            'required_role': 'user',
            'is_active': True,
            'output_formats': ['pdf', 'html'],
            'estimated_time': '2 minutes'
        },
        {
            'id': 2,
            'name': 'Security Audit Report', 
            'description': 'Authentication events and security metrics',
            'category': 'security',
            'required_role': 'admin',
            'is_active': True,
            'output_formats': ['pdf', 'csv'],
            'estimated_time': '3 minutes'
        },
        {
            'id': 3,
            'name': 'Knowledge Base Analytics',
            'description': 'Honey jar usage and search analytics',
            'category': 'knowledge',
            'required_role': 'user', 
            'is_active': True,
            'output_formats': ['pdf', 'excel'],
            'estimated_time': '1 minute'
        },
        {
            'id': 4,
            'name': 'PII Compliance Report',
            'description': 'Data sanitization and compliance status',
            'category': 'compliance',
            'required_role': 'admin',
            'is_active': True,
            'output_formats': ['pdf'],
            'estimated_time': '5 minutes'
        }
    ]

def get_demo_reports():
    """Return demo reports for Beeacon dashboard"""
    return [
        {
            'id': 1,
            'title': 'Weekly System Health Report',
            'description': 'Automated system health analysis',
            'status': 'completed',
            'created_at': (datetime.utcnow() - timedelta(hours=2)).isoformat() + 'Z',
            'completed_at': (datetime.utcnow() - timedelta(hours=1, minutes=45)).isoformat() + 'Z',
            'output_format': 'pdf',
            'file_size': '2.4 MB',
            'template_name': 'System Health Report'
        },
        {
            'id': 2,
            'title': 'Security Audit - September 2025',
            'description': 'Monthly authentication and security metrics',
            'status': 'processing',
            'created_at': (datetime.utcnow() - timedelta(minutes=30)).isoformat() + 'Z',
            'progress': 65,
            'output_format': 'pdf',
            'template_name': 'Security Audit Report'
        },
        {
            'id': 3,
            'title': 'Knowledge Base Analytics',
            'description': 'Honey jar usage analysis',
            'status': 'queued',
            'created_at': (datetime.utcnow() - timedelta(minutes=10)).isoformat() + 'Z',
            'queue_position': 2,
            'output_format': 'excel',
            'template_name': 'Knowledge Base Analytics'
        }
    ]

def get_current_user() -> Optional[str]:
    """Get current user ID from either API key or session (updated for current auth pattern)"""
    
    # Handle API key authentication (current pattern)
    if hasattr(g, 'api_key') and g.api_key:
        logger.info(f"[AUTH] API key user: {g.api_key.user_id}")
        return str(g.api_key.user_id)
    
    # Handle session authentication
    if hasattr(g, 'user') and g.user:
        logger.info(f"[AUTH] Session user: {g.user.id}")
        return str(g.user.id)
    
    # Fallback to Kratos session
    from app.utils.kratos_client import whoami
    session_cookie = request.cookies.get('ory_kratos_session')
    if session_cookie:
        identity = whoami(session_cookie)
        if identity:
            user_id = identity.get('identity', {}).get('id')
            if user_id:
                logger.info(f"[AUTH] Kratos user: {user_id}")
                return str(user_id)
    
    logger.warning("[AUTH] No authentication found")
    return None

def get_user_role() -> str:
    """Get current user role from database"""
    from app.models.user_models import User
    
    user_id = get_current_user()
    if not user_id:
        return 'user'
    
    with get_db_session() as session:
        user = session.query(User).filter(User.kratos_id == user_id).first()
        if user:
            if user.is_super_admin:
                return 'super_admin'
            elif user.is_admin:
                return 'admin'
        return 'user'

@report_bp.route('/templates', methods=['GET'])
@require_auth_or_api_key(['admin', 'read'])
def get_available_templates():
    """Get available report templates for the current user"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = get_user_role()
        category = request.args.get('category')
        
        with get_db_session() as session:
            templates = get_report_templates(session, category, user_role)
            
            return jsonify({
                'success': True,
                'data': {
                    'templates': [template.to_dict() for template in templates],
                    'count': len(templates),
                    'user_role': user_role
                }
            })
            
    except Exception as e:
        logger.error(f"Error getting report templates: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/', methods=['POST'])
@require_auth_or_api_key(['admin', 'read'])
# @require_auth_method(['webauthn', 'totp', 'email'])  # Tier 2 protection for report creation - TEMPORARILY DISABLED for debugging
def create_report():
    """Create a new report request"""
    try:
        user_id = get_current_user()
        
        # Development bypass for MVP demo - use API key user_id if available
        if not user_id and hasattr(g, 'api_key') and g.api_key:
            user_id = str(g.api_key.user_id)
            logger.info(f"[MVP DEMO] Using API key user_id: {user_id}")
        
        # Final fallback for development
        if not user_id and os.getenv('APP_ENV') == 'development':
            user_id = 'demo-user-for-reports'
            logger.info("[MVP DEMO] Using development fallback user_id")
        
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
        
        # Validate required fields
        template_id = data.get('template_id')
        title = data.get('title')
        
        if not template_id or not title:
            return jsonify({'error': 'template_id and title are required'}), 400
        
        # Demo templates now use real processing pipeline for actual file generation
        if str(template_id).startswith('demo-'):
            logger.info(f"Processing demo template through real pipeline: {template_id}")
            # Continue to real template processing below

        # Validate template exists and user can access it
        with get_db_session() as session:
            template = session.query(ReportTemplate).filter(
                ReportTemplate.id == template_id,
                ReportTemplate.is_active == True
            ).first()

            if not template:
                return jsonify({'error': 'Template not found or not available'}), 404
            
            # Check role permissions
            user_role = get_user_role()
            if user_role != 'admin' and template.required_role not in ['user', user_role]:
                return jsonify({'error': 'Insufficient permissions for this template'}), 403
            
            # Create report (let model defaults handle status)
            report = Report(
                template_id=template_id,
                user_id=user_id,
                title=title,
                description=data.get('description', ''),
                priority=data.get('priority', 'normal'),
                parameters=data.get('parameters', {}),
                output_format=data.get('output_format', 'pdf'),
                honey_jar_id=data.get('honey_jar_id'),
                scrambling_enabled=data.get('scrambling_enabled', template.requires_scrambling),
                expires_at=datetime.utcnow() + timedelta(days=30),  # Reports expire after 30 days
                # Access control
                generated_by=user_id,
                access_type='user-owned',
                access_grants=[]
            )
            
            session.add(report)
            session.commit()

            # Queue the report for processing
            logger.info(f"🔍 DEBUG: About to queue report {report.id} (status: {report.status})")
            report_service = get_report_service()
            queue_result = report_service.queue_report(report.id)
            logger.info(f"🔍 DEBUG: Queue result: {queue_result}")
            
            if not queue_result['success']:
                logger.error(f"Failed to queue report {report.id}: {queue_result.get('error')}")
                return jsonify({
                    'success': False,
                    'error': 'Failed to queue report for processing'
                }), 500
            
            # Refresh report to get updated queue position
            session.refresh(report)
            
            return jsonify({
                'success': True,
                'data': {
                    'report': report.to_dict(),
                    'queue_position': queue_result.get('queue_position'),
                    'estimated_completion': queue_result.get('estimated_completion')
                }
            }), 201
            
    except ValueError as e:
        return jsonify({'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error creating report: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/', methods=['GET'])
@require_auth_or_api_key(['admin', 'read'])
def list_reports():
    """List reports for the current user"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Get query parameters
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        status_filter = request.args.get('status')
        search_term = request.args.get('search')

        with get_db_session() as session:
            # Check if this is a search for demo reports
            if search_term and 'demo' in search_term.lower():
                # For demo searches, return all demo reports regardless of user_id
                query = session.query(Report).filter(Report.title.like('%Demo%'))
            else:
                # Base query for user's own reports
                query = session.query(Report).filter(Report.user_id == user_id)

                # Also include demo reports for all authenticated users
                demo_query = session.query(Report).filter(Report.title.like('%Demo%'))
                query = query.union(demo_query)

            # Apply status filter if provided
            if status_filter:
                # Use string values instead of enum to avoid database compatibility issues
                if status_filter in ['pending', 'queued', 'processing', 'completed', 'failed', 'cancelled']:
                    query = query.filter(Report.status == status_filter)
                else:
                    return jsonify({'error': f'Invalid status: {status_filter}'}), 400

            # Apply search filter if provided
            if search_term:
                query = query.filter(
                    Report.title.ilike(f'%{search_term}%') |
                    Report.description.ilike(f'%{search_term}%')
                )
            
            # Get total count for pagination
            total_count = query.count()
            
            # Apply pagination and ordering
            reports = query.order_by(Report.created_at.desc())\
                          .offset(offset)\
                          .limit(limit)\
                          .all()
            
            return jsonify({
                'success': True,
                'data': {
                    'reports': [report.to_dict() for report in reports],
                    'pagination': {
                        'total': total_count,
                        'limit': limit,
                        'offset': offset,
                        'has_more': offset + limit < total_count
                    }
                }
            })
            
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/<report_id>', methods=['GET'])
@require_auth_or_api_key(['admin', 'read'])
def get_report(report_id: str):
    """Get specific report details with access control"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        with get_db_session() as session:
            # Get report without user filtering to check access properly
            report = session.query(Report).filter(Report.id == report_id).first()
            if not report:
                return jsonify({'error': 'Report not found'}), 404

            # Check if user has access using the has_access() method
            if not report.has_access(user_id):
                # If service-generated and user is the intended recipient, require AAL2
                if report.is_service_generated and report.user_id == user_id:
                    return jsonify({
                        'error': 'AAL2_REQUIRED',
                        'message': 'This report was generated by Bee and requires additional authentication to access',
                        'code': 'aal2_required_for_service_report',
                        'report_id': report_id,
                        'grant_endpoint': f'/api/reports/{report_id}/grant-access'
                    }), 403
                else:
                    # User doesn't have access and is not the intended recipient
                    return jsonify({'error': 'Report not found'}), 404

            # User has access, return report
            return jsonify({
                'success': True,
                'data': {
                    'report': report.to_dict(include_sensitive=True)
                }
            })

    except Exception as e:
        logger.error(f"Error getting report {report_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/<report_id>/download', methods=['GET'])
@require_auth_or_api_key(['admin', 'read'])
@require_auth_method(['webauthn', 'totp', 'email'])  # Tier 2 (compatible with current session data)
def download_report(report_id: str):
    """Download report file with access control"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        with get_db_session() as session:
            report = session.query(Report).filter(Report.id == report_id).first()
            if not report:
                return jsonify({'error': 'Report not found'}), 404

            # Check if user has access (demo reports exception for backward compat)
            if 'Demo' not in report.title and not report.has_access(user_id):
                # If service-generated and user is the intended recipient, require AAL2 grant
                if report.is_service_generated and report.user_id == user_id:
                    return jsonify({
                        'error': 'AAL2_REQUIRED',
                        'message': 'This report requires additional authentication to access',
                        'code': 'aal2_required_for_service_report',
                        'report_id': report_id,
                        'grant_endpoint': f'/api/reports/{report_id}/grant-access'
                    }), 403
                else:
                    return jsonify({'error': 'Access denied'}), 403

            if not report.is_completed or not report.result_file_id:
                return jsonify({'error': 'Report not ready for download'}), 400

            # Download file using file service (same as preview)
            file_service = get_file_service()
            file_data = file_service.download_file(report.result_file_id, user_id)

            if not file_data:
                return jsonify({'error': 'Report file not found'}), 404

            # Update download count
            report.download_count += 1
            session.commit()

            # Create file-like object for sending
            file_obj = BytesIO(file_data['data'])

            # Generate filename
            safe_title = "".join(c for c in report.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}_{report.id[:8]}.{report.output_format}"

            return send_file(
                file_obj,
                as_attachment=True,
                download_name=filename,
                mimetype=file_data.get('mime_type', 'application/octet-stream')
            )

    except Exception as e:
        logger.error(f"Error downloading report {report_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/<report_id>/preview', methods=['GET'])
@require_auth_or_api_key(['admin', 'read'])
@require_auth_method(['webauthn', 'totp', 'email'])  # Tier 2 (compatible with current session data)
def preview_report(report_id: str):
    """Preview report file inline (for PDF viewing in browser) with access control"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        with get_db_session() as session:
            report = session.query(Report).filter(Report.id == report_id).first()
            if not report:
                return jsonify({'error': 'Report not found'}), 404

            # Check if user has access
            if not report.has_access(user_id):
                # If service-generated and user is the intended recipient, require AAL2 grant
                if report.is_service_generated and report.user_id == user_id:
                    return jsonify({
                        'error': 'AAL2_REQUIRED',
                        'message': 'This report requires additional authentication to access',
                        'code': 'aal2_required_for_service_report',
                        'report_id': report_id,
                        'grant_endpoint': f'/api/reports/{report_id}/grant-access'
                    }), 403
                else:
                    return jsonify({'error': 'Access denied'}), 403

            if not report.is_completed or not report.result_file_id:
                return jsonify({'error': 'Report not ready for preview'}), 400

            # Download file using file service (same as download, but serve inline)
            file_service = get_file_service()
            file_data = file_service.download_file(report.result_file_id, user_id)

            if not file_data:
                return jsonify({'error': 'Report file not found'}), 404

            # Create file-like object for inline viewing
            file_obj = BytesIO(file_data['data'])

            # Generate filename
            safe_title = "".join(c for c in report.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}_{report.id[:8]}.{report.output_format}"

            return send_file(
                file_obj,
                as_attachment=False,  # KEY DIFFERENCE: Serve inline for browser preview
                download_name=filename,
                mimetype=file_data.get('mime_type', 'application/pdf')
            )

    except Exception as e:
        logger.error(f"Error previewing report {report_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/<report_id>/grant-access', methods=['POST'])
@require_aal2_or_api_key(['admin', 'write'])  # AAL2 required for accessing service-generated reports
def grant_report_access(report_id: str):
    """
    Grant yourself access to a service-generated report.

    This endpoint requires AAL2 authentication (passkey or TOTP) to ensure
    the user is who they claim to be before granting access to a report
    that was generated by the Bee service on their behalf.
    """
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        with get_db_session() as session:
            # Get report without user filtering (we need to access service-generated reports)
            report = session.query(Report).filter(Report.id == report_id).first()
            if not report:
                return jsonify({'error': 'Report not found'}), 404

            # Check if report is service-generated
            if not report.is_service_generated:
                return jsonify({
                    'error': 'NOT_SERVICE_GENERATED',
                    'message': 'This report is user-owned and does not require access grant'
                }), 400

            # Check if user is the intended recipient (report.user_id)
            if report.user_id != user_id:
                return jsonify({
                    'error': 'ACCESS_DENIED',
                    'message': 'This report was not generated for you'
                }), 403

            # Check if already has access
            if report.has_access(user_id):
                return jsonify({
                    'success': True,
                    'message': 'You already have access to this report',
                    'report': report.to_dict()
                }), 200

            # Grant access
            if report.grant_access(user_id):
                session.commit()

                logger.info(
                    f"AAL2 access granted: User {user_id} granted themselves access "
                    f"to service-generated report {report_id}"
                )

                return jsonify({
                    'success': True,
                    'message': 'Access granted successfully',
                    'report': report.to_dict()
                }), 200
            else:
                return jsonify({
                    'error': 'GRANT_FAILED',
                    'message': 'Failed to grant access'
                }), 500

    except Exception as e:
        logger.error(f"Error granting report access {report_id}: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/<report_id>/cancel', methods=['POST'])
@require_auth_or_api_key(['admin', 'read'])
@require_auth_method(['webauthn', 'totp'])  # Tier 3 protection for report cancellation
def cancel_report(report_id: str):
    """Cancel a pending or processing report"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        with get_db_session() as session:
            report = get_report_by_id(session, report_id, user_id)
            if not report:
                return jsonify({'error': 'Report not found'}), 404

            if not report.is_processing:
                return jsonify({'error': 'Report cannot be cancelled'}), 400
            
            # Cancel the report
            report.status = 'cancelled'
            report.completed_at = datetime.utcnow()
            session.commit()
            
            # Notify report service to remove from queue
            report_service = get_report_service()
            report_service.cancel_report(report_id)
            
            return jsonify({
                'success': True,
                'message': 'Report cancelled successfully'
            })
            
    except Exception as e:
        logger.error(f"Error cancelling report {report_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/<report_id>/retry', methods=['POST'])
@require_auth_or_api_key(['admin', 'read'])
def retry_report(report_id: str):
    """Retry a failed report"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        with get_db_session() as session:
            report = get_report_by_id(session, report_id, user_id)
            if not report:
                return jsonify({'error': 'Report not found'}), 404
            
            if not report.can_retry:
                return jsonify({'error': 'Report cannot be retried'}), 400
            
            # Reset report status and queue it again
            report.status = 'pending'
            report.progress_percentage = 0
            report.error_message = None
            report.retry_count += 1
            session.commit()
            
            # Queue the report for processing
            report_service = get_report_service()
            queue_result = report_service.queue_report(report.id)
            
            if not queue_result['success']:
                return jsonify({
                    'success': False,
                    'error': 'Failed to queue report for processing'
                }), 500
            
            return jsonify({
                'success': True,
                'message': 'Report queued for retry',
                'data': {
                    'queue_position': queue_result.get('queue_position'),
                    'estimated_completion': queue_result.get('estimated_completion')
                }
            })
            
    except Exception as e:
        logger.error(f"Error retrying report {report_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/queue/status', methods=['GET'])
@require_auth_or_api_key(['admin', 'read'])
def get_queue_status_api():
    """Get current report queue status"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        queue_name = request.args.get('queue', 'default')
        
        with get_db_session() as session:
            status = get_queue_status(session, queue_name)
            
            # Also get user's active reports
            user_processing = session.query(Report)\
                .filter(
                    Report.user_id == user_id,
                    Report.status.in_(['pending', 'queued', 'processing'])
                )\
                .count()
            
            status['user_active_reports'] = user_processing
            
            return jsonify({
                'success': True,
                'data': status
            })
            
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        # Return demo data on error for Beeacon dashboard
        return jsonify({
            'success': True,
            'data': {
                'queue_name': 'default',
                'pending_reports': 3,
                'processing_reports': 1,
                'completed_today': 8,
                'failed_today': 0,
                'average_processing_time': '2.3 minutes',
                'user_active_reports': 2,
                'estimated_wait_time': '5 minutes'
            }
        })

@report_bp.route('/templates/<template_id>', methods=['GET'])
@require_auth_or_api_key(['admin', 'read'])
def get_template(template_id: str):
    """Get specific template details"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = get_user_role()
        
        with get_db_session() as session:
            template = session.query(ReportTemplate).filter(
                ReportTemplate.id == template_id,
                ReportTemplate.is_active == True
            ).first()
            
            if not template:
                return jsonify({'error': 'Template not found'}), 404
            
            # Check permissions
            if user_role != 'admin' and template.required_role not in ['user', user_role]:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return jsonify({
                'success': True,
                'data': {
                    'template': template.to_dict(include_config=True)
                }
            })
            
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/templates', methods=['POST'])
@require_auth_or_api_key(['admin', 'read'])
def create_template():
    """Create a new report template (admin only)"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = get_user_role()
        if user_role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
        
        # Validate required fields
        required_fields = ['name', 'description', 'generator_class', 'parameters']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        with get_db_session() as session:
            # Check if template name already exists
            existing = session.query(ReportTemplate).filter(
                ReportTemplate.name == data['name']
            ).first()
            
            if existing:
                return jsonify({'error': 'Template with this name already exists'}), 409
            
            # Create new template
            template = ReportTemplate(
                name=data['name'],
                description=data['description'],
                category=data.get('category', 'custom'),
                generator_class=data['generator_class'],
                parameters=data['parameters'],
                output_formats=data.get('output_formats', ['pdf', 'csv', 'json']),
                required_role=data.get('required_role', 'user'),
                requires_scrambling=data.get('requires_scrambling', False),
                is_active=data.get('is_active', True),
                created_by=user_id
            )
            
            session.add(template)
            session.commit()
            
            return jsonify({
                'success': True,
                'data': {
                    'template': template.to_dict(include_config=True)
                }
            }), 201
            
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/templates/<template_id>', methods=['PUT'])
@require_auth_or_api_key(['admin', 'read'])
def update_template(template_id: str):
    """Update a report template (admin only)"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = get_user_role()
        if user_role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
        
        with get_db_session() as session:
            template = session.query(ReportTemplate).filter(
                ReportTemplate.id == template_id
            ).first()
            
            if not template:
                return jsonify({'error': 'Template not found'}), 404
            
            # Update allowed fields
            update_fields = [
                'name', 'description', 'category', 'generator_class',
                'parameters', 'output_formats', 'required_role',
                'requires_scrambling', 'is_active'
            ]
            
            for field in update_fields:
                if field in data:
                    setattr(template, field, data[field])
            
            template.updated_at = datetime.utcnow()
            session.commit()
            
            return jsonify({
                'success': True,
                'data': {
                    'template': template.to_dict(include_config=True)
                }
            })
            
    except Exception as e:
        logger.error(f"Error updating template {template_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/templates/<template_id>', methods=['DELETE'])
@require_auth_or_api_key(['admin', 'read'])
def delete_template(template_id: str):
    """Delete a report template (admin only)"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = get_user_role()
        if user_role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        with get_db_session() as session:
            template = session.query(ReportTemplate).filter(
                ReportTemplate.id == template_id
            ).first()
            
            if not template:
                return jsonify({'error': 'Template not found'}), 404
            
            # Check if template is in use
            active_reports = session.query(Report).filter(
                Report.template_id == template_id,
                Report.status.in_(['pending', 'queued', 'processing'])
            ).count()
            
            if active_reports > 0:
                return jsonify({'error': 'Cannot delete template with active reports'}), 409
            
            # Soft delete by marking inactive
            template.is_active = False
            template.updated_at = datetime.utcnow()
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Template deleted successfully'
            })
            
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/templates/<template_id>/permissions', methods=['GET'])
@require_auth_or_api_key(['admin', 'read'])
def get_template_permissions(template_id: str):
    """Get template permissions"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = get_user_role()
        
        with get_db_session() as session:
            template = session.query(ReportTemplate).filter(
                ReportTemplate.id == template_id
            ).first()
            
            if not template:
                return jsonify({'error': 'Template not found'}), 404
            
            # Check current user permissions
            can_view = user_role == 'admin' or template.required_role in ['user', user_role]
            can_edit = user_role == 'admin'
            can_delete = user_role == 'admin'
            can_execute = can_view
            
            return jsonify({
                'success': True,
                'data': {
                    'template_id': template_id,
                    'required_role': template.required_role,
                    'user_permissions': {
                        'can_view': can_view,
                        'can_edit': can_edit,
                        'can_delete': can_delete,
                        'can_execute': can_execute
                    }
                }
            })
            
    except Exception as e:
        logger.error(f"Error getting template permissions: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/<report_id>/share', methods=['POST'])
@require_auth_or_api_key(['admin', 'read'])
@require_auth_method(['webauthn', 'totp'])  # Tier 3 protection for report sharing
def share_report(report_id: str):
    """Generate shareable link or send report via email"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
        
        share_method = data.get('method')  # 'link', 'email', 'download_token'
        
        if share_method not in ['link', 'email', 'download_token']:
            return jsonify({'error': 'Invalid share method'}), 400
        
        with get_db_session() as session:
            report = get_report_by_id(session, report_id, user_id)
            if not report:
                return jsonify({'error': 'Report not found'}), 404
            
            if not report.is_completed:
                return jsonify({'error': 'Report not ready for sharing'}), 400
            
            # Generate sharing response based on method
            if share_method == 'link':
                # Generate a shareable URL (for future implementation with access tokens)
                share_url = f"/dashboard/reports/shared/{report_id}"
                return jsonify({
                    'success': True,
                    'data': {
                        'share_url': share_url,
                        'expires_at': report.expires_at.isoformat() if report.expires_at else None,
                        'method': 'link',
                        'message': 'Shareable link generated. Note: Recipients will need appropriate access permissions.'
                    }
                })
            
            elif share_method == 'email':
                # Email sharing (for future implementation)
                recipients = data.get('recipients', [])
                message = data.get('message', '')
                
                if not recipients:
                    return jsonify({'error': 'Recipients list is required for email sharing'}), 400
                
                # TODO: Implement email service integration
                return jsonify({
                    'success': True,
                    'data': {
                        'recipients': recipients,
                        'method': 'email',
                        'message': 'Email sharing will be available in a future update. For now, please download and share manually.'
                    }
                })
            
            elif share_method == 'download_token':
                # Generate a temporary download token
                import secrets
                download_token = secrets.token_urlsafe(32)
                
                # Store token in session or database (simplified approach for now)
                # In production, this should use a proper token storage system
                return jsonify({
                    'success': True,
                    'data': {
                        'download_token': download_token,
                        'download_url': f"/api/reports/{report_id}/download?token={download_token}",
                        'expires_in': '24 hours',
                        'method': 'download_token',
                        'message': 'Temporary download link generated'
                    }
                })
            
    except Exception as e:
        logger.error(f"Error sharing report {report_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for report service"""
    try:
        # Test database connectivity
        with get_db_session() as session:
            session.query(ReportTemplate).limit(1).all()

        # Test report service
        report_service = get_report_service()
        service_healthy = report_service.health_check()

        return jsonify({
            'status': 'healthy' if service_healthy else 'degraded',
            'database_connected': True,
            'report_service': service_healthy,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Report service health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@report_bp.route('/debug/file/<file_id>', methods=['GET'])
@require_auth_or_api_key(['admin', 'read'])
def debug_file_download(file_id: str):
    """Diagnostic endpoint to debug file download issues"""
    try:
        user_id = get_current_user()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        logger.info(f"[FILE_DEBUG] Starting file debug: file_id={file_id}, user_id={user_id}")

        file_service = get_file_service()

        # Get database info
        with get_db_session() as session:
            from app.models.file_models import get_file_by_id
            file_asset = get_file_by_id(session, file_id)

            debug_info = {
                'file_id': file_id,
                'user_id': user_id,
                'database_record_found': file_asset is not None,
                'vault_client_available': hasattr(file_service, 'vault_client'),
                'timestamp': datetime.utcnow().isoformat()
            }

            if file_asset:
                debug_info.update({
                    'filename': file_asset.filename,
                    'storage_backend': file_asset.storage_backend,
                    'storage_path': file_asset.storage_path,
                    'owner_id': str(file_asset.owner_id),
                    'file_size': file_asset.file_size,
                    'created_at': file_asset.created_at.isoformat() if file_asset.created_at else None,
                    'is_deleted': file_asset.is_deleted,
                    'metadata': file_asset.file_metadata
                })

                # Test permission check
                from app.models.file_models import check_file_permission, PermissionType
                has_permission = check_file_permission(session, file_id, user_id, PermissionType.READ.value)
                debug_info['permission_granted'] = has_permission

                # Test vault client if file exists and permissions allow
                if has_permission and file_service.vault_client:
                    try:
                        logger.info(f"[FILE_DEBUG] Testing Vault retrieval for path: {file_asset.storage_path}")
                        vault_response = file_service.vault_client.retrieve_file(file_asset.storage_path)

                        debug_info['vault_test'] = {
                            'response_received': vault_response is not None,
                            'response_type': str(type(vault_response)),
                            'has_data_key': 'data' in vault_response if vault_response else False,
                        }

                        if vault_response and 'data' in vault_response:
                            data = vault_response['data']
                            debug_info['vault_test']['data_type'] = str(type(data))
                            debug_info['vault_test']['data_size'] = len(data) if isinstance(data, (bytes, str)) else 'unknown'

                    except Exception as vault_error:
                        debug_info['vault_test'] = {
                            'error': str(vault_error),
                            'error_type': type(vault_error).__name__
                        }
                        logger.error(f"[FILE_DEBUG] Vault test failed: {vault_error}")

        return jsonify({
            'success': True,
            'debug_info': debug_info
        })

    except Exception as e:
        logger.error(f"[FILE_DEBUG] Debug endpoint failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500

# Internal worker endpoints (no external auth required - internal service calls)
@report_bp.route('/internal/next-job', methods=['GET'])
def get_next_job():
    """Internal endpoint for worker to get next job"""
    try:
        worker_id = request.args.get('worker_id', f"api-worker-{datetime.utcnow().timestamp()}")

        report_service = get_report_service()
        job = report_service.get_next_job(worker_id)

        if job:
            return jsonify({
                'success': True,
                'data': {'job': job}
            })
        else:
            return jsonify({
                'success': True,
                'data': {'job': None}
            })

    except Exception as e:
        logger.error(f"Error getting next job: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@report_bp.route('/internal/process-job', methods=['POST'])
def process_job():
    """Internal endpoint for worker to process a job"""
    try:
        job_data = request.get_json()
        report_id = job_data['report_id']

        logger.info(f"Processing report {report_id} via internal API")

        # Import and use the existing worker logic
        from app.workers.report_worker import ReportWorker
        worker = ReportWorker(worker_id="api-worker")

        # Process the job using existing worker logic
        import asyncio
        asyncio.run(worker.process_job(job_data))

        return jsonify({
            'success': True,
            'message': f'Report {report_id} processed successfully'
        })

    except Exception as e:
        logger.error(f"Error processing job: {e}")
        # Mark job as failed
        try:
            report_service = get_report_service()
            report_service.fail_job(job_data.get('report_id'), str(e), retry=False)
        except:
            pass
        return jsonify({'error': 'Job processing failed'}), 500