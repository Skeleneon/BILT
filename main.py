import email
import imaplib
import os
from email.header import decode_header
from pypdf import PdfReader
from dotenv import load_dotenv
import re
import requests

load_dotenv()

# Configuration (Use GitHub Secrets for these!)
EMAIL = os.environ.get("MAIL_USER")
PASSWORD = os.environ.get("MAIL_PASS")

cookies={
  "d": os.environ.get("SLACK_D"),
  "d-s": os.environ.get("SLACK_DS")
}

 
IMAP_SERVER = "imap.gmail.com" 

def clean_filename(filename):
  return ("".join(c for c in filename if c.isalnum() or ("._- ") in c).rstrip()).rstrip(".pdf")+".pdf"


def process_emails():
  mail = imaplib.IMAP4_SSL(IMAP_SERVER)
  mail.login(EMAIL, PASSWORD)
  mail.select('"Slack Emails"')
  print("Connected to mailbox.")

  # Search for specific emails (e.g., Unread emails from a sender or with a subject)
  # Modify search criteria as needed: '(UNSEEN FROM "sender@example.com")'
  status, messages = mail.search(None,'(HEADER Subject "jsaenz14 mentioned everyone")')
  print("Status:", status)

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



        body_content = ""
        for part in msg.walk():
          print(f"Processing part: {part.get_content_type()}")
          if part.get_content_maintype() == "multipart":
            print("Skipping multipart part.")
            continue

          if part.get_content_type() in ["text/plain", "text/html"]:
            try:
              payload = part.get_payload(decode=True)
              if payload:
                body_content += payload.decode("utf-8", errors="ignore")
            except Exception:
              pass

        pdf_links = re.findall(r'https?://[^\s<>"]+?\.pdf[^\s<>"]*', body_content)

          
        html_links = re.findall(r'href="(https?://[^"]+)"', body_content)
        slack_pdf_links = [link for link in html_links if "pdf" in link.lower()]

        
        all_links = set(pdf_links + slack_pdf_links)

        for link in all_links:
          print(f"Found PDF link: {link}")
      
          try:
            print(f"Downloading from: {link}")
            response = requests.get(link, timeout=30, cookies=cookies)
            response.raise_for_status()

            # Determine filename from URL
            filename = link.split("/")[-1].split("?")[0]
            if not filename.endswith(".pdf"):
              filename = "schedule.pdf"

            # 1. Save temporarily to read it
            with open("downloaded_pdfs/" + filename, "wb") as f:
              print(response.content)
              f.write(response.content)

          except Exception as e:
            print(f"Failed to download {link}: {e}")
            continue

          mail.logout()

          return



"""
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

 
"""

if __name__ == "__main__":
  process_emails()