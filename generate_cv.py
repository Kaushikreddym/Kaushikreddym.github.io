#!/usr/bin/env python3
"""generate cv.typ from markdown sources."""

import re
from pathlib import Path

# ============================================================================
# utilities
# ============================================================================


def read_file(base, filename):
    """read markdown file and strip frontmatter."""
    text = (base / filename).read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3 :]
    return text.strip()


def _convert_bold_italic(text):
    """convert basic markdown styling markers."""
    bolds = []

    def save_bold(m):
        bolds.append(m.group(1))
        return f"\x00b{len(bolds) - 1}\x00"

    text = re.sub(r"\*\*(.+?)\*\*", save_bold, text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"_\1_", text)
    for i, b in enumerate(bolds):
        text = text.replace(f"\x00b{i}\x00", f"*{b}*")
    return text


def escape_typst(text):
    """sanitize input strings for output compatibility."""
    if not text:
        return ""

    text = re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\\\]^_`{|}~])', r"\1", text)
    links = []

    def save_bare_url(m):
        url = m.group(1).replace('"', '\\"')
        links.append(f'#link("{url}")')
        return f"\x00l{len(links) - 1}\x00"

    text = re.sub(r"<(https?://[^>]+)>", save_bare_url, text)

    def save_md_link(m):
        lt = m.group(1)
        url = m.group(2).replace('"', '\\"')
        lt = (
            lt.replace("\\", "\\\\")
            .replace("#", "\\#")
            .replace("@", "\\@")
            .replace("$", "\\$")
        )
        lt = _convert_bold_italic(lt)
        links.append(f'#link("{url}")[{lt}]')
        return f"\x00l{len(links) - 1}\x00"

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", save_md_link, text)

    text = (
        text.replace("\\", "\\\\")
        .replace("#", "\\#")
        .replace("@", "\\@")
        .replace("$", "\\$")
    )
    text = _convert_bold_italic(text)

    for i, link in enumerate(links):
        text = text.replace(f"\x00l{i}\x00", link)

    return text


def sentence_case(text):
    """normalize block lettering layout structures."""
    if not text:
        return ""

    normalized = re.sub(r"\s+", " ", text).strip()
    letters = [c for c in normalized if c.isalpha()]
    if not letters:
        return normalized

    if all(c.isupper() for c in letters):
        lowered = normalized.lower()
        normalized = lowered[:1].upper() + lowered[1:]

    return normalized


def format_description_lines(lines):
    """combine description elements into a segment."""
    return " #linebreak() ".join(lines) if lines else ""


def parse_table(text):
    """extract data framework from text blocks."""
    lines = [
        l.strip() for l in text.strip().split("\n") if l.strip().startswith("|")
    ]
    if len(lines) < 3:
        return []

    def split_row(line):
        cells = [c.strip() for c in line.split("|")]
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        return cells

    headers = split_row(lines[0])
    rows = []
    for line in lines[2:]:
        cells = split_row(line)
        row = {}
        for i, h in enumerate(headers):
            row[h] = cells[i] if i < len(cells) else ""
        rows.append(row)
    return rows


def extract_section(text, heading):
    """slice specific category out of target text using case-insensitive flags."""
    escaped = re.escape(heading)
    m = re.search(rf"^{escaped}\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not m:
        return ""
    start = m.end()
    
    # get header dynamic sequence match level
    level_match = re.match(r"^#+", heading)
    level = len(level_match.group()) if level_match else 2
    
    end_pat = rf"^#{{{1},{level}}}\s"
    end_m = re.search(end_pat, text[start:], re.MULTILINE)
    if end_m:
        return text[start : start + end_m.start()].strip()
    return text[start:].strip()


def parse_dropdowns(text):
    """locate inner structural components."""
    results = []
    for m in re.finditer(
        r":::\{dropdown\}\s*(.+?)\n(?::open:\n)?(.*?)\n\s*:::[ \t]*$",
        text,
        re.DOTALL | re.MULTILINE | re.IGNORECASE,
    ):
        results.append((m.group(1).strip(), m.group(2).strip()))
    return map(lambda x: (x[0], x[1]), results)


def split_entries(text):
    """segment string instances with spatial markers."""
    return [e.strip() for e in re.split(r"\n\s*\n", text.strip()) if e.strip()]


def split_hr_entries(section):
    """divide contents on markdown divider signals."""
    return [
        re.sub(r"\n\s*---+\s*$", "", block.strip())
        for block in re.split(r"\n\s*---+\s*\n", section)
        if block.strip().startswith("###")
    ]


def extract_markdown_section(text, heading):
    """isolate text segment matching specific header limits case-insensitively."""
    escaped = re.escape(heading)
    pattern = rf"^{escaped}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def parse_entry(block):
    """map fields into a unified structure dictionary."""
    title_match = re.search(r"^###\s+(.+)$", block, re.MULTILINE)
    institution_match = re.search(r"^\*\*(.+?)\*\*\s*$", block, re.MULTILINE)
    date_match = re.search(r"^📅\s*(.+?)\s*$", block, re.MULTILINE)

    return {
        "title": title_match.group(1).strip() if title_match else "",
        "institution": (
            institution_match.group(1).strip() if institution_match else ""
        ),
        "date": date_match.group(1).strip() if date_match else "",
        "body": block,
    }


def extract_bullets(body, heading):
    """parse targeted list sections case-insensitively from markdown text."""
    escaped = re.escape(heading)
    match = re.search(
        rf"\*\*{escaped}\*\*\s*\n(.*?)(?=\n\*\*|\Z)",
        body,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return []
    return [
        escape_typst(item.strip())
        for item in re.findall(r"^\s*-\s+(.*)$", match.group(1), re.MULTILINE)
    ]


def parse_bullets(text):
    """assemble structured item bullet entries cleanly."""
    items = []
    current = None
    for line in text.split("\n"):
        if re.match(r"^\s*---+\s*$", line):
            continue
        m = re.match(r"^[\-\*]\s+(.+)", line)
        if m:
            if current is not None:
                items.append(re.sub(r"\s*---+\s*$", "", current).strip())
            current = m.group(1)
        elif current is not None and line.strip():
            current += " " + line.strip()
    if current is not None:
        items.append(re.sub(r"\s*---+\s*$", "", current).strip())
    return items


def find_subsections(text):
    """gather nested lower level section divisions."""
    parts = re.split(r"^###\s+", text, flags=re.MULTILINE)
    results = []
    for part in parts[1:]:
        lines = part.split("\n", 1)
        title = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""
        results.append((title, content))
    return results


def parse_cards(text):
    """extract explicit semantic card parameters."""
    results = []
    for m in re.finditer(
        r":::\{card\}[ \t]+([^\n]+?)\n:link:\s*(.+?)\n(.*?)\n::filename*:::(?![:\{])",
        text,
        re.DOTALL | re.IGNORECASE,
    ):
        name = m.group(1).strip()
        link = m.group(2).strip()
        desc = m.group(3).strip()
        desc = re.sub(r"```\{image\}.*?```", "", desc, flags=re.DOTALL)
        desc = re.sub(r"\n+", " ", desc).strip()
        if name:
            results.append((name, link, desc))
    return results


def table_to_items(text):
    """process structural rows down into typst formats."""
    rows = parse_table(text)
    if not rows:
        return ""
    items = []
    for row in rows:
        vals = [escape_typst(v) for v in row.values() if v.strip()]
        if len(vals) >= 2:
            items.append(f"  - {vals[0]}: {', '.join(vals[1:])}")
        elif vals:
            items.append(f"  - {vals[0]}")
    return "#resume-item[\n" + "\n".join(items) + "\n]" if items else ""


# ============================================================================
# template engines
# ============================================================================


def gen_preamble():
    """generate target setup settings configurations."""
    return """#import "@preview/modern-cv:0.9.0": *

#fa-version("6")
#show "Résumé": "cv"

#set text(font: "times new roman")

#show: resume.with(
  author: (
    firstname: "Kaushik",
    lastname: "Muduchuru",
    email: "kaushik.reddy.m@gmail.com",
    phone: "(+49) 15510 527370",
    github: "GitHub",
    address: "ernst-thälmann-straße 102, 15374 müncheberg, germany",
    positions: (
      "research scientist",
    ),
    custom: (
      (text: "HomePage", icon: "house", link: "https://www.zalf.de/en/ueber_uns/mitarbeiter/pages/default_ag.aspx?idxs=x90x"),
      (text: "LinkedIn", icon: "linkedin", link: "https://www.linkedin.com/in/kaushik-muduchuru-ab911077/"),
      (text: "Scholar", icon: "google-scholar", link: "https://scholar.google.com/citations?user=MrB8A3gAAAAJ&hl=en"),
      (text: "0000-0002-8967-7872", icon: "orcid", link: "https://orcid.org/0000-0002-8967-7872"),
    ),
  ),
  // The template clips this into a fixed 4cm circle. The source photo is
  // portrait, so we render it slightly wider than the frame and nudge it left
  // (dx) so the subject is no longer snipped. Increase the negative dx to push
  // it further left; keep image width >= 4cm + |dx| to avoid a gap on the right.
  profile-picture: box(width: 4cm, height: 4cm, clip: true)[
    #place(left + horizon, dx: -3mm, image("professional-dp.png", width: 4.3cm))
  ],
  date: datetime.today().display(),
  language: "en",
  paper-size: "a4",
  accent-color: default-accent-color,
  colored-headers: true,
  show-footer: true,
  font: "Helvetica",          // <--- Overrides default "Source Sans Pro"
  header-font: "Helvetica",   // <--- Overrides default "Roboto"
)

#set heading(bookmarked: true)
#set document(title: "kaushik muduchuru - cv")"""

def gen_education(about):
    """compile target historical education profiles."""
    section = extract_section(about, "## 🎓 education")
    if not section:
        return ""

    # Updated pattern to handle looser structural variations between entries
    pattern = re.compile(
        r"###\s+(?P<degree>.+?)\n"
        r"\*\*(?P<institution>.+?)\*\*\s*\n"
        r"📅\s*(?P<date>.+?)\n"
        r"(?P<body>.*?)(?=\n\s*---|\n\s*###|\Z)",
        re.DOTALL,
    )

    lines = ["= education\n"]
    for match in pattern.finditer(section):
        degree = escape_typst(match.group("degree").strip())
        institution = escape_typst(match.group("institution").strip())
        date = escape_typst(match.group("date").strip())
        body = match.group("body")

        # 1. Base Entry Definition
        entry_block = (
            f"#resume-entry(\n"
            f"  title: [{degree}],\n"
            f"  location: [{institution}],\n"
            f"  date: [{date}],\n"
            f"  description: [],\n"  # Keep description clean to protect layouts
            f")"
        )
        lines.append(entry_block)

        # 2. Extract Thesis and Keywords safely
        bullet_items = []
        
        thesis_match = re.search(
            r"\*\*thesis:\*\*\s*\n\s*\*(.*?)\*", body, re.DOTALL | re.IGNORECASE
        )
        if thesis_match:
            thesis = sentence_case(thesis_match.group(1).strip())
            bullet_items.append(f"  - *Thesis:* {escape_typst(thesis)}")

        focus_match = re.search(
            r"\*\*(?:research areas|focus areas):\*\*\s*(.+)",
            body,
            re.IGNORECASE,
        )
        if focus_match:
            focus = sentence_case(focus_match.group(1).strip())
            bullet_items.append(f"  - *Keywords:* {escape_typst(focus)}")

        # 3. Append details via a dedicated content item block
        if bullet_items:
            item_block = "#resume-item[\n" + "\n".join(bullet_items) + "\n]"
            lines.append(item_block)

    return "\n\n".join(lines)

def gen_experiences(about):
    """gather past background profile data contents."""
    section = extract_markdown_section(about, "## 💼 experience")
    if not section:
        return ""

    entries = split_hr_entries(section)
    lines = ["= experience\n"]

    for block in entries:
        entry = parse_entry(block)
        bullet_items = []

        # 1. Gather Research Areas / Focus
        for heading in ["research areas", "research focus", "focus areas"]:
            bullets = extract_bullets(block, heading)
            if bullets:
                research = ", ".join(sentence_case(b) for b in bullets)
                bullet_items.append(f"  - *Research:* {escape_typst(research)}")
                break

        # 2. Gather Key Contributions as sub-bullets
        contributions = extract_bullets(block, "key contributions")
        for c in contributions:
            bullet_items.append(f"  - {sentence_case(c)}")

        # 3. Gather Skills
        skills_match = re.search(
            r"\*\*skills\*\*(.*?)(?=\n\*\*|\Z)", block, re.DOTALL | re.IGNORECASE
        )
        if skills_match:
            skills = re.sub(r"`", "", skills_match.group(1))
            skills = re.sub(r"\s*---+\s*", " ", skills)
            skills = re.sub(r"\s+", " ", skills).strip()
            bullet_items.append(
                f"  - *Skills:* {escape_typst(sentence_case(skills))}"
            )

        # 4. Generate the base layout entry cleanly
        institution = (
            escape_typst(entry["institution"]) if entry["institution"] else ""
        )
        entry_block = (
            f"#resume-entry(\n"
            f"  title: [{escape_typst(entry['title'])}],\n"
            f"  location: [{institution}],\n"
            f"  date: [{escape_typst(entry['date'])}],\n"
            f"  description: [],\n"  # Empty to protect date/meta alignment
            f")"
        )
        lines.append(entry_block)

        # 5. Append the formatted list block directly underneath
        if bullet_items:
            item_block = "#resume-item[\n" + "\n".join(bullet_items) + "\n]"
            lines.append(item_block)

    return "\n\n".join(lines)


