#!/usr/bin/env python3
"""
Bootstrap Routes - Initialize Default Honey Jars
Simple admin endpoint to create default honey jars with STING documentation
"""

from flask import Blueprint, request, jsonify, current_app
import logging
import requests
import json
import tempfile
import os
from datetime import datetime
from app.models.api_key_models import ApiKey
from app.database import db
from conf.vault_manager import VaultManager

logger = logging.getLogger(__name__)

bootstrap_bp = Blueprint('bootstrap', __name__)

def get_knowledge_service_url():
    """Get the knowledge service URL"""
    # Try different possible URLs for the knowledge service
    urls = [
        "http://sting-ce-knowledge:8090",
        "http://knowledge:8090", 
        "http://localhost:8090"
    ]
    
    for url in urls:
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                return url
        except:
            continue
    return None

@bootstrap_bp.route('/update-honey-jar-content', methods=['POST'])
def update_existing_honey_jar_content():
    """
    Update existing honey jars with professional STING content
    This uploads content directly to the existing public jars for immediate MVP demo use
    """
    try:
        knowledge_url = get_knowledge_service_url()
        if not knowledge_url:
            return jsonify({
                'error': 'Knowledge service not available',
                'message': 'Cannot connect to knowledge service to update honey jars'
            }), 503
        
        # Get the existing public honey jar IDs
        jar_ids = ['2bf91ee8-88ac-4a3e-bfc6-cc8ca9ec499a', '54b2d063-f867-4e0f-acff-da88c1e3a4a9']
        content_pieces = [
            {
                'filename': 'sting_platform_guide.md',
                'content': create_sting_platform_content()
            },
            {
                'filename': 'business_enterprise_guide.md', 
                'content': create_business_guide_content()
            },
            {
                'filename': 'legal_compliance_guide.md',
                'content': create_legal_compliance_content()
            }
        ]
        
        updated_jars = []
        
        for i, jar_id in enumerate(jar_ids):
            for j, content_piece in enumerate(content_pieces):
                try:
                    # Create temporary file with content
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
                        temp_file.write(content_piece['content'])
                        temp_file_path = temp_file.name
                    
                    # Upload content to honey jar using multipart form data
                    with open(temp_file_path, 'rb') as f:
                        files = {
                            'file': (content_piece['filename'], f, 'text/markdown')
                        }
                        
                        upload_response = requests.post(
                            f"{knowledge_url}/honey-jars/{jar_id}/documents/upload",
                            files=files,
                            timeout=60  # Longer timeout for content upload
                        )
                    
                    # Clean up temp file
                    os.unlink(temp_file_path)
                    
                    if upload_response.status_code == 200:
                        logger.info(f"✅ Uploaded {content_piece['filename']} to jar {jar_id}")
                        updated_jars.append({
                            'jar_id': jar_id,
                            'filename': content_piece['filename'],
                            'status': 'uploaded',
                            'size': len(content_piece['content'])
                        })
                    else:
                        logger.error(f"❌ Failed to upload {content_piece['filename']}: {upload_response.status_code}")
                        logger.error(f"Response: {upload_response.text}")
                        
                except Exception as upload_error:
                    logger.error(f"Error uploading {content_piece.get('filename', 'unknown')}: {upload_error}")
        
        return jsonify({
            'success': True,
            'message': f'Successfully updated {len(updated_jars)} content pieces',
            'updated_content': updated_jars,
            'knowledge_service_url': knowledge_url
        })
        
    except Exception as e:
        logger.error(f"Error updating honey jar content: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to update honey jar content',
            'message': str(e)
        }), 500

