from dotenv import load_dotenv
from datetime import date
from pathlib import Path
from src.digest import create_markdown_digest
from src.news_fetcher import fetch_articles
from src.ranker import apply_source_diversity, rank_articles
from delivery import send_to_discord


def main() -> None:
    load_dotenv()

    articles = fetch_articles(limit_per_source=8)

    if not articles:
        raise RuntimeError("No articles were fetched.")

    ranked_articles = rank_articles(articles, top_n=10)
    top_articles = apply_source_diversity(ranked_articles, max_per_source=1, final_count=3)

    digest = create_markdown_digest(top_articles)

    print(digest)
    digest_dir = Path("digests")
    digest_dir.mkdir(exist_ok=True)

    digest_path = digest_dir / f"{date.today().isoformat()}.md"

    with digest_path.open("w", encoding="utf-8") as file:
        file.write(digest)
        send_to_discord(digest)




if __name__ == "__main__":
    main()