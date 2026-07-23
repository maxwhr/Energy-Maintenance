from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.knowledge_graph import (
    KGEdgeCreate,
    KGEdgeUpdate,
    KGEvidenceCreate,
    KGExtractionRequest,
    KGNodeCreate,
    KGNodeMergeRequest,
    KGNodeUpdate,
)
from app.services.kg_extraction_service import KGExtractionPermissionError, KGExtractionServiceError
from app.services.knowledge_graph_service import (
    KnowledgeGraphPermissionError,
    KnowledgeGraphService,
    KnowledgeGraphServiceError,
)

router = APIRouter(prefix="/kg", tags=["knowledge-graph"])


@router.get("/overview")
def get_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).overview(current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403180)
    return success_response(data)


@router.get("/graph")
def get_graph(
    node_type: str | None = Query(default=None),
    relation_type: str | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    fault_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    include_source_nodes: bool = Query(default=False),
    limit: int = Query(default=80, ge=1, le=200),
    depth: int = Query(default=1, ge=1, le=3),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).graph(
            current_user=current_user,
            node_type=node_type,
            relation_type=relation_type,
            manufacturer=manufacturer,
            product_series=product_series,
            fault_type=fault_type,
            keyword=keyword,
            limit=limit,
            depth=depth,
            include_source_nodes=include_source_nodes,
        )
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403205)
    return success_response(data)


@router.post("/bootstrap")
def bootstrap_graph(
    max_documents: int = Query(default=6, ge=1, le=12),
    max_chunks_per_document: int = Query(default=40, ge=1, le=80),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).bootstrap(
            current_user=current_user,
            max_documents=max_documents,
            max_chunks_per_document=max_chunks_per_document,
        )
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403208)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400208)
    return success_response(data)


@router.get("/search")
def search_graph(
    keyword: str | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    node_type: str | None = Query(default=None),
    relation_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).search(
            current_user=current_user,
            keyword=keyword,
            manufacturer=manufacturer,
            product_series=product_series,
            node_type=node_type,
            relation_type=relation_type,
            limit=limit,
        )
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403206)
    return success_response(data)


@router.get("/business-context")
def get_business_context(
    device_id: UUID | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    fault_type: str | None = Query(default=None),
    alarm_code: str | None = Query(default=None),
    question: str | None = Query(default=None),
    diagnosis_trace_id: str | None = Query(default=None),
    sop_template_id: UUID | None = Query(default=None),
    task_id: UUID | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=80),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).business_context(
            current_user=current_user,
            device_id=device_id,
            manufacturer=manufacturer,
            product_series=product_series,
            fault_type=fault_type,
            alarm_code=alarm_code,
            question=question,
            diagnosis_trace_id=diagnosis_trace_id,
            sop_template_id=sop_template_id,
            task_id=task_id,
            limit=limit,
        )
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403207)
    return success_response(data)


@router.get("/nodes")
def list_nodes(
    node_type: str | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    device_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).list_nodes(
            current_user=current_user,
            node_type=node_type,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403181)
    return success_response(data)


@router.post("/nodes")
def create_node(
    payload: KGNodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).create_node(payload, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403182)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400182)
    return success_response(data)


@router.get("/nodes/{node_id}")
def get_node(
    node_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).get_node(node_id, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403183)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 404183)
    return success_response(data)


@router.put("/nodes/{node_id}")
def update_node(
    node_id: UUID,
    payload: KGNodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).update_node(node_id, payload, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403184)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400184)
    return success_response(data)


@router.post("/nodes/{node_id}/archive")
def archive_node(
    node_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).archive_node(node_id, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403185)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400185)
    return success_response(data)


@router.post("/nodes/{node_id}/merge")
def merge_node(
    node_id: UUID,
    payload: KGNodeMergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).merge_node(node_id, payload, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403186)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400186)
    return success_response(data)


@router.get("/edges")
def list_edges(
    source_node_id: UUID | None = Query(default=None),
    target_node_id: UUID | None = Query(default=None),
    relation_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).list_edges(
            current_user=current_user,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation_type=relation_type,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403187)
    return success_response(data)


@router.post("/edges")
def create_edge(
    payload: KGEdgeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).create_edge(payload, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403188)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400188)
    return success_response(data)


@router.get("/edges/{edge_id}")
def get_edge(
    edge_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).get_edge(edge_id, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403189)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 404189)
    return success_response(data)


@router.put("/edges/{edge_id}")
def update_edge(
    edge_id: UUID,
    payload: KGEdgeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).update_edge(edge_id, payload, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403190)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400190)
    return success_response(data)