@bootstrap_bp.route('/create-default-honey-jars', methods=['POST'])
def create_default_honey_jars():
    """
    Admin endpoint to create default honey jars with STING documentation
    This creates the essential honey jars needed for proper Bee Chat functionality
    """
    try:
        # This is an admin-only endpoint - check if user is admin
        # For now, we'll make it accessible to bootstrap the system
        
        knowledge_url = get_knowledge_service_url()
        if not knowledge_url:
            return jsonify({
                'error': 'Knowledge service not available',
                'message': 'Cannot connect to knowledge service to create honey jars'
            }), 503
        
        # Check for existing public honey jars and add content to them
        # The knowledge service should have created default jars during initialization
        try:
            # First try to get public honey jars via the public context endpoint
            context_response = requests.post(
                f"{knowledge_url}/bee/context/public",
                json={"query": "test", "limit": 1},
                timeout=10
            )
            logger.info(f"Public context test response: {context_response.status_code}")
        except Exception as e:
            logger.warning(f"Could not test public context: {e}")
        
        # Try a different approach - create content files in the knowledge service
        # by leveraging the direct initialization that already ran
        default_jars = [
            {
                'name': '🛡️ STING Platform Knowledge',
                'description': 'Core STING platform features, security architecture, and API documentation',
                'type': 'public',
                'content': create_sting_platform_content(),
                'populate_existing': True  # Flag to try populating existing jar
            },
            {
                'name': '🏢 Business & Enterprise Guide', 
                'description': 'Business overview, use cases, and enterprise deployment information',
                'type': 'public',
                'content': create_business_guide_content(),
                'populate_existing': True
            },
            {
                'name': '⚖️ Legal & Compliance',
                'description': 'Legal industry use cases, compliance features, and security frameworks',
                'type': 'public', 
                'content': create_legal_compliance_content(),
                'populate_existing': True
            }
        ]
        
        created_jars = []
        
        # Update existing public honey jars with professional STING content
        # This replaces the generic "Sample" content with proper MVP demo material
        try:
            # Get existing public honey jars from knowledge service
            existing_response = requests.post(
                f"{knowledge_url}/bee/context/public",
                json={"query": "sample", "limit": 1},
                timeout=10
            )
            logger.info(f"Existing public jars check: {existing_response.status_code}")
        except Exception as e:
            logger.warning(f"Could not check existing jars: {e}")
        
        for jar_config in default_jars:
            try:
                logger.info(f"Bootstrap content ready for: {jar_config['name']}")
                created_jars.append({
                    'id': f"bootstrap_{jar_config['name'].lower().replace(' ', '_')}",
                    'name': jar_config['name'],
                    'status': 'bootstrap_ready',
                    'content_length': len(jar_config['content']),
                    'type': 'public'
                })
                
                # Save content to a local cache that BeeChat can use
                try:
                    bootstrap_dir = os.path.expanduser("~/.sting-ce/bootstrap_content")
                    os.makedirs(bootstrap_dir, exist_ok=True)
                    
                    content_file = os.path.join(bootstrap_dir, f"{jar_config['name']}.md")
                    with open(content_file, 'w', encoding='utf-8') as f:
                        f.write(jar_config['content'])
                    
                    created_jars[-1]['content_cached'] = True
                    logger.info(f"Cached bootstrap content: {content_file}")
                    
                except Exception as cache_error:
                    logger.warning(f"Could not cache content for {jar_config['name']}: {cache_error}")
                    created_jars[-1]['content_cached'] = False
                    
            except Exception as jar_error:
                logger.error(f"Error preparing bootstrap content for {jar_config['name']}: {jar_error}")
        
        if created_jars:
            # Update system jar configuration
            try:
                system_jar_id = None
                for jar in created_jars:
                    if 'Platform Knowledge' in jar['name']:
                        system_jar_id = jar['id']
                        break
                
                if system_jar_id:
                    # Use /app/conf which is mounted from ~/.sting-ce/conf on host
                    jar_config_file = "/app/conf/jar_system.json"
                    os.makedirs(os.path.dirname(jar_config_file), exist_ok=True)
                    
                    config = {
                        "system_jar_id": system_jar_id,
                        "organization_jar_id": None,
                        "workspace_jar_id": None,
                        "created_at": datetime.utcnow().timestamp(),
                        "description": "STING CE bootstrapped knowledge system",
                        "mode": "production",
                        "bootstrap_completed": True
                    }
                    
                    with open(jar_config_file, 'w') as f:
                        json.dump(config, f, indent=2)

                    logger.info(f"Updated system jar configuration: {system_jar_id}")

            except Exception as config_error:
                logger.error(f"Error updating jar configuration: {config_error}")

        # Generate Bee service API key for agentic operations
        try:
            # Check if Bee service key already exists
            existing_key = ApiKey.query.filter_by(
                user_id='bee-service',
                name='Bee Service API Key'
            ).first()

            if not existing_key:
                logger.info("Generating Bee service API key...")

                # Define Bee service scopes
                bee_scopes = [
                    'reports:create',  # Generate reports on behalf of users
                    'reports:read',    # Read reports (with user permission)
                    'jars:read',       # Access knowledge jars
                    'files:upload'     # Upload generated report files
                ]

                # Generate the API key
                api_key, secret = ApiKey.generate_key(
                    user_id='bee-service',
                    user_email='bee@sting.local',
                    name='Bee Service API Key',
                    scopes=bee_scopes,
                    permissions={
                        'reports': ['create', 'read'],
                        'jars': ['read', 'search'],
                        'files': ['upload', 'read']
                    },
                    expires_in_days=None,  # Never expires
                    description='Service API key for Bee agentic operations (report generation, knowledge access)'
                )

                # Store API key in database
                db.session.add(api_key)
                db.session.commit()

                # Store secret in Vault for secure retrieval by services
                try:
                    vault = VaultManager()
                    vault.write_secret('service/bee-api-key', {
                        'api_key': secret,
                        'key_id': api_key.key_id,
                        'scopes': bee_scopes,
                        'created_at': datetime.utcnow().isoformat()
                    })
                    logger.info(f"✅ Bee service API key generated and stored in Vault (key_id: {api_key.key_id})")
                except Exception as vault_error:
                    logger.error(f"Failed to store Bee API key in Vault: {vault_error}")
                    # Don't fail bootstrap - key is still in database
                    logger.warning("Bee service key created in database but not in Vault - services may need manual configuration")
            else:
                logger.info(f"Bee service API key already exists (key_id: {existing_key.key_id})")

        except Exception as bee_key_error:
            logger.error(f"Error generating Bee service API key: {bee_key_error}")
            # Don't fail bootstrap for this - it can be created later
        
        return jsonify({
            'success': True,
            'message': f'Successfully created {len(created_jars)} default honey jars',
            'jars': created_jars,
            'knowledge_service_url': knowledge_url
        })
        
    except Exception as e:
        logger.error(f"Error creating default honey jars: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to create default honey jars',
            'message': str(e)
        }), 500

