from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from app.enums import UserRole, Status, CaseStatus, CheckStatus, NotificationCategory, NotificationChannel

class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: Optional[str] = "USER"
    role_id: Optional[str] = None
    status: str = "ACTIVE"
    territory: Optional[str] = None
    business_unit: Optional[str] = None
    customer_id: Optional[str] = None
    bvs_permissions: Optional[Dict[str, Any]] = None
    
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
    bvs_permissions: Optional[Dict[str, Any]] = None
    password: Optional[str] = None

class User(UserBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

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

class Candidate(CandidateBase):
    id: str

    model_config = ConfigDict(from_attributes=True)

class BatchBase(BaseModel):
    customer_id: str
    batch_no: Optional[str] = None
    file_url: Optional[str] = None
    cases_count: Optional[int] = 0
    tat_days: Optional[int] = 10
    case_rate: Optional[float] = 0.0
    upload_date: Optional[datetime] = None

class BatchCreate(BatchBase):
    pass

class BatchUpdate(BaseModel):
    customer_id: Optional[str] = None
    batch_no: Optional[str] = None
    file_url: Optional[str] = None
    cases_count: Optional[int] = None
    tat_days: Optional[int] = None
    case_rate: Optional[float] = None
    upload_date: Optional[datetime] = None

class Batch(BatchBase):
    id: str

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
    data: Optional[Dict[str, Any]] = None
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
    data: Optional[Dict[str, Any]] = None
    digital_token: Optional[str] = None
    verifier_remarks: Optional[str] = None
    verified_date: Optional[datetime] = None

class VerificationCheck(VerificationCheckBase):
    id: str
    verified_date: Optional[datetime] = None
    case_ref: Optional[str] = None
    candidate_name: Optional[str] = None
    customer_name: Optional[str] = None
    given_address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class CustomerBase(BaseModel):
    name: str
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

    model_config = ConfigDict(from_attributes=True)

class CaseBase(BaseModel):
    case_ref_no: Optional[str] = None
    customer_id: str
    candidate_id: Optional[str] = None
    batch_id: Optional[str] = None
    status: CaseStatus = CaseStatus.PENDING
    tat_days: int = 0
    assigned_to: Optional[str] = None
    qa_id: Optional[str] = None
    qc_id: Optional[str] = None
    ai_summary: Optional[str] = None
    file_no: Optional[str] = None
    
    @field_validator('status', mode='before')
    @classmethod
    def uppercase_case_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

class CaseCreate(CaseBase):
    pass

class CaseUpdate(BaseModel):
    case_ref_no: Optional[str] = None
    customer_id: Optional[str] = None
    candidate_id: Optional[str] = None
    batch_id: Optional[str] = None
    status: Optional[CaseStatus] = None
    tat_days: Optional[int] = None
    candidate: Optional[CandidateUpdate] = None
    services: Optional[List[str]] = None
    check_rates: Optional[Dict[str, float]] = None
    assigned_to: Optional[str] = None
    qa_id: Optional[str] = None
    qc_id: Optional[str] = None
    assigned_at: Optional[datetime] = None
    received_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    scope_of_work: Optional[str] = None
    check_scopes: Optional[Dict[str, str]] = None
    file_no: Optional[str] = None

class CaseCreateExtended(BaseModel):
    batch_id: str
    customer_id: str
    candidate: CandidateCreate
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
    insufficiency_count: Optional[int] = 0
    checks: List[VerificationCheck] = []

    model_config = ConfigDict(from_attributes=True)

class CaseRead(Case):
    candidate: Optional[Candidate] = None
    candidate_name: Optional[str] = None
    customer_name: Optional[str] = None
    batch_date: Optional[datetime] = None
    batch_no: Optional[str] = None
    assigned_user_name: Optional[str] = None
    assigned_user_role: Optional[str] = None
    qa_user_name: Optional[str] = None
    qc_user_name: Optional[str] = None
    queue_age: Optional[str] = None
    predicted_tat: Optional[int] = None
    is_at_risk: Optional[bool] = False
    in_tat: Optional[int] = 0
    out_tat: Optional[int] = 0

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
    case_analysis: List[CaseAnalysisPoint] = []
    verification_pending: List[VerificationPendingItem] = []
    today_data_entry: List[DataEntryItem] = []
    today_execution: List[CheckTypeCount] = []
    today_qc: List[CheckTypeCount] = []
    geo_data: List[GeoPoint] = []
    execution_stats: List[ExecutionPoint] = []
    activity_log: List[ActivityLogItem] = []
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
    id: str
    verifier_name: str
    verifier_email: str
    role: str
    assigned: int
    completed: int
    in_progress: int
    insufficient: int = 0
    revoked: int = 0

class VerifierDailyResponse(BaseModel):
    date: str
    verifiers: List[VerifierDailyStat]

class TodayRecord(BaseModel):
    client: str
    received: int
    completed: int
    pending: int
    insufficient: int
    verifier_revoke_count: Optional[int] = 0
    qc_revoke_count: Optional[int] = 0
    tat_percent: Optional[float] = 0.0

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

