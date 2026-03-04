import logging

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from .autoeval_database import AutoEvalDatabase
from .dependencies import get_autoeval_database
from .biotrainer_autoeval.autoeval_report_validator import AutoEvalReportValidator
from .models import PublishRequest, ReportsResponse, ComparisonStoreRequest, ComparisonStoreResponse, \
    ComparisonRetrieveResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/autoeval",
    tags=["autoeval", "biotrainer"]
)


@router.get("/",
            response_model=ReportsResponse,
            summary="Get all published autoeval reports",
            description="Retrieve all available published autoeval reports")
async def get_all_reports(
        autoeval_db: AutoEvalDatabase = Depends(get_autoeval_database)
):
    """Retrieve all published autoeval reports"""
    logger.info('[GET] All Public Autoeval Reports')
    publish_requests = autoeval_db.get_all_published_requests()
    reports = [req.report for req in publish_requests]
    return ReportsResponse(reports=reports)


@router.post("/publish/",
             summary="Publish a new autoeval report",
             description="Store a report and publisher information in the database")
async def publish_report(
        request: PublishRequest,
        autoeval_db: AutoEvalDatabase = Depends(get_autoeval_database)
):
    """Publish new data to the PLM leaderboard"""
    embedder_name = request.report.embedder_name
    logger.info(f'[POST] Publish Report: {embedder_name}')

    validator = AutoEvalReportValidator(request.report)
    validation_error = validator.validate()
    if validation_error is not None:
        return JSONResponse(content={"error": validation_error}, status_code=400)

    if autoeval_db.public_report_exists(request):
        return JSONResponse(content={"error": f"Report for {embedder_name} already exists."}, status_code=400)

    if autoeval_db.add_publish_request(request):
        return JSONResponse(content={"message": f"Report for {embedder_name} published successfully. "
                                                "Thank you for your contribution!"}, status_code=201)
    else:
        return JSONResponse(content={"error": "Internal error while trying to publish report"}, status_code=500)


@router.post("/compare/",
             response_model=ComparisonStoreResponse,
             summary="Store a report temporarily for comparison",
             description="Store a report in the database for 1 day")
async def store_comparison_report(
        request: ComparisonStoreRequest,
        autoeval_db: AutoEvalDatabase = Depends(get_autoeval_database)
):
    """Store a report temporarily for comparison"""
    logger.info(f'[POST] Store Comparison Report: {request.report.embedder_name}')

    maybe_uid = autoeval_db.add_comparison_request_report(request)
    if maybe_uid is not None:
        return ComparisonStoreResponse(uid=maybe_uid)
    else:
        return JSONResponse(content={"error": "Failed to store report for comparison"}, status_code=500)


@router.get("/compare/{uid}",
            response_model=ComparisonRetrieveResponse,
            summary="Retrieve a stored report for comparison",
            description="Retrieve a stored report given its unique identifier")
async def get_comparison_report(
        uid: str,
        autoeval_db: AutoEvalDatabase = Depends(get_autoeval_database)
):
    """Retrieve a stored report for comparison"""
    logger.info(f'[GET] Retrieve Comparison Report: UID={uid}')
    report = autoeval_db.get_comparison_request_report(uid)
    if not report:
        return JSONResponse(content={"error": "Report not found"}, status_code=404)
    return ComparisonRetrieveResponse(report=report)