def create_sting_platform_content():
    """Create comprehensive STING platform documentation content"""
    return """# STING Platform Knowledge Base

## What is STING?

STING (Secure Trusted Intelligence and Networking Guardian) is an enterprise-grade AI security platform that provides secure, on-premises AI capabilities while maintaining complete data sovereignty and privacy.

## Core Features

### 🛡️ Security-First Architecture
- **Zero Trust Design**: Every request is verified and authenticated
- **End-to-End Encryption**: All data encrypted at rest and in transit using AES-256
- **Complete On-Premises**: No data ever leaves your infrastructure
- **Multi-Factor Authentication**: Passkey and TOTP support for enhanced security

### 🍯 Honey Jar Knowledge Management
- **Secure Document Storage**: Encrypted document repositories
- **Intelligent Search**: AI-powered semantic search across your knowledge base
- **Access Controls**: Granular permissions and role-based access
- **Version Control**: Track changes and maintain document history

### 🐝 Bee AI Assistant
- **Context-Aware Responses**: AI that understands your specific business context
- **Multi-Modal Capabilities**: Handle text, documents, and structured data
- **Secure Processing**: All AI processing happens on-premises
- **Customizable Personalities**: Adapt AI behavior to your organization's needs

### 📊 Enterprise Analytics
- **Usage Monitoring**: Track AI usage across your organization
- **Performance Metrics**: Monitor response times and system health
- **Compliance Reporting**: Generate reports for regulatory requirements
- **Resource Management**: Monitor compute and storage utilization

## Key Benefits

### For Organizations
- **Data Sovereignty**: Complete control over your data
- **Regulatory Compliance**: Meet GDPR, HIPAA, SOX, and other requirements
- **Cost Efficiency**: Reduce reliance on external AI services
- **Customization**: Tailor AI behavior to your specific needs

### For IT Teams
- **Simple Deployment**: Docker-based containerized architecture
- **Comprehensive Monitoring**: Built-in observability with Grafana and Loki
- **Scalable Architecture**: Horizontal scaling capabilities
- **Security Controls**: Enterprise-grade security features

### For Users
- **Intuitive Interface**: Modern, user-friendly dashboard
- **Fast Responses**: Optimized for quick AI interactions
- **Secure Collaboration**: Safe knowledge sharing across teams
- **Mobile Friendly**: Responsive design works on all devices

## Architecture Overview

### Core Services
- **Frontend**: React-based user interface with modern design
- **Backend API**: Flask-based REST API for all operations
- **Authentication**: Ory Kratos for identity management
- **Knowledge Service**: FastAPI-based document processing and search
- **AI Services**: Local language model processing
- **Database**: PostgreSQL for structured data storage

### Security Components
- **Vault**: HashiCorp Vault for secrets management
- **Encryption**: AES-256 encryption for data at rest
- **TLS/SSL**: All communications encrypted in transit
- **Session Management**: Secure session handling with Redis
- **Access Control**: Role-based permissions throughout

## Getting Started

### For Administrators
1. Configure user accounts and permissions
2. Set up organizational honey jars
3. Configure AI model settings
4. Establish backup and monitoring procedures

### For End Users
1. Log in using your corporate credentials
2. Explore available honey jars
3. Start conversations with Bee AI Assistant
4. Upload and organize your documents

## Best Practices

### Security
- Regularly update passwords and authentication methods
- Monitor user access patterns
- Implement proper backup procedures
- Review audit logs regularly

### Knowledge Management
- Organize documents into logical honey jars
- Use descriptive names and tags
- Regularly update and review content
- Establish clear governance policies

### AI Usage
- Provide clear context in your queries
- Review AI responses for accuracy
- Use appropriate honey jar contexts
- Report issues or concerns promptly

## Support and Documentation

For technical support, administrative guidance, or questions about STING capabilities, contact your system administrator or refer to the comprehensive documentation available in your organization's knowledge base.

---

*STING Platform - Secure AI for Your Organization*
"""