def gen_skills(about):
    """compile target functional technical stack metrics."""
    section = extract_section(about, "## skills")
    if not section:
        return ""
    bullets = parse_bullets(section)
    if not bullets:
        return ""
    lines = ["= skills\n"]
    for b in bullets:
        m = re.match(r"\*\*([^*]+?):\*\*\s*(.+)", b, re.IGNORECASE)
        if not m:
            continue
        label = m.group(1).strip()
        values = [v.strip() for v in m.group(2).split(",") if v.strip()]
        items = ", ".join(f'"{v}"' for v in values)
        lines.append(f'#resume-skill-item(\n  "{label}",\n  ({items}),\n)')
    return "\n\n".join(lines)


def gen_research_areas(research):
    """create relevant core specialized study list fields."""
    section = extract_section(research, "## research areas")
    if not section:
        return ""
    bullets = parse_bullets(section)
    if not bullets:
        return ""
    items = tuple(f'"{b}"' for b in bullets)
    return (
        "= research areas\n\n"
        "#resume-skill-item(\n"
        '  "research focus",\n'
        f"  ({', '.join(items)}),\n"
        ")"
    )


def gen_patents(research):
    """compile intellectual property records data outputs."""
    section = extract_section(research, "## patents")
    if not section:
        return ""
    bullets = parse_bullets(section)
    if not bullets:
        bullets = split_entries(section)
    items = [f"  - {escape_typst(b)}" for b in bullets if b]
    if not items:
        return ""
    return "= patents\n\n#resume-item[\n" + "\n".join(items) + "\n]"


