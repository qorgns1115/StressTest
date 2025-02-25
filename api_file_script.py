import pdfplumber
import pytesseract
from PIL import Image
import re

def parse_api_spec_from_pdf():
        
    pdf_path = "test.pdf"

    ocr_lang = "kor+eng"

    all_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            extracted_text = page.extract_text()
            if extracted_text:
                all_text.append(extracted_text)

    full_text = "\n".join(all_text)

    return full_text
    api_blocks = re.split(r"\b\nAPI URI\s*", full_text)
    if api_blocks[0].strip() == "":
        api_blocks = api_blocks[1:]

    api_list = []

    for block in api_blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        endpoint = lines[0].strip().split()[0]
        info = {"api_endpoint": endpoint, "http_method": "", 
                "request" : {"header": [], "body": []},
                "response": {"header": [], "body": []}}   

        method_match = re.search(r"\bHTTP Method\s*([A-Z]+)", block)
        if method_match:
            info["http_method"] = method_match.group(1).strip()
            
        # find headers & bodies
        lines = block.strip().splitlines()    
        req_headers = []
        req_bodies = []
        res_headers = []
        res_bodies = []
        is_header_section = False
        is_body_section = False
        is_response = False

        for line in lines:
            if "응답 명세" in line:
                is_response = True
                is_header_section = False
                is_body_section = False
                continue

            if "요청 명세" in line:
                is_response = False
                is_header_section = False
                is_body_section = False
                continue

            if "HTTP" in line or "항목명" in line:
                continue

            if line.startswith('Header'):
                is_header_section = True
                is_body_section = False
                
                header_parts = line.split()[1:]  
                for part in header_parts:
                    if re.match(r'^[A-Za-z][\w-]+$', part):
                        if is_response :
                            res_headers.append(part)
                        else:
                            req_headers.append(part)
                continue
                
            if line.startswith('Body'):
                is_header_section = False
                is_body_section = True
                body_parts = line.split()[1:]
                for part in body_parts:
                    if re.match(r'^[a-z][\w-]*$', part):
                        if is_response:
                            res_bodies.append(part)
                        else :
                            req_bodies.append(part)
                continue
                
            if is_header_section:
                parts = line.split()
                if parts and re.match(r'^[A-Za-z][\w-]+$', parts[0]):
                    if is_response:
                        res_headers.append(parts[0])
                    else:
                        req_headers.append(parts[0])

            if is_body_section:
                parts = line.split()
                if parts :
                    first_col = parts[0]
                    if re.match(r'^[a-z][\w-]*$', first_col):
                        if is_response:
                            res_bodies.append(parts[0])
                        else:
                            req_bodies.append(parts[0])

        info["request"]["header"] = req_headers
        info["request"]["body"] = req_bodies
        info["response"]["header"] = res_headers
        info["response"]["body"] = res_bodies

        api_list.append(info)

    api_dict = {}
    for api in api_list:
        api_dict[api["api_endpoint"]] = {
            "http_method": api["http_method"],
            "request": {
                "header" : api["request"]["header"],
                "body": api["request"]["body"] 
            },
            "response" : {
                "header" : api["response"]["header"],
                "body": api["response"]["body"]
            }
        }

    # # for debug
    import json
    print(json.dumps(api_dict, indent=4, ensure_ascii=False))

    return api_dict