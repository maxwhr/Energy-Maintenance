# AGENTS.md

**Project:** Energy-Maintenance  
**Purpose:** Codex / AI coding agent development rules  
**Version:** v1.0  
**Scope:** Huawei & Sungrow PV inverter maintenance knowledge retrieval and work-assistance system  

---

## 1. Project Identity

Energy-Maintenance is a maintenance knowledge retrieval and work-assistance system for photovoltaic inverter operation and maintenance.

The first version is strictly focused on:

```text
Huawei / 华为
Sungrow / 阳光电源
PV inverter / 光伏逆变器
```

The system is designed to support:

```text
document upload
document parsing
knowledge chunk storage
maintenance question answering
source-traceable retrieval
fault diagnosis
maintenance task management
record tracing
LoongArch + Kylin native deployment
```

This project is not a generic renewable-energy platform, not a vehicle repair system, not an education platform, and not a general chatbot.

---

## 2. First-version Business Scope

### 2.1 Supported Manufacturers

Only the following manufacturers are supported in the first version:

```text
huawei：华为
sungrow：阳光电源
```

Do not add other manufacturers unless the user explicitly requests a later-version expansion.

Do not add the following as first-version manufacturers:

```text
ginlong
goodwe
growatt
sineng
solis
other generic inverter vendors
```

They may be future extensions, but they are not part of the first version.

---

### 2.2 Supported Product Series

First-version product series:

```text
SUN2000
FusionSolar
SG
```

Mapping:

```text
huawei  -> SUN2000
huawei  -> FusionSolar
sungrow -> SG
```

`FusionSolar` is allowed as Huawei's monitoring and operation-maintenance ecosystem identifier.

---

### 2.3 Supported Device Type

Only one core device type is supported in the first version:

```text
pv_inverter：光伏逆变器
```

Do not expose the following as first-version main device types:

```text
battery
energy_storage
box_transformer
transformer
power_inspection_device
generic_renewable_equipment
motorcycle
vehicle
engine
```

If historical code contains `inverter`, it may be kept as a compatibility value, but frontend and new business logic should prefer:

```text
pv_inverter
```

---

### 2.4 Supported Document Types

First-version document types:

```text
manual：设备手册
alarm_code：告警代码
sop：检修规程
fault_case：故障案例
inspection_standard：巡检规范
maintenance_record：检修记录
```

---

### 2.5 Supported Fault Types

First-version fault types:

```text
low_insulation_resistance
dc_abnormal
ac_overvoltage
ac_undervoltage
grid_connection_fault
over_temperature
fan_fault
communication_interruption
device_offline
mppt_abnormal
low_power_generation
alarm_code_query
```

These fault types must remain aligned across:

```text
database models
Pydantic schemas
API contracts
frontend select options
fault diagnosis rules
test cases
```

---

## 3. Documents That Must Guide Development

Before making code changes, read the relevant documents.

Core baseline documents:

```text
docs/01_project_scope_and_product_requirements.md
docs/02_technical_stack_and_architecture.md
docs/03_database_schema_design.md
docs/04_api_contract_design.md
docs/09_testing_acceptance_and_quality_spec.md
docs/10_vibe_coding_task_plan.md
```

Module-specific documents:

```text
docs/05_frontend_page_and_interaction_spec.md
docs/06_knowledge_base_and_document_processing_spec.md
docs/07_retrieval_qa_and_fault_diagnosis_spec.md
docs/08_deployment_and_loongarch_kylin_spec.md
```

If there is a conflict between code and docs, treat the docs as the baseline unless the user explicitly updates the requirement.

---

## 4. Development Mode

This project follows a high-standard vibe coding route.

The goal is not to quickly produce a rough prototype.

The goal is:

```text
write clear requirements
write clear architecture
write clear database schema
write clear API contracts
write clear frontend specifications
write clear testing standards
then let AI coding tools implement toward final deliverable quality
```

Therefore:

```text
small tasks only
clear scope only
no broad refactor unless requested
no fake acceptance
no fake data as real result
no simulated database as final result
```

---

## 5. Technical Stack Baseline

### 5.1 Backend

Use:

```text
Python 3.10+
FastAPI
Uvicorn
Pydantic / pydantic-settings
SQLAlchemy 2.x
Alembic
PostgreSQL
psycopg
python-multipart
pypdf
python-docx
```

