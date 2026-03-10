import anthropic
import os
import json
from typing import Dict, List, AsyncGenerator
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are an automotive technician AI. Given structured OBD diagnostic events and metrics, write a concise, plain-English preventive maintenance report. Include: a 2-sentence vehicle health summary, a bulleted list of detected issues with severity, specific recommended actions, and one driving behavior note. Be direct and practical. Do not speculate beyond the data."""

def format_diagnostic_data(events: List[Dict], features: Dict, trends: Dict = None) -> str:
    data = {
        "diagnostic_events": events,
        "metrics": features
    }

    if trends and trends.get('status') == 'success':
        data['trends'] = trends.get('trends', {})

    return json.dumps(data, indent=2)

async def generate_report_stream(events: List[Dict], features: Dict, trends: Dict = None) -> AsyncGenerator[str, None]:
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        yield "Error: ANTHROPIC_API_KEY not found in environment variables"
        return

    client = anthropic.Anthropic(api_key=api_key)

    user_message = format_diagnostic_data(events, features, trends)

    try:
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        ) as stream:
            for text in stream.text_stream:
                yield text

    except Exception as e:
        yield f"Error generating report: {str(e)}"

async def generate_report(events: List[Dict], features: Dict, trends: Dict = None) -> str:
    full_report = ""
    async for chunk in generate_report_stream(events, features, trends):
        full_report += chunk
    return full_report
