import sys, inspect
sys.path.insert(0, '/app')
from models.schemas import DrawSession, DrawEntry, SourceID

# ── 1. Show DrawSession fields ──────────────────────────────────────────
print("=== DrawSession source ===")
print(inspect.getsource(DrawSession))

# ── 2. Reproduce the EXACT constructor call parse_html makes ────────────
print("\n=== Exact parse_html constructor call ===")
entries = [DrawEntry(premio=1, milhar='5106', centena='106', dezena='06', grupo=2, bicho='Águia')]
try:
    s = DrawSession(
        source_id=SourceID.BOA_SORTE,
        source_url="https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje",
        draw_date="05/04/2026",
        draw_time="09:00",
        draw_label="BOA SORTE - GOIÁS, 09h - Resultado do dia 05/04/2026 (Domingo)",
        state="GO",
        banca=None,
        entries=entries,
        super5=[7, 8, 11, 12, 25],
        soma="8326",
        mult="666",
    )
    print(f"  OK: {s.session_id}")
except Exception as e:
    print(f"  FAILED: {e}")
