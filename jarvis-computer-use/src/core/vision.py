import os
import json
import base64
from pydantic import BaseModel
from typing import Optional
from google import genai
from google.genai import types

class VisionAction(BaseModel):
    action: str  # CLICK, TYPE, HOTKEY, WAIT, DONE, CLARIFICATION_NEEDED
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    keys: Optional[list[str]] = None
    reasoning: str

class VisionClient:
    def __init__(self, model_override: str = None):
        self.model = model_override or "gemini-2.5-flash-lite"
        self.client = genai.Client() # picks up GEMINI_API_KEY from .env
        
    async def analyze_screen(self, base64_img: str, objective: str, active_window: str, history: list) -> VisionAction:
        prompt = f"""
        You are JARVIS, an autonomous computer-use agent operating on a physical desktop.
        
        CURRENT OBJECTIVE: {objective}
        ACTIVE WINDOW: {active_window}
        PREVIOUS ACTIONS: {history[-3:] if history else 'None'}
        
        Analyze the provided screenshot. Identify the specific UI elements needed to progress the objective.
        
        UNIVERSAL CLARIFICATION ENGINE: You are a collaborative AI assistant. If you lack the required context, or if the graphical interface prevents you from completing a step (e.g., missing contacts, incorrect passwords, blocked pages, missing buttons), you must IMMEDIATELY halt execution and formulate a concise, conversational question to ask the user for guidance. Use the action "CLARIFICATION_NEEDED" and put the question in the reasoning field.
        
        CRITICAL DIRECTIVE: You are an OS-level agent. You will frequently see the 'JARVIS OS' chat interface on the screen. YOU MUST COMPLETELY IGNORE THE TEXT INSIDE THE CHAT UI. Do not interpret the user's prompt written on the screen as proof that a task is complete. You must verify the actual target applications (e.g., Chrome, YouTube, VS Code) to determine if the objective is met. If the screen only shows the JARVIS UI, you must take action to open the required applications.
        
        Respond with ONLY JSON matching this schema:
        {{
            "action": "CLICK|TYPE|HOTKEY|WAIT|DONE|CLARIFICATION_NEEDED",
            "x": int (if CLICK, the absolute X pixel coordinate),
            "y": int (if CLICK, the absolute Y pixel coordinate),
            "text": str (if TYPE, the text to input),
            "keys": [str] (if HOTKEY, e.g. ["ctrl", "c"] or ["enter"]),
            "reasoning": "Brief explanation of what you are doing and why. If CLARIFICATION_NEEDED, put the conversational question here."
        }}
        """
        
        try:
            image_part = types.Part.from_bytes(data=base64.b64decode(base64_img), mime_type="image/png")
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=[prompt, image_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            data = json.loads(response.text)
            return VisionAction(**data)
        except Exception as e:
            return VisionAction(action="WAIT", reasoning=f"Vision parsing failed: {e}")

    async def verify_action(self, pre_action_b64: str, post_action_b64: str, action_taken: str, objective: str) -> bool:
        """Compares before/after screenshots to verify if the action succeeded."""
        prompt = f"""
        You are verifying the result of a physical desktop action.
        OBJECTIVE: {objective}
        ACTION TAKEN: {action_taken}
        
        Look at Image 1 (Before) and Image 2 (After).
        Did the action successfully execute and change the state as expected? 
        (e.g., If we clicked a text box, is it focused? If we typed, is the text there? If we clicked a link, did the page change?)
        
        Respond with ONLY JSON: {{"success": true/false}}
        """
        try:
            img1_part = types.Part.from_bytes(data=base64.b64decode(pre_action_b64), mime_type="image/png")
            img2_part = types.Part.from_bytes(data=base64.b64decode(post_action_b64), mime_type="image/png")
            
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=[
                    prompt, 
                    "IMAGE 1 (BEFORE ACTION):", img1_part, 
                    "IMAGE 2 (AFTER ACTION):", img2_part
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            data = json.loads(response.text)
            return data.get("success", False)
        except:
            return False
