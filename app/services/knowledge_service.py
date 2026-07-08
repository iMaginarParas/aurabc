import logging
import re
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import KCCategory, KCArticle, KCBookmark, KCReadingHistory, KCArticleLike, KCAIGeneratedDraft

logger = logging.getLogger(__name__)

# ============================================================
# CATEGORIES SEED
# ============================================================

CATEGORIES_SEED = [
    {"slug": "countries", "name": "Country Guides", "description": "Complete guides for top study destinations — visa, cost of living, scholarships, and more.", "icon": "Globe2", "color": "blue", "hero_color": "from-blue-900 to-blue-700", "display_order": 1, "is_featured": True},
    {"slug": "visa-guides", "name": "Visa Guides", "description": "Step-by-step student visa application guides for every country.", "icon": "Shield", "color": "indigo", "hero_color": "from-indigo-900 to-indigo-700", "display_order": 2, "is_featured": True},
    {"slug": "scholarships", "name": "Scholarships", "description": "Fully-funded and partial scholarships for international students.", "icon": "Award", "color": "amber", "hero_color": "from-amber-900 to-amber-700", "display_order": 3, "is_featured": True},
    {"slug": "universities", "name": "University Guides", "description": "In-depth university reviews, rankings, and admission advice.", "icon": "GraduationCap", "color": "violet", "hero_color": "from-violet-900 to-violet-700", "display_order": 4, "is_featured": True},
    {"slug": "ielts", "name": "IELTS Preparation", "description": "Expert strategies, practice tests, and tips to score 7+ in IELTS.", "icon": "BookOpen", "color": "emerald", "hero_color": "from-emerald-900 to-emerald-700", "display_order": 5, "is_featured": True},
    {"slug": "toefl", "name": "TOEFL Preparation", "description": "Comprehensive TOEFL preparation guides and resources.", "icon": "BookOpen", "color": "teal", "hero_color": "from-teal-900 to-teal-700", "display_order": 6, "is_featured": False},
    {"slug": "gre", "name": "GRE Preparation", "description": "Complete GRE preparation — Quant, Verbal, and AWA strategies.", "icon": "BarChart", "color": "purple", "hero_color": "from-purple-900 to-purple-700", "display_order": 7, "is_featured": False},
    {"slug": "gmat", "name": "GMAT Preparation", "description": "GMAT exam strategy, preparation tips, and MBA admission advice.", "icon": "TrendingUp", "color": "rose", "hero_color": "from-rose-900 to-rose-700", "display_order": 8, "is_featured": False},
    {"slug": "accommodation", "name": "Accommodation", "description": "Student housing options — on-campus, homestay, and private rentals.", "icon": "Home", "color": "orange", "hero_color": "from-orange-900 to-orange-700", "display_order": 9, "is_featured": False},
    {"slug": "education-loans", "name": "Education Loans", "description": "Compare education loan options, interest rates, and repayment plans.", "icon": "DollarSign", "color": "green", "hero_color": "from-green-900 to-green-700", "display_order": 10, "is_featured": True},
    {"slug": "student-life", "name": "Student Life", "description": "Culture, food, transport, part-time jobs, and life abroad.", "icon": "Users", "color": "pink", "hero_color": "from-pink-900 to-pink-700", "display_order": 11, "is_featured": False},
    {"slug": "pr-pathways", "name": "PR Pathways", "description": "Permanent Residency routes for international students post-graduation.", "icon": "Passport", "color": "cyan", "hero_color": "from-cyan-900 to-cyan-700", "display_order": 12, "is_featured": True},
    {"slug": "jobs-internships", "name": "Jobs & Internships", "description": "Finding part-time work, internships, and graduate jobs abroad.", "icon": "Briefcase", "color": "slate", "hero_color": "from-slate-900 to-slate-700", "display_order": 13, "is_featured": False},
    {"slug": "mbbs-abroad", "name": "MBBS Abroad", "description": "NMC-approved MBBS programs, fees, and career pathways.", "icon": "Stethoscope", "color": "red", "hero_color": "from-red-900 to-red-700", "display_order": 14, "is_featured": True},
    {"slug": "courses", "name": "Course Guides", "description": "Detailed guides for popular courses — CS, MBA, Engineering, and more.", "icon": "BookMarked", "color": "lime", "hero_color": "from-lime-900 to-lime-700", "display_order": 15, "is_featured": False},
    {"slug": "masters", "name": "Masters Programs", "description": "Complete guide to applying for a Master's degree abroad.", "icon": "GraduationCap", "color": "violet", "hero_color": "from-violet-900 to-violet-700", "display_order": 16, "is_featured": False},
    {"slug": "bachelors", "name": "Bachelors Programs", "description": "Undergraduate study abroad — requirements, costs, and timelines.", "icon": "GraduationCap", "color": "blue", "hero_color": "from-blue-900 to-blue-700", "display_order": 17, "is_featured": False},
    {"slug": "engineering", "name": "Engineering", "description": "Top engineering programs, universities, and career outcomes worldwide.", "icon": "Settings", "color": "zinc", "hero_color": "from-zinc-900 to-zinc-700", "display_order": 18, "is_featured": False},
    {"slug": "business", "name": "Business & MBA", "description": "MBA rankings, business school profiles, and career outcomes.", "icon": "TrendingUp", "color": "amber", "hero_color": "from-amber-900 to-amber-700", "display_order": 19, "is_featured": False},
    {"slug": "nursing", "name": "Nursing Abroad", "description": "Nursing programs, registration requirements, and career pathways.", "icon": "Heart", "color": "rose", "hero_color": "from-rose-900 to-rose-700", "display_order": 20, "is_featured": False},
    {"slug": "student-stories", "name": "Student Stories", "description": "Real experiences from students studying abroad.", "icon": "MessageSquare", "color": "indigo", "hero_color": "from-indigo-900 to-indigo-700", "display_order": 21, "is_featured": False},
    {"slug": "pte", "name": "PTE Preparation", "description": "PTE Academic exam strategies, practice tests, and scoring tips.", "icon": "BookOpen", "color": "teal", "hero_color": "from-teal-900 to-teal-700", "display_order": 22, "is_featured": False},
]

# ============================================================
# ARTICLES SEED DATA
# ============================================================

def make_blocks(*items):
    """Helper to create content block list."""
    return list(items)

