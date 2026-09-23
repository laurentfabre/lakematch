"""Run only behind Databricks Apps ingress with explicit injected resources."""
import os

from .settings import require


def main():
    from .app import create_deployed_app
    import uvicorn
    port = os.environ.get('DATABRICKS_APP_PORT', '')
    require(port.isascii() and port.isdigit() and 1 <= int(port) <= 65535,
            'An injected app port is required')
    uvicorn.run(create_deployed_app(), host='0.0.0.0', port=int(port), workers=1)


if __name__ == '__main__':
    main()
