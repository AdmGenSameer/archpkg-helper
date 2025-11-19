import argparse
from archpkg.security import SecurityDB

db = SecurityDB()

parser= argparse.ArgumentParser()
subparsers= parser.add_subparsers(dest="command")

install_parser= subparsers.add_parser("install")
install_parser.add_argument("package")

report_parser= subparsers.add_parser("report")
report_parser.add_argument("package", help="Package to report as suspicious")
report_parser.add_argument("--reason", default="Suspicious package")

update_parser= subparsers.add_parser("update-security-db")

args=parser.parse_args()

if args.command == "install":
    status= db.check_package(args.package)
    if status=="blocked":
        print(f"{args.package} is blocked (unsafe)")
    elif status=="safe":
        print(f"{args.package} is verified and safe")
    else:
        print(f"{args.package} is not verified")
        confirm= input("Do you want to contribute? [y/N]")
        if confirm.lower() == "y":
            pass
        else:
            print("Installation aborted.")
elif args.command =="report":
    db.report_package(args.package, args.reason)
    print(f"Reported {args.package} as suspicious")
elif args.command=="update-security-db":
    db.update_security_db()
