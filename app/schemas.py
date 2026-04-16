from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from app.enums import UserRole, Status, CaseStatus, CheckStatus

class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: Optional[str] = "USER"
    role_id: Optional[str] = None
    status: str = "ACTIVE"
    territory: Optional[str] = None
    business_unit: Optional[str] = None
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

class CaseCreateExtended(BaseModel):
    batch_id: str
    customer_id: str
    candidate: CandidateCreate
    services: List[str]
    case_ref_no: Optional[str] = None
    check_rates: Optional[Dict[str, float]] = None

class Case(CaseBase):
    id: str
    received_date: datetime
    completed_date: Optional[datetime] = None
    
    candidate: Optional[Candidate] = None
    customer: Optional[Customer] = None
    checks: List[VerificationCheck] = []

    model_config = ConfigDict(from_attributes=True)

class CaseRead(Case):
    candidate_name: Optional[str] = None
    customer_name: Optional[str] = None
    batch_date: Optional[datetime] = None
    batch_no: Optional[str] = None
    assigned_user_name: Optional[str] = None

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
    verifier_name: str
    verifier_email: str
    assigned: int
    completed: int
    in_progress: int

class VerifierDailyResponse(BaseModel):
    date: str
    verifiers: List[VerifierDailyStat]

class TodayClientRecord(BaseModel):
    client: str
    received: int
    completed: int
    pending: int
    insufficient: int

class TodayRecordsResponse(BaseModel):
    date: str
    records: List[TodayClientRecord]
    totals: TodayClientRecord
