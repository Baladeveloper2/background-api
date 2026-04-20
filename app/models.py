import uuid
import json
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Date, Integer, Text, TypeDecorator, Float
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import UserRole, Status, CaseStatus, CheckStatus, NotificationCategory, NotificationChannel
from datetime import datetime

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
    city = Column(String(100), nullable=True)  # Replaces short_code
    contact_person = Column(String(255))
    phone = Column(String(50))
    email = Column(String(255))
    address = Column(Text)
    report_format = Column(String(50))
    customer_agreement = Column(String(255), nullable=True)
    active_status = Column(Integer, default=1)  # 0 for Off, 1 for On (Replaces package_enabled)
    status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    pricing_config = Column(JSONEncodedDict) # e.g. {"employment": 100, "education": 50}

class Partner(Base):
    __tablename__ = "partners"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False) # Organization
    executive_lead = Column(String(255))
    contact_points = Column(String(255)) # Email/Phone or JSON
    regional_cluster = Column(String(255))
    status = Column(String(50), default=Status.ACTIVE)
    cloud_status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), index=True)
    phone = Column(String(20))
    dob = Column(Date)
    client_emp_code = Column(String(50), nullable=True)
    address_details = Column(JSONEncodedDict)
    gender = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    documents = Column(JSONEncodedList) # List of Cloudinary URLs/Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)



class Batch(Base):
    __tablename__ = "batches"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(36), ForeignKey("customers.id"), index=True)
    batch_no = Column(String(50), unique=True, index=True)
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
    qa_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    qc_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    received_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    completed_date = Column(DateTime(timezone=True), nullable=True, index=True)
    tat_days = Column(Integer, default=0)
    verifier_revoke_count = Column(Integer, default=0)
    qc_revoke_count = Column(Integer, default=0)
    is_in_tat = Column(Integer, default=1) # 1 for In-TAT, 0 for Out-TAT
    ai_summary = Column(Text, nullable=True) # AI-generated executive summary

    # Relationships
    candidate = relationship("Candidate", backref="cases")
    customer = relationship("Customer", backref="cases")
    batch = relationship("Batch", backref="cases")
    assigned_user = relationship("User", foreign_keys=[assigned_to], backref="assigned_cases")
    qa_user = relationship("User", foreign_keys=[qa_id], backref="qa_cases")
    qc_user = relationship("User", foreign_keys=[qc_id], backref="qc_cases")
    checks = relationship("VerificationCheck", back_populates="case", cascade="all, delete-orphan")

class VerificationCheck(Base):
    __tablename__ = "verification_checks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    case = relationship("Case", back_populates="checks")
    check_type = Column(String(100), index=True) # Education, Employment, etc.
    status = Column(String(50), default=CheckStatus.INTERIM, index=True)
    data = Column(JSONEncodedDict) # Verification details
    digital_token = Column(String(100), unique=True, nullable=True) # For candidate link
    verifier_remarks = Column(Text)
    verified_date = Column(DateTime(timezone=True), nullable=True, index=True)
    rate = Column(Float, default=0.0)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    action = Column(String(255), index=True)
    resource_id = Column(String(100), index=True, nullable=True) # ID of Case, Batch, etc.
    details = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
class CaseComment(Base):
    __tablename__ = "case_comments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
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
    is_read = Column(Integer, default=0, index=True) # 0 for unread, 1 for read
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", backref="notifications")
    case_item = relationship("Case")