def gen_awards(awards_text):
    """compile professional recognition items matrix."""
    items = []

    # parse the awards table
    rows = parse_table(awards_text)
    for row in rows:
        year = re.sub(r"\*\*(.+?)\*\*", r"\1", row.get("Year", row.get("year", "")))
        year = re.sub(r"\*(.+?)\*", r"\1", year).strip()
        award = escape_typst(row.get("Award", row.get("award", "")))
        if award:
            items.append(f"  - {year}: {award}" if year else f"  - {award}")

    # also include the affiliations bullet list if present
    affiliations = extract_section(awards_text, "## affiliations")
    if affiliations:
        for b in parse_bullets(affiliations):
            items.append(f"  - {escape_typst(b)}")

    if not items:
        return ""
    lines = ["= awards & honors\n", "#v(0.5em)"]
    lines.append("#resume-item[\n" + "\n".join(items) + "\n]")
    return "\n\n".join(lines)


def gen_books(research):
    """extract registered bibliography book elements."""
    section = extract_section(research, "## books")
    if not section:
        return ""
    bullets = parse_bullets(section)
    if not bullets:
        return ""
    items = [f"  - {escape_typst(b)}" for b in bullets]
    return "= books\n\n#resume-item[\n" + "\n\n".join(items) + "\n]"


