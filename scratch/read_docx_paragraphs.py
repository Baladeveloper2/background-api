import zipfile
import xml.etree.ElementTree as ET

docx_path = r"d:\project\frontend\public\assets\CL-2026-05-0010 - Integra Software (1).docx"

try:
    with zipfile.ZipFile(docx_path) as z:
        doc_xml = z.read("word/document.xml")
        root = ET.fromstring(doc_xml)
        
        # Namespace map
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        print("Extracting text paragraphs from docx:")
        text_runs = []
        for elem in root.iter():
            if elem.tag.endswith('t'):
                if elem.text:
                    text_runs.append(elem.text)
                    
        full_text = " ".join(text_runs)
        print("Length of text runs:", len(text_runs))
        print("Sample Text (first 2000 chars):")
        print(full_text[:2000])
except Exception as e:
    print("Error reading docx:", e)
