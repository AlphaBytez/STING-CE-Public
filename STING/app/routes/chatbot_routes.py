"""
Chatbot (Bee) routes for STING application
Proxy requests to the chatbot service
"""

from flask import Blueprint, request, jsonify, g
from app.utils.decorators import require_auth_or_api_key
from app.utils.complexity_detector import get_complexity_detector, QueryComplexity
from app.services.report_service import get_report_service
from app.utils.flexible_auth import get_current_user, get_user_role
from datetime import datetime
import requests
import logging
import os
import json

chatbot_bp = Blueprint('chatbot', __name__)
logger = logging.getLogger(__name__)

# Chatbot service URL
CHATBOT_SERVICE_URL = os.getenv('CHATBOT_SERVICE_URL', 'http://chatbot:8888')
EXTERNAL_AI_SERVICE_URL = os.getenv('EXTERNAL_AI_SERVICE_URL', 'http://external-ai:8091')

@chatbot_bp.route('/api/bee/chat', methods=['POST'])
@require_auth_or_api_key(['admin', 'write', 'read'])
def chat_with_bee():
    """
    Chat endpoint for Bee assistant
    Requires authentication (session or API key)
    """
    try:

        # Get request data
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400

        message = data.get('message')
        conversation_id = data.get('conversation_id')
        context = data.get('context', {})

        # Generate conversation_id if not provided (for conversation history caching)
        if not conversation_id:
            import uuid
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
            logger.info(f"Generated new conversation_id: {conversation_id}")

        # Add user information to context (handle both session and API key auth)
        if hasattr(g, 'api_key') and g.api_key:
            # API key authentication
            logger.info(f"🔑 API Key Debug: Using API key {g.api_key.name} with user_id: {g.api_key.user_id}")
            context['user_id'] = str(g.api_key.user_id)
            context['user_email'] = str(g.api_key.user_email)
            context['user_role'] = 'admin' if 'admin' in g.api_key.scopes else 'user'
            context['auth_type'] = 'api_key'
        elif hasattr(g, 'user') and g.user:
            # Session authentication
            context['user_id'] = str(g.user.id)
            context['user_email'] = g.user.email
            context['user_role'] = str(g.user.role)
            context['auth_type'] = 'session'

            # Check if user has completed security setup (TOTP or passkey)
            # This is not required but helps provide better error messages
            try:
                from app.decorators.aal2 import aal2_manager
                enrollment_status = aal2_manager.check_passkey_enrollment(g.user.id)

                if not enrollment_status['enrolled']:
                    # User hasn't set up 2FA - provide helpful message
                    logger.warning(f"User {g.user.email} attempting to use Bee chat without 2FA setup")
                    return jsonify({
                        'error': 'SECURITY_SETUP_INCOMPLETE',
                        'message': '🔐 Please complete your security setup before using Bee chat. Set up TOTP or a passkey in your Security Settings.',
                        'code': 'MISSING_2FA',
                        'help_url': '/dashboard/settings/security',
                        'details': 'For security reasons, Bee chat requires two-factor authentication (TOTP or passkey) to be configured on your account.'
                    }), 403
            except Exception as security_check_error:
                # If security check fails, log but continue (don't block chat if check fails)
                logger.warning(f"Security check failed for {g.user.email}: {security_check_error}")
        else:
            # Fallback for API-only usage
            context['user_id'] = data.get('user_id', 'api_user')
            context['user_email'] = 'api@sting.local'
            context['user_role'] = 'user'
            context['auth_type'] = 'fallback'
        
        # Prepare request for chatbot service
        # If authenticated via API key or session, bypass Bee's auth check
        chat_request = {
            'message': message,
            'conversation_id': conversation_id,
            'context': context,
            'user_id': context['user_id'],
            'require_auth': False  # Auth already validated by Flask decorator
        }

        # Phase 3: Complexity detection and routing
        # Check if query is too complex for interactive chat
        try:
            complexity_detector = get_complexity_detector()
            complexity, metadata = complexity_detector.detect_complexity(
                user_message=message,
                conversation_history=data.get('conversation_history'),
                context=context
            )

            logger.info(
                f"Complexity detection for user {context['user_id']}: "
                f"{metadata['total_tokens']} tokens → {complexity.value}"
            )

            # If query is too large, return error with suggestion
            if complexity == QueryComplexity.TOO_LARGE:
                return jsonify({
                    'error': 'QUERY_TOO_LARGE',
                    'message': f"Your query is too large ({metadata['total_tokens']} tokens). "
                               f"Please break it into smaller queries or reduce the context.",
                    'metadata': metadata,
                    'suggestion': 'Try rephrasing your question more concisely or split it into multiple queries.'
                }), 413

            # If query is complex, route to report generation
            if complexity == QueryComplexity.COMPLEX:
                logger.info(
                    f"Routing complex query to report generation for user {context['user_id']} "
                    f"({metadata['total_tokens']} tokens)"
                )

                report_service = get_report_service()
                report_result = report_service.create_bee_service_report(
                    user_id=context['user_id'],
                    user_message=message,
                    conversation_id=conversation_id,
                    honey_jar_id=data.get('honey_jar_id'),
                    context=context
                )

                if not report_result['success']:
                    return jsonify({
                        'error': 'REPORT_CREATION_FAILED',
                        'message': 'Failed to create report for complex query',
                        'details': report_result.get('error')
                    }), 500

                # Return report creation response
                return jsonify({
                    'response': f"🔍 Your query is quite complex and will be processed as a detailed report.\n\n"
                                f"**Report ID:** {report_result['report_id']}\n"
                                f"**Queue Position:** {report_result.get('queue_position', 'N/A')}\n"
                                f"**Estimated Completion:** {report_result.get('estimated_completion', 'Soon')}\n\n"
                                f"You'll be notified when your report is ready. You can view it in the Reports section.",
                    'conversation_id': conversation_id,
                    'report_generated': True,
                    'report_metadata': {
                        'report_id': report_result['report_id'],
                        'complexity': complexity.value,
                        'token_count': metadata['total_tokens'],
                        'queue_position': report_result.get('queue_position'),
                        'estimated_completion': report_result.get('estimated_completion')
                    },
                    'metadata': metadata,
                    'bee_personality': 'professional_analyst',
                    'timestamp': datetime.now().isoformat()
                }), 200

        except Exception as complexity_error:
            # Log but don't block if complexity detection fails
            logger.warning(f"Complexity detection failed: {complexity_error}, proceeding with interactive chat")

        # Try external AI service first (modern stack)
        try:
            # Determine user identifier for logging
            user_identifier = context.get('user_email', context.get('user_id', 'unknown'))
            logger.info(f"Sending chat request to external AI service for user {user_identifier}")
            
            # Get session token if available
            auth_headers = {}
            if hasattr(g, 'session_token'):
                auth_headers['Authorization'] = f'Bearer {g.session_token}'
            
            response = requests.post(
                f"{EXTERNAL_AI_SERVICE_URL}/bee/chat",
                json=chat_request,
                headers=auth_headers,
                timeout=90  # Increased for AI inference (models can take 30-60s)
            )

            if response.status_code == 200:
                # Parse JSON with lenient mode to handle escape sequences from LLM responses (e.g., <think> tags)
                response_data = json.loads(response.text, strict=False)
                return jsonify(response_data)
            else:
                logger.warning(f"External AI service returned {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"External AI service unavailable: {e}")
        
        # Fallback to direct chatbot service
        try:
            logger.info("Falling back to direct chatbot service")
            
            response = requests.post(
                f"{CHATBOT_SERVICE_URL}/chat",
                json=chat_request,
                timeout=90  # Increased for AI inference (models can take 30-60s)
            )
            
            if response.status_code == 200:
                return jsonify(response.json())
            else:
                logger.error(f"Chatbot service returned {response.status_code}: {response.text}")
                return jsonify({
                    'error': 'Chat service temporarily unavailable',
                    'details': response.text
                }), response.status_code
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Chatbot service error: {e}")
            return jsonify({
                'error': 'CHAT_SERVICE_UNAVAILABLE',
                'message': '🐝 Bee is temporarily unavailable. Our team has been notified.',
                'details': 'The chat service is not responding. Please try again in a few moments.',
                'code': 'SERVICE_UNAVAILABLE',
                'help_text': 'If this persists, check that your LLM backend (Ollama) is running and accessible.'
            }), 503

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)

        # Provide more helpful error messages based on error type
        error_message = 'An unexpected error occurred while processing your message'
        help_text = None

        if 'connection' in str(e).lower():
            error_message = '🐝 Bee is having trouble connecting to the AI service'
            help_text = 'Please ensure your LLM backend (Ollama) is running and accessible.'
        elif 'timeout' in str(e).lower():
            error_message = '🐝 Bee is taking too long to respond'
            help_text = 'The AI service may be overloaded. Please try again in a moment.'
        elif 'authentication' in str(e).lower() or 'auth' in str(e).lower():
            error_message = '🔐 Authentication error'
            help_text = 'Please ensure you have completed your security setup (TOTP or passkey).'

        return jsonify({
            'error': 'CHAT_ERROR',
            'message': error_message,
            'code': 'INTERNAL_ERROR',
            'help_text': help_text,
            'details': str(e) if os.getenv('DEBUG') else None
        }), 500


