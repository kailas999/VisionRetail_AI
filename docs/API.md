# API Documentation — VisionRetail AI

Base URL: `http://localhost:8000`

---

## Authentication
No auth required for local/challenge deployment. Add Bearer token middleware for production.

---

## Endpoints

### `GET /health`
Service and database health check.

**Response:**
```json
{
  "status": "healthy",
  "database": "healthy",
  "version": "1.0.0",
  "environment": "production"
}
```

---

### `POST /events/ingest`
Idempotent batch event ingestion. Duplicate `event_id` values are silently ignored.

**Request:**
```json
{
  "events": [
    {
      "event_id": "550e8400-e29b-41d4-a716-446655440000",
      "store_id": "STORE_BLR_002",
      "visitor_id": "VIS_ABC123DEF456",
      "session_id": "optional-uuid",
      "event_type": "ENTRY",
      "timestamp": "2026-05-30T10:00:00+05:30",
      "zone_id": null,
      "confidence": 0.92,
      "is_staff": false,
      "camera_id": "CAM_01",
      "sequence_number": 1
    }
  ]
}
```

**Event Types:** `ENTRY` | `EXIT` | `ZONE_ENTER` | `ZONE_EXIT` | `ZONE_DWELL` | `BILLING_QUEUE_JOIN` | `BILLING_QUEUE_ABANDON` | `REENTRY`

**Response:**
```json
{
  "ingested": 1,
  "duplicates": 0,
  "errors": 0,
  "trace_id": "uuid"
}
```

---

### `GET /stores/{store_id}/metrics`
Pre-aggregated daily metrics. Reads from `daily_metrics` table — O(1) response.

**Query params:** `?date=2026-05-30`

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "date": "2026-05-30",
  "unique_visitors": 142,
  "staff_count": 4,
  "conversions": 38,
  "conversion_rate": 0.268,
  "avg_dwell_seconds": 672.4,
  "peak_hour": 17,
  "max_queue_depth": 7,
  "abandonment_count": 5,
  "reentry_count": 12,
  "total_revenue": 48250.0,
  "hourly_breakdown": [...]
}
```

---

### `GET /stores/{store_id}/funnel`
Entry → Zone Engagement → Billing Zone → Converted funnel.

**Query params:** `?date=2026-05-30`

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "stages": [
    {"stage": "ENTRY", "count": 142, "rate": 1.0},
    {"stage": "ZONE_ENGAGEMENT", "count": 121, "rate": 0.852},
    {"stage": "BILLING_ZONE_REACHED", "count": 55, "rate": 0.454},
    {"stage": "CONVERTED", "count": 38, "rate": 0.691}
  ]
}
```

---

### `GET /stores/{store_id}/heatmap`
Zone dwell-time heatmap with polygon coordinates and normalised intensity.

**Query params:** `?date=2026-05-30`

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "zones": [
    {
      "zone_id": "ZONE_BILLING_01",
      "zone_name": "Billing Counter",
      "zone_type": "BILLING",
      "avg_dwell_seconds": 284.5,
      "visitor_count": 55,
      "polygon": [[800,300],[1080,300],[1080,720],[800,720]],
      "intensity": 1.0
    }
  ]
}
```

---

### `GET /stores/{store_id}/anomalies`
All unresolved anomalies with severity and recommended actions.

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "active_count": 2,
  "anomalies": [
    {
      "anomaly_id": "uuid",
      "anomaly_type": "QUEUE_SPIKE",
      "severity": "HIGH",
      "confidence": 0.82,
      "metric_value": 12.0,
      "baseline_value": 4.2,
      "z_score": 2.91,
      "recommended_action": "Activate additional checkout counters...",
      "is_resolved": false,
      "detected_at": "2026-05-30T17:05:00+00:00"
    }
  ]
}
```

---

### `POST /copilot/query`
GPT-5.2 RAG-powered store intelligence query.

**Request:**
```json
{
  "store_id": "STORE_BLR_002",
  "question": "Why is conversion dropping?",
  "date": "2026-05-30"
}
```

**Response:**
```json
{
  "store_id": "STORE_BLR_002",
  "question": "Why is conversion dropping?",
  "observations": [
    "Conversion rate is 18.3%, below the 7-day average of 26.8%",
    "Queue abandonment count is 14, compared to baseline of 3.2"
  ],
  "evidence": [
    {"metric": "conversion_rate", "value": 0.183, "context": "From daily_metrics for 2026-05-30"},
    {"metric": "abandonment_count", "value": 14, "context": "Billing queue abandonments today"}
  ],
  "conclusion": "Conversion drop is driven by elevated queue abandonment at the billing counter — 14 vs baseline of 3.2.",
  "confidence": 0.84,
  "insufficient_data": false,
  "trace_id": "uuid"
}
```

**INSUFFICIENT_DATA response** (when evidence is lacking):
```json
{
  "conclusion": "INSUFFICIENT_DATA: No store data available for the requested period.",
  "confidence": 0.0,
  "insufficient_data": true,
  "observations": [],
  "evidence": []
}
```
