"""
tests/test_parsers.py
─────────────────────
Unit tests for all four parser implementations.
Uses inline HTML fixtures that mirror the real page structure observed
during Phase 1 recon — no network calls required.

Run:
    pip install pytest
    pytest tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import DrawSession, SourceID
from scrapers.resultado_facil_scraper import ResultadoFacilScraper
from scrapers.nacional_scraper import LoterianacionalScraper


# ─────────────────────────────────────────────────────────────────
# HTML FIXTURES
# ─────────────────────────────────────────────────────────────────

BOA_SORTE_HTML = """
<html><body>
<h3>BOA SORTE - GOIÁS, 11h - Resultado do dia 08/03/2026 (Domingo)</h3>
<table>
  <tr><th>Prêmio</th><th>Milhar</th><th>Grupo</th><th>Bicho</th></tr>
  <tr><td>1º</td><td>0535</td><td>09</td><td>Cobra</td></tr>
  <tr><td>2º</td><td>8125</td><td>07</td><td>Carneiro</td></tr>
  <tr><td>3º</td><td>2957</td><td>15</td><td>Jacaré</td></tr>
  <tr><td>4º</td><td>1461</td><td>16</td><td>Leão</td></tr>
  <tr><td>5º</td><td>4178</td><td>20</td><td>Peru</td></tr>
  <tr><td>6º [soma]</td><td>7256</td><td></td><td></td></tr>
  <tr><td>7º [mult]</td><td>346</td><td></td><td></td></tr>
</table>
<h3>BOA SORTE - GOIÁS, 14h - Resultado do dia 08/03/2026 (Domingo)</h3>
<table>
  <tr><th>Prêmio</th><th>Milhar</th><th>Grupo</th><th>Bicho</th></tr>
  <tr><td>1º</td><td>8086</td><td>22</td><td>Tigre</td></tr>
  <tr><td>2º</td><td>5321</td><td>06</td><td>Cabra</td></tr>
  <tr><td>3º</td><td>5518</td><td>05</td><td>Cachorro</td></tr>
  <tr><td>4º</td><td>9921</td><td>06</td><td>Cabra</td></tr>
  <tr><td>5º</td><td>1527</td><td>07</td><td>Carneiro</td></tr>
</table>
</body></html>
"""

LOOK_LOTERIAS_HTML = """
<html><body>
<h3>LOOK - GOIÁS, 09h - Resultado do dia 18/02/2026 (Quarta-feira)</h3>
<table>
  <tr><th>Prêmio</th><th>Milhar</th><th>Grupo</th><th>Bicho</th></tr>
  <tr><td>1º</td><td>2860</td><td>15</td><td>Jacaré</td></tr>
  <tr><td>2º</td><td>6777</td><td>20</td><td>Peru</td></tr>
  <tr><td>3º</td><td>1606</td><td>02</td><td>Águia</td></tr>
  <tr><td>4º</td><td>6068</td><td>17</td><td>Macaco</td></tr>
  <tr><td>5º</td><td>3776</td><td>19</td><td>Pavão</td></tr>
  <tr><td>6º [soma]</td><td>1087</td><td></td><td></td></tr>
  <tr><td>7º [mult]</td><td>382</td><td></td><td></td></tr>
</table>
<ul><li><strong>Super 5:</strong>  17 18 21 22 26</li></ul>
</body></html>
"""

BICHO_RJ_HTML = """
<html><body>
<h3>Resultado do Jogo do Bicho RJ, 11:00, PTM, 1º ao 5º</h3>
<table>
  <tr><th>Prêmio</th><th>Milhar</th><th>Grupo</th><th>Bicho</th></tr>
  <tr><td>1º</td><td>7488</td><td>22</td><td>Tigre</td></tr>
  <tr><td>2º</td><td>8931</td><td>08</td><td>Camelo</td></tr>
  <tr><td>3º</td><td>5552</td><td>13</td><td>Galo</td></tr>
  <tr><td>4º</td><td>9635</td><td>09</td><td>Cobra</td></tr>
  <tr><td>5º</td><td>3406</td><td>02</td><td>Águia</td></tr>
  <tr><td>6º [soma]</td><td>5012</td><td></td><td></td></tr>
  <tr><td>7º [mult]</td><td>875</td><td></td><td></td></tr>
</table>
</body></html>
"""

NACIONAL_HTML = """
<html><body>
<h3>Resultado Loteria Nacional - 08/03/2026 - 14h</h3>
<table>
  <tr><th>Prêmio</th><th>Milhar</th><th>Grupo</th><th>Bicho</th></tr>
  <tr><td>1º</td><td>3950</td><td>20</td><td>Peru</td></tr>
  <tr><td>2º</td><td>4113</td><td>03</td><td>Burro</td></tr>
  <tr><td>3º</td><td>4996</td><td>25</td><td>Vaca</td></tr>
  <tr><td>4º</td><td>2820</td><td>21</td><td>Touro</td></tr>
  <tr><td>5º</td><td>3215</td><td>11</td><td>Cavalo</td></tr>
