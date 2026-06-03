# System Architecture: VisionRetail AI

## High-Level Architecture Flow

```mermaid
graph TD
    %% Cameras & Detection
    subgraph Store Layout
        C1[CAM_01: Entrance]
        C2[CAM_02: Store Floor]
        C3[CAM_03: Checkout]
    end

    %% Event Streams
    subgraph Raw Event Emission
        E1(ENTRY<br>EXIT<br>REENTRY)
        E2(ZONE_ENTER<br>ZONE_EXIT<br>ZONE_DWELL)
        E3(BILLING_QUEUE_JOIN<br>BILLING_QUEUE_ABANDON<br>PURCHASE)
    end

    %% Pipeline
    subgraph Computer Vision Pipeline
        YOLO[YOLOv8m Object Detection]
        SORT[DeepSORT Tracking]
        OSNET[OSNet Feature Extraction]
    end

    %% Core Processing
    subgraph Backend Services
        REID[Cross-Camera Re-ID Service]
        INGEST[Event Ingestion API]
        ANALYTICS[Analytics & Funnel Engine]
        ANOMALY[Statistical Anomaly Detector]
    end

    %% AI Layer
    subgraph AI Intelligence
        GPT[OpenAI GPT-5.2]
        CACHE[15-Min TTLCache]
    end

    %% Presentation
    DASHBOARD[React + Vite Dashboard]

    %% Connections
    C1 --> YOLO
    C2 --> YOLO
    C3 --> YOLO

    YOLO --> SORT
    SORT --> OSNET
    OSNET --> E1
    OSNET --> E2
    OSNET --> E3

    E1 --> INGEST
    E2 --> INGEST
    E3 --> INGEST

    INGEST --> REID
    REID --> ANALYTICS
    REID --> ANOMALY

    ANALYTICS --> DASHBOARD
    ANOMALY --> DASHBOARD

    ANOMALY -. Z-Scores & Metrics .-> CACHE
    ANALYTICS -. Store Metrics .-> CACHE
    CACHE --> GPT
    GPT --> CACHE
    CACHE --> DASHBOARD
```

## Data Model & Component Interaction

### 1. Data Ingestion Sequence
```mermaid
sequenceDiagram
    participant CV as CV Pipeline (Cameras)
    participant API as FastAPI Backend
    participant DB as PostgreSQL

    CV->>API: POST /events/ingest (Batch of events)
    API->>DB: Read recent sessions for active visitors
    API->>API: Calculate OSNet Cosine Similarity
    alt Match > 0.65 (Re-ID Threshold)
        API->>DB: Link event to existing visitor_id
    else No Match
        API->>DB: Create new visitor_id
    end
    API->>DB: Insert into `events` table
    API-->>CV: 201 Created
```

### 2. Funnel Analytics Logic
The system enforces strict retail funnel hierarchy through a mathematical boolean CTE applied at query time.

```mermaid
graph LR
    A[ENTRY] -->|has_entry × has_engagement| B[ZONE ENGAGEMENT]
    B -->|has_engagement × has_billing| C[BILLING QUEUE]
    C -->|has_billing × has_purchase| D[CONVERTED]
```

### 3. AI Copilot / Insights Flow
```mermaid
sequenceDiagram
    participant UI as Dashboard
    participant API as Insight Service
    participant DB as PostgreSQL
    participant GPT as OpenAI GPT-5.2

    UI->>API: GET /stores/{id}/ai-summary
    API->>API: Check TTLCache
    alt Cache Hit
        API-->>UI: Return Cached Summary
    else Cache Miss
        API->>DB: Query daily metrics, conversions, anomalies
        DB-->>API: Deterministic Stats
        API->>GPT: Prompt + Deterministic Stats
        alt GPT Success
            GPT-->>API: JSON Recommendation
        else GPT Timeout/Failure
            API->>API: Generate Rule-based Fallback
        end
        API->>API: Store in TTLCache (15 min)
        API-->>UI: Return AI Summary
    end
```
