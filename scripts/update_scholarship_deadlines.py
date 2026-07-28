#!/usr/bin/env python3
"""Update scholarship application windows from their official pages.

The updater only replaces dates when the official page contains an explicit
opening and closing date. If extraction or validation fails, the last
confirmed interval in tools-data.json is preserved.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "secret" / "tools-data.json"
GEMINI_MODEL = "gemini-2.5-flash"
ALLOWED_YEAR_OFFSET = 2
MAX_SOURCE_CHARS = 60_000
REQUEST_TIMEOUT = 35
PORTUGUESE_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def scholarship_cards(data: dict[str, Any]) -> list[dict[str, Any]]:
    for category in data.get("categories", []):
        if category.get("id") != "universidade":
            continue
        for section in category.get("sections", []):
            if section.get("id") == "bolsas":
                return section.get("cards", [])
    raise RuntimeError("Não foi encontrada a secção universidade/bolsas.")


def extract_source_text(response: requests.Response) -> str:
    content_type = response.headers.get("content-type", "").lower()
    is_pdf = "pdf" in content_type or response.url.lower().endswith(".pdf")

    if is_pdf:
        reader = PdfReader(BytesIO(response.content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    else:
        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "noscript", "svg"]):
            element.decompose()
        text = soup.get_text(" ", strip=True)

    return re.sub(r"\s+", " ", text).strip()[:MAX_SOURCE_CHARS]


def fetch_official_text(url: str) -> str:
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; PortfolioScholarshipMonitor/1.0; "
                "+https://github.com/)"
            )
        },
    )
    response.raise_for_status()
    return extract_source_text(response)


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("A resposta não contém um objeto JSON.")
    return json.loads(cleaned[start : end + 1])


def deterministic_candidate(source_text: str, today: date) -> dict[str, Any]:
    month_names = "|".join(PORTUGUESE_MONTHS)
    written_pattern = re.compile(
        rf"\b(\d{{1,2}})\s+de\s+({month_names})\s+(?:de\s+)?(20\d{{2}})\b",
        re.IGNORECASE,
    )
    numeric_pattern = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b")
    yearless_range_pattern = re.compile(
        rf"\b(\d{{1,2}})\s+de\s+({month_names})\s+"
        rf"(?:a|até|e|[-–—])\s+(\d{{1,2}})\s+de\s+({month_names})\b",
        re.IGNORECASE,
    )
    occurrences: list[tuple[int, int, date]] = []

    for match in written_pattern.finditer(source_text):
        try:
            value = date(
                int(match.group(3)),
                PORTUGUESE_MONTHS[match.group(2).casefold()],
                int(match.group(1)),
            )
            occurrences.append((match.start(), match.end(), value))
        except (KeyError, ValueError):
            continue

    for match in numeric_pattern.finditer(source_text):
        try:
            value = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
            occurrences.append((match.start(), match.end(), value))
        except ValueError:
            continue

    occurrences.sort(key=lambda item: item[0])
    candidates: list[tuple[date, date, str, str]] = []

    for match in yearless_range_pattern.finditer(source_text):
        evidence_start = max(0, match.start() - 220)
        evidence_end = min(len(source_text), match.end() + 160)
        evidence = source_text[evidence_start:evidence_end].strip()
        if not re.search(r"candidat|inscri|submiss|prazo|bolsa", evidence.casefold()):
            continue
        year_match = re.search(r"\b(20\d{2})[/-](20\d{2})\b", evidence)
        if not year_match:
            continue
        academic_year = f"{year_match.group(1)}/{year_match.group(2)}"
        first_year = int(year_match.group(1))
        second_year = int(year_match.group(2))
        first_month = PORTUGUESE_MONTHS[match.group(2).casefold()]
        second_month = PORTUGUESE_MONTHS[match.group(4).casefold()]
        opens_year = first_year if first_month >= 7 else second_year
        deadline_year = first_year if second_month >= first_month else second_year
        try:
            opens = date(opens_year, first_month, int(match.group(1)))
            deadline = date(deadline_year, second_month, int(match.group(3)))
        except ValueError:
            continue
        if opens <= deadline:
            candidates.append((opens, deadline, academic_year, evidence))

    for index, (start_pos, _, opens) in enumerate(occurrences):
        for end_pos, deadline_end, deadline in occurrences[index + 1 : index + 5]:
            if end_pos - start_pos > 500 or opens > deadline:
                continue
            evidence_start = max(0, start_pos - 120)
            evidence_end = min(len(source_text), deadline_end + 120)
            evidence = source_text[evidence_start:evidence_end].strip()
            lowered = evidence.casefold()
            if not re.search(r"candidat|inscri|submiss|prazo|bolsa", lowered):
                continue
            between = source_text[start_pos:end_pos].casefold()
            if not re.search(r"\s(?:a|até|e)\s|[-–—]", between):
                continue
            year_match = re.search(r"\b(20\d{2})[/-](20\d{2})\b", evidence)
            if year_match:
                academic_year = f"{year_match.group(1)}/{year_match.group(2)}"
            elif opens.month >= 7:
                academic_year = f"{opens.year}/{opens.year + 1}"
            else:
                academic_year = f"{opens.year - 1}/{opens.year}"
            candidates.append((opens, deadline, academic_year, evidence))

    if not candidates:
        return {"found": False}

    viable = [item for item in candidates if item[1] >= today]
    selected = max(viable or candidates, key=lambda item: (item[1], item[0]))
    return {
        "found": True,
        "opens": selected[0].isoformat(),
        "deadline": selected[1].isoformat(),
        "academicYear": selected[2],
        "evidence": selected[3],
    }


def ask_gemini(
    api_key: str,
    title: str,
    source_url: str,
    source_text: str,
    today: date,
) -> dict[str, Any]:
    prompt = f"""
