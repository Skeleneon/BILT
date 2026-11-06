import email
import imaplib
import os
from email.header import decode_header
import pdfplumber
from pypdf import PdfReader
from dotenv import load_dotenv
import re
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from tomlkit import datetime
import json
from datetime import datetime, timedelta

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
        print("found link") if slack_pdf_links else print()

 

        
  all_links = set(pdf_links + slack_pdf_links)
  print(all_links)

  pdfs = []
  open("processed.txt", "a").close()

  with open("processed.txt", "r") as f:
    processed_files = f.read().splitlines()
    global processed
    processed = []
    for i in processed_files:
      processed.append(i.split("$@$"))

  # download PDFs
  
  for link in all_links:
    cont = False
    for i in processed:
      if link in i:
        print(f"Already processed: {link}")
        cont = True
        break
      
    if cont:
      continue
      
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


  if not pdfs:
    print("No new schedules found")
    return

    
  for pdf_fname in pdfs:
    print("Pulling schedule from PDF:", pdf_fname)



    pdf_path = os.path.join("downloaded_pdfs", pdf_fname)
    with pdfplumber.open(pdf_path) as pdf:

      first_page_text = pdf.pages[0].extract_text()
      match = re.search(r"For the period of (\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{1,2}/\d{1,2}/\d{4})", first_page_text)

      if match:
        week_start_str = match.group(1)  # e.g., "11/2/2026"
        week_end_str = match.group(2)  # e.g., "11/8/2026"

        week_start_date = datetime.strptime(week_start_str, "%m/%d/%Y")
        week_end_date = datetime.strptime(week_end_str, "%m/%d/%Y")
        print(f"Found week start date: {week_start_str}")
        print(f"Found week end date: {week_end_str}")

        for i in processed:
          if f"{week_start_str}-{week_end_str}" == i[1]:
            print(f"Already processed schedule for {week_start_str}-{week_end_str}, deleting old set")
            delete_work_events_in_range(week_start_str, week_end_str)
            

         


      else:
        print("Warning: Could not find schedule period header, skipping file.")
        continue


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
      
        needs_cleanup = True
        while len(shift_times)>1 and needs_cleanup:
          
          for i in range(len(shift_times)-1):
            if shift_times[i][1] == shift_times[i+1][0]:
              temp = [shift_times[i][0],shift_times[i+1][1]]
              shift_times.insert(i,temp)
              a=shift_times.pop(i+1)
              a=shift_times.pop(i+1)
              for i in range(len(shift_times)-1):
                if shift_times[i][1] == shift_times[i+1][0]:
                  needs_cleanup = True
                  break
                else:
                  needs_cleanup = False
              break
        cleaned_shifts[shift] = shift_times    
            
    
  
    cleaned_shifts["week_start"] = week_start_str
    cleaned_shifts["week_end"] = week_end_str

    with open("processed.txt", "a") as f:
      for pdf_fname in pdfs:
        f.write(f"{link}$@${week_start_str}-{week_end_str}\n")

    mail.logout() 
    print(cleaned_shifts)

    schedule_shifts(cleaned_shifts)
    cleaned_shifts.clear()
    shifts.clear()
    shift_times.clear()
    os.remove(pdf_path)



def add_to_calendar(event_name="Test", event_location="Downtown Pheonix Campus", event_description="Testing automated calendar sync locally",event_start_time=None, event_end_time=None):
  sa_json = os.environ.get("GCP_SA_KEY")
  if not sa_json:
    print("Error: GCP_SA_KEY not found in .env file.")
    return

  sa_info = json.loads(sa_json)
  creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/calendar"]
    )
  service = build("calendar", "v3", credentials=creds)

  
  dt_start = datetime.now() if not event_start_time else event_start_time
  dt_end = dt_start + timedelta(hours=1) if not event_end_time else event_end_time
  

  event = {
      "summary": event_name,
      "location": event_location,
      "description": event_description,
      "start": {"dateTime": dt_start.isoformat(), "timeZone": "America/Phoenix"},
      "end": {"dateTime": dt_end.isoformat(), "timeZone": "America/Phoenix"},
  }

  # 4. Push to primary calendar (or substitute your calendar email if needed)
  created_event = (
      service.events().insert(
        calendarId="e3fa2d7675fd0c62ef9ce956566f231744af375978008992f9b15b8f27a92939@group.calendar.google.com",
          body=event).execute()
  )
  print(f"Success! Event created")




def delete_work_events_in_range(start_date_str, end_date_str, query_name="Work"):
  sa_json = os.environ.get("GCP_SA_KEY")
  if not sa_json:
    print("Error: GCP_SA_KEY not found.")
    return

  sa_info = json.loads(sa_json)
  creds = service_account.Credentials.from_service_account_info(
      sa_info, scopes=["https://www.googleapis.com/auth/calendar"]
  )
  service = build("calendar", "v3", credentials=creds)

  calendar_id = (
      "e3fa2d7675fd0c62ef9ce956566f231744af375978008992f9b15b8f27a92939@group.calendar.google.com"
  )
  start_datetime = datetime.strptime(start_date_str, "%m/%d/%Y")
  end_datetime = datetime.strptime(end_date_str, "%m/%d/%Y")

  # Format datetimes to ISO format strings with timezone offset
  time_min = start_datetime.isoformat() + "-07:00"
  time_max = end_datetime.isoformat() + "-07:00"

  # 1. List events using BOTH time window and text query filters
  events_result = (
      service.events()
      .list(
          calendarId=calendar_id,
          q=query_name,  # Limits results to events containing this name (e.g., "Work")
          timeMin=time_min,  # Start of the range
          timeMax=time_max,  # End of the range
          singleEvents=True,
          orderBy="startTime",
      )
      .execute()
  )

  events = events_result.get("items", [])

  if not events:
    print(
        f"No events matching '{query_name}' found between {start_datetime} and"
        f" {end_datetime}."
    )
    return

  # 2. Loop through matches and delete them
  for event in events:
    event_id = event["id"]
    summary = event.get("summary", "No Title")
    start_time = event["start"].get("dateTime", event["start"].get("date"))

    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    print(f"Deleted event: '{summary}' (Scheduled for {start_time})")


def schedule_shifts(shift):
  shifts = shift
  day_offsets = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }

  # Parse the base week start date once
  week_start_date = datetime.strptime(shifts["week_start"], "%m/%d/%Y")

  for day, offset in day_offsets.items():
    if shifts.get(day):
      # Calculate the exact date for this specific day of the week
      current_day_date = week_start_date + timedelta(days=offset)
      date_str = current_day_date.strftime("%m/%d/%Y")

      for shift in shifts[day]:
        start_time = datetime.strptime(
            f"{date_str} {shift[0]}", "%m/%d/%Y %I:%M %p"
        )
        end_time = datetime.strptime(
            f"{date_str} {shift[1]}", "%m/%d/%Y %I:%M %p"
        )

        add_to_calendar(
            event_name="Work",
            event_location="Downtown Phoenix Campus - UCENT 267",
            event_description="Automated calendar sync for work shifts.",
            event_start_time=start_time,
            event_end_time=end_time,
        )



if __name__ == "__main__":
  process_emails()