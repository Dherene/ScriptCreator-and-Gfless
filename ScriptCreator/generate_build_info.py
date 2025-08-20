import sys
from datetime import datetime, timedelta
from license_manager import generate_license

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 30
KEY_ARG = sys.argv[2] if len(sys.argv) > 2 else None
key = generate_license(DAYS, KEY_ARG, reset=True)
expires = (datetime.now() + timedelta(days=DAYS)).date().isoformat()
with open('build_info.py', 'w') as f:
    f.write('# Auto-generated build information\n')
    f.write(f"BUILD_EXPIRATION = \"{expires}\"\n")
    f.write(f"BUILD_LICENSE_KEY = \"{key}\"\n")
print('License key:', key)