Analisa o texto de uma página oficial sobre a bolsa "{title}".
A data atual é {today.isoformat()}.

Devolve APENAS JSON com este formato:
{{
  "found": true ou false,
  "opens": "YYYY-MM-DD" ou null,
  "deadline": "YYYY-MM-DD" ou null,
  "academicYear": "YYYY/YYYY" ou null,
  "evidence": "fragmento curto copiado literalmente da fonte"
}}

Regras obrigatórias:
- Usa apenas datas de candidatura explicitamente presentes no texto.
- Escolhe o intervalo mais recente que esteja aberto, seja futuro, ou pertença
  ao ano letivo atual/seguinte.
- Só usa found=true quando existirem no texto a data de abertura E a data final.
- Não confundas datas de publicação, resultados, matrículas ou cerimónias.
- Não completes nem infiras datas em falta.
- evidence tem de ser uma passagem literal da fonte que sustente as duas datas.

Fonte oficial: {source_url}
Texto:
{source_text}
""".strip()

    response = requests.post(
        (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent"
        ),
        timeout=REQUEST_TIMEOUT,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        },
    )
    response.raise_for_status()
    payload = response.json()
    answer = payload["candidates"][0]["content"]["parts"][0]["text"]
    return extract_json_object(answer)


def parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def normalize_for_evidence(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def validate_candidate(
    candidate: dict[str, Any],
    source_text: str,
    today: date,
) -> tuple[date, date, str] | None:
    if candidate.get("found") is not True:
        return None

    opens = parse_iso_date(candidate.get("opens"))
    deadline = parse_iso_date(candidate.get("deadline"))
    academic_year = candidate.get("academicYear")
    evidence = candidate.get("evidence")

    if not opens or not deadline or opens > deadline:
        return None
    if opens.year < today.year - 1 or deadline.year > today.year + ALLOWED_YEAR_OFFSET:
        return None
    if not isinstance(academic_year, str) or not re.fullmatch(r"\d{4}/\d{4}", academic_year):
        return None
    if not isinstance(evidence, str) or len(evidence.strip()) < 12:
        return None
    if normalize_for_evidence(evidence) not in normalize_for_evidence(source_text):
        return None

    return opens, deadline, academic_year


def portuguese_interval(opens: date, deadline: date) -> str:
    months = (
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    )
    return (
        f"{opens.day} de {months[opens.month - 1]} de {opens.year} "
        f"a {deadline.day} de {months[deadline.month - 1]} de {deadline.year}"
    )


def load_local_key() -> str:
    key_path = ROOT / "gemini_api_key.local.txt"
    if not key_path.exists():
        return ""
    contents = key_path.read_text(encoding="utf-8")
    match = re.search(r"\bAIza[0-9A-Za-z_-]{35}\b", contents)
    return match.group(0) if match else ""


def safe_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return f"resposta HTTP {exc.response.status_code}"
    if isinstance(exc, requests.RequestException):
        return exc.__class__.__name__
    return str(exc)


def update_cards(api_key: str, dry_run: bool) -> int:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    today = date.today()
    updates = 0

    if not api_key:
        print("GEMINI_API_KEY não configurada: a usar extração determinística.")

    for card in scholarship_cards(data):
        application = card.get("application") or {}
        if application.get("mode") in {"automatic", "not-applicable"}:
            continue

        title = card.get("title", "Bolsa")
        source_url = application.get("sourceUrl") or card.get("href")
        if not source_url:
            print(f"[ignorada] {title}: sem fonte oficial")
            continue

        try:
            source_text = fetch_official_text(source_url)
            if not source_text:
                raise ValueError("a página oficial não contém texto legível")
        except Exception as exc:
            print(f"[preservada] {title}: {safe_error(exc)}")
            continue

        candidate = deterministic_candidate(source_text, today)
        valid = validate_candidate(candidate, source_text, today)
        if api_key:
            try:
                ai_candidate = ask_gemini(api_key, title, source_url, source_text, today)
                ai_valid = validate_candidate(ai_candidate, source_text, today)
                if ai_valid:
                    valid = ai_valid
            except Exception as exc:
                print(f"[aviso] {title}: IA indisponível ({safe_error(exc)}); usada extração local")

        if not valid:
            print(f"[preservada] {title}: sem novo intervalo explícito e validado")
            continue

        opens, deadline, academic_year = valid
        replacement = {
            "mode": "fixed",
            "opens": opens.isoformat(),
            "deadline": deadline.isoformat(),
            "academicYear": academic_year,
            "label": portuguese_interval(opens, deadline),
            "sourceUrl": source_url,
            "checkedAt": today.isoformat(),
        }

        if application != replacement:
            card["application"] = replacement
            updates += 1
            print(f"[atualizada] {title}: {opens.isoformat()} — {deadline.isoformat()}")
        else:
            print(f"[confirmada] {title}: intervalo sem alterações")

    if updates and not dry_run:
        DATA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"{updates} intervalo(s) {'encontrado(s)' if dry_run else 'atualizado(s)'}.")
    return updates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Consulta e valida as fontes, mas não altera o ficheiro JSON.",
    )
    parser.add_argument(
        "--use-local-key",
        action="store_true",
        help="Usa gemini_api_key.local.txt (apenas para teste local).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if args.use_local_key and not api_key:
        api_key = load_local_key()
    update_cards(api_key, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
