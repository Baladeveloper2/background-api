from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from .models import UserRole, Status, CaseStatus, CheckStatus

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole
    role_id: Optional[str] = None # Added for structured RBAC
    status: Status = Status.ACTIVE
    territory: Optional[str] = None
    business_unit: Optional[str] = None
    bvs_permissions: Optional[Dict[str, Dict[str, bool]]] = None

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: Optional[Dict[str, bool]] = None

class RoleCreate(RoleBase):
    pass

class Role(RoleBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True


class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

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
    address_details: Optional[Dict[str, Any]] = None
    documents: Optional[List[Dict[str, Any]]] = None

class CandidateCreate(CandidateBase):
    pass

class Candidate(CandidateBase):
    id: str

    class Config:
        from_attributes = True

class BatchBase(BaseModel):
    customer_id: str
    batch_no: Optional[str] = None
    file_url: Optional[str] = None

class BatchCreate(BatchBase):
    pass

class Batch(BatchBase):
    id: str
    upload_date: datetime

    class Config:
        from_attributes = True

class BatchSummary(BaseModel):
    id: str
    batch_no: str
    customer_name: str
    upload_date: datetime
    case_count: int
    age_days: int
    pending_count: int
    tat: int
    total_value: float
    completed_date: Optional[datetime] = None
    status: str

    class Config:
        from_attributes = True

class CaseBase(BaseModel):
    case_ref_no: str
    customer_id: str
    candidate_id: str
    batch_id: Optional[str] = None
    status: CaseStatus = CaseStatus.PENDING
    tat_days: int = 0

class CaseCreate(CaseBase):
    pass

class Case(CaseBase):
    id: str
    received_date: datetime
    completed_date: Optional[datetime] = None

    class Config:
        from_attributes = True

class CaseRead(Case):
    candidate_name: Optional[str] = None
    customer_name: Optional[str] = None

    class Config:
        from_attributes = True

class VerificationCheckBase(BaseModel):
    case_id: str
    check_type: str
    status: CheckStatus = CheckStatus.INTERIM
    data: Optional[Dict[str, Any]] = None
    verifier_remarks: Optional[str] = None

class VerificationCheckCreate(VerificationCheckBase):
    pass

class VerificationCheck(VerificationCheckBase):
    id: str
    verified_date: Optional[datetime] = None

    class Config:
        from_attributes = True

class CustomerBase(BaseModel):
    name: str
    short_code: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    report_format: Optional[str] = "Report Format-1 (Normal)"
    customer_agreement: Optional[str] = None
    package_enabled: Optional[bool] = False
    status: Status = Status.ACTIVE
    pricing_config: Optional[Dict[str, float]] = None

class CustomerCreate(CustomerBase):
    pass

class Customer(CustomerBase):
    id: str

    class Config:
        from_attributes = True

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
    total_applicants: int
    current_month: int = 0
    today_entry: int
    today_entry_percent: float = 0
    insufficient_cases: int
    interim_cases: int = 0
    total_customers: int
    top_customer: str = ""
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