Do not replace FastAPI with Flask, Django, Node.js, or other frameworks unless the user explicitly changes the architecture.

---

### 5.2 Frontend

Use:

```text
Vue 3
Vite
TypeScript
Vue Router
Pinia
Axios
Element Plus
```

Do not replace Vue3 with React unless the user explicitly changes the frontend architecture.

---

### 5.3 Database

Use PostgreSQL as the formal relational database.

Do not use SQLite as the formal database.

Do not use MySQL as the formal database.

Do not write code that silently falls back to SQLite when PostgreSQL is unavailable.

---

### 5.4 Deployment

Formal deployment target:

```text
LoongArch + Kylin
Python virtual environment
native PostgreSQL service
systemd
Nginx
```

Docker is not the formal deployment route.

It is acceptable to use a temporary PostgreSQL container in local development only if clearly stated as temporary. Do not write Docker as the selected final deployment strategy.

---

## 6. Backend Architecture Rules

Backend code must follow layered architecture:

```text
api -> service -> repository -> model
```

### 6.1 API Layer

API layer responsibilities:

```text
receive request
validate parameters
call service
return unified response
```

API layer must not:

```text
write complex SQL directly
contain business rules for retrieval scoring
contain document parsing logic
contain fault diagnosis rules
directly fabricate references
```

---

### 6.2 Service Layer

Service layer responsibilities:

```text
business orchestration
transaction boundary where needed
call repositories
call knowledge processor
call retriever
call diagnosis rules
assemble response data
```

---

### 6.3 Repository Layer

Repository layer responsibilities:

```text
database query
database insert
database update
pagination
filtering
```

Do not put API response formatting inside repository classes.

---

### 6.4 Model Layer

Model layer responsibilities:

```text
SQLAlchemy table definitions
relationships
indexes
basic field constraints
```

Models must be included in Alembic metadata.

---

## 7. Database Rules

### 7.1 Core Tables

The first version must support these core tables:

```text
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
```

Recommended supporting tables:

```text
users
devices
operation_logs
model_call_logs
```

---

### 7.2 Required Domain Fields

The following fields are critical and must not be omitted from relevant tables:

```text
manufacturer
product_series
device_type
document_type
fault_type
alarm_code
trace_id
references
retrieved_chunks
source_trace_id
```

---

### 7.3 Alembic Rules

All schema changes must be handled through Alembic migrations.

Do not manually change the database schema without adding a migration.

After model changes, update:

```text
SQLAlchemy model
Pydantic schema
repository logic
Alembic migration
API response if needed
frontend type if needed
```

---

### 7.4 PostgreSQL Real Verification

When claiming database completion, the following must have been truly executed:

```bash
cd backend
alembic -c alembic.ini upgrade head
```

or:

```bash
cd backend
uv run alembic -c alembic.ini upgrade head
```

If PostgreSQL is not running, say so explicitly.

Do not claim that migrations passed if only offline SQL generation or static code checks were performed.

---

## 8. API Contract Rules

The public API prefix is:

```text
/api
```

Do not change public paths to `/api/v1` unless the user explicitly requests API versioning and all docs/frontend calls are updated.

Core API endpoints:

```text
GET  /api/health
GET  /api/system/info
GET  /api/system/status

POST /api/knowledge/documents/upload
GET  /api/knowledge/documents
GET  /api/knowledge/documents/{document_id}
GET  /api/knowledge/documents/{document_id}/chunks
DELETE /api/knowledge/documents/{document_id}
POST /api/knowledge/documents/{document_id}/reparse

POST /api/retrieval/query

POST /api/maintenance/diagnose
POST /api/maintenance/tasks
GET  /api/maintenance/tasks
GET  /api/maintenance/tasks/{task_id}
PATCH /api/maintenance/tasks/{task_id}/status

GET /api/records/qa
GET /api/records/diagnosis
```

---

### 8.1 Unified Response Format

All APIs should return:

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

Errors should return:

```json
{
  "code": 400,
  "message": "error message",
  "data": null
}
```

Do not return inconsistent structures across modules.

---

### 8.2 Write APIs Must Persist Data

The following APIs must write to PostgreSQL:

```text
POST /api/knowledge/documents/upload
POST /api/retrieval/query
POST /api/maintenance/diagnose
POST /api/maintenance/tasks
PATCH /api/maintenance/tasks/{task_id}/status
```

