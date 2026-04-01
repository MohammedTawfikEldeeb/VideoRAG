import os

import pixeltable as pxt
from PIL import Image


@pxt.udf
def extract_caption_from_response(response: pxt.Json) -> str:
    """Extract the assistant message text from an openai.chat_completions response dict."""
    return response['choices'][0]['message']['content']


@pxt.udf
def transcribe_audio(audio: pxt.Audio) -> pxt.Json:
    from openai import OpenAI
    client = OpenAI(
        api_key=os.environ["GROQ_API_KEY"],
        base_url=os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    )
    with open(audio, "rb") as f:
        result = client.audio.transcriptions.create(
            model=os.environ.get("AUDIO_TRANSCRIPT_MODEL", "whisper-large-v3"),
            file=f,
            response_format="json",
        )
    return {"text": result.text}


@pxt.udf
def extract_text_from_chunk(transcript: pxt.type_system.Json) -> str:
    """
    Extract text from a transcript JSON object.
    Note: Predictions of common S2T models are in dict format containing the text and chunk timestamps metadata. We need the text only.
    """
    return f"{transcript['text']}"


@pxt.udf
def resize_image(image: pxt.type_system.Image, width: int, height: int) -> pxt.type_system.Image:
    """
    Resize an image to fit within the specified width and height while maintaining aspect ratio.
    Note: The PIL.Image.thumbnail() method modifies the image in place.
    """
    if not isinstance(image, Image.Image):
        raise TypeError("Input must be a PIL Image")

    image.thumbnail((width, height))
    return image