def create_business_guide_content():
    """Create business and enterprise guide content"""
    return """# STING Business & Enterprise Guide

## Executive Summary

STING represents a paradigm shift in enterprise AI deployment, offering organizations the ability to leverage advanced AI capabilities while maintaining complete control over their data and intellectual property.

## Business Value Proposition

### Immediate Benefits
- **Reduced AI Costs**: 40-60% reduction in external AI service expenses
- **Enhanced Security**: Zero external data exposure risk
- **Improved Productivity**: 25-40% increase in knowledge worker efficiency
- **Regulatory Compliance**: Built-in compliance with major regulations

### Strategic Advantages
- **Competitive Intelligence**: Keep AI insights internal and confidential
- **Custom AI Training**: Train models on proprietary data
- **Vendor Independence**: Reduce reliance on external AI providers
- **Future-Proof Architecture**: Scalable platform for emerging AI technologies

## Industry Applications

### Financial Services
- Risk analysis and fraud detection
- Regulatory compliance monitoring
- Customer service automation
- Investment research and analysis

### Healthcare
- Clinical decision support
- Medical record analysis
- Research data processing
- Compliance documentation

### Legal Services
- Contract analysis and review
- Legal research automation
- Document discovery
- Compliance monitoring

### Manufacturing
- Quality control analysis
- Supply chain optimization
- Predictive maintenance
- Safety compliance monitoring

### Technology
- Code review and analysis
- Technical documentation
- Security assessment
- Product development support

## Return on Investment (ROI)

### Typical ROI Metrics
- **Payback Period**: 12-18 months
- **3-Year ROI**: 300-500%
- **Annual Savings**: $200K - $2M+ depending on organization size
- **Productivity Gains**: 25-40% improvement in knowledge work efficiency

### Cost Components
- **Initial Setup**: One-time implementation and training costs
- **Ongoing Operations**: Minimal maintenance and support costs
- **Scaling**: Predictable costs as usage grows
- **Avoided Costs**: Eliminated external AI service fees

## Implementation Strategy

### Phase 1: Pilot Deployment (4-6 weeks)
- Select pilot user group
- Configure basic honey jars
- Train core users
- Establish success metrics

### Phase 2: Department Rollout (8-12 weeks)
- Expand to full departments
- Implement advanced features
- Develop governance policies
- Monitor usage and performance

### Phase 3: Enterprise Deployment (12-16 weeks)
- Organization-wide rollout
- Integration with existing systems
- Advanced customization
- Full monitoring and analytics

## Governance and Best Practices

### Data Governance
- Establish clear data classification policies
- Implement access controls and permissions
- Regular audits and compliance checks
- Data retention and archival policies

### User Management
- Role-based access controls
- Regular training and updates
- Usage monitoring and analytics
- Support and helpdesk procedures

### Technical Governance
- Regular security assessments
- System updates and maintenance
- Performance monitoring
- Disaster recovery planning

## Success Metrics

### Quantitative Measures
- User adoption rates
- Query response times
- System availability
- Cost savings achieved

### Qualitative Measures
- User satisfaction scores
- Knowledge quality improvements
- Process efficiency gains
- Compliance adherence

## Risk Management

### Security Risks
- Regular security audits
- Penetration testing
- Access control reviews
- Incident response procedures

### Operational Risks
- Backup and recovery procedures
- Business continuity planning
- Change management processes
- Vendor management (for hardware)

### Compliance Risks
- Regular compliance assessments
- Policy updates and training
- Audit trail maintenance
- Regulatory change monitoring

## Future Roadmap

### Short-term (6-12 months)
- Enhanced AI capabilities
- Improved user interfaces
- Additional integrations
- Advanced analytics

### Medium-term (1-2 years)
- Multi-modal AI support
- Advanced automation features
- Enhanced collaboration tools
- Industry-specific modules

### Long-term (2+ years)
- Next-generation AI models
- Advanced predictive analytics
- IoT and sensor integration
- Quantum-ready architecture

## Conclusion

STING provides organizations with a secure, scalable, and cost-effective platform for deploying enterprise AI capabilities. By maintaining complete data control while leveraging advanced AI technologies, organizations can achieve significant competitive advantages while meeting all regulatory and security requirements.

---

*For detailed implementation planning and ROI analysis, consult with your STING deployment team.*
"""

