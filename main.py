import email
import imaplib
import os
from email.header import decode_header
import pdfplumber
from pypdf import PdfReader
from dotenv import load_dotenv
import re
import requests

load_dotenv()


EMAIL = os.environ.get("MAIL_USER")
PASSWORD = os.environ.get("MAIL_PASS")

cookies={
  "d": os.environ.get("SLACK_D"),
  "d-s": os.environ.get("SLACK_DS")
}


COLUMN_DAYS = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}
 
IMAP_SERVER = "imap.gmail.com" 

def clean_filename(filename):
  return ("".join(c for c in filename if c.isalnum() or ("._- ") in c).rstrip()).rstrip(".pdf")+".pdf"


def process_emails():
  mail = imaplib.IMAP4_SSL(IMAP_SERVER)
  mail.login(EMAIL, PASSWORD)
  mail.select('"Slack Emails"')
  print("Connected to mailbox.")


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

  #pull links from emails


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

  pdfs = []

  # download PDFs

  for link in all_links:
    print(f"Found PDF link: {link}")
      
    try:
      print(f"Downloading from: {link}")
      response = requests.get(link, timeout=30, cookies=cookies)
      response.raise_for_status()
  
      filename = link.split("/")[-1].split("?")[0]

      
      with open("downloaded_pdfs/" + filename, "wb") as f:
        f.write(response.content)
        pdfs.append(filename)
        print(f"Downloaded and saved: {filename}")

    except Exception as e:
      print(f"Failed to download {link}: {e}")
      continue

    


  print(f"Total PDFs downloaded: {len(pdfs)}")
  shifts = {"Sunday":[], "Monday":[], "Tuesday":[], "Wednesday":[], "Thursday":[], "Friday":[], "Saturday":[]}

  #Pull Shift from PDF
    
  for pdf_fname in pdfs:
    print("Pulling schedule from PDF:", pdf_fname)
    pdf_path = os.path.join("downloaded_pdfs", pdf_fname)
    with pdfplumber.open(pdf_path) as pdf:
      for page_num, page in enumerate(pdf.pages, 1):
        table = page.extract_table()
        if not table:continue


        
        i = 0
        while i < len(table):
          row = table[i]

          
          if row and row[0] and "Aman Suhail" in str(row[0]):
            print(f"Found Aman Suhail on Page {page_num}:")

            current_row_idx = i
            while current_row_idx < len(table):
              target_row = table[current_row_idx]

             
              if (
                  current_row_idx != i
                  and target_row
                  and target_row[0]
                  and target_row[0].strip() != ""
              ):
                break

              for col_index, cell_value in enumerate(target_row):
                if (
                    col_index in COLUMN_DAYS
                    and cell_value
                    and cell_value.strip()
                ):
                  day_name = COLUMN_DAYS[col_index]
                  shift_time = cell_value.strip().replace("\n", " ")
                  if "UCENT" not in shift_time:
                    print(f"  {day_name}: {shift_time}")

                    shifts[day_name].append(shift_time.split("-"))

              current_row_idx += 1

          i += 1

  

  cleaned_shifts = {}
  shift_times = []

    # Shifts cleanup
  for shift in shifts:
    if shifts[shift]:
      shift_times = shifts[shift].copy()
      print(shift_times)
      needs_cleanup = True
      while len(shift_times)>1 and needs_cleanup:
        print("loop")
        for i in range(len(shift_times)-1):
          if shift_times[i][1] == shift_times[i+1][0]:
            temp = [shift_times[i][0],shift_times[i+1][1]]
            print(temp)
            shift_times.insert(i,temp)
            print(shift_times)
            shift_times.pop(i+1)
            print(shift_times)
            shift_times.pop(i+1)
            print(shift_times)
            for i in range(len(shift_times)-1):
              if shift_times[i][1] == shift_times[i+1][0]:
                needs_cleanup = True
                break
              else:
                needs_cleanup = False
            break
      cleaned_shifts[shift] = shift_times    
          
      
      


  mail.logout()  

if __name__ == "__main__":
  process_emails()