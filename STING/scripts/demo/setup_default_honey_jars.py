#!/usr/bin/env python3
"""
Setup Default Honey Jars with STING Documentation
Creates comprehensive honey jars with STING documentation for accurate Bee Chat responses.
Includes enterprise features, compliance info, and industry-specific guides.

This script runs automatically during fresh installs to populate the knowledge base.
"""

import os
import sys
import json
import requests
import time
import tempfile
from pathlib import Path

def wait_for_services(max_attempts=30, delay=10):
    """Wait for knowledge service to be available"""
    base_urls = ["http://localhost:8090", "http://knowledge:8090", "http://sting-ce-knowledge:8090"]
    
    for attempt in range(max_attempts):
        for base_url in base_urls:
            try:
                health_response = requests.get(f"{base_url}/health", timeout=5)
                if health_response.status_code == 200:
                    print(f"✅ Knowledge service available at: {base_url}")
                    return base_url
            except:
                continue
        
        if attempt < max_attempts - 1:
            print(f"⏳ Waiting for knowledge service... ({attempt + 1}/{max_attempts})")
            time.sleep(delay)
    
    print("❌ Knowledge service not available after maximum attempts")
    return None

def get_admin_session():
    """Get admin session token for fresh install setup"""
    # In fresh install, try to get admin credentials
    admin_password_file = os.path.expanduser("~/.sting-ce/admin_password.txt")
    
    if os.path.exists(admin_password_file):
        with open(admin_password_file, 'r') as f:
            admin_password = f.read().strip()
    else:
        admin_password = "Password1!"  # Default fallback
    
    try:
        session = requests.Session()
        session.verify = False
        
        # Initialize login flow
        flow_response = session.get("https://localhost:4433/self-service/login/api", timeout=10)
        if flow_response.status_code != 200:
            print("❌ Cannot initialize Kratos login flow")
            return None
            
        flow_data = flow_response.json()
        flow_id = flow_data["id"]
        
        # Submit login
        login_data = {
            "method": "password",
            "password": admin_password,
            "password_identifier": "admin@sting.local"
        }
        
        login_response = session.post(
            f"https://localhost:4433/self-service/login?flow={flow_id}",
            json=login_data,
            timeout=10
        )
        
        if login_response.status_code == 200:
            response_data = login_response.json()
            session_token = response_data.get('session_token')
            if session_token:
                print("✅ Admin authentication successful")
                return session_token
        
        print("❌ Admin authentication failed")
        return None
        
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None

def create_honey_jar(name, description, session_token, knowledge_url, jar_type="public"):
    """Create a new honey jar via the knowledge service API"""
    headers = {
        "Authorization": f"Bearer {session_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "name": name,
        "description": description, 
        "type": jar_type
    }
    
    try:
        response = requests.post(f"{knowledge_url}/honey-jars", json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            jar = response.json()
            jar_id = jar.get('id')
            print(f"✅ Created honey jar: {name} (ID: {jar_id})")
            return jar_id
        else:
            print(f"❌ Failed to create honey jar {name}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error creating honey jar {name}: {str(e)}")
        return None

def upload_document(jar_id, file_path, session_token, knowledge_url):
    """Upload a document to a honey jar"""
    if not os.path.exists(file_path):
        print(f"  ⚠️  File not found: {file_path}")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    filename = os.path.basename(file_path)
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, 'text/markdown')}
            data = {'tags': ['documentation', 'enterprise', 'default-install']}
            
            response = requests.post(
                f"{knowledge_url}/honey-jars/{jar_id}/documents/upload",
                files=files,
                data=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"    ✅ {filename}")
                return True
            else:
                print(f"    ❌ {filename}: {response.status_code}")
                return False
    except Exception as e:
        print(f"    ❌ {filename}: {e}")
        return False

