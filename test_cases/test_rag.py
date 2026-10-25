import json
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from agent.bank_knowledge_base import bank_retriever, ALFA_REPORTS_INDEX
from agent.prompts.qwen_rag import build_rag_prompt

def run_rag_test():
    golden_path = root_dir / "test_cases" / "golden_dataset.json"
    with open(golden_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    lines = []
    lines.append(f"Всего отчетов Альфа-Банка в индексе: {len(ALFA_REPORTS_INDEX)}")
    lines.append("=" * 70)

    for i, c in enumerate(cases, 1):
        comp = c["company"]
        news = c["news"]
        expected_chunk = c.get("bank_report_chunk", {})
        expected_pdf = expected_chunk.get("source_file")

        matches = bank_retriever.find_relevant_reports(
            news["title"],
            news["body"],
            sector_name=comp["mainokved_name"],
            top_k=2
        )
        top = matches[0] if matches else None

        lines.append(f"\nКЕЙС {i}: {c['title']}")
        lines.append(f"Клиент: {comp['display_name']} [Отрасль: {comp['mainokved_name']}]")
        lines.append(f"Новость: {news['title']}")
        lines.append(f"-> НАЙДЕННЫЙ ОТЧЕТ БАНКА: {top.report_title if top else 'НЕ НАЙДЕН'}")
        lines.append(f"-> ФАЙЛ ПЕРВОИСТОЧНИКА: {top.source_filename if top else 'None'} (Ожидался: {expected_pdf})")
        lines.append(f"-> ОФИЦИАЛЬНАЯ РЕКОМЕНДАЦИЯ БАНКА: {top.official_recommendation if top else 'None'}")
        
        # Test prompt generation for Qwen 3.6 RAG
        rag_prompt = build_rag_prompt(
            news={"title": news["title"], "factual_essence": news["body"][:200]},
            retrieved_chunks=top.detailed_text if top else ""
        )
        lines.append(f"-> СФОРМИРОВАННЫЙ ПРОМПТ ДЛЯ QWEN 3.6 (RAG):\n{rag_prompt['user']}")
        lines.append("-" * 70)

    out_file = root_dir / "test_cases" / "rag_test_results.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"RAG test finished! Results saved to {out_file}")

if __name__ == "__main__":
    run_rag_test()
