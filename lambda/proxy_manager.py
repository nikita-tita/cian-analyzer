"""
Proxy Manager for AWS Lambda
Gets Decodo proxy credentials from AWS Secrets Manager or environment variables
"""

import os
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Cache for secrets (Lambda container reuse optimization)
_cached_credentials: Optional[Dict] = None


def get_proxy_config() -> Dict:
    """
    Get Decodo proxy configuration

    Priority:
    1. AWS Secrets Manager (production)
    2. Environment variables (development/testing)

    Returns:
        Dict with proxy configuration
    """
    global _cached_credentials

    if _cached_credentials:
        return _cached_credentials

    # Try AWS Secrets Manager first
    secret_name = os.environ.get('PROXY_SECRET_NAME', 'decodo/proxy-prod')

    try:
        import boto3
        from botocore.exceptions import ClientError

        client = boto3.client('secretsmanager', region_name='eu-central-1')
        response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])

        _cached_credentials = {
            'host': secret.get('host', 'ru.decodo.com'),
            'port': int(secret.get('port', 40000)),
            'username': secret['username'],
            'password': secret['password'],
            'protocol': secret.get('protocol', 'socks5')
        }

        logger.info(f"Loaded proxy credentials from Secrets Manager: {secret_name}")
        return _cached_credentials

    except Exception as e:
        logger.warning(f"Failed to get secret from Secrets Manager: {e}")

    # Fallback to environment variables
    username = os.environ.get('PROXY_USER')
    password = os.environ.get('PROXY_PASS')

    if username and password:
        _cached_credentials = {
            'host': os.environ.get('PROXY_HOST', 'ru.decodo.com'),
            'port': int(os.environ.get('PROXY_PORT', '40000')),
            'username': username,
            'password': password,
            'protocol': os.environ.get('PROXY_PROTOCOL', 'socks5')
        }
        logger.info("Loaded proxy credentials from environment variables")
        return _cached_credentials

    raise ValueError("No proxy credentials found in Secrets Manager or environment")


def get_proxy_url() -> str:
    """
    Get full proxy URL for httpx

    Returns:
        Proxy URL in format: socks5://user:pass@host:port
    """
    config = get_proxy_config()
    return f"{config['protocol']}://{config['username']}:{config['password']}@{config['host']}:{config['port']}"


def clear_cache():
    """Clear cached credentials (for testing)"""
    global _cached_credentials
    _cached_credentials = None
