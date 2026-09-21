#!/usr/bin/env python3
"""Build the VinAura landing page from landing/src.

  landing/vinaura-landing.html  paste into a WordPress Custom HTML block (pictures from the media library)
  landing/preview.html          open locally (pictures from landing/images)
"""
import html
import json
import re
from pathlib import Path

LANDING = Path(__file__).resolve().parent.parent / "landing"
SRC = LANDING / "src"
MEDIA = "https://vinish.dev/wp-content/uploads/2026/09/"
PAGE_URL = "https://vinish.dev/vinaura/"

HEADER = """<!--
  VinAura landing page - paste everything in this file into a WordPress "Custom HTML" block.

  1. The pictures are linked straight from the WordPress media library:
       {media}vinaura-designer-invoice.webp ... (upload every file of landing/images)
  2. The form posts to data-endpoint: the Rounds lead mailer plugin, version 2.1.0 or later,
     which knows the product, company, country and licence fields (see landing/README.md).
     If it can't be reached, the form offers an e-mail link to data-fallback-email (leave it
     empty to show no address on the public page).
  Built by tools/build_landing.py from landing/src - edit the sources, not this file.
-->
"""


def json_ld(body: str) -> str:
    faqs = []
    for q, a in re.findall(r"<details[^>]*><summary>(.*?)</summary><p>(.*?)</p></details>", body, re.S):
        faqs.append({
            "@type": "Question",
            "name": html.unescape(re.sub(r"<[^>]+>", "", q)),
            "acceptedAnswer": {"@type": "Answer", "text": html.unescape(re.sub(r"<[^>]+>", "", a))},
        })
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": "VinAura",
                "alternateName": "VinAura - Visual PDF Report Designer for Oracle APEX",
                "applicationCategory": "DeveloperApplication",
                "applicationSubCategory": "PDF report designer for Oracle APEX",
                "operatingSystem": "Oracle Database with Oracle APEX",
                "description": "VinAura is a visual PDF report designer for Oracle APEX. Design invoices, statements "
                               "and labels on a canvas, bind them to SQL queries and page items, and get the PDF "
                               "as a BLOB with one PL/SQL call. Pure PL/SQL: no BI Publisher, no print server.",
                "url": PAGE_URL,
                "image": MEDIA + "vinaura-designer-invoice.webp",
                "screenshot": [MEDIA + f"vinaura-{n}.webp" for n in
                               ("designer-invoice", "designer-queries", "designer-preview", "demo-dialog")],
                "featureList": [
                    "Visual layout designer with bands", "Up to ten SQL queries per report with APEX page item binds",
                    "Tables that flow over pages with repeated headers", "Totals, groups and sub-totals",
                    "Amount in words", "Code 128 barcodes and label sheets", "Batch documents",
                    "Any page size, portrait or landscape", "Logos and images", "Export and import as JSON",
                ],
                "offers": {"@type": "Offer", "availability": "https://schema.org/InStock",
                           "url": PAGE_URL + "#va-get", "description": "Price on request"},
                "author": {"@type": "Person", "name": "Vinish Kapoor", "url": "https://vinish.dev"},
            },
            {"@type": "FAQPage", "mainEntity": faqs},
        ],
    }
    return '<script type="application/ld+json">\n' + json.dumps(data, indent=1, ensure_ascii=False) + "\n</script>\n"


def build(img_base: str) -> str:
    body = (SRC / "body.html").read_text().replace("{{IMG}}", img_base)
    css = (SRC / "base.css").read_text().rstrip() + "\n\n" + (SRC / "extra.css").read_text()
    return (
        HEADER.format(media=MEDIA)
        + '<div id="vinaura-lp" class="alignfull"\n     data-endpoint="/wp-json/rounds/v1/lead"\n     data-fallback-email="">\n\n'
        + "<style>\n" + css.strip() + "\n</style>\n\n"
        + (SRC / "icons.svg").read_text().strip() + "\n\n"
        + body.strip() + "\n\n"
        + json_ld(body) + "\n"
        + "<script>\n" + (SRC / "script.js").read_text().strip() + "\n</script>\n</div>\n"
    )


def main():
    page = build(MEDIA)
    (LANDING / "vinaura-landing.html").write_text(page)
    preview = build("images/")
    (LANDING / "preview.html").write_text(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>VinAura - Visual PDF Report Designer for Oracle APEX</title></head>\n<body>\n"
        + preview + "</body></html>\n")
    print(f"vinaura-landing.html {len(page) // 1024} KB, preview.html written")


if __name__ == "__main__":
    main()