def heading(text, level=2):
    return {"type": "heading", "level": level, "text": text, "id": re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')}

def para(text):
    return {"type": "paragraph", "text": text}

def tip(title, text):
    return {"type": "tip", "title": title, "text": text}

def warning(title, text):
    return {"type": "warning", "title": title, "text": text}

def callout(title, text, emoji="💡"):
    return {"type": "callout", "title": title, "text": text, "emoji": emoji}

def bullet_list(title, items):
    return {"type": "list", "title": title, "style": "bullet", "items": items}

def numbered_list(title, items):
    return {"type": "list", "title": title, "style": "numbered", "items": items}

def table(title, headers, rows):
    return {"type": "table", "title": title, "headers": headers, "rows": rows}

def image_block(url, caption, alt=""):
    return {"type": "image", "url": url, "caption": caption, "alt": alt or caption}


ARTICLES_SEED = [
    {
        "slug": "complete-guide-to-studying-in-canada-2025",
        "title": "Complete Guide to Studying in Canada 2025",
        "subtitle": "Everything you need to know — universities, visas, costs, scholarships, and PR pathways",
        "excerpt": "Canada is the #1 study destination for Indian students. This comprehensive guide covers every aspect — from choosing a university to getting your PR.",
        "category_slug": "countries",
        "country": "Canada",
        "tags": ["Canada", "Study Permit", "PGWP", "PR", "SDS"],
        "hero_image_url": "https://images.unsplash.com/photo-1517935706615-2717063c2225?w=1200&q=80",
        "reading_time_minutes": 15,
        "word_count": 3800,
        "difficulty": "Beginner",
        "author_name": "Priya Sharma",
        "author_role": "Canada Immigration Specialist",
        "is_featured": True,
        "seo_title": "Complete Guide to Studying in Canada 2025 | Aura Routes",
        "seo_description": "Everything Indian students need to know about studying in Canada — universities, Study Permit, SDS, PGWP, and Express Entry PR pathway.",
        "seo_keywords": ["study in Canada", "Canada student visa", "SDS Canada", "PGWP", "study permit Canada 2025"],
        "faqs": [
            {"q": "Do I need IELTS to study in Canada?", "a": "Yes. Most Canadian universities and colleges require IELTS Academic with a minimum overall band of 6.0–6.5. Some programs accept TOEFL iBT or PTE Academic."},
            {"q": "Can I work while studying in Canada?", "a": "Yes. International students with a valid study permit can work up to 20 hours per week during semester and full-time during scheduled breaks."},
            {"q": "What is the PGWP?", "a": "The Post-Graduation Work Permit (PGWP) allows you to work in Canada for up to 3 years after completing a program at a Designated Learning Institution (DLI). It is a key pathway to permanent residency."},
            {"q": "How much does it cost to study in Canada?", "a": "Tuition ranges from CAD 7,000 to CAD 35,000 per year depending on the institution and program. Living costs average CAD 12,000–20,000 per year."},
            {"q": "What is the SDS (Student Direct Stream)?", "a": "SDS is a fast-track visa program for students from India, China, Pakistan, and other countries. It offers processing in 20 days and requires a GIC of CAD 10,000 and an IELTS score of 6.0+."},
        ],
        "content_blocks": make_blocks(
            heading("Why Canada is the #1 Choice for Indian Students"),
            para("Canada consistently ranks as the top study destination for Indian students, and for good reason. With over 100 Designated Learning Institutions (DLIs), a clear pathway to Permanent Residency via Express Entry, and a welcoming multicultural environment, Canada offers everything an international student needs to succeed."),
            callout("2025 Update", "Canada issued over 900,000 study permits in 2024. The government has announced new international student caps for 2025 — always check the latest DLI status before applying.", "📢"),
            heading("Top Universities in Canada for International Students"),
            table("Top Canadian Universities", ["University", "QS Ranking 2025", "Location", "Avg Tuition (CAD/year)"], [
                ["University of Toronto", "#25", "Toronto, ON", "45,000–55,000"],
                ["University of British Columbia", "#38", "Vancouver, BC", "38,000–52,000"],
                ["McGill University", "#46", "Montreal, QC", "22,000–40,000"],
                ["University of Alberta", "#111", "Edmonton, AB", "25,000–35,000"],
                ["University of Waterloo", "#112", "Waterloo, ON", "28,000–42,000"],
                ["McMaster University", "#176", "Hamilton, ON", "24,000–38,000"],
                ["University of Calgary", "#182", "Calgary, AB", "20,000–32,000"],
                ["Simon Fraser University", "#291", "Burnaby, BC", "22,000–34,000"],
            ]),
            heading("Canada Study Permit — Step-by-Step Application"),
            numbered_list("How to Apply for a Canadian Study Permit", [
                "Receive your Letter of Acceptance (LOA) from a DLI",
                "Obtain your IELTS/TOEFL score (min 6.0 for SDS)",
                "Open a GIC (Guaranteed Investment Certificate) of CAD 10,000 with a partner bank",
                "Create a MyCIC account and complete the online application",
                "Pay the study permit fee (CAD 150) and biometrics fee (CAD 85)",
                "Submit your documents — passport, LOA, GIC, IELTS, transcripts, financial proof",
                "Attend biometrics appointment",
                "Receive your Port of Entry (POE) letter",
                "Travel to Canada and receive your study permit at the border",
            ]),
            tip("SDS Advantage", "Apply under the Student Direct Stream (SDS) for guaranteed 20-day processing. Requirements: IELTS 6.0+, GIC of CAD 10,000, and acceptance from a DLI."),
            heading("Cost of Living in Canada"),
            table("Monthly Living Costs in Canada", ["Expense", "Toronto", "Vancouver", "Montreal", "Calgary"], [
                ["Rent (1-bed)", "CAD 2,000–2,800", "CAD 2,200–3,000", "CAD 1,400–2,000", "CAD 1,500–2,200"],
                ["Groceries", "CAD 400–600", "CAD 400–600", "CAD 350–500", "CAD 380–550"],
                ["Transport (pass)", "CAD 156", "CAD 110", "CAD 94", "CAD 120"],
                ["Phone", "CAD 45–80", "CAD 45–80", "CAD 40–75", "CAD 45–80"],
                ["Total Estimate", "CAD 2,700–3,600", "CAD 2,900–3,800", "CAD 2,000–2,700", "CAD 2,100–3,000"],
            ]),
            heading("Top Scholarships for International Students in Canada"),
            bullet_list("Major Scholarships", [
                "Vanier Canada Graduate Scholarships — CAD 50,000/year for PhD students",
                "Banting Postdoctoral Fellowship — CAD 70,000/year",
                "Ontario Graduate Scholarship — CAD 10,000–15,000",
                "University of Toronto Excellence Awards",
                "UBC International Major Entrance Scholarship — up to CAD 40,000",
                "McGill Entrance Scholarships — up to CAD 12,000",
            ]),
            heading("Post-Study Work Rights — PGWP"),
            para("After graduating from a DLI, you can apply for the Post-Graduation Work Permit (PGWP). The duration is equal to your program length, up to a maximum of 3 years. Programs longer than 2 years grant a full 3-year PGWP."),
            warning("PGWP Eligibility", "Only graduates of Designated Learning Institutions (DLIs) qualify for PGWP. Private colleges that are not DLIs do NOT qualify. Always verify DLI status before enrolling."),
            heading("Canada PR Pathway After Graduation"),
            numbered_list("Express Entry for International Graduates", [
                "Obtain PGWP and start working in Canada",
                "Gain 1 year of Canadian work experience (NOC TEER 0, 1, 2, or 3)",
                "Create an Express Entry profile (CRS score determines invite)",
                "Receive Invitation to Apply (ITA)",
                "Submit PR application — processing time 6 months",
                "Become a Canadian Permanent Resident",
            ]),
            tip("CRS Boost", "Canadian work experience, provincial nomination, and French language skills significantly boost your CRS score. A score of 470+ generally receives an ITA."),
        ),
    },
    {
        "slug": "uk-student-visa-complete-guide-2025",
        "title": "UK Student Visa (CAS) — The Complete Guide for 2025",
        "subtitle": "From CAS number to Graduate Visa — everything Indian students need",
        "excerpt": "Applying for a UK Student Visa? This guide walks you through every step — CAS, biometrics, financial proof, and the 2-year Graduate Visa.",
        "category_slug": "visa-guides",
        "country": "United Kingdom",
        "tags": ["UK", "Student Visa", "CAS", "Graduate Visa", "UKVI"],
        "hero_image_url": "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=1200&q=80",
        "reading_time_minutes": 12,
        "word_count": 3000,
        "difficulty": "Intermediate",
        "author_name": "Aura Routes Team",
        "author_role": "UK Visa Specialists",
        "is_featured": True,
        "seo_title": "UK Student Visa Guide 2025 — CAS, Biometrics & Graduate Visa | Aura Routes",
        "seo_description": "Complete UK Student Visa guide 2025. Learn how to get your CAS, meet financial requirements, book biometrics, and apply for the Graduate Visa after graduation.",
        "seo_keywords": ["UK student visa 2025", "CAS number UK", "UK graduate visa", "UKVI student route", "UK study permit"],
        "faqs": [
            {"q": "What is a CAS number?", "a": "A Confirmation of Acceptance for Studies (CAS) is a unique reference number issued by your UK university. You need it to apply for a UK Student Visa. Universities typically issue CAS 2–3 months before your course starts."},
            {"q": "How much money do I need to show for a UK student visa?", "a": "You must show funds for tuition fees for the first year PLUS GBP 1,334 per month for living costs (up to 9 months) if studying in London, or GBP 1,023 per month outside London."},
            {"q": "Can I work on a UK Student Visa?", "a": "Yes. Most students can work up to 20 hours per week during term time and full-time during vacations. Degree-level students and above typically have this right — check your CAS."},
            {"q": "What is the Graduate Visa?", "a": "The UK Graduate Visa allows international graduates to stay and work in the UK for 2 years (3 years for PhD graduates). It is unsponsored and gives you full work flexibility."},
            {"q": "How long does UK student visa processing take?", "a": "The standard decision time is 3 weeks (21 working days). Priority processing (additional fee) takes 5 working days. Always apply well in advance of your course start date."},
        ],
        "content_blocks": make_blocks(
            heading("UK Student Visa — An Overview"),
            para("The UK Student Visa (formerly Tier 4) allows non-EEA students to study in the UK at degree level or above at a licensed Student Sponsor. It is managed by UK Visas and Immigration (UKVI)."),
            callout("2025 Update", "The UK government has tightened rules around student visa dependants and increased English language requirements. Ensure your university is a licensed Student Sponsor with a Highly Trusted status.", "⚠️"),
            heading("Step-by-Step UK Student Visa Application"),
            numbered_list("UK Student Visa Application Process", [
                "Receive your Unconditional Offer from a UK university",
                "Meet all conditions (IELTS, transcripts, financial proof)",
                "Receive your CAS (Confirmation of Acceptance for Studies) number",
                "Collect required documents — passport, IELTS, financial statements (28-day rule), ATAS (if required)",
                "Apply online at UKVI — pay visa fee (GBP 490) and Immigration Health Surcharge (IHS)",
                "Book and attend your biometrics appointment at a VFS/UKVCAS centre",
                "Wait for decision (3 weeks standard, 5 days priority)",
                "Collect your BRP (Biometric Residence Permit) after arrival in UK",
            ]),
            heading("Financial Requirements — The 28-Day Rule"),
            para("UKVI requires you to show that you have held the required funds for a continuous 28-day period ending within 31 days of your application date."),
            table("Financial Requirements", ["Situation", "Amount Required (GBP)"], [
                ["Studying in London (9 months)", "Tuition + (1,334 × months, max 9)"],
                ["Studying outside London (9 months)", "Tuition + (1,023 × months, max 9)"],
                ["Course under 9 months", "Tuition + monthly amount × course length"],
                ["Accepted on NHS list (reduced requirement)", "Reduced — check with university"],
            ]),
            warning("28-Day Rule", "Funds must be held for 28 consecutive days in a bank account in your name. Moving money in and out during this period can result in visa refusal."),
            heading("English Language Requirements"),
            table("UKVI Accepted English Tests", ["Test", "Minimum Score"], [
                ["IELTS Academic (UKVI)", "6.0–7.0 overall (varies by institution)"],
                ["TOEFL iBT", "72–100 (varies)"],
                ["PTE Academic", "51–65 (varies)"],
                ["Cambridge C1/C2", "169–185 (varies)"],
            ]),
            heading("The UK Graduate Visa — Stay After You Graduate"),
            para("The Graduate Visa is one of the biggest draws for international students. After graduating from a UK institution, you can apply for a 2-year visa (3 years for PhD) with no restrictions on the type of work you do."),
            bullet_list("Graduate Visa Benefits", [
                "Work for any employer in any sector",
                "No minimum salary requirement",
                "Start your own business",
                "Use the time to secure a Skilled Worker sponsor",
                "Access to NHS healthcare",
            ]),
            tip("Graduate Visa to Settlement", "Use your Graduate Visa to find an employer who can sponsor a Skilled Worker visa. After 5 years on a Skilled Worker visa, you become eligible for Indefinite Leave to Remain (ILR)."),
        ),
    },
    {
        "slug": "how-to-score-7-plus-in-ielts-complete-guide",
        "title": "How to Score 7+ in IELTS — Complete Preparation Guide 2025",
        "subtitle": "Expert strategies for Listening, Reading, Writing, and Speaking",
        "excerpt": "Scoring 7+ in IELTS requires a structured approach. This guide gives you the exact strategies, resources, and timelines used by top scorers.",
        "category_slug": "ielts",
        "country": None,
        "tags": ["IELTS", "Band 7", "Academic", "Speaking", "Writing"],
        "hero_image_url": "https://images.unsplash.com/photo-1434030216411-0b793f4b6f53?w=1200&q=80",
        "reading_time_minutes": 14,
        "word_count": 3500,
        "difficulty": "Intermediate",
        "author_name": "Rahul Verma",
        "author_role": "IELTS Expert | Band 8.5 Scorer",
        "is_featured": True,
        "seo_title": "How to Score 7+ in IELTS 2025 | Complete Preparation Guide | Aura Routes",
        "seo_description": "Proven strategies to score 7 or above in IELTS Academic. Covers all four sections with expert tips, resources, and 8-week study plan.",
        "seo_keywords": ["IELTS 7+ preparation", "IELTS academic guide", "IELTS writing tips", "IELTS speaking band 7", "IELTS study plan 2025"],
        "faqs": [
            {"q": "How long does it take to prepare for IELTS?", "a": "With 2–3 hours of daily practice, most students can prepare sufficiently in 8–12 weeks. If you're starting from a lower level, allow 3–4 months."},
            {"q": "What is the difference between IELTS Academic and IELTS General?", "a": "IELTS Academic is required for undergraduate/postgraduate university admissions. IELTS General is for work visa and immigration purposes. Always apply for Academic for student visa applications."},
            {"q": "Can I take IELTS on a computer?", "a": "Yes. IELTS on Computer (IoC) is available at many test centres. The format is identical to paper-based IELTS, but results are typically available in 3–5 days."},
            {"q": "How many times can I take IELTS?", "a": "There is no limit. You can take IELTS as many times as needed. Most test centres offer sessions almost every week."},
        ],
        "content_blocks": make_blocks(
            heading("Understanding the IELTS Band Score System"),
            table("IELTS Band Descriptors", ["Band", "Skill Level", "University Requirement"], [
                ["9.0", "Expert User", "Rare — typically for academic staff"],
                ["8.0–8.5", "Very Good User", "Top UK/Australian universities"],
                ["7.0–7.5", "Good User", "Most UK, Canadian, Australian universities"],
                ["6.5", "Competent User", "Many universities, minimum for SDS Canada"],
                ["6.0", "Competent User", "Entry level for many colleges"],
            ]),
            callout("Target Score", "Most reputable universities require IELTS 6.5–7.0 overall with no individual band below 6.0. Check your specific university's requirement.", "🎯"),
            heading("Section 1: IELTS Listening — How to Score 8+"),
            para("The Listening section has 4 recordings and 40 questions. You have 30 minutes to listen and answer, plus 10 minutes to transfer answers."),
            bullet_list("Top Listening Strategies", [
                "Preview the questions BEFORE each audio starts — you get time between sections",
                "Underline keywords in questions to listen for",
                "Be careful of British spelling — 'centre', 'programme', 'colour'",
                "Answers usually appear in order in the audio",
                "Check word limits: 'ONE WORD ONLY' means exactly one word",
                "Watch for spelling — even correct answers lose marks with typos",
            ]),
            tip("Practice Hack", "Watch BBC News, TED Talks, and British TV shows without subtitles to train your ear for native-speed English."),
            heading("Section 2: IELTS Reading — How to Score 8+"),
            para("Academic Reading has 3 passages and 40 questions in 60 minutes. Each passage gets harder. Time management is critical."),
            numbered_list("Reading Attack Strategy", [
                "Skim the entire passage in 60–90 seconds for main idea",
                "Read the questions carefully — match keywords to the text",
                "Use 'Skimming and Scanning' — do NOT read word for word",
                "Allocate: P1 = 15 min, P2 = 20 min, P3 = 25 min",
                "True/False/Not Given: 'Not Given' means the text doesn't address it — not that it's false",
                "For Matching Headings — identify the main idea of each paragraph first",
            ]),
            warning("Common Trap", "In True/False/Not Given questions, 'True' requires the statement to exactly match the text. If the text doesn't mention it at all — it's 'Not Given', not 'False'."),
            heading("Section 3: IELTS Writing — Task 1 and Task 2"),
            heading("Writing Task 1 (Academic)", 3),
            para("You must describe a visual (graph, chart, table, diagram) in at least 150 words. Write in 20 minutes. Focus on: overview, key features, data comparison."),
            callout("Task 1 Formula", "Introduction (paraphrase task) → Overview (2 main trends) → Body 1 (key group 1) → Body 2 (key group 2). Always include an overview paragraph — it's worth significant marks.", "📝"),
            heading("Writing Task 2 (Essay)", 3),
            para("You must write an academic essay in at least 250 words in 40 minutes. Essay types: Opinion, Discussion, Problem-Solution, Advantages-Disadvantages, Two-Part Question."),
            bullet_list("Task 2 Band 7+ Checklist", [
                "Answer ALL parts of the question",
                "Use a clear 4-paragraph structure: Introduction, Body 1, Body 2, Conclusion",
                "Use topic sentences to start each body paragraph",
                "Include specific examples — not just 'for example, many people...'",
                "Vary your vocabulary — avoid repeating the same words",
                "Use a range of complex sentence structures",
                "Aim for 280–320 words (more is fine, but quality > quantity)",
            ]),
            heading("Section 4: IELTS Speaking — How to Score 7+"),
            para("The Speaking test is a face-to-face interview with an examiner lasting 11–14 minutes. It has 3 parts: Introduction/Interview, Long Turn (cue card), and Discussion."),
            tip("The Examiner Is On Your Side", "IELTS examiners are trained to make you feel comfortable. Speak naturally, extend your answers, and don't worry about making minor grammatical errors — fluency matters more."),
            bullet_list("Speaking Band 7+ Strategies", [
                "Never give one-word answers — always extend",
                "Use discourse markers: 'That's a great question...', 'To be honest...', 'What I really enjoy is...'",
                "Paraphrase and rephrase naturally — don't memorise scripts",
                "Record yourself and listen back — identify fluency issues",
                "Part 2 Cue Card: spend 1 minute planning, then speak for 2 full minutes",
                "Part 3: Give opinions with reasons — 'I believe... because...'",
            ]),
            heading("8-Week IELTS Study Plan"),
            table("Study Plan by Week", ["Week", "Focus Area", "Daily Practice"], [
                ["1–2", "Diagnostic + Listening", "2 sections/day + vocabulary building"],
                ["3–4", "Reading + Vocabulary", "1 full reading test/day + academic wordlists"],
                ["5", "Writing Task 1", "1 Task 1 per day, get feedback"],
                ["6", "Writing Task 2", "1 Task 2 per day, analyse model answers"],
                ["7", "Speaking", "1 mock speaking test per day"],
                ["8", "Full Mock Tests", "2 full tests under timed conditions"],
            ]),
        ),
    },
    {
        "slug": "top-scholarships-for-indian-students-2025",
        "title": "Top 15 Scholarships for Indian Students Studying Abroad in 2025",
        "subtitle": "Fully-funded and partial scholarships you can actually win",
        "excerpt": "Scholarships can save you lakhs in tuition fees. Here are 15 real scholarships that Indian students have won — with eligibility, amounts, and how to apply.",
        "category_slug": "scholarships",
        "country": None,
        "tags": ["Scholarships", "Fully Funded", "India", "2025", "Merit-based"],
        "hero_image_url": "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=1200&q=80",
        "reading_time_minutes": 10,
        "word_count": 2500,
        "difficulty": "Beginner",
        "author_name": "Aura Routes Team",
        "author_role": "Scholarship Research Division",
        "is_featured": True,
        "seo_title": "Top 15 Scholarships for Indian Students Abroad 2025 | Aura Routes",
        "seo_description": "Discover fully-funded scholarships for Indian students in 2025 — DAAD, Chevening, Commonwealth, Australia Awards, and more with eligibility and application details.",
        "seo_keywords": ["scholarships for Indian students 2025", "fully funded scholarships India", "DAAD scholarship", "Chevening scholarship", "Commonwealth scholarship India"],
        "faqs": [
            {"q": "Do I need a high GPA to get a scholarship?", "a": "Most merit-based scholarships require a GPA of 3.0/4.0 (75%+) or above. However, many scholarships also consider leadership, community work, and financial need — not just grades."},
            {"q": "Can I apply for multiple scholarships?", "a": "Yes, in most cases. However, some scholarships prohibit holding another scholarship simultaneously. Read each scholarship's terms carefully."},
            {"q": "When should I start applying for scholarships?", "a": "Start 12–18 months before your intended enrollment date. Many deadlines fall in September–December for the following academic year."},
        ],
        "content_blocks": make_blocks(
            callout("Key Insight", "Indian students are among the most competitive internationally. In 2024, India was the top source country for Chevening, DAAD, and Australia Awards scholars.", "🏆"),
            heading("1. Chevening Scholarships (UK)"),
            para("Fully-funded scholarships for outstanding emerging leaders to pursue a one-year Master's degree in the UK. Funded by the UK Foreign, Commonwealth and Development Office."),
            table("Chevening Overview", ["Detail", "Information"], [
                ["Value", "Full tuition + living allowance + flights"],
                ["Duration", "1 year (Master's)"],
                ["Eligibility", "2+ years work experience, Bachelor's degree, IELTS 6.5+"],
                ["Deadline", "Typically November (for next year's intake)"],
                ["Apply", "chevening.org"],
            ]),
            heading("2. DAAD Scholarship (Germany)"),
            para("The German Academic Exchange Service (DAAD) offers fully-funded Master's and PhD scholarships in Germany. Germany has no tuition fees at public universities, making this an incredible value."),
            table("DAAD Overview", ["Detail", "Information"], [
                ["Value", "EUR 934/month stipend + tuition waiver + health insurance"],
                ["Duration", "12–24 months"],
                ["Eligibility", "Bachelor's with 75%+, IELTS 6.0+ or German B2"],
                ["Deadline", "October–November (varies by program)"],
                ["Apply", "daad.de"],
            ]),
            heading("3. Commonwealth Master's Scholarships (UK)"),
            para("For students from low and middle income Commonwealth countries pursuing a Master's degree in the UK. India qualifies."),
            table("Commonwealth Overview", ["Detail", "Information"], [
                ["Value", "Full tuition + flights + living allowance"],
                ["Duration", "1 year (Master's)"],
                ["Eligibility", "Bachelor's 1st class, max age 35, Indian citizen"],
                ["Apply via", "Association of Indian Universities (AIU)"],
            ]),
            heading("4. Australia Awards Scholarships"),
            para("Funded by the Australian Government for students from developing countries including India. Covers undergraduate and postgraduate programs."),
            heading("5. Erasmus Mundus Joint Masters"),
            para("The EU funds exceptional Master's programs across multiple European universities. Scholarships cover tuition, travel, and living costs across all participating countries."),
            table("Erasmus Mundus Overview", ["Detail", "Information"], [
                ["Value", "EUR 1,400/month stipend + tuition (up to EUR 9,000/year)"],
                ["Duration", "1–2 years"],
                ["Programs", "100+ joint Master's programs across Europe"],
                ["Eligibility", "Bachelor's degree, no prior Erasmus scholarship"],
            ]),
            heading("6. Government of Ireland International Education Scholarship"),
            para("50 scholarships per year for top international students from outside the EU to study full-time postgraduate programs in Ireland."),
            heading("7. New Zealand Excellence Awards"),
            para("For students from countries with which New Zealand has development partnerships, including India. Covers tuition, living costs, and airfares."),
            heading("8. GREAT Scholarships (UK)"),
            para("British Council and UK universities jointly offer scholarships of at least GBP 10,000 for Indian students. Over 200 scholarships available across multiple universities."),
            heading("9. Inlaks Shivdasani Foundation Scholarships"),
            para("For exceptional Indian students to pursue Master's programs at top international universities. Award value: up to USD 100,000."),
            heading("10. Aga Khan Foundation International Scholarship"),
            para("For outstanding Indian students from less privileged backgrounds. Covers 50% grant + 50% loan. Focused on social development and leadership."),
            heading("11. Sweden Institute Scholarships for Global Professionals"),
            para("Fully-funded Master's scholarships in Sweden for students with professional experience and a commitment to contributing to sustainable development."),
            heading("12. MEXT Scholarship (Japan)"),
            para("Japanese Government scholarships for foreign students. Covers tuition, accommodation, and monthly stipend of JPY 143,000."),
            heading("13. Ontario Graduate Scholarship (Canada)"),
            para("Merit-based scholarships of CAD 10,000–15,000 for graduate students at Ontario universities. Indian students consistently win this scholarship."),
            heading("14. University-Specific Scholarships"),
            bullet_list("Top University Scholarships", [
                "UBC International Major Entrance Scholarship — up to CAD 40,000",
                "University of Toronto Lester B. Pearson — fully funded for undergrad",
                "University of Edinburgh Global Scholarship",
                "TU Munich Excellence Scholarship (Germany)",
                "NUS Research Scholarship (Singapore)",
            ]),
            heading("15. Education Loan Subsidy Schemes (India)"),
            para("While not a 'scholarship', the Government of India's Padho Pardesh scheme and various state government schemes provide interest subsidies on education loans for minority and economically weaker section students."),
            tip("Application Strategy", "Apply for 5–8 scholarships simultaneously. Tailor your Statement of Purpose for each one. Start your Chevening application in August — it opens in August and closes in November."),
            warning("Scam Alert", "Never pay anyone to 'guarantee' a scholarship. All legitimate scholarships listed above are free to apply. Report any scholarship scams to the British Council or relevant embassy."),
        ),
    },
    {
        "slug": "australia-student-visa-subclass-500-guide",
        "title": "Australia Student Visa (Subclass 500) — Complete Guide 2025",
        "subtitle": "Everything you need to know about applying, studying, and working in Australia",
        "excerpt": "Australia Subclass 500 Student Visa — step by step guide covering GTE, financial proof, health insurance, and the 485 Graduate visa.",
        "category_slug": "visa-guides",
        "country": "Australia",
        "tags": ["Australia", "Subclass 500", "GTE", "Student Visa", "485 Visa"],
        "hero_image_url": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1200&q=80",
        "reading_time_minutes": 11,
        "word_count": 2800,
        "difficulty": "Intermediate",
        "author_name": "Aura Routes Team",
        "author_role": "Australia Immigration Specialists",
        "is_featured": False,
        "seo_title": "Australia Student Visa Subclass 500 Guide 2025 | Aura Routes",
        "seo_description": "Complete Australia Subclass 500 Student Visa guide — GTE statement, financial requirements, health insurance, work rights, and 485 Graduate visa pathway.",
        "seo_keywords": ["Australia student visa 500", "GTE statement Australia", "subclass 500", "student visa Australia 2025", "485 graduate visa"],
        "faqs": [
            {"q": "What is the GTE requirement?", "a": "The Genuine Temporary Entrant (GTE) requirement assesses whether you genuinely intend to temporarily enter Australia for study purposes. Immigration officers assess your home country ties, immigration history, and study rationale."},
            {"q": "How long does Australia student visa processing take?", "a": "Median processing time is 4–6 weeks for straightforward applications. Complex cases can take 2–4 months."},
            {"q": "Can I bring my family to Australia on a student visa?", "a": "Yes. Partners and children can apply as dependants on your student visa. They can work unlimited hours if you are enrolled in a master's or doctoral degree."},
        ],
        "content_blocks": make_blocks(
            heading("Australia Student Visa Overview"),
            para("The Subclass 500 Student Visa allows you to study full-time in a registered course at an Australian institution (CRICOS-registered). It is valid for the duration of your course plus extra time for travel."),
            heading("Eligibility Requirements"),
            bullet_list("Core Requirements", [
                "Enrollment in a CRICOS-registered course",
                "Meet GTE (Genuine Temporary Entrant) requirement",
                "IELTS 5.5–6.5+ (varies by institution)",
                "Overseas Student Health Cover (OSHC)",
                "Financial capacity proof",
                "Valid passport",
                "English language proficiency",
            ]),
            heading("The GTE Statement — How to Write It"),
            para("The GTE is the most critical part of your application. Officers assess whether you genuinely intend to study temporarily in Australia."),
            bullet_list("GTE Statement Must Include", [
                "Your specific reasons for choosing this course and institution",
                "How the course relates to your career goals and existing qualifications",
                "Your ties to your home country (family, property, employment prospects)",
                "Why you chose Australia over studying in India",
                "Your long-term plans after completing your studies",
            ]),
            tip("GTE Writing Tip", "Be specific and genuine. A generic GTE is the most common reason for visa refusal. Mention the professor's research, the specific module that aligns with your career, and your concrete plans to return."),
            heading("Financial Requirements"),
            table("Financial Proof Required", ["Expense", "Amount"], [
                ["Tuition Fees (Year 1)", "As per your CoE (Certificate of Enrolment)"],
                ["Living Costs", "AUD 24,505/year (2025 rate)"],
                ["Dependant Partner", "AUD 8,574/year additional"],
                ["Dependant Child", "AUD 3,670/year per child"],
            ]),
            heading("Work Rights on Australian Student Visa"),
            para("Students can work up to 48 hours per fortnight during study and unlimited hours during semester breaks. Master's and PhD students' partners can work without restrictions."),
            heading("485 Temporary Graduate Visa — After Graduation"),
            para("After completing an Australian qualification, you can apply for the 485 Temporary Graduate Visa to live and work in Australia."),
            table("485 Visa Duration by Qualification", ["Qualification", "485 Duration"], [
                ["Bachelor's, Honours, Master's by coursework", "2 years"],
                ["Master's by research", "3 years"],
                ["Doctoral degree (PhD)", "4 years"],
                ["STEM degree (any level)", "+2 additional years from Nov 2023"],
            ]),
        ),
    },
    {
        "slug": "education-loans-studying-abroad-complete-guide",
        "title": "Education Loans for Studying Abroad — The Complete Guide for Indian Students",
        "subtitle": "Secured vs unsecured loans, interest rates, moratorium periods, and the best banks to choose",
        "excerpt": "Education loans can fund your dream of studying abroad. This guide compares all major Indian banks and NBFCs, explains secured vs unsecured loans, and tells you exactly how to apply.",
        "category_slug": "education-loans",
        "country": None,
        "tags": ["Education Loan", "Bank of Baroda", "SBI", "HDFC Credila", "Collateral"],
        "hero_image_url": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1200&q=80",
        "reading_time_minutes": 13,
        "word_count": 3200,
        "difficulty": "Intermediate",
        "author_name": "Aura Routes Team",
        "author_role": "Education Finance Specialists",
        "is_featured": True,
        "seo_title": "Education Loans for Studying Abroad India 2025 — Bank Comparison | Aura Routes",
        "seo_description": "Complete guide to education loans for Indian students going abroad — SBI, Bank of Baroda, HDFC Credila vs Prodigy Finance. Compare interest rates, collateral, and moratorium.",
        "seo_keywords": ["education loan abroad India", "SBI education loan", "Bank of Baroda education loan", "HDFC Credila", "education loan without collateral"],
        "faqs": [
            {"q": "What is the maximum education loan I can get?", "a": "PSU banks typically offer up to INR 1.5 crore with collateral. NBFCs like HDFC Credila and Avanse can go up to INR 75 lakhs without collateral for top universities."},
            {"q": "Do I need collateral for an education loan?", "a": "Loans above INR 7.5 lakhs typically require collateral (property, FD, insurance) from PSU banks. NBFCs offer unsecured loans for top universities but at higher interest rates (11–14%)."},
            {"q": "When does loan repayment start?", "a": "Most education loans have a moratorium period: course duration + 6–12 months. Repayment starts after that. Some banks charge simple interest during the moratorium."},
        ],
        "content_blocks": make_blocks(
            heading("Why Take an Education Loan?"),
            para("Studying abroad can cost anywhere from INR 30 lakhs to INR 1.5 crore for a complete degree program. Very few students can pay this from savings alone. An education loan bridges this gap — and the interest is tax-deductible under Section 80E."),
            callout("Tax Benefit", "Under Section 80E of the Income Tax Act, you can deduct the entire interest paid on education loans with no upper limit. This benefit is available for 8 consecutive years from the year repayment starts.", "💰"),
            heading("Types of Education Loans"),
            table("Secured vs Unsecured Loans", ["Feature", "Secured (PSU Banks)", "Unsecured (NBFCs)"], [
                ["Collateral", "Required (property, FD)", "Not required (top unis)"],
                ["Loan Amount", "Up to INR 1.5 crore", "Up to INR 75 lakhs"],
                ["Interest Rate", "9.5–11.5% p.a.", "11–14% p.a."],
                ["Processing Fee", "Nil to 1%", "1–2%"],
                ["Best for", "Any university, lower rates", "Top 200 QS universities"],
            ]),
            heading("Bank-by-Bank Comparison"),
            table("Major Education Loan Providers", ["Lender", "Max Amount", "Interest Rate", "Collateral", "Moratorium"], [
                ["SBI Scholar Loan", "INR 1.5 Cr", "9.55–10.05%", "Required >7.5L", "Course + 12 months"],
                ["Bank of Baroda Baroda Vidya", "INR 1.5 Cr", "9.70–10.25%", "Required >4L", "Course + 12 months"],
                ["Axis Bank", "INR 75 Lakhs", "13.70–15.20%", "Optional", "Course + 12 months"],
                ["HDFC Credila", "INR 75 Lakhs", "11–13.5%", "Optional", "Course + 6 months"],
                ["Avanse Financial", "INR 75 Lakhs", "11.5–13%", "Optional", "Course + 6 months"],
                ["Prodigy Finance (int'l)", "USD 220,000", "7–15% (USD)", "None", "Course + 6 months"],
            ]),
            tip("Best Strategy", "Apply to PSU banks first for the lower interest rate. If rejected (due to university ranking), use HDFC Credila or Avanse as a backup. The interest rate difference of 2–3% means lakhs of rupees over 8 years."),
            heading("Documents Required for Education Loan"),
            bullet_list("Standard Document Checklist", [
                "University offer letter / admission confirmation",
                "Last 2 years academic transcripts",
                "IELTS/TOEFL score card",
                "Co-applicant (parent) KYC — Aadhaar, PAN, passport photos",
                "Co-applicant income proof — last 2 ITRs, salary slips, Form 16",
                "Co-applicant bank statements — last 6 months",
                "Collateral documents (if applicable) — property papers, FD receipts",
                "Fee structure from university",
                "Estimated living cost statement",
            ]),
            warning("Avoid These Mistakes", "1. Don't apply to multiple banks simultaneously — it lowers your CIBIL score. 2. Don't take a loan larger than needed — calculate exactly: tuition + living + insurance + travel. 3. Read the fine print on prepayment penalties."),
            heading("Section 80E Tax Deduction"),
            para("Under Section 80E, the interest paid on an education loan (taken for yourself, spouse, or children) is fully deductible from your taxable income. There is no upper limit. This benefit is available for 8 years from the year you start repayment."),
        ),
    },
    {
        "slug": "canada-pr-after-study-express-entry-guide",
        "title": "Canada PR After Study — Express Entry & PNP Guide for Graduates",
        "subtitle": "How to go from international student to Canadian Permanent Resident",
        "excerpt": "Graduating from a Canadian university is one of the best pathways to PR. This guide explains PGWP, Express Entry, CRS scores, and Provincial Nominee Programs.",
        "category_slug": "pr-pathways",
        "country": "Canada",
        "tags": ["Canada PR", "Express Entry", "PNP", "PGWP", "CRS Score"],
        "hero_image_url": "https://images.unsplash.com/photo-1503614472-8c93d56e92ce?w=1200&q=80",
        "reading_time_minutes": 12,
        "word_count": 3000,
        "difficulty": "Advanced",
        "author_name": "Priya Sharma",
        "author_role": "Canadian Immigration Consultant (RCIC)",
        "is_featured": False,
        "seo_title": "Canada PR for International Students 2025 — Express Entry Guide | Aura Routes",
        "seo_description": "Step-by-step guide to getting Canadian PR after graduating — PGWP, Express Entry, CRS score, Provincial Nominee Programs, and timeline.",
        "seo_keywords": ["Canada PR for international students", "express entry 2025", "CRS score", "PGWP to PR", "provincial nominee program"],
        "faqs": [
            {"q": "What CRS score do I need for Express Entry?", "a": "The CRS cutoff changes with every draw. Recent draws have been in the 470–510 range. Canadian work experience, strong IELTS, and provincial nomination all boost your score significantly."},
            {"q": "Which provinces are best for international students?", "a": "Ontario (OINP), British Columbia (BCPNP), Nova Scotia, New Brunswick, and Saskatchewan all have strong pathways for international graduates. Nova Scotia and New Brunswick accept lower CRS scores."},
            {"q": "Can I get PR without Canadian work experience?", "a": "It's difficult via Express Entry without Canadian experience. However, some Provincial Nominee Programs accept international graduates directly after graduation without work experience."},
        ],
        "content_blocks": make_blocks(
            heading("Overview: The International Student PR Pathway"),
            numbered_list("Typical PR Timeline for International Students", [
                "Study at a Canadian DLI (2–4 years)",
                "Graduate and apply for PGWP (Post-Graduation Work Permit)",
                "Find employment in NOC TEER 0, 1, 2, or 3",
                "Gain 1 year of Canadian work experience",
                "Create Express Entry profile",
                "Receive ITA (Invitation to Apply)",
                "Submit PR application",
                "Become a Permanent Resident",
            ]),
            heading("Step 1: PGWP — Your Bridge to PR"),
            para("The PGWP allows you to work for any employer in Canada after graduating. Its duration equals your study program length (up to 3 years). It's the most important visa for your PR pathway."),
            warning("PGWP Deadline", "You must apply for PGWP within 180 days of receiving your final marks transcript. Do not let this deadline pass — there are no extensions."),
            heading("Step 2: Building Your CRS Score"),
            table("CRS Score Factors", ["Factor", "Max Points", "How to Maximise"], [
                ["Age (18–35)", "110", "Apply earlier — each year reduces points after 29"],
                ["Education", "150", "Canadian degree/diploma adds bonus points"],
                ["Language (IELTS)", "160", "Score 8+ in all bands for maximum points"],
                ["Work Experience", "80", "Both foreign and Canadian experience count"],
                ["Canadian Work Exp.", "80 bonus", "1+ year in Canada adds significant points"],
                ["Spouse Factors", "40", "Spouse's language and education add to score"],
                ["Provincial Nomination", "600", "Instant CRS boost — almost guarantees ITA"],
            ]),
            tip("Highest Impact Actions", "Getting a provincial nomination (+600 CRS) or scoring 8+ in IELTS (+15–20 points) are the most impactful ways to improve your Express Entry ranking."),
            heading("Provincial Nominee Programs (PNPs) for Graduates"),
            table("Best PNPs for International Graduates", ["Province", "Program", "Key Requirement"], [
                ["Ontario", "OINP International Student Stream", "Job offer OR study in Ontario, NOC 0/A/B"],
                ["British Columbia", "BC PNP Skills Immigration", "Job offer from BC employer"],
                ["Nova Scotia", "NS Demand: Express Entry", "Lower CRS required, job offer OR occupation list"],
                ["New Brunswick", "NB Graduate Stay", "Graduated from NB institution"],
                ["Saskatchewan", "SINP International Graduate", "Graduated from SK institution, no job offer needed"],
                ["Alberta", "AINP — Alberta Opportunity Stream", "Working in Alberta in eligible NOC"],
            ]),
            heading("The Rural and Northern Immigration Pilot"),
            para("For students willing to settle in smaller Canadian communities, the Rural and Northern Immigration Pilot (RNIP) offers a community-driven PR pathway with lower requirements."),
            heading("Timeline: Student to PR"),
            table("Expected Timeline", ["Stage", "Duration"], [
                ["Complete program", "2–4 years"],
                ["Apply and receive PGWP", "Within 180 days of graduation"],
                ["Find qualifying employment", "1–6 months"],
                ["Gain 1 year work experience", "12 months"],
                ["Submit Express Entry profile", "Immediate"],
                ["Receive ITA", "1–12 months (CRS dependent)"],
                ["Submit PR application", "60 days after ITA"],
                ["PR approved", "6 months processing"],
                ["Total: Student to PR", "4–8 years typical"],
            ]),
        ),
    },
    {
        "slug": "mbbs-abroad-for-indian-students-complete-guide",
        "title": "MBBS Abroad for Indian Students — NMC-Approved Countries & Colleges 2025",
        "subtitle": "Complete guide to studying MBBS overseas — costs, NMC approval, FMGE, and career pathways",
        "excerpt": "MBBS abroad is a viable path for Indian students who miss domestic cutoffs. This guide covers NMC-approved countries, fees, FMGE pass rates, and the best colleges.",
        "category_slug": "mbbs-abroad",
        "country": None,
        "tags": ["MBBS", "NMC", "FMGE", "Russia", "Philippines", "Medical"],
        "hero_image_url": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=1200&q=80",
        "reading_time_minutes": 14,
        "word_count": 3600,
        "difficulty": "Intermediate",
        "author_name": "Dr. Meera Nair",
        "author_role": "Medical Education Consultant",
        "is_featured": True,
        "seo_title": "MBBS Abroad for Indian Students 2025 — NMC Approved Countries | Aura Routes",
        "seo_description": "Complete MBBS abroad guide — NMC-approved countries, fees, FMGE/NExT exam, top colleges in Russia, Philippines, Georgia, and career pathways.",
        "seo_keywords": ["MBBS abroad for Indian students", "NMC approved colleges abroad", "MBBS Russia India", "FMGE 2025", "MBBS Philippines India"],
        "faqs": [
            {"q": "Is MBBS abroad recognised in India?", "a": "Yes, if the college is NMC (National Medical Commission) approved and WHO-listed. After returning, you must pass the FMGE (now transitioning to NExT) to practice medicine in India."},
            {"q": "What is the FMGE?", "a": "The Foreign Medical Graduate Examination is a screening test by the National Board of Examinations. Students with MBBS from foreign universities must pass FMGE to get Indian medical registration. From 2025, FMGE is being replaced by NExT (National Exit Test)."},
            {"q": "Which country has the highest FMGE pass rate for Indian students?", "a": "Philippines typically has the highest FMGE pass rates (40–60%) for Indian students, partly because instruction is in English and the curriculum closely follows the Indian syllabus. Russia and China are lower at 15–25%."},
        ],
        "content_blocks": make_blocks(
            heading("Why Consider MBBS Abroad?"),
            para("India has approximately 100,000 MBBS seats for over 2 million applicants each year. Students who miss the NEET cutoff but are committed to a medical career choose MBBS abroad. When done right — choosing NMC-approved colleges and preparing seriously for FMGE — it is a fully valid career pathway."),
            callout("NEET is Required", "Even for MBBS abroad, you MUST have a valid NEET score. The minimum qualifying percentile for SC/ST is 40th, and for unreserved category students is 50th. This has been mandatory since 2018.", "⚠️"),
            heading("NMC-Approved Countries for MBBS"),
            table("Top MBBS Abroad Destinations", ["Country", "Duration", "Fee Range (INR)", "Medium", "FMGE Pass Rate"], [
                ["Russia", "6 years (incl. internship)", "18–45 Lakhs total", "English/Russian", "15–25%"],
                ["Philippines", "5.5 years (4 yr MD + 1 yr internship)", "25–50 Lakhs total", "English", "40–60%"],
                ["Georgia", "6 years (incl. internship)", "20–35 Lakhs total", "English", "25–35%"],
                ["Kazakhstan", "5 years", "15–30 Lakhs total", "English", "20–30%"],
                ["Ukraine", "6 years", "20–40 Lakhs (pre-2022)", "English", "15–25%"],
                ["China", "6 years", "25–50 Lakhs total", "English/Chinese", "15–20%"],
                ["Bangladesh", "5 years", "35–55 Lakhs total", "English", "35–45%"],
            ]),
            warning("Ukraine Status", "Due to the ongoing conflict, Ukraine is NOT recommended for new admissions. Students already enrolled should contact the NMC and their Indian embassy for guidance."),
            heading("Russia — The Most Popular Choice"),
            para("Russia hosts the largest number of Indian MBBS students globally. Top universities like Peoples' Friendship University (RUDN) and Kazan Federal University offer recognised programs."),
            bullet_list("Top Russian MBBS Universities (NMC Approved)", [
                "Peoples' Friendship University (RUDN), Moscow — INR 28–35 Lakhs total",
                "Kazan Federal University — INR 22–28 Lakhs total",
                "Ural State Medical University, Yekaterinburg",
                "Sechenov First Moscow State Medical University",
                "St. Petersburg State Pediatric Medical University",
            ]),
            heading("Philippines — Best for FMGE Success"),
            para("The Philippines is unique because it follows a 4-year BS Medicine + 1-year internship model, with instruction entirely in English. The curriculum closely mirrors the Indian and American medical education systems."),
            bullet_list("Top Philippines MBBS Colleges", [
                "University of Santo Tomas (UST), Manila — Top ranked, FMGE pass rate 50%+",
                "Our Lady of Fatima University",
                "AMA School of Medicine",
                "Davao Medical School Foundation",
                "University of Perpetual Help System DALTA",
            ]),
            tip("Philippines Advantage", "Because the Philippines uses the same textbooks as India (Harrison's, Robbins), FMGE preparation is more straightforward. Many coaching centres in India specifically prepare Philippines graduates."),
            heading("FMGE / NExT Examination"),
            para("After completing MBBS abroad, Indian students must pass the FMGE (being replaced by NExT from 2025) to obtain Indian medical registration. The exam is conducted twice a year (June and December)."),
            table("FMGE vs NExT", ["Aspect", "FMGE", "NExT"], [
                ["Full Form", "Foreign Medical Graduate Examination", "National Exit Test"],
                ["Subjects", "19 preclinical + clinical subjects", "Same subjects, integrated"],
                ["Pass Mark", "50% (150/300)", "TBD (similar threshold expected)"],
                ["Attempts", "No limit", "Limited attempts expected"],
                ["Language", "English only", "English only"],
            ]),
        ),
    },
    {
        "slug": "student-accommodation-guide-on-campus-vs-off-campus",
        "title": "Student Accommodation Abroad — On-Campus vs Off-Campus (Complete 2025 Guide)",
        "subtitle": "How to find safe, affordable student housing in Canada, UK, Australia, and more",
        "excerpt": "Where you live affects everything — budget, commute, social life, and safety. This guide breaks down all housing options for international students in top study destinations.",
        "category_slug": "accommodation",
        "country": None,
        "tags": ["Accommodation", "Student Housing", "On-campus", "Homestay", "Rent"],
        "hero_image_url": "https://images.unsplash.com/photo-1555854877-bab0e564b8d5?w=1200&q=80",
        "reading_time_minutes": 10,
        "word_count": 2500,
        "difficulty": "Beginner",
        "author_name": "Aura Routes Team",
        "author_role": "Student Life Experts",
        "is_featured": False,
        "seo_title": "Student Accommodation Abroad 2025 — On-Campus vs Off-Campus Guide | Aura Routes",
        "seo_description": "Complete student housing guide for international students — compare on-campus, off-campus, and homestay options across Canada, UK, and Australia with costs.",
        "seo_keywords": ["student accommodation abroad", "international student housing", "student housing Canada UK Australia", "off campus student accommodation"],
        "faqs": [
            {"q": "Should I book accommodation before arriving?", "a": "Absolutely yes. International students should secure accommodation at least 2–3 months before arrival. University halls fill up very quickly. Never arrive without confirmed accommodation."},
            {"q": "Is on-campus accommodation more expensive?", "a": "Not necessarily. On-campus housing in Canada/UK often includes utilities, internet, and sometimes a meal plan. When you factor in these costs in off-campus living, on-campus can sometimes be cheaper overall for first-year students."},
        ],
        "content_blocks": make_blocks(
            heading("Types of Student Accommodation"),
            heading("1. University/College Residence Halls (On-Campus)", 3),
            para("Managed by the university. Typically includes a single or shared room, internet, utilities, and sometimes a meal plan. Most secure option for first-year international students."),
            table("On-Campus Pros & Cons", ["Pros", "Cons"], [
                ["Close to classes, library, campus facilities", "Can be more expensive per sq ft"],
                ["Community — easy to make friends", "Limited privacy"],
                ["All-inclusive (utilities, internet)", "Fixed meal plans can be restrictive"],
                ["Safe and secure environment", "Less independence"],
                ["No commute time or cost", "Can fill up quickly — apply early"],
            ]),
            heading("2. Private Purpose-Built Student Accommodation (PBSA)", 3),
            para("Companies like Unite Students, Host, and Amberstudent offer purpose-built student accommodation near campuses. More expensive than halls but more modern."),
            heading("3. Private Rented Apartments/Houses", 3),
            para("Living with 2–5 students in a shared flat. Cheapest per-room option but requires managing bills, tenancy agreements, and sometimes dealing with difficult landlords."),
            heading("4. Homestay", 3),
            para("Living with a local family. Excellent for English improvement, cultural immersion, and safety. Popular for foundation year students. Includes meals."),
            heading("Average Monthly Accommodation Costs by City"),
            table("Student Accommodation Costs 2025", ["City", "On-Campus", "Shared Flat", "Homestay"], [
                ["Toronto, Canada", "CAD 1,200–1,800", "CAD 900–1,400", "CAD 1,100–1,600"],
                ["Vancouver, Canada", "CAD 1,400–2,000", "CAD 1,100–1,600", "CAD 1,200–1,800"],
                ["London, UK", "GBP 800–1,500", "GBP 700–1,200", "GBP 850–1,300"],
                ["Manchester, UK", "GBP 500–900", "GBP 450–750", "GBP 600–900"],
                ["Sydney, Australia", "AUD 400–700/week", "AUD 300–550/week", "AUD 300–450/week"],
                ["Melbourne, Australia", "AUD 350–650/week", "AUD 280–500/week", "AUD 280–420/week"],
                ["Berlin, Germany", "EUR 400–700", "EUR 350–600", "EUR 450–650"],
                ["Dublin, Ireland", "EUR 800–1,300", "EUR 700–1,100", "EUR 900–1,200"],
            ]),
            tip("Apply for On-Campus Housing Immediately", "Apply for university housing the same day you accept your offer — even if you're not sure. You can always cancel. Waiting lists form within days of offer acceptance opening."),
            heading("How to Find Off-Campus Accommodation"),
            bullet_list("Reliable Platforms by Country", [
                "Canada: Rentals.ca, Kijiji, Facebook Groups, PadMapper",
                "UK: Rightmove, Zoopla, SpareRoom, OpenRent",
                "Australia: Domain.com.au, realestate.com.au, Flatmates.com.au",
                "Germany: WG-Gesucht, ImmobilienScout24",
                "Ireland: Daft.ie, Rent.ie",
            ]),
            warning("Scam Alert", "Never pay a deposit without viewing the property (in person or via video call). Never send money via Western Union or gift cards. Use a signed tenancy agreement for every rental."),
        ),
    },
    {
        "slug": "german-student-visa-guide-2025",
        "title": "Germany Student Visa Guide 2025 — Apply, Study Free, and Stay",
        "subtitle": "No tuition fees, world-class universities, and a clear PR path — here's how",
        "excerpt": "Germany offers free education at public universities, one of the best post-study work visas in Europe, and a clear path to German citizenship. Here's everything you need to know.",
        "category_slug": "visa-guides",
        "country": "Germany",
        "tags": ["Germany", "German Student Visa", "APS", "Blocked Account", "Job Seeker Visa"],
        "hero_image_url": "https://images.unsplash.com/photo-1467269204594-9661b134dd2b?w=1200&q=80",
        "reading_time_minutes": 11,
        "word_count": 2800,
        "difficulty": "Intermediate",
        "author_name": "Aura Routes Team",
        "author_role": "Germany Education Specialists",
        "is_featured": False,
        "seo_title": "Germany Student Visa Guide 2025 — APS, Blocked Account & Job Seeker Visa | Aura Routes",
        "seo_description": "Complete Germany student visa guide for Indian students — APS certificate, blocked account, health insurance, language requirements, and job seeker visa after graduation.",
        "seo_keywords": ["Germany student visa India", "APS certificate Germany", "blocked account Germany", "study in Germany free", "German job seeker visa"],
        "faqs": [
            {"q": "Is education really free in Germany?", "a": "At public universities, there are no tuition fees for all students regardless of nationality. You only pay a semester contribution of EUR 150–350 which covers public transport and student services. Private universities in Germany do charge tuition."},
            {"q": "What is the APS certificate?", "a": "The Academic Evaluation Centre (APS) certificate is mandatory for Indian, Chinese, and Vietnamese students applying to German universities. It verifies your academic credentials. The process takes 4–8 weeks."},
            {"q": "What is the blocked account for Germany?", "a": "You must open a blocked account (Sperrkonto) and deposit EUR 11,208 (2025 rate) before applying for your visa. This proves you can fund your first year of living expenses. Providers include Fintiba, Expatrio, and Deutsche Bank."},
        ],
        "content_blocks": make_blocks(
            heading("Why Germany is an Exceptional Choice"),
            bullet_list("Germany Advantages", [
                "No tuition fees at public universities (for all nationalities)",
                "18-month Job Seeker Visa after graduation",
                "Opportunity Visa — apply without a job offer",
                "Strong STEM industry — highest demand for engineers and tech professionals",
                "Clear path to German Citizenship after 5 years",
                "Central Europe location — travel access to 26 Schengen countries",
            ]),
            heading("APS Certificate — Mandatory for Indian Students"),
            para("The APS (Akademische Prüfstelle) certificate verifies that your Indian academic credentials are genuine and comparable to German standards. It is mandatory for all Indian students applying to German universities."),
            numbered_list("APS Application Steps", [
                "Register on the APS India website (aps-india.de)",
                "Submit application with all academic documents (10th, 12th, degree transcripts)",
                "Attend the APS interview in Chennai or Delhi",
                "Receive APS certificate within 4–8 weeks",
                "Include APS certificate in your university application",
            ]),
            tip("Get APS Early", "Apply for APS as early as possible. Processing can take 8+ weeks in busy periods. Without APS, your visa application will be rejected."),
            heading("Financial Requirements — The Blocked Account"),
            para("A blocked account (Sperrkonto) is a special German bank account that holds living expense funds. It releases EUR 934/month to you once you're in Germany."),
            table("Blocked Account Providers", ["Provider", "Setup Fee", "Processing Time", "Special Features"], [
                ["Fintiba", "EUR 89/year", "1–3 days", "Fast, fully digital"],
                ["Expatrio", "EUR 89/year", "1–3 days", "Health insurance bundle available"],
                ["Deutsche Bank", "EUR 0", "4–6 weeks", "Traditional bank, slower"],
                ["Coracle", "EUR 89/year", "1–3 days", "Student focused"],
            ]),
            heading("Language Requirements"),
            para("Most Master's programs taught in German require DSH-2 or TestDaF TDN 4. English-taught programs (International Master's) require IELTS 6.5+ or TOEFL 95+."),
            heading("Post-Study — 18-Month Job Seeker Visa"),
            para("After completing your degree in Germany, you automatically qualify for an 18-month Job Seeker Visa to find qualified employment. Once employed, you switch to a work permit. After 2 years on a work permit, you can apply for a Settlement Permit (permanent residence)."),
        ),
    },
]

# ============================================================
# SEEDER FUNCTION
# ============================================================

def seed_knowledge_data(db: Session):
    """
    Seeds Knowledge Center categories and articles.
    Idempotent — skips existing records.
    """
    try:
        # Seed categories
        cat_count = db.query(KCCategory).count()
        if cat_count == 0:
            for cat_data in CATEGORIES_SEED:
                db.add(KCCategory(**cat_data))
            db.commit()
            logger.info(f"Knowledge Center: Seeded {len(CATEGORIES_SEED)} categories.")
        else:
            logger.info(f"Knowledge Center: Categories already seeded ({cat_count}).")

        # Seed articles
        art_count = db.query(KCArticle).count()
        if art_count == 0:
            for art_data in ARTICLES_SEED:
                cat_slug = art_data.pop("category_slug", None)
                cat = db.query(KCCategory).filter(KCCategory.slug == cat_slug).first()
                published_at = datetime.utcnow()
                article = KCArticle(
                    **art_data,
                    category_id=cat.id if cat else None,
                    published_at=published_at,
                    og_image=art_data.get("hero_image_url"),
                )
                db.add(article)
                # bump category article count
                if cat:
                    cat.article_count = (cat.article_count or 0) + 1
            db.commit()
            logger.info(f"Knowledge Center: Seeded {len(ARTICLES_SEED)} articles.")
        else:
            logger.info(f"Knowledge Center: Articles already seeded ({art_count}).")

    except Exception as e:
        logger.error(f"Knowledge Center seed failed: {str(e)}")
        db.rollback()


# ============================================================
# AI SERVICES
# ============================================================

def generate_article_with_ai(topic: str, category_slug: str, country: str | None, db: Session) -> dict:
    """Generates a full article using GPT-4o and stores as draft."""
    try:
        from openai import OpenAI
        from ..config import settings

        if not settings.openai_api_key:
            return {"error": "OpenAI API key not configured"}

        client = OpenAI(api_key=settings.openai_api_key)

        prompt = f"""You are an expert study abroad content writer for Aura Routes, India's leading AI study abroad platform.

Write a comprehensive, SEO-optimised article about: "{topic}"
Category: {category_slug}
{f'Country Focus: {country}' if country else ''}

Return a JSON object with:
{{
  "title": "Compelling, SEO-friendly title",
  "subtitle": "Descriptive subtitle",
  "excerpt": "2-3 sentence summary for article cards",
  "slug": "url-friendly-slug",
  "seo_title": "SEO title (under 60 chars)",
  "seo_description": "Meta description (under 160 chars)",
  "seo_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "reading_time_minutes": 10,
  "difficulty": "Beginner|Intermediate|Advanced",
  "tags": ["tag1", "tag2", "tag3"],
  "content_blocks": [
    {{"type": "paragraph", "text": "..."}},
    {{"type": "heading", "level": 2, "text": "...", "id": "slug-of-heading"}},
    {{"type": "tip", "title": "...", "text": "..."}},
    {{"type": "warning", "title": "...", "text": "..."}},
    {{"type": "callout", "title": "...", "text": "...", "emoji": "💡"}},
    {{"type": "list", "title": "...", "style": "bullet|numbered", "items": ["..."]}},
    {{"type": "table", "title": "...", "headers": ["col1", "col2"], "rows": [["val1", "val2"]]}}
  ],
  "table_of_contents": [
    {{"id": "section-id", "title": "Section Title", "level": 2}}
  ],
  "faqs": [
    {{"q": "Question?", "a": "Answer."}}
  ]
}}

Write minimum 2000 words of actual content. Include real data, statistics, and actionable advice. No placeholders."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        import json
        content = json.loads(response.choices[0].message.content)

        # Store as draft
        draft = KCAIGeneratedDraft(
            topic=topic,
            category_slug=category_slug,
            country=country,
            generated_title=content.get("title"),
            generated_slug=content.get("slug"),
            generated_content=content,
            status="draft"
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

        return {"draft_id": draft.id, "content": content}

    except Exception as e:
        logger.error(f"AI article generation failed: {str(e)}")
        return {"error": str(e)}


def ask_ai_about_article(article_title: str, article_excerpt: str, article_content: list, question: str, mode: str) -> str:
    """
    Answers a question about an article using GPT-4o-mini.
    Modes: summarize | explain | checklist | compare | custom
    """
    try:
        from openai import OpenAI
        from ..config import settings

        if not settings.openai_api_key:
            return "AI features require an OpenAI API key. Please contact support."

        client = OpenAI(api_key=settings.openai_api_key)

        # Extract text from content blocks
        text_content = []
        for block in (article_content or []):
            if block.get("type") == "paragraph":
                text_content.append(block.get("text", ""))
            elif block.get("type") == "heading":
                text_content.append(f"\n## {block.get('text', '')}\n")
            elif block.get("type") in ("tip", "warning", "callout"):
                text_content.append(f"[{block.get('type').upper()}] {block.get('title', '')}: {block.get('text', '')}")
            elif block.get("type") == "list":
                items = block.get("items", [])
                text_content.append(f"{block.get('title', '')}:\n" + "\n".join(f"- {i}" for i in items))

        article_text = "\n".join(text_content)[:8000]  # Limit context

        mode_prompts = {
            "summarize": "Summarise this article in 3 clear, concise bullet points that capture the most important takeaways.",
            "explain": "Explain the key concepts in this article in simple language that a high school student can understand.",
            "checklist": "Extract a practical action checklist from this article. Format as numbered steps the reader should take.",
            "compare": f"Based on this article, {question}",
            "custom": question,
        }

        system_prompt = f"""You are Aura AI, an expert study abroad assistant for Aura Routes. 
You are helping a student understand an article titled: "{article_title}"

Article Summary: {article_excerpt}

Full Article Content:
{article_text}

Answer in a helpful, conversational tone. Be specific and cite information from the article. 
Keep response under 400 words unless a detailed checklist is requested."""

        user_message = mode_prompts.get(mode, question)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=600,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"AI article assistant failed: {str(e)}")
        return "I'm having trouble connecting to AI right now. Please try again in a moment."


def get_personalized_articles(user_id: str, preferred_country: str | None, preferred_course: str | None, db: Session, limit: int = 6) -> list:
    """Returns personalised article recommendations based on user profile."""
    from sqlalchemy import or_, desc

    query = db.query(KCArticle).filter(
        KCArticle.is_published == True,
        KCArticle.is_active == True
    )

    filters = []
    if preferred_country:
        filters.append(KCArticle.country == preferred_country)
    if preferred_course:
        filters.append(KCArticle.category_name.ilike(f"%{preferred_course}%"))

    if filters:
        query = query.filter(or_(*filters))

    articles = query.order_by(desc(KCArticle.view_count)).limit(limit).all()

    # If not enough, fill with featured
    if len(articles) < limit:
        featured_ids = [a.id for a in articles]
        extras = db.query(KCArticle).filter(
            KCArticle.is_published == True,
            KCArticle.is_featured == True,
            ~KCArticle.id.in_(featured_ids) if featured_ids else True
        ).order_by(desc(KCArticle.view_count)).limit(limit - len(articles)).all()
        articles += extras

    return articles