def gen_publications(research):
    """parse refereed publications from ### subsections in research.md."""
    section = extract_section(research, "## refereed publications")
    if not section:
        return ""

    lines = ["= refereed publications\n"]

    for title, content in find_subsections(section):
        # split on blank lines; drop bare hr separators
        raw = [e.strip() for e in re.split(r"\n\s*\n", content.strip()) if e.strip()]
        entries = [e for e in raw if not re.match(r"^-{3,}$", e)]
        items = [f"  - {escape_typst(e)}" for e in entries if e]
        if items:
            lines.append(f"\n== {escape_typst(title.lower())}\n")
            lines.append("#resume-item[\n\n" + "\n\n".join(items) + "\n]")

    return "\n".join(lines)


def gen_grants(research):
    """process financial project sponsorship files data."""
    grants = extract_section(research, "## grants")
    if not grants:
        return ""

    lines = ["= grants"]
    funded = extract_section(grants, "### funded")
    if funded:
        lines.append("\n== funded")
        for label, content in parse_dropdowns(funded):
            entries = split_entries(content)
            items = [f"  - {escape_typst(e)}" for e in entries if e]
            if items:
                lines.append(f"\n=== {label}\n")
                lines.append("#resume-item[\n" + "\n\n".join(items) + "\n]")

    pending = extract_section(grants, "### pending")
    if pending:
        lines.append("\n== pending")
        entries = split_entries(pending)
        items = [f"  - {escape_typst(e)}" for e in entries if e]
        if items:
            lines.append("\n#resume-item[\n" + "\n\n".join(items) + "\n]")

    return "\n".join(lines)