</table>
</body></html>
"""


# ─────────────────────────────────────────────────────────────────
# TESTS — Boa Sorte
# ─────────────────────────────────────────────────────────────────

class TestBoaSorteScraper:
    def _make_scraper(self):
        from unittest.mock import MagicMock
        client = MagicMock()
        return ResultadoFacilScraper(
            client=client,
            source_id=SourceID.BOA_SORTE,
            url="https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje",
            state="GO",
        )

    def test_parses_two_sessions(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(BOA_SORTE_HTML)
        assert len(sessions) == 2

    def test_first_session_entries(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(BOA_SORTE_HTML)
        first = sessions[0]
        assert first.draw_time == "11:00"
        assert first.draw_date == "08/03/2026"
        assert len(first.entries) == 5

    def test_first_milhar(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(BOA_SORTE_HTML)
        assert sessions[0].first_milhar == "0535"

    def test_complemento_derived(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(BOA_SORTE_HTML)
        entry = sessions[0].entries[0]
        assert entry.milhar == "0535"
        assert entry.complemento == "9464"   # 9999 - 535 = 9464

    def test_soma_mult_not_in_entries(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(BOA_SORTE_HTML)
        for s in sessions:
            premios = [e.premio for e in s.entries]
            assert 6 not in premios
            assert 7 not in premios

    def test_source_id(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(BOA_SORTE_HTML)
        for s in sessions:
            assert s.source_id == SourceID.BOA_SORTE

    def test_state(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(BOA_SORTE_HTML)
        assert all(s.state == "GO" for s in sessions)


# ─────────────────────────────────────────────────────────────────
# TESTS — Look Loterias
# ─────────────────────────────────────────────────────────────────

class TestLookLoterias:
    def _make_scraper(self):
        from unittest.mock import MagicMock
        client = MagicMock()
        return ResultadoFacilScraper(
            client=client,
            source_id=SourceID.LOOK_LOTERIAS,
            url="https://www.resultadofacil.com.br/resultados-look-loterias-de-hoje",
            state="GO",
        )

    def test_super5_parsed(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(LOOK_LOTERIAS_HTML)
        assert sessions[0].super5 is not None
        assert sessions[0].super5.numbers == [17, 18, 21, 22, 26]

    def test_five_entries(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(LOOK_LOTERIAS_HTML)
        assert len(sessions[0].entries) == 5


# ─────────────────────────────────────────────────────────────────
# TESTS — Bicho RJ
# ─────────────────────────────────────────────────────────────────

class TestBichoRJ:
    def _make_scraper(self):
        from unittest.mock import MagicMock
        client = MagicMock()
        return ResultadoFacilScraper(
            client=client,
            source_id=SourceID.BICHO_RJ,
            url="https://www.resultadofacil.com.br/resultado-do-jogo-do-bicho/rj",
            state="RJ",
        )

    def test_banca_detected(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(BICHO_RJ_HTML)
        assert sessions[0].banca == "PTM"

    def test_state_rj(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(BICHO_RJ_HTML)
        assert sessions[0].state == "RJ"


# ─────────────────────────────────────────────────────────────────
# TESTS — Nacional
# ─────────────────────────────────────────────────────────────────

class TestNacionalScraper:
    def _make_scraper(self):
        from unittest.mock import MagicMock
        client = MagicMock()
        s = LoterianacionalScraper(client)
        return s

    def test_parses_session(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(NACIONAL_HTML)
        assert len(sessions) == 1

    def test_five_entries(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(NACIONAL_HTML)
        assert len(sessions[0].entries) == 5

    def test_first_milhar(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(NACIONAL_HTML)
        assert sessions[0].first_milhar == "3950"

    def test_complemento(self):
        scraper = self._make_scraper()
        sessions = scraper.parse_html(NACIONAL_HTML)
        e = sessions[0].entries[0]
        assert e.complemento == f"{9999 - 3950:04d}"


# ─────────────────────────────────────────────────────────────────
# TESTS — Webhook Payload
# ─────────────────────────────────────────────────────────────────

class TestWebhookPayload:
    def test_from_session(self):
        from unittest.mock import MagicMock
        client = MagicMock()
        scraper = ResultadoFacilScraper(
            client=client,
            source_id=SourceID.BOA_SORTE,
            url="https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje",
        )
        sessions = scraper.parse_html(BOA_SORTE_HTML)
        from models.schemas import WebhookPayload
        payload = WebhookPayload.from_session(sessions[0])
        assert len(payload.numbers) == 5
        assert len(payload.complementos) == 5
        assert payload.source == "boa_sorte"
        # Complementos must all be 4-digit strings
        for c in payload.complementos:
            assert len(c) == 4
            assert c.isdigit()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
