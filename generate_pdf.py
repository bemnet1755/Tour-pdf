from pathlib import Path

INPUT = Path('addis_ababa_travel_guide_content.md')
OUTPUT = Path('addis_ababa_travel_guide.pdf')


def clean_line(line: str) -> str:
    line = line.rstrip('\n')
    # light markdown cleanup for readable PDF
    replacements = [
        ('**', ''),
        ('`', ''),
        ('---', ''),
    ]
    for a, b in replacements:
        line = line.replace(a, b)
    if line.startswith('#### '):
        line = '• ' + line[5:]
    elif line.startswith('### '):
        line = line[4:].upper()
    elif line.startswith('## '):
        line = line[3:].upper()
    elif line.startswith('# '):
        line = line[2:].upper()
    return line


def wrap_text(text: str, width: int = 95):
    if not text:
        return ['']
    words = text.split(' ')
    lines = []
    current = ''
    for w in words:
        candidate = (current + ' ' + w).strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def pdf_escape(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def build_pdf_pages(lines):
    # A4 points: 595x842
    page_w, page_h = 595, 842
    margin_left, margin_top, margin_bottom = 48, 60, 50
    line_h = 13
    max_lines = (page_h - margin_top - margin_bottom) // line_h

    pages = []
    cur = []
    for line in lines:
        if len(cur) >= max_lines:
            pages.append(cur)
            cur = []
        cur.append(line)
    if cur:
        pages.append(cur)

    contents = []
    for page_no, page_lines in enumerate(pages, start=1):
        y = page_h - margin_top
        ops = ['BT', f'/F1 11 Tf', f'{margin_left} {y} Td']
        first = True
        for ln in page_lines:
            text = pdf_escape(ln)
            if first:
                ops.append(f'({text}) Tj')
                first = False
            else:
                ops.append(f'0 -{line_h} Td')
                ops.append(f'({text}) Tj')
        # footer
        ops.append(f'0 -{line_h*2} Td')
        ops.append(f'(Page {page_no} of {len(pages)}) Tj')
        ops.append('ET')
        data = '\n'.join(ops).encode('latin-1', 'replace')
        contents.append(data)
    return pages, contents


def write_pdf(content_streams):
    objects = []

    def add_obj(data: bytes) -> int:
        objects.append(data)
        return len(objects)

    font_obj = add_obj(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')

    page_objs = []
    content_obj_ids = []
    for stream in content_streams:
        stream_obj = b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream'
        content_obj_ids.append(add_obj(stream_obj))

    pages_kids_placeholder = []
    pages_obj_id = add_obj(b'')  # placeholder for pages tree

    for cobj in content_obj_ids:
        page_dict = (
            f'<< /Type /Page /Parent {pages_obj_id} 0 R /MediaBox [0 0 595 842] '
            f'/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {cobj} 0 R >>'
        ).encode('latin-1')
        page_objs.append(add_obj(page_dict))

    kids = ' '.join(f'{pid} 0 R' for pid in page_objs)
    pages_dict = f'<< /Type /Pages /Kids [{kids}] /Count {len(page_objs)} >>'.encode('latin-1')
    objects[pages_obj_id - 1] = pages_dict

    catalog_obj = add_obj(f'<< /Type /Catalog /Pages {pages_obj_id} 0 R >>'.encode('latin-1'))

    # write file
    out = bytearray(b'%PDF-1.4\n')
    xref = [0]
    for i, obj in enumerate(objects, start=1):
        xref.append(len(out))
        out.extend(f'{i} 0 obj\n'.encode('latin-1'))
        out.extend(obj)
        out.extend(b'\nendobj\n')

    xref_start = len(out)
    out.extend(f'xref\n0 {len(objects)+1}\n'.encode('latin-1'))
    out.extend(b'0000000000 65535 f \n')
    for off in xref[1:]:
        out.extend(f'{off:010d} 00000 n \n'.encode('latin-1'))

    out.extend(
        f'trailer\n<< /Size {len(objects)+1} /Root {catalog_obj} 0 R >>\nstartxref\n{xref_start}\n%%EOF\n'.encode('latin-1')
    )

    OUTPUT.write_bytes(out)


def main():
    raw = INPUT.read_text(encoding='utf-8').splitlines()
    lines = []
    for ln in raw:
        cl = clean_line(ln)
        wrapped = wrap_text(cl)
        lines.extend(wrapped)
    _, streams = build_pdf_pages(lines)
    write_pdf(streams)
    print(f'Generated {OUTPUT} ({OUTPUT.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
