from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from app.enums import UserRole, Status, CaseStatus, CheckStatus, NotificationCategory, NotificationChannel, QCStatus, FinalResult, QCIssueStatus, QCIssueType

class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: Optional[str] = "USER"
    role_id: Optional[str] = None
    status: str = "ACTIVE"
    territory: Optional[str] = None
    business_unit: Optional[str] = None
    customer_id: Optional[str] = None
    zone_id: Optional[str] = None
    branch_id: Optional[str] = None
    bvs_permissions: Optional[Dict[str, Any]] = None
    phone: Optional[str] = None
    is_2fa_enabled: Optional[bool] = False
    theme_preference: Optional[str] = "professional-violet"
    
    @field_validator('status', 'role', mode='before')
    @classmethod
    def uppercase_enums(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None

class RoleCreate(RoleBase):
    pass

class Role(RoleBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ModuleBase(BaseModel):
    name: str
    code: str
    category: str
    description: Optional[str] = None

class ModuleCreate(ModuleBase):
    pass

class Module(ModuleBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    role_id: Optional[str] = None
    status: Optional[Status] = None
    territory: Optional[str] = None
    business_unit: Optional[str] = None
    customer_id: Optional[str] = None
    zone_id: Optional[str] = None
    branch_id: Optional[str] = None
    bvs_permissions: Optional[Dict[str, Any]] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    is_2fa_enabled: Optional[bool] = None
    theme_preference: Optional[str] = None

class User(UserBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    status: Optional[str] = "success"
    temp_token: Optional[str] = None
    phone_masked: Optional[str] = None
    branding: Optional[Dict[str, Any]] = None

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class CandidateBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    dob: Optional[date] = None
    client_emp_code: Optional[str] = None
    address_details: Optional[Dict[str, Any]] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    documents: Optional[List[Dict[str, Any]]] = None
    pan_no: Optional[str] = None
    passport_no: Optional[str] = None
    nationality: Optional[str] = None
    identity_type: Optional[str] = None
    db_candidate_name: Optional[str] = None
    db_dob: Optional[date] = None
    database_scope: Optional[str] = None
    zone_id: Optional[str] = None
    customer_id: Optional[str] = None
    branch_id: Optional[str] = None
    created_by: Optional[str] = None
    assigned_executive_id: Optional[str] = None

    @field_validator('documents', mode='before')
    @classmethod
    def ensure_list(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, dict) and not v:
            return []
        if isinstance(v, dict):
            # This should not happen for a 'documents' field but just in case
            return []
        return v

class CandidateCreate(CandidateBase):
    pass

class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    dob: Optional[date] = None
    client_emp_code: Optional[str] = None
    address_details: Optional[Dict[str, Any]] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    documents: Optional[List[Dict[str, Any]]] = None
    pan_no: Optional[str] = None
    passport_no: Optional[str] = None
    nationality: Optional[str] = None
    identity_type: Optional[str] = None
    db_candidate_name: Optional[str] = None
    db_dob: Optional[date] = None
    database_scope: Optional[str] = None
    zone_id: Optional[str] = None
    customer_id: Optional[str] = None
    branch_id: Optional[str] = None
    assigned_executive_id: Optional[str] = None

import re

class CandidateCreateFull(CandidateBase):
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name is required")
        if not re.match(r'^[A-Za-z\s]+$', v):
            raise ValueError("Name can only contain letters and spaces")
        return v
        
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            raise ValueError("Mobile Number is required")
        if not re.match(r'^[6-9]\d{9}$', v):
            raise ValueError("Enter a valid 10-digit mobile number")
        return v
        
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[EmailStr]) -> Optional[EmailStr]:
        if not v:
            raise ValueError("Email is required")
        return v
        
    @field_validator('dob')
    @classmethod
    def validate_dob(cls, v: Optional[date]) -> Optional[date]:
        if not v:
            raise ValueError("DOB is required")
        if v > date.today():
            raise ValueError("DOB cannot be a future date")
        age = (date.today() - v).days / 365.25
        if age < 18:
            raise ValueError("Candidate must be at least 18 years old")
        return v
        
    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            raise ValueError("Gender is required")
        return v
        
    @field_validator('client_emp_code')
    @classmethod
    def validate_emp_code(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            raise ValueError("Client Emp Code is required")
        if ' ' in v:
            raise ValueError("Client Emp Code cannot contain spaces")
        return v

class Candidate(CandidateBase):
    id: str

    model_config = ConfigDict(from_attributes=True)

class BatchBase(BaseModel):
    customer_id: str
    zone_id: Optional[str] = None
    branch_id: Optional[str] = None
    batch_no: Optional[str] = None
    cl_ref_no: Optional[str] = None
    file_url: Optional[str] = None
    cases_count: Optional[int] = 0
    tat_days: Optional[int] = 10
    case_rate: Optional[float] = 0.0
    upload_date: Optional[datetime] = None

class BatchCreate(BatchBase):
    pass

class BatchUpdate(BaseModel):
    customer_id: Optional[str] = None
    zone_id: Optional[str] = None
    branch_id: Optional[str] = None
    batch_no: Optional[str] = None
    file_url: Optional[str] = None
    cases_count: Optional[int] = None
    tat_days: Optional[int] = None
    case_rate: Optional[float] = None
    upload_date: Optional[datetime] = None

class Batch(BatchBase):
    id: str

    model_config = ConfigDict(from_attributes=True)

class CandidateDraftBase(BaseModel):
    batch_id: str
    form_data: Dict[str, Any]

class CandidateDraftCreate(CandidateDraftBase):
    pass

class CandidateDraftResponse(CandidateDraftBase):
    id: str
    last_saved_at: datetime
    created_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class BatchSummary(BaseModel):
    id: str
    batch_no: str
    customer_id: str
    customer_name: str
    upload_date: datetime
    case_count: int
    intended_cases: int
    case_rate: float
    age_days: int
    pending_count: int
    verification_active_count: int = 0
    qc_active_count: int = 0
    qa_pending_count: int = 0
    completed_count: int
    tat: int
    total_value: float
    completed_date: Optional[datetime] = None
    file_url: Optional[str] = None
    status: str = "Entry Pending"

    model_config = ConfigDict(from_attributes=True)

class VerificationCheckBase(BaseModel):
    case_id: str
    check_type: str
    status: CheckStatus = CheckStatus.INTERIM
    data: Optional[Any] = None
    digital_token: Optional[str] = None
    verifier_remarks: Optional[str] = None
    rate: Optional[float] = 0.0

    @field_validator('status', mode='before')
    @classmethod
    def uppercase_check_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

class VerificationCheckCreate(VerificationCheckBase):
    pass

class VerificationCheckUpdate(BaseModel):
    check_type: Optional[str] = None
    status: Optional[CheckStatus] = None
    data: Optional[Any] = None
    digital_token: Optional[str] = None
    verifier_remarks: Optional[str] = None
    verified_date: Optional[datetime] = None
    
    # Finalization fields
    finalized_by: Optional[str] = None
    finalized_at: Optional[datetime] = None
    final_remarks: Optional[str] = None
    final_result: Optional[FinalResult] = None
    
    # Legacy QC-specific updates (compatibility)
    qc_verifier_id: Optional[str] = None
    qc_status: Optional[QCStatus] = None
    qc_remarks: Optional[str] = None
    qc_reviewed_at: Optional[datetime] = None

class VerificationDocumentRead(BaseModel):
    id: str
    file_name: str
    file_url: str
    file_type: Optional[str] = None
    is_primary: bool = False
    uploaded_at: datetime
    uploaded_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class VerificationLogRead(BaseModel):
    id: str
    action: str
    remarks: Optional[str] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    created_at: datetime
    performer_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class VerificationCheck(VerificationCheckBase):
    id: str
    verified_date: Optional[datetime] = None
    case_ref: Optional[str] = None
    candidate_name: Optional[str] = None
    customer_name: Optional[str] = None
    given_address: Optional[str] = None
    
    # New Operational Fields
    confidence_score: float = 0.0
    api_sync_status: str = "NOT_SYNCED"
    assigned_verifier_name: Optional[str] = None
    
    # Finalization Fields
    finalized_by: Optional[str] = None
    finalized_user_name: Optional[str] = None
    finalized_at: Optional[datetime] = None
    final_remarks: Optional[str] = None
    final_result: Optional[str] = None
    
    # Legacy QC Extension Fields (compatibility)
    qc_verifier_id: Optional[str] = None
    qc_verifier_name: Optional[str] = None
    qc_status: str = "APPROVED"
    qc_remarks: Optional[str] = None
    qc_reviewed_at: Optional[datetime] = None
    
    # Nested Relationships
    documents: List[VerificationDocumentRead] = []
    logs: List[VerificationLogRead] = []

    model_config = ConfigDict(from_attributes=True)


class CustomerBase(BaseModel):
    name: str
    short_code: Optional[str] = None
    city: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    report_format: Optional[str] = "Report Format-1 (Normal)"
    active_status: Optional[int] = 1 # 0 for Off, 1 for On
    status: Status = Status.ACTIVE
    pricing_config: Optional[Dict[str, float]] = None
    customer_agreement: Optional[str] = None
    documents: Optional[List[Dict[str, Any]]] = None
    zone_id: Optional[str] = None
    company_name: Optional[str] = None
    company_code: Optional[str] = None
    head_office: Optional[str] = None
    industry: Optional[str] = None
    
    @field_validator('status', mode='before')
    @classmethod
    def uppercase_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

class CustomerCreate(CustomerBase):
    pass

class Customer(CustomerBase):
    id: str
    created_at: datetime
    batches_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

class CaseBase(BaseModel):
    case_ref_no: Optional[str] = None
    customer_id: Optional[str] = None
    zone_id: Optional[str] = None
    branch_id: Optional[str] = None
    candidate_id: Optional[str] = None
    batch_id: Optional[str] = None
    status: CaseStatus = CaseStatus.PENDING
    tat_days: int = 0
    assigned_to: Optional[str] = None
    
    # Finalization fields
    finalized_by: Optional[str] = None
    finalized_at: Optional[datetime] = None
    final_remarks: Optional[str] = None
    
    # Legacy QC Compatibility
    qa_id: Optional[str] = None
    qc_id: Optional[str] = None
    ai_summary: Optional[str] = None
    file_no: Optional[str] = None
    final_result: Optional[str] = None
    final_report_status: Optional[str] = None
    qc_remarks: Optional[str] = None
    
    @field_validator('status', mode='before')
    @classmethod
    def uppercase_case_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            val = v.upper()
            mapping = {
                "PENDING": "PENDING",
                "NEW": "PENDING",
                "LINK_SHARED": "LINK_SHARED",
                "INVITED": "INVITED",
                
                "IN_VERIFICATION": "WIP",
                "VERIFICATION": "WIP",
                "IN_PROGRESS": "WIP",
                "REOPENED": "WIP",
                "DOCUMENTS_SUBMITTED": "WIP",
                
                "QC": "REVIEW",
                "QC_REVIEW": "REVIEW",
                "QA_PENDING": "REVIEW",
                "QC_PENDING": "REVIEW",
                "UNDER_REVIEW": "REVIEW",
                
                "COMPLETED": "FINALIZED",
                "CLOSED": "FINALIZED",
                "CANCELLED": "FINALIZED",
                "QC_VERIFIED": "FINALIZED",
                "POSITIVE": "FINALIZED",
                "NEGATIVE": "FINALIZED",
                "DISCREPANCY": "FINALIZED",
                "UNABLE_TO_VERIFY": "FINALIZED",
                
                "INSUFFICIENT": "ON_HOLD",
                "INSUFFICIENCY": "ON_HOLD",
                "HOLD": "ON_HOLD",
                "ON_HOLD": "ON_HOLD",
            }
            return mapping.get(val, val)
        return v

class CaseCreate(CaseBase):
    pass

class CaseUpdate(BaseModel):
    case_ref_no: Optional[str] = None
    customer_id: Optional[str] = None
    zone_id: Optional[str] = None
    branch_id: Optional[str] = None
    candidate_id: Optional[str] = None
    batch_id: Optional[str] = None
    status: Optional[CaseStatus] = None
    tat_days: Optional[int] = None
    candidate: Optional[CandidateUpdate] = None
    services: Optional[List[str]] = None
    check_rates: Optional[Dict[str, float]] = None
    assigned_to: Optional[str] = None
    
    # Finalization fields
    finalized_by: Optional[str] = None
    finalized_at: Optional[datetime] = None
    final_remarks: Optional[str] = None

    # Legacy compatibility fields
    qa_id: Optional[str] = None
    qc_id: Optional[str] = None
    assigned_at: Optional[datetime] = None
    received_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    scope_of_work: Optional[str] = None
    check_scopes: Optional[Dict[str, str]] = None
    file_no: Optional[str] = None
    final_result: Optional[str] = None
    final_report_status: Optional[str] = None
    qc_remarks: Optional[str] = None

    @field_validator('status', mode='before')
    @classmethod
    def uppercase_case_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            val = v.upper()
            mapping = {
                "PENDING": "ASSIGNED",
                "NEW": "ASSIGNED",
                "LINK_SHARED": "ASSIGNED",
                "INVITED": "ASSIGNED",
                
                "IN_VERIFICATION": "WIP",
                "VERIFICATION": "WIP",
                "IN_PROGRESS": "WIP",
                "REOPENED": "WIP",
                "DOCUMENTS_SUBMITTED": "WIP",
                
                "QC": "REVIEW",
                "QC_REVIEW": "REVIEW",
                "QA_PENDING": "REVIEW",
                "QC_PENDING": "REVIEW",
                "UNDER_REVIEW": "REVIEW",
                
                "COMPLETED": "FINALIZED",
                "CLOSED": "FINALIZED",
                "CANCELLED": "FINALIZED",
                "QC_VERIFIED": "FINALIZED",
                "POSITIVE": "FINALIZED",
                "NEGATIVE": "FINALIZED",
                "DISCREPANCY": "FINALIZED",
                "UNABLE_TO_VERIFY": "FINALIZED",
                
                "INSUFFICIENT": "ON_HOLD",
                "INSUFFICIENCY": "ON_HOLD",
                "HOLD": "ON_HOLD",
                "ON_HOLD": "ON_HOLD",
            }
            return mapping.get(val, val)
        return v

class CaseCreateExtended(BaseModel):
    batch_id: str
    customer_id: str
    branch_id: Optional[str] = None
    zone_id: Optional[str] = None
    candidate: CandidateCreateFull
    services: List[str]
    case_ref_no: Optional[str] = None
    check_rates: Optional[Dict[str, float]] = None
    check_scopes: Optional[Dict[str, str]] = None
    scope_of_work: Optional[str] = None # Keeping for backward compatibility if needed, though we moved to per-check
    file_no: Optional[str] = None

class Case(CaseBase):
    id: str
    received_date: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    tat_days: Optional[int] = 0
    verifier_revoke_count: Optional[int] = 0
    qc_revoke_count: Optional[int] = 0
    is_in_tat: Optional[int] = 1
    ai_summary: Optional[str] = None
    file_no: Optional[str] = None
    final_result: Optional[str] = None
    final_report_status: Optional[str] = None
    qc_remarks: Optional[str] = None
    insufficiency_count: Optional[int] = 0
    checks: List[VerificationCheck] = []

    model_config = ConfigDict(from_attributes=True)

class InsufficiencyRead(BaseModel):
    id: str
    case_id: str
    check_id: str
    raised_by: str
    raised_by_role: Optional[str] = None
    message: str
    status: str
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_remarks: Optional[str] = None
    created_at: datetime
    check_name: Optional[str] = None
    due_date: Optional[datetime] = None
    notification_count: Optional[int] = 0
    last_notified_at: Optional[datetime] = None
    response_at: Optional[datetime] = None
    timeline: Optional[List[Dict[str, Any]]] = []

    model_config = ConfigDict(from_attributes=True)


class CaseRead(Case):
    candidate: Optional[Candidate] = None
    candidate_name: Optional[str] = None
    customer_name: Optional[str] = None
    batch_date: Optional[datetime] = None
    batch_no: Optional[str] = None
    assigned_user_name: Optional[str] = None
    assigned_user_role: Optional[str] = None
    finalized_user_name: Optional[str] = None
    qa_user_name: Optional[str] = None
    qc_user_name: Optional[str] = None
    queue_age: Optional[str] = None
    predicted_tat: Optional[int] = None
    is_at_risk: Optional[bool] = False
    in_tat: Optional[int] = 0
    out_tat: Optional[int] = 0
    insufficiencies: List[InsufficiencyRead] = []
    verification_logs: List[VerificationLogRead] = [] # Global Case Logs

    model_config = ConfigDict(from_attributes=True)


class InsufficiencyLogBase(BaseModel):
    case_id: str
    user_id: str
    from_status: str
    notes: Optional[str] = None

class InsufficiencyLog(InsufficiencyLogBase):
    id: str
    marked_at: datetime
    resolved_at: Optional[datetime] = None
    user_name: Optional[str] = None
    case_ref_no: Optional[str] = None
    customer_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PartnerBase(BaseModel):
    name: str
    executive_lead: Optional[str] = None
    contact_points: Optional[str] = None
    regional_cluster: Optional[str] = None
    status: Status = Status.ACTIVE
    cloud_status: Optional[str] = "ACTIVE"
    
    @field_validator('status', mode='before')
    @classmethod
    def uppercase_partner_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

class PartnerCreate(PartnerBase):
    pass

class Partner(PartnerBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ServiceDistribution(BaseModel):
    label: str
    value: int
    color: str

class TATSummary(BaseModel):
    category: str
    days: float

class ActivityItem(BaseModel):
    id: str
    action: str
    details: str
    timestamp: datetime
    user_email: Optional[str] = None

class VerificationPendingItem(BaseModel):
    type: str
    case: int
    status: str = "Pending"
    date: str = ""

class DataEntryItem(BaseModel):
    user: str
    count: int
    percent: float = 0

class CheckTypeCount(BaseModel):
    type: str
    count: int

class CaseAnalysisPoint(BaseModel):
    name: str
    total: int = 0
    completed: int = 0
    pending: int = 0

class GeoPoint(BaseModel):
    name: str
    value: int
    color: str

class ExecutionPoint(BaseModel):
    subject: str
    A: int
    B: int = 0

class ActivityLogItem(BaseModel):
    id: int
    icon: str
    action: str
    time: str
    user: str

class DashboardStats(BaseModel):
    total_candidates: int
    current_month: int = 0
    today_entry: int
    today_entry_percent: float = 0
    insufficient_cases: int
    interim_cases: int = 0
    total_clients: int
    top_client: str = ""
    pending_verification: int = 0
    pending_qc: int = 0
    completed_today: int = 0
    total_completed: int = 0
    total_revenue: float = 0.0
    entry_pending_count: int = 0
    verification_pending_count: int = 0
    at_risk_count: int = 0
    candidate_submissions_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    amber_count: int = 0
    stop_count: int = 0
    total_assigned: int = 0
    case_analysis: List[CaseAnalysisPoint] = []
    verification_pending: List[VerificationPendingItem] = []
    today_data_entry: List[DataEntryItem] = []
    today_execution: List[CheckTypeCount] = []
    today_qc: List[CheckTypeCount] = []
    geo_data: List[GeoPoint] = []
    execution_stats: List[ExecutionPoint] = []
    activity_log: List[ActivityLogItem] = []
    status_counts: Dict[str, int] = {}
    address_change_requests: Dict[str, int] = {}
class DailyStat(BaseModel):
    customer: str
    received: int
    completed: int
    pending: int
    insufficient: int

class DailyReportResponse(BaseModel):
    date: str
    stats: List[DailyStat]
    totals: DailyStat

class VerifierDailyStat(BaseModel):
    verifier_id: str
    verifier_name: str
    verifier_email: str
    role: str
    assigned: int
    data_entry: int = 0
    wip: int = 0
    insufficient: int = 0
    interim: int = 0
    qc_pending: int = 0
    completed: int = 0
    today_tat: int = 0
    revoked: int = 0
    earnings: float = 0.0
    efficiency: float = 0.0

class VerifierDailyResponse(BaseModel):
    date: str
    verifiers: List[VerifierDailyStat]

class TodayRecord(BaseModel):
    client: str
    received: int
    data_entry: int = 0
    wip: int = 0
    pending: int = 0
    insufficient: int = 0
    interim: int = 0
    qc_pending: int = 0
    completed: int = 0
    today_tat: int = 0
    verifier_revoke_count: int = 0
    qc_revoke_count: int = 0
    tat_percent: float = 0.0

class TodayRecordsResponse(BaseModel):
    date: str
    records: List[TodayRecord]
    totals: TodayRecord

class HeatmapPoint(BaseModel):
    hour: str
    load: int
    forecast: int

class ThroughputResponse(BaseModel):
    date: str
    data: List[HeatmapPoint]

class AuditLogRead(BaseModel):
    id: str
    user_id: str
    action: str
    resource_id: Optional[str] = None
    details: str
    timestamp: datetime
    user_full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class BulkActionRequest(BaseModel):
    case_ids: List[str]
    action: str # 'status', 'assign', 'delete', 'allocate'
    target_value: Optional[str] = None

class CaseCommentBase(BaseModel):
    content: str

class CaseCommentCreate(CaseCommentBase):
    pass

class CaseComment(CaseCommentBase):
    id: str
    case_id: str
    user_id: str
    created_at: datetime
    user_full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class NotificationRead(BaseModel):
    id: str
    title: str
    message: str
    category: NotificationCategory
    channel: NotificationChannel
    is_read: int
    case_id: Optional[str] = None
    case_name: Optional[str] = None
    case_ref: Optional[str] = None
    case_status: Optional[str] = None
    extra_data: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class NotificationMarkRead(BaseModel):
    notification_ids: List[str]

class ResolveInsufficiencyRequest(BaseModel):
    remarks: str
    check_id: Optional[str] = None
    documents: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None

class ClientRespondInsufficiencyRequest(BaseModel):
    remarks: str
    documents: Optional[List[Dict[str, Any]]] = None

class VerifierReviewInsufficiencyRequest(BaseModel):
    action: str # APPROVE, REJECT, NEED_MORE_INFO
    remarks: Optional[str] = None

class SendBgvLinkRequest(BaseModel):
    checks: List[str]
    email_subject: Optional[str] = None
    email_message: Optional[str] = None

class BulkInsufficientRequest(BaseModel):
    case_ids: List[str]
    reason: Optional[str] = "Incomplete documentation"

class RaiseInsufficiencyRequest(BaseModel):
    message: str
    documents: Optional[List[Dict[str, Any]]] = []

class PublicInsufficiencyResponse(BaseModel):
    id: str
    status: str
    message: str
    candidate_name: str
    case_ref: str
    check_name: str
    customer_name: str

class PublicInsufficiencySubmit(BaseModel):
    remarks: str
    documents: List[dict] = []

class InviteCandidateRequest(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    emp_id: Optional[str] = None
    customer_id: Optional[str] = None

class BulkAllocateRequest(BaseModel):
    case_ids: List[str]
    user_id: Optional[str] = None

class FaceMatchRequest(BaseModel):
    url1: str
    url2: str

class OcrExtractRequest(BaseModel):
    url: str

class QCFieldIssueBase(BaseModel):
    case_id: Optional[str] = None
    check_id: Optional[str] = None
    field_name: str
    issue_type: QCIssueType
    comment: Optional[str] = None
    assigned_to: Optional[str] = None

class QCFieldIssueCreate(QCFieldIssueBase):
    pass

class QCFieldIssueRead(QCFieldIssueBase):
    id: str
    status: QCIssueStatus
    raised_by: str
    raised_by_name: Optional[str] = None
    assigned_to_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QCFieldIssueResolve(BaseModel):
    comment: Optional[str] = None

class FinalizeCaseRequest(BaseModel):
    case_id: Optional[str] = None
    remarks: Optional[str] = None
    final_result: Optional[str] = None


class SystemSettingBase(BaseModel):
    key: str
    value: str

class SystemSettingRead(SystemSettingBase):
    id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SystemSettingUpdate(BaseModel):
    value: str

class OcrExtractionCreate(BaseModel):
    file_name: str
    file_url: str
    s3_key: Optional[str] = None
    candidate_id: Optional[str] = None
    batch_id: Optional[str] = None

class OcrClassificationRead(BaseModel):
    id: str
    extraction_id: str
    detected_type: str
    confidence: float
    manual_override_type: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class OcrProcessingLogRead(BaseModel):
    id: str
    extraction_id: str
    step: str
    status: str
    details: Optional[str] = None
    duration_ms: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class OcrReviewQueueRead(BaseModel):
    id: str
    extraction_id: str
    confidence_score: float
    assigned_to: Optional[str] = None
    status: str
    reviewer_comments: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class OcrFieldMappingRead(BaseModel):
    id: str
    document_type: str
    ocr_field_name: str
    bgv_field_name: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class OcrExtractionRead(BaseModel):
    id: str
    file_name: str
    file_url: str
    s3_key: Optional[str] = None
    ocr_status: str
    ocr_progress: int
    ocr_started_at: Optional[datetime] = None
    ocr_completed_at: Optional[datetime] = None
    ocr_duration_ms: int = 0
    ocr_json: Dict[str, Any] = {}
    ocr_engine: Optional[str] = None
    ocr_error: Optional[str] = None
    ocr_version: str = "2.0"
    last_retry_at: Optional[datetime] = None
    document_type: str
    confidence_score: float
    extracted_data: Dict[str, Any]
    confidence_scores: Dict[str, Any]
    fraud_flags: List[str]
    review_status: str
    is_verified: bool
    candidate_id: Optional[str] = None
    batch_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class OcrExtractionUpdate(BaseModel):
    extracted_data: Optional[Dict[str, Any]] = None
    review_status: Optional[str] = None
    is_verified: Optional[bool] = None

class OcrExtractionAction(BaseModel):
    action: str # APPROVE, REJECT, REPROCESS


class OcrAnalyticsRead(BaseModel):
    id: str
    extraction_id: str
    engine_used: Optional[str] = None
    processing_time_ms: int
    retry_count: int
    overall_confidence: float
    missing_fields: List[str]
    preprocessing_steps: List[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