def create_law_firm_guide():
    """Create comprehensive law firm guide content"""
    return """# STING for Law Firms: Enterprise AI Security Platform

## Executive Summary

STING (Secure Trusted Intelligence and Networking Guardian) provides law firms with enterprise-grade AI capabilities while maintaining the highest standards of client confidentiality and regulatory compliance.

## Key Benefits for Law Firms

### 🔒 Client Confidentiality & Privilege Protection
- **Complete On-Premises Deployment**: All data remains within your infrastructure
- **Zero External Dependencies**: No client data ever leaves your firm
- **Attorney-Client Privilege Safeguards**: Built-in protections for privileged communications
- **Secure Document Classification**: Automatic identification and protection of sensitive legal documents

### ⚖️ Regulatory Compliance
- **State Bar Compliant**: Meets confidentiality requirements in all US jurisdictions
- **GDPR & International Standards**: Full European data protection compliance
- **Audit Trails**: Comprehensive logging for regulatory reporting
- **Data Retention Policies**: Automated compliance with document retention requirements

### 🚀 Legal Practice Enhancement
- **Contract Analysis**: AI-powered contract review and risk identification
- **Legal Research**: Intelligent search across case law, statutes, and firm knowledge
- **Brief Generation**: AI-assisted legal writing and document preparation
- **Case Strategy**: Pattern analysis across similar cases and outcomes

### 📊 Knowledge Management
- **Firm Expertise Capture**: Preserve and share institutional knowledge
- **Precedent Library**: Searchable database of successful strategies and documents
- **Client Matter Organization**: Secure, organized access to all case materials
- **Cross-Practice Collaboration**: Safe knowledge sharing between practice groups

## Use Cases by Practice Area

### Corporate Law
- M&A due diligence document review
- Contract analysis and risk assessment
- Regulatory compliance monitoring
- Corporate governance documentation

### Litigation
- Discovery document analysis
- Legal precedent research
- Brief writing assistance
- Case strategy development

### Intellectual Property
- Patent and trademark research
- IP portfolio management
- Prior art analysis
- Filing deadline tracking

### Real Estate
- Property document review
- Title analysis and verification
- Lease agreement optimization
- Zoning and compliance research

### Employment Law
- Policy development and review
- Compliance monitoring
- Investigation documentation
- Training material creation

## Security Architecture

### Enterprise-Grade Security
- **End-to-End Encryption**: All data encrypted at rest and in transit
- **Multi-Factor Authentication**: Passkey and TOTP support
- **Role-Based Access Control**: Granular permissions for different staff levels
- **Network Isolation**: Complete air-gapped deployment options

### Compliance Features
- **PII Detection**: Automatic identification and protection of personal data
- **Data Loss Prevention**: Prevent accidental disclosure of confidential information
- **Secure Communications**: Encrypted messaging and file sharing
- **Audit Logging**: Complete trail of all system access and activities

## Implementation & ROI

### Cost Benefits
- Reduce external counsel fees by 30-40%
- Increase attorney productivity by 25%
- Minimize compliance violations and penalties
- Streamline document review processes

### Revenue Enhancement
- Faster case resolution and client delivery
- Higher quality work product
- Expanded service capabilities
- Improved client satisfaction and retention

## Getting Started

STING can be deployed in phases:
1. **Assessment**: Infrastructure and security requirements (2-4 weeks)
2. **Pilot**: Single practice group deployment (4-6 weeks)  
3. **Full Deployment**: Firm-wide rollout (8-12 weeks)

Contact your STING administrator for a confidential demonstration tailored to your firm's specific needs.

---

*STING: Secure AI for Legal Excellence*
"""

