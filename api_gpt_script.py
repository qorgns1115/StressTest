import PyPDF2
from openai import OpenAI

from typing import Optional, List

class TextAnalyzer:
    def __init__(self, api_key: str):
        """
        텍스트 추출기 초기화
        Args:
            api_key : OpenAI API key
        """
        self.client = OpenAI(api_key=api_key)
    
    def analyze_with_gpt(self, text:str, prompt: str) -> str:
        """
        GPT를 사용하여 추출된 텍스트를 분석합니다.
        Args:
            text: 분석할 텍스트
            prompt: GPT에게 전달할 프롬프트
        Returns:
            GPT의 응답
        """
# 알고리즘 변경
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role" : "user", "content" : text}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error during GPT analysis: {str(e)}"
