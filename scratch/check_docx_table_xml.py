import zipfile

docx_path = r"d:\project\frontend\public\assets\CL-2026-05-0010 - Integra Software (1).docx"

with zipfile.ZipFile(docx_path) as z:
    xml_content = z.read("word/document.xml").decode("utf-8")
    
    # Let's find index of Table tag
    tbl_idx = xml_content.find("<w:tbl>")
    if tbl_idx != -1:
        print("Found w:tbl at:", tbl_idx)
        # Let's extract first 4000 characters from tbl_idx
        print(xml_content[tbl_idx:tbl_idx+5000])
    else:
        print("No w:tbl found!")
