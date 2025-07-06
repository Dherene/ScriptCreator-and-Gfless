import argparse

from license_manager import generate_license, extend_license


parser = argparse.ArgumentParser(description="License management")
subparsers = parser.add_subparsers(dest="cmd")

create_p = subparsers.add_parser("create", help="create a new license")
create_p.add_argument("days", type=int, help="validity in days")

extend_p = subparsers.add_parser("extend", help="extend an existing license")
extend_p.add_argument("key", help="license key")
extend_p.add_argument("days", type=int, help="new validity from now in days")

args = parser.parse_args()

if args.cmd == "create":
    key = generate_license(args.days)
    print(key)
elif args.cmd == "extend":
    extend_license(args.key, args.days)
    print("extended")
else:
    parser.print_help()
