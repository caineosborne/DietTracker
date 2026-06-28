from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from prompts import build_estimation_instructions
from schemas import MealEstimate

DEFAULT_MODEL = "gpt-5.4-mini"


class MealEstimator:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        load_dotenv()
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise ValueError("OPENAI_API_KEY is not set.")

        self.model = model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
        self.client = OpenAI(api_key=resolved_api_key)

    def estimate(self, raw_text: str, now_local: datetime) -> MealEstimate:
        cleaned_text = raw_text.strip()
        if not cleaned_text:
            raise ValueError("Meal text cannot be empty.")

        response = self.client.responses.parse(
            model=self.model,
            instructions=build_estimation_instructions(now_local),
            input=cleaned_text,
            text_format=MealEstimate,
        )

        if response.output_parsed is None:
            raise ValueError("The model did not return a structured meal estimate.")

        return response.output_parsed
