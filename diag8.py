import sys
sys.path.insert(0, '/app')
from models.schemas import WebhookPayload, DrawSession, SourceID, DrawEntry
from datetime import datetime

# Build a minimal fake session
session = DrawSession(
    source_id=SourceID.BOA_SORTE,
    source_url="https://example.com",
    draw_date="05/04/2026",
    draw_time="09:00",
    entries=[
        DrawEntry(premio=1, milhar="1234", centena="123", dezena="23", animal="Avestruz"),
        DrawEntry(premio=2, milhar="5678", centena="567", dezena="67", animal="Águia"),
        DrawEntry(premio=3, milhar="9012", centena="901", dezena="01", animal="Burro"),
        DrawEntry(premio=4, milhar="3456", centena="345", dezena="45", animal="Borboleta"),
        DrawEntry(premio=5, milhar="7890", centena="789", dezena="89", animal="Cachorro"),
    ],
)

payload = WebhookPayload.from_session(session)
print("=== Current payload being sent ===")
print(payload.model_dump_json(indent=2))
