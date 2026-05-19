import uuid
import json
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Date, Integer, Text, TypeDecorator, Float, Index, Boolean
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import UserRole, Status, CaseStatus, CheckStatus, NotificationCategory, NotificationChannel, QCStatus, FinalResult, QCIssueStatus, QCIssueType
from datetime import datetime
import os
from cryptography.fernet import Fernet

# Initialize Encryption Key from environment or generate a stable fallback for dev
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Use a valid 32-byte base64 key for development
    ENCRYPTION_KEY = b'F_AbrO9ACR5CuZALXglre4TUCIiO2fsj9gzK7kTqL1s='
fernet = Fernet(ENCRYPTION_KEY)

class JSONEncodedDict(TypeDecorator):
    impl = MEDIUMTEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return '{}'
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if not value:
            return {}
        return json.loads(value)

class JSONEncodedList(TypeDecorator):
    impl = MEDIUMTEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return '[]'
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if not value:
            return []
        try:
            data = json.loads(value)
            return data if isinstance(data, list) else []
        except:
            return []

class EncryptedString(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for AES-256 field-level encryption.
    Automatically encrypts data on write and decrypts on read.
    """
    impl = String(1024) # Extra space for encryption overhead
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            # Fallback for existing plain text data during migration phase
            return value

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), default=UserRole.USER)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=True) # New RBAC Role
    status = Column(String(50), default=Status.ACTIVE)
    territory = Column(String(255), nullable=True)
    business_unit = Column(String(255), nullable=True)
    bvs_permissions = Column(JSONEncodedDict, default=lambda: {})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=True)

    # Relationships
    role_rel = relationship("Role", backref="users")
    customer = relationship("Customer", backref="users")

    # Composite index for filtering users by customer and status
    __table_args__ = (
        Index("index_user_customer_status", "customer_id", "status"),
        {'extend_existing': True}
    )

class Role(Base):
    __tablename__ = "roles"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True, nullable=False)
    description = Column(String(500), nullable=True)
    permissions = Column(JSONEncodedDict, default=lambda: {}) # e.g. {"bvs.verification": true}
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Module(Base):
    __tablename__ = "modules"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True, nullable=False)
    code = Column(String(100), unique=True, nullable=False) # e.g. "bvs.verification"
    category = Column(String(100), nullable=False) # e.g. "BVS"
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Customer(Base):
    __tablename__ = "customers"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), index=True)
    short_code = Column(String(50), unique=True, index=True, nullable=True)
    city = Column(String(100), nullable=True)
    contact_person = Column(String(255))
    phone = Column(String(50))
    email = Column(String(255))
    address = Column(Text)
    report_format = Column(String(50))
    customer_agreement = Column(String(255), nullable=True)
    active_status = Column(Integer, default=1)
    status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    pricing_config = Column(JSONEncodedDict)
    documents = Column(JSONEncodedList)
    # White-Labeling Branding
    brand_primary_color = Column(String(20), default="#7c3aed")
    brand_secondary_color = Column(String(20), default="#f5f3ff")
    logo_url = Column(String(512), nullable=True)
    custom_domain = Column(String(255), nullable=True)

class ClientDocument(Base):
    __tablename__ = "client_documents"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=False)
    name = Column(String(255), nullable=False) # File or Folder name
    is_folder = Column(Boolean, default=False)
    parent_id = Column(String(36), ForeignKey("client_documents.id"), nullable=True)
    file_path = Column(String(500), nullable=True)
    file_type = Column(String(100), nullable=True)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    read_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", backref="client_docs")
    uploader = relationship("User", foreign_keys=[uploaded_by], backref="uploaded_client_docs")
    reader = relationship("User", foreign_keys=[read_by], backref="read_client_docs")

class Partner(Base):
    __tablename__ = "partners"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    executive_lead = Column(String(255))
    contact_points = Column(String(255))
    regional_cluster = Column(String(255))
    status = Column(String(50), default=Status.ACTIVE)
    cloud_status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), index=True)
    phone = Column(String(20), index=True)
    dob = Column(Date)
    client_emp_code = Column(String(50), nullable=True, index=True)
    address_details = Column(JSONEncodedDict)
    gender = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    documents = Column(JSONEncodedList)
    
    # Global Database / Identity specialized fields (Encrypted)
    pan_no = Column(EncryptedString, nullable=True, index=True)
    passport_no = Column(EncryptedString, nullable=True, index=True)
    nationality = Column(String(100), nullable=True)
    identity_type = Column(String(100), nullable=True)
    db_candidate_name = Column(String(255), nullable=True)
    db_dob = Column(Date, nullable=True)
    database_scope = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class Batch(Base):
    __tablename__ = "batches"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(36), ForeignKey("customers.id"), index=True)
    batch_no = Column(String(50), unique=True, index=True)
    cl_ref_no = Column(String(50), nullable=True, index=True)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    file_url = Column(String(255))
    cases_count = Column(Integer, default=0)
    tat_days = Column(Integer, default=10)
    case_rate = Column(Float, default=0.0)

class Case(Base):
    __tablename__ = "cases"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_ref_no = Column(String(50), unique=True, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    batch_id = Column(String(36), ForeignKey("batches.id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(String(50), default=CaseStatus.PENDING, index=True)
    assigned_to = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    finalized_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    received_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    link_shared_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    completed_date = Column(DateTime(timezone=True), nullable=True, index=True)
    tat_days = Column(Integer, default=0)
    verifier_revoke_count = Column(Integer, default=0)
    is_in_tat = Column(Integer, default=1)
    ai_summary = Column(Text, nullable=True)
    file_no = Column(String(50), nullable=True, index=True)
    insufficiency_count = Column(Integer, default=0)
    # SLA Breach Prediction & Risk Analytics
    risk_score = Column(Integer, default=0) # 0-100 probability
    risk_factors = Column(JSONEncodedDict, default=lambda: {}) # Reasons: ["Slow Employer Response", "Missing Docs"]
    last_risk_assessment = Column(DateTime, nullable=True)
    
    # Global Verdict & Quality Audit Rollup
    final_result = Column(String(50), nullable=True) # Holistic Case Verdict
    final_report_status = Column(String(50), nullable=True) # POSITIVE, NEGATIVE, DISCREPANCY, INTERIM, INSUFFICIENT
    final_remarks = Column(Text, nullable=True) # Overall Finalization Remarks

    __table_args__ = (
        Index("index_customer_status", "customer_id", "status"),
        Index("index_assigned_status", "assigned_to", "status"),
        Index("index_status_received", "status", "received_date"),
        Index("index_assigned_status_date", "assigned_to", "status", "received_date"),
        {'extend_existing': True}
    )

    candidate = relationship("Candidate", backref="cases")
    customer = relationship("Customer", backref="cases")
    batch = relationship("Batch", backref="cases")
    assigned_user = relationship("User", foreign_keys=[assigned_to], backref="assigned_cases")
    finalized_user = relationship("User", foreign_keys=[finalized_by], backref="finalized_cases")
    checks = relationship("VerificationCheck", back_populates="case", cascade="all, delete-orphan")
    insufficiencies = relationship("Insufficiency", back_populates="case", cascade="all, delete-orphan")

    @property
    def qc_remarks(self):
        return self.final_remarks
    @qc_remarks.setter
    def qc_remarks(self, val):
        self.final_remarks = val

    @property
    def qc_id(self):
        return self.finalized_by
    @qc_id.setter
    def qc_id(self, val):
        self.finalized_by = val

    @property
    def qa_id(self):
        return self.finalized_by
    @qa_id.setter
    def qa_id(self, val):
        self.finalized_by = val

    @property
    def qc_user(self):
        return self.finalized_user
    @qc_user.setter
    def qc_user(self, val):
        self.finalized_user = val

    @property
    def qa_user(self):
        return self.finalized_user
    @qa_user.setter
    def qa_user(self, val):
        self.finalized_user = val

class VerificationCheck(Base):
    __tablename__ = "verification_checks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    case = relationship("Case", back_populates="checks")
    check_type = Column(String(100), index=True)
    status = Column(String(50), default=CheckStatus.VERIFICATION, index=True)
    data = Column(JSONEncodedDict)
    digital_token = Column(String(100), unique=True, nullable=True)
    verifier_remarks = Column(Text)
    verified_date = Column(DateTime(timezone=True), nullable=True, index=True)
    rate = Column(Float, default=0.0)
    
    # New Operational Fields for Dynamic Workflow
    confidence_score = Column(Float, default=0.0) # 0-100
    api_sync_status = Column(String(100), default="NOT_SYNCED") # e.g. "SYNCED", "FAILED", "PENDING"
    assigned_verifier_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    finalized_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    final_remarks = Column(Text, nullable=True)
    final_result = Column(String(50), nullable=True) # Maps to FinalResult Enum string values
    
    # Relationships
    assigned_verifier = relationship("User", foreign_keys=[assigned_verifier_id])
    finalized_user = relationship("User", foreign_keys=[finalized_by])
    
    @property
    def assigned_verifier_name(self):
        return self.assigned_verifier.full_name if self.assigned_verifier else None

    @property
    def finalized_user_name(self):
        return self.finalized_user.full_name if self.finalized_user else None

    # Legacy QC Compatibility Properties
    @property
    def qc_verifier_id(self):
        return self.finalized_by
    @qc_verifier_id.setter
    def qc_verifier_id(self, val):
        self.finalized_by = val

    @property
    def qc_status(self):
        return "APPROVED"
    @qc_status.setter
    def qc_status(self, val):
        pass

    @property
    def qc_remarks(self):
        return self.final_remarks
    @qc_remarks.setter
    def qc_remarks(self, val):
        self.final_remarks = val

    @property
    def qc_reviewed_at(self):
        return self.finalized_at
    @qc_reviewed_at.setter
    def qc_reviewed_at(self, val):
        self.finalized_at = val

    @property
    def qc_verifier(self):
        return self.finalized_user
    @qc_verifier.setter
    def qc_verifier(self, val):
        self.finalized_user = val

    @property
    def qc_verifier_name(self):
        return self.finalized_user_name

    insufficiencies = relationship("Insufficiency", back_populates="check", cascade="all, delete-orphan")
    documents = relationship("VerificationDocument", back_populates="check", cascade="all, delete-orphan")
    logs = relationship("VerificationLog", back_populates="check", cascade="all, delete-orphan")

class VerificationDocument(Base):
    __tablename__ = "verification_documents"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    check_id = Column(String(36), ForeignKey("verification_checks.id", ondelete="CASCADE"), index=True)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(512), nullable=False) # S3 Public URL or signed URL
    file_type = Column(String(100))
    s3_key = Column(String(255), nullable=True)
    is_primary = Column(Boolean, default=False)
    uploaded_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    check = relationship("VerificationCheck", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by_id])
    
    @property
    def uploaded_by_name(self):
        return self.uploader.full_name if self.uploader else None

class VerificationLog(Base):
    __tablename__ = "verification_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    check_id = Column(String(36), ForeignKey("verification_checks.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String(255), nullable=False) # e.g. "STATUS_UPDATED", "DOCUMENT_UPLOADED"
    performed_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    remarks = Column(Text, nullable=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    case = relationship("Case", backref="verification_logs")
    check = relationship("VerificationCheck", back_populates="logs")
    performer = relationship("User", foreign_keys=[performed_by_id])
    
    @property
    def performer_name(self):
        return self.performer.full_name if self.performer else None


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    action = Column(String(255), index=True)
    resource_id = Column(String(100), index=True, nullable=True)
    details = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("index_audit_resource_time", "resource_id", "timestamp"),
        {'extend_existing': True}
    )

class CaseComment(Base):
    __tablename__ = "case_comments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user = relationship("User")
    case = relationship("Case", backref="comments")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    title = Column(String(255))
    message = Column(Text)
    category = Column(Enum(NotificationCategory), default=NotificationCategory.SYSTEM_ALERT)
    channel = Column(Enum(NotificationChannel), default=NotificationChannel.SYSTEM)
    is_read = Column(Integer, default=0, index=True)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True)
    extra_data = Column(JSONEncodedDict, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("index_user_unread", "user_id", "is_read"),
        {'extend_existing': True}
    )

    user = relationship("User", backref="notifications")
    case_item = relationship("Case")

class RevokeLog(Base):
    __tablename__ = "revoke_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    revoke_type = Column(String(50), nullable=False)
    from_status = Column(String(50), nullable=False)
    to_status = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    revoked_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user = relationship("User")
    case = relationship("Case", backref="revoke_logs")

class InsufficiencyLog(Base):
    __tablename__ = "insufficiency_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    check_id = Column(String(36), ForeignKey("verification_checks.id", ondelete="CASCADE"), index=True, nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    from_status = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    marked_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    user = relationship("User")
    case = relationship("Case", backref="insufficiency_logs")
    check = relationship("VerificationCheck", backref="insufficiency_logs")

class Insufficiency(Base):
    __tablename__ = "insufficiencies"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    check_id = Column(String(36), ForeignKey("verification_checks.id", ondelete="CASCADE"), index=True, nullable=False)
    raised_by = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    role = Column(String(50))
    message = Column(Text, nullable=False)
    documents = Column(JSONEncodedList) # Support for customer evidence uploads
    status = Column(String(50), default="INSUFFICIENT")
    is_resolved = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_remarks = Column(Text, nullable=True)
    token = Column(String(100), unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    case = relationship("Case", back_populates="insufficiencies")
    check = relationship("VerificationCheck", back_populates="insufficiencies")
    user = relationship("User", foreign_keys=[raised_by], backref="raised_insufficiencies")
    resolver = relationship("User", foreign_keys=[resolved_by], backref="resolved_insufficiencies")
    updater = relationship("User", foreign_keys=[updated_by], backref="updated_insufficiencies")

class DashboardSummary(Base):
    __tablename__ = "dashboard_summaries"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(36), ForeignKey("customers.id"), index=True, nullable=True)
    summary_date = Column(Date, index=True)
    total_received = Column(Integer, default=0)
    total_completed = Column(Integer, default=0)
    total_pending = Column(Integer, default=0)
    total_at_risk = Column(Integer, default=0)
    average_velocity = Column(Float, default=0.0)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    customer = relationship("Customer")

class DocumentMetadata(Base):
    __tablename__ = "document_metadata"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_hash = Column(String(64), index=True, nullable=False)
    file_name = Column(String(255))
    mime_type = Column(String(100))
    size = Column(Integer)
    uploader_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    uploader = relationship("User")
    candidate = relationship("Candidate")

class QCFieldIssue(Base):
    __tablename__ = "qc_field_issues"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    check_id = Column(String(36), ForeignKey("verification_checks.id", ondelete="CASCADE"), index=True, nullable=True)
    field_name = Column(String(255), nullable=False)
    issue_type = Column(Enum(QCIssueType), nullable=False)
    comment = Column(Text, nullable=True)
    raised_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    assigned_to = Column(String(36), ForeignKey("users.id"), nullable=True) # Usually the original verifier
    status = Column(Enum(QCIssueStatus), default=QCIssueStatus.OPEN, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    case = relationship("Case", backref="qc_field_issues")
    check = relationship("VerificationCheck", backref="qc_field_issues")
    raiser = relationship("User", foreign_keys=[raised_by], backref="raised_qc_issues")
    assignee = relationship("User", foreign_keys=[assigned_to], backref="assigned_qc_issues")