def gen_software(software):
    """list software tool distributions collections info."""
    cards = parse_cards(software)
    if not cards:
        return ""
    lines = ["= open-source software", ""]
    items = []
    for name, link, desc in cards:
        escaped_name = escape_typst(name)
        gh_path = link.replace("https://github.com/", "")
        gh_inline = f'#box(baseline: 1pt, fa-icon("github", fill: color-darknight)) #link("{link}")[{gh_path}]'
        if desc:
            items.append(
                f"  - *{escaped_name}*: {escape_typst(desc)} ({gh_inline})"
            )
        else:
            items.append(f"  - *{escaped_name}* ({gh_inline})")
    lines.append("#resume-item[\n" + "\n".join(items) + "\n]")
    return "\n".join(lines)


def gen_teaching(teaching):
    """arrange academic course delivery history segments."""
    lines = ["= teaching"]
    produced = False

    # --- Teaching Assistantships (our format) ---
    ta_section = extract_section(teaching, "## teaching assistantships")
    if ta_section:
        for inst_title, content in find_subsections(ta_section):
            date_m = re.search(r"📅\s*(.+)", content)
            date = date_m.group(1).strip() if date_m else ""
            rows = parse_table(content)
            if not rows:
                continue
            entry_block = (
                f"#resume-entry(\n"
                f"  title: [Teaching Assistant],\n"
                f"  location: [{escape_typst(inst_title)}],\n"
                f"  date: [{escape_typst(date)}],\n"
                f"  description: [],\n"
                f")"
            )
            lines.append(entry_block)
            items = []
            for row in rows:
                course = escape_typst(row.get("Course", row.get("course", "")))
                ttl = escape_typst(row.get("Title", row.get("title", "")))
                year = escape_typst(row.get("Year", row.get("year", "")))
                if course and ttl:
                    items.append(f"  - {course} ({year}) — {ttl}" if year else f"  - {course}: {ttl}")
                elif course:
                    items.append(f"  - {course}")
            if items:
                lines.append("#resume-item[\n" + "\n".join(items) + "\n]")
            produced = True

    # --- Self-paced online courses (legacy format) ---
    online = extract_section(teaching, "## self-paced online courses")
    if online:
        rows = parse_table(online)
        if rows:
            lines.append("\n== self-paced online courses\n")
            items = []
            for row in rows:
                course = escape_typst(row.get("course", ""))
                title = escape_typst(row.get("title", ""))
                website = escape_typst(row.get("website", ""))
                parts = [f"{course}: {title}"]
                if website:
                    parts.append(website)
                items.append(f"  - {', '.join(parts)}")
            lines.append("#resume-item[\n" + "\n".join(items) + "\n]")
            produced = True

    # --- Courses at <institution> (legacy format) ---
    for m in re.finditer(
        r"^## (courses at .+)$", teaching, re.MULTILINE | re.IGNORECASE
    ):
        heading = m.group(0)
        label = m.group(1)
        section = extract_section(teaching, heading)
        if not section:
            continue
        rows = parse_table(section)
        if not rows:
            continue
        lines.append(f"\n== {label}\n")
        items = []
        for row in rows:
            course = escape_typst(row.get("course", ""))
            title = escape_typst(row.get("title", ""))
            semesters = escape_typst(row.get("semesters", ""))
            items.append(f"  - {course}: {title} ({semesters})")
        lines.append("#resume-item[\n" + "\n".join(items) + "\n]")
        produced = True

    return "\n\n".join(lines) if produced else ""