@router.post("/edges/{edge_id}/archive")
def archive_edge(
    edge_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).archive_edge(edge_id, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403191)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400191)
    return success_response(data)


@router.get("/evidence")
def list_evidence(
    node_id: UUID | None = Query(default=None),
    edge_id: UUID | None = Query(default=None),
    source_type: str | None = Query(default=None),
    document_id: UUID | None = Query(default=None),
    chunk_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).list_evidence(
            current_user=current_user,
            node_id=node_id,
            edge_id=edge_id,
            source_type=source_type,
            document_id=document_id,
            chunk_id=chunk_id,
            page=page,
            page_size=page_size,
        )
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403192)
    return success_response(data)


@router.post("/evidence")
def create_evidence(
    payload: KGEvidenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).create_evidence(payload, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403193)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400193)
    return success_response(data)


@router.get("/neighborhood/{node_id}")
def get_neighborhood(
    node_id: UUID,
    depth: int = Query(default=1, ge=1, le=3),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).neighborhood(node_id, current_user=current_user, depth=depth)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403194)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 404194)
    return success_response(data)


@router.get("/path")
def get_path(
    source_node_id: UUID = Query(...),
    target_node_id: UUID = Query(...),
    max_depth: int = Query(default=3, ge=1, le=5),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).path(
            current_user=current_user,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            max_depth=max_depth,
        )
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403195)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400195)
    return success_response(data)


@router.post("/extract/from-document/{document_id}")
def extract_from_document(
    document_id: UUID,
    payload: KGExtractionRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).extract_from_document(
            document_id,
            payload or KGExtractionRequest(),
            current_user=current_user,
        )
    except (KnowledgeGraphPermissionError, KGExtractionPermissionError) as exc:
        return error_response(str(exc), 403196)
    except (KnowledgeGraphServiceError, KGExtractionServiceError) as exc:
        return error_response(str(exc), 400196)
    return success_response(data)


@router.post("/extract/from-contribution/{contribution_id}")
def extract_from_contribution(
    contribution_id: UUID,
    payload: KGExtractionRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).extract_from_contribution(
            contribution_id,
            payload or KGExtractionRequest(),
            current_user=current_user,
        )
    except (KnowledgeGraphPermissionError, KGExtractionPermissionError) as exc:
        return error_response(str(exc), 403197)
    except (KnowledgeGraphServiceError, KGExtractionServiceError) as exc:
        return error_response(str(exc), 400197)
    return success_response(data)


@router.post("/extract/from-record/{record_type}/{record_id}")
def extract_from_record(
    record_type: str,
    record_id: UUID,
    payload: KGExtractionRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).extract_from_record(
            record_type,
            record_id,
            payload or KGExtractionRequest(),
            current_user=current_user,
        )
    except (KnowledgeGraphPermissionError, KGExtractionPermissionError) as exc:
        return error_response(str(exc), 403198)
    except (KnowledgeGraphServiceError, KGExtractionServiceError) as exc:
        return error_response(str(exc), 400198)
    return success_response(data)


@router.get("/extraction-runs")
def list_extraction_runs(
    source_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).list_runs(
            current_user=current_user,
            source_type=source_type,
            status=status,
            page=page,
            page_size=page_size,
        )
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403199)
    return success_response(data)


@router.get("/extraction-runs/{run_id}")
def get_extraction_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).get_run(run_id, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403200)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 404200)
    return success_response(data)


@router.get("/candidates")
def list_candidates(
    run_id: UUID | None = Query(default=None),
    candidate_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).list_candidates(
            current_user=current_user,
            run_id=run_id,
            candidate_type=candidate_type,
            status=status,
            page=page,
            page_size=page_size,
        )
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403201)
    return success_response(data)


@router.get("/candidates/{candidate_id}")
def get_candidate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).get_candidate(candidate_id, current_user=current_user)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403202)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 404202)
    return success_response(data)


@router.post("/candidates/{candidate_id}/approve")
def approve_candidate(
    candidate_id: UUID,
    comment: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).approve_candidate(candidate_id, current_user=current_user, comment=comment)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403203)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400203)
    return success_response(data)


@router.post("/candidates/{candidate_id}/reject")
def reject_candidate(
    candidate_id: UUID,
    comment: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeGraphService(db).reject_candidate(candidate_id, current_user=current_user, comment=comment)
    except KnowledgeGraphPermissionError as exc:
        return error_response(str(exc), 403204)
    except KnowledgeGraphServiceError as exc:
        return error_response(str(exc), 400204)
    return success_response(data)