@chatbot_bp.route('/api/bee/conversations', methods=['GET'])
def get_conversations():
    """
    Get user's conversation history
    """
    try:
        if not hasattr(g, 'user') or not g.user:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Forward request to chatbot service
        response = requests.get(
            f"{CHATBOT_SERVICE_URL}/conversations/{g.user.id}",
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch conversations'}), response.status_code
            
    except Exception as e:
        logger.error(f"Get conversations error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@chatbot_bp.route('/api/bee/health', methods=['GET'])
def chatbot_health():
    """
    Check chatbot service health
    """
    try:
        # Check external AI service
        external_ai_healthy = False
        try:
            response = requests.get(f"{EXTERNAL_AI_SERVICE_URL}/health", timeout=5)
            external_ai_healthy = response.status_code == 200
        except:
            pass
        
        # Check direct chatbot service
        chatbot_healthy = False
        try:
            response = requests.get(f"{CHATBOT_SERVICE_URL}/health", timeout=5)
            chatbot_healthy = response.status_code == 200
        except:
            pass
        
        return jsonify({
            'status': 'healthy' if (external_ai_healthy or chatbot_healthy) else 'unhealthy',
            'services': {
                'external_ai': external_ai_healthy,
                'chatbot': chatbot_healthy
            }
        })
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500