def gen_mentoring(teaching):
    """gather institutional personal advisory listings."""
    mentoring = extract_section(teaching, "## mentoring")
    if not mentoring:
        return ""

    lines = ["= mentoring"]
    subsections = find_subsections(mentoring)
    for title, content in subsections:
        if "past" in title.lower():
            lines.append(f"\n== {escape_typst(title)}\n")
            dropdowns = parse_dropdowns(content)
            for dd_label, dd_content in dropdowns:
                lines.append(f"\n=== {escape_typst(dd_label)}\n")
                rows = parse_table(dd_content)
                if rows:
                    items = []
                    for row in rows:
                        vals = [
                            escape_typst(v) for v in row.values() if v.strip()
                        ]
                        items.append(f"  - {': '.join(vals)}")
                    lines.append("#resume-item[\n" + "\n".join(items) + "\n]")
        else:
            lines.append(f"\n== {escape_typst(title)}\n")
            rows = parse_table(content)
            if rows:
                items = []
                for row in rows:
                    vals = [escape_typst(v) for v in row.values() if v.strip()]
                    items.append(f"  - {': '.join(vals)}")
                lines.append("#resume-item[\n" + "\n".join(items) + "\n]")

    return "\n".join(lines)


def _gen_talks_section(talks, heading, cv_title, include_summary=False):
    """generic template constructor engine for talk modules."""
    section = extract_section(talks, heading)
    if not section:
        return ""

    lines = [f"= {cv_title}"]
    if include_summary:
        m = re.search(r"^\(.+\)$", section, re.MULTILINE)
        if m:
            lines.append(f"\n{escape_typst(m.group())}")

    dropdowns = parse_dropdowns(section)
    for label, content in dropdowns:
        bullets = parse_bullets(content)
        if bullets:
            items = [f"  - {escape_typst(b)}" for b in bullets]
            lines.append(f"\n== {label}\n")
            lines.append("#resume-item[\n" + "\n".join(items) + "\n]")

    return "\n".join(lines)


def gen_workshops(talks):
    """extract seminar events segments."""
    return _gen_talks_section(talks, "## workshop host", "workshops")


def gen_invited_talks(talks):
    """extract guest speaker talk categories."""
    return _gen_talks_section(
        talks, "## invited talks", "invited talks", include_summary=True
    )


def gen_conf_proceedings(talks):
    """gather direct presentation transcript listings."""
    section = extract_section(talks, "## conference proceedings")
    if not section:
        return ""
    entries = split_entries(section)
    items = [f"  - {escape_typst(e)}" for e in entries if e]
    if not items:
        return ""
    return "= conference proceedings\n\n#resume-item[\n" + "\n".join(items) + "\n]"