def create_enterprise_guide():
    """Create enterprise features overview"""
    return """# STING Enterprise Features & Capabilities

## Platform Overview

STING is designed for enterprise deployment with advanced security, scalability, and integration capabilities that meet the most demanding organizational requirements.

## Core Enterprise Features

### 🏢 Multi-Tenant Architecture
- **Organization Isolation**: Complete data separation between tenants
- **Centralized Administration**: Unified management across departments
- **Resource Allocation**: Granular control over compute and storage resources
- **Custom Branding**: White-label deployment options

### 🔐 Enterprise Security
- **Zero Trust Architecture**: Verify every request and access attempt
- **Advanced Encryption**: AES-256 encryption with hardware security modules
- **Identity Federation**: Integration with Active Directory, LDAP, SAML, OAuth
- **Compliance Frameworks**: SOC 2, ISO 27001, FedRAMP, GDPR, HIPAA

### 📊 Advanced Analytics & Monitoring
- **Usage Analytics**: Comprehensive insights into platform utilization
- **Performance Monitoring**: Real-time system health and performance metrics
- **Audit Reporting**: Detailed logs for compliance and security auditing
- **Custom Dashboards**: Configurable views for different stakeholders

### 🔗 Enterprise Integrations
- **API-First Design**: RESTful APIs for seamless integration
- **Webhook Support**: Real-time notifications and event triggers
- **Data Connectors**: Direct integration with enterprise data sources
- **SSO Integration**: Single sign-on with corporate identity providers

## Honey Jar Enterprise Features

### 🍯 Advanced Knowledge Management
- **Versioning**: Track document changes and maintain revision history
- **Approval Workflows**: Multi-stage review and approval processes
- **Access Controls**: Granular permissions at document and folder level
- **Metadata Management**: Rich tagging and classification systems

### 🔄 Data Lifecycle Management
- **Retention Policies**: Automated data retention and deletion
- **Archival Systems**: Long-term storage with retrieval capabilities
- **Backup & Recovery**: Automated backup with point-in-time recovery
- **Data Migration**: Tools for importing existing knowledge bases

### 🌐 Global Distribution
- **Multi-Region Deployment**: Deploy across multiple data centers
- **Content Distribution**: Optimized content delivery for global teams
- **Disaster Recovery**: Automated failover and business continuity
- **High Availability**: 99.9% uptime SLA with redundancy

## Bee AI Enterprise Capabilities

### 🧠 Advanced AI Features
- **Custom Model Training**: Fine-tune models on organization-specific data
- **Multi-Language Support**: Support for 50+ languages
- **Domain Expertise**: Specialized models for different industries
- **Contextual Awareness**: Deep understanding of organizational context

### 🛠️ Enterprise Tools Integration
- **Workflow Automation**: Integrate AI into business processes
- **Decision Support**: AI-powered recommendations and insights
- **Quality Assurance**: Automated review and validation capabilities
- **Performance Optimization**: Continuous learning and improvement

## Deployment Options

### On-Premises
- **Complete Control**: Full data sovereignty and control
- **Custom Hardware**: Optimized for your specific requirements
- **Air-Gapped**: Isolated from external networks
- **Professional Services**: White-glove setup and configuration

### Private Cloud
- **Hybrid Flexibility**: Combine on-premises with cloud benefits
- **Managed Services**: 24/7 monitoring and maintenance
- **Scalable Resources**: Dynamic scaling based on demand
- **Geographic Distribution**: Multi-region deployments

### Dedicated Cloud
- **Isolated Environment**: Dedicated infrastructure in cloud
- **Enterprise SLA**: Guaranteed performance and availability
- **Managed Updates**: Automated patching and updates
- **Custom Configuration**: Tailored to organizational needs

## Industry-Specific Solutions

### Healthcare
- **HIPAA Compliance**: Full healthcare data protection
- **Medical Terminology**: Specialized medical AI models
- **Clinical Workflows**: Integration with EHR systems
- **Research Support**: AI-powered medical research tools

### Financial Services
- **Regulatory Compliance**: Meet banking and financial regulations
- **Risk Assessment**: AI-powered risk analysis and reporting
- **Fraud Detection**: Advanced pattern recognition for security
- **Trading Support**: Real-time market analysis and insights

### Government
- **Security Clearance**: Support for classified environments
- **Compliance**: Meet government security requirements
- **Accessibility**: Section 508 compliance for accessibility
- **Audit Trail**: Complete logging for government oversight

### Manufacturing
- **Operational Intelligence**: AI-powered manufacturing insights
- **Supply Chain**: Optimization and risk management
- **Quality Control**: Automated inspection and quality assurance
- **Predictive Maintenance**: AI-driven maintenance scheduling

## Support & Services

### Professional Services
- **Implementation**: Expert deployment and configuration
- **Training**: Comprehensive user and administrator training
- **Custom Development**: Tailored solutions and integrations
- **Migration**: Seamless migration from existing systems

### Ongoing Support
- **24/7 Support**: Round-the-clock technical assistance
- **Success Management**: Dedicated customer success team
- **Regular Reviews**: Quarterly business reviews and optimization
- **Continuous Updates**: Regular feature updates and security patches

## Pricing & Licensing

### Flexible Licensing Options
- **Per-User**: Straightforward per-user pricing
- **Concurrent Users**: Cost-effective for large organizations
- **Department-Based**: Pricing based on organizational structure
- **Enterprise**: Custom pricing for large deployments

### Value Proposition
- **ROI**: Typical 300-500% return on investment within 18 months
- **Cost Savings**: 40-60% reduction in AI infrastructure costs
- **Productivity**: 25-40% improvement in knowledge worker productivity
- **Risk Reduction**: Significant reduction in security and compliance risks

Contact your STING representative for detailed pricing and deployment consultation tailored to your enterprise requirements.

---

*STING Enterprise: Secure AI at Scale*
"""

