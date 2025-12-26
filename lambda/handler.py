"""
AWS Lambda Handler for Cian Parser
Entry point for Lambda function
"""

import json
import logging
import traceback
from typing import Dict, Any

from lambda_parser import LambdaCianParser

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point

    Event format (API Gateway):
    {
        "body": "{\"url\": \"https://spb.cian.ru/sale/flat/123456/\"}"
    }

    Or direct invocation:
    {
        "url": "https://spb.cian.ru/sale/flat/123456/"
    }

    Returns:
        API Gateway response with parsed property data
    """
    logger.info(f"Lambda invoked with event: {json.dumps(event)[:500]}")

    try:
        # Parse request body
        if 'body' in event:
            # API Gateway request
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            # Direct Lambda invocation
            body = event

        url = body.get('url')
        if not url:
            return _error_response(400, "Missing 'url' parameter")

        # Validate URL
        if not _validate_cian_url(url):
            return _error_response(400, f"Invalid Cian URL: {url}")

        # Parse property
        logger.info(f"Parsing URL: {url}")

        parser = LambdaCianParser(timeout=45, use_proxy=True)
        result = parser.parse_detail_page(url)

        logger.info(f"Successfully parsed: {result.get('title', 'Unknown')[:50]}")

        return _success_response(result)

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return _error_response(400, f"Invalid JSON: {str(e)}")

    except Exception as e:
        logger.error(f"Parsing error: {e}")
        logger.error(traceback.format_exc())
        return _error_response(500, f"Parsing failed: {str(e)}")


def _validate_cian_url(url: str) -> bool:
    """Validate that URL is a valid Cian property URL"""
    if not url:
        return False

    # Must be cian.ru domain
    if 'cian.ru' not in url:
        return False

    # Must be a property page (sale/flat, sale/suburban, rent/flat, etc.)
    valid_paths = ['/sale/flat/', '/rent/flat/', '/sale/suburban/', '/rent/suburban/']
    return any(path in url for path in valid_paths)


def _success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create successful API Gateway response"""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Api-Key',
        },
        'body': json.dumps({
            'success': True,
            'data': data
        }, ensure_ascii=False)
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': False,
            'error': message
        }, ensure_ascii=False)
    }


# For local testing
if __name__ == '__main__':
    # Test event
    test_event = {
        'body': json.dumps({
            'url': 'https://spb.cian.ru/sale/flat/316296015/'
        })
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2, ensure_ascii=False))
