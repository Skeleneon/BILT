import email
import imaplib
import os
from email.header import decode_header
from pypdf import PdfReader

# Configuration (Use GitHub Secrets for these!)
EMAIL = os.environ.get("MAIL_USER")
PASSWORD = os.environ.get("MAIL_PASS")
IMAP_SERVER = "imap.gmail.com"  # Change if using Outlook/Yahoo

"""
def clean_filename(filename):
  return "".join(c for c in filename if c.isalnum() or c.- in ("._- ")).rstrip()
"""

def process_emails():
  # Connect to email server
  mail = imaplib.IMAP4_SSL(IMAP_SERVER)
  mail.login(EMAIL, PASSWORD)
  mail.select("inbox")

  # Search for specific emails (e.g., Unread emails from a sender or with a subject)
  # Modify search criteria as needed: '(UNSEEN FROM "sender@example.com")'
  status, messages = mail.search(None, '(UNSEEN SUBJECT "PDF Report")')

  if status != "OK":
    print("No matching emails found.")
    return

  os.makedirs("extracted_texts", exist_ok=True)
  os.makedirs("downloaded_pdfs", exist_ok=True)

  for num in messages[0].split():
    status, msg_data = mail.fetch(num, "(RFC822)")
    if status != "OK":
      continue

    for response_part in msg_data:
      if isinstance(response_part, tuple):
        msg = email.message_from_bytes(response_part[1])
        subject = decode_header(msg["Subject"])[0][0]
        if isinstance(subject, bytes):
          subject = subject.decode(
              decode_header(msg["Subject"])[0][1] or "utf-8"
          )

        print(f"Processing email: {subject}")

        # Walk through email parts to find attachments
        for part in msg.walk():
          if part.get_content_maintype() == "multipart":
            continue
          if part.get("Content-Disposition") is None:
            continue

          filename = part.get_filename()
          if filename:
            decoded_header = decode_header(filename)[0]
            if isinstance(decoded_header[0], bytes):
              filename = decoded_header[0].decode(
                  decoded_header[1] or "utf-8"
              )
            else:
              filename = decoded_header[0]

            if filename.lower().endswith(".pdf"):
              safe_name = clean_filename(filename)
              pdf_path = os.path.join("downloaded_pdfs", safe_name)

              # Save PDF attachment
              with open(pdf_path, "wb") as f:
                f.write(part.get_payload(decode=True))
              print(f"Downloaded: {safe_name}")

              # Convert PDF to Text
              reader = PdfReader(pdf_path)
              text_content = ""
              for page in reader.pages:
                text_content += page.extract_text() or ""

              txt_filename = os.path.splitext(safe_name)[0] + ".txt"
              txt_path = os.path.join("extracted_texts", txt_filename)

              with open(txt_path, "w", encoding="utf-8") as txt_file:
                txt_file.write(text_content)
              print(f"Converted to text: {txt_filename}")

    # Optional: Mark email as read so it isn't processed twice next time
    mail.store(num, "+FLAGS", "\\Seen")

  mail.logout()


if __name__ == "__main__":
  process_emails()