def create_sting_ce_three_jar_system(session_token, knowledge_url):
    """
    Create the strategic 3-jar system for STING CE:
    1. System jar - Core STING platform knowledge (protected)
    2. Organization jar - Admin/org-specific knowledge
    3. General jar - User workspace for custom queries
    """
    print("🏛️ Creating STING CE strategic 3-jar knowledge system...")
    print("   📋 Optimized for STING CE 3-jar limit")
    
    jar_ids = {}
    
    # 1. System Jar - Core STING Knowledge (Protected)
    system_jar_id = create_honey_jar(
        name="🛡️ STING System Knowledge",
        description="Core STING platform knowledge - Contains essential platform documentation for accurate Bee responses. Reserved system jar.",
        session_token=session_token,
        knowledge_url=knowledge_url,
        jar_type="public"
    )
    
    if system_jar_id:
        jar_ids['system'] = system_jar_id
        print(f"✅ Created system jar: {system_jar_id}")
    else:
        print("❌ Failed to create system honey jar")
        return None
    
    # 2. Organization Jar - Admin/Business Knowledge
    org_jar_id = create_honey_jar(
        name="🏢 Organization Knowledge",
        description="Organization-specific knowledge base for admin team and business documentation. Managed by administrators.",
        session_token=session_token,
        knowledge_url=knowledge_url,
        jar_type="public"
    )
    
    if org_jar_id:
        jar_ids['organization'] = org_jar_id
        print(f"✅ Created organization jar: {org_jar_id}")
    
    # 3. General Workspace Jar - User Queries
    workspace_jar_id = create_honey_jar(
        name="📋 General Workspace",
        description="General purpose knowledge workspace for user documents and custom queries. Available for team collaboration.",
        session_token=session_token,
        knowledge_url=knowledge_url,
        jar_type="public"
    )
    
    if workspace_jar_id:
        jar_ids['workspace'] = workspace_jar_id
        print(f"✅ Created workspace jar: {workspace_jar_id}")
    
    # Save jar IDs for system reference
    # This script runs on the host, so use the actual host path
    jar_config_file = os.path.expanduser("~/.sting-ce/conf/jar_system.json")
    os.makedirs(os.path.dirname(jar_config_file), exist_ok=True)
    
    try:
        with open(jar_config_file, 'w') as f:
            json.dump({
                "system_jar_id": jar_ids.get('system'),
                "organization_jar_id": jar_ids.get('organization'), 
                "workspace_jar_id": jar_ids.get('workspace'),
                "created_at": time.time(),
                "description": "STING CE 3-jar system configuration"
            }, f, indent=2)
        print(f"📝 Jar system config saved to: {jar_config_file}")
    except Exception as e:
        print(f"⚠️  Warning: Could not save jar config: {e}")
    
    return jar_ids

