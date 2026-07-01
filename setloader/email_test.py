# email_test.py
import argparse
import sys
from mailer import send_email_with_attachment  # uses your existing function

def main():
    p = argparse.ArgumentParser(description="Send a test email (with optional attachments).")
    p.add_argument("--to", required=True, help="Recipient email address")
    p.add_argument("--subject", default="SetLoader test email", help="Subject")
    p.add_argument("--body", default="This is a test email from SetLoader.", help="Body text")
    p.add_argument("--attach", action="append", default=[], help="Path to file to attach (repeatable)")
    args = p.parse_args()

    try:
        # Your send_email_with_attachment can accept a list of paths
        send_email_with_attachment(
            to_addr=args.to,
            subject=args.subject,
            body=args.body,
            attachments=args.attach or None,
        )
        print("✅ Email sent.")
    except Exception as e:
        print(f"❌ Email failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()