Do not use in-memory lists as final implementation.

---

## 9. Knowledge Base Rules

### 9.1 Supported File Types

First version supports:

```text
txt
md
pdf
docx
```

Do not add OCR, Excel parsing, PowerPoint parsing, image parsing, or archive parsing unless the user explicitly requests it.

---

### 9.2 Recommended Parsers

Use:

```text
txt/md: text parser
pdf: pypdf
docx: python-docx
```

Avoid first-version dependency on:

```text
PyMuPDF
OCR engines
OpenCV
large local vision models
```

because the final target is LoongArch + Kylin.

---

### 9.3 Upload Safety

Must check:

```text
file extension
file size
empty file
path traversal
safe file name
upload directory permissions
```

Upload files must not be saved under frontend directories.

---

### 9.4 Parse Status

Use:

```text
pending
processing
parsed
failed
```

Rules:

```text
parsed -> chunk_count > 0
failed -> error_message non-empty
failed -> chunk_count = 0
```

Do not mark a document as parsed if no chunks were generated.

---

### 9.5 Chunk Rules

`knowledge_chunks` must contain real parsed content.

Each chunk should include:

```text
document_id
manufacturer
product_series
device_type
document_type
chunk_index
content
section_title
char_count
page_number
embedding_status
metadata_json
status
```

Do not create fake chunks.

---

## 10. Retrieval and QA Rules

### 10.1 First-version Retrieval

First-version retrieval uses:

```text
PostgreSQL keyword retrieval
Chinese keyword expansion
domain-specific scoring
references from real knowledge_chunks
```

Do not introduce pgvector, embeddings, reranker, or LLM as required first-version dependencies unless the user explicitly starts an enhancement task.

---

### 10.2 References Must Be Real

Every reference must come from real:

```text
knowledge_documents
knowledge_chunks
```

Do not fabricate:

```text
document_id
document_title
section_title
chunk_index
page_number
source
score
```

If retrieval finds no relevant chunks:

```json
"references": [],
"retrieved_chunks": []
```

---

### 10.3 QA Records

Every successful call to:

```text
POST /api/retrieval/query
```

must save a `qa_records` row.

Save at least:

```text
question
normalized_query
manufacturer
product_series
device_type
document_type
answer
references
retrieved_chunks
suggested_steps
confidence
trace_id
created_at
```

No retrieval result is still a record and should be saved unless request validation fails.

---

### 10.4 Confidence Rules

`confidence` is not accuracy.

Do not return:

```text
1.0
```

No references should imply low confidence.

---

## 11. Fault Diagnosis Rules

Fault diagnosis should output:

```text
possible_causes
inspection_steps
safety_notes
recommended_actions
references
confidence
trace_id
```

`safety_notes` must never be empty for electrical maintenance scenarios.

Do not claim the system can definitively determine the fault cause.

Do not replace field engineer judgment or manufacturer safety manuals.

---

### 11.1 Diagnosis Records

Every successful call to:

```text
POST /api/maintenance/diagnose
```

must save a `diagnosis_records` row.

If request validation fails, do not save.

---

## 12. Maintenance Task Rules

Maintenance task status values:

```text
pending
in_progress
completed
cancelled
```

Allowed transitions:

```text
pending -> in_progress
pending -> cancelled
in_progress -> completed
in_progress -> cancelled
```

Do not allow:

```text
completed -> pending
cancelled -> in_progress
```

If not yet implemented, mark it as a known issue rather than pretending it works.

---

## 13. Frontend Rules

Frontend pages must match:

```text
docs/05_frontend_page_and_interaction_spec.md
```

Core pages:

```text
DashboardView
KnowledgeBaseView
RetrievalChatView
FaultDiagnosisView
MaintenanceTaskView
RecordCenterView
SystemStatusView
LoginView
```

---

### 13.1 Frontend Scope

Frontend copy and options must focus on:

```text
Huawei
Sungrow
PV inverter
maintenance knowledge
fault diagnosis
source tracing
task management
```

Do not show first-version main navigation for:

```text
storage battery
box transformer
generic renewable equipment
vehicle repair
education platform
```

---

### 13.2 Frontend API Base

Use:

```text
/api
```

Do not hardcode:

```text
http://127.0.0.1:8000
```

inside individual pages.

Use a centralized Axios instance.

