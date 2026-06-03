# API Reference: VisionRetail AI

All API endpoints reside on the FastAPI backend, typically exposed at `http://localhost:8000`. 
Below is the documentation for all currently implemented endpoints.

---

## 1. System Health

### GET `/health`
Returns the status of the backend API. Used by Docker and Load Balancers for health checks.

**Request:** No parameters.

**Response:** 
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## 2. Event Ingestion

### POST `/events/ingest`
Ingests a batch of semantic events from the CV Pipeline. Automatically performs OSNet Cosine Similarity matching for cross-camera Re-ID.

**Request Body:**
```json
{
  "events": [
    {
      "camera_id": "CAM_01",
      "timestamp": "2026-06-01T07:15:00Z",
      "event_type": "ENTRY",
      "feature_vector": [0.12, -0.45, 0.88, ...],
      "metadata": {
        "confidence": 0.92
      }
    }
  ]
}
```

**Response (201 Created):**
```json
{
  "ingested": 1,
  "duplicates": 0,
  "errors": 0,
  "trace_id": "req-xyz-123"
}
```

**Error Codes:**
- `422 Unprocessable Entity`: Invalid payload structure.

---

## 3. Metrics & Analytics

### GET `/stores/{store_id}/metrics`
Returns comprehensive daily metrics for the specified store, computed dynamically using the mathematically guaranteed visitor-journey CTE.

**Query Parameters:**
- `date` (optional): Date filter (YYYY-MM-DD). Defaults to today.

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "date": "2026-06-01",
  "unique_visitors": 450,
  "conversion_rate": 0.45,
  "avg_dwell_seconds": 210.5,
  "hourly_breakdown": [
    {
      "hour_bucket": "2026-06-01T09:00:00Z",
      "unique_visitors": 55,
      "conversions": 25,
      "conversion_rate": 0.4545
    }
  ]
}
```

---

### GET `/stores/{store_id}/funnel`
Returns the stage-by-stage retail funnel metrics (Entry → Engagement → Billing → Converted).

**Query Parameters:**
- `date` (optional): Date filter (YYYY-MM-DD). Defaults to today.

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "date": "2026-06-01",
  "stages": [
    { "stage": "ENTRY", "count": 1000, "rate": 1.0 },
    { "stage": "ZONE_ENGAGEMENT", "count": 800, "rate": 0.8 },
    { "stage": "BILLING_ZONE_REACHED", "count": 400, "rate": 0.5 },
    { "stage": "CONVERTED", "count": 350, "rate": 0.875 }
  ]
}
```

---

### GET `/stores/{store_id}/heatmap`
Provides zone-by-zone analytics (visitors and dwell time) for rendering the store heatmap.

**Query Parameters:**
- `date` (optional): Date filter (YYYY-MM-DD). Defaults to today.

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "date": "2026-06-01",
  "zones": [
    {
      "zone_id": "ZONE_SKINCARE",
      "zone_name": "Skincare Aisle",
      "avg_dwell_seconds": 120.5,
      "visitor_count": 320,
      "zone_enter_count": 320,
      "zone_exit_count": 315
    }
  ]
}
```

---

### GET `/stores/{store_id}/event-stream`
Provides absolute raw event counts across all cameras. Useful for debugging the direct output of the CV Pipeline.

**Response:**
```json
{
  "entrance": {
    "entry_count": 1153,
    "exit_count": 1098,
    "reentry_count": 74,
    "current_occupancy": 55
  },
  "zone": {
    "zone_enter_count": 2781,
    "zone_exit_count": 2744,
    "zone_dwell_count": 975,
    "avg_dwell_seconds": 289
  },
  "billing": {
    "queue_join_count": 320,
    "queue_abandon_count": 52,
    "purchase_count": 268,
    "queue_abandon_rate": 16.2,
    "billing_conversion_rate": 83.7
  },
  "reid": {
    "cross_camera_matches": 842,
    "match_rate": 73.1,
    "fragmented_visitors": 19,
    "avg_confidence": 88.5
  }
}
```

---

## 4. Anomalies & AI Insights

### GET `/stores/{store_id}/anomalies`
Returns a list of currently active (unresolved) operational anomalies.

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "active_count": 1,
  "anomalies": [
    {
      "anomaly_id": "uuid",
      "store_id": "STORE_BLR_002",
      "anomaly_type": "QUEUE_SPIKE",
      "severity": "HIGH",
      "metric_value": 15.0,
      "baseline_value": 4.5,
      "z_score": 3.2,
      "is_resolved": false
    }
  ]
}
```

---

### GET `/stores/{store_id}/anomalies/{anomaly_id}/insight`
Generates (or retrieves from cache) a GPT-5.2 powered root-cause explanation for a specific anomaly.

**Response:**
```json
{
  "anomaly_id": "uuid",
  "store_id": "STORE_BLR_002",
  "anomaly_type": "QUEUE_SPIKE",
  "root_cause": "Queue depth is significantly above the 7-day baseline.",
  "business_impact": "High abandonment risk.",
  "recommended_actions": ["Open another counter."],
  "priority_level": "HIGH",
  "fallback": false
}
```

---

### GET `/stores/{store_id}/ai-summary`
Returns an always-available GPT-5.2 executive summary of the entire store's performance based on the day's deterministic metrics.

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "executive_summary": "Store operations are performing nominally with healthy conversion.",
  "revenue_risk": "Queue times are creeping up in the billing zone.",
  "top_opportunities": "Focus on the Skincare zone which has high dwell but low conversion.",
  "recommended_actions": ["Reallocate staff to Skincare"],
  "priority_level": "MEDIUM",
  "fallback": false
}
```

---

### POST `/copilot/query`
Natural language RAG endpoint allowing operators to query store performance.

**Request:**
```json
{
  "store_id": "STORE_BLR_002",
  "question": "Why did conversion drop yesterday?"
}
```

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "question": "Why did conversion drop yesterday?",
  "observations": ["Conversion dropped by 12%."],
  "evidence": [...],
  "conclusion": "The drop coincides with a QUEUE_SPIKE anomaly at 14:00.",
  "confidence": 0.95
}
```
