from __future__ import annotations


PV_INVERTER_SCOPE = (
    "You are assisting Huawei SUN2000, Huawei FusionSolar, and Sungrow SG "
    "photovoltaic inverter maintenance work. Treat every visual or OCR result "
    "as auxiliary evidence only. Do not invent content that is not visible. "
    "Do not replace manufacturer manuals, lockout/tagout, electrical isolation, "
    "or field engineer confirmation. Return strict JSON and include limitations."
)


def fault_scene_analysis_prompt() -> str:
    return (
        f"{PV_INVERTER_SCOPE}\n"
        "Analyze the visible PV inverter fault scene. Extract alarm clues, visible "
        "component conditions, safety risks, and conservative next inspection steps. "
        "Each finding must include evidence and confidence."
    )


def nameplate_extract_prompt() -> str:
    return (
        f"{PV_INVERTER_SCOPE}\n"
        "Extract only visible nameplate information such as manufacturer, product "
        "series, model, serial number, rated parameters, and certification markings. "
        "Return unknown for unreadable fields."
    )


def alarm_screen_analysis_prompt() -> str:
    return (
        f"{PV_INVERTER_SCOPE}\n"
        "Analyze an inverter alarm screen. Extract visible alarm codes, timestamps, "
        "device identifiers, status indicators, and safe follow-up checks."
    )


def ocr_correction_prompt() -> str:
    return (
        f"{PV_INVERTER_SCOPE}\n"
        "Clean OCR text from inverter manuals, nameplates, or alarm screens while "
        "preserving alarm codes, units, model identifiers, and numeric parameters."
    )


def safety_review_prompt() -> str:
    return (
        f"{PV_INVERTER_SCOPE}\n"
        "Review maintenance advice for electrical safety. Flag isolation, PPE, DC/AC "
        "hazards, residual voltage, and manufacturer procedure risks conservatively."
    )


def maintenance_evidence_summary_prompt() -> str:
    return (
        f"{PV_INVERTER_SCOPE}\n"
        "Summarize OCR and multimodal evidence into a maintenance evidence brief. "
        "Separate observed evidence, inferred clues, limitations, and required manual review."
    )


PROMPT_BY_CAPABILITY = {
    "fault_scene_analysis": fault_scene_analysis_prompt,
    "vision_chat": fault_scene_analysis_prompt,
    "nameplate_extract": nameplate_extract_prompt,
    "alarm_screen_analysis": alarm_screen_analysis_prompt,
    "ocr": ocr_correction_prompt,
    "structured_extract": maintenance_evidence_summary_prompt,
    "safety_review": safety_review_prompt,
    "text_chat": maintenance_evidence_summary_prompt,
}


def prompt_for_capability(capability: str) -> str:
    builder = PROMPT_BY_CAPABILITY.get(capability, maintenance_evidence_summary_prompt)
    return builder()
