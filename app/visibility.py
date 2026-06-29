from sqlalchemy import or_
from . import models

def get_tenant_filters(current_user: models.User, model_class):
    """
    Returns a SQLAlchemy filter condition for the given model_class based on the current user's role and hierarchy.
    Supported models: Zone, Customer, Branch, User, Candidate, Case
    """
    # 1. Super Admin sees everything
    role_name = current_user.role_rel.name.upper() if current_user.role_rel else str(current_user.role).upper()
    
    if role_name in ["SUPER ADMIN", "SUPER_ADMIN", "SYSTEM ADMIN"]:
        return True # No filter, all records visible

    # 2. Zone Admin sees their Zone, and all Customers/Branches/Users in that Zone
    if role_name == "ZONE_ADMIN" or role_name == "ZONE ADMIN":
        if not current_user.zone_id:
            return False # Invalid configuration, block access

        if model_class == models.Zone:
            return model_class.id == current_user.zone_id
        if hasattr(model_class, 'zone_id'):
            return model_class.zone_id == current_user.zone_id
        
        # If model doesn't have zone_id but has customer_id (like Branch, Candidate, Case), we need to join or we rely on the fact that customer_id is tied to zone_id.
        # But wait, User has zone_id, customer_id, branch_id.
        # Case has customer_id. 
        # Since this is a simple filter function, if the model doesn't have zone_id directly, we might need a join in the route.
        # For now, let's assume if it has customer_id, we just return True and let the route handle the join, or we can't do it here easily.
        # Let's check if the model has customer_id:
        if hasattr(model_class, 'customer_id'):
            # The route must join Customer to filter by Customer.zone_id == current_user.zone_id
            # We return None to indicate the route needs to handle it.
            return None

    # 3. Customer Head sees their Customer, and all Branches/Users in that Customer
    if role_name == "CUSTOMER_HEAD" or role_name == "CUSTOMER HEAD" or role_name == "CUSTOMER":
        if not current_user.customer_id:
            return False
        
        if model_class == models.Zone:
            # Can see their own zone
            return model_class.id == current_user.zone_id
        if model_class == models.Customer:
            return model_class.id == current_user.customer_id
        if hasattr(model_class, 'customer_id'):
            return model_class.customer_id == current_user.customer_id

    # 4. Branch level users see only their Branch
    if role_name in ["BRANCH_ADMIN", "BRANCH ADMIN", "HR", "RECRUITER", "VERIFIER", "DATA_ENTRY", "DATA ENTRY", "VIEWER"]:
        # Some of these might not be branch restricted if they are global verifiers, but let's assume if they have a customer_id and branch_id they are restricted.
        if current_user.customer_id and current_user.branch_id:
            if model_class == models.Customer:
                return model_class.id == current_user.customer_id
            if model_class == models.Branch:
                return model_class.id == current_user.branch_id
            if hasattr(model_class, 'branch_id'):
                return model_class.branch_id == current_user.branch_id
            # If the model only has customer_id but not branch_id, they can see it if it belongs to their customer?
            # Or should they only see records tied to their branch?
            # Cases and Candidates might only have customer_id or both.
            if hasattr(model_class, 'customer_id'):
                return model_class.customer_id == current_user.customer_id

        elif current_user.customer_id:
            # Fallback if no branch_id is assigned (maybe a customer-level HR)
            if model_class == models.Customer:
                return model_class.id == current_user.customer_id
            if hasattr(model_class, 'customer_id'):
                return model_class.customer_id == current_user.customer_id

    # Default deny if none of the above matched
    return False

