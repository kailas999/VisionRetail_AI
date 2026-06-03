"""
GPT-5.2 Store Intelligence Copilot Service — RAG Architecture.

This service acts as an orchestrator, delegating to the `ai` module for:
- Retrieval (`ai.retrieval.store_retriever`)
- Prompts (`ai.prompts.copilot_prompts`)
- LLM interaction (`ai.llm_client`)
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any, Optional

from app.utils.logging import get_logger
from ai.retrieval.store_retriever import fetch_store_evidence, build_context_string
from ai.prompts.copilot_prompts import COPILOT_SYSTEM_PROMPT, COPILOT_USER_TEMPLATE
from ai.llm_client import chat_completion

logger = get_logger(__name__)


class CopilotService:
    """RAG-based AI Copilot using GPT-5.2 / GPT-5.2."""

    async def query(
        self,
        store_id: str,
        question: str,
        db_session,       # AsyncSession — avoid circular import
        query_date: Optional[date] = None,
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Full RAG pipeline: retrieve → build context → prompt → validate response.
        """
        trace_id = trace_id or str(uuid.uuid4())

        # ── Step 1: Retrieve evidence ──────────────────────────────────────
        evidence = await fetch_store_evidence(db_session, store_id, query_date)

        if not evidence or evidence.get("data_coverage", 0) < 1:
            return {
                "store_id": store_id,
                "question": question,
                "observations": [],
                "evidence": [],
                "conclusion": "INSUFFICIENT_DATA: No store data available for the requested period.",
                "confidence": 0.0,
                "insufficient_data": True,
                "trace_id": trace_id,
            }

        # ── Step 2: Build context ──────────────────────────────────────────
        query_date = query_date or date.today()
        context = build_context_string(store_id, question, evidence, query_date)

        # ── Step 3: Call GPT ───────────────────────────────────────────────
        user_message = COPILOT_USER_TEMPLATE.format(context=context, question=question)
        
        raw_response = await chat_completion(
            system_prompt=COPILOT_SYSTEM_PROMPT,
            user_message=user_message,
        )

        # Detect OpenAI unavailable and trigger rule-based fallback
        if (
            raw_response.get("insufficient_data")
            and raw_response.get("conclusion") == "INSUFFICIENT_DATA: LLM service unavailable."
        ):
            raw_response = self._generate_rule_based_fallback(question, evidence)

        # ── Step 4: Validate response ──────────────────────────────────────
        validated = self._validate_response(raw_response, evidence)
        validated["store_id"] = store_id
        validated["question"] = question
        validated["trace_id"] = trace_id

        return validated

    def _generate_rule_based_fallback(self, question: str, evidence: dict[str, Any]) -> dict[str, Any]:
        """
        Generate a high-quality, deterministic, rule-based response grounded in real store data
        when the LLM is unavailable.
        """
        q = question.lower()
        observations = []
        raw_evidence = []
        conclusion = ""
        confidence = 0.85

        daily_metrics = evidence.get("daily_metrics", {})
        active_anomalies = evidence.get("active_anomalies", [])
        
        # Extract common variables
        visitors = daily_metrics.get("unique_visitors", 0)
        conversions = daily_metrics.get("conversions", 0)
        conversion_rate = daily_metrics.get("conversion_rate_pct", 0.0)
        avg_dwell = daily_metrics.get("avg_dwell_minutes", 0.0)
        peak_hour = daily_metrics.get("peak_hour")
        max_queue = daily_metrics.get("max_queue_depth", 0)
        abandonments = daily_metrics.get("abandonment_count", 0)
        
        # 1. Check for anomalies question
        if any(w in q for w in ["anomaly", "anomalies", "issue", "problem", "wrong", "investigate", "alert"]):
            raw_evidence.append({
                "metric": "active_anomalies_count",
                "value": len(active_anomalies),
                "context": "Count of unresolved anomalies retrieved from database"
            })
            if active_anomalies:
                observations.append(f"Detected {len(active_anomalies)} active operational anomalies in the database.")
                for i, a in enumerate(active_anomalies):
                    metric_name = a.get("type", "UNKNOWN").replace("_", " ").title()
                    observations.append(
                        f"Anomaly {i+1}: {metric_name} ({a.get('severity')}) of {a.get('metric_value')} vs "
                        f"baseline {a.get('baseline_value')} (z-score: {a.get('z_score')})."
                    )
                
                anom_types = [a.get("type", "UNKNOWN") for a in active_anomalies]
                conclusion = f"Rule-Based Fallback: Operational issues are present today: {', '.join(anom_types)}. Immediate inspection of affected zones is recommended."
            else:
                observations.append("No active operational anomalies are currently logged in the database.")
                conclusion = "Rule-Based Fallback: No anomalies have been detected today. Operational parameters are running within normal historical limits."
        
        # 2. Check for conversion rate drop / conversions question
        elif any(w in q for w in ["conversion", "rate", "dropping", "drop", "sale", "sales", "purchase", "purchases", "buy"]):
            raw_evidence.extend([
                {"metric": "conversion_rate_pct", "value": conversion_rate, "context": "Daily conversion rate percentage"},
                {"metric": "conversions", "value": conversions, "context": "Total completed purchases"},
                {"metric": "unique_visitors", "value": visitors, "context": "Total unique customer visitors"},
                {"metric": "queue_abandonments", "value": abandonments, "context": "Count of customers who left the billing queue"}
            ])
            observations.append(f"The store conversion rate today is {conversion_rate}%.")
            observations.append(f"Completed purchases: {conversions} transactions out of {visitors} unique customer visits.")
            observations.append(f"Billing queue checkout abandonments: {abandonments} events.")
            
            # Check if there's any active anomaly related to queue or conversion
            q_anom = [a for a in active_anomalies if "QUEUE" in a.get("type", "") or "CONVERSION" in a.get("type", "")]
            if q_anom:
                observations.append(f"There is an active alert: {q_anom[0].get('type')} with severity {q_anom[0].get('severity')}.")
                conclusion = f"Rule-Based Fallback: The conversion rate is {conversion_rate}% with {conversions} purchases. A critical issue is present in the checkout funnel: {q_anom[0].get('type')} alert is active."
            elif abandonments > 5:
                conclusion = f"Rule-Based Fallback: Today's conversion rate is {conversion_rate}%. High queue abandonment ({abandonments} checkouts abandoned) is a primary bottleneck."
            else:
                conclusion = f"Rule-Based Fallback: Today's conversion rate is {conversion_rate}%. There are {conversions} conversions from {visitors} visitors, with checkout operations running smoothly."
                
        # 3. Check for traffic / footfall question
        elif any(w in q for w in ["traffic", "visitor", "visitors", "footfall", "crowd", "people", "occupancy"]):
            raw_evidence.extend([
                {"metric": "unique_visitors", "value": visitors, "context": "Total unique customer visitors"},
                {"metric": "avg_dwell_minutes", "value": avg_dwell, "context": "Average customer dwell time in minutes"},
                {"metric": "peak_hour", "value": peak_hour, "context": "Hour of peak customer traffic"}
            ])
            observations.append(f"Total unique visitors today: {visitors}.")
            observations.append(f"Average customer dwell time: {avg_dwell} minutes.")
            if peak_hour is not None:
                observations.append(f"Traffic peaked during hour {peak_hour}:00.")
                
            conclusion = f"Rule-Based Fallback: Foot traffic today stands at {visitors} unique visitors, with an average dwell time of {avg_dwell} minutes. Traffic peaked at hour {peak_hour or 'N/A'}."

        # 4. Default / General Summary
        else:
            raw_evidence.extend([
                {"metric": "unique_visitors", "value": visitors, "context": "Total unique customer visitors"},
                {"metric": "conversion_rate_pct", "value": conversion_rate, "context": "Daily conversion rate percentage"},
                {"metric": "active_anomalies_count", "value": len(active_anomalies), "context": "Total unresolved anomalies"}
            ])
            observations.append(f"Store has {visitors} unique visitors with {conversions} conversions ({conversion_rate}% conversion rate).")
            observations.append(f"Average dwell time: {avg_dwell} minutes; max queue depth: {max_queue} customers.")
            observations.append(f"Active alerts count: {len(active_anomalies)}.")
            
            conclusion = f"Rule-Based Fallback: Store is currently operating with {visitors} unique visitors, {conversion_rate}% conversion rate, and {len(active_anomalies)} active anomalies."

        return {
            "observations": observations,
            "evidence": raw_evidence,
            "conclusion": conclusion,
            "confidence": confidence,
            "insufficient_data": False
        }

    def _validate_response(self, response: dict, evidence: dict) -> dict:
        """
        Validate GPT response:
        - Ensure required fields present.
        - Cap confidence if data coverage is low.
        - Force insufficient_data if no observations.
        """
        validated = {
            "observations": response.get("observations", []),
            "evidence": response.get("evidence", []),
            "conclusion": response.get("conclusion", ""),
            "confidence": float(response.get("confidence", 0.0)),
            "insufficient_data": bool(response.get("insufficient_data", False)),
        }

        # Cap confidence based on data coverage
        coverage = evidence.get("data_coverage", 0)
        if coverage < 2:
            validated["confidence"] = min(validated["confidence"], 0.4)
        elif coverage < 3:
            validated["confidence"] = min(validated["confidence"], 0.65)

        # Force insufficient_data if no observations or conclusion is placeholder
        if not validated["observations"] or not validated["conclusion"]:
            validated["insufficient_data"] = True
            validated["confidence"] = 0.0

        if "INSUFFICIENT_DATA" in validated["conclusion"].upper():
            validated["insufficient_data"] = True

        return validated

