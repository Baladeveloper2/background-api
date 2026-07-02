
@router.post("/insufficiencies/{id}/respond")
async def client_respond_insufficiency(
    id: str,
    data: schemas.ClientRespondInsufficiencyRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Client submits their response and documents for an insufficiency."""
    stmt = select(models.Insufficiency).filter(models.Insufficiency.id == id).options(joinedload(models.Insufficiency.case))
    res = await db.execute(stmt)
    insuff = res.scalar_one_or_none()
    
    if not insuff:
        raise HTTPException(status_code=404, detail="Insufficiency not found")
        
    if insuff.status not in ["PENDING", "NEED_MORE_INFO"]:
        raise HTTPException(status_code=400, detail="Cannot respond to this insufficiency at the current status")
        
    now = datetime.utcnow()
    insuff.status = "SUBMITTED"
    insuff.response_at = now
    if data.documents:
        insuff.documents = data.documents
    insuff.updated_at = now
    insuff.updated_by = current_user.id
    
    existing_tl = insuff.timeline or []
    existing_tl.append({
        "event": "SUBMITTED",
        "title": "Documents Submitted",
        "description": data.remarks,
        "timestamp": now.isoformat(),
        "actor": current_user.full_name or current_user.email
    })
    insuff.timeline = existing_tl
    
    # Add a case comment for audit
    comment = models.CaseComment(
        case_id=insuff.case_id,
        user_id=current_user.id,
        content=f"Client responded to insufficiency: {data.remarks}"
    )
    db.add(comment)
    
    await db.commit()
    return {"message": "Response submitted successfully"}

@router.get("/insufficiencies/review/queue")
async def get_insufficiency_review_queue(
    client_id: Optional[str] = None,
    candidate_id: Optional[str] = None,
    check_id: Optional[str] = None,
    priority: Optional[str] = None,
    verifier_id: Optional[str] = None,
    db: AsyncSession = Depends(get_read_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get the queue of insufficiencies waiting for review."""
    stmt = select(models.Insufficiency).filter(
        models.Insufficiency.status == "SUBMITTED",
        models.Insufficiency.is_resolved == False
    ).options(
        joinedload(models.Insufficiency.case).joinedload(models.Case.candidate),
        joinedload(models.Insufficiency.check)
    )
    
    if client_id:
        stmt = stmt.join(models.Case).filter(models.Case.customer_id == client_id)
    if candidate_id:
        stmt = stmt.join(models.Case).filter(models.Case.candidate_id == candidate_id)
    if check_id:
        stmt = stmt.filter(models.Insufficiency.check_id == check_id)
    if priority:
        stmt = stmt.filter(models.Insufficiency.priority == priority)
    
    res = await db.execute(stmt)
    items = res.unique().scalars().all()
    
    results = []
    for i in items:
        results.append({
            "id": i.id,
            "case_id": i.case_id,
            "case_ref_no": i.case.case_ref_no if i.case else None,
            "candidate_name": i.case.candidate.full_name if i.case and i.case.candidate else None,
            "customer_id": i.case.customer_id if i.case else None,
            "check_name": i.check.check_type if i.check else None,
            "priority": i.priority,
            "due_date": i.due_date,
            "status": i.status,
            "message": i.message,
            "raised_by": i.raised_by,
            "created_at": i.created_at,
            "response_at": i.response_at
        })
        
    return results

@router.post("/insufficiencies/{id}/review")
async def verifier_review_insufficiency(
    id: str,
    data: schemas.VerifierReviewInsufficiencyRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Verifier approves, rejects, or requests more info on a submitted insufficiency."""
    stmt = select(models.Insufficiency).filter(models.Insufficiency.id == id).options(joinedload(models.Insufficiency.case))
    res = await db.execute(stmt)
    insuff = res.scalar_one_or_none()
    
    if not insuff:
        raise HTTPException(status_code=404, detail="Insufficiency not found")
        
    if insuff.status != "SUBMITTED":
        raise HTTPException(status_code=400, detail="Insufficiency is not in SUBMITTED state")
        
    action = data.action.upper()
    now = datetime.utcnow()
    existing_tl = insuff.timeline or []
    
    if action == "APPROVE":
        insuff.status = "ACCEPTED"
        insuff.is_resolved = True
        insuff.resolved_at = now
        insuff.resolved_by = current_user.id
        insuff.resolved_remarks = data.remarks or "Documents Accepted"
        
        existing_tl.append({
            "event": "ACCEPTED",
            "title": "Documents Accepted",
            "description": data.remarks or "Documents Accepted by Verifier",
            "timestamp": now.isoformat(),
            "actor": current_user.full_name or current_user.email
        })
        
        # Resolve the specific check
        if insuff.check_id:
            check_stmt = select(models.VerificationCheck).filter(models.VerificationCheck.id == insuff.check_id)
            check_res = await db.execute(check_stmt)
            check = check_res.scalar_one_or_none()
            if check:
                check.status = enums.CheckStatus.WIP
        
        # Check if there are any other unresolved insufficiencies for this case
        rem_stmt = select(func.count(models.Insufficiency.id)).filter(
            models.Insufficiency.case_id == insuff.case_id,
            models.Insufficiency.is_resolved == False,
            models.Insufficiency.id != id
        )
        rem_res = await db.execute(rem_stmt)
        remaining = rem_res.scalar() or 0
        if remaining == 0:
            insuff.case.status = enums.CaseStatus.IN_VERIFICATION # Move case back to WIP
            
    elif action == "REJECT":
        if not data.remarks:
            raise HTTPException(status_code=400, detail="Remarks are mandatory for REJECT action")
            
        insuff.status = "REJECTED"
        existing_tl.append({
            "event": "REJECTED",
            "title": "Documents Rejected",
            "description": data.remarks,
            "timestamp": now.isoformat(),
            "actor": current_user.full_name or current_user.email
        })
        
    elif action == "NEED_MORE_INFO":
        if not data.remarks:
            raise HTTPException(status_code=400, detail="Remarks are mandatory for NEED_MORE_INFO action")
            
        insuff.status = "NEED_MORE_INFO"
        existing_tl.append({
            "event": "NEED_MORE_INFO",
            "title": "Need More Information",
            "description": data.remarks,
            "timestamp": now.isoformat(),
            "actor": current_user.full_name or current_user.email
        })
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    insuff.timeline = existing_tl
    insuff.updated_at = now
    insuff.updated_by = current_user.id
    
    comment = models.CaseComment(
        case_id=insuff.case_id,
        user_id=current_user.id,
        content=f"Verifier {action} insufficiency: {data.remarks or ''}"
    )
    db.add(comment)
    
    await db.commit()
    return {"message": f"Insufficiency {action.lower()}ed successfully"}
