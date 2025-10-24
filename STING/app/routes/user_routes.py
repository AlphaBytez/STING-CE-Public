"""
User management API routes
Handles user administration, role management, and SSO preparation
"""

import logging
import os
import json
from datetime import datetime
from flask import Blueprint, jsonify, request, g
from functools import wraps
from app.services.user_service import UserService
from app.services.kratos_service import kratos_admin
from app.models.user_models import User
from app.extensions import db
from app.utils.decorators import require_auth_method

logger = logging.getLogger(__name__)

# Create blueprint
user_bp = Blueprint('user', __name__, url_prefix='/api/users')

def require_admin(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # TODO: Implement proper authentication check
        # For now, we'll check if user exists in g.user (set by auth middleware)
        
        if not hasattr(g, 'user') or not g.user:
            return jsonify({'error': 'Authentication required'}), 401
        
        if not g.user.is_admin and not g.user.is_super_admin:
            return jsonify({'error': 'Admin privileges required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_super_admin(f):
    """Decorator to require super admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            return jsonify({'error': 'Authentication required'}), 401
        
        if not g.user.is_super_admin:
            return jsonify({'error': 'Super admin privileges required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

@user_bp.route('/stats', methods=['GET'])
@require_admin
def get_user_stats():
    """Get user statistics"""
    try:
        stats = UserService.get_user_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return jsonify({'error': 'Failed to get user statistics'}), 500

@user_bp.route('/admins', methods=['GET'])
@require_admin
def get_admin_users():
    """Get all admin users"""
    try:
        admins = UserService.get_admin_users()
        return jsonify({
            'admins': [admin.to_dict() for admin in admins]
        }), 200
    except Exception as e:
        logger.error(f"Error getting admin users: {e}")
        return jsonify({'error': 'Failed to get admin users'}), 500

@user_bp.route('/<int:user_id>/promote', methods=['POST'])
@require_super_admin
def promote_user(user_id):
    """Promote a user to admin"""
    try:
        data = request.get_json() or {}
        role = data.get('role', 'admin')  # 'admin' or 'super_admin'
        
        if role not in ['admin', 'super_admin']:
            return jsonify({'error': 'Invalid role. Must be admin or super_admin'}), 400
        
        success = UserService.promote_user_to_admin(user_id, g.user.id)
        
        if success:
            return jsonify({
                'message': f'User promoted to {role} successfully',
                'user_id': user_id
            }), 200
        else:
            return jsonify({'error': 'Failed to promote user'}), 400
            
    except Exception as e:
        logger.error(f"Error promoting user {user_id}: {e}")
        return jsonify({'error': 'Failed to promote user'}), 500

@user_bp.route('/create-admin', methods=['POST'])
@require_super_admin
def create_admin_user():
    """Create a new admin user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        email = data.get('email')
        password = data.get('password')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        is_super_admin = data.get('is_super_admin', False)
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        result = UserService.create_admin_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_super_admin=is_super_admin
        )
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
        return jsonify({'error': 'Failed to create admin user'}), 500

# Removed duplicate /me endpoint - using /api/auth/me from auth_routes.py instead

@user_bp.route('/profile', methods=['GET'])
def get_current_user_profile():
    """Get current user's profile from Kratos"""
    try:
        if not hasattr(g, 'user') or not g.user:
            # In development, return mock data if no user is authenticated
            if os.getenv('APP_ENV') == 'development':
                return jsonify({
                    'id': 'dev-user',
                    'email': 'dev@example.com',
                    'firstName': 'Dev',
                    'lastName': 'User',
                    'displayName': 'Development User',
                    'bio': '',
                    'location': '',
                    'website': '',
                    'organization': '',
                    'profilePicture': '',
                    'role': 'user',
                    'effective_role': 'user',
                    'kratos_synced': False
                }), 200
            return jsonify({'error': 'Authentication required'}), 401
        
        user = g.user
        profile_data = user.to_dict()
        
        # Try to get the latest data from Kratos
        if user.kratos_id:
            kratos_identity = kratos_admin.get_identity(user.kratos_id)
            if kratos_identity and 'traits' in kratos_identity:
                traits = kratos_identity['traits']
                
                # Update profile data with Kratos traits
                if 'name' in traits:
                    profile_data['firstName'] = traits['name'].get('first', '')
                    profile_data['lastName'] = traits['name'].get('last', '')
                
                if 'profile' in traits:
                    profile = traits['profile']
                    profile_data['displayName'] = profile.get('displayName', '')
                    profile_data['bio'] = profile.get('bio', '')
                    profile_data['location'] = profile.get('location', '')
                    profile_data['website'] = profile.get('website', '')
                    profile_data['organization'] = profile.get('organization', '')
                    profile_data['profilePicture'] = profile.get('profilePicture', '')
                
                profile_data['email'] = traits.get('email', user.email)
                profile_data['kratos_synced'] = True
        
        return jsonify(profile_data), 200
        
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify({'error': 'Failed to get user profile'}), 500

@user_bp.route('/profile', methods=['PUT'])
@require_auth_method(['webauthn', 'totp', 'email'])
def update_user_profile():
    """Update current user's profile - syncs with Kratos"""
    try:
        if not hasattr(g, 'user') or not g.user:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        user = g.user
        
        # First, update in Kratos
        kratos_success = False
        if user.kratos_id:
            # Update Kratos identity traits
            kratos_success = kratos_admin.update_identity_traits(
                user.kratos_id,
                data  # Pass the raw data, the service will handle field mapping
            )
            
            if not kratos_success:
                logger.warning(f"Failed to update Kratos identity for user {user.id}")
        
        # Then update local database for backwards compatibility
        # This can be removed once we fully migrate to Kratos
        if 'firstName' in data:
            user.first_name = data['firstName']
        if 'lastName' in data:
            user.last_name = data['lastName']
        if 'displayName' in data:
            user.display_name = data['displayName']
        if 'bio' in data:
            user.bio = data['bio']
        if 'location' in data:
            user.location = data['location']
        if 'website' in data:
            user.website = data['website']
        if 'organization' in data:
            user.organization = data['organization']
        if 'profilePicture' in data:
            # Note: You might want to handle profile picture uploads differently
            # For now, we'll store the base64 data URL if it's small enough
            if len(data['profilePicture']) < 1048576:  # 1MB limit
                user.profile_picture = data['profilePicture']
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Return the updated user data
        result = user.to_dict()
        result['kratos_sync_success'] = kratos_success
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update user profile'}), 500

@user_bp.route('/first-admin-status', methods=['GET'])
def get_first_admin_status():
    """Check if first admin has been created (public endpoint for setup)"""
    try:
        is_created = UserService.is_first_admin_created()
        stats = UserService.get_user_stats()
        
        return jsonify({
            'first_admin_created': is_created,
            'total_users': stats['total_users'],
            'admin_users': stats['admin_users'],
            'needs_setup': stats['total_users'] == 0 or stats['admin_users'] == 0
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking first admin status: {e}")
        return jsonify({'error': 'Failed to check admin status'}), 500

@user_bp.route('/sso-readiness', methods=['GET'])
@require_super_admin
def get_sso_readiness():
    """Get SSO migration readiness assessment"""
    try:
        readiness = UserService.prepare_for_sso_migration()
        return jsonify(readiness), 200
        
    except Exception as e:
        logger.error(f"Error getting SSO readiness: {e}")
        return jsonify({'error': 'Failed to assess SSO readiness'}), 500

@user_bp.route('/', methods=['GET'])
@require_admin
def list_users():
    """List all users (admin only)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        
        query = User.query
        
        if search:
            query = query.filter(
                User.email.contains(search) |
                User.first_name.contains(search) |
                User.last_name.contains(search) |
                User.display_name.contains(search)
            )
        
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'users': [user.to_dict() for user in pagination.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev,
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify({'error': 'Failed to list users'}), 500

@user_bp.route('/settings', methods=['GET'])
def get_user_settings():
    """Get user settings from database"""
    try:
        user = g.user
        if not user:
            return jsonify({'error': 'Not authenticated'}), 401
        
        # Get user settings from database
        from app.models.user_settings import UserSettings
        
        # Use kratos_id for lookup
        user_id = user.kratos_id if hasattr(user, 'kratos_id') else str(user.id)
        settings = UserSettings.query.filter_by(user_id=user_id).first()
        
        if settings:
            return jsonify({
                'user_id': settings.user_id,
                'email': settings.email,
                'role': settings.role,
                'force_password_change': settings.force_password_change,
                'password_changed_at': settings.password_changed_at.isoformat() if settings.password_changed_at else None,
                'created_at': settings.created_at.isoformat() if settings.created_at else None,
                'updated_at': settings.updated_at.isoformat() if settings.updated_at else None
            })
        else:
            # Return default settings if none exist
            return jsonify({
                'user_id': user_id,
                'email': user.email,
                'role': 'user',
                'force_password_change': False,
                'password_changed_at': None,
                'created_at': None,
                'updated_at': None
            })
            
    except Exception as e:
        logger.error(f"Error getting user settings: {str(e)}")
        return jsonify({'error': 'Failed to get user settings'}), 500

@user_bp.route('/system-jar-config', methods=['GET'])
def get_system_jar_config():
    """Get STING CE system jar configuration for BeeChat defaults"""
    try:
        # Try to read the jar system configuration file
        # Use /app/conf which is mounted from ~/.sting-ce/conf on host
        jar_config_path = "/app/conf/jar_system.json"
        
        if not os.path.exists(jar_config_path):
            logger.warning(f"Jar system config not found at {jar_config_path}")
            return jsonify({
                'system_jar_id': None,
                'message': 'System jar not configured. Please run setup script.'
            }), 404
        
        with open(jar_config_path, 'r') as f:
            jar_config = json.load(f)
        
        return jsonify({
            'system_jar_id': jar_config.get('system_jar_id'),
            'organization_jar_id': jar_config.get('organization_jar_id'),
            'workspace_jar_id': jar_config.get('workspace_jar_id'),
            'description': jar_config.get('description', 'STING CE 3-jar system'),
            'created_at': jar_config.get('created_at')
        })
        
    except Exception as e:
        logger.error(f"Error reading jar system config: {str(e)}")
        return jsonify({'error': 'Failed to get jar system configuration'}), 500

@user_bp.route('/beechat-preferences', methods=['GET'])
def get_beechat_preferences():
    """Get user's BeeChat preferences including default honey jar"""
    try:
        # For future enhancement: get user from auth middleware
        # For now, return system defaults for CE edition
        # Use /app/conf which is mounted from ~/.sting-ce/conf on host
        jar_config_path = "/app/conf/jar_system.json"
        default_jar_id = None
        
        if os.path.exists(jar_config_path):
            with open(jar_config_path, 'r') as f:
                jar_config = json.load(f)
                default_jar_id = jar_config.get('system_jar_id')
        
        return jsonify({
            'default_honey_jar_id': default_jar_id,
            'auto_load_system_jar': True,  # Always true for CE edition
            'show_welcome_message': True,
            'edition': 'ce'
        })
        
    except Exception as e:
        logger.error(f"Error getting BeeChat preferences: {str(e)}")
        return jsonify({'error': 'Failed to get BeeChat preferences'}), 500

@user_bp.route('/beechat-preferences', methods=['POST'])
def update_beechat_preferences():
    """Update user's BeeChat preferences (limited in CE edition)"""
    try:
        data = request.get_json()
        
        # In CE edition, only allow toggling welcome message
        # Default jar is always system jar
        show_welcome = data.get('show_welcome_message', True)
        
        # For future: store in user preferences table
        # For now, just return success for CE constraints
        
        return jsonify({
            'success': True,
            'message': 'Preferences updated',
            'constraints': {
                'ce_edition': True,
                'default_jar_locked': 'System jar is always default in CE edition',
                'customizable': ['show_welcome_message']
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating BeeChat preferences: {str(e)}")
        return jsonify({'error': 'Failed to update BeeChat preferences'}), 500

# Error handlers
@user_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'User not found'}), 404

@user_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405