def setup_default_honey_jars():
    """Set up STING CE 3-jar knowledge system for fresh installs"""
    print("🍯 Setting up STING CE knowledge base...")
    print("🏷️  Optimized for 3-jar limit with strategic allocation")
    print("=" * 60)
    
    # Wait for services to be ready
    knowledge_url = wait_for_services()
    if not knowledge_url:
        print("❌ Cannot connect to knowledge service")
        return False
    
    # Get admin authentication
    session_token = get_admin_session()
    if not session_token:
        print("❌ Cannot authenticate as admin")
        return False
    
    # Create the strategic 3-jar system
    jar_ids = create_sting_ce_three_jar_system(session_token, knowledge_url)
    if not jar_ids:
        print("❌ Failed to create 3-jar system")
        return False
    
    total_docs = 0
    
    # Populate System Jar with core STING knowledge
    print(f"\n📚 Populating system jar with core STING platform knowledge...")
    system_docs = [
        "docs/STING_QUICK_REFERENCE.md",
        "docs/ARCHITECTURE.md",
        "docs/BUSINESS_OVERVIEW.md",
        "docs/BEE_AGENTIC_CAPABILITIES.md"
    ]
    
    system_upload_count = 0
    for doc_path in system_docs:
        if upload_document(jar_ids['system'], doc_path, session_token, knowledge_url):
            system_upload_count += 1
            total_docs += 1
        time.sleep(1)
    
    # Add comprehensive enterprise and law firm guides to system jar
    law_firm_content = create_law_firm_guide()
    law_firm_file = "/tmp/sting_law_firm_guide.md"
    
    try:
        with open(law_firm_file, 'w') as f:
            f.write(law_firm_content)
        
        if upload_document(jar_ids['system'], law_firm_file, session_token, knowledge_url):
            system_upload_count += 1
            total_docs += 1
        
        os.unlink(law_firm_file)
    except Exception as e:
        print(f"  ❌ Error adding law firm guide: {e}")
    
    enterprise_content = create_enterprise_guide()
    enterprise_file = "/tmp/sting_enterprise_guide.md"
    
    try:
        with open(enterprise_file, 'w') as f:
            f.write(enterprise_content)
        
        if upload_document(jar_ids['system'], enterprise_file, session_token, knowledge_url):
            system_upload_count += 1
            total_docs += 1
        
        os.unlink(enterprise_file)
    except Exception as e:
        print(f"  ❌ Error adding enterprise guide: {e}")
    
    print(f"  📄 System jar: {system_upload_count} core documents")
    
    # Populate Organization Jar with admin/business documentation
    if jar_ids.get('organization'):
        print(f"\n🏢 Populating organization jar with admin documentation...")
        org_docs = [
            "docs/INSTALLATION.md",
            "docs/features/HONEY_JAR_USER_GUIDE.md",
            "docs/guides/AI_ASSISTANT.md",
            "docs/security/authentication-requirements.md"
        ]
        
        org_upload_count = 0
        for doc_path in org_docs:
            if upload_document(jar_ids['organization'], doc_path, session_token, knowledge_url):
                org_upload_count += 1
                total_docs += 1
            time.sleep(1)
        
        print(f"  📄 Organization jar: {org_upload_count} admin documents")
    
    # Leave Workspace Jar empty for user content
    if jar_ids.get('workspace'):
        print(f"\n📋 Workspace jar ready for user content")
        print(f"     Users can upload documents and collaborate here")
    
    print(f"\n🎉 STING CE 3-jar knowledge system setup complete!")
    print(f"   🛡️  System jar: Core STING knowledge ({system_upload_count} docs)")
    print(f"   🏢 Organization jar: Admin documentation ({org_upload_count if jar_ids.get('organization') else 0} docs)")
    print(f"   📋 Workspace jar: Ready for user content")
    print(f"   📊 Total documents: {total_docs}")
    print(f"   💾 Configuration saved for future reference")
    
    if total_docs > 0:
        print(f"\n💡 Strategic jar usage for STING CE:")
        print(f"   🛡️  System jar: Always available for accurate STING information")
        print(f"   🏢 Organization jar: Business/admin team knowledge base")
        print(f"   📋 Workspace jar: User collaboration and custom queries")
        print(f"\n🐝 Test Bee Chat with these queries:")
        print(f"   • 'What is STING and how does it work?'")
        print(f"   • 'How can STING help my law firm?'")
        print(f"   • 'What are STING's enterprise security features?'")
        print(f"   • 'Tell me about STING's installation process'")
        print(f"\n   Bee should now provide comprehensive, accurate responses!")
    
    return total_docs > 0

if __name__ == "__main__":
    success = setup_default_honey_jars()
    sys.exit(0 if success else 1)