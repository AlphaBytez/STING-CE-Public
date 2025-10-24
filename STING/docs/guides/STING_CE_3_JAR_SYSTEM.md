# STING CE 3-Jar Knowledge System

## Overview

STING CE includes a strategic 3-jar knowledge management system optimized for the platform's honey jar limits. This system provides persistent, organized knowledge while maximizing utility within constraints.

## The 3-Jar Architecture

### 🛡️ System Jar: "STING System Knowledge" 
**Purpose**: Core platform knowledge that persists across updates
**Content**: 
- Essential STING platform documentation
- Architecture and technical specifications
- Law firm and enterprise application guides
- Business overview and capabilities

**Characteristics**:
- ✅ Always maintained by the system
- ✅ Contains comprehensive STING knowledge for accurate Bee responses
- ✅ Automatically populated during fresh installs
- ⚠️ Should not be deleted (contains critical knowledge)

### 🏢 Organization Jar: "Organization Knowledge"
**Purpose**: Admin and business team knowledge base
**Content**:
- Installation and setup documentation
- Administrative guides and procedures
- Security and authentication details
- Team-specific documentation

**Characteristics**:
- ✅ Managed by administrators
- ✅ Contains business-specific knowledge
- ✅ Suitable for internal documentation and processes
- 📝 Can be customized per organization needs

### 📋 Workspace Jar: "General Workspace"
**Purpose**: User collaboration and custom queries
**Content**:
- User-uploaded documents
- Project-specific materials
- Temporary research documents
- Collaborative knowledge base

**Characteristics**:
- ✅ Available for all users
- ✅ Flexible content based on current needs
- ✅ Can be cleared and repopulated as needed
- 🔄 Most dynamic of the three jars

## Strategic Benefits

### Optimized for STING CE Limits
- **Maximum Utility**: Each jar serves a distinct purpose
- **Persistent Knowledge**: System jar ensures consistent platform knowledge
- **Flexible Usage**: Organization and workspace jars adapt to business needs
- **No Knowledge Loss**: Critical STING information always available

### Business Workflow Integration
1. **New Employee Onboarding**: System jar provides STING basics
2. **Administrative Tasks**: Organization jar contains procedures
3. **Daily Work**: Workspace jar for current projects and collaboration
4. **Client Queries**: All jars combine to provide comprehensive context

## Usage Guidelines

### For Administrators
- **System Jar**: Monitor but avoid deleting - contains critical knowledge
- **Organization Jar**: Populate with business procedures and admin guides
- **Workspace Jar**: Allow users to populate with project materials

### For Users
- **Query Strategy**: Ask broad STING questions to leverage system jar
- **Upload Strategy**: Use workspace jar for collaboration and project docs
- **Organization Access**: Reference organization jar for company procedures

### For Developers
- **System Maintenance**: Scripts ensure system jar is always populated
- **Configuration**: Jar IDs stored in `~/.sting-ce/conf/jar_system.json`
- **Recovery**: `ensure_primary_honey_jar.py` can recreate the system if needed

## Maintenance Commands

### Check System Health
```bash
# Verify all 3 jars are healthy
python3 scripts/ensure_primary_honey_jar.py
```

### Recreate System (if needed)
```bash
# Recreate entire 3-jar system
python3 scripts/setup_default_honey_jars.py
```

### Monitor Usage
```bash
# Check jar contents via knowledge service API
curl -H "Authorization: Bearer $TOKEN" http://localhost:8090/honey-jars
```

## Configuration Files

### System Configuration
- **Location**: `~/.sting-ce/conf/jar_system.json`
- **Content**: Jar IDs and metadata
- **Purpose**: System reference for jar management

### Example Configuration
```json
{
  "system_jar_id": "uuid-system-jar",
  "organization_jar_id": "uuid-org-jar", 
  "workspace_jar_id": "uuid-workspace-jar",
  "created_at": 1642781234.567,
  "description": "STING CE 3-jar system configuration"
}
```

## Best Practices

### Content Strategy
1. **System Jar**: Keep focused on core STING knowledge - don't add unrelated content
2. **Organization Jar**: Update with business procedures and admin documentation
3. **Workspace Jar**: Refresh periodically to keep content relevant

### Query Optimization
- Use specific queries that can leverage the right jar's expertise
- Combine questions to get context from multiple jars
- Ask follow-up questions to drill down into specific areas

### Team Coordination
- Establish guidelines for what goes in each jar
- Regular cleanup of workspace jar to maintain relevance
- Document jar usage patterns for team knowledge

## Troubleshooting

### "No Honey Jars Available" Error
1. Check if services are running: `./manage_sting.sh status`
2. Verify jar system: `python3 scripts/ensure_primary_honey_jar.py`
3. Recreate if needed: `python3 scripts/setup_default_honey_jars.py`

### Inaccurate Bee Responses
1. Verify system jar has content
2. Check if knowledge service is accessible
3. Ensure authentication is working properly

### Jar Limit Reached
- STING CE is limited to 3 honey jars maximum
- Delete workspace jar content if needed for flexibility
- Consider upgrading to STING Enterprise for unlimited jars

---

The STING CE 3-jar system maximizes knowledge management capabilities within platform constraints, providing persistent platform knowledge while enabling flexible business use cases.