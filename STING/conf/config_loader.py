import os
try:
    import yaml  # type: ignore
except ImportError:
    yaml = None
import json
import logging
import secrets
import string
import time
import sys  # Added sys import
import base64
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from pathlib import Path
try:
    import hvac  # type: ignore
except ImportError:
    hvac = None
import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
class ConfigurationError(Exception):
    """Exception raised for errors in the configuration loader."""
    pass

def check_config_exists(config_path: str) -> bool:
    """
    Check if config.yml exists, and if not, create it from the best available template.
    Automatically detects macOS and uses Mac-optimized template when available.
    Returns True if config exists or was created successfully, False otherwise.
    """
    if os.path.exists(config_path):
        return True
    
    # Platform detection for optimal template selection
    import platform
    is_macos = platform.system() == 'Darwin'
    
    # Choose the best template based on platform
    mac_config_path = config_path + '.default.mac'
    default_config_path = config_path + '.default'
    
    if is_macos and os.path.exists(mac_config_path):
        template_path = mac_config_path
        platform_name = "macOS/Apple Silicon"
    elif os.path.exists(default_config_path):
        template_path = default_config_path
        platform_name = "general"
    else:
        logger.error(f"❌ No configuration templates found!")
        logger.error(f"   Looked for: {mac_config_path if is_macos else default_config_path}")
        logger.error(f"   And: {default_config_path}")
        logger.error("Cannot proceed without configuration template.")
        return False
    
    logger.warning(f"⚠️  Configuration file not found: {config_path}")
    logger.info(f"🖥️  Detected platform: {platform.system()} ({platform.machine()})")
    logger.info(f"📝 Creating config.yml from {platform_name} template: {template_path}")
    
    try:
        import shutil
        shutil.copy2(template_path, config_path)
        logger.info(f"✅ Configuration file created successfully!")
        logger.info(f"💡 Mac-optimized configuration applied!" if is_macos and template_path.endswith('.mac') else f"💡 Please customize {config_path} for your environment.")
        
        if is_macos and template_path.endswith('.mac'):
            logger.info("🍎 Apple Silicon optimizations enabled:")
            logger.info("   - MPS (Metal Performance Shaders) acceleration")
            logger.info("   - fp16 precision for faster inference")
            logger.info("   - Model preloading for instant responses")
            logger.info("   - Unified memory optimization")
            logger.info("   - Response caching (10 minutes)")
        else:
            logger.info("   Key settings to review:")
            logger.info("   - application.install_dir")
            logger.info("   - application.models_dir") 
            logger.info("   - llm_service.performance.profile (for speed optimization)")
            logger.info("   - speed optimization presets (see bottom of config file)")
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create config file: {e}")
        return False

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from a YAML or JSON file."""
    try:
        # Check if config file exists
        if not os.path.exists(config_path):
            raise ConfigurationError(f"Configuration file not found: {config_path}. Use check_config_exists() to create from template.")
        
        # Read file content
        with open(config_path, 'r') as f:
            content = f.read()
        # Determine format and parse accordingly
        if config_path.lower().endswith('.json'):
            config = json.loads(content)
        else:
            if yaml is not None:
                config = yaml.safe_load(content)
            else:
                # Simple YAML parser for key: value pairs
                config = {}
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if ':' not in line:
                        continue
                    key, val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    lower_val = val.lower()
                    if lower_val == 'true':
                        config[key] = True
                    elif lower_val == 'false':
                        config[key] = False
                    else:
                        try:
                            if '.' in val:
                                config[key] = float(val)
                            else:
                                config[key] = int(val)
                        except ValueError:
                            config[key] = val
        if not isinstance(config, dict):
            raise ConfigurationError(f"Configuration file must contain a mapping/dict, got {type(config)}")
        # Convert boolean values to lowercase strings
        result: Dict[str, Any] = {}
        for key, value in config.items():
            if isinstance(value, bool):
                result[key] = str(value).lower()
            else:
                result[key] = value
        return result
    except FileNotFoundError as e:
        raise ConfigurationError(f"Configuration file not found: {config_path}") from e
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        raise ConfigurationError(f"Failed to parse configuration file: {e}") from e
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {e}") from e

def validate_config(config: Dict[str, Any]) -> None:
    """Validate that required configuration keys are present."""
    required_keys = [
        'APP_PORT', 'FLASK_DEBUG', 'FLASK_APP', 'APP_ENV',
        'REACT_PORT', 'APP_HOST',
        'POSTGRES_USER', 'POSTGRES_PASSWORD', 'DB_PORT',
        'LOG_MAX_SIZE', 'BACKUP_DEFAULT_DIRECTORY',
        'BACKUP_COMPRESSION_LEVEL', 'BACKUP_RETENTION_COUNT',
        'BACKUP_EXCLUDE_PATTERNS'
    ]
    missing = [key for key in required_keys if key not in config]
    if missing:
        raise ConfigurationError(f"Missing required configuration keys: {', '.join(missing)}")

def substitute_env_variables(config: Any) -> Any:
    """Recursively substitute environment variables in config values."""
    if isinstance(config, dict):
        return {k: substitute_env_variables(v) for k, v in config.items()}
    if isinstance(config, list):
        return [substitute_env_variables(item) for item in config]
    if isinstance(config, str):
        import re
        pattern = re.compile(r'\$\{([^}]+)\}')
        def repl(match: re.Match) -> str:
            return os.environ.get(match.group(1), '')
        return pattern.sub(repl, config)
    return config

def sanitize_key(key: str) -> str:
    """Remove invalid characters from configuration keys."""
    return ''.join(c for c in key if c.isalnum() or c == '_')

def sanitize_path(path: str) -> str:
    """Sanitize file paths by removing '..' segments and duplicates."""
    absolute = path.startswith('/')
    parts = path.split('/')
    new_parts = [p for p in parts if p and p != '..']
    sanitized = '/'.join(new_parts)
    return ('/' if absolute else '') + sanitized

@dataclass
class LLMServiceConfig:
    """LLM service configuration container."""
    enabled: bool
    default_model: str
    models: Dict[str, Dict[str, Any]]
    filtering: Dict[str, Any]
    routing: Dict[str, Any]
    model_lifecycle: Dict[str, Any]  # Add model lifecycle configuration
    ollama: Dict[str, Any]  # Add Ollama configuration
    external_ai: Dict[str, Any]  # Add External AI service configuration
    
    @classmethod
    def process_config(cls, raw_config: Dict) -> 'LLMServiceConfig':
        llm_config = raw_config.get('llm_service', {})
        
        return cls(
            enabled=llm_config.get('enabled', True),
            default_model=llm_config.get('default_model', 'phi3'),
            models=llm_config.get('models', {}),
            filtering=llm_config.get('filtering', {}),
            routing=llm_config.get('routing', {}),
            model_lifecycle=llm_config.get('model_lifecycle', {}),
            ollama=llm_config.get('ollama', {
                'enabled': True,
                'endpoint': 'http://localhost:11434',
                'default_model': 'phi3:mini',
                'models_to_install': ['phi3:mini', 'deepseek-r1:latest'],
                'auto_install': True
            }),
            external_ai=llm_config.get('external_ai', {
                'enabled': True,
                'port': 8091,
                'ollama_endpoint': 'http://localhost:11434'
            })
        )

@dataclass
class DatabaseConfig:
    """Database configuration container."""
    host: str
    port: int
    name: str
    user: str
    password: str
    
    @classmethod
    def process_config(cls, raw_config: Dict) -> 'DatabaseConfig':
        db_config = raw_config.get('database', {})
        
        return cls(
            host=db_config.get('host', 'localhost'),
            port=db_config.get('port', 5432),
            name=db_config.get('name', 'sting_app'),
            user=db_config.get('user', 'postgres'),
            password=db_config.get('password', 'postgres')
        )

# SupertokensConfig removed - deprecated in favor of Kratos authentication

@dataclass
class KratosConfig:
    """Ory Kratos configuration container."""
    public_url: str
    admin_url: str
    cookie_domain: str

    @classmethod
    def process_config(cls, raw_config: Dict[str, Any]) -> 'KratosConfig':
        kr = raw_config.get('kratos', {})
        return cls(
            public_url=kr.get('public_url', 'http://localhost:4433'),
            admin_url=kr.get('admin_url', 'http://localhost:4434'),
            cookie_domain=kr.get('cookie_domain', 'localhost')
        )

class ConfigurationManager:
    """Manages application configuration and secrets."""
    
    _config_cache = {}
    
    def __init__(self, config_file: str, mode: str = 'runtime'):
        
        mode = os.getenv('INIT_MODE', mode)
        logger.info(f"Initializing ConfigurationManager in {mode} mode")
        
        os.environ.setdefault('POSTGRES_USER', 'postgres')
        os.environ.setdefault('POSTGRES_PASSWORD', 'default_password')
        os.environ.setdefault('POSTGRES_DATABASE_NAME', 'sting_app')
        os.environ.setdefault('POSTGRES_HOST', 'db')
        os.environ.setdefault('POSTGRES_PORT', '5432')
        
        self.config_file = config_file
        # Base installation directory (can be overridden via INSTALL_DIR env var)
        self.install_dir = os.environ.get('INSTALL_DIR', '/app')
        # Directory containing configuration files
        self.config_dir = os.path.join(self.install_dir, 'conf')
        # Directory for generated environment files
        self.env_dir = os.path.join(self.install_dir, 'env')
        # Ensure environment directory exists
        os.makedirs(self.env_dir, exist_ok=True)
        self._database_config = None
        self._supertokens_config = None
        self.raw_config = {}
        self.processed_config = {}
        self.mode = mode  # Can be 'runtime', 'build', 'reinstall', 'initialize'
        self.cache_key = f"{config_file}:{mode}"
        self.state_file = os.path.join(self.config_dir, '.config_state')
        
        # Initialize Vault client based on mode
        self.vault_url = os.getenv("VAULT_ADDR", "http://vault:8200")
        self.vault_token = os.environ.get('VAULT_TOKEN', 'dev-only-token')
        self.vault_token = os.environ.get('VAULT_TOKEN') or self.vault_token

        # Always try to read vault token from file (even in bootstrap mode)
        self._read_vault_token_from_file()

        self.client = self._init_vault_client() if self._should_init_vault() else None
        
        # Get STING domain
        self.sting_domain = self._get_sting_domain()

        # Detect platform for Docker networking configuration
        self.platform = self._detect_platform()
        self.docker_host_gateway = self._get_docker_host_gateway()
        logger.info(f"Platform detected: {self.platform}, Docker host gateway: {self.docker_host_gateway}")

    def _read_vault_token_from_file(self):
        """Read vault token from file without connecting to Vault"""
        auto_init_file = os.path.join(self.config_dir, '.vault-auto-init.json')
        token_file = os.path.join(self.config_dir, '.vault_token')

        # Try auto-init file first (created by vault entrypoint)
        if os.path.exists(auto_init_file):
            try:
                with open(auto_init_file, 'r') as f:
                    vault_data = json.load(f)
                    auto_token = vault_data.get('root_token')
                    if auto_token:
                        logger.info(f"Found vault token in {auto_init_file}")
                        self.vault_token = auto_token
                        return
            except Exception as e:
                logger.warning(f"Could not read auto-init token: {e}")

        # Fall back to .vault_token file
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    self.vault_token = f.read().strip()
                    logger.info(f"Found vault token in {token_file}")
                    return
            except Exception as e:
                logger.warning(f"Could not read token file: {e}")

        logger.debug(f"No vault token file found, using default: {self.vault_token}")

    def _should_init_vault(self) -> bool:
        mode_actions = {
            'runtime': True,      # Full initialization
            'build': False,       # Skip vault during builds
            'reinstall': False,   # Skip during reinstall
            'initialize': True,    # Full initialization for first setup
            'bootstrap': False    # Skip during bootstrap
        }
        return mode_actions.get(self.mode, True)

    def _detect_platform(self) -> str:
        """
        Detect the platform STING is running on.
        Returns: 'macos', 'linux', 'wsl2', or 'unknown'
        """
        import platform

        system = platform.system()

        if system == 'Darwin':
            return 'macos'
        elif system == 'Linux':
            # Check if running in WSL2
            try:
                with open('/proc/version', 'r') as f:
                    version_str = f.read().lower()
                    if 'microsoft' in version_str:
                        # Check for WSL2 specifically
                        with open('/proc/sys/kernel/osrelease', 'r') as release:
                            if 'microsoft' in release.read().lower():
                                return 'wsl2'
            except FileNotFoundError:
                pass
            return 'linux'
        else:
            logger.warning(f"Unknown platform: {system}")
            return 'unknown'

    def _get_docker_host_gateway(self) -> str:
        """
        Get the appropriate Docker host gateway address based on platform.

        Returns:
        - macOS: 'host.docker.internal' (Docker Desktop native support)
        - WSL2 with Docker Desktop: 'host.docker.internal'
        - WSL2 native/Linux: 'host-gateway' (will be resolved via extra_hosts)
        """
        if self.platform == 'macos':
            return 'host.docker.internal'
        elif self.platform == 'wsl2':
            # Check if Docker Desktop is installed (docker.exe available)
            import shutil
            if shutil.which('docker.exe'):
                return 'host.docker.internal'
            else:
                # Native Docker in WSL2 - use host-gateway
                return 'host-gateway'
        elif self.platform == 'linux':
            # Native Linux Docker - use host-gateway
            # This will be resolved via extra_hosts in docker-compose.yml
            return 'host-gateway'
        else:
            # Default to host.docker.internal for unknown platforms
            logger.warning(f"Unknown platform {self.platform}, defaulting to host.docker.internal")
            return 'host.docker.internal'

    def _init_vault_client(self) -> Optional[Any]:
        token_file = os.path.join(self.config_dir, '.vault_token')
        init_file = os.path.join(self.config_dir, '.vault_init.json')
        # Check for auto-init script token first (shared via config volume)
        auto_init_file = os.path.join(self.config_dir, '.vault-auto-init.json')
        max_retries = 3
        retry_delay = 10

        # Quick health check first - no delay if vault is already responsive
        try:
            client = hvac.Client(url=self.vault_url)
            if client.sys.is_initialized():
                # Check if Vault is sealed (production mode)
                if client.sys.is_sealed():
                    logger.info("Vault is sealed, attempting to unseal...")
                    if os.path.exists(init_file):
                        with open(init_file, 'r') as f:
                            vault_data = json.load(f)
                            unseal_key = vault_data.get('unseal_key')
                            if unseal_key:
                                client.sys.submit_unseal_key(unseal_key)
                                logger.info("Vault unsealed successfully")

                # Check for auto-init script token first (shared via config volume)
                if os.path.exists(auto_init_file):
                    try:
                        with open(auto_init_file, 'r') as f:
                            vault_data = json.load(f)
                            auto_token = vault_data.get('root_token')
                            if auto_token:
                                logger.info("Found auto-init script token, using it")
                                self.vault_token = auto_token
                                client = hvac.Client(url=self.vault_url, token=self.vault_token)
                                if client.is_authenticated():
                                    logger.info("Vault connection established with auto-init token")
                                    return client
                    except Exception as e:
                        logger.warning(f"Could not read auto-init token: {e}")

                # Fallback to saved token file
                if os.path.exists(token_file):
                    with open(token_file, 'r') as f:
                        self.vault_token = f.read().strip()
                    client = hvac.Client(url=self.vault_url, token=self.vault_token)
                    if client.is_authenticated():
                        logger.info("Vault connection established with saved token")
                        return client
        except Exception:
            # Vault not ready, proceed with retry logic
            logger.info("Vault not immediately available, starting retry sequence")
            pass

        # Only delay if quick check failed
        initial_delay = 5
        time.sleep(initial_delay)

        for attempt in range(max_retries):
            try:
                client = hvac.Client(url=self.vault_url)
                if client.sys.is_initialized():
                    # Check if Vault is sealed (production mode)
                    if client.sys.is_sealed():
                        logger.info("Vault is sealed, attempting to unseal...")
                        if os.path.exists(init_file):
                            with open(init_file, 'r') as f:
                                vault_data = json.load(f)
                                unseal_key = vault_data.get('unseal_key')
                                if unseal_key:
                                    client.sys.submit_unseal_key(unseal_key)
                                    logger.info("Vault unsealed successfully")

                    if os.path.exists(token_file):
                        with open(token_file, 'r') as f:
                            self.vault_token = f.read().strip()
                        client = hvac.Client(url=self.vault_url, token=self.vault_token)
                        if client.is_authenticated():
                            return client
                else:
                    # Initialize Vault (works for both dev and prod modes)
                    result = client.sys.initialize(secret_shares=1, secret_threshold=1)
                    self.vault_token = result['root_token']
                    unseal_key = result['keys'][0] if 'keys' in result else result.get('keys_base64', [None])[0]

                    # Save both token and unseal key
                    vault_data = {
                        'root_token': self.vault_token,
                        'unseal_key': unseal_key,
                        'initialized_at': datetime.now().isoformat()
                    }

                    with open(token_file, 'w') as f:
                        f.write(self.vault_token)

                    # Save complete init data
                    init_file = os.path.join(self.config_dir, '.vault_init.json')
                    with open(init_file, 'w') as f:
                        json.dump(vault_data, f)

                    # Unseal if needed (production mode)
                    if client.sys.is_sealed() and unseal_key:
                        client.sys.submit_unseal_key(unseal_key)

                    # Enable KV v2 secrets engine at 'sting' path
                    vault_client = hvac.Client(url=self.vault_url, token=self.vault_token)
                    try:
                        vault_client.sys.enable_secrets_engine(
                            backend_type='kv',
                            path='sting',
                            options={'version': 2}
                        )
                        logger.info("Enabled KV v2 secrets engine at path 'sting'")
                    except Exception as e:
                        if "already in use" not in str(e):
                            logger.warning(f"Failed to enable KV engine: {e}")

                    return vault_client

                # Development fallback
                if os.getenv('APP_ENV') == 'development':
                    client = hvac.Client(url=self.vault_url, token=self.vault_token)
                    if client.is_authenticated():
                        with open(token_file, 'w') as f:
                            f.write(self.vault_token)
                        return client

                time.sleep(retry_delay)
            except Exception as e:
                logger.warning(f"Vault initialization attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        return None
    
    def _get_sting_domain(self) -> str:
        """Get STING domain from config, file or environment."""
        # Check config.yml first
        if self.raw_config:
            system_config = self.raw_config.get('system', {})
            domain = system_config.get('domain')
            if domain:
                return domain
        
        # Check for domain file
        domain_file = os.path.join(self.install_dir, '.sting_domain')
        if os.path.exists(domain_file):
            try:
                with open(domain_file, 'r') as f:
                    domain = f.read().strip()
                    if domain:
                        return domain
            except Exception:
                pass
        
        # Check environment variable
        if 'STING_DOMAIN' in os.environ:
            return os.environ['STING_DOMAIN']
        
        # Default to localhost
        return 'localhost'

    def _generate_secret(self, length: int = 32, supertokens_safe: bool = False) -> str:
        """Generate a secure secret using proper base64 encoding.
        
        Args:
            length: The length of the secret to generate (in bytes)
            supertokens_safe: Legacy parameter, ignored
        """
        # Generate proper base64-encoded secrets for all uses
        key_bytes = secrets.token_bytes(length)
        return base64.b64encode(key_bytes).decode('utf-8')
    
    def _generate_web_safe_password(self, length: int = 16) -> str:
        """Generate a web-safe password without problematic characters.
        
        Args:
            length: The length of the password to generate
        """
        # Use alphanumeric characters only (no +, /, =, etc.)
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
        
    def _get_secret(self, path: str, key: str, supertokens_safe: bool = False) -> str:
        """Retrieve a secret from Vault with fallback to generation."""
        if self.client:
            try:
                logger.info(f"Attempting to read secret from path: sting/{path}")
                secret = self.client.secrets.kv.v2.read_secret_version(
                    path=f"sting/data/{path}"
                ).get("data", {}).get("data", {}).get(key)
                
                logger.info(f"Secret read status for {path}: {'[EXISTS]' if secret else '[NOT_FOUND]'}")
                
                if secret and supertokens_safe:
                    if all(c in string.ascii_letters + string.digits + "=-" for c in secret):
                        return secret
                elif secret:
                    return secret
                    
            except Exception as e:
                logger.debug(f"Failed to retrieve secret from Vault: {e}")

        # Generate new secret - all secrets now use proper base64 encoding
        new_secret = self._generate_secret(length=32, supertokens_safe=False)
        
        if self.client:
            try:
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=f"sting/{path}",
                    secret={key: new_secret}
                )
                logger.info(f"Created new secret at sting/{path} with key: {key}")
            except Exception as e:
                logger.debug(f"Failed to store secret in Vault: {e}")
        
        return new_secret
    
    def _get_kratos_secret(self, path: str, key: str) -> str:
        """Retrieve a Kratos-compatible secret (32 hex chars) from Vault with fallback to generation."""
        if self.client:
            try:
                logger.info(f"Attempting to read Kratos secret from path: sting/{path}")
                secret = self.client.secrets.kv.v2.read_secret_version(
                    path=f"sting/data/{path}"
                ).get("data", {}).get("data", {}).get(key)
                
                logger.info(f"Kratos secret read status for {path}: {'[EXISTS]' if secret else '[NOT_FOUND]'}")
                
                if secret and len(secret) == 32:
                    return secret
                elif secret:
                    logger.warning(f"Kratos secret {key} has wrong length ({len(secret)}), regenerating")
                    
            except Exception as e:
                logger.debug(f"Failed to read Kratos secret from Vault: {e}")
        
        # Generate 32-character hex secret for Kratos
        new_secret = secrets.token_hex(16)  # 16 bytes = 32 hex chars
        
        if self.client:
            try:
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=f"sting/{path}",
                    secret={key: new_secret}
                )
                logger.info(f"Created new Kratos secret at sting/{path} with key: {key}")
            except Exception as e:
                logger.debug(f"Failed to store Kratos secret in Vault: {e}")
        
        return new_secret

    def load_config(self) -> None:
        """Load raw configuration from YAML or JSON file."""
        try:
            # First check if config exists, create from template if needed
            if not check_config_exists(self.config_file):
                raise ConfigurationError("Failed to create configuration file from template")
            
            # Delegate to top-level loader with YAML/JSON support
            self.raw_config = load_config(self.config_file)
        except ConfigurationError as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def validate_critical_variables(self):
        """Validate that all critical configuration variables are present."""
        critical_vars = [
            'POSTGRES_USER',
            'POSTGRES_PASSWORD',
            'POSTGRES_DB',
            'ST_API_KEY',
            'SUPERTOKENS_URL'
        ]

        missing_vars = [var for var in critical_vars if not self.processed_config.get(var)]
        if missing_vars:
            logger.error(f"Missing critical configuration variables: {', '.join(missing_vars)}")
            raise ValueError(f"Critical configuration missing: {', '.join(missing_vars)}")
        logger.info("All critical variables are present.")

    def _process_database_config(self) -> DatabaseConfig:
        """Process and return database configuration."""
        return DatabaseConfig(
            host=self.processed_config.get('POSTGRES_HOST', 'db'),
            port=int(self.processed_config.get('POSTGRES_PORT', 5432)),
            name=self.processed_config.get('POSTGRES_DB', 'sting_app'),
            user=self.processed_config.get('POSTGRES_USER', 'postgres'),
            password=self.processed_config.get('POSTGRES_PASSWORD', '')
        )

    # _process_supertokens_config removed - deprecated in favor of Kratos

    def _process_llm_service_config(self) -> LLMServiceConfig:
        """Process and return LLM service configuration."""
        return LLMServiceConfig.process_config(self.raw_config)
    
    def _process_profile_service_config(self) -> Dict[str, Any]:
        """Process and return profile service configuration."""
        profile_config = self.raw_config.get('profile_service', {})
        
        return {
            'enabled': profile_config.get('enabled', True),
            'port': profile_config.get('port', 8092),
            'max_file_size': profile_config.get('max_file_size', 52428800),  # 50MB
            'allowed_image_types': profile_config.get('allowed_image_types', [
                'image/jpeg', 'image/png', 'image/webp'
            ]),
            'image_processing': profile_config.get('image_processing', {
                'max_width': 1024,
                'max_height': 1024,
                'quality': 85
            }),
            'features': profile_config.get('features', {
                'profile_pictures': True,
                'profile_extensions': True,
                'activity_logging': True,
                'search': True
            }),
            'privacy': profile_config.get('privacy', {
                'default_visibility': 'private',
                'allow_public_profiles': True
            })
        }

    def invalidate_cache(self):
        """Invalidate the configuration cache."""
        if self.cache_key in self._config_cache:
            del self._config_cache[self.cache_key]
            logger.debug(f"Invalidated cache for {self.cache_key}")
            
    def process_config(self) -> Dict[str, Any]:
        # Load the configuration file if not already loaded
        if not self.raw_config:
            self.load_config()
        
        # Generate Flask secret key if not exists
        flask_secret = self._get_secret('flask', 'secret_key')
        logger.info(f"Generated/Retrieved Flask secret key status: {'[EXISTS]' if flask_secret else '[NOT_FOUND]'}")
        
        # Generate and set database password first
        self.db_password = self._clean_value(self._get_secret('database', 'password', supertokens_safe=False))
        # SuperTokens secrets removed - no longer used (Kratos handles auth)
        # self.api_key = self._clean_value(self._get_secret('supertokens', 'api_key', supertokens_safe=True))
        self.api_key = None  # SuperTokens removed, set to None to prevent AttributeError
        # self.dashboard_api_key = self._clean_value(self._get_secret('supertokens', 'dashboard_api_key', supertokens_safe=True))
        self.dashboard_api_key = None  # SuperTokens removed, set to None to prevent AttributeError
        
        # Generate Honey Reserve encryption master key
        self.honey_reserve_master_key = self._clean_value(self._get_secret('honey_reserve', 'master_key', supertokens_safe=False))

        # Generate STING service API key for inter-service authentication
        self.service_api_key = self._clean_value(self._get_secret('sting/service_auth', 'api_key', supertokens_safe=False))

        # Get Bee service API key for agentic operations
        bee_api_secret = self._get_secret('service/bee-api-key', 'api_key')
        self.bee_service_api_key = self._clean_value(bee_api_secret) if bee_api_secret else None
        if not self.bee_service_api_key:
            logger.warning("Bee service API key not found in Vault - run bootstrap to generate")

        # Get system domain configuration
        system_config = self.raw_config.get('system', {})
        domain = system_config.get('domain', 'localhost')
        protocol = system_config.get('protocol', 'https')
        ports = system_config.get('ports', {})
        frontend_port = ports.get('frontend', 8443)
        api_port = ports.get('api', 5050)
        kratos_port = ports.get('kratos', 4433)
        
        # Build URLs based on domain configuration
        public_url = f"{protocol}://{domain}:{frontend_port}"
        api_url = f"{protocol}://{domain}:{api_port}"
        kratos_public_url = f"{protocol}://{domain}:{kratos_port}"
        kratos_browser_url = kratos_public_url  # Same as public for browser access
        
        # Store domain configuration in environment
        self.processed_config['STING_DOMAIN'] = domain
        self.processed_config['STING_PROTOCOL'] = protocol
        self.processed_config['PUBLIC_URL'] = public_url
        self.processed_config['KRATOS_PUBLIC_URL'] = kratos_public_url
        self.processed_config['KRATOS_BROWSER_URL'] = kratos_browser_url
        
        api_domain = self.raw_config.get('application', {}).get('api_url', api_url)
        ssl_config = self.raw_config.get('application', {}).get('ssl', {})

        # Check cache
        if self.cache_key in self._config_cache:
            logger.debug(f"Using cached configuration for {self.cache_key}")
            self.processed_config = self._config_cache[self.cache_key]
            return self.processed_config

        # State management check
        if os.path.exists(self.state_file) and self.mode != 'initialize':
            logger.info("Found existing configuration state")
            with open(self.state_file, 'r') as f:
                state_data = json.load(f)
                if self._verify_state_validity(state_data):
                    self.processed_config = state_data
                    return self.processed_config

        if not self.raw_config:
            self.load_config()
        
        # Get application config first
        app_config = self.raw_config.get('application', {})

        # Determine LLM models directory (users can override in config.yml)
        models_dir = app_config.get('models_dir')
        if not models_dir:
            models_dir = '${INSTALL_DIR}/models'
        self.processed_config['STING_MODELS_DIR'] = models_dir

        # Build database URL without quotes and with SSL mode disabled
        database_url = f"postgresql://{self._clean_value('postgres')}:{self._clean_value(self.db_password)}@db:5432/sting_app?sslmode=disable"

        # Set all database-related variables
        db_vars = {
            'POSTGRES_USER': 'postgres',
            'POSTGRES_PASSWORD': self._clean_value(self.db_password),
            'POSTGRES_DB': 'sting_app',
            'POSTGRES_HOST': 'db',
            'POSTGRES_PORT': '5432',
            'POSTGRES_HOST_AUTH_METHOD': 'md5',
            'DATABASE_URL': self._clean_value(database_url),
            'LANG': 'en_US.utf8',
            'LC_ALL': 'en_US.utf8'
        }

        # Clean Supertokens database variables
        st_db_vars = {
            'API_KEY': self._clean_value(self.api_key),
            'ST_API_KEY': self._clean_value(self.api_key),
            'ST_DASHBOARD_API_KEY': self._clean_value(self.dashboard_api_key),
            'POSTGRESQL_USER': self._clean_value(db_vars['POSTGRES_USER']),
            'POSTGRESQL_PASSWORD': self._clean_value(self.db_password),
            'POSTGRESQL_DATABASE_NAME': 'sting_app',
            'POSTGRESQL_HOST': 'db',
            'POSTGRESQL_PORT': '5432',
            'DATABASE_URL': self._clean_value(database_url),
            'POSTGRESQL_CONNECTION_URI': self._clean_value(database_url),
            # SuperTokens removed - using Kratos for authentication
            # 'SUPERTOKENS_API_DOMAIN': 'http://localhost:5050',
            # 'SUPERTOKENS_URL': 'http://supertokens:3567',
            # 'SUPERTOKENS_CORS_ORIGINS': 'http://localhost:8443'
        }
        
        self.processed_config.update({
            'SSL_ENABLED': ssl_config.get('enabled', True),
            'SSL_CERT_DIR': ssl_config.get('cert_dir', f"{self.install_dir}/certs"),
            'DOMAIN_NAME': ssl_config.get('domain', 'localhost'),
            'CERTBOT_EMAIL': ssl_config.get('email', 'your-email@example.com')
        })

        # Update processed config
        self.processed_config.update(db_vars)
        self.processed_config.update(st_db_vars)

        # Get HF token from environment, config.yml, or vault (env wins)
        # NOTE: HuggingFace integration is deprecated - these operations are non-fatal
        hf_token = os.environ.get('HF_TOKEN', '')
        if not hf_token:
            hf_token = self.raw_config.get('llm_service', {}).get('huggingface', {}).get('token', '') or ''
        if not hf_token and self.client:
            try:
                hf_token = self._get_secret('huggingface', 'token', False) or ''
            except Exception as e:
                logger.warning(f"Could not read deprecated HuggingFace token from Vault: {e}")
                hf_token = ''

        # Store token in processed config
        self.processed_config['HF_TOKEN'] = hf_token

        # Only store non-empty, non-placeholder tokens in Vault (deprecated, non-fatal)
        if hf_token and self.client and hf_token != "<REDACTED>" and hf_token.strip():
            try:
                self.client.secrets.kv.v2.create_or_update_secret(
                    path="sting/huggingface",
                    secret={"token": hf_token}
                )
            except Exception as e:
                logger.warning(f"Could not store deprecated HuggingFace token in Vault: {e}")

        # Set environment variables
        for key, value in db_vars.items():
            os.environ[key] = self._clean_value(str(value))

        # Process configurations
        db_config = self._process_database_config()
        # st_config removed - Supertokens deprecated in favor of Kratos
        llm_config = self._process_llm_service_config()
        profile_config = self._process_profile_service_config()

        # Add remaining configuration
        self.processed_config.update({
            'APP_ENV': app_config.get('env', 'development'),
            'APP_DEBUG': app_config.get('debug', True),
            'APP_HOST': app_config.get('host', 'localhost'),
            'APP_PORT': app_config.get('port', 5050),
            'APP_URL': api_domain,
            'INSTALL_DIR': self.install_dir,
            'FLASK_APP': 'app.run:app',
            'FLASK_DEBUG': app_config.get('env', 'development'),
            'FLASK_SECRET_KEY': flask_secret,
            'SECRET_KEY': flask_secret,
            'GUNICORN_WORKERS': str(app_config.get('gunicorn_workers', 4)),
            'GUNICORN_TIMEOUT': str(app_config.get('gunicorn_timeout', 120)),
            'DATABASE_URL': self._clean_value(database_url),
            'SQLALCHEMY_DATABASE_URI': self._clean_value(database_url),
            # SuperTokens API keys removed - no longer used
            # 'ST_API_KEY': self._clean_value(self.api_key),
            # 'API_KEY': self._clean_value(self.api_key),
            # 'ST_DASHBOARD_API_KEY': self._clean_value(self.dashboard_api_key),
            # SuperTokens removed - using Kratos for authentication
            # 'SUPERTOKENS_URL': 'http://supertokens:3567',
            # 'SUPERTOKENS_CORS_ORIGINS': 'http://localhost:8443',
            # 'SUPERTOKENS_API_DOMAIN': api_domain,
            'ST_ACCESS_TOKEN_VALIDITY': '3600',
            'ST_REFRESH_TOKEN_VALIDITY': '2592000',
            'REACT_PORT': self.raw_config.get('frontend', {}).get('react', {}).get('port', 8443),
            'HF_TOKEN': hf_token,
            'REACT_APP_API_URL': api_domain,
            # 'REACT_APP_SUPERTOKENS_URL': 'http://localhost:3567',  # Removed - using Kratos
            'REACT_APP_KRATOS_PUBLIC_URL': self.processed_config.get('KRATOS_PUBLIC_URL', kratos_public_url),
            'REACT_APP_KRATOS_BROWSER_URL': self.processed_config.get('KRATOS_BROWSER_URL', kratos_browser_url),
            'NODE_ENV': app_config.get('env', 'development'),
            'VAULT_ADDR': 'http://vault:8200',
            'VAULT_TOKEN': self._clean_value(self.vault_token),
            'HEALTH_CHECK_INTERVAL': self.raw_config.get('monitoring', {}).get('health_checks', {}).get('interval', '30s'),
            'HEALTH_CHECK_TIMEOUT': self.raw_config.get('monitoring', {}).get('health_checks', {}).get('timeout', '10s'),
            'HEALTH_CHECK_RETRIES': str(self.raw_config.get('monitoring', {}).get('health_checks', {}).get('retries', 3)),
            'HEALTH_CHECK_START_PERIOD': self.raw_config.get('monitoring', {}).get('health_checks', {}).get('start_period', '40s'),
            # SuperTokens WebAuthn removed - Kratos handles this natively
            # 'SUPERTOKENS_WEBAUTHN_ENABLED': 'true',
            # 'SUPERTOKENS_WEBAUTHN_RP_ID': '${HOSTNAME:-localhost}',
            # 'SUPERTOKENS_WEBAUTHN_RP_NAME': 'STING',
            # 'SUPERTOKENS_WEBAUTHN_RP_ORIGINS': '["http://localhost:8443", "https://${HOSTNAME:-' +
            #     self.processed_config.get('APP_HOST','your-production-domain.com') +
            #     '}"]'
        })

        # Add LLM service specific ENV vars
        raw_llm_config = self.raw_config.get('llm_service', {})
        gateway_config = raw_llm_config.get('gateway', {})
        models_config = raw_llm_config.get('models', {})

        # Add LLM-specific configuration 
        self.processed_config.update({
            'LLM_SERVICE_ENABLED': str(llm_config.enabled).lower(),
            'LLM_DEFAULT_MODEL': llm_config.default_model,
            'LLM_FILTERING_ENABLED': str(llm_config.filtering.get('toxicity', {}).get('enabled', True)).lower() if hasattr(llm_config, 'filtering') else 'true',
            'LLM_TOXICITY_THRESHOLD': str(llm_config.filtering.get('toxicity', {}).get('threshold', 0.7)) if hasattr(llm_config, 'filtering') else '0.7',
            'LLM_DATA_LEAKAGE_ENABLED': str(llm_config.filtering.get('data_leakage', {}).get('enabled', True)).lower() if hasattr(llm_config, 'filtering') else 'true',
            # Ollama configuration
            'OLLAMA_ENABLED': str(llm_config.ollama.get('enabled', True)).lower(),
            'OLLAMA_ENDPOINT': llm_config.ollama.get('endpoint', 'http://localhost:11434'),
            'OLLAMA_DEFAULT_MODEL': llm_config.ollama.get('default_model', 'phi3:mini'),
            'OLLAMA_MODELS_TO_INSTALL': ','.join(llm_config.ollama.get('models_to_install', ['phi3:mini'])),
            'OLLAMA_AUTO_INSTALL': str(llm_config.ollama.get('auto_install', True)).lower(),
            # External AI service configuration
            'EXTERNAL_AI_ENABLED': str(llm_config.external_ai.get('enabled', True)).lower(),
            'EXTERNAL_AI_PORT': str(llm_config.external_ai.get('port', 8091)),
            'EXTERNAL_AI_OLLAMA_ENDPOINT': llm_config.external_ai.get('ollama_endpoint', 'http://localhost:11434'),
        })
        
        # Add model lifecycle configuration
        lifecycle_config = llm_config.model_lifecycle if hasattr(llm_config, 'model_lifecycle') else {}
        self.processed_config.update({
            'LLM_LAZY_LOADING': str(lifecycle_config.get('lazy_loading', True)).lower(),
            'LLM_IDLE_TIMEOUT': str(lifecycle_config.get('idle_timeout', 30)),
            'LLM_MAX_LOADED_MODELS': str(lifecycle_config.get('max_loaded_models', 2)),
            'LLM_PRELOAD_ON_STARTUP': str(lifecycle_config.get('preload_on_startup', False)).lower(),
            'LLM_DEVELOPMENT_MODE': str(lifecycle_config.get('development_mode', False)).lower(),
        })

        # Generate gateway ENV vars
        self.processed_config.update({
            'LLM_GATEWAY_PORT': str(gateway_config.get('port', 8080)),
            'LLM_GATEWAY_LOG_LEVEL': gateway_config.get('log_level', 'INFO'),
            'LLM_DEFAULT_MODEL': llm_config.default_model,
            'LLM_SERVICE_TIMEOUT': str(gateway_config.get('timeout', 30)),
            'LLM_MAX_RETRIES': str(gateway_config.get('max_retries', 3)),
            'LLM_MODELS_ENABLED': ','.join([
                model for model, config in models_config.items() 
                if config.get('enabled', True)
            ]),
        })

        # Generate model-specific ENV vars
        for model, config in models_config.items():
            if config.get('enabled', True):
                model_env = {
                    f'{model.upper()}_MODEL_PATH': config.get('path', f'/app/models/{model}'),
                    f'{model.upper()}_MAX_TOKENS': str(config.get('max_tokens', 1024)),
                    f'{model.upper()}_TEMPERATURE': str(config.get('temperature', 0.7)),
                }
                self.processed_config.update(model_env)

        # Add Profile service specific ENV vars
        self.processed_config.update({
            'PROFILE_SERVICE_ENABLED': str(profile_config.get('enabled', True)).lower(),
            'PROFILE_SERVICE_PORT': str(profile_config.get('port', 8092)),
            'PROFILE_MAX_FILE_SIZE': str(profile_config.get('max_file_size', 52428800)),
            'PROFILE_ALLOWED_IMAGE_TYPES': ','.join(profile_config.get('allowed_image_types', [])),
            'PROFILE_IMAGE_MAX_WIDTH': str(profile_config.get('image_processing', {}).get('max_width', 1024)),
            'PROFILE_IMAGE_MAX_HEIGHT': str(profile_config.get('image_processing', {}).get('max_height', 1024)),
            'PROFILE_IMAGE_QUALITY': str(profile_config.get('image_processing', {}).get('quality', 85)),
            'PROFILE_FEATURES_PICTURES': str(profile_config.get('features', {}).get('profile_pictures', True)).lower(),
            'PROFILE_FEATURES_EXTENSIONS': str(profile_config.get('features', {}).get('profile_extensions', True)).lower(),
            'PROFILE_FEATURES_ACTIVITY_LOG': str(profile_config.get('features', {}).get('activity_logging', True)).lower(),
            'PROFILE_FEATURES_SEARCH': str(profile_config.get('features', {}).get('search', True)).lower(),
            'PROFILE_DEFAULT_VISIBILITY': profile_config.get('privacy', {}).get('default_visibility', 'private'),
            'PROFILE_ALLOW_PUBLIC': str(profile_config.get('privacy', {}).get('allow_public_profiles', True)).lower(),
        })
        
        # Add Honey Reserve configuration
        honey_reserve_config = self.raw_config.get('honey_reserve', {})
        file_upload_config = honey_reserve_config.get('file_upload', {})
        lifecycle_config = honey_reserve_config.get('lifecycle', {})
        quotas_config = honey_reserve_config.get('quotas', {})
        security_config = honey_reserve_config.get('security', {})
        
        self.processed_config.update({
            'HONEY_RESERVE_ENABLED': str(honey_reserve_config.get('enabled', True)).lower(),
            'HONEY_RESERVE_DEFAULT_QUOTA': str(honey_reserve_config.get('default_quota', 1073741824)),
            'HONEY_RESERVE_MAX_FILE_SIZE': str(file_upload_config.get('max_file_size', 104857600)),
            'HONEY_RESERVE_TEMP_RETENTION_HOURS': str(file_upload_config.get('temp_retention_hours', 48)),
            'HONEY_RESERVE_RATE_LIMIT_MINUTE': str(file_upload_config.get('rate_limit_per_minute', 10)),
            'HONEY_RESERVE_RATE_LIMIT_HOUR': str(file_upload_config.get('rate_limit_per_hour', 100)),
            'HONEY_RESERVE_WARNING_THRESHOLD': str(quotas_config.get('warning_threshold_percent', 90)),
            'HONEY_RESERVE_CRITICAL_THRESHOLD': str(quotas_config.get('critical_threshold_percent', 95)),
            'HONEY_RESERVE_AUTO_CLEANUP': str(quotas_config.get('auto_cleanup_at_percent', 100)),
            'HONEY_RESERVE_ACTIVE_DAYS': str(lifecycle_config.get('active_to_standard_days', 2)),
            'HONEY_RESERVE_STANDARD_DAYS': str(lifecycle_config.get('standard_to_archive_days', 30)),
            'HONEY_RESERVE_ARCHIVE_DAYS': str(lifecycle_config.get('archive_to_deletion_days', 365)),
            'HONEY_RESERVE_AUTO_ARCHIVE': str(lifecycle_config.get('auto_archive_enabled', True)).lower(),
            # Encryption settings
            'HONEY_RESERVE_ENCRYPT_AT_REST': str(security_config.get('encrypt_at_rest', True)).lower(),
            'HONEY_RESERVE_ENCRYPTION_ALGORITHM': security_config.get('encryption_algorithm', 'AES-256-GCM'),
            'HONEY_RESERVE_KEY_DERIVATION': security_config.get('key_derivation', 'HKDF-SHA256'),
            'HONEY_RESERVE_AUDIT_ACCESS': str(security_config.get('audit_all_access', True)).lower(),
            # Master encryption key for file encryption
            'HONEY_RESERVE_MASTER_KEY': self._clean_value(self.honey_reserve_master_key),
            # Service API key for inter-service authentication
            'STING_SERVICE_API_KEY': self._clean_value(self.service_api_key),
        })

        logger.info(f"Config keys present: {list(self.processed_config.keys())}")
        
        # Add debug logging for key values
        logger.info(f"Generated key configuration values:")
        for key in ['POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB', 'POSTGRES_HOST', 'POSTGRES_PORT', 'ST_API_KEY']:
            value = self.processed_config.get(key, 'NOT_SET')
            logger.info(f"  {key}: {'SET' if value and value != 'NOT_SET' else 'NOT_SET'}")
        
        # Cache and save state
        self._config_cache[self.cache_key] = self.processed_config
        self._save_config_state(self.processed_config)
        
        return self.processed_config
    
    def _generate_email_env_vars(self):
        """Generate email configuration environment variables."""
        email_config = self.raw_config.get('email_service', {})
        
        # Determine email mode (development or production)
        email_mode = os.environ.get('EMAIL_MODE', email_config.get('mode', 'development'))
        
        env_vars = {
            'EMAIL_MODE': email_mode
        }
        
        if email_mode == 'development':
            # Development mode - use mailpit
            dev_config = email_config.get('development', {})
            env_vars.update({
                'EMAIL_PROVIDER': 'mailpit',
                'SMTP_HOST': dev_config.get('host', 'mailpit'),
                'SMTP_PORT': str(dev_config.get('port', 1025)),
                'SMTP_USERNAME': '',
                'SMTP_PASSWORD': '',
                'SMTP_FROM': 'noreply@sting.local',
                'SMTP_FROM_NAME': 'STING Platform (Dev)',
                'SMTP_TLS_ENABLED': 'false',
                'SMTP_STARTTLS_ENABLED': 'false',
                'SMTP_SSL_VERIFY': 'false'
            })
            
            # Generate Kratos connection URI for mailpit
            smtp_uri = f"smtp://mailpit:1025/?skip_ssl_verify=true&disable_starttls=true"
            
        else:
            # Production mode - use external SMTP
            prod_config = email_config.get('production', {})
            smtp_config = prod_config.get('smtp', {})
            
            # Get SMTP credentials from environment or config
            smtp_host = os.environ.get('SMTP_HOST', smtp_config.get('host', ''))
            smtp_port = os.environ.get('SMTP_PORT', str(smtp_config.get('port', 587)))
            smtp_username = os.environ.get('SMTP_USERNAME', smtp_config.get('username', ''))
            smtp_password = os.environ.get('SMTP_PASSWORD', smtp_config.get('password', ''))
            smtp_from = os.environ.get('SMTP_FROM', smtp_config.get('from_address', 'noreply@yourdomain.com'))
            smtp_from_name = os.environ.get('SMTP_FROM_NAME', smtp_config.get('from_name', 'STING Platform'))
            smtp_tls = os.environ.get('SMTP_TLS_ENABLED', str(smtp_config.get('tls_enabled', True)).lower())
            smtp_starttls = os.environ.get('SMTP_STARTTLS_ENABLED', str(smtp_config.get('starttls_enabled', True)).lower())
            
            env_vars.update({
                'EMAIL_PROVIDER': prod_config.get('provider', 'smtp'),
                'SMTP_HOST': smtp_host,
                'SMTP_PORT': smtp_port,
                'SMTP_USERNAME': smtp_username,
                'SMTP_PASSWORD': smtp_password,
                'SMTP_FROM': smtp_from,
                'SMTP_FROM_NAME': smtp_from_name,
                'SMTP_TLS_ENABLED': smtp_tls,
                'SMTP_STARTTLS_ENABLED': smtp_starttls,
                'SMTP_SSL_VERIFY': 'true'
            })
            
            # Generate Kratos connection URI for production SMTP
            if smtp_username and smtp_password:
                # Use STARTTLS for standard ports (587, 25)
                if smtp_port in ['587', '25']:
                    smtp_uri = f"smtp://{smtp_username}:{smtp_password}@{smtp_host}:{smtp_port}/?disable_starttls=false"
                # Use direct TLS for secure ports (465)
                elif smtp_port == '465':
                    smtp_uri = f"smtps://{smtp_username}:{smtp_password}@{smtp_host}:{smtp_port}/"
                else:
                    # Default to SMTP with optional STARTTLS
                    smtp_uri = f"smtp://{smtp_username}:{smtp_password}@{smtp_host}:{smtp_port}/"
            else:
                logger.warning("SMTP credentials not configured for production mode")
                smtp_uri = f"smtp://{smtp_host}:{smtp_port}/"
        
        env_vars['COURIER_SMTP_CONNECTION_URI'] = smtp_uri
        env_vars['COURIER_SMTP_FROM_ADDRESS'] = env_vars['SMTP_FROM']
        env_vars['COURIER_SMTP_FROM_NAME'] = env_vars['SMTP_FROM_NAME']
        
        # Store in processed config for other services
        self.processed_config.update(env_vars)
        
        return env_vars

    def _generate_kratos_env_vars(self):
        """Generate environment variables for Kratos from the config file."""
        kratos_config = self.raw_config.get('kratos', {})
        
        # Database connection with proper password and SSL mode disabled
        db_user = self.processed_config.get('POSTGRES_USER', 'postgres')
        db_password = self.processed_config.get('POSTGRES_PASSWORD', 'postgres')
        db_host = self.processed_config.get('POSTGRES_HOST', 'db')
        db_port = self.processed_config.get('POSTGRES_PORT', '5432')
        db_name = self.processed_config.get('POSTGRES_DB', 'sting_app')
        
        dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode=disable"
        
        # Log DSN with redacted password for debugging
        redacted_dsn = dsn.replace(db_password, "********")
        logger.info(f"Generated Kratos database connection string: {redacted_dsn}")
        
        # Basic URLs - use domain configuration if available
        system_config = self.raw_config.get('system', {})
        domain = system_config.get('domain', 'localhost')
        protocol = system_config.get('protocol', 'https')
        ports = system_config.get('ports', {})
        
        public_url = kratos_config.get('public_url', f"{protocol}://{domain}:{ports.get('kratos', 4433)}")
        admin_url = kratos_config.get('admin_url', f"{protocol}://{domain}:4434")
        frontend_url = self.raw_config.get('frontend', {}).get('react', {}).get('api_url', f"{protocol}://{domain}:{ports.get('frontend', 8443)}")
        
        # Self-service configuration
        selfservice = kratos_config.get('selfservice', {})
        default_return_url = selfservice.get('default_return_url', frontend_url)
        login_ui_url = selfservice.get('login', {}).get('ui_url', f"{frontend_url}/login")
        login_lifespan = selfservice.get('login', {}).get('lifespan', '1h')
        registration_ui_url = selfservice.get('registration', {}).get('ui_url', f"{frontend_url}/register")
        registration_lifespan = selfservice.get('registration', {}).get('lifespan', '1h')
        
        # Authentication methods
        methods = kratos_config.get('methods', {})
        
        # WebAuthn (Passkeys)
        # Check for WebAuthn config in deprecated supertokens section first
        supertokens_config = self.raw_config.get('security', {}).get('supertokens', {})
        webauthn_config = supertokens_config.get('webauthn', {})
        
        # If not found, check in methods
        if not webauthn_config:
            webauthn_config = methods.get('webauthn', {})
            
        webauthn_enabled = str(webauthn_config.get('enabled', True)).lower()
        
        # Get RP ID and expand HOSTNAME variable or use STING domain
        rp_id_raw = webauthn_config.get('rp_id', 'localhost')
        # Use STING domain first, then fall back to HOSTNAME (but avoid Docker container IDs)
        docker_hostname = os.environ.get('HOSTNAME', '')
        # If HOSTNAME looks like a Docker container ID (hex string), use STING domain instead
        if docker_hostname and len(docker_hostname) == 12 and all(c in '0123456789abcdef' for c in docker_hostname):
            hostname = self.sting_domain
        else:
            hostname = docker_hostname or self.sting_domain
        
        # If the rp_id contains a variable placeholder, replace it
        if '${' in rp_id_raw:
            webauthn_rp_id = rp_id_raw.replace('${HOSTNAME:-localhost}', hostname)
        else:
            # Use STING domain if rp_id is just 'localhost'
            webauthn_rp_id = self.sting_domain if rp_id_raw == 'localhost' else rp_id_raw
        
        webauthn_display_name = webauthn_config.get('rp_name', 'STING Authentication')
        
        # Handle rp_origins array
        rp_origins = webauthn_config.get('rp_origins', [])
        if rp_origins:
            # Expand HOSTNAME in origins
            webauthn_origins = []
            for origin in rp_origins:
                expanded_origin = origin.replace('${HOSTNAME:-your-production-domain.com}', hostname)
                webauthn_origins.append(expanded_origin)
            webauthn_origin = webauthn_origins[0] if webauthn_origins else frontend_url
        else:
            # Use STING domain for origin if not specified
            default_origin = f"https://{self.sting_domain}:8443" if self.sting_domain != 'localhost' else frontend_url
            webauthn_origin = webauthn_config.get('origin', default_origin)
        
        # Password authentication
        password_enabled = str(methods.get('password', {}).get('enabled', True)).lower()
        
        # OIDC configuration
        oidc_enabled = str(methods.get('oidc', {}).get('enabled', False)).lower()
        oidc_providers = methods.get('oidc', {}).get('providers', [])
        
        # Generate email configuration first
        email_env_vars = self._generate_email_env_vars()
        
        # Use the generated email connection URI
        courier_smtp_uri = email_env_vars.get('COURIER_SMTP_CONNECTION_URI', 'smtp://mailpit:1025/?skip_ssl_verify=true')
        
        # Session secret from vault or generated
        session_secret = self.processed_config.get('FLASK_SECRET_KEY', self._get_secret('kratos', 'session_secret'))
        
        # Cookie secrets - generate and persist in Vault (Kratos needs exactly 32 hex chars)
        cookies_secret = self._get_kratos_secret('kratos', 'cookies_secret')
        cipher_secret = self._get_kratos_secret('kratos', 'cipher_secret')
        
        # Cookie configuration - use STING domain if available
        session_cookie_name = 'ory_kratos_session'
        session_cookie_domain = self.sting_domain if self.sting_domain != 'localhost' else domain
        
        # Convert all the config values into environment variables
        env_vars = {
            # Database connection
            'DSN': dsn,
            
            # Core URLs
            'KRATOS_PUBLIC_URL': public_url,
            'KRATOS_ADMIN_URL': admin_url,
            'FRONTEND_URL': frontend_url,
            
            # Identity schema location
            'IDENTITY_DEFAULT_SCHEMA_URL': 'file:///etc/config/kratos/identity.schema.json',
            
            # Session secret
            'SESSION_SECRET': session_secret,
            
            # Self-service flows
            'DEFAULT_RETURN_URL': default_return_url,
            'LOGIN_UI_URL': login_ui_url,
            'LOGIN_LIFESPAN': login_lifespan,
            'REGISTRATION_UI_URL': registration_ui_url,
            'REGISTRATION_LIFESPAN': registration_lifespan,
            
            # WebAuthn (Passkeys) configuration
            'WEBAUTHN_ENABLED': webauthn_enabled,
            'WEBAUTHN_RP_ID': webauthn_rp_id,
            'WEBAUTHN_RP_DISPLAY_NAME': webauthn_display_name,
            'WEBAUTHN_RP_ORIGIN': webauthn_origin,
            
            # Password authentication
            'PASSWORD_ENABLED': password_enabled,
            
            # OIDC configuration
            'OIDC_ENABLED': oidc_enabled,
            
            # Cookie secrets
            'COOKIES_SECRET': cookies_secret,
            'CIPHER_SECRET': cipher_secret,
            
            # Session cookie configuration
            'SESSION_COOKIE_NAME': session_cookie_name,
            'SESSION_COOKIE_DOMAIN': session_cookie_domain
        }
        
        # Add OIDC provider configuration if enabled
        if oidc_enabled == 'true' and oidc_providers:
            for idx, provider in enumerate(oidc_providers):
                prefix = f'OIDC_PROVIDER_{idx}'
                env_vars[f'{prefix}_ID'] = provider.get('id', '')
                env_vars[f'{prefix}_PROVIDER'] = provider.get('provider', '')
                env_vars[f'{prefix}_CLIENT_ID'] = provider.get('client_id', '')
                env_vars[f'{prefix}_CLIENT_SECRET'] = provider.get('client_secret', '')
                env_vars[f'{prefix}_SCOPES'] = ','.join(provider.get('scopes', []))
        
        # Add SMTP configuration
        env_vars['SMTP_CONNECTION_URI'] = courier_smtp_uri
        env_vars['COURIER_SMTP_FROM_ADDRESS'] = email_env_vars.get('COURIER_SMTP_FROM_ADDRESS', 'noreply@sting.local')
        env_vars['COURIER_SMTP_FROM_NAME'] = email_env_vars.get('COURIER_SMTP_FROM_NAME', 'STING Platform')
        
        # Add WebAuthn values to processed_config for app.env generation
        self.processed_config['WEBAUTHN_RP_ID'] = webauthn_rp_id
        self.processed_config['WEBAUTHN_RP_NAME'] = webauthn_display_name
        self.processed_config['WEBAUTHN_RP_ORIGIN'] = webauthn_origin
        
        # Add VAULT_TOKEN to processed_config for app.env generation
        self.processed_config['VAULT_TOKEN'] = self._clean_value(self.vault_token)
        
        return env_vars

    def _generate_knowledge_env_vars(self):
        """Generate environment variables for Knowledge Service from the config file."""
        knowledge_config = self.raw_config.get('knowledge_service', {})
        honey_reserve_config = self.raw_config.get('honey_reserve', {})
        
        # Basic service configuration
        port = str(knowledge_config.get('port', 8090))
        host = knowledge_config.get('host', '0.0.0.0')
        
        # ChromaDB configuration
        chroma_config = knowledge_config.get('chroma', {})
        chroma_url = chroma_config.get('url', 'http://chroma:8000')
        chroma_enabled = str(chroma_config.get('enabled', True)).lower()
        
        # Authentication configuration
        auth_config = knowledge_config.get('authentication', {})
        dev_mode = str(auth_config.get('development_mode', False)).lower()
        kratos_public_url = auth_config.get('kratos_public_url', 'https://kratos:4433')
        kratos_admin_url = auth_config.get('kratos_admin_url', 'https://kratos:4434')
        
        # Access control configuration
        access_control = knowledge_config.get('access_control', {})
        creation_roles = ','.join(access_control.get('creation_roles', ['admin', 'support', 'moderator', 'editor']))
        team_based_access = str(access_control.get('team_based_access', True)).lower()
        
        # Honey jar configuration
        honey_jars = knowledge_config.get('honey_jars', {})
        max_per_user = str(honey_jars.get('max_per_user', 0))
        max_document_size = str(honey_jars.get('max_document_size', 52428800))
        allowed_document_types = ','.join(honey_jars.get('allowed_document_types', [
            'text/plain', 'text/markdown', 'text/html', 'application/pdf', 
            'application/json', 'application/xml', 'text/csv'
        ]))
        
        # Document processing
        processing = honey_jars.get('processing', {})
        chunk_size = str(processing.get('chunk_size', 1000))
        chunk_overlap = str(processing.get('chunk_overlap', 200))
        chunking_strategy = processing.get('chunking_strategy', 'sentence')
        
        # Search configuration
        search_config = knowledge_config.get('search', {})
        max_results = str(search_config.get('max_results', 20))
        min_relevance_score = str(search_config.get('min_relevance_score', 0.3))
        semantic_search = str(search_config.get('semantic_search', True)).lower()
        keyword_fallback = str(search_config.get('keyword_fallback', True)).lower()
        
        # Bee integration
        bee_config = knowledge_config.get('bee_integration', {})
        bee_enabled = str(bee_config.get('enabled', True)).lower()
        max_context_items = str(bee_config.get('max_context_items', 5))
        context_threshold = str(bee_config.get('context_threshold', 0.5))
        
        # Audit configuration
        audit_config = knowledge_config.get('audit', {})
        audit_enabled = str(audit_config.get('enabled', True)).lower()
        retention_days = str(audit_config.get('retention_days', 90))
        
        # Honey Reserve configuration
        file_upload_config = honey_reserve_config.get('file_upload', {})
        lifecycle_config = honey_reserve_config.get('lifecycle', {})
        quotas_config = honey_reserve_config.get('quotas', {})
        
        # Convert all the config values into environment variables
        env_vars = {
            # Basic service configuration
            'KNOWLEDGE_PORT': port,
            'KNOWLEDGE_HOST': host,
            'PYTHONPATH': '/app',
            
            # ChromaDB configuration
            'CHROMA_URL': chroma_url,
            'CHROMA_ENABLED': chroma_enabled,
            
            # Authentication configuration
            'KNOWLEDGE_DEV_MODE': dev_mode,
            'KRATOS_PUBLIC_URL': kratos_public_url,
            'KRATOS_ADMIN_URL': kratos_admin_url,
            
            # Access control
            'KNOWLEDGE_CREATION_ROLES': creation_roles,
            'KNOWLEDGE_TEAM_BASED_ACCESS': team_based_access,
            
            # Honey jar configuration
            'KNOWLEDGE_MAX_PER_USER': max_per_user,
            'KNOWLEDGE_MAX_DOCUMENT_SIZE': max_document_size,
            'KNOWLEDGE_ALLOWED_DOCUMENT_TYPES': allowed_document_types,
            
            # Document processing
            'KNOWLEDGE_CHUNK_SIZE': chunk_size,
            'KNOWLEDGE_CHUNK_OVERLAP': chunk_overlap,
            'KNOWLEDGE_CHUNKING_STRATEGY': chunking_strategy,
            
            # Search configuration
            'KNOWLEDGE_MAX_RESULTS': max_results,
            'KNOWLEDGE_MIN_RELEVANCE_SCORE': min_relevance_score,
            'KNOWLEDGE_SEMANTIC_SEARCH': semantic_search,
            'KNOWLEDGE_KEYWORD_FALLBACK': keyword_fallback,
            
            # Bee integration
            'KNOWLEDGE_BEE_ENABLED': bee_enabled,
            'KNOWLEDGE_MAX_CONTEXT_ITEMS': max_context_items,
            'KNOWLEDGE_CONTEXT_THRESHOLD': context_threshold,
            
            # Audit configuration
            'KNOWLEDGE_AUDIT_ENABLED': audit_enabled,
            'KNOWLEDGE_AUDIT_RETENTION_DAYS': retention_days,
            
            # Honey Reserve configuration
            'HONEY_RESERVE_ENABLED': str(honey_reserve_config.get('enabled', True)).lower(),
            'HONEY_RESERVE_DEFAULT_QUOTA': str(honey_reserve_config.get('default_quota', 1073741824)),
            'HONEY_RESERVE_MAX_FILE_SIZE': str(file_upload_config.get('max_file_size', 104857600)),
            'HONEY_RESERVE_TEMP_RETENTION_HOURS': str(file_upload_config.get('temp_retention_hours', 48)),
            'HONEY_RESERVE_WARNING_THRESHOLD': str(quotas_config.get('warning_threshold_percent', 90)),
            'HONEY_RESERVE_CRITICAL_THRESHOLD': str(quotas_config.get('critical_threshold_percent', 95)),
            'HONEY_RESERVE_RATE_LIMIT_MINUTE': str(file_upload_config.get('rate_limit_per_minute', 10)),
            'HONEY_RESERVE_RATE_LIMIT_HOUR': str(file_upload_config.get('rate_limit_per_hour', 100))
        }
        
        # Add development user configuration if in dev mode
        if dev_mode == 'true':
            dev_user = auth_config.get('development_user', {})
            env_vars.update({
                'KNOWLEDGE_DEV_USER_ID': dev_user.get('id', 'dev-user'),
                'KNOWLEDGE_DEV_USER_EMAIL': dev_user.get('email', 'dev@sting.local'),
                'KNOWLEDGE_DEV_USER_ROLE': dev_user.get('role', 'admin'),
                'KNOWLEDGE_DEV_USER_FIRST_NAME': dev_user.get('name', {}).get('first', 'Dev'),
                'KNOWLEDGE_DEV_USER_LAST_NAME': dev_user.get('name', {}).get('last', 'User')
            })
        
        return env_vars

    def _generate_observability_env_vars(self):
        """Generate environment variables for Observability services (Grafana, Loki, Promtail)."""
        try:
            # Read observability config directly from root config
            observability_config = self.raw_config.get('observability', {})
            
            # Check if observability is enabled
            obs_enabled = str(observability_config.get('enabled', False)).lower()
            
            logger.info(f"Generating observability.env with enabled={obs_enabled}")
            
            # Grafana configuration
            grafana_config = observability_config.get('grafana', {})
            grafana_enabled = str(grafana_config.get('enabled', False)).lower()
            grafana_port = str(grafana_config.get('port', 3000))
            
            # Generate Grafana admin credentials and store in Vault
            grafana_admin_user = grafana_config.get('admin_user', 'admin')
            
            # Use web-safe password for Grafana admin (avoid +, /, = characters)
            try:
                grafana_admin_password = self._get_secret('observability', 'grafana_admin_password')
                # If the password has problematic characters, regenerate
                if any(c in grafana_admin_password for c in ['+', '/', '=']):
                    grafana_admin_password = self._generate_web_safe_password(16)
            except:
                grafana_admin_password = self._generate_web_safe_password(16)
            
            try:
                grafana_secret_key = self._get_secret('observability', 'grafana_secret_key')
            except:
                grafana_secret_key = self._generate_web_safe_password(32)
            
            # Loki configuration
            loki_config = observability_config.get('loki', {})
            loki_enabled = str(loki_config.get('enabled', False)).lower()
            loki_port = str(loki_config.get('port', 3100))
            
            # Loki storage and performance settings
            storage_config = loki_config.get('storage', {})
            retention_period = storage_config.get('retention_period', '168h')
            compaction_interval = storage_config.get('compaction_interval', '10m')
            
            limits_config = loki_config.get('limits', {})
            max_line_size = limits_config.get('max_line_size', '256KB')
            max_streams_per_user = str(limits_config.get('max_streams_per_user', 5000))
            ingestion_rate_mb = str(limits_config.get('ingestion_rate_mb', 4))
            ingestion_burst_size_mb = str(limits_config.get('ingestion_burst_size_mb', 6))
            
            # Promtail configuration
            promtail_config = observability_config.get('promtail', {})
            promtail_enabled = str(promtail_config.get('enabled', False)).lower()
            promtail_port = str(promtail_config.get('port', 9080))
            
            # Sanitization settings
            sanitization_config = promtail_config.get('sanitization', {})
            sanitization_enabled = str(sanitization_config.get('enabled', True)).lower()
            
            # Vault integration settings
            vault_integration = sanitization_config.get('vault_integration', {})
            vault_references_enabled = str(vault_integration.get('enabled', True)).lower()
            vault_reference_format = vault_integration.get('reference_format', '<VAULT_REF:sting/data/{category}/{field}>')
            
            # Log forwarding configuration
            log_forwarding = observability_config.get('log_forwarding', {})
            log_forwarding_enabled = str(log_forwarding.get('enabled', False)).lower()
            
            # Alerting configuration
            alerting_config = observability_config.get('alerting', {})
            alerting_enabled = str(alerting_config.get('enabled', False)).lower()
            
            # Environment variables for all observability services
            env_vars = {
                # Global observability settings
                'OBSERVABILITY_ENABLED': obs_enabled,
                
                # Grafana environment variables
                'GRAFANA_ENABLED': grafana_enabled,
                'GRAFANA_PORT': grafana_port,
                'GRAFANA_ADMIN_USER': grafana_admin_user,
                'GRAFANA_ADMIN_PASSWORD': grafana_admin_password,
                'GRAFANA_SECRET_KEY': grafana_secret_key,
                'GF_SECURITY_ADMIN_USER': grafana_admin_user,
                'GF_SECURITY_ADMIN_PASSWORD': grafana_admin_password,
                'GF_SECURITY_SECRET_KEY': grafana_secret_key,
                'GF_SECURITY_ALLOW_EMBEDDING': 'false',
                'GF_SECURITY_COOKIE_SECURE': 'true',
                'GF_SECURITY_COOKIE_SAMESITE': 'strict',
                'GF_SECURITY_STRICT_TRANSPORT_SECURITY': 'true',
                'GF_ANALYTICS_REPORTING_ENABLED': 'false',
                'GF_ANALYTICS_CHECK_FOR_UPDATES': 'false',
                'GF_SNAPSHOTS_EXTERNAL_ENABLED': 'false',
                
                # Loki environment variables
                'LOKI_ENABLED': loki_enabled,
                'LOKI_PORT': loki_port,
                'LOKI_RETENTION_PERIOD': retention_period,
                'LOKI_COMPACTION_INTERVAL': compaction_interval,
                'LOKI_MAX_LINE_SIZE': max_line_size,
                'LOKI_MAX_STREAMS_PER_USER': max_streams_per_user,
                'LOKI_INGESTION_RATE_MB': ingestion_rate_mb,
                'LOKI_INGESTION_BURST_SIZE_MB': ingestion_burst_size_mb,
                
                # Promtail environment variables
                'PROMTAIL_ENABLED': promtail_enabled,
                'PROMTAIL_PORT': promtail_port,
                'PROMTAIL_SANITIZATION_ENABLED': sanitization_enabled,
                'PROMTAIL_VAULT_REFERENCES_ENABLED': vault_references_enabled,
                'PROMTAIL_VAULT_REFERENCE_FORMAT': vault_reference_format,
                
                # Log forwarding
                'LOG_FORWARDING_ENABLED': log_forwarding_enabled,
                
                # Alerting
                'ALERTING_ENABLED': alerting_enabled,
                
                # Service URLs for inter-service communication
                'LOKI_URL': 'http://loki:3100',
                'GRAFANA_URL': 'http://grafana:3000',
                'PROMTAIL_URL': 'http://promtail:9080',
                
                # Health check configuration
                'HEALTH_CHECK_INTERVAL': '30s',
                'HEALTH_CHECK_TIMEOUT': '10s',
                'HEALTH_CHECK_RETRIES': '5',
                'HEALTH_CHECK_START_PERIOD': '60s'
            }
        
            # Add external log forwarding targets if configured
            targets = log_forwarding.get('targets', [])
            for i, target in enumerate(targets):
                if target.get('enabled', False):
                    prefix = f'LOG_FORWARD_TARGET_{i}_'
                    env_vars.update({
                        f'{prefix}NAME': target.get('name', f'target_{i}'),
                        f'{prefix}TYPE': target.get('type', 'syslog'),
                        f'{prefix}ENDPOINT': target.get('endpoint', ''),
                        f'{prefix}FORMAT': target.get('format', 'json'),
                        f'{prefix}ENABLED': 'true'
                    })
            
            # Add alerting channels if configured
            channels = alerting_config.get('channels', [])
            for i, channel in enumerate(channels):
                prefix = f'ALERT_CHANNEL_{i}_'
                env_vars.update({
                    f'{prefix}NAME': channel.get('name', f'channel_{i}'),
                    f'{prefix}TYPE': channel.get('type', 'webhook'),
                    f'{prefix}URL': channel.get('url', ''),
                    f'{prefix}RECIPIENTS': ','.join(channel.get('recipients', []))
                })
            
            return env_vars
        except Exception as e:
            logger.error(f"Failed to generate observability environment variables: {e}")
            # Return minimal fallback configuration to ensure observability.env is created
            return {
                'OBSERVABILITY_ENABLED': 'false',
                'GRAFANA_ENABLED': 'false',
                'GRAFANA_ADMIN_USER': 'admin',
                'GRAFANA_ADMIN_PASSWORD': 'admin',
                'GRAFANA_SECRET_KEY': 'changeme',
                'LOKI_ENABLED': 'false',
                'PROMTAIL_ENABLED': 'false',
                'LOG_FORWARDING_ENABLED': 'false',
                'ALERTING_ENABLED': 'false'
            }

    def _generate_headscale_env_vars(self):
        """Generate headscale environment variables from configuration"""
        try:
            headscale_config = self.raw_config.get('headscale', {})
            server_config = headscale_config.get('server', {})
            database_config = headscale_config.get('database', {})
            security_config = headscale_config.get('security', {})
            support_config = headscale_config.get('support_sessions', {})
            community_config = support_config.get('community', {})
            professional_config = support_config.get('professional', {})
            logging_config = headscale_config.get('logging', {})

            logger.info(f"Generating headscale.env with enabled={headscale_config.get('enabled', False)}")
            
            return {
                # Core headscale configuration
                'HEADSCALE_DATABASE_TYPE': database_config.get('type', 'sqlite'),
                'HEADSCALE_DATABASE_SQLITE_PATH': database_config.get('path', '/var/lib/headscale/db.sqlite'),
                'HEADSCALE_EPHEMERAL_NODE_INACTIVITY_TIMEOUT': security_config.get('ephemeral_node_timeout', '30m'),
                'HEADSCALE_BASE_DOMAIN': server_config.get('base_domain', 'support.sting.local'),
                'HEADSCALE_LISTEN_ADDR': server_config.get('listen_addr', '0.0.0.0:8070'),
                'HEADSCALE_METRICS_LISTEN_ADDR': f"0.0.0.0:{server_config.get('metrics_port', 9090)}",
                
                # Security settings
                'HEADSCALE_RANDOMIZE_CLIENT_PORT': str(security_config.get('randomize_client_port', True)).lower(),
                'HEADSCALE_ENABLE_ROUTING': str(security_config.get('enable_routing', False)).lower(),
                
                # Support session configuration
                'HEADSCALE_COMMUNITY_BUNDLE_DURATION': community_config.get('bundle_download_duration', '48h'),
                'HEADSCALE_COMMUNITY_SECURE_LINK': str(community_config.get('secure_link_enabled', True)).lower(),
                'HEADSCALE_COMMUNITY_LIVE_TUNNEL': str(community_config.get('live_tunnel_enabled', False)).lower(),
                'HEADSCALE_PROFESSIONAL_TUNNEL_DURATION': professional_config.get('tunnel_duration', '4h'),
                'HEADSCALE_PROFESSIONAL_BUNDLE_DURATION': professional_config.get('bundle_download_duration', '7d'),
                'HEADSCALE_PROFESSIONAL_LIVE_TUNNEL': str(professional_config.get('live_tunnel_enabled', True)).lower(),
                
                # Logging configuration
                'HEADSCALE_LOG_LEVEL': logging_config.get('level', 'info'),
                'HEADSCALE_LOG_FILE': logging_config.get('file', '/var/log/headscale/headscale.log'),
                
                # Policy file
                'HEADSCALE_POLICY_PATH': headscale_config.get('policy_file', '/etc/headscale/policy.hujson'),
                
                # Service metadata
                'HEADSCALE_ENABLED': str(headscale_config.get('enabled', True)).lower(),
                'HEADSCALE_PORT': str(server_config.get('port', 8070)),
                'HEADSCALE_METRICS_PORT': str(server_config.get('metrics_port', 9090))
            }

        except Exception as e:
            logger.error(f"Failed to generate headscale environment variables: {e}")
            # Return minimal fallback configuration
            return {
                'HEADSCALE_ENABLED': 'false',
                'HEADSCALE_DATABASE_TYPE': 'sqlite',
                'HEADSCALE_DATABASE_SQLITE_PATH': '/var/lib/headscale/db.sqlite',
                'HEADSCALE_EPHEMERAL_NODE_INACTIVITY_TIMEOUT': '30m',
                'HEADSCALE_BASE_DOMAIN': 'support.sting.local',
                'HEADSCALE_LISTEN_ADDR': '0.0.0.0:8070',
                'HEADSCALE_METRICS_LISTEN_ADDR': '0.0.0.0:9090',
                'HEADSCALE_LOG_LEVEL': 'info',
                'HEADSCALE_LOG_FILE': '/var/log/headscale/headscale.log',
                'HEADSCALE_POLICY_PATH': '/etc/headscale/policy.hujson',
                'HEADSCALE_PORT': '8070',
                'HEADSCALE_METRICS_PORT': '9090'
            }

    def _generate_nectar_worker_env_vars(self):
        """Generate nectar-worker environment variables from configuration"""
        try:
            nectar_config = self.raw_config.get('nectar_worker', {})
            ollama_config = nectar_config.get('ollama', {})
            limits_config = nectar_config.get('limits', {})
            performance_config = nectar_config.get('performance', {})
            security_config = nectar_config.get('security', {})
            logging_config = nectar_config.get('logging', {})

            logger.info(f"Generating nectar-worker.env with enabled={nectar_config.get('enabled', False)}")

            # Generate STING API key for internal service communication
            sting_api_key = self._generate_secret(32)

            # Get Ollama URL with platform-aware host gateway
            # Try nectar_worker.ollama.url first, fall back to llm_service.ollama.endpoint
            ollama_url = ollama_config.get('url') or self.raw_config.get('llm_service', {}).get('ollama', {}).get('endpoint', 'http://localhost:11434')
            # Replace host.docker.internal with platform-specific gateway
            ollama_url = ollama_url.replace('host.docker.internal', self.docker_host_gateway)

            return {
                # STING API Configuration
                'STING_API_URL': 'https://app:5050',
                'STING_API_KEY': sting_api_key,

                # Ollama Configuration
                'OLLAMA_URL': ollama_url,
                'DEFAULT_MODEL': ollama_config.get('default_model', 'phi3:mini'),
                'OLLAMA_KEEP_ALIVE': ollama_config.get('keep_alive', '30m'),

                # Nectar Bot Limits
                'MAX_HONEY_JARS_PER_BOT': str(limits_config.get('max_honey_jars_per_bot', 3)),
                'MAX_CONTEXT_TOKENS': str(limits_config.get('max_context_tokens', 2000)),
                'MAX_CONCURRENT_REQUESTS': str(limits_config.get('max_concurrent_requests', 10)),
                'REQUEST_TIMEOUT': str(limits_config.get('request_timeout', 60)),

                # Performance & Caching
                'HONEY_JAR_CACHE_SIZE': str(performance_config.get('honey_jar_cache_size', 100)),
                'HONEY_JAR_CACHE_TTL': str(performance_config.get('honey_jar_cache_ttl', 300)),
                'BOT_CONFIG_CACHE_TTL': str(performance_config.get('bot_config_cache_ttl', 300)),

                # Logging
                'LOG_LEVEL': logging_config.get('level', 'INFO'),

                # Service metadata
                'NECTAR_WORKER_ENABLED': str(nectar_config.get('enabled', True)).lower()
            }

        except Exception as e:
            logger.error(f"Failed to generate nectar-worker environment variables: {e}")
            # Return minimal fallback configuration
            fallback_api_key = self._generate_secret(32)

            return {
                'STING_API_URL': 'https://app:5050',
                'STING_API_KEY': fallback_api_key,
                'OLLAMA_URL': 'http://ollama:11434',
                'DEFAULT_MODEL': 'phi3:mini',
                'OLLAMA_KEEP_ALIVE': '30m',
                'MAX_HONEY_JARS_PER_BOT': '3',
                'MAX_CONTEXT_TOKENS': '2000',
                'MAX_CONCURRENT_REQUESTS': '10',
                'REQUEST_TIMEOUT': '60',
                'HONEY_JAR_CACHE_SIZE': '100',
                'HONEY_JAR_CACHE_TTL': '300',
                'BOT_CONFIG_CACHE_TTL': '300',
                'LOG_LEVEL': 'INFO',
                'NECTAR_WORKER_ENABLED': 'true'
            }

    def _generate_email_secrets(self):
        email_secrets = {
            'smtp_password': self._generate_secret(),
            'smtp_username': 'your-email@gmail.com'
        }
        self.write_secret('email/credentials', email_secrets)
    
    def _verify_state_validity(self, state_data: Dict) -> bool:
        """Verify if stored state is valid and complete"""
        required_keys = [
            'POSTGRES_USER',
            'POSTGRES_PASSWORD',
            'ST_API_KEY',
            'VAULT_TOKEN'
        ]
        return all(key in state_data for key in required_keys)

    def _save_config_state(self, config: Dict) -> None:
        """Save configuration state to persistent storage"""
        with open(self.state_file, 'w') as f:
            json.dump(config, f)
        os.chmod(self.state_file, 0o600)  # Secure file permissions

    def _clean_value(self, value: str) -> str:
        """Clean configuration values by removing quotes."""
        if isinstance(value, str):
            return value.replace('"', '').replace("'", '')
        return str(value)

            
    def generate_env_file(self, env_path: Optional[str] = None, service_specific: bool = True) -> None:
        """Generate service-specific .env files with processed configuration."""
        # ALWAYS remove any supertokens.env file if it exists (no conditions)
        st_env_files = [
            os.path.join(self.env_dir, "supertokens.env"),
            os.path.join(self.config_dir, "supertokens.env"),
            os.path.join(os.path.expanduser("~/.sting-ce/env"), "supertokens.env")
        ]
        
        for st_file in st_env_files:
            if os.path.exists(st_file):
                try:
                    os.remove(st_file)
                    logger.info(f"Removed deprecated supertokens.env file at {st_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove supertokens.env at {st_file}: {e}")
                    
        # Create .no_supertokens marker file to prevent future generation
        no_st_file = os.path.join(self.env_dir, ".no_supertokens")
        try:
            with open(no_st_file, 'w') as f:
                f.write("# This file prevents creation of supertokens.env\n")
                f.write(f"# Created: {datetime.datetime.now().isoformat()}\n")
            logger.info(f"Created .no_supertokens guard file at {no_st_file}")
        except Exception as e:
            logger.warning(f"Failed to create .no_supertokens guard file: {e}")
            
        # Debug logging before processing
        logger.info("===== BEFORE ENV GENERATION =====")
        for key in ['POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB', 'HF_TOKEN']:
            logger.info(f"{key}: {'[SET]' if self.processed_config.get(key) else '[EMPTY]'}")
        
        self.processed_config = {}  # Clear existing config
        self.process_config()  # Generate fresh configuration
        
        # Ensure HF_TOKEN is in processed_config (add this check)
        logger.info(f"HF_TOKEN in processed_config: {self.processed_config.get('HF_TOKEN', 'NOT_FOUND')}")
        
        sensitive_keys = {
            'API_KEY', 'ST_API_KEY', 'ST_DASHBOARD_API_KEY',
            'POSTGRESQL_PASSWORD', 'POSTGRES_PASSWORD',
            'DATABASE_URL', 'POSTGRESQL_CONNECTION_URI',
            'SQLALCHEMY_DATABASE_URI',
            'POSTGRESQL_USER', 'POSTGRES_USER',
            'POSTGRESQL_DATABASE_NAME', 'POSTGRES_DB',
            'POSTGRESQL_HOST', 'POSTGRES_HOST',
            'POSTGRESQL_PORT', 'POSTGRES_PORT',
            'FLASK_SECRET_KEY', 'SECRET_KEY',
            'HF_TOKEN'  # Add HF_TOKEN to sensitive keys
        }

        if service_specific:
            # Define service-specific configurations
            service_configs = {
                'app.env': {
                    'APP_ENV', 'FLASK_DEBUG', 'DATABASE_URL', 'ST_API_KEY',
                    'SQLALCHEMY_DATABASE_URI', 'FLASK_APP', 'APP_PORT', 'API_URL',
                    'FLASK_SECRET_KEY','SECRET_KEY', 'SUPERTOKENS_URL', 'SUPERTOKENS_API_DOMAIN',
                    'WEBAUTHN_RP_ID', 'WEBAUTHN_RP_NAME', 'WEBAUTHN_RP_ORIGIN',
                    'HONEY_RESERVE_ENABLED', 'HONEY_RESERVE_DEFAULT_QUOTA', 'HONEY_RESERVE_MAX_FILE_SIZE',
                    'HONEY_RESERVE_TEMP_RETENTION_HOURS', 'HONEY_RESERVE_WARNING_THRESHOLD', 
                    'HONEY_RESERVE_CRITICAL_THRESHOLD', 'HONEY_RESERVE_RATE_LIMIT_MINUTE',
                    'HONEY_RESERVE_RATE_LIMIT_HOUR', 'HONEY_RESERVE_ENCRYPT_AT_REST',
                    'HONEY_RESERVE_MASTER_KEY', 'HONEY_RESERVE_ENCRYPTION_ALGORITHM',
                    'HONEY_RESERVE_KEY_DERIVATION', 'HONEY_RESERVE_AUDIT_ACCESS',
                    'VAULT_TOKEN'
                },
                'db.env': {
                    'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB',
                    'POSTGRES_HOST', 'POSTGRES_PORT'
                },
                'vault.env': {
                    'VAULT_TOKEN', 'VAULT_ADDR', 'VAULT_API_ADDR'
                },
                'frontend.env': {
                    'REACT_APP_API_URL', 'REACT_APP_SUPERTOKENS_URL',
                    'REACT_APP_KRATOS_PUBLIC_URL', 'REACT_APP_KRATOS_BROWSER_URL',
                    'NODE_ENV', 'REACT_PORT', 'PUBLIC_URL'
                },
                'llm-gateway.env': {
                    'PORT': self.processed_config.get('LLM_GATEWAY_PORT', '8080'),
                    'LOG_LEVEL': self.processed_config.get('LLM_GATEWAY_LOG_LEVEL', 'INFO'),
                    'DEFAULT_MODEL': self.processed_config.get('LLM_DEFAULT_MODEL', 'llama3'),
                    'HF_TOKEN': self.processed_config.get('HF_TOKEN', ''),
                    'OLLAMA_HOST': self.raw_config.get('llm_service', {}).get('ollama', {}).get('endpoint', 'http://localhost:11434'),
                    'EXTERNAL_AI_HOST': 'http://host.docker.internal:8091'
                },
                'chatbot.env': {
                    'PORT': '8081',
                    'BEE_PORT': '8888',
                    'HOST': '0.0.0.0',
                    'LOG_LEVEL': 'INFO',
                    'CHATBOT_NAME': self.raw_config.get('chatbot', {}).get('name', 'Bee'),
                    'CHATBOT_MODEL': self.raw_config.get('chatbot', {}).get('model', 'phi3'),
                    'CHATBOT_CONTEXT_WINDOW': str(self.raw_config.get('chatbot', {}).get('context_window', 10)),
                    'CHATBOT_SYSTEM_PROMPT': self.raw_config.get('chatbot', {}).get('default_system_prompt', 'You are Bee, a helpful and friendly assistant for the STING platform.'),
                    'CHATBOT_TOOLS_ENABLED': 'true',
                    'CHATBOT_ALLOWED_TOOLS': 'search,summarize,analyze',
                    'CHATBOT_REQUIRE_AUTH': 'true',
                    'CHATBOT_LOG_CONVERSATIONS': 'true',
                    'CHATBOT_CONTENT_FILTER_LEVEL': 'strict',
                    'LLM_GATEWAY_URL': 'http://llm-gateway:8080',
                    'NATIVE_LLM_URL': 'http://host.docker.internal:8086',
                    'BEE_MESSAGING_SERVICE_ENABLED': 'true',
                    'MESSAGING_SERVICE_URL': 'http://messaging:8889',
                    'BEE_SENTIMENT_ENABLED': 'true',
                    'BEE_ENCRYPTION_ENABLED': 'true',
                    'BEE_TOOLS_ENABLED': 'true',
                    'KRATOS_PUBLIC_URL': 'https://kratos:4433',
                    'KRATOS_ADMIN_URL': 'https://kratos:4434',
                    'BEE_HOST': '0.0.0.0',
                    'KNOWLEDGE_SERVICE_URL': 'http://knowledge:8090',
                    'KNOWLEDGE_ENABLED': 'true',
                    'STING_SERVICE_API_KEY': self.processed_config.get('STING_SERVICE_API_KEY', ''),
                    'BEE_SERVICE_API_KEY': self.bee_service_api_key or '',  # Bee's service API key for agentic operations
                    # Conversation management settings
                    'BEE_CONVERSATION_MAX_TOKENS': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('max_tokens', 4096)),
                    'BEE_CONVERSATION_MAX_MESSAGES': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('max_messages', 50)),
                    'BEE_CONVERSATION_TOKEN_BUFFER_PERCENT': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('token_buffer_percent', 20)),
                    'BEE_CONVERSATION_PERSISTENCE_ENABLED': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('persistence_enabled', True)).lower(),
                    'BEE_CONVERSATION_SESSION_TIMEOUT_HOURS': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('session_timeout_hours', 24)),
                    'BEE_CONVERSATION_ARCHIVE_AFTER_DAYS': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('archive_after_days', 30)),
                    'BEE_CONVERSATION_CLEANUP_INTERVAL_HOURS': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('cleanup_interval_hours', 1)),
                    'BEE_CONVERSATION_SUMMARIZATION_ENABLED': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('summarization_enabled', True)).lower(),
                    'BEE_CONVERSATION_SUMMARIZE_AFTER_MESSAGES': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('summarize_after_messages', 20)),
                    'BEE_CONVERSATION_SUMMARY_MAX_TOKENS': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('summary_max_tokens', 200)),
                    'BEE_CONVERSATION_SUMMARY_MODEL': self.raw_config.get('chatbot', {}).get('conversation', {}).get('summary_model', 'phi3:mini'),
                    'BEE_CONVERSATION_PRUNING_STRATEGY': self.raw_config.get('chatbot', {}).get('conversation', {}).get('pruning_strategy', 'sliding_window'),
                    'BEE_CONVERSATION_KEEP_SYSTEM_MESSAGES': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('keep_system_messages', True)).lower(),
                    'BEE_CONVERSATION_KEEP_RECENT_MESSAGES': str(self.raw_config.get('chatbot', {}).get('conversation', {}).get('keep_recent_messages', 10))
                },
                'kratos.env': self._generate_kratos_env_vars(),
                'knowledge.env': self._generate_knowledge_env_vars(),
                'profile.env': {
                    'PROFILE_SERVICE_ENABLED': 'true',
                    'PROFILE_SERVICE_PORT': '8092',
                    'FLASK_ENV': self.processed_config.get('APP_ENV', 'development'),
                    'FLASK_SECRET_KEY': self.processed_config.get('FLASK_SECRET_KEY', ''),
                    'DATABASE_URL': self.processed_config.get('DATABASE_URL', ''),
                    'VAULT_ADDR': 'http://vault:8200',
                    'VAULT_TOKEN': self.processed_config.get('VAULT_TOKEN', 'root'),
                    'KRATOS_PUBLIC_URL': 'https://localhost:4433',
                    'KRATOS_ADMIN_URL': 'http://kratos:4434',
                    'PROFILE_MAX_FILE_SIZE': '52428800',
                    'PROFILE_ALLOWED_IMAGE_TYPES': 'image/jpeg,image/png,image/webp',
                    'PROFILE_IMAGE_MAX_WIDTH': '1024',
                    'PROFILE_IMAGE_MAX_HEIGHT': '1024',
                    'PROFILE_IMAGE_QUALITY': '85',
                    'PROFILE_FEATURES_PICTURES': 'true',
                    'PROFILE_FEATURES_EXTENSIONS': 'true',
                    'PROFILE_FEATURES_ACTIVITY_LOG': 'true',
                    'PROFILE_FEATURES_SEARCH': 'true',
                    'PROFILE_DEFAULT_VISIBILITY': 'private',
                    'PROFILE_ALLOW_PUBLIC': 'true',
                    'HEALTH_CHECK_INTERVAL': '30s',
                    'HEALTH_CHECK_TIMEOUT': '10s',
                    'HEALTH_CHECK_RETRIES': '5',
                    'HEALTH_CHECK_START_PERIOD': '60s'
                },
                'messaging.env': {
                    'MESSAGING_PORT': '8889',
                    'MESSAGING_HOST': '0.0.0.0',
                    'MESSAGING_ENCRYPTION_ENABLED': 'true',
                    'MESSAGING_QUEUE_ENABLED': 'true',
                    'MESSAGING_NOTIFICATIONS_ENABLED': 'true',
                    'MESSAGING_STORAGE_BACKEND': 'postgresql',
                    'DATABASE_URL': self.processed_config.get('DATABASE_URL', ''),
                    'PYTHONPATH': '/app'
                },
                'external-ai.env': {
                    'EXTERNAL_AI_HOST': '0.0.0.0',
                    'EXTERNAL_AI_PORT': self.raw_config.get('llm_service', {}).get('external_ai', {}).get('port', '8091'),
                    'OLLAMA_BASE_URL': self.raw_config.get('llm_service', {}).get('ollama', {}).get('endpoint', 'http://localhost:11434'),
                    'REDIS_HOST': 'redis',
                    'REDIS_PORT': '6379',
                    'REDIS_LLM_DB': '1',
                    'LLM_MAX_QUEUE_SIZE': '1000',
                    'LLM_REQUEST_TIMEOUT': '300',
                    'LLM_MAX_RETRIES': '3',
                    'LLM_QUEUE_POLL_INTERVAL': '0.1',
                    'CORS_ORIGINS': 'https://localhost:3000,http://localhost:3000,https://localhost:3010,http://localhost:3010',
                    'LOG_LEVEL': 'INFO',
                    'BEE_SERVICE_API_KEY': self.bee_service_api_key or '',  # Service API key for report generation
                    'STING_API_URL': 'https://app:5050'  # For API calls back to main app
                },
                'observability.env': self._generate_observability_env_vars(),
                'headscale.env': self._generate_headscale_env_vars(),
                'nectar-worker.env': self._generate_nectar_worker_env_vars()
                # SUPERTOKENS IS COMPLETELY REMOVED - DO NOT UNCOMMENT
                # DO NOT ADD ANY SUPERTOKENS ENV FILES HERE
            }
            
            # Generate service-specific env files in both config and env directories
            for filename, config in service_configs.items():
                # Paths for config_dir and env_dir
                paths = [
                    os.path.join(self.config_dir, filename),
                    os.path.join(self.env_dir, filename)
                ]
                for service_env_path in paths:
                    # Skip any supertokens.env files
                    if "supertokens.env" in service_env_path:
                        logger.warning(f"Skipping deprecated {service_env_path}, SuperTokens is no longer used")
                        continue
                        
                    logger.info(f"Generating {filename} at {service_env_path}")
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(service_env_path), exist_ok=True)
                    with open(service_env_path, 'w', opener=lambda path, flags: os.open(path, flags, 0o600)) as f:
                        # Config-based writing for services
                        if isinstance(config, dict):
                            items = config.items()
                        else:
                            items = ((key, self.processed_config.get(key, '')) for key in config)
                        for key, value in items:
                            if key in sensitive_keys:
                                f.write(f'{key}={value}\n')
                            else:
                                f.write(f'{key}="{str(value)}"\n')
        else:
            # Generate single combined .env file
            env_path = env_path or os.path.join(self.config_dir, '.env')
            logger.info(f"Generating combined .env file at {env_path}")
        
            with open(env_path, 'w', opener=lambda path, flags: os.open(path, flags, 0o600)) as f:
                for key, value in sorted(self.processed_config.items()):
                    if key in sensitive_keys:
                        f.write(f'{key}={str(value)}\n')
                    else:
                        if isinstance(value, bool):
                            value = str(value).lower()
                        elif isinstance(value, (list, dict)):
                            value = json.dumps(value)
                        elif value is None:
                            value = ''
                        f.write(f'{key}="{str(value)}"\n')
                        
        # Debug logging after processing
        logger.info("===== AFTER ENV GENERATION =====")
        for key in ['POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB', 'HF_TOKEN']:
            logger.info(f"{key}: {'[SET]' if self.processed_config.get(key) else '[EMPTY]'}")
        # Generate a concrete Kratos YAML configuration based on environment variables
        kratos_conf_dir = os.path.join(self.config_dir, 'kratos')
        os.makedirs(kratos_conf_dir, exist_ok=True)

        kratos_path = os.path.join(kratos_conf_dir, 'kratos.yml')

        # Check if kratos.yml already exists (generated by configure_hostname during installation)
        # If it exists, don't overwrite it - it has the correct hostname configuration
        if os.path.exists(kratos_path):
            logger.info(f"Kratos config already exists at {kratos_path}, skipping generation (preserves hostname config)")
            return True

        # If kratos.yml doesn't exist, generate it from template
        # Try kratos.yml.template first (preferred - supports hostname substitution)
        template_kratos_path = os.path.join(self.config_dir, 'kratos', 'kratos.yml.template')
        full_kratos_path = os.path.join(self.config_dir, 'kratos', 'kratos.yml')
        minimal_kratos_path = os.path.join(os.path.dirname(self.config_dir), 'kratos', 'minimal.kratos.yml')

        # Prefer template, then full config, then minimal as fallback
        if os.path.exists(template_kratos_path):
            template_path = template_kratos_path
            template_type = "template"
        elif os.path.exists(full_kratos_path):
            template_path = full_kratos_path
            template_type = "full"
        else:
            template_path = minimal_kratos_path
            template_type = "minimal"

        if os.path.exists(template_path):
            try:
                # Read template content
                with open(template_path, 'r') as src:
                    content = src.read()

                # If using template, substitute hostname
                if template_type == "template":
                    # Get hostname from environment or use localhost as fallback
                    sting_hostname = os.environ.get('STING_HOSTNAME', 'localhost')
                    content = content.replace('__STING_HOSTNAME__', sting_hostname)
                    logger.info(f"Generated Kratos config from template with hostname: {sting_hostname}")

                # Write to destination
                with open(kratos_path, 'w') as dest:
                    dest.write(content)

                os.chmod(kratos_path, 0o600)
                logger.info(f"Copied Kratos {template_type} config from {template_path} to {kratos_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to copy Kratos template: {e}")
                # Fall back to generating config
        else:
            logger.warning(f"No Kratos template found at {template_path}, falling back to generated config")
            return False
        
        # Fallback: Generate a simple config that uses environment variables
        kratos_config = {
            'version': 'v0.8.2-alpha.1',
            'dsn': '${DSN}',
            'log': {
                'level': 'info'
            },
            'serve': {
                'public': {
                    'base_url': '${KRATOS_PUBLIC_URL}',
                    'cors': {
                        'enabled': True,
                        'allowed_origins': [
                            'http://localhost:8443',
                            'https://localhost:8443'
                        ],
                        'allowed_methods': [
                            'GET',
                            'POST',
                            'OPTIONS'
                        ],
                        'allowed_headers': ['*'],
                        'allow_credentials': True
                    }
                },
                'admin': {
                    'base_url': '${KRATOS_ADMIN_URL}'
                }
            },
            'identity': {
                'schemas': [{
                    'id': 'default',
                    'url': '${IDENTITY_DEFAULT_SCHEMA_URL}'
                }]
            },
            'selfservice': {
                'default_browser_return_url': '${DEFAULT_RETURN_URL}',
                'flows': {
                    'login': {
                        'ui_url': '${LOGIN_UI_URL}',
                        'lifespan': '${LOGIN_LIFESPAN}'
                    },
                    'registration': {
                        'ui_url': '${REGISTRATION_UI_URL}',
                        'lifespan': '${REGISTRATION_LIFESPAN}'
                    }
                },
                'methods': {
                    'password': {
                        'enabled': True
                    },
                    'webauthn': {
                        'enabled': True,
                        'config': {
                            'rp': {
                                'id': '${WEBAUTHN_RP_ID}',
                                'display_name': '${WEBAUTHN_RP_DISPLAY_NAME}',
                                'origin': '${WEBAUTHN_RP_ORIGIN}'
                            }
                        }
                    }
                }
            },
            'courier': {
                'smtp': {
                    'connection_uri': '${SMTP_CONNECTION_URI}'
                }
            }
        }
        kratos_path = os.path.join(kratos_conf_dir, 'kratos.yml')
        try:
            # Dump YAML for Kratos
            with open(kratos_path, 'w') as f:
                yaml.safe_dump(kratos_config, f)
            os.chmod(kratos_path, 0o600)
            logger.info(f"Generated Kratos config at {kratos_path}")
        except Exception as e:
            logger.error(f"Failed to generate Kratos config: {e}")

    def _refresh_vault_token(self):
        """Refresh Vault token if needed"""
        if self.client and self.client.is_authenticated():
            try:
                self.client.auth.token.renew_self()
                return True
            except Exception:
                return False
        return False

    def generate_service_configs(self) -> Dict[str, Dict[str, Any]]:
        """Generate service-specific configurations."""
        if not self.processed_config:
            self.process_config()
        
        return {
            'supertokens': {
                'environment': {
                    'POSTGRESQL_CONNECTION_URI': self.processed_config['DATABASE_URL'],
                    'API_KEY': self.processed_config['ST_API_KEY'],
                    'DASHBOARD_API_KEY': self.processed_config.get('ST_DASHBOARD_API_KEY', ''),
                }
            },
            'app': {
                'environment': {
                    'APP_ENV': self.processed_config['APP_ENV'],
                    'FLASK_DEBUG': str(self.processed_config['APP_DEBUG']).lower(),
                    'DATABASE_URL': self.processed_config['DATABASE_URL'],
                    'ST_API_KEY': self.processed_config['ST_API_KEY'],
                }
            },
            'frontend': {
                'environment': {
                    'NODE_ENV': self.processed_config['APP_ENV'],
                    'REACT_APP_API_URL': self.processed_config['REACT_APP_API_URL'],
                    'REACT_APP_SUPERTOKENS_URL': self.processed_config['REACT_APP_SUPERTOKENS_URL'],
                }
            }
        }


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='STING Configuration Manager')
    parser.add_argument('config_file', help='Path to configuration YAML file')
    parser.add_argument('--env-file', help='Path to output .env file')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--mode', default=os.getenv('INIT_MODE', 'runtime'),
                       choices=['runtime', 'build', 'reinstall', 'initialize', 'bootstrap'],
                       help='Configuration initialization mode')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        manager = ConfigurationManager(args.config_file, mode=args.mode)
        manager.process_config()
        manager.generate_env_file(args.env_file)
        logger.info("Configuration processing completed successfully")
        return 0
    except Exception as e:
        logger.error(f"Configuration processing failed: {e}")
        if args.debug:
            logger.exception("Detailed error information:")
        return 1

if __name__ == '__main__':
    sys.exit(main())
    
