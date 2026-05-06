import os, anthropic
from dotenv import load_dotenv; load_dotenv()
from notion_client import Client

def verify_anthropic():
  c = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
  r = c.messages.create(model="claude-haiku-4-5-20251001", max_tokens=10, messages=[{"role":"user","content":"Say OK"}])
  print(f"✓ Anthropic: {r.content[0].text}")

def verify_notion():
  c = Client(auth=os.environ["NOTION_TOKEN"])
  r = c.search(query="", page_size=1)
  print(f"✓ Notion: {len(r['results'])} item(s)")

verify_anthropic(); verify_notion(); print("✅ Ready for Day 2")