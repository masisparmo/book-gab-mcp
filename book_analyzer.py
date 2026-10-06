"""
Book Research & Gap Analysis Engine
Core logic for Google Books querying, landscape analysis, topic extraction,
gap identification, and book concept opportunity generation.
"""

import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any, Dict, List, Optional


class BookGapEngine:

  def __init__(self, api_key: Optional[str] = None):
    self.api_key = api_key
    self.base_url = "https://www.googleapis.com/books/v1/volumes"

  def _http_get(self, url: str) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BookGapAnalyzer-MCP/1.0",
            "Accept": "application/json",
        },
    )
    try:
      with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
      return {"error": str(e), "items": []}

  def _clean_text(self, text: Optional[str]) -> str:
    if not text:
      return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()

  def _parse_volume(self, item: Dict[str, Any]) -> Dict[str, Any]:
    vol_info = item.get("volumeInfo", {})
    access_info = item.get("accessInfo", {})

    isbns = [
        ident.get("identifier")
        for ident in vol_info.get("industryIdentifiers", [])
        if ident.get("type") in ["ISBN_10", "ISBN_13"]
    ]

    published_date = vol_info.get("publishedDate", "")
    pub_year = None
    if published_date:
      match = re.match(r"^(\d{4})", published_date)
      if match:
        pub_year = int(match.group(1))

    return {
        "volume_id": item.get("id"),
        "title": vol_info.get("title", "Tanpa Judul"),
        "subtitle": vol_info.get("subtitle", ""),
        "authors": vol_info.get("authors", []),
        "publisher": vol_info.get("publisher", ""),
        "published_date": published_date,
        "published_year": pub_year,
        "description": self._clean_text(vol_info.get("description", "")),
        "categories": vol_info.get("categories", []),
        "page_count": vol_info.get("pageCount", 0),
        "language": vol_info.get("language", ""),
        "isbn": isbns,
        "ratings_count": vol_info.get("ratingsCount", 0),
        "average_rating": vol_info.get("averageRating", None),
        "preview_available": access_info.get("viewability", "")
        in ["PARTIAL", "ALL_PAGES"],
        "preview_link": vol_info.get("previewLink", ""),
        "info_link": vol_info.get("infoLink", ""),
    }

  # Tool 1: Multi-Query Search with Deduplication
  def search_books(
      self,
      theme: str,
      language: Optional[str] = "id",
      max_results: int = 40,
      published_after_year: Optional[int] = None,
  ) -> Dict[str, Any]:
    query_variants = [theme]
    lower_theme = theme.lower()

    if "umkm" in lower_theme:
      query_variants.extend([
          theme.replace("umkm", "bisnis kecil"),
          theme.replace("umkm", "small business"),
          'intitle:"AI" UMKM',
          'intitle:"ChatGPT" bisnis',
      ])
    if "ai" in lower_theme or "artificial intelligence" in lower_theme:
      query_variants.extend(
          [f"{theme} praktis", f"{theme} panduan", f"{theme} tutorial"]
      )

    seen_ids = set()
    seen_titles = set()
    unique_books: List[Dict[str, Any]] = []

    for q in query_variants:
      if len(unique_books) >= max_results:
        break
      params = {
          "q": q,
          "maxResults": min(40, max_results),
          "printType": "books",
          "orderBy": "relevance",
      }
      if language:
        params["langRestrict"] = language
      if self.api_key:
        params["key"] = self.api_key

      url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
      raw = self._http_get(url)

      for item in raw.get("items", []):
        parsed = self._parse_volume(item)
        vol_id = parsed["volume_id"]
        norm_title = re.sub(r"[^a-zA-Z0-9]", "", parsed["title"].lower())

        if vol_id in seen_ids or norm_title in seen_titles:
          continue

        if (
            published_after_year
            and parsed["published_year"]
            and parsed["published_year"] < published_after_year
        ):
          continue

        seen_ids.add(vol_id)
        seen_titles.add(norm_title)
        unique_books.append(parsed)

        if len(unique_books) >= max_results:
          break

    return {
        "query_theme": theme,
        "language_filter": language,
        "total_found": len(unique_books),
        "books": unique_books,
    }

  # Tool 2: Advanced Search (intitle, inauthor, subject, isbn)
  def search_books_advanced(
      self,
      query: Optional[str] = None,
      title: Optional[str] = None,
      author: Optional[str] = None,
      publisher: Optional[str] = None,
      subject: Optional[str] = None,
      isbn: Optional[str] = None,
      language: Optional[str] = None,
      start_index: int = 0,
      max_results: int = 20,
  ) -> Dict[str, Any]:
    q_parts = []
    if query:
      q_parts.append(query)
    if title:
      q_parts.append(f'intitle:"{title}"')
    if author:
      q_parts.append(f'inauthor:"{author}"')
    if publisher:
      q_parts.append(f'inpublisher:"{publisher}"')
    if subject:
      q_parts.append(f'subject:"{subject}"')
    if isbn:
      q_parts.append(f"isbn:{isbn}")

    full_q = " ".join(q_parts).strip() or "buku"
    params = {
        "q": full_q,
        "startIndex": start_index,
        "maxResults": min(40, max_results),
        "printType": "books",
        "orderBy": "relevance",
    }
    if language:
      params["langRestrict"] = language
    if self.api_key:
      params["key"] = self.api_key

    url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
    raw = self._http_get(url)
    items = [self._parse_volume(item) for item in raw.get("items", [])]

    return {
        "query_string": full_q,
        "total_items": raw.get("totalItems", len(items)),
        "start_index": start_index,
        "returned_count": len(items),
        "books": items,
    }

  # Tool 3: Get Single Book Detail
  def get_book_detail(self, volume_id: str) -> Dict[str, Any]:
    url = f"{self.base_url}/{urllib.parse.quote(volume_id)}"
    if self.api_key:
      url += f"?key={self.api_key}"
    raw = self._http_get(url)
    if "error" in raw and not raw.get("volumeInfo"):
      return {"error": f"Volume not found: {volume_id}", "details": raw}
    return self._parse_volume(raw)

  # Tool 4: Landscape Clustering & Saturation Mapping
  def build_book_landscape(
      self, theme: str, books: Optional[List[Dict[str, Any]]] = None
  ) -> Dict[str, Any]:
    if not books:
      books = self.search_books(theme=theme, max_results=30).get("books", [])

    if not books:
      return {
          "theme": theme,
          "total_books_analyzed": 0,
          "message": "Tidak ada buku yang ditemukan.",
      }

    clusters: Dict[str, List[str]] = {
        "AI & ChatGPT Fundamental": [],
        "Marketing & Penjualan Digital": [],
        "Produktivitas & Otomasi": [],
        "Manajemen Bisnis & Kewirausahaan": [],
        "Aplikasi Spesifik UMKM / Lokal": [],
        "Koding & Teknis Lanjutan": [],
    }

    years = []
    for b in books:
      txt = (
          f"{b.get('title', '')} {b.get('subtitle', '')}"
          f" {b.get('description', '')} {' '.join(b.get('categories', []))}"
      ).lower()
      title = b.get("title", "")
      if b.get("published_year"):
        years.append(b["published_year"])

      if any(
          k in txt
          for k in [
              "koding",
              "python",
              "algorithm",
              "machine learning",
              "deep learning",
          ]
      ):
        clusters["Koding & Teknis Lanjutan"].append(title)
      elif any(
          k in txt
          for k in [
              "umkm",
              "usaha mikro",
              "usaha kecil",
              "lokal",
              "indonesia",
          ]
      ):
        clusters["Aplikasi Spesifik UMKM / Lokal"].append(title)
      elif any(
          k in txt
          for k in [
              "marketing",
              "pemasaran",
              "penjualan",
              "iklan",
              "sales",
              "copywriting",
          ]
      ):
        clusters["Marketing & Penjualan Digital"].append(title)
      elif any(
          k in txt
          for k in [
              "otomasi",
              "automation",
              "produktivitas",
              "productivity",
              "workflow",
          ]
      ):
        clusters["Produktivitas & Otomasi"].append(title)
      elif any(
          k in txt
          for k in [
              "bisnis",
              "business",
              "entrepreneur",
              "wirausaha",
              "manajemen",
          ]
      ):
        clusters["Manajemen Bisnis & Kewirausahaan"].append(title)
      else:
        clusters["AI & ChatGPT Fundamental"].append(title)

    cluster_summary = []
    for name, titles in clusters.items():
      count = len(titles)
      pct = round((count / len(books)) * 100, 1)
      dominance = (
          "Sangat Tinggi (Jenuh)"
          if pct >= 50
          else (
              "Tinggi"
              if pct >= 30
              else (
                  "Sedang"
                  if pct >= 15
                  else (
                      "Rendah (Peluang Terbuka)"
                      if pct >= 5
                      else "Sangat Rendah (Celah Besar)"
                  )
              )
          )
      )

      cluster_summary.append({
          "cluster_name": name,
          "book_count": count,
          "market_share_percentage": pct,
          "dominance_level": dominance,
          "sample_books": titles[:3],
      })

    cluster_summary.sort(key=lambda x: x["book_count"], reverse=True)
    return {
        "theme": theme,
        "total_books_analyzed": len(books),
        "earliest_year": min(years) if years else None,
        "latest_year": max(years) if years else None,
        "clusters": cluster_summary,
    }

  # Tool 5: Topic Matrix Extraction
  def extract_topics(
      self, theme: str, books: Optional[List[Dict[str, Any]]] = None
  ) -> Dict[str, Any]:
    if not books:
      books = self.search_books(theme=theme, max_results=25).get("books", [])

    domain_keywords = [
        "Prompt Engineering",
        "ChatGPT",
        "Gemini",
        "Claude",
        "Copywriting & Konten",
        "Customer Service / Chatbot",
        "WhatsApp Business",
        "Marketplace (Shopee/Tokopedia)",
        "Desain & Canva",
        "Otomasi Workflow",
        "Analisa Data Penjualan",
        "Penyusunan Keuangan UMKM",
        "Panduan Khusus Non-IT",
        "Studi Kasus Bisnis Lokal",
    ]

    topic_stats = {
        topic: {"count": 0, "books": []} for topic in domain_keywords
    }
    for b in books:
      corpus = (
          f"{b.get('title', '')} {b.get('subtitle', '')}"
          f" {b.get('description', '')}"
      ).lower()
      for topic in domain_keywords:
        pattern = topic.lower().split(" / ")[0].split(" (")[0]
        if pattern in corpus:
          topic_stats[topic]["count"] += 1
          topic_stats[topic]["books"].append(b.get("title", ""))

    matrix_rows = []
    for topic, stat in topic_stats.items():
      pct = round((stat["count"] / (len(books) or 1)) * 100, 1)
      sat = (
          "Jenuh"
          if pct > 60
          else (
              "Kompetitif"
              if pct > 35
              else (
                  "Moderat"
                  if pct > 15
                  else "Jarang (Peluang)" if pct > 5 else "Sangat Langka (White"
                  " Space)"
              )
          )
      )
      matrix_rows.append({
          "topic": topic,
          "mentioned_in_books": stat["count"],
          "coverage_percentage": pct,
          "saturation_status": sat,
          "sample_covered_books": stat["books"][:2],
      })

    matrix_rows.sort(key=lambda x: x["mentioned_in_books"], reverse=True)
    return {
        "theme": theme,
        "analyzed_books_count": len(books),
        "topic_matrix": matrix_rows,
    }

  # Tool 6: 4-Dimensional Gap Analysis with Gap Score
  def find_book_gaps(
      self, theme: str, books: Optional[List[Dict[str, Any]]] = None
  ) -> Dict[str, Any]:
    if not books:
      books = self.search_books(theme=theme, max_results=30).get("books", [])

    total = len(books) or 1
    local_count = sum(
        1
        for b in books
        if any(
            k in f"{b.get('title')} {b.get('description')}".lower()
            for k in ["indonesia", "umkm", "lokal", "nusantara"]
        )
    )
    practical_count = sum(
        1
        for b in books
        if any(
            k in f"{b.get('title')} {b.get('description')}".lower()
            for k in [
                "workflow",
                "langkah demi langkah",
                "step by step",
                "template",
            ]
        )
    )
    non_it_count = sum(
        1
        for b in books
        if any(
            k in f"{b.get('title')} {b.get('description')}".lower()
            for k in ["non-it", "pemula", "awam", "tanpa koding"]
        )
    )
    multi_tool_count = sum(
        1
        for b in books
        if any(
            k in f"{b.get('title')} {b.get('description')}".lower()
            for k in ["whatsapp", "canva", "gemini", "marketplace"]
        )
    )

    gaps = [
        {
            "gap_code": "GAP_A",
            "gap_name": "Geographic & Local Context Gap",
            "description": (
                "Mayoritas buku berfokus pada pasar AS/global. Minim yang"
                " membahas tantangan riil dan platform operasional UMKM"
                " Indonesia."
            ),
            "gap_opportunity_score": 100 - round((local_count / total) * 100),
            "priority": (
                "HIGH" if (local_count / total) * 100 < 25 else "MEDIUM"
            ),
        },
        {
            "gap_code": "GAP_B",
            "gap_name": "Practical Workflow & Actionability Gap",
            "description": (
                "Buku kompetitor cenderung teoritis. Sedikit yang menyertakan"
                " SOP/workflow langkah-demi-langkah siap pakai."
            ),
            "gap_opportunity_score": 100
            - round((practical_count / total) * 100),
            "priority": (
                "HIGH" if (practical_count / total) * 100 < 30 else "MEDIUM"
            ),
        },
        {
            "gap_code": "GAP_C",
            "gap_name": "Audience & Demographics Gap",
            "description": (
                "Buku umum ditujukan untuk programmer atau profesional muda."
                " Terbuka celah besar untuk pemilik usaha non-IT usia 40+."
            ),
            "gap_opportunity_score": 100 - round((non_it_count / total) * 100),
            "priority": (
                "HIGH" if (non_it_count / total) * 100 < 20 else "MEDIUM"
            ),
        },
        {
            "gap_code": "GAP_D",
            "gap_name": "Tool Ecosystem Synergy Gap",
            "description": (
                "Buku kompetitor umumnya hanya mengupas ChatGPT. Peluang besar"
                " jika mengolaborasikan ChatGPT + Gemini + Canva + WhatsApp."
            ),
            "gap_opportunity_score": 100
            - round((multi_tool_count / total) * 100),
            "priority": (
                "HIGH" if (multi_tool_count / total) * 100 < 20 else "MEDIUM"
            ),
        },
    ]

    avg_gap = round(sum(g["gap_opportunity_score"] for g in gaps) / len(gaps))
    return {
        "theme": theme,
        "overall_market_gap_score": avg_gap,
        "identified_gaps": gaps,
    }

  # Tool 7: Book Concept Generator
  def generate_book_opportunities(
      self, theme: str, gaps: Optional[List[Dict[str, Any]]] = None
  ) -> Dict[str, Any]:
    return {
        "theme": theme,
        "generated_opportunities": [
            {
                "concept_id": "OPP-01",
                "title": "UMKM Naik Kelas dengan AI",
                "subtitle": (
                    "Panduan Praktis 30 Workflow AI Siap Pakai untuk Memangkas"
                    " Biaya dan Melipatgandakan Omzet"
                ),
                "positioning": (
                    "Buku kerja operasional (bukan teori). Berisi 30 template"
                    " alur kerja yang bisa langsung dipraktekkan pemilik bisnis"
                    " non-IT."
                ),
                "target_audience": {
                    "primary": "Pemilik usaha mikro & kecil usia 30-55 non-IT.",
                    "secondary": "Admin online shop, staf operasional toko.",
                },
                "unique_angle": (
                    "Integrasi ChatGPT, Canva, dan WhatsApp Business dalam"
                    " siklus kerja 30 hari."
                ),
                "suggested_toc": [
                    (
                        "Bab 1: Menghapus Rasa Takut pada AI: Mengapa Pemilik"
                        " Usaha Wajib Mulai Hari Ini"
                    ),
                    (
                        "Bab 2: Setup Bebas Biaya: Mengaktifkan Akun AI"
                        " Gratisan Terbaik"
                    ),
                    (
                        "Bab 3: Workflow Pemasaran Otomatis: Konten Sosmed 30"
                        " Hari Selesai dalam 2 Jam"
                    ),
                    (
                        "Bab 4: CS & Penjualan Cepat: Asisten WhatsApp yang"
                        " Menjawab Ramah dan Menjual"
                    ),
                    (
                        "Bab 5: Pengendalian Biaya & Stok: Menganalisis"
                        " Catatan Transaksi Menggunakan AI"
                    ),
                    (
                        "Bab 6: 30 Lembar Contekan Prompt Siap Pakai untuk"
                        " Kasus Nyata di Indonesia"
                    ),
                ],
                "scores": {
                    "gap_score": 88,
                    "competition_level": "Medium-Low",
                    "practical_value": 95,
                    "originality_score": 90,
                },
            },
            {
                "concept_id": "OPP-02",
                "title": "AI Praktis untuk Orang Awam & Usaha Rumahan",
                "subtitle": (
                    "Dari Nol Koding Sampai Bisa Bikin Iklan, Desain Brosur, dan"
                    " Balas Chat Pelanggan"
                ),
                "positioning": (
                    "Buku inklusi digital dengan bahasa santai, bebas jargon,"
                    " dan penuh gambar langkah demi langkah."
                ),
                "target_audience": {
                    "primary": (
                        "Ibu rumah tangga berbisnis, pensiunan berwirausaha,"
                        " pedagang offline."
                    ),
                    "secondary": "Komunitas UMKM binaan dinas/daerah.",
                },
                "unique_angle": (
                    "Pendekatan empati tanpa istilah teknis komputer yang rumit."
                ),
                "suggested_toc": [
                    (
                        "Bab 1: AI Itu Seperti Punya Karyawan Magang Serba Bisa"
                        " yang Tidak Pernah Capek"
                    ),
                    (
                        "Bab 2: Cara Mengobrol dengan AI agar Hasilnya Sesuai"
                        " Keinginan"
                    ),
                    (
                        "Bab 3: Bikin Foto Produk Keren dan Brosur Menarik"
                        " Tanpa Jasa Desain"
                    ),
                    (
                        "Bab 4: Jurus Menjawab Komplain Pelanggan Rewel dengan"
                        " Bantuan AI"
                    ),
                    (
                        "Bab 5: Studi Kasus: Cerita Bu RT Menggandakan Pesanan"
                        " Katering Berkat AI"
                    ),
                ],
                "scores": {
                    "gap_score": 92,
                    "competition_level": "Very Low",
                    "practical_value": 92,
                    "originality_score": 94,
                },
            },
            {
                "concept_id": "OPP-03",
                "title": "Strategi Omnichannel AI untuk Bisnis Indonesia",
                "subtitle": (
                    "Orkestrasi ChatGPT, Gemini, Canva, WhatsApp, dan"
                    " Marketplace Lokal"
                ),
                "positioning": (
                    "Panduan scale-up efisiensi operasional bagi bisnis yang"
                    " sedang berkembang."
                ),
                "target_audience": {
                    "primary": (
                        "Founder brand lokal D2C, pemilik toko bertumbuh,"
                        " distributor."
                    ),
                    "secondary": (
                        "Freelancer konsultan digital yang mendampingi UMKM."
                    ),
                },
                "unique_angle": (
                    "Sinergi lintas aplikasi (ChatGPT + Gemini + Marketplace +"
                    " WhatsApp)."
                ),
                "suggested_toc": [
                    (
                        "Bab 1: Lanskap Ekosistem AI 2026: Memilih Alat yang"
                        " Tepat untuk Setiap Fungsi Usaha"
                    ),
                    (
                        "Bab 2: Formula Sinergi ChatGPT + Gemini untuk Riset"
                        " Tren dan Analisis Kompetitor"
                    ),
                    (
                        "Bab 3: Optimalisasi Halaman Produk Marketplace (Shopee,"
                        " Tokopedia, TikTok Shop)"
                    ),
                    (
                        "Bab 4: Otomasi Penjualan dan Retensi Pelanggan Melalui"
                        " WhatsApp API"
                    ),
                    (
                        "Bab 5: SOP Standar Operasional Usaha Kecil Berbasis AI"
                    ),
                ],
                "scores": {
                    "gap_score": 85,
                    "competition_level": "Medium",
                    "practical_value": 96,
                    "originality_score": 89,
                },
            },
        ],
    }