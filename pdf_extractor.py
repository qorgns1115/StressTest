import pdfplumber
import re

pdf_path = "test.pdf"

all_text = []
with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        extracted_text = page.extract_text()
        if extracted_text:
            all_text.append(extracted_text)

full_text = "\n".join(all_text)

# full_text에 OCR 혹은 텍스트 추출 결과가 들어있다고 가정
lines = full_text.splitlines()

# 예: "API_ENDPOINT: /CN001/membership" 형태를 찾는 정규식
api_pattern = re.compile(r"API_ENDPOINT\s*:\s*(.+)")
method_pattern = re.compile(r"HTTP_METHOD\s*:\s*(GET|POST|PUT|DELETE|PATCH)", re.IGNORECASE)
header_pattern = re.compile(r"Header\s*:\s*(.+)")
body_pattern = re.compile(r"Request\s+Body\s*:\s*(.+)")

api_endpoints = []
current_endpoint_info = {}

for line in lines:
    line = line.strip()
    # API_ENDPOINT 추출
    match_api = api_pattern.search(line)
    if match_api:
        # 이전에 수집 중이던 endpoint info를 저장
        if current_endpoint_info:
            api_endpoints.append(current_endpoint_info)
        current_endpoint_info = {"api_endpoint": match_api.group(1).strip()}
        continue

    # HTTP_METHOD 추출
    match_method = method_pattern.search(line)
    if match_method and current_endpoint_info:
        current_endpoint_info["http_method"] = match_method.group(1).strip().upper()
        continue

    # Header 추출
    match_header = header_pattern.search(line)
    if match_header and current_endpoint_info:
        current_endpoint_info["header"] = match_header.group(1).strip()
        continue

    # Request Body 추출
    match_body = body_pattern.search(line)
    if match_body and current_endpoint_info:
        current_endpoint_info["request_body"] = match_body.group(1).strip()
        continue

# 마지막 API 정보 저장
if current_endpoint_info:
    api_endpoints.append(current_endpoint_info)

print(api_endpoints)