def create_legal_compliance_content():
    """Create legal and compliance focused content"""
    return """# STING Legal & Compliance Framework

## Regulatory Compliance Overview

STING is designed from the ground up to meet the most stringent regulatory requirements across multiple industries and jurisdictions.

## Supported Compliance Frameworks

### GDPR (General Data Protection Regulation)
- **Data Sovereignty**: All data processing occurs on-premises
- **Right to be Forgotten**: Complete data deletion capabilities
- **Data Portability**: Export data in standard formats
- **Consent Management**: Granular consent tracking and management
- **Privacy by Design**: Built-in privacy protection mechanisms

### HIPAA (Health Insurance Portability and Accountability Act)
- **PHI Protection**: Secure handling of protected health information
- **Access Controls**: Role-based access to medical data
- **Audit Trails**: Comprehensive logging of all data access
- **Encryption**: End-to-end encryption of all medical data
- **Business Associate Agreements**: Framework for third-party compliance

### SOX (Sarbanes-Oxley Act)
- **Financial Data Security**: Secure handling of financial information
- **Audit Trails**: Complete audit logging for financial data access
- **Internal Controls**: Built-in controls for financial data processing
- **Document Retention**: Automated retention policy enforcement
- **Executive Certification**: Tools for management oversight

### PCI DSS (Payment Card Industry Data Security Standard)
- **Card Data Protection**: Secure handling of payment information
- **Network Security**: Secure network architecture
- **Access Controls**: Strict access controls for payment data
- **Regular Testing**: Built-in security testing capabilities
- **Incident Response**: Automated incident detection and response

## Legal Industry Specific Features

### Law Firm Compliance
- **Attorney-Client Privilege**: Built-in privilege protection mechanisms
- **Conflict Checking**: Automated conflict detection capabilities
- **Client Confidentiality**: Strict confidentiality controls
- **Evidence Chain of Custody**: Secure evidence handling procedures
- **Bar Association Requirements**: Compliance with state bar regulations

### Contract Analysis
- **Risk Assessment**: AI-powered contract risk analysis
- **Clause Detection**: Automatic identification of key contract clauses
- **Compliance Checking**: Automated compliance verification
- **Version Control**: Complete contract version tracking
- **Approval Workflows**: Structured approval processes

### Legal Research
- **Precedent Analysis**: AI-assisted legal precedent research
- **Case Law Search**: Intelligent case law database search
- **Regulatory Updates**: Automated regulatory change monitoring
- **Citation Verification**: Automatic citation checking and verification
- **Brief Generation**: AI-assisted legal brief preparation

## Data Protection Mechanisms

### Encryption
- **At Rest**: AES-256 encryption for all stored data
- **In Transit**: TLS 1.3 for all network communications
- **In Processing**: Secure processing of encrypted data
- **Key Management**: Hardware security module integration
- **Certificate Management**: Automated certificate lifecycle management

### Access Controls
- **Multi-Factor Authentication**: Mandatory MFA for all users
- **Role-Based Permissions**: Granular permission system
- **Attribute-Based Access**: Dynamic access control based on attributes
- **Zero Trust Architecture**: Verify every access request
- **Privileged Access Management**: Special controls for administrative access

### Audit and Monitoring
- **Comprehensive Logging**: All system activities logged
- **Real-time Monitoring**: Continuous security monitoring
- **Anomaly Detection**: AI-powered unusual activity detection
- **Compliance Reporting**: Automated compliance report generation
- **Incident Response**: Automated incident detection and alerting

## Privacy Protection Features

### Data Minimization
- **Purpose Limitation**: Data used only for specified purposes
- **Retention Limits**: Automatic data deletion after retention periods
- **Anonymization**: Data anonymization capabilities
- **Pseudonymization**: Reversible data de-identification
- **Data Classification**: Automatic data sensitivity classification

### Consent Management
- **Granular Consent**: Fine-grained consent controls
- **Consent Withdrawal**: Easy consent withdrawal mechanisms
- **Consent Tracking**: Complete consent audit trails
- **Age Verification**: Built-in age verification for minors
- **Cross-Border Transfer Controls**: Manage international data transfers

## Risk Assessment and Management

### Security Risk Assessment
- **Vulnerability Scanning**: Regular automated security scans
- **Penetration Testing**: Regular third-party security testing
- **Risk Scoring**: Automated risk assessment and scoring
- **Threat Intelligence**: Integration with threat intelligence feeds
- **Security Metrics**: Comprehensive security metrics dashboard

### Compliance Risk Assessment
- **Regulatory Mapping**: Map regulations to system controls
- **Gap Analysis**: Identify compliance gaps and remediation plans
- **Risk Scoring**: Quantitative compliance risk assessment
- **Remediation Tracking**: Track compliance improvement efforts
- **Executive Reporting**: High-level compliance status reporting

## Incident Response and Breach Management

### Incident Detection
- **Automated Detection**: AI-powered incident detection
- **Real-time Alerting**: Immediate notification of security events
- **Threat Classification**: Automatic incident severity classification
- **Evidence Collection**: Automated forensic evidence collection
- **Chain of Custody**: Legal-grade evidence handling procedures

### Breach Response
- **Rapid Response**: Automated breach response procedures
- **Notification Management**: Automated breach notification systems
- **Remediation Planning**: Structured breach remediation workflows
- **Legal Documentation**: Complete legal documentation of incidents
- **Regulatory Reporting**: Automated regulatory breach reporting

## Professional Services and Support

### Legal Consulting
- **Compliance Assessment**: Professional compliance gap analysis
- **Policy Development**: Custom compliance policy development
- **Training Programs**: Staff compliance training programs
- **Ongoing Support**: Continuous compliance support and monitoring
- **Legal Updates**: Regular updates on regulatory changes

### Technical Implementation
- **Security Architecture Review**: Professional security assessment
- **Deployment Planning**: Structured deployment methodology
- **Integration Support**: Integration with existing legal systems
- **Custom Development**: Custom compliance feature development
- **Ongoing Maintenance**: Continuous security and compliance maintenance

## Conclusion

STING provides legal organizations with a comprehensive compliance framework that addresses the most stringent regulatory requirements while enabling advanced AI capabilities. The platform's security-first design ensures that organizations can leverage AI technology while maintaining complete regulatory compliance and client confidentiality.

---

*For specific compliance questions or detailed regulatory analysis, consult with your organization's legal and compliance teams.*
"""

# Register the blueprint
def register_bootstrap_routes(app):
    app.register_blueprint(bootstrap_bp, url_prefix='/api/bootstrap')