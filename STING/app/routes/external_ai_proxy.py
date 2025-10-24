"""
External AI service proxy routes
Forwards requests to the external-ai service container
"""

from flask import Blueprint, request, jsonify, g
import requests
import logging
import os
from app.utils.decorators import require_auth_or_api_key

external_ai_proxy_bp = Blueprint('external_ai_proxy', __name__)
logger = logging.getLogger(__name__)

# External AI service URL
EXTERNAL_AI_SERVICE_URL = os.getenv('EXTERNAL_AI_SERVICE_URL', 'http://external-ai:8091')

@external_ai_proxy_bp.route('/api/external-ai/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@require_auth_or_api_key(['admin', 'write', 'read'])
def proxy_external_ai(path):
    """
    Proxy all requests to the external AI service
    """
    try:
        # Build the target URL
        target_url = f"{EXTERNAL_AI_SERVICE_URL}/{path}"
        
        # Get request headers and remove hop-by-hop headers
        headers = {key: value for key, value in request.headers if key.lower() not in [
            'host', 'connection', 'keep-alive', 'proxy-authenticate', 
            'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade'
        ]}
        
        # Add authentication if available
        if hasattr(g, 'session_token'):
            headers['Authorization'] = f'Bearer {g.session_token}'
        elif hasattr(g, 'user') and g.user:
            headers['X-User-Id'] = str(g.user.id)
            headers['X-User-Email'] = g.user.email
            headers['X-User-Role'] = g.user.role
        
        # Forward the request
        logger.debug(f"Proxying {request.method} request to {target_url}")
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            allow_redirects=False,
            timeout=90  # Increased for AI inference (models can take 30-60s)
        )
        
        # Create response with same status code and headers
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = {k: v for k, v in response.headers.items() if k.lower() not in excluded_headers}
        
        return response.content, response.status_code, headers
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout proxying request to external AI service: {path}")
        return jsonify({'error': 'External AI service timeout'}), 504
        
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error proxying to external AI service: {path}")
        return jsonify({'error': 'External AI service unavailable'}), 503
        
    except Exception as e:
        logger.error(f"Error proxying to external AI service: {e}")
        return jsonify({'error': 'Internal proxy error'}), 500