def gen_conf_presentations(talks):
    """generate formal standard summit speaker listings."""
    return _gen_talks_section(
        talks, "## conference presentations", "conference presentations"
    )


def gen_oral_presentations(talks):
    """parse oral presentations from talks.md."""
    section = extract_section(talks, "## oral presentations")
    if not section:
        return ""
    bullets = parse_bullets(section)
    items = [f"  - {escape_typst(b)}" for b in bullets if b]
    if not items:
        return ""
    return "= oral presentations\n\n#resume-item[\n" + "\n".join(items) + "\n]"


def gen_poster_presentations(talks):
    """parse poster presentations from talks.md."""
    section = extract_section(talks, "## poster presentations")
    if not section:
        return ""
    bullets = parse_bullets(section)
    items = [f"  - {escape_typst(b)}" for b in bullets if b]
    if not items:
        return ""
    return "= poster presentations\n\n#resume-item[\n" + "\n".join(items) + "\n]"


def gen_workshop_moderation(talks):
    """parse workshop moderation / organisation from talks.md."""
    section = extract_section(talks, "## workshop moderation / organisation")
    if not section:
        return ""
    bullets = parse_bullets(section)
    items = [f"  - {escape_typst(b)}" for b in bullets if b]
    if not items:
        return ""
    return "= workshop moderation\n\n#resume-item[\n" + "\n".join(items) + "\n]"


def gen_outreach(blog):
    """parse outreach and media entries from blog.md."""
    section = extract_section(blog, "## outreach & media")
    if not section:
        return ""
    bullets = parse_bullets(section)
    items = [f"  - {escape_typst(b)}" for b in bullets if b]
    if not items:
        return ""
    return "= outreach & media\n\n#resume-item[\n" + "\n".join(items) + "\n]"


def gen_services(services):
    """gather community peer evaluation service rows."""
    parts = []
    prof = extract_section(services, "## professional services")
    if prof:
        parts.append("= professional services\n")
        result = table_to_items(prof)
        if result:
            parts.append(result)

    inst = extract_section(services, "## institutional services")
    if inst:
        parts.append("= institutional services\n")
        for title, content in find_subsections(inst):
            parts.append(f"== {escape_typst(title)}\n")
            result = table_to_items(content)
            if result:
                parts.append(result)

    disc = extract_section(services, "## disciplinary services")
    if disc:
        parts.append("= disciplinary services\n")
        for title, content in find_subsections(disc):
            parts.append(f"== {escape_typst(title)}\n")
            content_escaped = escape_typst(content.strip())
            if content_escaped:
                parts.append(content_escaped)

    return "\n\n".join(p for p in parts if p)


# ============================================================================
# workflow execution dispatch
# ============================================================================


def main():
    """orchestrate generation pipeline logic sequences."""
    base = Path(__file__).parent
    pages = base / "pages"

    about = read_file(pages, "about.md")
    research = read_file(pages, "research.md")
    software = read_file(pages, "software.md")
    teaching = read_file(pages, "teaching.md")
    talks = read_file(pages, "talks.md")
    awards = read_file(pages, "awards.md")
    services = read_file(pages, "services.md")
    blog = read_file(pages, "blog.md")

    sections = [
        gen_preamble(),
        gen_education(about),
        gen_experiences(about),
        gen_skills(about),
        gen_research_areas(research),
        gen_patents(research),
        gen_awards(awards),
        gen_books(research),
        gen_publications(research),
        gen_grants(research),
        gen_outreach(blog),
        gen_software(software),
        gen_teaching(teaching),
        gen_mentoring(teaching),
        gen_oral_presentations(talks),
        gen_poster_presentations(talks),
        gen_workshop_moderation(talks),
        gen_workshops(talks),
        gen_invited_talks(talks),
        gen_conf_proceedings(talks),
        gen_conf_presentations(talks),
        gen_services(services),
    ]

    output = "\n\n".join(s for s in sections if s)
    out_path = base / "cv.typ"
    out_path.write_text(output, encoding="utf-8")
    print(f"generated {out_path} ({len(output):,} bytes)")


if __name__ == "__main__":
    main()