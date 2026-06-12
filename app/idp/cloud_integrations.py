import os
import logging
from typing import Tuple, Optional, Any

logger = logging.getLogger("idp.cloud_integrations")

class CloudOCREngines:
    @staticmethod
    def load_google_vision() -> Optional[Any]:
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            return None
        try:
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()
            logger.info("Google Vision API loaded.")
            return client
        except Exception as e:
            logger.warning(f"Google Vision unavailable: {e}")
            return None

    @staticmethod
    def run_google_vision(client, img_bytes: bytes) -> Tuple[str, float]:
        try:
            from google.cloud import vision
            image = vision.Image(content=img_bytes)
            response = client.document_text_detection(image=image)
            text = response.full_text_annotation.text
            
            # Simple confidence estimation
            confidences = []
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            confidences.append(word.confidence)
            avg_conf = (sum(confidences) / len(confidences)) * 100 if confidences else 85.0
            return text, avg_conf
        except Exception as e:
            logger.error(f"Google Vision failed: {e}")
            raise

    @staticmethod
    def load_azure_document_ai() -> Optional[Any]:
        endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        if not endpoint or not key:
            return None
        try:
            from azure.ai.formrecognizer import DocumentAnalysisClient
            from azure.core.credentials import AzureKeyCredential
            client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
            logger.info("Azure Document AI loaded.")
            return client
        except Exception as e:
            logger.warning(f"Azure Document AI unavailable: {e}")
            return None

    @staticmethod
    def run_azure_document_ai(client, img_bytes: bytes) -> Tuple[str, float]:
        try:
            poller = client.begin_analyze_document("prebuilt-read", img_bytes)
            result = poller.result()
            text = result.content
            # Azure gives high accuracy for typed text
            return text, 95.0
        except Exception as e:
            logger.error(f"Azure Document AI failed: {e}")
            raise

    @staticmethod
    def load_aws_textract() -> Optional[Any]:
        if not os.environ.get("AWS_ACCESS_KEY_ID"):
            return None
        try:
            import boto3
            client = boto3.client('textract', region_name=os.environ.get("AWS_REGION", "us-east-1"))
            logger.info("AWS Textract loaded.")
            return client
        except Exception as e:
            logger.warning(f"AWS Textract unavailable: {e}")
            return None

    @staticmethod
    def run_aws_textract(client, img_bytes: bytes) -> Tuple[str, float]:
        try:
            response = client.detect_document_text(Document={'Bytes': img_bytes})
            blocks = response.get('Blocks', [])
            text_parts = []
            confs = []
            for block in blocks:
                if block['BlockType'] == 'WORD':
                    text_parts.append(block['Text'])
                    confs.append(block['Confidence'])
            text = " ".join(text_parts)
            avg_conf = sum(confs) / len(confs) if confs else 85.0
            return text, avg_conf
        except Exception as e:
            logger.error(f"AWS Textract failed: {e}")
            raise

    @staticmethod
    def load_gemini_vision() -> Optional[Any]:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-pro-vision-latest')
            logger.info("Gemini Vision loaded.")
            return model
        except Exception as e:
            logger.warning(f"Gemini Vision unavailable: {e}")
            return None

    @staticmethod
    def run_gemini_vision(model, img_bytes: bytes) -> Tuple[str, float]:
        try:
            response = model.generate_content([
                "Extract all text from this document accurately. Output plain text only.",
                {"mime_type": "image/jpeg", "data": img_bytes}
            ])
            text = response.text
            # Gemini doesn't return confidence scores per word, so we estimate
            return text, 90.0
        except Exception as e:
            logger.error(f"Gemini Vision failed: {e}")
            raise