---

### 13.3 Frontend Must Not Fake Success

If API fails, show error.

Do not:

```text
show upload success when backend failed
show generated answer when retrieval API failed
fabricate references in frontend
show database connected when backend reports disconnected
```

---

## 14. Deployment Rules

Formal deployment follows:

```text
LoongArch + Kylin
Python venv
native PostgreSQL
systemd
Nginx
```

Do not create Dockerfile or docker-compose as the official deployment path.

Deployment artifacts may include:

```text
deploy/systemd/energy-maintenance-backend.service
deploy/nginx/energy-maintenance.conf
scripts/deploy_backend.sh
scripts/deploy_frontend.sh
scripts/backup_database.sh
scripts/health_check.sh
```

---

## 15. Testing and Acceptance Rules

Before claiming a task is complete, execute relevant checks from:

```text
docs/09_testing_acceptance_and_quality_spec.md
```

At minimum, use relevant checks among:

```bash
python -m compileall app
alembic -c alembic.ini upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/system/status
npm run build
```

For knowledge and retrieval tasks, also test:

```text
document upload
chunk query
retrieval query
qa_records query
diagnosis query
maintenance task creation
```

If a command cannot be executed, state:

```text
not executed
reason: ...
```

---

## 16. Required Codex Output Format

After each task, output:

```text
# Task Result

## 1. Task Summary
...

## 2. Modified Files
- ...

## 3. Implementation Details
- ...

## 4. Commands Executed
- command: ...
  result: passed / failed / not executed

## 5. Acceptance Results
- Database migration: passed / failed / not executed
- Backend API: passed / failed / not executed
- Frontend build: passed / failed / not executed
- Real PostgreSQL write: passed / failed / not executed

## 6. Known Issues
- ...

## 7. Next Suggested Task
- ...
```

Do not omit known issues.

Do not claim success for unexecuted steps.

---

## 17. Prohibited Actions

Do not:

```text
1. Expand first-version scope beyond Huawei and Sungrow PV inverters
2. Use SQLite as formal database
3. Use Docker as formal deployment path
4. Change /api to /api/v1 without explicit instruction
5. Fake references
6. Fake chunks
7. Fake qa_records or diagnosis_records
8. Put business logic directly inside API handlers
9. Save uploaded files under frontend
10. Remove manufacturer/product_series/device_type fields
11. Return confidence = 1.0
12. Hide PostgreSQL connection failure
13. Claim real tests passed when they were not executed
14. Use frontend mock data as final business result
15. Introduce heavy x86-only model dependencies in the first version
```

---

## 18. Preferred Development Sequence

Follow the task sequence in:

```text
docs/10_vibe_coding_task_plan.md
```

Recommended order:

```text
Task 01: scope and wording cleanup
Task 02: database fields and migration
Task 03: PostgreSQL real connection
Task 04: sample documents
Task 05: knowledge upload closed loop
Task 06: retrieval and references
Task 07: qa_records persistence
Task 08: fault diagnosis records
Task 09: maintenance tasks
Task 10: record center
Task 11: system status
Task 12: frontend interactions
Task 13: end-to-end acceptance
Task 14: LoongArch + Kylin deployment
Task 15: final demo preparation
```

Do not jump to advanced features before the real PostgreSQL closed loop works.

---

## 19. Advanced Features Are Deferred

The following are not first-version requirements:

```text
real LLM generation
embedding
pgvector
reranker
OCR
multimodal image understanding
IoT real-time monitoring
multi-tenant permission system
complex workflow approval
cloud deployment
Kubernetes
Docker final deployment
```

They may be future enhancements only after the first-version core closed loop is stable.

---

## 20. Final Definition of Done

The first version can only be considered complete when the following real closed loop works:

```text
1. PostgreSQL connects successfully
2. Alembic migration succeeds
3. Huawei sample document uploads and generates chunks
4. Sungrow sample document uploads and generates chunks
5. retrieval query returns real references
6. qa_records saves the query result
7. fault diagnosis returns causes, steps, safety notes, and actions
8. diagnosis_records saves the diagnosis result
9. maintenance task can be created and updated
10. records page can trace QA and diagnosis records
11. frontend build succeeds
12. system status shows real database and knowledge statistics
13. deployment docs and scripts follow LoongArch + Kylin native route
```

If any item is missing, report it as a known issue.
